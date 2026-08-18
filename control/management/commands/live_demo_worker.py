import time

from django.core.management.base import BaseCommand

from control.models import Run
from control.services import process_single_run


class Command(BaseCommand):
    help = "Continuously process queued runs in the local demo system."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=3.0)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Live demo worker started"))
        while True:
            run = Run.objects.filter(status=Run.Status.QUEUED).select_related("workflow_version__workflow").order_by("created_at").first()
            if not run:
                time.sleep(options["interval"])
                continue

            self.stdout.write(f"Processing queued run {run.id} for workflow {run.workflow_version.workflow.name}")
            try:
                process_single_run(run)
                self.stdout.write(self.style.SUCCESS(f"Run {run.id} finished with status {run.status}"))
            except Exception as exc:  # pragma: no cover - operational logging path
                self.stderr.write(self.style.ERROR(f"Worker error for run {run.id}: {exc}"))
            time.sleep(options["interval"])
