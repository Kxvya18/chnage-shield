from django.test import SimpleTestCase
from control.diagnostics import GroqDiagnosisProvider


class GroqContractTests(SimpleTestCase):
    def test_accepts_exact_schema(self):
        value = {"failure_class": "missing_locator", "summary": "Name changed", "evidence_event_ids": [1], "recommended_candidate_id": 2, "confidence": 0.92, "abstain_reason": None}
        self.assertEqual(GroqDiagnosisProvider._validate(value), value)

    def test_rejects_extra_fields(self):
        value = {"failure_class": "x", "summary": "x", "evidence_event_ids": [], "recommended_candidate_id": None, "confidence": 1, "abstain_reason": None, "shell": "rm"}
        with self.assertRaises(RuntimeError):
            GroqDiagnosisProvider._validate(value)
