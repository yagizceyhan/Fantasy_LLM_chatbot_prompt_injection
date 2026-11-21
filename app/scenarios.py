"""Load the fixed M01-M20 design and build explicit, single-attempt A/B plans."""

import json
from pathlib import Path

from app.evaluation import ATTACK_TARGETS
from app.validation import validate_message

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = ROOT / "experiments/scenarios.json"
FIXTURE_DIR = ROOT / "experiments/fixtures"
DEVELOPMENT = {"M01", "M03", "M04", "M05", "M07", "M08", "M10", "M11", "M13", "M15", "M17", "M19"}
KINDS = {"normal", "control", "attack"}
FIELDS = {"case_id", "split", "kind", "attack_target", "fixture", "request", "rules", "techniques", "expected", "manual_criteria"}


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("cases"), list):
        raise ValueError("Unsupported scenario document.")
    cases = document["cases"]
    if any(not isinstance(case, dict) or set(case) != FIELDS or not isinstance(case["case_id"], str) for case in cases):
        raise ValueError("Invalid scenario fields.")
    if len(cases) != 20 or {case["case_id"] for case in cases} != {f"M{i:02d}" for i in range(1, 21)}:
        raise ValueError("Exactly one of each case M01-M20 is required.")
    for case in cases:
        expected_split = "development" if case["case_id"] in DEVELOPMENT else "holdout"
        if case["split"] != expected_split or not isinstance(case["kind"], str) or case["kind"] not in KINDS:
            raise ValueError("Invalid case split or kind.")
        target = case["attack_target"]
        if (case["kind"] == "attack" and target not in ATTACK_TARGETS) or (case["kind"] != "attack" and target is not None):
            raise ValueError("Attack targets must match case intent.")
        if not isinstance(case["fixture"], str) or case["fixture"] not in {f"F{i:02d}" for i in range(1, 8)}:
            raise ValueError("Unknown fixture.")
        request = case["request"]
        if not isinstance(request, dict) or set(request) != {"message", "player_a", "player_b"}:
            raise ValueError("Scenario requests must contain only the three API fields.")
        validate_message(request["message"])
        if (request["player_a"], request["player_b"]) != ("player_a", "player_b"):
            raise ValueError("Use valid A/B selectors; ask about absent C in the message.")
        for field in ("rules", "techniques", "manual_criteria"):
            if not isinstance(case[field], list) or not case[field] or any(not isinstance(x, str) or not x.strip() for x in case[field]):
                raise ValueError(f"A nonempty {field} list is required.")
        if not isinstance(case["expected"], str) or not case["expected"].strip():
            raise ValueError("Expected behavior is required.")
    return sorted(cases, key=lambda case: case["case_id"])


def build_plan(
    cases: list[dict],
    split: str,
    *,
    selected: list[str] | None = None,
    attempt: int = 1,
) -> list[dict]:
    if split not in {"development", "holdout"} or attempt < 1:
        raise ValueError("Choose development/holdout and a positive attempt number.")
    eligible = [case for case in cases if case["split"] == split]
    if selected is not None:
        if not selected or len(set(selected)) != len(selected) or not set(selected) <= {case["case_id"] for case in eligible}:
            raise ValueError("Selected cases must be unique and belong to the chosen split.")
        eligible = [case for case in eligible if case["case_id"] in selected]
    plan = []
    for index, case in enumerate(eligible):
        variants = ("A", "B") if (index + attempt - 1) % 2 == 0 else ("B", "A")
        for variant in variants:
            plan.append({"case": case, "variant": variant, "attempt": attempt})
    if not plan:
        raise ValueError("An empty experiment is not allowed.")
    return plan
