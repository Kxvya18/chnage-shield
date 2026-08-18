from __future__ import annotations

from typing import Any

from edge.redaction import redact
from .diagnostics import REPAIR_THRESHOLD, MARGIN_THRESHOLD, classify_failure
from .models import LocatorCandidate, Run


def _require_run(run_id: Any) -> Run:
    try:
        run_id_int = int(run_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid run ID") from exc
    try:
        return Run.objects.select_related("workflow_version__workflow").get(pk=run_id_int)
    except Run.DoesNotExist as exc:
        raise ValueError(f"Invalid run ID: {run_id_int}") from exc


def _step_for_run(run: Run, step_id: str | None):
    if not step_id:
        return {}
    for step in run.effective_spec.get("steps", []):
        if step.get("id") == step_id:
            return step
    return {}


def _candidate_rows(run_id: Any, limit: int = 5):
    candidate_limit = max(1, min(int(limit), 10))
    return list(
        LocatorCandidate.objects.filter(run_id=int(run_id)).order_by("-score", "id")[:candidate_limit]
    )


def get_run(run_id: Any) -> dict[str, Any]:
    run = _require_run(run_id)
    event = run.failure_events.order_by("created_at").first()
    return {
        "run_id": run.id,
        "status": run.status,
        "failed_step": event.step_id if event else None,
        "workflow_version": run.workflow_version.number,
        "workflow_name": run.workflow_version.workflow.name,
        "failure_category": classify_failure(event.code, event.message) if event else None,
    }


def get_failure_evidence(run_id: Any) -> dict[str, Any]:
    run = _require_run(run_id)
    event = run.failure_events.order_by("created_at").first()
    if event is None:
        return {"run_id": run.id, "sanitized_error": None, "expected_semantic_name": None, "role": None, "page_context": None}

    step = _step_for_run(run, event.step_id)
    locator = step.get("locator", {}) if isinstance(step, dict) else {}
    return {
        "run_id": run.id,
        "step_id": event.step_id,
        "sanitized_error": redact(event.message),
        "expected_semantic_name": locator.get("name"),
        "role": locator.get("role"),
        "page_context": redact(step.get("postcondition") or step.get("context") or {}),
        "action": step.get("action"),
    }


def list_locator_candidates(run_id: Any, limit: int = 5) -> list[dict[str, Any]]:
    rows = _candidate_rows(run_id, limit)
    result = []
    for candidate in rows:
        locator = candidate.locator or {}
        result.append(
            {
                "candidate_id": candidate.id,
                "name": locator.get("name") or locator.get("value"),
                "role": locator.get("role"),
                "score": round(float(candidate.score), 4),
                "unique": bool(candidate.unique),
                "deterministic_score": round(float(candidate.score), 4),
            }
        )
    return result


def compare_locator_candidates(run_id: Any, limit: int = 2) -> dict[str, Any]:
    rows = _candidate_rows(run_id, limit)
    top_candidates = [
        {
            "candidate_id": candidate.id,
            "name": (candidate.locator or {}).get("name") or (candidate.locator or {}).get("value"),
            "role": (candidate.locator or {}).get("role"),
            "score": round(float(candidate.score), 4),
            "unique": bool(candidate.unique),
        }
        for candidate in rows
    ]
    margin = None
    if len(top_candidates) > 1:
        margin = round(float(top_candidates[0]["score"]) - float(top_candidates[1]["score"]), 4)
    return {
        "run_id": int(run_id),
        "top_candidates": top_candidates,
        "margin": margin,
    }


def get_workflow_context(run_id: Any) -> dict[str, Any]:
    run = _require_run(run_id)
    spec = run.effective_spec or {}
    steps = spec.get("steps", [])
    failed_event = run.failure_events.order_by("created_at").first()
    failed_step_id = failed_event.step_id if failed_event else None
    context_steps = []
    for step in steps:
        context_steps.append(
            {
                "id": step.get("id"),
                "action": step.get("action"),
                "locator": step.get("locator"),
                "postcondition": step.get("postcondition"),
            }
        )
    return {
        "workflow_name": run.workflow_version.workflow.name,
        "workflow_version": run.workflow_version.number,
        "failed_step": failed_step_id,
        "steps": context_steps,
    }


def validate_llm_recommendation(run_id: Any, candidate_id: Any) -> bool:
    try:
        run = _require_run(run_id)
        candidate = LocatorCandidate.objects.filter(run=run, pk=int(candidate_id)).first()
    except (TypeError, ValueError):
        return False
    if candidate is None:
        return False

    if not candidate.unique or candidate.score < REPAIR_THRESHOLD:
        return False

    second = (
        LocatorCandidate.objects.filter(run=run)
        .exclude(pk=candidate.pk)
        .order_by("-score", "id")
        .first()
    )
    second_score = second.score if second is not None else 0.0
    if candidate.score - second_score < MARGIN_THRESHOLD:
        return False
    return True


MCP_TOOLS = {
    "get_run": get_run,
    "get_failure_evidence": get_failure_evidence,
    "list_locator_candidates": list_locator_candidates,
    "compare_locator_candidates": compare_locator_candidates,
    "get_workflow_context": get_workflow_context,
    "validate_llm_recommendation": validate_llm_recommendation,
}


def dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    if name not in MCP_TOOLS:
        raise KeyError(f"Tool {name} is not allow-listed")
    return MCP_TOOLS[name](**args)
