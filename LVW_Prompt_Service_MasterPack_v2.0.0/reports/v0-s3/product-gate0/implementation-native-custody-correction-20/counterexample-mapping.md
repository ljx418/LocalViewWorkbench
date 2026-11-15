# Correction 20 — mapping of the seven residual counterexamples of the 19 review

Source of the counterexamples: the independent STATIC review of the
correction 19 (`reports/v0-s3/product-gate0/native-custody-correction-19/
test-review-01/review-result/review.md` and `receipt.json`, F0/M2/m0,
M1 `CLOSED_STATIC`, M2 `OPEN`, M3 `OPEN`).

Baseline: report delivery `7bf0c53822b396be3ea2091bdd6d3e18df0bf7b4`,
source candidate `c3286cce2cc4e4e8f4bb25fde60fa8f998e2fdce`.
Candidate of this correction: the single file
`tools/test_v0_s3_native_custody_correction10.py` plus this NEW report
directory.

The line numbers of the **baseline** are the ones of the review; the line
numbers of the **candidate** are the ones of this correction.

---

## M2-19-A — the launch plan was clobbered by the coordination evidence

* Baseline: `document = dict(r10_raw['r10-coordination'], …)` (7253–7268)
  replaced the sealed launch document of 6871–6872; the first
  `_m09_timeout_phase` (7314) handed that DTO to
  `NativeCustodySession.start` (5628–5645) and the production refused the
  key set before any read schedule.
* Candidate: the coordination evidence has its **own** binding
  `coord_document` (7656) and its own entry of the shared fact store
  (`r10_raw['r10-coordination']`). `document` is bound **exactly once**
  (7227, the launch plan) and it reaches the chain (7256) and the five
  schedules (7743, 7749, 7764, 7770, 7786) unchanged.
* Static proof: `static-checks/static-checks-report.json` →
  `M2.1_original_plan_binding`: `document_stores = [7227]`,
  `coord_document_stores = [7656]`, every schedule receives the name
  `document`.

## M2-19-B — the outer recovery wrote from the wrong fact store

* Baseline: the recovery (7368–7389) read `r10_raw` while the phase kept
  its snapshots, the barrier identity, the persistence facts and the
  errors in **local** `raw`/`api`/`write_errors`/`cleanup_errors`.
* Candidate: the two phase helpers take a `store` keyword and bind
  `raw = store if store is not None else {}`; the group passes
  `store=r10_raw` to all five schedules. The **full intended** facts of
  every document (the barrier identity, `barrier_persisted`,
  `barrier_write_error`, `original_failure`, `cleanup_errors`,
  `evidence_write_errors`, `proof_failure`, `quiescent` and the attempts
  of the drain) are written into the store **before** the terminal
  persistence is attempted. The recovery rebuilds the document from the
  store (`dict(r10_raw.get(r10_name, {}))`) and **joins** the detail of
  the original failure instead of replacing it; a failed write stays
  `ATTEMPTED` and the retry carries the full facts.
* Static proof: `M2.2_shared_recovery_facts`: the five calls carry
  `store='r10_raw'`, both phases bind `raw` to the store and the recovery
  document is `dict(r10_raw.get(r10_name, {}))`.

## M2-19-C — the earlier final verdict ignored the original failure

* Baseline: `early_failure` (7027–7036) was derived from the cleanup
  only, so `r10-early-salvage` could be `PASSED` and `ledger.pass_` could
  run after a real failure; the error of the evidence write was appended
  after the document was built and could disappear.
* Candidate: the verdict is a **FAIL** when `early_original['type']` is
  not None (the cleanup being clean never certifies a failed round); the
  intended facts are stored before the write; a failed write updates the
  store (`status='FAIL'`, `evidence_write_errors`, joined detail) and the
  error list and the evidence is **closed** after the cleanup with the
  priority of the cleanup (the pending exact interruption first, then the
  write failure, then the ordinary proof assertion). The coordination
  evidence is closed the same way (`coord_write_failure`).
* Static proof: `M2.3_early_final_verdict`.

## M2-19-D — the failure inventory was local and not durable

* Baseline: the write errors of the recovery and of the `NOT_RUN` writes
  only reached `first_failure` (7379–7386, 7414–7425) and the assertions
  after the `try` (7439–7450) are unreachable while the original unwinds.
* Candidate: the `finally` of the group writes a **durable final summary**
  once and **after** every action of the inventory
  (`r10-final-summary`, 7899): the intended state of every name
  (`states`), the names that were written (`written`), the names that were
  **not** persisted (`not_persisted`), the full facts of every document
  (`facts`), the original failure (`original_failure`) and **every**
  additional write error (`write_errors`). The summary never replaces the
  original exception; the failure of the summary itself is recorded as a
  persistence diagnostic, so the group never claims that the failure log
  is durable when its own write failed. A name is `NOT_RUN` only when it
  was never entered.
* Static proof: `M2.4_durable_final_inventory`: the summary carries the
  ten required keys and is written **after** the `NOT_RUN` write.

## M3-19-A / M3-19-B — the priority of the exact interruption

* Baseline: the seam write cancellation was reduced to a
  `BARRIER_DOCUMENT_NOT_WRITTEN` `AssertionError` (5732–5751) and that
  new assertion took the precedence over the exact `KeyboardInterrupt`;
  the zero (3609–3624), parent (3900–3922) and controlled (4533–4554)
  evidence writers did `if interrupted: raise` **before** the pending
  list, so a current cancellation `K2` won over an earlier `K1`.
* Candidate: the seam retains the **exact** object
  (`_M09TimeoutApi.barrier_interruption`) and the phase raises **that
  object** (`raise api.barrier_interruption`) instead of synthesising an
  assertion; the three evidence writers consult the pending list **first**
  and re-raise `interrupts[0]`. The priority is everywhere: the failure
  that is already unwinding, then the **first** exact pending interruption
  of the cleanup, then the ordinary proof/evidence assertion. The exact
  objects stay in memory; the documents show the type and the detail
  separately.
* Static proof: `M3.1_interruption_priority`: the three priority sites
  report `pending_at < bare_raise_at` and the phase raises
  `api.barrier_interruption`.

## M3-19-C — the initial gate releases were unguarded

* Baseline: the callers executed the same gates **unguarded** before the
  guarded drain: zero (3536–3537), parent (3842), controlled (4429–4430),
  timeout (5998), published (6542–6544) and coordination (7196). A
  cancellation of the first release skipped the whole cleanup and it
  replaced the original failure.
* Candidate: one helper `_release_gate(action, errors, interrupts)`
  releases **one** gate, retains the error and the **exact** object of a
  cancellation and never raises it in place; `_raise_first_interruption`
  re-raises the **first** pending exact interruption when no other failure
  is unwinding. All **22** cleanup releases of the module go through the
  helper, including the ones that the inspection found outside the six
  named sites (the admission gate, the paused queue of the dispatch, the
  two releases of the controlled region, the release of the reader of the
  launch, the gate of the creation, the gate of the await, the gate of the
  retry, the two gates of the startup owner, the tail of the interrupted
  start and the publication of the completion of the seam). No bare
  `.set()` remains in any `finally` of the module. A cancellation of one
  gate never skips the second gate, the closes, the stop, the joins, the
  proof and the evidence that follow it.
* Static proof: `M3.2_every_initial_gate_guarded`:
  `bare_releases_in_finally = []`, `guarded_releases = 22`.

## M3-19-D — the observed fallback depended on the failing query

* Baseline: `_registry_owners` (924–943) replaced the entries by `[]` on
  failure and derived `observed` from that **same** value; the drain kept
  its initial empty owner list on a first enumeration failure, so the
  partial child of the registry was never attempted.
* Candidate: `_OwnerRegistry.observed_threads()` is an **independent** view
  of the exact started objects and `_observed_thread_refs` reads it — or,
  if that view fails, the exact objects the registry holds — **without**
  ever calling `entries()`. `_registry_owners` reads it **before** the
  query of the entries and merges it after the traversal; `_drain_owners`
  seeds its owners with it and the final resnapshot falls back to it as
  well. A failure of one query never drops the partial child and never
  replaces the owners of the round with an empty list; the generation
  stability, the resnapshot, the producer joins and the single 30 s total
  bound are untouched and no deadline of the product is renewed.
* Static proof: `M3.3_independent_observed_fallback`:
  `helper_uses_entries = false`, `drain_seeds_owners = true`.

---

## What was deliberately **not** changed

* The public driver of the zero round, its values, its order and its
  oracles (the M1 closure of the 19 review) — only the shared cleanup of
  that region changed.
* The guarded terminal writes that leave `ATTEMPTED`, the non-quiescent
  proof that fails a round, the exact child/constructor driver, the
  coordination boundary that encloses the construction and the start, the
  per-endpoint `BaseException` loop of the parent, the durable barrier
  identity of the rewrite and the `NOT_RUN` ordering — all kept.
* The 189 identifiers, their order and their signatures; the assertion
  predicates of the baseline (0 removed, static multiset diff).
* The six other sources of the correction (SHA256 pins, byte identical).
* The 28-name inventory of the group; the durable summary is a group
  artefact and not a 29th phase.
* The thresholds, the contracts, the root packets, the control documents,
  the manifest, the production code and the other tests.

## Honest limits of this delivery

This is a **STATIC** correction. Nothing was executed: no candidate
import, no collection, no pytest, no ctypes, no native call, no product
process, no model, no GPU, no service, no network, no media, no database.
The static checks prove the **shape** of the seven repairs and the
**absence of a regression** in the denominator; they prove **nothing** about
the runtime behaviour. The dynamic correction 20 is `NOT_RUN`, the native
evidence is `NOT_PROVEN`, and the group stays `V1/R1/WP-R1-U3/S3_P4`.
This document grants no Major closure, no Stage PASS, no native PASS and
no product acceptance.
