from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from control.models import AuditEvent, RepairProposal, Run, WorkflowVersion
from control.services import approve_proposal, begin_validation, claim_run, complete_run, process_single_run, rollback_workflow
from .helpers import create_domain


class LifecycleTests(TestCase):
    def setUp(self):
        self.user, self.workflow, self.version, self.runner, _ = create_domain()

    def _failed_run_with_proposal(self):
        run = Run.objects.create(workflow_version=self.version)
        claimed = claim_run(self.runner)
        self.assertEqual(claimed, run)
        complete_run(run, {
            "status": "failed",
            "steps": [{"step_id": "purchase", "status": "failed", "duration_ms": 1000}],
            "failure": {"step_id": "purchase", "code": "locator_timeout", "message": "waiting for locator role=link name=Purchasing", "evidence": {}},
            "interactive_elements": [
                {"role": "link", "name": "Purchase", "unique": True, "tag": "a"},
                {"role": "button", "name": "Settings", "unique": True, "tag": "button"},
            ],
        })
        return run, RepairProposal.objects.get(diagnosis__run=run)

    def test_claim_is_atomic_in_state(self):
        run = Run.objects.create(workflow_version=self.version)
        self.assertEqual(claim_run(self.runner), run)
        self.assertIsNone(claim_run(self.runner))
        run.refresh_from_db()
        self.assertEqual(run.status, Run.Status.RUNNING)

    def test_non_locator_failure_never_proposes_repair(self):
        run = Run.objects.create(workflow_version=self.version)
        claim_run(self.runner)
        complete_run(run, {"status": "failed", "failure": {"step_id": "purchase", "code": "network_error", "message": "net::ERR_CONNECTION_REFUSED"}, "steps": []})
        self.assertFalse(RepairProposal.objects.filter(diagnosis__run=run).exists())
        self.assertEqual(run.diagnosis.failure_class, "network")

    def test_three_passes_unlock_approval_and_rollback(self):
        _, proposal = self._failed_run_with_proposal()
        validation = begin_validation(proposal, self.user.username)
        self.assertEqual(validation.attempts.count(), 3)
        with self.assertRaises(ValidationError):
            approve_proposal(proposal, self.user)
        for attempt in validation.attempts.order_by("id"):
            attempt.runner = self.runner
            attempt.status = Run.Status.RUNNING
            attempt.save(update_fields=["runner", "status"])
            complete_run(attempt, {"status": "passed", "steps": [{"step_id": "purchase", "status": "passed", "duration_ms": 300}]})
        validation.refresh_from_db(); proposal.refresh_from_db()
        self.assertEqual(validation.status, "passed")
        self.assertEqual(proposal.status, "validated")
        new_version = approve_proposal(proposal, self.user)
        self.assertEqual(new_version.number, 2)
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.active_version, new_version)
        previous = rollback_workflow(self.workflow, self.user)
        self.assertEqual(previous.number, 1)
        self.assertTrue(AuditEvent.objects.filter(action="workflow.rolled_back").exists())

    @patch("control.services.execute_workflow")
    def test_process_single_run_creates_diagnosis_and_proposal(self, mock_execute):
        run = Run.objects.create(workflow_version=self.version)
        mock_execute.return_value = {
            "status": "failed",
            "steps": [{"step_id": "purchase", "status": "failed", "duration_ms": 250}],
            "failure": {"step_id": "purchase", "code": "locator_timeout", "message": "waiting for locator role=link name=Purchasing", "evidence": {}},
            "interactive_elements": [
                {"role": "link", "name": "Purchase", "unique": True, "tag": "a", "context": "Purchase menu"},
                {"role": "link", "name": "Purchasing", "unique": True, "tag": "a", "context": "Purchasing menu"},
            ],
        }

        process_single_run(run, browser=object())

        run.refresh_from_db()
        self.assertEqual(run.status, Run.Status.FAILED)
        self.assertTrue(hasattr(run, "diagnosis"))
        self.assertTrue(RepairProposal.objects.filter(diagnosis__run=run).exists())

    def test_workflow_versions_are_immutable(self):
        self.version.change_reason = "rewritten history"
        with self.assertRaises(ValidationError):
            self.version.save()

