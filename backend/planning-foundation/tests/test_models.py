import unittest

from pydantic import ValidationError

from planning_foundation import (
    Concern, Obligation, PlanningInput, PlanningIssue, RepairResult,
    SemanticDependency, Task, TaskPlan,
)
from tests.helpers import input_data, plan_data, planning_input


class ContractTests(unittest.TestCase):
    def test_core_models_and_json_round_trip(self):
        plan = TaskPlan.model_validate(plan_data())
        self.assertIsInstance(plan.obligations[0], Obligation)
        self.assertIsInstance(plan.concerns[0], Concern)
        self.assertIsInstance(plan.tasks[0], Task)
        self.assertIsInstance(plan.dependencies[0], SemanticDependency)
        self.assertEqual(TaskPlan.model_validate_json(plan.model_dump_json()), plan)
        source = planning_input()
        self.assertEqual(PlanningInput.model_validate_json(source.model_dump_json()), source)
        result = RepairResult(status="valid", plan=plan)
        self.assertEqual(RepairResult.model_validate_json(result.model_dump_json()), result)

    def test_frozen_models_and_immutable_collections(self):
        plan = TaskPlan.model_validate(plan_data())
        with self.assertRaises(ValidationError):
            plan.request_id = "changed"
        self.assertIsInstance(plan.tasks, tuple)
        self.assertIsInstance(plan.tasks[0].obligation_ids, tuple)

    def test_blank_or_non_string_text_is_rejected(self):
        for description in ("", "  \n ", 12, False, None):
            with self.subTest(description=description), self.assertRaises(ValidationError):
                Obligation(id="O-1", description=description)

    def test_invalid_ids_and_extra_fields_are_rejected(self):
        for identifier in ("", "two words", "../file", 17):
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                Obligation(id=identifier, description="Requirement")
        with self.assertRaises(ValidationError):
            Obligation(id="O-1", description="Requirement", invented_field=True)

    def test_wrong_schema_version_is_rejected(self):
        data = plan_data()
        data["schema_version"] = "2.0"
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)

    def test_task_limit_requires_bounded_integer(self):
        for value in (0, 257, "4", True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PlanningInput(request_id="R-1", request="Design API", max_tasks=value)

    def test_duplicate_entity_ids_are_rejected(self):
        for name in ("obligations", "concerns", "tasks"):
            data = plan_data()
            data[name].append(data[name][0])
            with self.subTest(name=name), self.assertRaises(ValidationError):
                TaskPlan.model_validate(data)

    def test_duplicate_input_ids_and_roles_are_rejected(self):
        for name in ("obligations", "concerns", "evidence", "available_roles"):
            data = input_data()
            data[name].append(data[name][0])
            with self.subTest(name=name), self.assertRaises(ValidationError):
                PlanningInput.model_validate(data)

    def test_task_requires_at_least_one_obligation(self):
        data = plan_data()["tasks"][0]
        data["obligation_ids"] = []
        with self.assertRaises(ValidationError):
            Task.model_validate(data)

    def test_duplicate_task_references_are_rejected(self):
        for name in ("obligation_ids", "concern_ids", "evidence_ids"):
            data = plan_data()["tasks"][0]
            data[name].append(data[name][0])
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Task.model_validate(data)

    def test_unknown_obligation_and_concern_references_are_rejected(self):
        for name in ("obligation_ids", "concern_ids"):
            data = plan_data()
            data["tasks"][0][name] = ["missing"]
            with self.subTest(name=name), self.assertRaises(ValidationError):
                TaskPlan.model_validate(data)
        data = plan_data()
        data["concerns"][0]["obligation_ids"] = ["missing"]
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)
        data = input_data()
        data["concerns"][0]["obligation_ids"] = ["missing"]
        with self.assertRaises(ValidationError):
            PlanningInput.model_validate(data)

    def test_missing_coverage_must_be_explicit(self):
        data = plan_data()
        data["tasks"] = [data["tasks"][0]]
        data["dependencies"] = []
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)
        data["unassigned_obligation_ids"] = ["O-data"]
        self.assertFalse(TaskPlan.model_validate(data).is_complete)

    def test_unassigned_concerns_must_be_explicit(self):
        data = plan_data()
        for task in data["tasks"]:
            task["concern_ids"] = []
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)
        data["unassigned_concern_ids"] = ["C-security"]
        self.assertFalse(TaskPlan.model_validate(data).is_complete)

    def test_unassigned_lists_cannot_conflict_with_assignments(self):
        for name, values in (
            ("unassigned_obligation_ids", ["O-api"]),
            ("unassigned_concern_ids", ["C-security"]),
            ("unassigned_obligation_ids", ["missing"]),
        ):
            data = plan_data()
            data[name] = values
            with self.subTest(name=name, values=values), self.assertRaises(ValidationError):
                TaskPlan.model_validate(data)

    def test_shared_evidence_and_concerns_are_allowed(self):
        plan = TaskPlan.model_validate(plan_data())
        self.assertTrue(plan.is_complete)
        self.assertEqual(plan.tasks[0].evidence_ids, plan.tasks[1].evidence_ids)
        self.assertEqual(plan.tasks[0].concern_ids, plan.tasks[1].concern_ids)

    def test_unknown_dependency_and_self_dependency_are_rejected(self):
        for predecessor in ("T-missing", "T-api"):
            data = plan_data()
            data["dependencies"][0]["predecessor_task_id"] = predecessor
            with self.subTest(predecessor=predecessor), self.assertRaises(ValidationError):
                TaskPlan.model_validate(data)

    def test_duplicate_dependency_is_rejected_even_with_different_kind(self):
        data = plan_data()
        edge = dict(data["dependencies"][0], kind="requires_context")
        data["dependencies"].append(edge)
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)

    def test_dependency_cycle_is_rejected(self):
        data = plan_data()
        data["dependencies"].append({
            "predecessor_task_id": "T-api", "successor_task_id": "T-data",
            "kind": "requires_context", "rationale": "Creates a cycle",
        })
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)

    def test_topological_order_and_independent_tasks(self):
        data = plan_data()
        self.assertEqual(TaskPlan.model_validate(data).topological_task_ids(), ("T-data", "T-api"))
        data["dependencies"] = []
        self.assertEqual(TaskPlan.model_validate(data).topological_task_ids(), ("T-api", "T-data"))

    def test_empty_tasks_are_rejected(self):
        data = plan_data()
        data["tasks"] = []
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(data)

    def test_repair_result_invariants(self):
        plan = TaskPlan.model_validate(plan_data())
        issue = PlanningIssue(code="invalid_json", message="Invalid JSON")
        invalid_cases = (
            {"status": "valid"},
            {"status": "valid", "plan": plan, "issues": (issue,)},
            {"status": "valid", "plan": plan, "repairs": ("strip_bom",)},
            {"status": "repaired", "plan": plan},
            {"status": "invalid"},
            {"status": "invalid", "plan": plan, "issues": (issue,)},
        )
        for data in invalid_cases:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                RepairResult(**data)


if __name__ == "__main__":
    unittest.main()
