# Correction17 — the static implementation of the three open Majors

**V1 / R1 / WP-R1-U3 / S3_P4.** Baseline `4dafa1f316242d8bd348b81c52f375aa37254754`
(the correction16 static candidate). The design of this correction is the
**approved** one: `design.md` (sections 2–9) and its authoritative
**correction addendum** `design.md` section 10, which closes the five
defects D1–D5 of the root design review. The root ACKed that design
(`ROOT DESIGN ACK — revision2 plus binding clarifications`) for the
**static implementation only**.

**One file of the product changed:** `tools/test_v0_s3_native_custody_correction10.py`.
No production source, no other test module, no contract, no threshold,
no root packet / control / MANIFEST and no historical report was touched.
The **189** node identities and their order are unchanged, the six other
sources are byte identical to the baseline, and the evidence of this
correction is written in the **new** directory of the correction 17.

**Nothing was executed.** The candidate was never imported, never
collected, never run with pytest, and no ctypes, runtime, native,
operating system business process, model, GPU, service, network, medium,
database, ledger or counter action was performed. The static checks of
this delivery are a text/AST/symtable/hash reading of the sources.

---

## 1. What changed, and where

| # | change | where | residual |
|---|---|---|---|
| 1 | the evidence of this module is written in the **new** directory of the correction 17 | `EVIDENCE_DIR` | M2 |
| 2 | `_R07OrdinaryAssertion` — the deliberate ordinary assertion of the group carries an **exact token** and is caught by **its own type** | module level | M3 |
| 3 | `_OwnerRegistry` holds the **provenance** of every start (`mark_starting` / `mark_started` / `mark_failed`, `pending_starts`, `start_provenance`, `generation`) | module level | M3 |
| 4 | `_StartObserver` — the observer of the starts: it forwards **every** start, never refuses one, and registers the **exact** thread object | module level | M3 |
| 5 | `_PhaseLedger` — `PLANNED` / `ATTEMPTED` / `PASSED` / `FAIL` / `NOT_RUN` with terminal states | module level | M2 |
| 6 | `_owner_start_state` — `NEVER_STARTED` only with a **proven** provenance, otherwise `UNKNOWN` | module level | M3 |
| 7 | `_salvage_threads` — the **classification** is inside the per-owner guard, every error is kept in a **list**, the wait is cropped by the remaining budget | module level | M3 |
| 8 | `_assert_salvage_proved` / `_prove_salvage` — an owner that met an error fails the proof | module level | M3 |
| 9 | `_capture_stop` — the **actual** evidence keys, the live state, the retention and the **identity** of the retained broker against the broker of the round, an explicit `snapshot_error` | module level | M3 |
| 10 | `_registry_owners` — the **reversed** fallback arguments are fixed and the provenance of the starts is merged into the hints | module level | M3 |
| 11 | `_drain_owners` — the **bounded drain** with one overall bound of 30 s per round, the quiescence asserted **after** the drain | module level | M3 |
| 12 | `start_round` returns the **actual** return value of the public `NativeCustodySession.start` | N10-R07 | M1 |
| 13 | the zero round: the **class** method is patched, the actual error value is separated from its `repr`, the returned state of the public start is captured and used, the retention oracle checks the **value** and the **identity**, the order of the start/pump/reply/gate/queue is recorded and asserted | N10-R07 | M1 |
| 14 | the parent round: the observer is armed around the round, the owners are drained, the close failures of the child must be **empty** | N10-R07 | M3 |
| 15 | the controlled subcases: the cleanup region is moved **outward**, the deliberate failures are raised **inside** it and caught **outside** of it, the constructor seam takes effect on the **exact** drain of the child, the close oracle is **exact** | N10-R07 | M3 |
| 16 | the seam of the barrier finalises the barrier on **both** paths, persists it as a **real document** and publishes the completion | N10-R10 | M2 |
| 17 | the schedules of N10-R10: the construction is **inside** the guard, the barrier is waited for **after** its cause, the documents are persisted before they are marked, an executed failure is a **FAIL**, the result is written **last** | N10-R10 | M2 |
| 18 | the outer inventory of N10-R10 is installed **before** any setup, is **complete** (27 names) and unique, and the whole body of the test is guarded | N10-R10 | M2 |

---

## 2. The mapping of every Major: event, oracle, negative oracle, cleanup

### M1 — the public zero-admission chain (N10-R07)

| event (what really happens) | the oracle of the group | the negative oracle (what fails) | the cleanup |
|---|---|---|---|
| the public `NativeCustodySession.start` is called on the round of the zero expiry | `zero_start_return` is the value that the public operation **returned** (`start_round` returns it) | the returned state is not `UNKNOWN_RETAINED` | the gates are released and the owners are drained in the `finally` of the block |
| the read of the **broker** is held at the gate | the patch is `patch.object(broker_module.BrokerProcess, 'read', zero_gated_broker_read)` — the **class** is the target and the replacement forwards the original signature and the original result | the gate was never reached (`zero_gate_facts` is empty) or it timed out (`released is not True`) or it was not bounded (`timeout != ZERO_GATE_SECONDS`) | the gate is released **unconditionally** in the `finally` |
| the pump of the round reaches its admission | `zero_premise['pump_at_admission'] is True` and the recorded order `E1 < E2 < E3 < E4 < E5 < E6 < E7` | the order is violated or an event was never observed | the same `finally` |
| the pump is **not** at the end of its stream | `zero_premise['pump_eof_at_admission'] is False` | the pump was at the EOF before the admission | the same `finally` |
| the pump did **not** fail | `zero_premise['pump_error_is_none'] is True` and `pump_error_repr is None` — the **actual** value, never the display form | the pump failed before the admission | the same `finally` |
| the reply of the parent is waited for | `zero_reply_waits[-1] == 0.0` (the actual argument) | the reply asked for a wait after the expiry | the same `finally` |
| the attached pump asks the queue for **nothing** | `zero_queue_waits[-1] == 0.0` and `zero_pump is zero_session._pump` and `facts['zero_pump_finished'] is True` | the pump is not the pump of the session, it did not end, or the queue asked for a wait | the same `finally` |
| the public start failed **with the timeout** | `'CUSTODY_CHANNEL_TIMEOUT' in facts['zero_failures']` and `'CUSTODY_CHANNEL_EOF' not in facts['zero_failures']` | the round ended at the EOF instead of the timeout | the same `finally` |
| the round **retained** its broker | `facts['zero_broker_retained'] is True`, `zero_session.broker is zero_broker`, `identity_source == 'PARENT_ORIGINAL_HANDLE'` and the pid of the identity is the pid of the broker | the retention value is not `True`, the retained object is not the object of the round, or the identity is a claim | the same `finally` |
| the owners of the round are released | `_assert_salvage_proved(zero_salvage, 'the round of zero')` — no unknown start state, no error, every started owner joined and not alive | an owner was left behind or met an error | the bounded drain, one overall bound of 30 s |

### M2 — the truthful inventory of the phases (N10-R10)

| event | the oracle | the negative oracle | the cleanup |
|---|---|---|---|
| the construction of the chain of a schedule | the construction is **inside** the local guard; the holders are initialised to `None` before it | a construction that failed half way is an **attempted** construction with a durable `FAIL` document | the teardown of the schedule runs in the `finally` and skips a `None` holder |
| the barrier of the publication | the seam **finalises** the barrier in a `finally` — on the successful path **and** on the refused path — records the failure, the return state and the generation, persists the snapshot as a **real document** and publishes `barrier_completed` | the barrier never completed → the phase persists `{'status': 'FAIL', 'premise': 'BARRIER_NOT_COMPLETED'}` and fails; the phase never continues with an empty barrier | the seam always finalises; the phase always writes a document |
| the wait for the barrier | the wait happens **after** the cause (`bind_deadline` + `clock.advance`) and never before it | the cause was moved ahead of the wait | the same |
| the facts of the barrier | the phase reads the **persisted** snapshot of the seam (`api.barrier_snapshot`), never a live re-read | a late snapshot can never look completed | the same |
| the two real stops of the round | the stops are marked `attempt()` **before** the call; the document of a stop is written **before** its assertions | an attempted stop that raises is a **FAIL**, never a `NOT_RUN` | the same |
| the document of a phase | the raw facts are written **before** the assertions; the persistence happens **before** the name is marked | a document that is marked really exists on the disk | the same |
| the result of a phase | the result document is written **last**, after both stops **and** after the cleanup; it is `PASSED` only when the barrier check, both stop checks and the cleanup all passed | a later failed stop makes the result `FAIL` while the earlier checks keep `PASSED` and their facts | the same |
| a phase that was never entered | the outer inventory writes `NOT_RUN` with the reason and **no fact** | a `NOT_RUN` document never carries a fact | the same |
| the inventory of the group | the complete list of **27** names is installed before any setup; it is unique and every name reaches a terminal state | a name that was entered and that failed is a `FAIL`; a name that was never entered is a `NOT_RUN` | the same |
| the owners of the schedule | the drain of the schedule is bounded and the quiescence is asserted **after** it | a drain that is not quiescent is a `FAIL` | the drain |

### M3 — the owner cleanup region, the genuine unwinding and the bounded salvage (N10-R07 and N10-R10)

| event | the oracle | the negative oracle | the cleanup |
|---|---|---|---|
| the start of the round and the assertion of its state | both are **inside** the cleanup region; the assertion is made on the **returned** evidence of the public start | a failure of either is cleaned up, joined and proved | the region runs in the `finally` of the region |
| the deliberate sentinel | `failure['class'] is _R07Sentinel` and `failure['token'] == checkpoint` | the type is not the expected class or the token differs | the cleanup region runs **while** the failure unwinds |
| the deliberate ordinary assertion | `failure['class'] is _R07OrdinaryAssertion`, `failure['is_assertion_error'] is True` and `failure['token'] == _R07OrdinaryAssertion.TOKEN` | an unrelated failure of the group is never taken for the deliberate one (it is caught by **its own** type) | the same |
| the deliberate constructor failure | `failure['class'] is _R07ConstructorFailure` and `failure['token'] == 'CONSTRUCTOR_FAILURE'`; the seam took effect on **exactly one** drain and that drain is the drain of the child | the seam touched another thread, or it did not take effect at all | the same |
| the cleanup ran **while** the failure unwound | `controlled['cleanup_ran_while_unwinding'] is True` | the cleanup did not run during the unwinding | the same |
| the injected close failure | `CLOSE_FAILURE` is a **cleanup only** case: `controlled['failure'] is None`, `cleanup_ran_while_unwinding is False`, **exactly one** failure, `owner == 'controlled:transport'`, `type == 'RuntimeError'`, `detail == 'controlled_close_failure'` and **no** failure with another owner or another type | an unrelated close or endpoint error fails the subcase | the region continues with every other cleanup action |
| the physical cleanup of the round | `_assert_salvage_proved(controlled['salvage'], ...)` and `controlled['quiescent'] is True` | an owner was left behind, met an error or was not quiescent | the bounded drain |
| the start of a thread | the observer registers the **exact** thread object before the original start and marks it after the start returned | a thread whose start did not return is `UNKNOWN` and it fails the proof | the drain |
| the state of an owner | `NEVER_STARTED` only with a **proven** provenance, otherwise `UNKNOWN` | an ident-less owner without a provenance is `UNKNOWN` | the same |
| the salvage | **every** owner is attempted; a failure of the classification, of the join or of the liveness query is retained in a **list** with its kind, its exact type and its detail | an owner with an error or with `alive is None` fails the proof | the same |
| the stop of the product | the **returned** state, the exception, the live state, the **actual** evidence keys and the **identity** of the retained broker are captured **before** the salvage | a snapshot that failed carries an explicit `snapshot_error` and it never certifies a cleanup | the same |
| the deadline of the product | the fixture never renews, publishes or extends a deadline of the round; the waits of the fixture are its own bounded waits (10 s per owner, 30 s per drain, 15 s per observation, 30 s per gate) | — | — |

---

## 3. The removed assertions and their equivalent or stronger replacements

The independent review of the correction16 candidate recorded **seven**
removed predicate units with **eight** prior occurrences (evidence01).
Every one of them is replaced by an **equal or stronger** predicate in
this candidate; two further weakened forms are restored in a stronger
form. No predicate is weakened and none is dropped.

| # | prior line | removed predicate | the replacement in this candidate | stronger because |
|---|---|---|---|---|
| A1 | 2225 | `zero_session.state == 'RUNNING'` | `facts['zero_state'] == 'UNKNOWN_RETAINED'` — the state of the value that the **public start returned** — with `'CUSTODY_CHANNEL_TIMEOUT' in facts['zero_failures']`, `'CUSTODY_CHANNEL_EOF' not in ...` and the retention value and identity | a transient live attribute is replaced by the **terminal** state that the public operation returned, with the exact cause and the actual retained resource |
| A2 | 2231 | `zero_attached_pump is not None` | `zero_pump is zero_session._pump` **and** `facts['zero_pump_context_is_the_session_context'] is True` **and** `facts['zero_pump_finished'] is True` | identity, context and a proven end instead of a presence |
| A3 | 2233 | `zero_attached_pump.is_alive()` | `facts['zero_pump_finished'] is True` **and** `zero_queue_waits[-1] == 0.0` | a liveness snapshot is replaced by a **completed lifecycle** with the actual argument of the read |
| A4 | 2273 | `zero_held.wait(15.0)` | `zero_premise['pump_at_admission'] is True` **and** `zero_premise['pump_eof_at_admission'] is False` **and** `zero_gate_facts[0]['released'] is True` **and** `zero_gate_facts[0]['timeout'] == ZERO_GATE_SECONDS` **and** the recorded order `E1<E2<E3<E4<E5<E6<E7` | a bare "the event fired" is replaced by the no-EOF fact, the bounded gate fact and the required ordering |
| A5 | 2349 | `item['alive'] is False` (the zero round) | `_assert_salvage_proved(zero_salvage, 'the round of zero')` — no `UNKNOWN` start state, no error, and every started owner joined and not alive | a per-item check becomes a **whole-round** proof that also rejects an unknown start, an unjoined owner and a recorded error |
| A6 | 2495 | `item['alive'] is False` (the parent round) | the same whole-round proof over the drain of the parent round, plus the stop exception with the live state and the retention captured **before** the salvage, plus the quiescence condition | the parent round gains the same (and stronger) proof, the stop facts and the quiescence |
| A7 | 2788 | `controlled['sentinel'] == '_R07Sentinel'` | `failure['class'] is _R07Sentinel` (the **class object**) **and** `failure['token'] == checkpoint` **and** `controlled['cleanup_ran_while_unwinding'] is True` | a **string** equality on a type *name* becomes an **identity** check on the type, the exact token and the proof that the cleanup ran during the unwinding |
| A8 | 2796 | `item['alive'] is False` (the controlled subcases) | the whole-round proof over the drain of **every** controlled checkpoint (`_assert_salvage_proved`) plus the exact close oracle | a per-item check becomes a whole-round proof for every checkpoint and an exact close oracle |
| A9 | 3398 | `assert controlled['failure'] is not None` | the **exact** type and the **exact** token per checkpoint (`_R07Sentinel` / `_R07OrdinaryAssertion` / `_R07ConstructorFailure` / `RuntimeError`) | any non-`None` failure is replaced by the exact expected failure |
| A10 | 3411 | `assert any(item['owner'] == 'controlled:transport' ...)` | exactly one failure, the exact owner, the exact type, the exact message, and **no** unrelated close or endpoint failure | the presence of a record is replaced by the exact identity of the failure and the rejection of unrelated failures |

The static checker of this delivery proves the presence of every
replacement and the absence of every forbidden form
(`reports/v0-s3/product-gate0/implementation-native-custody-correction-17/static-checks.json`).

---

## 4. The inventory of the group of N10-R10 — the arithmetic

The inventory is **derived from the operations that are really
instrumented** and it is **complete** and **unique**:

| part | names | count |
|---|---|---|
| four timeout schedules (`r10-timeout-confirmed`, `r10-timeout-failed`, `r10-barrier-absent`, `r10-barrier-wrong-generation`) with five names each: the result of the phase, the construction of the chain, the barrier of the publication, the first stop and the second stop | 4 × 5 | 20 |
| the published-before-timeout schedule with four names: the result of the phase, the construction of the chain, the first stop and the second stop — its construction is instrumented like the construction of the other schedules | | 4 |
| the three documents of the earlier work of the group: `r10-first`, `r10-second`, `r10-coordination` | | 3 |
| **total** | | **27** |

Every name is `plan`ned before anything runs. A name that was entered
and that failed is a `FAIL` with the facts that it really observed; a
name that was never entered is a `NOT_RUN` without a fact; a name whose
check held is a `PASSED` and it is terminal. **No phantom document is
created** to satisfy a count and **no node of the 189 was touched**.

---

## 5. The delta between the approved design and this implementation

The design is implemented as it was approved, with five declared
differences:

1. **the inventory has 27 names and not 26** — the published-before-timeout
   schedule contributes a **construction** name, because its construction is
   instrumented inside the guard exactly like the construction of the four
   timeout schedules, and a construction that fails must record an
   attempted `FAIL`. This is the case that the root clarification named
   ("explicitly include any published construction ... only if actually
   instrumented").
2. **`_R07OrdinaryAssertion`** is a subclass of `AssertionError` with a
   token. The exact-token requirement cannot be met with a bare `assert`,
   because the test runner rewrites the message of an assertion; the
   deliberate ordinary assertion is therefore really raised and really
   fails, and its token is normalised so that the **exact** token survives.
   It is caught by **its own** type, so an unrelated failure of the group
   is never taken for the deliberate one.
3. **the drain is applied to every round of the two touched nodes** — the
   parent round, the zero round, the five controlled subcases, the earlier
   work of N10-R10 and the five schedules of N10-R10 — and not only to
   the rounds that the design of §10.3 named.
4. **the quiescence of a drain is asserted after the drain** and a failed
   proof raises the failure of the proof when no other failure is
   unwinding; the design named the truthfulness of the failure and this
   is its exact implementation.
5. **the evidence of the module is written in the new directory of the
   correction 17** — the evidence of the correction 16 stays untouched.

---

## 6. The static checks of this delivery

`static_checks.py` is a **static** checker: it reads the sources as
text, it parses them with the standard `ast` and `symtable` modules and
it writes `static-checks.json`. It never imports, collects or executes
anything.

| check | result |
|---|---|
| the pins of the two production sources and of the four other test modules | unchanged |
| the 189 node identities and their order | 189, unique, the frozen order |
| the names, the order, the signatures and the decorators of the fourteen nodes of this module | unchanged |
| no skip, no xfail, no skipif, no deleted node | none |
| the module compiles in memory | yes |
| every global that the module reads is really bound | yes (symtable) |
| the eight removed assertions and the two weakened forms | absent or replaced |
| the ten replacements of the mapping of §3 | present |
| the forbidden forms of the correction16 candidate | absent |
| the required forms of the correction 17 | present |
| the inventory of N10-R10 | 27 names, unique, all present |

`static-checks.json`: **93 checks, 0 failed**.

---

## 7. The pins and the identity of the nodes

| source | before | after | changed |
|---|---|---|---|
| `tools/v0_s3_native_broker.py` | `06cfc951…bb83` | `06cfc951…bb83` | no |
| `tools/v0_s3_native_custody.py` | `7f26e927…4581` | `7f26e927…4581` | no |
| `tools/test_v0_s3_native_custody.py` | `fe96d2ff…7d32` | `fe96d2ff…7d32` | no |
| `tools/test_v0_s3_native_custody_regressions.py` | `03250ea0…cb93` | `03250ea0…cb93` | no |
| `tools/test_v0_s3_native_custody_correction05.py` | `8563989f…d130` | `8563989f…d130` | no |
| `tools/test_v0_s3_native_custody_correction07.py` | `dc74cf7f…6cdf` | `dc74cf7f…6cdf` | no |
| `tools/test_v0_s3_native_custody_correction10.py` | `3c1c89e6…74a` | the sha of the candidate | **yes** |

The full pins are in `source-pins.json`; the identity of the 189 nodes,
with their signatures, their decorators and their order, is in
`node-identity.json`.

---

## 8. The request of the finite validation

`validation-plan-request.json` is a **REQUEST** and not an execution.
It asks the root to freeze and to ACK **three** commands — the
observation of the absence of the counter before the batch, the guarded
validation of the 189 nodes and the observation of the absence of the
counter after the batch — with **one** batch of at most **300 s**, the
frozen environment, the pinned sources and the frozen order of the 189
nodes. Nothing of it was run.

---

## 9. What this delivery does **not** claim

* **No Major is closed by the implementer.** The three Majors of the
  correction16 review are addressed by this candidate and they are closed
  by an **independent** review, not by this report.
* **No dynamic result.** `dynamic15 = NOT_RUN`, `dynamic16 = NOT_RUN`,
  `native = NOT_PROVEN`, `stage_pass = false`, `product_acceptance = false`,
  `human_signoff = false`.
* **No execution** of the candidate, no runtime plan ACKed, no budget
  consumed, no 429 and no approval refusal.
* The historical 189 green evidence of the correction 14 stays historical
  and it is not extended to this candidate.
