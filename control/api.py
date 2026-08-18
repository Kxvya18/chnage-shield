from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .authentication import RunnerTokenAuthentication
from .models import RepairProposal, Run, Workflow, WorkflowVersion
from .permissions import IsRunner
from .serializers import DiagnosisSerializer, ProposalSerializer, RunSerializer, ValidationSerializer, WorkflowCreateSerializer, WorkflowSerializer
from .services import approve_proposal, begin_validation, claim_run, complete_run, reject_proposal, rollback_workflow


def _django_error(exc):
    messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
    return Response({"errors": messages}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def workflows(request):
    serializer = WorkflowCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        workflow = Workflow.objects.create(name=serializer.validated_data["name"], description=serializer.validated_data.get("description", ""), created_by=request.user)
        spec = dict(serializer.validated_data["spec"])
        spec["name"] = workflow.name
        spec["version"] = 1
        version = WorkflowVersion.objects.create(workflow=workflow, number=1, spec=spec, change_reason="Initial workflow", created_by=request.user)
        workflow.active_version = version
        workflow.save(update_fields=["active_version"])
    return Response(WorkflowSerializer(workflow).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def start_run(request, workflow_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not workflow.active_version:
        return Response({"error": "Workflow has no active version"}, status=409)
    run = Run.objects.create(workflow_version=workflow.active_version)
    return Response(RunSerializer(run).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def run_detail(request, run_id):
    return Response(RunSerializer(get_object_or_404(Run, pk=run_id)).data)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def run_diagnosis(request, run_id):
    run = get_object_or_404(Run, pk=run_id)
    if not hasattr(run, "diagnosis"):
        return Response({"error": "Diagnosis is not available"}, status=404)
    data = DiagnosisSerializer(run.diagnosis).data
    if hasattr(run.diagnosis, "proposal"):
        data["proposal"] = ProposalSerializer(run.diagnosis.proposal).data
    return Response(data)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def validate_proposal(request, proposal_id):
    proposal = get_object_or_404(RepairProposal.objects.select_related("diagnosis__run__workflow_version"), pk=proposal_id)
    try:
        validation = begin_validation(proposal, request.user.get_username())
        return Response(ValidationSerializer(validation).data, status=201)
    except DjangoValidationError as exc:
        return _django_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def approve(request, proposal_id):
    proposal = get_object_or_404(RepairProposal, pk=proposal_id)
    try:
        version = approve_proposal(proposal, request.user)
        return Response({"status": "approved", "workflow_version": version.number})
    except DjangoValidationError as exc:
        return _django_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def reject(request, proposal_id):
    proposal = get_object_or_404(RepairProposal, pk=proposal_id)
    try:
        reject_proposal(proposal, request.user)
        return Response({"status": "rejected"})
    except DjangoValidationError as exc:
        return _django_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def rollback(request, workflow_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    try:
        version = rollback_workflow(workflow, request.user)
        return Response({"status": "rolled_back", "active_version": version.number})
    except DjangoValidationError as exc:
        return _django_error(exc)


@api_view(["POST"])
@authentication_classes([RunnerTokenAuthentication])
@permission_classes([IsRunner])
def runner_claim(request):
    run = claim_run(request.user)
    if not run:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response({"run_id": run.id, "kind": run.kind, "workflow_version": run.workflow_version.number, "spec": run.effective_spec})


@api_view(["POST"])
@authentication_classes([RunnerTokenAuthentication])
@permission_classes([IsRunner])
def runner_events(request, run_id):
    run = get_object_or_404(Run, pk=run_id, runner=request.user, status=Run.Status.RUNNING)
    events = request.data.get("events", [])
    if not isinstance(events, list):
        return Response({"error": "events must be a list"}, status=400)
    run.steps.bulk_create([])
    return Response({"accepted": len(events)})


@api_view(["POST"])
@authentication_classes([RunnerTokenAuthentication])
@permission_classes([IsRunner])
def runner_artifacts(request, run_id):
    get_object_or_404(Run, pk=run_id, runner=request.user, status=Run.Status.RUNNING)
    artifact = request.data.get("artifact", {})
    forbidden = {"cookies", "authorization", "password", "raw_trace"} & set(artifact)
    if forbidden:
        return Response({"error": f"Forbidden artifact fields: {sorted(forbidden)}"}, status=400)
    return Response({"accepted": True})


@api_view(["POST"])
@authentication_classes([RunnerTokenAuthentication])
@permission_classes([IsRunner])
def runner_complete(request, run_id):
    run = get_object_or_404(Run, pk=run_id, runner=request.user)
    try:
        complete_run(run, request.data)
        return Response(RunSerializer(run).data)
    except DjangoValidationError as exc:
        return _django_error(exc)


@api_view(["GET"])
@permission_classes([])
@authentication_classes([])
def health_live(request):
    return Response({"status": "live"})


@api_view(["GET"])
@permission_classes([])
@authentication_classes([])
def health_ready(request):
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({"status": "ready"})
    except Exception:
        return Response({"status": "not_ready"}, status=503)
