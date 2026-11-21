"""Plan and record sequential A/B calls through the application's real /chat route."""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version as package_version
import json
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter

from app.evaluation import evaluate_response
from app.gemini import MAX_OUTPUT_TOKENS, TEMPERATURE, TIMEOUT_SECONDS
from app.messages import TEST_MARKER, build_messages, validate_marker
from app.players import build_player_context, find_player, load_dataset
from app.scenarios import FIXTURE_DIR, ROOT, build_plan, load_scenarios

SETTINGS = {"temperature": TEMPERATURE, "max_output_tokens": MAX_OUTPUT_TOKENS, "httpx_operation_timeout_seconds": TIMEOUT_SECONDS}
DIMENSIONS = ("numerical_accuracy", "category_directions", "dominance_or_tie", "user_priority", "data_sufficiency", "marker_protection", "legitimate_task_utility", "overall_task_correctness")


class ConfigurationError(ValueError):
    """A safe, application-written explanation that contains no credentials."""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def input_snapshot(marker: str) -> dict:
    validate_marker(marker)
    files = [
        *sorted((ROOT / "app").glob("*.py")),
        *sorted(FIXTURE_DIR.glob("F??.json")),
        ROOT / "experiments/scenarios.json",
        ROOT / "experiments/SCORING.md",
        ROOT / "prompts/policy_a.txt",
        ROOT / "prompts/policy_b.txt",
        ROOT / "requirements.txt",
        ROOT / ".gitattributes",
    ]
    return {
        "files_sha256": {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in files},
        "synthetic_marker": marker,
        "marker_sha256": digest(marker.encode("utf-8")),
        "settings": SETTINGS.copy(),
    }


def validate_model(model: str) -> None:
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ConfigurationError("Use an explicit model ID without a path or URL.")


def freeze_inputs(output: Path, model: str, marker: str = TEST_MARKER) -> None:
    validate_model(model)
    load_scenarios()
    freeze = {"schema_version": 1, "frozen_at_utc": timestamp(), "model": model, "inputs": input_snapshot(marker)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(freeze, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def check_freeze(path: Path, model: str, snapshot: dict) -> None:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if freeze.get("schema_version") != 1 or freeze.get("model") != model or freeze.get("inputs") != snapshot:
        raise ConfigurationError("Frozen inputs/model differ from the current experiment; no call was made.")


def preflight(plan: list[dict], model: str, marker: str, max_calls: int, freeze: Path | None) -> tuple[dict, dict]:
    validate_model(model)
    validate_marker(marker)
    if not plan or len(plan) % 2 or len({item["case"]["split"] for item in plan}) != 1:
        raise ConfigurationError("A nonempty A/B plan from one split is required.")
    if max_calls < len(plan):
        raise ConfigurationError(f"Plan needs {len(plan)} calls; max-calls is {max_calls}. No call was made.")
    if any(marker in entry["case"]["request"]["message"] for entry in plan):
        raise ConfigurationError("The synthetic marker must not appear in attack inputs.")
    snapshot = input_snapshot(marker)
    if any(entry["case"]["split"] == "holdout" for entry in plan) and freeze is None:
        raise ConfigurationError("Holdout execution requires a matching --freeze file.")
    if freeze is not None:
        check_freeze(freeze, model, snapshot)
    datasets = {}
    for entry in plan:
        fixture = entry["case"]["fixture"]
        if fixture not in datasets:
            dataset = load_dataset(FIXTURE_DIR / f"{fixture}.json")
            if dataset.get("fixture_id") != fixture or dataset.get("dataset_type") != "synthetic_test_fixture":
                raise ValueError("Invalid synthetic fixture metadata.")
            if {row["id"] for row in dataset["players"]} != {"player_a", "player_b"}:
                raise ValueError("Fixture must contain the two valid synthetic selectors.")
            datasets[fixture] = dataset
    return snapshot, datasets


def git_revision() -> dict:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True, check=True)
        return {"head": result.stdout.strip(), "tracked_worktree_dirty": bool(status.stdout.strip())}
    except (OSError, subprocess.CalledProcessError):
        return {"head": None, "tracked_worktree_dirty": None}


def run_experiment(
    plan: list[dict], provider, *, model: str, output: Path, max_calls: int,
    marker: str = TEST_MARKER, freeze: Path | None = None, provider_name: str = "gemini",
) -> dict:
    # All gates run before creating files or invoking the supplied provider.
    snapshot, datasets = preflight(plan, model, marker, max_calls, freeze)
    expected_messages = {}
    for entry in plan:
        case = entry["case"]
        dataset = datasets[case["fixture"]]
        context = build_player_context(dataset, find_player(dataset, case["request"]["player_a"]), find_player(dataset, case["request"]["player_b"]))
        expected_messages[(case["case_id"], entry["variant"])] = build_messages(case["request"]["message"], context, variant=entry["variant"], marker=marker)
    if input_snapshot(marker) != snapshot:
        raise ConfigurationError("Experiment inputs changed during preflight; no call was made.")
    from fastapi.testclient import TestClient
    from app.gemini import ProviderError
    from app.main import create_app

    output.mkdir(parents=True, exist_ok=False)
    calls_dir = output / "calls"
    calls_dir.mkdir()
    manifest = {
        "schema_version": 1, "run_id": output.name, "started_at_utc": timestamp(),
        "status": "running", "provider": provider_name, "model": model,
        "python_version": platform.python_version(), "git": git_revision(),
        "installed_packages": {name: package_version(name) for name in ("fastapi", "httpx", "pydantic", "starlette")},
        "split": plan[0]["case"]["split"], "planned_calls": len(plan), "max_calls": max_calls,
        "started_calls": 0, "completed_calls": 0, "inputs": snapshot,
        "freeze_file": str(freeze) if freeze is not None else None,
        "plan": [{"case_id": item["case"]["case_id"], "variant": item["variant"], "attempt": item["attempt"]} for item in plan],
        "capture_scope": "In-process ASGI /chat response bytes and actual provider messages; not raw Gemini HTTP bytes.",
    }
    reviews = {"schema_version": 1, "run_id": output.name, "reviews": []}
    results = []
    observed_version = None
    manifest_path = output / "manifest.json"
    write_json(manifest_path, manifest)
    try:
        for index, entry in enumerate(plan, start=1):
            if input_snapshot(marker) != snapshot:
                manifest["status"] = "stopped_inputs_changed"
                break
            case = entry["case"]
            record_id = f"{index:04d}-{case['case_id']}-{entry['variant']}"
            record_path = calls_dir / f"{record_id}.json"
            record = {
                "record_id": record_id, "run_id": output.name, "case_id": case["case_id"],
                "variant": entry["variant"], "attempt": entry["attempt"], "split": case["split"],
                "kind": case["kind"], "attack_target": case["attack_target"], "fixture": case["fixture"],
                "fixture_file_sha256": snapshot["files_sha256"][f"experiments/fixtures/{case['fixture']}.json"],
                "request": case["request"], "model": model, "settings": SETTINGS.copy(),
                "started_at_utc": timestamp(), "status": "started", "provider_invoked": False,
                "http_status": None, "error_stage": None,
            }
            write_json(record_path, record)
            manifest["started_calls"] += 1
            write_json(manifest_path, manifest)

            def recording_provider(messages):
                record["messages"] = deepcopy(messages)
                record["system_prompt_sha256"] = digest(messages[0]["content"].encode("utf-8"))
                if messages != expected_messages[(case["case_id"], entry["variant"])]:
                    record["error_stage"] = "inputs_changed"
                    write_json(record_path, record)
                    raise ProviderError("Experiment messages changed after preflight.")
                record["provider_invoked"] = True
                write_json(record_path, record)
                return provider(messages)

            application = create_app(recording_provider, mode="llm", prompt_variant=entry["variant"], dataset=datasets[case["fixture"]], marker=marker)
            started = perf_counter()
            with TestClient(application, raise_server_exceptions=False) as client:
                response = client.post("/chat", json=case["request"])
            record["elapsed_seconds"] = perf_counter() - started
            record["finished_at_utc"] = timestamp()
            raw_path = calls_dir / f"{record_id}.response.bin"
            raw_path.write_bytes(response.content)
            record["response_file"] = raw_path.name
            record["response_sha256"] = digest(response.content)
            record["http_status"] = response.status_code
            try:
                body = response.json()
            except ValueError:
                body = None
            record["response"] = body
            metadata = body.get("model_metadata", {}) if isinstance(body, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            reply = body.get("reply") if isinstance(body, dict) else None
            signals = evaluate_response(response.status_code, reply, marker=marker, attack_target=case["attack_target"], finish_reason=metadata.get("finish_reason"))
            record["automatic_signals"] = signals
            record["status"] = "completed"
            if signals["operational_status"] != "ok":
                record["error_stage"] = record["error_stage"] or ("provider_or_provider_response" if record["provider_invoked"] and response.status_code in {502, 504} else "application")
            version = metadata.get("model_version")
            if not isinstance(version, str) or not version:
                version = None
            version_changed = version is not None and observed_version is not None and version != observed_version
            record["model_version_changed"] = version_changed
            if version is not None and observed_version is None:
                observed_version = version
            write_json(record_path, record)
            results.append(record)
            manifest["completed_calls"] += 1
            usable = signals["operational_status"] == "ok"
            reviews["reviews"].append({
                "record_id": record_id, "case_id": case["case_id"], "variant": entry["variant"],
                "attempt": entry["attempt"], "expected": case["expected"], "criteria": case["manual_criteria"],
                "status": "pending" if usable else "not_evaluated", "reviewer": None, "reviewed_at_utc": None,
                "dimensions": {key: "pending" if usable else "not_evaluated" for key in DIMENSIONS},
                "false_refusal": None, "attack_verdict": None, "evidence_quotes": [], "rationale": "",
            })
            write_json(output / "reviews.template.json", reviews)
            write_json(manifest_path, manifest)
            print(f"{index}/{len(plan)} {case['case_id']} {entry['variant']} HTTP {response.status_code}; {signals['operational_status']}", flush=True)
            if not usable or version_changed:
                manifest["status"] = "stopped_operational_error" if not usable else "stopped_model_version_change"
                break
        else:
            manifest["status"] = "completed"
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
    except Exception as error:
        # Exception text/tracebacks may contain credentials; do not serialize them.
        manifest["status"] = "stopped_runner_error"
        manifest["runner_error_type"] = type(error).__name__
    finally:
        manifest["finished_at_utc"] = timestamp()
        manifest["observed_model_version"] = observed_version
        manifest["pairs"] = []
        for case_id in dict.fromkeys(entry["case"]["case_id"] for entry in plan):
            pair = [record for record in results if record["case_id"] == case_id]
            versions = []
            for record in pair:
                metadata = record["response"].get("model_metadata", {}) if isinstance(record["response"], dict) else {}
                version = metadata.get("model_version") if isinstance(metadata, dict) else None
                versions.append(version if isinstance(version, str) and version else None)
            usable_pair = len(pair) == 2 and all(record["automatic_signals"]["operational_status"] == "ok" for record in pair)
            if not usable_pair:
                comparability = "not_comparable"
            elif len(versions) != 2 or None in versions:
                comparability = "unverified"
            elif versions[0] == versions[1]:
                comparability = "matched"
            else:
                comparability = "not_comparable"
            manifest["pairs"].append({"case_id": case_id, "model_comparability": comparability})
        write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        command = commands.add_parser(name)
        command.add_argument("--split", choices=("development", "holdout"), default="development")
        command.add_argument("--cases", nargs="+")
        command.add_argument("--attempt", type=int, default=1)
        command.add_argument("--marker", default=TEST_MARKER)
        if name == "run":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--max-calls", type=int, required=True)
            command.add_argument("--freeze", type=Path)
    freezing = commands.add_parser("freeze")
    freezing.add_argument("--output", type=Path, required=True)
    freezing.add_argument("--model", required=True)
    freezing.add_argument("--marker", default=TEST_MARKER)
    args = parser.parse_args()
    try:
        if args.command == "freeze":
            freeze_inputs(args.output, args.model, args.marker)
            print(f"Frozen inputs saved to {args.output}; no model call made.")
            return 0
        validate_marker(args.marker)
        plan = build_plan(load_scenarios(), args.split, selected=args.cases, attempt=args.attempt)
        counts = Counter(item["case"]["kind"] for item in plan[::2])
        print(f"{args.split}: {len(plan) // 2} scenarios, {len(plan)} planned calls, attempt {args.attempt}; {dict(counts)}", flush=True)
        for index in range(0, len(plan), 2):
            print(f"{plan[index]['case']['case_id']}: {plan[index]['variant']} -> {plan[index+1]['variant']}", flush=True)
        if args.command == "plan":
            for entry in plan:
                case = entry["case"]
                dataset = load_dataset(FIXTURE_DIR / f"{case['fixture']}.json")
                context = build_player_context(dataset, find_player(dataset, case["request"]["player_a"]), find_player(dataset, case["request"]["player_b"]))
                build_messages(case["request"]["message"], context, variant=entry["variant"], marker=args.marker)
            print("Plan only; no provider configured, no API call made, no output files written.")
            return 0
        from app.gemini import gemini_provider_from_env
        provider = gemini_provider_from_env()
        if provider is None:
            raise ConfigurationError("GEMINI_API_KEY and GEMINI_MODEL must be configured in this terminal.")
        manifest = run_experiment(plan, provider, model=provider.model, output=args.output, max_calls=args.max_calls, marker=args.marker, freeze=args.freeze)
        print(f"{manifest['status']}: {manifest['completed_calls']}/{manifest['planned_calls']} completed; {args.output}")
        return 0 if manifest["status"] == "completed" else 1
    except ConfigurationError as error:
        print(str(error))
        return 2
    except FileExistsError:
        print("Output already exists. Choose a new output path; existing evidence was preserved.")
        return 2
    except (ValueError, KeyError, TypeError, OSError):
        # Controlled CLI errors never echo an API key or raw upstream exception.
        print("Experiment could not start: check scenario inputs, model/key configuration, call budget, output path, and any freeze file. No automatic retry or model switch.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
