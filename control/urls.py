from django.urls import path
from . import api, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("workflows/<int:workflow_id>/queue/", views.queue_run, name="queue-run"),
    path("workflows/<int:workflow_id>/", views.workflow_detail, name="workflow-detail"),
    path("runs/<int:run_id>/", views.run_detail_page, name="run-detail-page"),
    path("proposals/<int:proposal_id>/", views.proposal_detail, name="proposal-detail"),
    path("audit/", views.audit_log, name="audit-log"),
    path("health/live", api.health_live),
    path("health/ready", api.health_ready),
    path("api/v1/workflows", api.workflows),
    path("api/v1/workflows/<int:workflow_id>/runs", api.start_run),
    path("api/v1/workflows/<int:workflow_id>/rollback", api.rollback),
    path("api/v1/runs/<int:run_id>", api.run_detail),
    path("api/v1/runs/<int:run_id>/diagnosis", api.run_diagnosis),
    path("api/v1/proposals/<int:proposal_id>/validate", api.validate_proposal),
    path("api/v1/proposals/<int:proposal_id>/approve", api.approve),
    path("api/v1/proposals/<int:proposal_id>/reject", api.reject),
    path("api/v1/runner/jobs/claim", api.runner_claim),
    path("api/v1/runner/runs/<int:run_id>/events", api.runner_events),
    path("api/v1/runner/runs/<int:run_id>/artifacts", api.runner_artifacts),
    path("api/v1/runner/runs/<int:run_id>/complete", api.runner_complete),
]

