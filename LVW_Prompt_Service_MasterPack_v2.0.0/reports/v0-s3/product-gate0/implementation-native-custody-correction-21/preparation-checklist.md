# Correction 21 — preparation checklist (counterexample → control flow)

Static preparation only. No candidate import, no collection, no pytest, no
ctypes, no runtime, no native call, no OS business process, no model, no GPU,
no service, no network, no media, no DB, no ledger/counter side effect.
Scope: `tools/test_v0_s3_native_custody_correction10.py` only, plus this NEW
report directory. Baseline delivery `845b786…`, baseline candidate `206a7fe…`.

## The five residual counterexamples of the review of the correction 20

| # | Counterexample (20 review) | Concrete defect in the baseline blob | Narrow local control flow of the correction | Candidate lines |
|---|---|---|---|---|
| 1 | **M2.a** — the final recovery cannot preserve all cleanup facts: the timeout and the published final documents export only `drain['attempts']`/`drain['proof']`, the coordination exports attempts/proof, the second owner error `E2` exists only in the local `all_salvage` and the final-resnapshot error only in `drain['errors']` | `_prove_salvage` returns only the **first** failed owner; `drain['errors']` is taken **before** the last attempts snapshot; the callers of the drain drop `all_salvage`, the final `salvage` and the error list | One helper `_drain_facts(drain)` returns the **complete** bundle (`drain_salvage`, `drain_all_salvage`, `drain_owner_errors`, `drain_attempts`, `drain_errors`, `drain_quiescent`, `drain_proof`) and every durable final document of a round **unpacks** it; the drain keeps the **per owner** errors of **every** iteration in `owner_errors`; the actual returned state of the public stop and the original failure join the bundle | helper `790`; drain `1340`/`1394`; zero `3926`; parent `4263`; controlled `4974`; timeout `6747`/`6802`; published `7350`/`7403`; early `7820`; coordination `8069` |
| 2 | **M2.b** — the incomplete-barrier terminal rewrite omits the persistence fields: `barrier_failed_facts` has identity booleans and `completion=False` but no `barrier_persisted` and no `barrier_write_error`, and the exception handler skips the name because the ledger already closed it | the branch at 5980–6003 builds the terminal document without the persistence facts; the handler at 6251–6291 skips a name whose state is no longer `ATTEMPTED` | the terminal document of the **not completed** barrier carries the **actual** `barrier_persisted`, the **actual** `barrier_write_error`, the presence of the snapshot and the **observed** snapshot (`observed`, `observed_generation`, `observed_error`, `return_state`) — even when they are absent; the identity stays a **boolean**; the status stays `FAIL`/`executed=True`; the shared store keeps the same fields before the write | `6313`–`6343` |
| 3 | **M3.a** — a late controlled release swallows the exact interruption after all verdicts: the last `frames_ready.set` runs in the outer `finally` **after** the facts, the evidence and the interruption check, and the function then returns | the outer `finally` of 4808–4815 appends `K` and the next statement (4816) returns `facts` | the outer `finally` restores the observer and the patch **unconditionally** (their failures are recorded), releases the gate **last**, then performs a **guarded final update** — the facts get the complete cleanup history, the evidence is closed with it — and only then the **priority**: the failure that is unwinding wins, then the **first** exact pending interruption, then the ordinary proof | `5032`–`5085` |
| 4 | **M3.b** — the deferred cancellation is rethrown **inside** the startup-owner loop and the direct joins can raise and skip the remaining owners | `for owner in owners:` at 5130–5138 joins the first owner and calls `_raise_first_interruption` **inside** the loop; the sites 1506–1510, 4223–4228 and 4305–4306 join or query **directly** | one helper `_join_owner(label, thread, errors, interrupts, …)` guards the join **and** the liveness query of **one** owner and records the failure with its exact type, its exact detail and the **exact** object of a cancellation; **every** owner is attempted, the priority is enforced **after** the whole traversal and the ordinary proof runs **after** it | helper `845`; startup `5405`–`5436`; the audited sites below |
| 5 | **M3.c** — the post-drain registry query can replace the original unwinding or the pending `K1`: `registry.facts()` is called **before** the guarded writer of the zero and of the controlled round and it is the very query of the `entries()` that the drain fallback tolerates | `zero_registry.facts()` at 3575 and 3762, `controlled_registry.facts()` at 4748 — all outside the guarded write | one helper `_registry_snapshot(registry, errors, interrupts, label)` guards the query: the failure is retained with its exact type and detail, the **exact** object of a cancellation is retained, the snapshot of a failed query is **unknown** (`None`) and it is an explicit diagnostic that **fails the proof** — never a fabricated empty registry | helper `817`; zero `3701`/`3909`; parent `4235`; controlled `4947` |

## The callsite inventory of the **same** root cause (audited once)

| # | Site (baseline → candidate) | Class | Repair |
|---|---|---|---|
| 1 | `1506–1510` → `1622` | cleanup `finally`, one owner | `_join_owner`, priority after, proof last |
| 2 | `1607–1608` → `1732` | cleanup `finally`, one owner | `_join_owner` |
| 3 | `1974–1979` → `2103` | cleanup `finally`, one owner | `_join_owner`, priority after, proof last |
| 4 | `4223–4228` → `4409` | cleanup `finally`, stop **and** join | guarded `stop_accepting`, `_join_owner(join_bounded)` |
| 5 | `4305–4307` → `4512` | cleanup `finally`, join **before** a close | `_join_owner` — the close of the endpoint is never skipped |
| 6 | `5006–5011` → `5279` | cleanup `finally`, one owner | `_join_owner`, priority after, proof last |
| 7 | `5130–5138` → `5405` | cleanup `finally`, **multi**-owner loop | every owner attempted, priority **and** proof after the traversal |
| 8 | `5194–5196` → `5500` | cleanup `finally`, one owner | `_join_owner`, priority after, proof last |
| 9 | `5271–5280` → `5586` | cleanup `finally`, settle loop + join | guarded `settle`, `_join_owner`, priority after, proof last |
| 10 | `8215–8216` → `8594` | cleanup `finally`, join **before** the stop | `_join_owner` — the stop of the round is never skipped |
| 11 | `3575`/`3762`/`4080`/`4748` → `3701`/`3909`/`4235`/`4947` | registry query | `_registry_snapshot` |

**Inspected and classified, not repaired** (they are **scenario** steps of a
`try` body, not cleanup actions: they skip no cleanup and no owner): the
`creator.join` of the scenario at 1602, the `reader_thread.join` of the
scenario at 1933, the `reader.join` of the scenario at 4291, the
`thread.join(5.0)` of the never-started subcase at 5631, the confirmation
`worker.join` of the seam at 5617, the `reader_thread.join` of the timeout
phase at 5967 and the `reader.join` of the coordination at 7588. The closes
of the endpoints and of the channels are either guarded already or are the
**last** action of their cleanup region.

## Boundary rules that were held

* The M1-closed public driver, its values, its order and its oracles are
  untouched; only the shared cleanup of the zero round changed.
* The 189 identifiers, their order and their signatures are unchanged; the
  assertion predicates are **414 → 414** with **0 removed** and **0 added**.
* The six other sources of the correction are byte identical (SHA256 pins).
* The 28-name inventory of the group is unchanged; the bundle of the facts of
  a drain is a **key set of the existing documents** and not a 29th phase.
* No new manager, no new framework, no new product obligation, no new
  threshold and no 189th node.
* The evidence root of the module moves to the NEW correction-21 directory;
  the documents of correction 20 stay where they are and are never
  overwritten, never deleted and never replaced by a summary.
