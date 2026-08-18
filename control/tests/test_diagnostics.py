from django.test import TestCase
from control.diagnostics import classify_failure, create_candidates, deterministic_recommendation, score_candidate
from control.models import Run
from .helpers import create_domain


class FailureClassificationTests(TestCase):
    def test_taxonomy(self):
        cases = [
            (("http_401", "session expired"), "authentication"),
            (("network_error", "net::ERR_CONNECTION_REFUSED"), "network"),
            (("locator_timeout", "waiting for locator"), "missing_locator"),
            (("ambiguous", "strict mode violation multiple elements"), "ambiguous_locator"),
            (("postcondition", "expected approved"), "business_assertion"),
            (("timeout", "overlay was not stable"), "transient_rendering"),
        ]
        for args, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_failure(*args), expected)


class CandidateRankingTests(TestCase):
    def setUp(self):
        _, _, version, _, _ = create_domain()
        self.run = Run.objects.create(workflow_version=version)
        self.expected = {"strategy": "role", "role": "link", "name": "Purchasing"}

    def test_semantic_candidate_scores_above_threshold(self):
        scores = score_candidate(self.expected, {"role": "link", "name": "Purchase"})
        self.assertGreaterEqual(scores["score"], 0.82)

    def test_clear_candidate_is_recommended(self):
        candidates = create_candidates(self.run, "purchase", self.expected, [
            {"role": "link", "name": "Purchase", "unique": True, "tag": "a"},
            {"role": "button", "name": "Settings", "unique": True, "tag": "button"},
        ])
        best, reason = deterministic_recommendation(candidates)
        self.assertIsNotNone(best)
        self.assertEqual(best.locator["name"], "Purchase")
        self.assertEqual(reason, "")

    def test_ambiguous_candidates_force_abstention(self):
        candidates = create_candidates(self.run, "purchase", self.expected, [
            {"role": "link", "name": "Purchase", "unique": False},
            {"role": "link", "name": "Purchases", "unique": False},
        ])
        best, reason = deterministic_recommendation(candidates)
        self.assertIsNone(best)
        self.assertTrue("not unique" in reason or "margin" in reason)

