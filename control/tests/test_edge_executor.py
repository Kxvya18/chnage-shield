import os
import tempfile
import unittest
from urllib.parse import quote
from django.test import SimpleTestCase
from playwright.sync_api import sync_playwright
from edge.executor import execute_workflow


@unittest.skipUnless(os.getenv("RUN_BROWSER_TESTS") == "true", "set RUN_BROWSER_TESTS=true after installing Chromium")
class EdgeExecutorBrowserTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def job(self, button_name):
        html = "<html><body><main><h1>Purchase</h1><a role='link' href='#purchase'>Purchase</a><button>New</button></main></body></html>"
        data_url = "data:text/html," + quote(html)
        return {"run_id": 99, "spec": {"name": "fixture", "version": 1, "steps": [
            {"id": "open", "action": "navigate", "url": data_url},
            {"id": "purchase", "action": "click", "locator": {"strategy": "role", "role": "link", "name": button_name}},
            {"id": "verify", "action": "assert_text", "locator": {"strategy": "role", "role": "button", "name": "New"}, "value": "New"},
        ]}}

    def test_valid_workflow_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = execute_workflow(self.browser, self.job("Purchase"), directory)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual([step["status"] for step in result["steps"]], ["passed", "passed", "passed"])

    def test_outdated_name_fails_and_captures_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            result = execute_workflow(self.browser, self.job("Purchasing"), directory)
        self.assertEqual(result["status"], "failed")
        purchase = next(item for item in result["interactive_elements"] if item["name"] == "Purchase")
        self.assertEqual(purchase["role"], "link")
        self.assertTrue(purchase["unique"])

    def test_supported_actions_and_locator_strategies(self):
        html = "<label for='email'>Email</label><input id='email'><input placeholder='Token'><select id='team'><option value='ops'>Ops</option></select><div data-testid='ready'>Ready</div>"
        job = {"run_id": 100, "spec": {"name": "actions", "version": 1, "steps": [
            {"id": "open", "action": "navigate", "url": "data:text/html," + quote(html)},
            {"id": "email", "action": "fill", "locator": {"strategy": "label", "value": "Email"}, "value": "operator@example.test"},
            {"id": "token", "action": "fill", "locator": {"strategy": "placeholder", "value": "Token"}, "value": "local-value"},
            {"id": "team", "action": "select", "locator": {"strategy": "css", "value": "#team"}, "value": "ops"},
            {"id": "wait", "action": "wait_for", "locator": {"strategy": "test_id", "value": "ready"}},
            {"id": "text", "action": "assert_text", "locator": {"strategy": "test_id", "value": "ready"}, "value": "Ready"},
            {"id": "url", "action": "assert_url", "value": "data:text/html"},
        ]}}
        with tempfile.TemporaryDirectory() as directory:
            result = execute_workflow(self.browser, job, directory)
        self.assertEqual(result["status"], "passed", result)
