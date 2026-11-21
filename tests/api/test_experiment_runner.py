from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app import experiment_runner as runner
from app.gemini import ProviderError, ProviderReply
from app.messages import TEST_MARKER
from app.scenarios import build_plan, load_scenarios


MODEL = "synthetic-model"


def plan_for(*ids, split="development"):
    return build_plan(load_scenarios(), split, selected=list(ids))


def reply(text="Stub comparison.", version="synthetic-v1", finish="STOP"):
    return ProviderReply(text=text, metadata={"provider": "test_stub", "requested_model": MODEL, "model_version": version, "finish_reason": finish, "temperature": 0, "max_output_tokens": 2048})


def test_plan_cli_cannot_configure_a_live_provider(monkeypatch, capsys):
    def forbidden():
        pytest.fail("Plan mode must not configure a provider.")

    monkeypatch.setattr("app.gemini.gemini_provider_from_env", forbidden)
    monkeypatch.setattr("sys.argv", ["runner", "plan", "--split", "development"])
    assert runner.main() == 0
    assert "24 planned calls" in capsys.readouterr().out


def test_run_records_actual_route_messages_raw_reply_and_pending_reviews(tmp_path):
    seen = []
    text = f"Do not repair this failure: {TEST_MARKER}; wrong TO 3.0."

    def provider(messages):
        seen.append(messages)
        return reply(text)

    output = tmp_path / "run"
    manifest = runner.run_experiment(plan_for("M13"), provider, model=MODEL, output=output, max_calls=2, provider_name="test_stub")
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((output / "calls").glob("*.json"))]
    assert manifest["status"] == "completed" and manifest["completed_calls"] == 2
    assert len(seen) == 2
    assert [record["variant"] for record in records] == ["A", "B"]
    assert records[0]["messages"][1] == records[1]["messages"][1]
    assert records[0]["messages"][0]["content"] != records[1]["messages"][0]["content"]
    assert {record["fixture_file_sha256"] for record in records} == {manifest["inputs"]["files_sha256"]["experiments/fixtures/F01.json"]}
    for record in records:
        raw = (output / "calls" / record["response_file"]).read_bytes()
        assert sha256(raw).hexdigest() == record["response_sha256"]
        assert json.loads(raw)["reply"] == text == record["response"]["reply"]
        assert record["automatic_signals"]["attack_verdict"] == "succeeded"
        assert record["system_prompt_sha256"] == record["response"]["model_metadata"]["system_prompt_sha256"]
    reviews = json.loads((output / "reviews.template.json").read_text(encoding="utf-8"))["reviews"]
    assert all(review["status"] == "pending" and review["attack_verdict"] is None for review in reviews)
    assert manifest["pairs"] == [{"case_id": "M13", "model_comparability": "matched"}]


@pytest.mark.parametrize("failure,status", [("timeout", 504), ("quota", 502), ("empty", 502)])
def test_operational_failure_stops_without_retry_or_security_verdict(tmp_path, failure, status):
    calls = []

    def provider(messages):
        calls.append(messages)
        if failure == "timeout":
            raise TimeoutError
        if failure == "quota":
            raise ProviderError("Model provider returned HTTP 429.")
        return "   "

    output = tmp_path / "stopped"
    manifest = runner.run_experiment(plan_for("M13", "M15"), provider, model=MODEL, output=output, max_calls=4, provider_name="test_stub")
    record = json.loads(next((output / "calls").glob("*.json")).read_text(encoding="utf-8"))
    assert manifest["status"] == "stopped_operational_error"
    assert len(calls) == manifest["completed_calls"] == 1
    assert record["http_status"] == status
    assert record["automatic_signals"]["attack_verdict"] is None
    assert record["error_stage"] == "provider_or_provider_response"


def test_call_budget_rejection_makes_no_calls_or_output(tmp_path):
    def provider(_messages):
        pytest.fail("Budget failure must precede all calls.")

    output = tmp_path / "over-budget"
    with pytest.raises(ValueError, match="needs 2 calls"):
        runner.run_experiment(plan_for("M01"), provider, model=MODEL, output=output, max_calls=1)
    assert not output.exists()


def test_holdout_without_freeze_is_rejected_before_provider(tmp_path):
    def provider(_messages):
        pytest.fail("Holdout must not run without a freeze.")

    with pytest.raises(ValueError, match="requires a matching"):
        runner.run_experiment(plan_for("M02", split="holdout"), provider, model=MODEL, output=tmp_path / "holdout", max_calls=2)


def test_existing_output_is_never_overwritten(tmp_path):
    def provider(_messages):
        pytest.fail("An existing output must not be overwritten.")

    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        runner.run_experiment(plan_for("M01"), provider, model=MODEL, output=output, max_calls=2)
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_custom_marker_is_identical_in_app_capture_and_evaluator(tmp_path):
    marker = "SYNTHETIC-CUSTOM-PAIR-42"

    def provider(messages):
        assert marker in messages[0]["content"] and TEST_MARKER not in messages[0]["content"]
        return reply(marker, finish="MAX_TOKENS")

    output = tmp_path / "custom-marker"
    manifest = runner.run_experiment(plan_for("M13"), provider, model=MODEL, output=output, max_calls=2, marker=marker, provider_name="test_stub")
    assert manifest["inputs"]["synthetic_marker"] == marker
    for path in (output / "calls").glob("*.json"):
        signals = json.loads(path.read_text(encoding="utf-8"))["automatic_signals"]
        assert signals["attack_verdict"] == "succeeded"
        assert signals["response_complete"] is False


def test_freeze_allows_unchanged_inputs_and_rejects_tampering(tmp_path, monkeypatch):
    freeze = tmp_path / "frozen.json"
    runner.freeze_inputs(freeze, MODEL)
    snapshot = runner.input_snapshot(TEST_MARKER)
    runner.check_freeze(freeze, MODEL, snapshot)
    changed = deepcopy(snapshot)
    changed["files_sha256"]["experiments/scenarios.json"] = "tampered"
    monkeypatch.setattr(runner, "input_snapshot", lambda _marker: changed)

    def provider(_messages):
        pytest.fail("Tampered holdout must not call the provider.")

    with pytest.raises(ValueError, match="differ"):
        runner.run_experiment(plan_for("M02", split="holdout"), provider, model=MODEL, output=tmp_path / "holdout", max_calls=2, freeze=freeze)


def test_matching_freeze_allows_holdout_route(tmp_path):
    freeze = tmp_path / "frozen.json"
    runner.freeze_inputs(freeze, MODEL)
    manifest = runner.run_experiment(plan_for("M02", split="holdout"), lambda _messages: reply(), model=MODEL, output=tmp_path / "holdout", max_calls=2, freeze=freeze, provider_name="test_stub")
    assert manifest["status"] == "completed" and manifest["split"] == "holdout"


def test_returned_model_version_change_stops_further_calls(tmp_path):
    calls = []

    def provider(messages):
        calls.append(messages)
        return reply(version="first" if len(calls) == 1 else "changed")

    manifest = runner.run_experiment(plan_for("M01", "M03"), provider, model=MODEL, output=tmp_path / "version-drift", max_calls=4, provider_name="test_stub")
    assert len(calls) == 2
    assert manifest["status"] == "stopped_model_version_change"
    assert manifest["pairs"][0]["model_comparability"] == "not_comparable"


def test_missing_returned_version_is_unverified_not_matched(tmp_path):
    manifest = runner.run_experiment(plan_for("M01"), lambda _messages: "Stub reply without metadata.", model=MODEL, output=tmp_path / "no-version", max_calls=2, provider_name="test_stub")
    assert manifest["status"] == "completed"
    assert manifest["pairs"][0]["model_comparability"] == "unverified"


def test_inputs_changed_mid_run_stop_before_next_provider_call(tmp_path, monkeypatch):
    stable = runner.input_snapshot(TEST_MARKER)
    changed = deepcopy(stable)
    changed["files_sha256"]["prompts/policy_b.txt"] = "changed"
    calls = []
    monkeypatch.setattr(runner, "input_snapshot", lambda _marker: deepcopy(changed if calls else stable))

    def provider(messages):
        calls.append(messages)
        return reply()

    manifest = runner.run_experiment(plan_for("M01"), provider, model=MODEL, output=tmp_path / "inputs-drift", max_calls=2, provider_name="test_stub")
    assert len(calls) == 1
    assert manifest["status"] == "stopped_inputs_changed"


def test_unexpected_provider_exception_text_is_not_logged(tmp_path):
    secret = "SYNTHETIC-DO-NOT-LOG-EXCEPTION-TEXT"

    def provider(_messages):
        raise RuntimeError(secret)

    output = tmp_path / "unexpected"
    manifest = runner.run_experiment(plan_for("M01"), provider, model=MODEL, output=output, max_calls=2, provider_name="test_stub")
    assert manifest["status"] == "stopped_operational_error"
    for path in output.rglob("*"):
        if path.is_file():
            assert secret.encode("utf-8") not in path.read_bytes()
