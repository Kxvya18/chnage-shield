import os
import time
import requests
from playwright.sync_api import sync_playwright
from .executor import execute_workflow


class ControlPlaneClient:
    def __init__(self):
        self.base_url = os.getenv("CONTROL_PLANE_URL", "http://control:8000").rstrip("/")
        token = os.getenv("RUNNER_TOKEN", "")
        if not token:
            raise RuntimeError("RUNNER_TOKEN is required")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    def claim(self):
        response = self.session.post(f"{self.base_url}/api/v1/runner/jobs/claim", timeout=15)
        if response.status_code == 204: return None
        response.raise_for_status()
        return response.json()

    def complete(self, run_id, result):
        response = self.session.post(f"{self.base_url}/api/v1/runner/runs/{run_id}/complete", json=result, timeout=30)
        response.raise_for_status()
        return response.json()


def reset_validation_sandbox():
    url = os.getenv("SANDBOX_RESET_URL", "")
    token = os.getenv("SANDBOX_RESET_TOKEN", "")
    if not url or not token:
        raise RuntimeError("Validation requires SANDBOX_RESET_URL and SANDBOX_RESET_TOKEN")
    response = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=150)
    response.raise_for_status()


def main():
    client = ControlPlaneClient()
    artifact_dir = os.getenv("ARTIFACT_DIR", "/artifacts")
    once = os.getenv("RUN_ONCE", "false").lower() == "true"
    profile_dir = os.getenv("PLAYWRIGHT_PROFILE_DIR", "/tmp/playwright-profile")
    os.makedirs(profile_dir, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            profile_dir,
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            args=["--disable-dev-shm-usage"],
        )
        try:
            while True:
                job = client.claim()
                if job:
                    if job["kind"] == "validation":
                        try:
                            reset_validation_sandbox()
                        except (RuntimeError, requests.RequestException) as exc:
                            client.complete(job["run_id"], {"status": "failed", "steps": [], "failure": {"step_id": "sandbox_reset", "code": "sandbox_reset_failed", "message": str(exc), "evidence": {}}})
                            if once: break
                            continue
                    client.complete(job["run_id"], execute_workflow(browser, job, artifact_dir))
                if once: break
                time.sleep(3 if job else 8)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
