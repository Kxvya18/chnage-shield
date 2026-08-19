# ChangeShield

ChangeShield is a prototype for repairing browser automations that break against software you do not control.

Many real business workflows depend on browser-based systems such as Odoo, and those systems can change in ways that break automation: a button label changes, a form moves, a login flow fails, or a page loads differently than expected. When that happens, the automation usually stops and someone has to investigate manually.

ChangeShield explores a safer way to handle that problem. It runs a declared Playwright workflow, captures evidence when a step fails, scores repair candidates, and requires validation plus human approval before activating a new workflow version.

This repository is meant to be public and readable. It shows the control plane, the browser workflow, and the safety checks behind the prototype without claiming production readiness.

## Project overview

- Django control plane for runs, proposals, approvals, and audit history
- Playwright edge runner that talks to unmodified Odoo Community
- deterministic failure classification and candidate scoring
- human approval before any repair becomes active

## Problem statement

The core problem is not just running browser automation. The hard part is keeping automation useful after the target application changes.

ChangeShield is aimed at the case where:

- the target application is owned by someone else
- the browser flow can break without warning
- a failed run needs evidence instead of guesswork
- not every candidate locator should be trusted
- a repair should be reviewed before it becomes active

That makes the project different from a simple script or a one-off browser macro. It is trying to manage failure, evidence, and approval around an external system.

## Prototype status

This is a working prototype, not a production deployment. It demonstrates the control-plane pattern, the browser execution path, and the repair review flow.

## What it does

- Connects to Odoo Community as the business app under test
- Runs a declared browser workflow
- Captures failure evidence when a step breaks
- Scores repair candidates and rejects weak or ambiguous ones
- Requires validation and approval before a repair becomes active

## How the prototype works

The flow is intentionally simple and controlled:

1. A workflow is defined in the control plane.
2. The runner executes that workflow in a browser.
3. If a step fails, the system records the failure and captures evidence.
4. The diagnosis layer classifies the failure and looks for a safe repair candidate.
5. A candidate only becomes eligible if it passes the project rules.
6. The fix is validated before approval.
7. Human approval is required before the new version becomes active.

The important part is that the prototype does not let the model freely change the workflow. It keeps the repair process bounded and reviewable.

## Future production work

If this prototype moves into production, the next steps are to harden the deployment, move runtime state to managed services, strengthen access control, isolate validation runs, add auditing and monitoring, and verify the workflow in staging before release.

## Run locally

Use this to start the local demo:

```bash
cp .env.example .env
docker compose up -d --build
```

For a non-Docker control-plane run:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Case study](docs/CASE_STUDY.md)

## What to expect from this repo

This repo is intentionally honest about scope. It shows a working prototype and the design behind it. It does not claim to be a finished production system, and it does not claim real customer impact yet.

## Status

The unit and service tests run locally. Live Odoo, Docker Compose, and any future AWS deployment still depend on the target environment and should be verified there before calling the system production-ready.

