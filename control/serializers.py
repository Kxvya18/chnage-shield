from rest_framework import serializers
from .models import Diagnosis, RepairProposal, Run, ValidationRun, Workflow, WorkflowVersion
from .schema import validate_workflow_spec


class WorkflowCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    spec = serializers.JSONField()

    def validate_spec(self, value):
        validate_workflow_spec(value)
        return value


class WorkflowVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowVersion
        fields = ["id", "number", "spec", "change_reason", "created_at"]


class WorkflowSerializer(serializers.ModelSerializer):
    active_version = WorkflowVersionSerializer(read_only=True)

    class Meta:
        model = Workflow
        fields = ["id", "name", "description", "active_version", "created_at"]


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = ["id", "failure_class", "summary", "evidence_event_ids", "recommended_candidate_id", "confidence", "abstain_reason", "provider", "model", "prompt_version", "created_at"]


class RunSerializer(serializers.ModelSerializer):
    diagnosis = DiagnosisSerializer(read_only=True)

    class Meta:
        model = Run
        fields = ["id", "workflow_version_id", "runner_id", "kind", "status", "started_at", "finished_at", "created_at", "diagnosis"]


class ProposalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairProposal
        fields = ["id", "diagnosis_id", "step_id", "replacement_locator", "status", "created_at"]


class ValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationRun
        fields = ["id", "proposal_id", "required_attempts", "status", "results", "created_at", "completed_at"]

