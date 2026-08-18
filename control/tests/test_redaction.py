from django.test import SimpleTestCase
from edge.redaction import redact


class RedactionTests(SimpleTestCase):
    def test_recursive_secret_redaction(self):
        value = {"Authorization": "Bearer abc", "nested": {"password": "hunter2", "message": "use Bearer xyz"}, "cookies": ["a=b"]}
        result = redact(value)
        self.assertEqual(result["Authorization"], "[REDACTED]")
        self.assertEqual(result["nested"]["password"], "[REDACTED]")
        self.assertEqual(result["nested"]["message"], "use Bearer [REDACTED]")
        self.assertEqual(result["cookies"], "[REDACTED]")

