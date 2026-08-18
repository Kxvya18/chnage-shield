import hashlib
import secrets
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .schema import validate_workflow_spec


class Runner(models.Model):
    name = models.CharField(max_length=120, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def issue(cls, name):
        token = secrets.token_urlsafe(32)
        runner = cls.objects.create(name=name, token_hash=cls.hash_token(token))
        return runner, token


class Workflow(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    active_version = models.ForeignKey("WorkflowVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="active_for")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class WorkflowVersion(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    spec = models.JSONField()
    change_reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workflow", "number"], name="unique_workflow_version")]
        ordering = ["-number"]

    def clean(self):
        validate_workflow_spec(self.spec)

    def save(self, *args, **kwargs):
        if self.pk and WorkflowVersion.objects.filter(pk=self.pk).exists():
            raise ValidationError("Workflow versions are immutable")
        self.full_clean()
        return super().save(*args, **kwargs)


class Run(models.Model):
    class Kind(models.TextChoices):
        NORMAL = "normal", "Normal"
        VALIDATION = "validation", "Validation"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.PROTECT, related_name="runs")
    runner = models.ForeignKey(Runner, on_delete=models.PROTECT, null=True, blank=True, related_name="runs")
    validation_run = models.ForeignKey("ValidationRun", on_delete=models.PROTECT, null=True, blank=True, related_name="attempts")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    spec_override = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def effective_spec(self):
        return self.spec_override or self.workflow_version.spec


class StepRun(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="steps")
    step_id = models.CharField(max_length=120)
    status = models.CharField(max_length=20)
    duration_ms = models.PositiveIntegerField(default=0)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class FailureEvent(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="failure_events")
    step_id = models.CharField(max_length=120, blank=True)
    code = models.CharField(max_length=80)
    message = models.TextField()
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class LocatorCandidate(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="locator_candidates")
    step_id = models.CharField(max_length=120)
    locator = models.JSONField()
    role_score = models.FloatField(default=0)
    name_score = models.FloatField(default=0)
    attribute_score = models.FloatField(default=0)
    context_score = models.FloatField(default=0)
    score = models.FloatField(default=0)
    unique = models.BooleanField(default=False)
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score", "id"]


class Diagnosis(models.Model):
    run = models.OneToOneField(Run, on_delete=models.PROTECT, related_name="diagnosis")
    failure_class = models.CharField(max_length=80)
    summary = models.TextField()
    evidence_event_ids = models.JSONField(default=list)
    recommended_candidate = models.ForeignKey(LocatorCandidate, on_delete=models.PROTECT, null=True, blank=True)
    confidence = models.FloatField(default=0)
    abstain_reason = models.TextField(blank=True)
    provider = models.CharField(max_length=80)
    model = models.CharField(max_length=120)
    prompt_version = models.CharField(max_length=40, default="diagnosis-v1")
    created_at = models.DateTimeField(auto_now_add=True)


class RepairProposal(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        VALIDATING = "validating", "Validating"
        VALIDATED = "validated", "Validated"
        REJECTED = "rejected", "Rejected"
        APPROVED = "approved", "Approved"

    diagnosis = models.OneToOneField(Diagnosis, on_delete=models.PROTECT, related_name="proposal")
    step_id = models.CharField(max_length=120)
    replacement_locator = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    created_at = models.DateTimeField(auto_now_add=True)


class ValidationRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    proposal = models.ForeignKey(RepairProposal, on_delete=models.PROTECT, related_name="validations")
    required_attempts = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    results = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class Approval(models.Model):
    proposal = models.OneToOneField(RepairProposal, on_delete=models.PROTECT, related_name="approval")
    approved_version = models.OneToOneField(WorkflowVersion, on_delete=models.PROTECT, related_name="approval")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=100)
    actor = models.CharField(max_length=120)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit events are immutable")
        return super().save(*args, **kwargs)

