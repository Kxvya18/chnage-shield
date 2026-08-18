import asyncio
import os
import threading
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from edge.executor import execute_workflow
from .diagnostics import diagnose_run
from .models import Approval, AuditEvent, FailureEvent, RepairProposal, Run, Runner, StepRun, ValidationRun, WorkflowVersion
from .schema import apply_locator_patch, validate_workflow_spec


def audit(action, entity, actor, detail=None):
    return AuditEvent.objects.create(action=action, entity_type=entity.__class__.__name__, entity_id=str(entity.pk), actor=actor, detail=detail or {})


@transaction.atomic
def claim_run(runner):
    run = Run.objects.select_for_update(skip_locked=True).filter(status=Run.Status.QUEUED).order_by("created_at").first()
    if not run:
        return None
    run.runner = runner
    run.status = Run.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["runner", "status", "started_at"])
    runner.last_seen_at = timezone.now()
    runner.save(update_fields=["last_seen_at"])
    audit("run.claimed", run, f"runner:{runner.name}")
    return run


def _process_single_run_with_browser(run, browser):
    job = {"run_id": run.id, "spec": run.effective_spec}
    result = execute_workflow(browser, job, artifact_dir=os.getenv("ARTIFACT_DIR", "/tmp/changeshield"))
    complete_run(run, result)
    return run


def _run_sync_in_thread(func, *args, **kwargs):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return func(*args, **kwargs)

    result = {}
    error = {}

    def runner():
        try:
            result["value"] = func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive async bridge for hosts that create a loop
            error["value"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result.get("value")


def process_single_run(run, browser=None):
    def _impl(browser_arg):
        if run.status == Run.Status.QUEUED:
            runner = run.runner or Runner.objects.filter(enabled=True).order_by("created_at").first()
            if runner is None:
                runner, _ = Runner.issue("local-demo-runner")
            run.runner = runner
            run.status = Run.Status.RUNNING
            run.started_at = timezone.now()
            run.save(update_fields=["runner", "status", "started_at"])

        if run.status != Run.Status.RUNNING:
            return run

        if browser_arg is None:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser_local = playwright.chromium.launch(headless=True)
                try:
                    return _process_single_run_with_browser(run, browser_local)
                finally:
                    browser_local.close()

        return _process_single_run_with_browser(run, browser_arg)

    return _run_sync_in_thread(_impl, browser)


@transaction.atomic
def complete_run(run, payload):
    run.refresh_from_db()
    if run.status != Run.Status.RUNNING:
        raise ValidationError("Only a running job can be completed")
    status = payload.get("status")
    if status not in {Run.Status.PASSED, Run.Status.FAILED}:
        raise ValidationError("status must be passed or failed")
    for step in payload.get("steps", []):
        StepRun.objects.create(run=run, step_id=str(step.get("step_id", ""))[:120], status=str(step.get("status", "unknown"))[:20], duration_ms=max(0, int(step.get("duration_ms", 0))), detail=step.get("detail", {}))
    if status == Run.Status.FAILED:
        failure = payload.get("failure") or {}
        FailureEvent.objects.create(run=run, step_id=str(failure.get("step_id", ""))[:120], code=str(failure.get("code", "unknown"))[:80], message=str(failure.get("message", "Unknown failure"))[:4000], evidence=failure.get("evidence", {}))
    run.status = status
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at"])
    audit(f"run.{status}", run, f"runner:{run.runner.name if run.runner else 'unknown'}")
    if status == Run.Status.FAILED and run.kind == Run.Kind.NORMAL:
        diagnose_run(run, payload.get("interactive_elements", []))
    if run.validation_run_id:
        finalize_validation(run.validation_run)
    return run


@transaction.atomic
def begin_validation(proposal, actor):
    if proposal.status not in {RepairProposal.Status.PROPOSED, RepairProposal.Status.VALIDATING}:
        raise ValidationError("Only a proposed repair can be validated")
    if not proposal.diagnosis.recommended_candidate_id:
        raise ValidationError("An abstained diagnosis cannot be validated")
    spec = apply_locator_patch(proposal.diagnosis.run.workflow_version.spec, proposal.step_id, proposal.replacement_locator)
    validation = ValidationRun.objects.create(proposal=proposal, required_attempts=3)
    for _ in range(validation.required_attempts):
        Run.objects.create(workflow_version=proposal.diagnosis.run.workflow_version, validation_run=validation, kind=Run.Kind.VALIDATION, spec_override=spec)
    proposal.status = RepairProposal.Status.VALIDATING
    proposal.save(update_fields=["status"])
    audit("proposal.validation_started", proposal, actor, {"attempts": 3})
    return validation


@transaction.atomic
def finalize_validation(validation):
    attempts = list(validation.attempts.order_by("created_at"))
    if len(attempts) < validation.required_attempts or any(run.status in {Run.Status.QUEUED, Run.Status.RUNNING} for run in attempts):
        return validation
    validation.results = [{"run_id": run.id, "status": run.status} for run in attempts]
    validation.completed_at = timezone.now()
    validation.status = ValidationRun.Status.PASSED if all(run.status == Run.Status.PASSED for run in attempts) else ValidationRun.Status.FAILED
    validation.save(update_fields=["results", "completed_at", "status"])
    proposal = validation.proposal
    proposal.status = RepairProposal.Status.VALIDATED if validation.status == ValidationRun.Status.PASSED else RepairProposal.Status.PROPOSED
    proposal.save(update_fields=["status"])
    audit(f"validation.{validation.status}", validation, "system", {"results": validation.results})
    return validation


@transaction.atomic
def approve_proposal(proposal, user):
    if proposal.status != RepairProposal.Status.VALIDATED or not proposal.validations.filter(status=ValidationRun.Status.PASSED).exists():
        raise ValidationError("Proposal requires a successful three-attempt validation")
    workflow = proposal.diagnosis.run.workflow_version.workflow
    latest = workflow.versions.aggregate(Max("number"))["number__max"] or 0
    spec = apply_locator_patch(proposal.diagnosis.run.workflow_version.spec, proposal.step_id, proposal.replacement_locator)
    spec["version"] = latest + 1
    version = WorkflowVersion.objects.create(workflow=workflow, number=latest + 1, spec=spec, change_reason=f"Approved repair proposal {proposal.id}", created_by=user)
    workflow.active_version = version
    workflow.save(update_fields=["active_version"])
    proposal.status = RepairProposal.Status.APPROVED
    proposal.save(update_fields=["status"])
    Approval.objects.create(proposal=proposal, approved_version=version, actor=user)
    audit("proposal.approved", proposal, user.get_username(), {"version": version.number})
    return version


@transaction.atomic
def reject_proposal(proposal, user):
    if proposal.status == RepairProposal.Status.APPROVED:
        raise ValidationError("An approved proposal cannot be rejected; use rollback")
    proposal.status = RepairProposal.Status.REJECTED
    proposal.save(update_fields=["status"])
    audit("proposal.rejected", proposal, user.get_username())


@transaction.atomic
def rollback_workflow(workflow, user):
    if not workflow.active_version:
        raise ValidationError("Workflow has no active version")
    previous = workflow.versions.filter(number__lt=workflow.active_version.number).order_by("-number").first()
    if not previous:
        raise ValidationError("No previous version exists")
    old = workflow.active_version
    workflow.active_version = previous
    workflow.save(update_fields=["active_version"])
    audit("workflow.rolled_back", workflow, user.get_username(), {"from": old.number, "to": previous.number})
    return previous
