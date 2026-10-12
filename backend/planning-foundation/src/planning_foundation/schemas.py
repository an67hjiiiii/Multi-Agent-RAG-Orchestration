"""Export standard JSON Schema contracts without contacting an LLM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import PlanningInput, RepairResult, TaskPlan

SCHEMA_MODELS = {
    "planning_input": PlanningInput,
    "task_plan": TaskPlan,
    "repair_result": RepairResult,
}


def export_schemas(output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, model in SCHEMA_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return tuple(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("schemas"))
    args = parser.parse_args()
    for path in export_schemas(args.output):
        print(path)


if __name__ == "__main__":
    main()
