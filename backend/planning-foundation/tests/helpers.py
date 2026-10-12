import json
from pathlib import Path

from planning_foundation import PlanningInput

ROOT = Path(__file__).resolve().parents[1]


def input_data() -> dict:
    return json.loads((ROOT / "examples" / "planning_input.json").read_text(encoding="utf-8"))


def plan_data() -> dict:
    return json.loads((ROOT / "examples" / "task_plan.json").read_text(encoding="utf-8"))


def planning_input() -> PlanningInput:
    return PlanningInput.model_validate(input_data())
