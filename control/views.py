from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .mcp_tools import MCP_TOOLS
from .models import AuditEvent, RepairProposal, Run, Workflow


@login_required
def dashboard(request):
    workflows = Workflow.objects.select_related("active_version").all()
    runs = Run.objects.select_related("workflow_version__workflow", "runner").all()[:12]
    tool_cards = [
        {"name": name, "purpose": {
            "get_run": "Fetch status and failure context for a run.",
            "get_failure_evidence": "Return sanitized evidence from the failing step.",
            "list_locator_candidates": "Show ranked locator candidates and their scores.",
            "compare_locator_candidates": "Compare top candidates and the score gap.",
            "get_workflow_context": "Return the workflow spec and failing step context.",
            "validate_llm_recommendation": "Enforce deterministic eligibility before any LLM output is trusted.",
        }.get(name, "Read-only evidence lookup.")}
        for name in MCP_TOOLS.keys()
    ]
    guardrails = [
        "Read-only evidence only; no shell or DB mutation.",
        "All locator recommendations must pass deterministic eligibility rules.",
        "Every proposal requires validation before approval.",
        "Human approval is mandatory before activation.",
    ]
    return render(request, "control/dashboard.html", {"workflows": workflows, "runs": runs, "mcp_tools": tool_cards, "guardrails": guardrails})


@login_required
def queue_run(request, workflow_id):
    workflow = get_object_or_404(Workflow.objects.select_related("active_version"), pk=workflow_id)
    if workflow.active_version is None:
        return redirect("dashboard")
    run = Run.objects.create(workflow_version=workflow.active_version, status=Run.Status.QUEUED)
    return redirect("run-detail-page", run_id=run.id)


@login_required
def workflow_detail(request, workflow_id):
    workflow = get_object_or_404(Workflow.objects.select_related("active_version"), pk=workflow_id)
    return render(request, "control/workflow_detail.html", {"workflow": workflow, "versions": workflow.versions.all(), "runs": Run.objects.filter(workflow_version__workflow=workflow)[:30]})


@login_required
def run_detail_page(request, run_id):
    run = get_object_or_404(Run.objects.select_related("workflow_version__workflow", "runner"), pk=run_id)
    diagnosis = getattr(run, "diagnosis", None)
    proposal = getattr(diagnosis, "proposal", None) if diagnosis else None
    return render(request, "control/run_detail.html", {"run": run, "diagnosis": diagnosis, "proposal": proposal, "events": run.failure_events.all(), "candidates": run.locator_candidates.all()})


@login_required
def proposal_detail(request, proposal_id):
    proposal = get_object_or_404(RepairProposal.objects.select_related("diagnosis__run__workflow_version__workflow"), pk=proposal_id)
    return render(request, "control/proposal_detail.html", {"proposal": proposal, "validations": proposal.validations.prefetch_related("attempts")})


@login_required
def audit_log(request):
    return render(request, "control/audit.html", {"events": AuditEvent.objects.all()[:200]})

