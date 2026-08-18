from django.test import TestCase

from control.diagnostics import classify_failure
from control.mcp_tools import (
    compare_locator_candidates,
    get_failure_evidence,
    get_run,
    get_workflow_context,
    list_locator_candidates,
    validate_llm_recommendation,
)
from control.models import FailureEvent, LocatorCandidate, Run
from .helpers import create_domain


class McpToolTests(TestCase):
    def setUp(self):
        self.user, self.workflow, self.version, self.runner, self.token = create_domain()
        self.run = Run.objects.create(workflow_version=self.version, status=Run.Status.FAILED)
        self.event = FailureEvent.objects.create(
            run=self.run,
            step_id="purchase",
            code="locator_timeout",
            message="waiting for locator Purchasing; Authorization: Bearer secret-token",
        )
        self.candidate_a = LocatorCandidate.objects.create(
            run=self.run,
            step_id="purchase",
            locator={"strategy": "role", "role": "link", "name": "Purchase", "exact": True},
            role_score=1.0,
            name_score=0.94,
            attribute_score=0.0,
            context_score=0.8,
            score=0.94,
            unique=True,
            evidence={"tag": "a", "text": "Purchase", "context": "main"},
        )
        self.candidate_b = LocatorCandidate.objects.create(
            run=self.run,
            step_id="purchase",
            locator={"strategy": "role", "role": "link", "name": "Purchase Orders", "exact": True},
            role_score=1.0,
            name_score=0.69,
            attribute_score=0.0,
            context_score=0.7,
            score=0.69,
            unique=True,
            evidence={"tag": "a", "text": "Purchase Orders", "context": "side"},
        )

    def test_read_only_mcp_tools_return_safe_summary(self):
        result = get_run(self.run.id)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed_step"], "purchase")
        self.assertEqual(result["failure_category"], classify_failure(self.event.code, self.event.message))

        evidence = get_failure_evidence(self.run.id)
        self.assertIn("sanitized_error", evidence)
        self.assertNotIn("secret-token", evidence["sanitized_error"])
        self.assertEqual(evidence["expected_semantic_name"], "Purchasing")

        candidates = list_locator_candidates(self.run.id, limit=5)
        self.assertEqual(len(candidates), 2)
        self.assertIn("candidate_id", candidates[0])
        self.assertLessEqual(len(candidates), 5)

        comparison = compare_locator_candidates(self.run.id, limit=2)
        self.assertIn("top_candidates", comparison)
        self.assertEqual(comparison["top_candidates"][0]["candidate_id"], self.candidate_a.id)

        context = get_workflow_context(self.run.id)
        self.assertEqual(context["workflow_name"], self.workflow.name)
        self.assertIn("steps", context)

    def test_invalid_run_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            get_run(999999)
        with self.assertRaises(ValueError):
            get_failure_evidence(999999)

    def test_llm_recommendation_must_be_bound_to_eligible_candidate(self):
        self.assertTrue(validate_llm_recommendation(self.run.id, self.candidate_a.id))
        self.assertFalse(validate_llm_recommendation(self.run.id, self.candidate_b.id))
        self.assertFalse(validate_llm_recommendation(self.run.id, 999999))
