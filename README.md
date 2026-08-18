# ChangeShield

**Prototype: safe recovery for broken enterprise browser automations.**

ChangeShield is a local-first prototype for a browser-automation recovery control plane. It runs a declarative Playwright workflow against software it does not control, records evidence when a step fails, ranks safe locator replacements, and requires validation plus human approval before activating a new immutable workflow version.

This repository is intentionally presented as a prototype and demo project. It demonstrates the architecture, runtime loop, and decision policy for safe automation recovery, while clearly documenting the production path that would be required for full deployment.

## Prototype status

This project is designed to show the complete control-plane pattern and the operational idea behind it. The current state is best described as:

- working local prototype
- real queue/worker/browser flow verified in part
- live Odoo + Docker integration still environment-dependent
- production deployment path documented but not claimed as complete

## What the demo proves

The included demonstration protects a synthetic student-club procurement workflow in unmodified Odoo Community. The initial workflow intentionally looks for **Purchasing** while the target application exposes **Purchase**, reproducing a common UI rename failure.

## Production-end-to-end path

The production implementation path is described in [docs/PRODUCTION_PATH.md](docs/PRODUCTION_PATH.md). It covers the intended architecture from Odoo workflow execution, queue processing, worker orchestration, evidence collection, deterministic diagnosis, repair validation, and human approval.

## Demo evidence

The confirmed runtime evidence and commands are recorded in [docs/DEMO_EVIDENCE.md](docs/DEMO_EVIDENCE.md).

## Why this is not “AI writes a selector”

The deterministic system classifies failures first. Only missing-locator failures enter repair analysis. Candidate elements are ranked by role, semantic name, stable attributes and context. A candidate must score at least `0.82`, be unique, and beat the runner-up by `0.12`. The LLM can inspect only five read-only tools and cannot generate executable code. Ambiguity means abstention.

## Agent + MCP + LLM boundary

The model is a constrained reasoning assistant, not an autonomous operator. It lives behind a narrow read-only tool layer and is never allowed to execute Python, shell commands, credential changes, database writes, or arbitrary selector generation. The control plane validates the model output against a strict schema, checks the candidate against the actual run, and rejects any recommendation that violates the deterministic eligibility policy.

```text
Failure classifier
   ↓
Candidate scorer
   ↓
eligible?
  ┌──────┴──────┐
  no            yes
  ↓             ↓
ABSTAIN       MCP read-only tools
                  ↓
                LLM
                  ↓
            recommendation
                  ↓
         schema + policy check
                  ↓
         human approval required
```

```text
Odoo network                 AWS control plane
┌──────────────────────┐     ┌───────────────────────────┐
│ Odoo + PostgreSQL    │     │ Django REST + PostgreSQL  │
│ Playwright edge      │────▶│ Runs, evidence, proposals │
│ Raw traces + secrets │ TLS │ approvals and audit       │
└──────────────────────┘     └───────────────────────────┘
```

## Run locally

Prerequisites: Docker Desktop with Compose and a free Groq API key (optional).

```bash
cp .env.example .env
# Replace any production secrets; the local demo defaults are already set to operator / operator123.
docker compose up -d --build
```

Open `http://localhost:8000`, sign in with `operator / operator123`, and queue the procurement workflow. The control plane receives only redacted step metadata and candidate summaries while the live Playwright trace stays in the `runner_artifacts` volume.

Without Docker, the control plane can be exercised directly:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

## Prove it

```bash
.venv/bin/python manage.py check
.venv/bin/coverage run manage.py test
.venv/bin/coverage report
```

The tests cover the constrained workflow schema, failure taxonomy, semantic scoring, ambiguity abstention, runner isolation, secret redaction, atomic claiming, three-pass validation, immutable versions, approval and rollback.

## API surface

Operator requests use Django sessions and CSRF. Edge requests use a revocable runner bearer token.

```text
POST /api/v1/workflows
POST /api/v1/workflows/{id}/runs
GET  /api/v1/runs/{id}
GET  /api/v1/runs/{id}/diagnosis
POST /api/v1/proposals/{id}/validate
POST /api/v1/proposals/{id}/approve
POST /api/v1/proposals/{id}/reject
POST /api/v1/workflows/{id}/rollback

POST /api/v1/runner/jobs/claim
POST /api/v1/runner/runs/{id}/events
POST /api/v1/runner/runs/{id}/artifacts
POST /api/v1/runner/runs/{id}/complete
```

## Documentation

- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Evaluation report](docs/EVALUATION.md)
- [What broke](docs/CASE_STUDY.md)
- [AWS deployment](deploy/README.md)
- [Demo script](docs/DEMO.md)

## Given another week

Pilot with a real club, calibrate the scoring thresholds on observed failures, add webhook notifications, sign workflow exports, store sanitized artifacts in S3, expose the existing diagnostic tools through MCP, and evaluate a local model for sensitive customer environments.

## AI assistance disclosure

AI assistance was used to scaffold and review portions of the implementation and documentation. The submitter must read, run and be able to explain every accepted line. Important decisions to defend are: declarative workflows instead of generated code, deterministic classification before LLM use, customer-side credentials, abstention thresholds, three isolated validation passes, immutable versions and human approval.

## Honest status

The unit/integration suite runs without external services. Live Odoo, Docker Compose and AWS deployment require Docker/AWS access and must be verified in the target environment before claiming a production pilot. No real-user impact or time savings are claimed yet.

