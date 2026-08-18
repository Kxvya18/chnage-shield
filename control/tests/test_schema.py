from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from control.schema import apply_locator_patch, validate_workflow_spec
from .helpers import workflow_spec


class WorkflowSchemaTests(SimpleTestCase):
    def test_valid_declarative_workflow(self):
        self.assertEqual(validate_workflow_spec(workflow_spec())["name"], "Club procurement")

    def test_rejects_arbitrary_action_and_fields(self):
        spec = workflow_spec()
        spec["steps"][1]["action"] = "run_shell"
        spec["steps"][1]["command"] = "whoami"
        with self.assertRaises(ValidationError):
            validate_workflow_spec(spec)

    def test_patch_changes_one_locator_and_preserves_assertions(self):
        spec = workflow_spec()
        patched = apply_locator_patch(spec, "purchase", {"strategy": "role", "role": "link", "name": "Purchase", "exact": True})
        self.assertEqual(patched["steps"][1]["locator"]["name"], "Purchase")
        self.assertEqual(patched["steps"][2], spec["steps"][2])
        self.assertEqual(spec["steps"][1]["locator"]["name"], "Purchasing")

    def test_patch_cannot_target_non_locator_step(self):
        with self.assertRaises(ValidationError):
            apply_locator_patch(workflow_spec(), "assert", {"strategy": "css", "value": "body"})

