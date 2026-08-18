from django.test import Client, TestCase
from control.models import Run, Runner
from .helpers import create_domain


class OperatorApiTests(TestCase):
    def setUp(self):
        self.user, self.workflow, self.version, self.runner, self.token = create_domain()
        self.client = Client()

    def test_operator_endpoints_require_login(self):
        response = self.client.post(f"/api/v1/workflows/{self.workflow.id}/runs", content_type="application/json")
        self.assertIn(response.status_code, {401, 403})

    def test_logged_in_operator_can_queue_run(self):
        self.client.force_login(self.user)
        response = self.client.post(f"/api/v1/workflows/{self.workflow.id}/runs", content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "queued")


class RunnerApiTests(TestCase):
    def setUp(self):
        _, _, self.version, self.runner, self.token = create_domain()
        self.client = Client()
        self.run = Run.objects.create(workflow_version=self.version)

    def test_valid_runner_claims_job(self):
        response = self.client.post("/api/v1/runner/jobs/claim", HTTP_AUTHORIZATION=f"Bearer {self.token}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_id"], self.run.id)

    def test_revoked_runner_is_rejected(self):
        self.runner.enabled = False; self.runner.save(update_fields=["enabled"])
        response = self.client.post("/api/v1/runner/jobs/claim", HTTP_AUTHORIZATION=f"Bearer {self.token}", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_runner_cannot_complete_another_runners_job(self):
        other, other_token = Runner.issue("other")
        self.run.runner = other; self.run.status = Run.Status.RUNNING; self.run.save(update_fields=["runner", "status"])
        response = self.client.post(f"/api/v1/runner/runs/{self.run.id}/complete", data={"status": "passed", "steps": []}, HTTP_AUTHORIZATION=f"Bearer {self.token}", content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_forbidden_raw_artifact_is_rejected(self):
        self.run.runner = self.runner; self.run.status = Run.Status.RUNNING; self.run.save(update_fields=["runner", "status"])
        response = self.client.post(f"/api/v1/runner/runs/{self.run.id}/artifacts", data={"artifact": {"raw_trace": "secret"}}, HTTP_AUTHORIZATION=f"Bearer {self.token}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

