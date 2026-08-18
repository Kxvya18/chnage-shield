from django.contrib import admin
from .models import Approval, AuditEvent, Diagnosis, FailureEvent, LocatorCandidate, RepairProposal, Run, Runner, StepRun, ValidationRun, Workflow, WorkflowVersion

admin.site.register([Runner, Workflow, WorkflowVersion, Run, StepRun, FailureEvent, LocatorCandidate, Diagnosis, RepairProposal, ValidationRun, Approval, AuditEvent])
