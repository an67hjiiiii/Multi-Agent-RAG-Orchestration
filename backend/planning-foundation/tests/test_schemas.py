import json
import tempfile
import unittest
from pathlib import Path

from planning_foundation.schemas import SCHEMA_MODELS, export_schemas
from tests.helpers import ROOT


class SchemaTests(unittest.TestCase):
    def test_committed_schemas_match_models(self):
        for name, model in SCHEMA_MODELS.items():
            with self.subTest(name=name):
                stored = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
                self.assertEqual(stored, model.model_json_schema())

    def test_main_schemas_forbid_unknown_fields(self):
        for model in SCHEMA_MODELS.values():
            with self.subTest(model=model.__name__):
                self.assertFalse(model.model_json_schema()["additionalProperties"])

    def test_output_schema_contains_all_core_models(self):
        definitions = SCHEMA_MODELS["repair_result"].model_json_schema()["$defs"]
        self.assertTrue({"Obligation", "Concern", "Task", "TaskPlan", "SemanticDependency"} <= set(definitions))

    def test_schema_export_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = export_schemas(Path(directory))
            before = [path.read_bytes() for path in paths]
            self.assertEqual(export_schemas(Path(directory)), paths)
            self.assertEqual(before, [path.read_bytes() for path in paths])


if __name__ == "__main__":
    unittest.main()
