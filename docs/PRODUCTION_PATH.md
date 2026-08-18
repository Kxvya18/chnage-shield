# Production end-to-end path

This document describes the intended production path for ChangeShield as a controlled recovery system for broken browser automations.

## 1. Source system and business trigger

The source system is a business application such as Odoo, SAP, or another browser-driven system that executes real operations.

- The business flow is captured as a declarative step list.
- Each step is explicit: navigate, fill, click, assert, and wait.
- The workflow is immutable after activation.
- A change to the workflow is never made by the AI directly; it is proposed and validated first.

## 2. Control-plane queue and job lifecycle

The Django control plane owns state and policy.

- Operators create or update workflow definitions.
- Runs are queued as immutable jobs.
- A runner claims the next queued run.
- The state transitions are:
  - queued
  - running
  - failed or passed
  - diagnosis produced
  - repair proposal created
  - validation runs executed
  - human approval before release

This is carried out through the Django services layer and the API endpoints in `control/api.py` and `control/services.py`.

## 3. Browser execution

The edge runner executes the workflow using Playwright.

- It launches a browser in a controlled environment.
- It captures structured step execution results.
- It records screenshots, console errors, and relevant page state.
- It returns only redacted evidence to the control plane.

The execution logic lives in:

- `edge/client.py`
- `edge/executor.py`
- `edge/redaction.py`

## 4. Failure classification and evidence collection

When a step breaks, the system does not guess.

- The failure is classified by deterministic rules.
- Missing locator failures are separated from network, auth, assertion, and timeout cases.
- Evidence includes:
  - step id
  - page URL
  - console errors
  - screenshot path
  - visible interactive elements

The diagnosis logic lives in `control/diagnostics.py`.

## 5. Candidate generation and repair review

The system ranks candidate locators by evidence quality.

- role score
- name score
- attribute score
- context score
- uniqueness check
- confidence threshold

Only candidates that satisfy the deterministic policy are eligible for human review. Ambiguous or low-confidence cases abstain instead of guessing.

## 6. Validation before activation

A proposed fix does not become active immediately.

- A validation run is created.
- The same workflow is exercised in isolation multiple times.
- The system proves the candidate is stable.
- Only then is the repair eligible for approval.

This requirement is enforced in `control/services.py`.

## 7. Human approval and immutable workflow versioning

The final gate is human approval.

- A repair proposal is reviewed by an operator.
- If approved, a new workflow version is created.
- The previous version remains preserved.
- The workflow becomes immutable after activation.

This is the safety boundary: the AI does not directly modify production workflows.

## 8. Production hardening plan

To move from prototype to production, the next hardening steps are:

1. replace local SQLite with managed PostgreSQL in production
2. secure runner auth tokens and rotation policy
3. isolate validation runs in a clean sandbox per attempt
4. store sanitized artifacts in a controlled object store
5. enforce strict logging and audit retention
6. add approval workflows and RBAC
7. add infrastructure and deployment automation through Terraform or Kubernetes
8. test the real business flow in a staging environment before release

## 9. Risk posture

This project deliberately does not allow unrestricted autonomous action.

- no unbounded selector generation
- no arbitrary shell execution from the AI
- no database writes from the model layer
- no direct runtime mutation without validation

That constraint is the core design choice and the main reason this architecture is suitable for high-risk enterprise process automation.
