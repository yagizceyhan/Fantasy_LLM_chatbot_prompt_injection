from copy import deepcopy
import json

import pytest

from app.scenarios import build_plan, load_scenarios


def test_case_inventory_preserves_splits_and_attack_counts():
    cases = load_scenarios()
    development = [case for case in cases if case["split"] == "development"]
    holdout = [case for case in cases if case["split"] == "holdout"]
    assert len(development) == 12
    assert len(holdout) == 8
    assert sum(case["kind"] == "attack" for case in cases) == 9
    assert sum(case["kind"] == "attack" for case in holdout) == 4
    assert {case["case_id"] for case in cases if case["kind"] == "control"} == {"M09", "M20"}


@pytest.mark.parametrize("split,expected", [("development", 24), ("holdout", 16)])
def test_plan_has_two_variants_and_alternating_order(split, expected):
    plan = build_plan(load_scenarios(), split)
    assert len(plan) == expected
    assert [item["variant"] for item in plan[:4]] == ["A", "B", "B", "A"]
    for index in range(0, len(plan), 2):
        assert plan[index]["case"] == plan[index + 1]["case"]
        assert {plan[index]["variant"], plan[index + 1]["variant"]} == {"A", "B"}


def test_explicit_repeat_preserves_case_identity_and_flips_order():
    plan = build_plan(load_scenarios(), "development", selected=["M13", "M01"], attempt=2)
    assert [(item["case"]["case_id"], item["variant"], item["attempt"]) for item in plan] == [
        ("M01", "B", 2), ("M01", "A", 2), ("M13", "A", 2), ("M13", "B", 2),
    ]


@pytest.mark.parametrize("selected,attempt", [(["M02"], 1), (["M01", "M01"], 1), (["M01"], 0)])
def test_invalid_selections_or_attempts_are_rejected(selected, attempt):
    with pytest.raises(ValueError):
        build_plan(load_scenarios(), "development", selected=selected, attempt=attempt)


def test_corrupt_split_is_rejected(tmp_path):
    cases = deepcopy(load_scenarios())
    cases[0]["split"] = "holdout"
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"schema_version": 1, "cases": cases}), encoding="utf-8")
    with pytest.raises(ValueError, match="split"):
        load_scenarios(source)
