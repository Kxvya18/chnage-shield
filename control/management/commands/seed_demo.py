import json
import os
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from control.models import Runner, Workflow, WorkflowVersion


class Command(BaseCommand):
    help = "Create a synthetic Odoo procurement workflow, operator, and edge runner token."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("DEMO_ADMIN_USERNAME", "operator")
        password = os.getenv("DEMO_ADMIN_PASSWORD", "operator123")
        user, created = User.objects.get_or_create(username=username, defaults={"is_staff": True, "is_superuser": True})
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        workflow, workflow_created = Workflow.objects.get_or_create(name="Club procurement: RFQ approval", defaults={"description": "Create a request for quotation in Odoo and verify procurement approval.", "created_by": user})
        if workflow_created:
            spec_path = Path(__file__).resolve().parents[2] / "fixtures" / "odoo_purchase.json"
            spec = json.loads(spec_path.read_text())
            version = WorkflowVersion.objects.create(workflow=workflow, number=1, spec=spec, change_reason="Initial procurement workflow", created_by=user)
            workflow.active_version = version
            workflow.save(update_fields=["active_version"])
        if not Runner.objects.filter(name="club-edge-runner").exists():
            token = os.getenv("RUNNER_TOKEN", "")
            if token:
                Runner.objects.create(name="club-edge-runner", token_hash=Runner.hash_token(token))
            else:
                _, token = Runner.issue("club-edge-runner")
            self.stdout.write(self.style.WARNING(f"RUNNER_TOKEN={token}"))
        self.stdout.write(self.style.SUCCESS(f"Demo ready. Operator username: {username}"))
        if created:
            self.stdout.write(self.style.WARNING("The demo password came from DEMO_ADMIN_PASSWORD; change it before deployment."))
