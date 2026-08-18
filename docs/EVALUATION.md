# Evaluation report

## Acceptance matrix

| Scenario | Expected | Automated evidence |
|---|---|---|
| `Purchasing` renamed to unique `Purchase` link | Propose repair | Candidate ranking and lifecycle tests |
| Broken CSS with unique semantic target | Propose repair | Schema/ranking tests; live fixture pending |
| Two similarly named purchase targets | Abstain | Ambiguous-candidate test |
| Expired session | Authentication diagnosis, no patch | Failure-taxonomy test |
| Odoo unavailable | Network diagnosis, no patch | Failure-taxonomy and non-locator lifecycle test |
| Only two validation passes | Approval rejected | Lifecycle test checks pre-validation rejection |
| Three validation passes | New immutable version | Lifecycle test |
| Human rollback | Prior version active | Lifecycle test |
| Raw trace uploaded | API rejects | Runner API test |
| Nested credentials in bundle | Redacted | Recursive redaction test |

## Current measured result

The suite contains 24 tests, including three real Chromium executor tests, and reaches 80% statement coverage. It proves control-plane behavior and the Playwright evidence path without depending on network services. It does not prove the current Odoo DOM contract.

## Live verification still required

On a machine with Docker:

1. Start Odoo 19 and capture the seeded snapshot.
2. Run the workflow once with the corrected `Purchase` locator to establish baseline.
3. Reactivate the intentionally stale `Purchasing` version and verify failure evidence.
4. Validate the proposed patch three times from restored snapshots.
5. Record trace paths, run IDs, timings, proposal score and final active version here.

Do not replace this section with invented measurements.
