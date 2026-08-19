# Case study

ChangeShield started as a small idea: if browser automation breaks because the target system changes, can the tool explain what failed, suggest a repair safely, and keep a human in control? In practice, the answer turned out to depend on several small but important engineering choices.

The prototype became more interesting once it had to deal with real edge cases. That is where the case study comes from: the system did not just need to “work,” it needed to fail in a predictable way, explain itself, and avoid acting on weak evidence.

## 1. The scoring threshold was too strict

The first version of candidate scoring treated missing evidence as if it should still count against the locator. That made a good semantic match stall below the approval threshold.

This looked like a simple tuning issue, but it was actually a design problem. The system was assuming evidence that did not exist. In a real browser flow, especially one tied to another system’s UI, missing attributes are normal. Treating them as a penalty made the threshold unreachable.

What changed:

- only the evidence that actually exists is counted
- missing dimensions are dropped before normalization
- the regression test now expects `Purchasing` to resolve to `Purchase`

## 2. Locator timeouts were grouped too broadly

Some locator failures were being treated like generic rendering timeouts. That meant the repair path could miss the cases that should actually be analyzed.

This mattered because not all failures mean the same thing. A page loading slowly is not the same as a selector no longer matching the UI. If those are mixed together, the system can propose the wrong type of repair or miss a repair opportunity entirely.

What changed:

- explicit locator timeouts are classified first
- generic timeout handling comes later
- only locator failures can enter repair review

## 3. Job completion trusted stale state

The worker could claim a run, but another reference still thought it was queued. That caused completion to fail even though the database already held the claimed state.

This was a concurrency issue. The code had to behave like a real distributed system, even though the prototype is small. Once the run was claimed in one place and completed in another, the service had to trust the database, not the old in-memory object.

What changed:

- completion refreshes the run inside the transaction
- the service checks database truth, not caller state
- the test now mirrors separate claim and completion requests

## What the case study shows

The main lesson is that the hard part was not just browser automation. The hard part was making a recovery system that could handle uncertainty safely.

The project had to answer questions like:

- what counts as strong enough evidence
- when the system should abstain
- how to keep the model from overreaching
- how to validate a repair before activation
- how to handle state safely when runs move between worker and database

Those constraints shaped the prototype more than the original idea did.
