# Correction 22 — the mapping of the six residual counterexamples

Coordinate V1/R1/WP-R1-U3/S3_P4. Baseline delivery `08e2096…`, baseline
source candidate `ed4afb5…`. Candidate: `tools/test_v0_s3_native_custody_correction10.py`,
SHA256 `f1f8fe1a4167000265e3490417205adb52bcbe84ef54131c3835bfc6a895e6ec`
(Git blob `e7506faf1575f2a05f5e913a07171f204fe36582`, 9219 lines).

The **central rule** of this correction is the order of the cleanup:

```
ALL the actions of the cleanup  ->  the COMPLETE facts and a durable
evidence attempt  ->  the priority of the failures:
the original that is unwinding > the FIRST exact pending interruption >
the ordinary error of the proof
```

A deliberate failure that was already **caught** is **not** a failure that is
unwinding: it never exempts a **new** unexpected error of the cleanup from
failing the round.

## The three helpers that carry the rule

| Helper | Line | Contract |
|---|---|---|
| `_cleanup_verdict(errors, base_proof, detail)` | `699` | the **final** verdict of a cleanup: the proof that was already found is **preserved** and the errors of the cleanup are **added** to it; an error never erases an error and never disappears because the proof already failed |
| `_owner_alive(join_fact)` | `722` | the **actual** liveness of an owner is the fact that the **guarded** join returned; the query is never repeated outside its guard; an **unknown** liveness is never read as the end of an owner; an owner that never started has no thread and it is not alive |
| `_publish_cleanup(facts, writer, errors, interrupts)` | `739` | the document of a cleanup carries **every** actual error and **every** actual interruption and it is written **before** the priority; a write that failed is an **actual** error: it is retained with its exact type and detail, the facts are updated **in memory** and the durability is a **best effort** (one second attempt) |

They are three local functions in the style of the helpers of the correction 21
(`_join_owner`, `_release_gate`, `_registry_snapshot`). They are **not** a
framework: no manager, no registry, no state machine, no new phase, no new
node.

## M2.a — the last controlled write can fail silently

* **Baseline** `4955–4974`, `5062–5086`, `5195–5205`.
* **Trigger** the controlled `CLOSE_FAILURE` meets its exact singleton oracle
  and the physical joins, every earlier write succeeds and **only** the last
  write of the subcase raises an ordinary `OSError`.
* **Expected (baseline)** the error is retained in the last actual facts, the
  subcase fails closed after the cleanup and the original unwinding exception
  is preserved.
* **Actual (baseline)** the error is appended **after** the copied facts, the
  proof is not recomputed, the returned and the durable facts keep
  `proof_failure = None` and the caller passes.
* **Repair** the outer `finally` of the subcase (`5252–5329`) reads the state
  of the unwinding **first** (`5257`), keeps the index of the errors of the
  inner region (`5262`), **recomputes** the verdict of the subcase with every
  actual error of the last actions (`5301`, `5311`), attempts the **last**
  write through `_publish_cleanup` (`5304`) and **enforces** the verdict
  (`5324–5328`): the original unwinding wins, then the **first** exact pending
  interruption, then the ordinary verdict.
* **Static proof** `M2.a_final_controlled_verdict` — a **real AST order**
  check of the `finally` of the subcase.

## M2.b — the errors of the query of the registry of the zero round vanish

* **Baseline** `833–842`, `3909–3926`.
* **Trigger** the drain of the round of the zero expiry has already produced a
  proof `D` and the distinct post-drain query of the registry raises an
  ordinary error `E`; the evidence is written.
* **Expected (baseline)** the additional exact type and detail of `E` survive
  next to the original failure `D`.
* **Actual (baseline)** `E` is only in `zero_registry_errors`, the proof keeps
  `D` and the document has **no field** for the errors of the query.
* **Repair** the verdict of the round is recomputed with the errors of the
  query (`4086–4088`) and the document of the round carries them as the
  **explicit durable field** `registry_errors` (`4099`). The parent already
  exported `registry_errors` (`4435`) and the controlled round merges its
  query errors into its own cleanup list — the audit found no other auxiliary
  list with the same omission.
* **Static proof** `M2.b_zero_registry_durable` — a **real AST** check of the
  durable field and of the recomputed verdict.

## M3.a — R12 raises the interruption before the public stop of the round

* **Baseline** `8594–8607`.
* **Trigger** the guarded join of the owner of the round retains the exact `K`
  and no original exception is unwinding.
* **Expected (baseline)** every action of the cleanup is attempted, then the
  priority: the original unwinding, the **first** exact interruption, the
  ordinary proof.
* **Actual (baseline)** `_raise_first_interruption` (`8598`) raises before the
  stop (`8604–8607`), the stop is skipped, its ordinary exception is silently
  swallowed and `r12_cleanup_errors` has no consumer at all.
* **Repair** the guarded join (`8978`), then the **guarded** public stop
  (`8989–8995`) that retains the exact type, the exact detail and the returned
  state of the stop, then the durable facts (`8998–9005`), then the priority
  (`9008`), then the ordinary proof (`9011–9013`) and the ordinary error of
  the cleanup (`9015–9016`).
* **Static proof** `M3.a_r12_all_actions_before_priority` — a **real AST
  order** check plus the absence of the silent `except Exception: pass`.

## M3.b — the close of the awaited endpoint replaces the original or `K1`

* **Baseline** `4507–4519`.
* **Trigger** the gate or the join of the reader retains the exact `K1` and the
  close of the endpoint raises `K2`; or an original failure `O` is already
  unwinding and the close raises `K2`.
* **Expected (baseline)** `K2` is retained as a secondary diagnostic, every
  remaining action is attempted, `K1` (or `O`) is the failure that leaves.
* **Actual (baseline)** `K2` escapes the bare `endpoint.close()` (`4516`),
  bypasses the priority (`4519`) and replaces `K1` or `O`.
* **Repair** the close is guarded (`4710–4721`), the facts of the cleanup are
  complete and durable (`4722–4729`), the priority is enforced **outside** the
  cleanup region (`4732`) and the ordinary errors of the cleanup are consumed
  (`4735–4737`).
* **Static proof** `M3.b_guarded_closes` — a **real AST** check: no direct
  close of an endpoint or of a channel in a cleanup region is unguarded and the
  priority of the await is not a statement of its `finally`.

## M3.c — the errors of the fixture cleanups have no consumer

* **Baseline** `858–877`, `5404–5441`, `5585–5612` and the cited sites
  `1622–1635`, `4419–4434`, `5278–5287`, `5503–5515`.
* **Trigger** the guarded join of the first owner raises an ordinary error `E`
  and every later join succeeds and every liveness check returns `False`.
* **Expected (baseline)** every owner is attempted, `E` is retained, the
  cleanup proof fails and the evidence carries `E`.
* **Actual (baseline)** the error list is appended and **never read**, the
  follow-up `is_alive` query is unguarded and can escape, the query of the
  owners in flight (`5591`) and the lookup of the thread of the owner (`5599`)
  are unguarded, and the priority of the interrupted start is **inside** the
  `if thread is not None`.
* **Repair** the liveness of an owner is the fact of the guarded join
  (`_owner_alive`), the errors of every region feed a verdict and fail the
  round (`raise AssertionError('the cleanup of … met %s')`), the facts of the
  cleanup are durable in the document of the phase (`_publish_cleanup`), the
  queries of the cleanup are guarded and the priority is deferred **after**
  every action. The twelve new consumers are listed in
  `preparation-checklist.md`.
* **Static proof** `M3.c_error_list_consumers` — a **real AST dataflow**
  check: every list of the errors of a cleanup is read somewhere else than in
  its own `append` — and `M3.c_deferred_priority` — a **real AST nesting**
  check: no loop over the owners re-raises inside its body.

## M3.d — a late ordinary error of the cleanup does not refresh the proof

* **Baseline** `5034–5086`, `5195–5205`.
* **Trigger** the last release, the disarm or the stop of the patch fails with
  an ordinary error after the proof of the subcase was finalised; or the
  deliberate failure was already caught and a new error follows.
* **Expected (baseline)** the final proof and the verdict are updated with
  every unexpected error of the cleanup and the exact cancellation has its
  priority after all the actions.
* **Actual (baseline)** the error is appended after the proof was frozen, the
  proof stays `None` and the subcase passes; the `not raised` clause exempts
  the pending `K` when a deliberate failure was caught.
* **Repair** the verdict is recomputed with the errors of the last actions
  (`5301`, `5311`), the `not raised` exemption is **gone** (`5324–5328`) and
  the exact expected `CLOSE_FAILURE` singleton stays the only allowed
  injected fault: it is recorded in `close_failures` and not in the cleanup
  list, so the verdict of that subcase stays `None`.
* **Static proof** `M2.a_final_controlled_verdict` — the check of the absence
  of the exemption and of the order of the actions.

## The same-class call sites that were repaired with them

| # | Region | Baseline | Candidate | The same-class defect |
|---|---|---|---|---|
| 1 | the recovery of the façade | `1617–1635` | `1695–1727` | the errors of the join had no consumer; the liveness was requeried outside the guard |
| 2 | the creation of the child | `1727–1742` | `1823–1846` | the errors of the join had no consumer; the facts of the join were not durable |
| 3 | the reader of the launch | `2094–2113` | `2198–2233` | the lookup of the thread was unguarded; the priority and the proof were **inside** the `if` and were skipped when the thread was absent |
| 4 | the admission of the parent | `3460–3475` | `3637–3645` | the errors of the release of the gate had no consumer |
| 5 | the endpoints of the linearization | `2816`, `2907`, `2936` | `2910`, `2948`, `2963` | three direct closes could replace the original unwinding failure |
| 6 | the worker of the dispatch | `4404–4434` | `4594–4625` | the errors had no consumer; the liveness was requeried outside the guard |
| 7 | the endpoint of the await | `4507–4519` | `4700–4737` | the close was unguarded and the errors had no consumer |
| 8 | the controlled subcase | `4849–5086` | `5252–5329` | the late errors did not refresh the proof; `not raised` exempted the `K` |
| 9 | the worker of the retry | `5276–5287` | `5523–5549` | the errors had no consumer; the liveness was requeried outside the guard |
| 10 | the owners of the startup | `5404–5441` | `5668–5722` | the errors had no consumer; the liveness was requeried outside the guard |
| 11 | the tightener of the deadline | `5503–5515` | `5783–5812` | the errors had no consumer; the liveness was requeried outside the guard |
| 12 | the interrupted start | `5585–5612` | `5886–5948` | the query of the owners and the lookup of the thread were unguarded; the priority was **inside** the `if` |
| 13 | the round of R12 | `8592–8607` | `8976–9017` | the priority preceded the stop; the stop was silently swallowed |
| 14 | the rounds of R11, R13 and R14 | `8430`, `8665`, `8697`, `8763` | `8770`, `9079`, `9122`, `9205` | four salvage stops silently passed an ordinary exception |
| 15 | the channels of R11 | `8450`, `8472` | `8805`, `8838` | two direct closes could replace the original unwinding failure |

## The equivalence of the moved assertions

The multiset of the predicates is **414 → 414**: **8 predicates moved**, **0
added**, **0 removed**. Every moved predicate is the **requery of the liveness**
of an owner and every replacement is **equivalent or stronger**:

| Baseline predicate | Occurrences | Candidate predicate | Occurrences | The mapping |
|---|---|---|---|---|
| `not thread.is_alive()` | 4 | `not _owner_alive(launch_join)`, `not _owner_alive(item)` (the startup owners), `not _owner_alive(interrupted_join)` and `not _owner_alive(r12_join)` | 4 | the value is the fact of the **guarded** join; an **unknown** liveness is treated as alive, so the predicate can only fail **more** often and never passes where the baseline failed |
| `not worker.is_alive()` | 3 | `not recovery_alive`, `not dispatch_alive` and `not retry_alive` | 3 | the same mapping |
| `not tightener.is_alive()` | 1 | `not tightener_alive` | 1 | the same mapping |

The message of every moved predicate is **unchanged** and the **number** of
the assertions is unchanged: the correction never adds an oracle and never
removes one. The one occurrence of the baseline predicates that was **not**
moved is the **scenario** step of the subcase of the thread that never
started (`5998`), which the classification of the correction 21 already
listed.

The predicates that the correction 15 and the correction 16 removed are still
removed exactly as they were (`10` and `7` occurrences); the corrections 17,
18 and 20 removed none.
