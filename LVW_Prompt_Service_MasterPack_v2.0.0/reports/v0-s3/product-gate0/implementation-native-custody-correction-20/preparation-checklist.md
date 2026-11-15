# Correction 20 — preparation checklist (counterexample → control flow)

Static preparation only. No candidate import, no collection, no pytest, no
ctypes, no runtime, no native call, no OS business process, no model, no GPU,
no service, no network, no media, no DB, no ledger/counter side effect.
Scope: `tools/test_v0_s3_native_custody_correction10.py` only, plus this NEW
report directory. Baseline delivery `7bf0c53…`, baseline candidate `c3286cc…`.

| # | Counterexample (19 review) | Concrete defect in the baseline blob | Narrow local control flow of the correction | Files/lines touched |
|---|---|---|---|---|
| 1 | M2-19-A: the coordination evidence DTO replaced the launch plan before the required schedules | `document = dict(r10_raw['r10-coordination'], …)` in the same test function overwrote the sealed launch document; `_m09_timeout_phase` then handed that DTO to `NativeCustodySession.start`, which refuses the key set | Give the coordination evidence its **own** binding (`coord_document`) and keep `document` bound exactly once to the launch plan; the evidence DTO is stored in the shared fact store under its own name | T10 `test_n10_r10…`: the `coord_document` binding, the store write and the five schedule calls |
| 2 | M2-19-B: the outer recovery wrote from an unrelated fact store | the recovery read `r10_raw` while `_m09_timeout_phase` kept its raw/api/write-error/cleanup facts in **local** `raw` | One **shared** per-document LAST ACTUAL fact store (`store=` → `r10_raw`); the phase stores the *full intended* facts **before** the terminal persistence; the recovery rewrites the ATTEMPTED name from those facts and joins the detail instead of replacing it | T10 `_m09_timeout_phase`, `_m09_published_fault_phase`, the recovery loop of `test_n10_r10…` |
| 3 | M2-19-C: the earlier final verdict ignored the original failure and its write error could disappear | `early_failure` was derived from the cleanup only, so `r10-early-salvage` could be `PASSED` after a real failure; the write error was appended after the document was built | The verdict is a **FAIL** when `early_original['type']` is not None; the store keeps the intended facts before the write; a failed write updates the store and the error list and the evidence is **closed** after the cleanup with the priority of the cleanup; the coordination evidence is closed the same way | T10 the early block and the coordination block of `test_n10_r10…` |
| 4 | M2-19-D: the failure inventory was local and not durable | the write errors of the recovery and of the `NOT_RUN` writes only reached `first_failure`, and the assertions after the `try` are unreachable while the original unwinds | A **durable final summary** written once **after** every inventory action: intended state of every name, the names that were not persisted, the full facts, the original failure and every additional write error; the summary never replaces the original and its own failure is recorded as a persistence diagnostic | T10 the `finally` of `test_n10_r10…` |
| 5 | M3-19-A/B: a seam write cancellation became an ordinary assertion and the **current** cancellation won over the **first** pending one | the barrier branch synthesised an `AssertionError` over the exact `KeyboardInterrupt`; the zero/parent/controlled evidence writers did `if interrupted: raise` **before** the pending list | The seam retains the **exact** object (`barrier_interruption`) and the phase raises **that object**; the evidence writers consult the pending list **first** and re-raise `interrupts[0]` | T10 `_M09TimeoutApi._persist_barrier`, the barrier branch, the three evidence writers |
| 6 | M3-19-C: the initial gate releases were unguarded before the guarded drain | `zero_gate.set()`, `api.frames_ready.set()`, `gate.set()`, `api.release_the_worker.set()` and the coordination `gate.set()` ran unguarded at the head of a `finally`, so a cancellation skipped the whole cleanup | One helper `_release_gate(action, errors, interrupts)` releases **one** gate, retains the exact cancellation and never raises it in place; every cleanup release goes through it, the errors feed the proof of the round and the exact cancellation is re-raised with the priority of the cleanup. The same treatment is applied to the other cleanup releases of the module that the inspection found | T10 `_release_gate`, `_raise_first_interruption` and **22** call sites |
| 7 | M3-19-D: the observed fallback depended on the failing `entries()` query | `observed` was derived from the same `registry.entries()` value that was replaced by `[]` on failure | An **independent** view of the exact started objects (`_OwnerRegistry.observed_threads` / `_observed_thread_refs`) that never calls `entries()`; the registry owners and the drain seed their owners from it, so a first enumeration failure still attempts the partial child and every known owner | T10 `_OwnerRegistry`, `_registry_owners`, `_drain_owners` |

## Boundary rules that were held

* The M1-closed public driver, its values, its order and its oracles are
  untouched; only the shared cleanup of the zero round changed.
* The 189 identifiers, their order and their signatures are unchanged; no
  assertion predicate of the baseline was removed (static multiset diff).
* The six other sources of the correction are byte identical (SHA256 pins).
* The 28-name inventory of the group is unchanged; the durable summary is a
  **group** artefact and not a 29th phase.
* No new manager, no new framework, no new product obligation, no new
  threshold and no 189th node.
* The evidence root of the module moves to the NEW correction-20 directory;
  the documents of correction 19 stay where they are and are never
  overwritten, never deleted and never replaced by a summary.

## Repair log (kept from correction 19, not re-opened)

The guarded terminal writes that leave `ATTEMPTED`, the non-quiescent proof
that fails the round, the exact child/constructor driver, the coordination
boundary that encloses the construction and the start, the per-endpoint
`BaseException` loop of the parent and the durable barrier identity of the
rewrite are **kept**. This correction only repairs the seven residual paths.
