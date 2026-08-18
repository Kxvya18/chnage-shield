# What broke and how it was proved

## 1. The eligibility threshold was initially unreachable

**Symptom:** a role-and-name candidate could score at most `0.60`, below the required `0.82`.

**Hypothesis:** attribute and context weights were being counted even when the old workflow contained no comparable evidence.

**Proof:** a unit test scored an exact semantic candidate and reproduced the ceiling.

**Fix:** include only available evidence dimensions and normalize their weights. The threshold now means “82% of evidence we actually possess,” not “82% of an imaginary complete signature.” A regression test requires `Purchasing` → `Purchase` to clear the threshold.

## 2. Locator timeouts were misclassified

**Symptom:** `locator_timeout` matched the generic timeout rule and became transient rendering instead of missing locator.

**Hypothesis:** taxonomy precedence was too broad.

**Proof:** a table-driven classification test exercised authentication, network, locator, ambiguity, assertion and transient failures.

**Fix:** classify explicit locator timeouts before generic rendering timeouts. Only the former may enter repair analysis.

## 3. A stale in-memory job failed completion

**Symptom:** after a service atomically claimed a job, another reference still held status `queued` and completion rejected it.

**Hypothesis:** the service trusted caller state rather than database truth.

**Proof:** the lifecycle test claimed and completed the same logical run through separate object instances.

**Fix:** completion refreshes the run inside its transaction before checking state. This mirrors separate HTTP claim and completion requests.

These failures are retained because the debugging process is part of the project evidence.

