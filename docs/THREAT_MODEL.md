# Threat model

## Assets

- ERP credentials and sessions
- Workflow definitions and active-version pointer
- Raw Playwright traces
- Runner and sandbox-reset tokens
- Human approval identity
- Audit history

## Trust boundaries and mitigations

| Threat | Mitigation |
|---|---|
| Prompt injection in ERP text | Page content is tool data, never instructions; tools are read-only and allow-listed. |
| LLM invents a locator | Candidate ID must belong to the failed run; deterministic eligibility cannot be overridden. |
| LLM generates dangerous code | No code patch type exists; schema accepts one locator replacement. |
| Stolen runner token | High-entropy token stored only as SHA-256; revocable and scoped to runner routes. |
| Runner completes another job | Every completion is filtered by both run ID and authenticated runner. |
| Secrets leak in evidence | Recursive key/bearer redaction; raw traces stay local; artifact API rejects raw traces/cookies/passwords. |
| Concurrent job claim | Database transaction with row lock and `skip_locked`. |
| Silent workflow mutation | Versions reject updates; approval creates a new version; audit events reject updates. |
| Unsafe repair activation | Three isolated full-run passes plus authenticated human approval. |
| Reset endpoint destroys production | Separate synthetic database, internal/localhost binding, distinct token, fixed database name. |
| Cloud compromise reaches ERP | Edge makes outbound requests; cloud stores no ERP credentials and has no general remote-execution endpoint. |

## Explicit non-goals

The v1 is not a general autonomous agent, production RPA fleet manager, secret vault or ERP authorization system. It must never target a non-synthetic database with the sandbox-reset service.

