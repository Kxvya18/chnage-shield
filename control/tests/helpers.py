from django.contrib.auth import get_user_model
from control.models import Runner, Workflow, WorkflowVersion


def workflow_spec(locator_name="Purchasing"):
    return {
        "name": "Club procurement",
        "version": 1,
        "steps": [
            {"id": "open", "action": "navigate", "url": "/web/login"},
            {"id": "purchase", "action": "click", "locator": {"strategy": "role", "role": "link", "name": locator_name}, "postcondition": {"url_contains": "purchase"}},
            {"id": "assert", "action": "assert_url", "value": "purchase"},
        ],
    }


def create_domain():
    user = get_user_model().objects.create_user("operator", password="test-password")
    workflow = Workflow.objects.create(name="Club procurement", description="test", created_by=user)
    version = WorkflowVersion.objects.create(workflow=workflow, number=1, spec=workflow_spec(), change_reason="initial", created_by=user)
    workflow.active_version = version
    workflow.save(update_fields=["active_version"])
    runner, token = Runner.issue("test-runner")
    return user, workflow, version, runner, token

