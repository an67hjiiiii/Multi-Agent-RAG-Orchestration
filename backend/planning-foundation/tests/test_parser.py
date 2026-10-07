import json
import unittest

from planning_foundation import PlanningInput, parse_planning_output
from tests.helpers import input_data, plan_data, planning_input


class BoundaryTests(unittest.TestCase):
    def parse(self, data):
        return parse_planning_output(json.dumps(data), planning_input())

    def assert_invalid(self, result, code):
        self.assertEqual(result.status, "invalid")
        self.assertIsNone(result.plan)
        self.assertIn(code, {issue.code for issue in result.issues})

    def test_plain_json_is_valid_and_preserves_content(self):
        result = self.parse(plan_data())
        self.assertEqual(result.status, "valid")
        self.assertFalse(result.repairs)
        self.assertEqual(result.plan.tasks[0].description, plan_data()["tasks"][0]["description"])

    def test_one_outer_json_fence_is_safely_unwrapped(self):
        for label in ("json", "JSON", ""):
            raw = f"```{label}\n{json.dumps(plan_data())}\n```"
            with self.subTest(label=label):
                result = parse_planning_output(raw, planning_input())
                self.assertEqual(result.status, "repaired")
                self.assertEqual(result.repairs, ("unwrap_json_fence",))

    def test_bom_and_fence_repairs_are_recorded(self):
        raw = "\ufeff```json\n" + json.dumps(plan_data()) + "\n```"
        result = parse_planning_output(raw, planning_input())
        self.assertEqual(result.status, "repaired")
        self.assertEqual(result.repairs, ("strip_bom", "unwrap_json_fence"))

    def test_trailing_prose_or_second_object_is_not_extracted(self):
        raw = json.dumps(plan_data())
        for text in ("Here is a plan: " + raw, raw + "\n{}", raw + "\nDone"):
            with self.subTest(text=text[:30]):
                self.assert_invalid(parse_planning_output(text, planning_input()), "invalid_json")

    def test_broken_or_non_json_fence_is_rejected(self):
        raw = json.dumps(plan_data())
        for text in (f"```python\n{raw}\n```", f"```json\n{raw}", f"```json\n{raw}\n```\nDone"):
            with self.subTest(text=text[:30]):
                self.assert_invalid(parse_planning_output(text, planning_input()), "invalid_format")

    def test_invalid_json_is_not_guessed_or_repaired(self):
        for text in ("", "  ", "{'tasks': []}", '{"tasks": [],}', '{"x": NaN}'):
            with self.subTest(text=text):
                self.assert_invalid(parse_planning_output(text, planning_input()), "invalid_json")

    def test_non_object_json_and_non_string_output_are_rejected(self):
        for text in ("null", "[]", "3", '"text"', "true", None, {}):
            with self.subTest(text=text):
                self.assert_invalid(parse_planning_output(text, planning_input()), "invalid_format")

    def test_duplicate_keys_are_rejected_at_any_depth(self):
        for text in ('{"request_id":"a","request_id":"b"}', '{"nested":{"id":"a","id":"b"}}'):
            with self.subTest(text=text):
                self.assert_invalid(parse_planning_output(text, planning_input()), "duplicate_key")

    def test_schema_errors_are_returned_with_paths(self):
        data = plan_data()
        data["tasks"][0]["title"] = 17
        result = self.parse(data)
        self.assert_invalid(result, "schema_validation")
        self.assertEqual(result.issues[0].path, ("tasks", 0, "title"))

    def test_unknown_output_fields_are_rejected(self):
        data = plan_data()
        data["invented"] = True
        self.assert_invalid(self.parse(data), "schema_validation")

    def test_request_mismatch_is_rejected(self):
        data = plan_data()
        data["request_id"] = "REQ-other"
        self.assert_invalid(self.parse(data), "request_mismatch")

    def test_task_budget_is_checked_against_input(self):
        data = input_data()
        data["max_tasks"] = 1
        result = parse_planning_output(json.dumps(plan_data()), PlanningInput.model_validate(data))
        self.assert_invalid(result, "task_limit_exceeded")

    def test_unknown_roles_are_rejected_and_role_names_are_extensible(self):
        data = plan_data()
        data["tasks"][0]["role"] = "custom-role"
        self.assert_invalid(self.parse(data), "unknown_role")
        source = input_data()
        source["available_roles"] = ["database", "custom-role"]
        result = parse_planning_output(json.dumps(data), PlanningInput.model_validate(source))
        self.assertEqual(result.status, "valid")

    def test_unknown_evidence_is_rejected(self):
        data = plan_data()
        data["tasks"][0]["evidence_ids"] = ["E-missing"]
        self.assert_invalid(self.parse(data), "unknown_evidence")

    def test_existing_entities_cannot_be_dropped_or_rewritten(self):
        for name in ("obligations", "concerns"):
            data = plan_data()
            data[name][0]["description"] = "Changed meaning"
            with self.subTest(name=name):
                self.assert_invalid(self.parse(data), "input_entity_changed")
        source = input_data()
        source["obligations"].append({"id": "O-extra", "description": "Do not omit this"})
        result = parse_planning_output(json.dumps(plan_data()), PlanningInput.model_validate(source))
        self.assert_invalid(result, "input_entity_changed")

    def test_raw_request_can_be_used_without_prior_analysis(self):
        data = plan_data()
        for task in data["tasks"]:
            task["evidence_ids"] = []
        source = PlanningInput(request_id="REQ-001", request="Design an API and database")
        self.assertEqual(parse_planning_output(json.dumps(data), source).status, "valid")

    def test_partial_plan_is_explicit_and_has_warning(self):
        data = plan_data()
        data["tasks"] = [data["tasks"][0]]
        data["dependencies"] = []
        data["unassigned_obligation_ids"] = ["O-data"]
        result = self.parse(data)
        self.assertEqual(result.status, "valid")
        self.assertFalse(result.plan.is_complete)
        self.assertEqual(result.issues[0].severity, "warning")
        self.assertEqual(result.issues[0].code, "partial_plan")

    def test_invalid_output_keeps_attempted_normalization_audit(self):
        result = parse_planning_output("```json\n{}\n```", planning_input())
        self.assert_invalid(result, "schema_validation")
        self.assertEqual(result.repairs, ("unwrap_json_fence",))

    def test_output_limit_and_deep_non_object_json(self):
        result = parse_planning_output(json.dumps(plan_data()), planning_input(), max_output_chars=10)
        self.assert_invalid(result, "output_too_large")
        deep = parse_planning_output("[" * 2000 + "]" * 2000, planning_input())
        self.assertEqual(deep.status, "invalid")
        self.assertIsNone(deep.plan)
        self.assertIn(deep.issues[0].code, {"invalid_json", "invalid_format"})
        for value in (0, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_planning_output("{}", planning_input(), max_output_chars=value)


if __name__ == "__main__":
    unittest.main()
