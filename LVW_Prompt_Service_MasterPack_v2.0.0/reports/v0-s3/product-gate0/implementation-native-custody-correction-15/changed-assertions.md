# The changed assertions of the correction 15

Product candidate `63b490ae8b5678113fc13ed16fb2a8a54e5ca39c`, evidence
baseline `8a6ed7462a69bfa7e29d4d143c2d6fed289a1912`.  The correction is
**test only**: **one** test module changes
(`tools/test_v0_s3_native_custody_correction10.py`) and **no** production
source, no schema, no threshold, no denominator, no node id, no node
order and no historical report changes.

**No assertion is removed.**  The only lines that leave their place are
the seven assertions of the child of N10-R07: they are moved **into**
the inner ``try`` of the fixture so that the close of the transport of
the child runs in the inner ``finally`` **even when one of them fails**.
Their text, their order and their meaning are unchanged.

Every assertion that is **added** is listed here with the Major that
demanded it and with the production fact that it reads.  No oracle is
weakened: the three Majors of the independent test/evidence-design
review are closed by **stronger** assertions that read the same
production facts on a **public** chain, with a **checked** barrier and
with an **unconditional** cleanup.

## M1 — N10-R07 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r07_the_context_of_the_round_reaches_every_layer`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | the zero expiry was observed on a **fresh**, **unstarted** and **unattached** `custody_module._ChannelPump` that the group built itself and called directly (`zero_pump.take(...)`) after the pump of the round had already ended | the zero expiry is observed on a **second, separately bounded** round that is really started through the production `NativeCustodySession.start` and the production default launcher, with the ORIGINAL context of **that** round and **one** clock domain; the group observes the **attached** pump of that round (`session._pump`) | the helper proved the helper and not the public parent chain.  The acceptance oracle is now the pump that the production really started and really owns. |
| 2 | — | `assert zero_session.state == 'RUNNING'` | the round of the zero expiry is really started; the state is the state that the production applied from the real STATUS reply. |
| 3 | — | `assert zero_attached_pump is not None` and `assert zero_attached_pump.is_alive()` | the attached pump exists and it really runs; the group never builds a replacement for it. |
| 4 | — | `assert zero_held.wait(15.0)` | the **attached** pump of the round really reached its next admission and the admission is really held at the transparent gate. |
| 5 | — | `assert zero_queue_waits` and `assert zero_queue_waits[-1] == 0.0` | the **attached** pump of the round really asked the queue of the round for **nothing** after the zero expiry was published on the ORIGINAL context. |
| 6 | — | `assert zero_reply_waits` and `assert zero_reply_waits[-1] == 0.0` | the reply of the parent was really waited for and it asked for **nothing**: the recorded argument is the argument that the production really passed to the event of the reply. |
| 7 | — | `assert facts['zero_pump_finished'] is True` | the attached pump of the round really ended after the bound arrived; it never spins on a round that is over. |
| 8 | — | `assert facts['zero_pump_context_is_the_session_context'] is True` and `assert facts['zero_channel_context_is_the_session_context'] is True` | the pump and the channel of the zero round read the **one** context of that round; an admission is never inferred from the identity of a context or from `owner is None`. |
| 9 | — | the phase document `n10-r07-zero-public-chain.json` (the recorded arguments, the frames of the pump, its error, its end and the state of the session) | the facts of the public chain are recorded **before** the assertions of the phase. |
| 10 | — | the phase document `n10-r07-zero-salvage.json` and the assertion that every owner that really started is **not alive** | the owners of the round of the zero expiry are joined with an explicitly bounded wait and their liveness is asserted. |
| 11 | the direct helper of the group was the **oracle** | the direct helper of the group is kept as a **supplement** (the original four assertions of the zero expiry of the original round are **unchanged**) and it is never the oracle | the contract permits a direct helper check as a supplement; the acceptance oracle is the public chain. |

The **positive** scenario of the group (the remaining of the round at the
admission, the published cleanup deadline, the actual remaining) and the
original four assertions of the zero expiry of the original round are
**unchanged**.

## M2 — N10-R10 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | the seam of the failed coordination stored the result of `_wait_for_outcome` (which may be `None`) and returned `REQUESTED` in every case | the seam runs a **checked** barrier: it demands the outcome of the **exact** generation, the expected kind of the ordinary failure and the **exact** original error object, and it stores the checked monotonic order, generation and object facts | the barrier could return without the specific outcome and its failure was not an oracle. |
| 2 | — | `assert barrier['failure'] is None`, `assert barrier['passed'] is True`, `assert barrier['returned'] == 'REQUESTED'` | the premise of the barrier **succeeded** and the cancel primitive really returned after it. |
| 3 | — | `assert barrier['observed_generation'] == generation`, `assert barrier['observed_error'] == 'RuntimeError'`, `assert barrier['observed_object'] is fault` | the barrier observed the outcome of the **exact** generation, the expected kind of the failure and the **exact** original error object. |
| 4 | — | `assert barrier['entered_at'] <= barrier['observed_at'] <= barrier['left_at']` | the **checked order** of the barrier is a fact of the test and not an assumption. |
| 5 | `published_before_cancel_return` was **written** and never asserted | it is still written and it is now **covered** by the checked barrier (`barrier['passed']`, `barrier['returned']`) | the boolean alone could not prove the order. |
| 6 | — | the two negative subcases `r10-barrier-absent` and `r10-barrier-wrong-generation` with the assertions `barrier['failure'] is not None`, `barrier['passed'] is False`, `barrier['returned'] is None`, `barrier['refused'] == barrier['failure']` | the barrier must **fail closed** on an absent and on a wrong-generation outcome; the premise is then **refused** and the subcase is never counted as a successful failed coordination. |
| 7 | — | the record of the barrier is captured **before** the main assertions of the phase and is written in the phase document | an exception that the production swallowed is never a test oracle. |
| 8 | — | `write_phase_not_run` and the marking of every phase that was **not** executed as `NOT_RUN` | a phase that did not run is never written as if it had run and it never carries a fabricated fact. |

The **confirmed** coordination, the required order of the schedule
(`r10-published-before-timeout`), the exact original error object, the
two real `Session.stop` calls, the `UNKNOWN` state and the history
checks of the reader are **unchanged**.

## M3 — N10-R07 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r07_the_context_of_the_round_reaches_every_layer`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | `transport.close()` was only on the **success path** of the child | the close of the transport of the child runs in an **inner** `finally`, and a **partial** construction closes the two endpoints that it really built | a failed assertion of the group left the drain thread of the transport and the workers of its endpoints behind. |
| 2 | the outer `finally` only called `session.stop()` and **ignored** its return | the outer `finally` calls the stop of the product (its own deadline, its own returned state) and **then** performs the **separate** salvage of the test owner | the stop of the product may retain live owners when the bound of the round is expired; the salvage is the work of the test. |
| 3 | — | the registry `_session_owners` (the background threads and the closer threads of the session) and `_channel_owners` (the drain thread of the channel and the workers of its two endpoints) | every owner that **really** started is registered **immediately**. |
| 4 | — | `_salvage_threads` joins every registered owner with an explicitly bounded wait (10 s) and reports `started`, `alive` and `joined` | the liveness of every started owner is a **fact** of the test and not an assumption. |
| 5 | — | the assertion that every started owner of the parent, of the zero round and of the two controlled rounds is **not alive**, plus the phase documents `n10-r07-parent-salvage.json`, `n10-r07-zero-salvage.json` and `n10-r07-controlled-failure-*.json` | the returned state of the product and the salvage are recorded **separately**. |
| 6 | — | `_started_owner` reports an owner **without an identity** as `started: False` and **never** joins it | a thread that never started is not a thread to join and no exit is inferred from it. |
| 7 | — | the two **controlled assertion failure** subcases `PARENT_ADMISSION` and `CHILD_TRANSPORT`: the distinctive sentinel `_R07Sentinel` is raised at an established checkpoint of a real round and caught again, and the test asserts that the sentinel was raised, that the gate of the test was **released** and that every started owner is **gone** | a receipt of the happy path cannot prove the negative path of the fixture. |

## What is **not** changed

* The two production modules (`tools/v0_s3_native_broker.py`,
  `tools/v0_s3_native_custody.py`) and the native runtime are **byte
  identical** to the baseline (`source-pins.json`).
* The other four test modules of the batch are **byte identical** to the
  baseline.
* The 189 node ids and their order are **identical** to the frozen list
  of the plan of the root (`node-identity.json`).
* No `skip`, no `xfail`, no removed assertion and no shrunk denominator.
* Every historical report, the root packets, the execution control, the
  MANIFEST and the trusted guard/runner/absence tools are untouched.
