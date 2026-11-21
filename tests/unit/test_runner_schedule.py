import pytest

from app.experiment_runner import run_experiment
from app.scenarios import build_plan, load_scenarios


@pytest.mark.parametrize("delay_seconds", [-1, float("nan"), float("inf"), 61])
def test_invalid_delay_is_rejected_before_any_call_or_output(tmp_path, delay_seconds):
    def provider(_messages):
        pytest.fail("Invalid scheduling must be rejected before a model call.")

    output = tmp_path / "invalid-delay"
    plan = build_plan(load_scenarios(), "development", selected=["M01"])
    with pytest.raises(ValueError, match="finite number"):
        run_experiment(plan, provider, model="synthetic-model", output=output, max_calls=2, delay_seconds=delay_seconds)
    assert not output.exists()
