# Correction 20 — static implementation of the seven residual counterexamples

**Coordinate** V1/R1/WP-R1-U3/S3_P4.
**Baseline** report delivery `7bf0c53822b396be3ea2091bdd6d3e18df0bf7b4`, source
candidate `c3286cce2cc4e4e8f4bb25fde60fa8f998e2fdce`.
**Independent review** `reports/v0-s3/product-gate0/native-custody-correction-19/
test-review-01/review-result` — `CHANGES_REQUIRED`, Fatal 0 / Major 2 / Minor 0,
M1 `CLOSED_STATIC`, M2 `OPEN`, M3 `OPEN`.
**Candidate** `tools/test_v0_s3_native_custody_correction10.py`,
Git commit `206a7fe7f21343d89ca83e03a0e4dc7e670cd381`,
SHA256 `662f6a2a0b1af5dd5b2baad737c2b6fc82edcab755beac49c67848f6fff6102a`.

**This delivery is STATIC. Nothing was executed.** No candidate import, no
collection, no pytest, no ctypes, no runtime, no native call, no OS business
process, no model, no GPU, no service, no network, no media, no database, no
ledger or counter action. The dynamic correction 20 is `NOT_RUN`, the native
behaviour is `NOT_PROVEN`, the historical 189 PASS of the correction 14 stays
historical. **No Major is closed by this delivery and no Stage, native or
product PASS is claimed.**

## What was repaired

One narrowly scoped static correction of **all seven** residual counterexamples
of the 19 review, in one file, with narrow local control flow. No new manager,
no new generic framework, no new product obligation, no new threshold and no
189th node.

| # | Counterexample | The repair | The static proof |
|---|---|---|---|
| M2-19-A | the coordination evidence DTO replaced the launch plan before the required schedules | the coordination evidence has its **own** binding `coord_document` and its own entry of the shared fact store; `document` is bound **once** and reaches the chain and the five schedules unchanged | `M2.1_original_plan_binding` — a **scope/dataflow** check, not a key/name presence check |
| M2-19-B | the bounded terminal recovery wrote from an unrelated fact store | one **shared** per-document LAST ACTUAL fact store; the **full intended** facts (barrier identity, `barrier_persisted`, `barrier_write_error`, `original_failure`, every cleanup/evidence diagnostic, the quiescence and the attempts of the drain) are stored **before** the terminal persistence; the recovery rewrites the ATTEMPTED name from those facts and **joins** the original error | `M2.2_shared_recovery_facts` |
| M2-19-C | the earlier final verdict ignored the original failure and its write error could disappear | the verdict is a **FAIL** when `early_original['type']` is not None; a failed evidence write updates the store and the error list and the evidence is **closed** after the cleanup with the priority of the cleanup; the coordination evidence is closed the same way | `M2.3_early_final_verdict` |
| M2-19-D | the failure inventory was local and not durable | a **durable final summary** (`r10-final-summary`) written once **after** every inventory action: the intended state of every name, the names that were not persisted, the incomplete names, the full facts, the original failure and **every** additional write error; it never replaces the original exception and the group never claims a durable failure log when its own write failed | `M2.4_durable_final_inventory` |
| M3-19-A | the seam write cancellation was converted into an ordinary assertion | the seam retains the **exact** object (`barrier_interruption`) and the phase raises **that object** instead of a synthesised `AssertionError`; the exact objects stay in memory and the documents show the type and the detail separately | `M3.1_interruption_priority` |
| M3-19-B | the current cancellation of the write won over the first pending one | the zero, parent and controlled evidence writers consult the pending list **first** and re-raise `interrupts[0]`; the priority is everywhere *unwinding original > first exact pending interruption > ordinary proof/evidence assertion* | `M3.1_interruption_priority` |
| M3-19-C | the initial gate releases were unguarded before the guarded drain | one helper `_release_gate(action, errors, interrupts)` releases **one** gate, retains the error and the **exact** object of a cancellation and never raises it in place; `_raise_first_interruption` re-raises the first pending exact interruption when nothing else is unwinding. **22** releases go through the helper and **no bare `.set()` remains in any `finally`** of the module | `M3.2_every_initial_gate_guarded` |
| M3-19-D | the observed fallback depended on the failing `entries()` query | an **independent** view of the exact started objects (`_OwnerRegistry.observed_threads` / `_observed_thread_refs`) that never calls `entries()`; the registry owners and the drain seed their owners from it, so a first enumeration failure still attempts the partial child and every known owner | `M3.3_independent_observed_fallback` |

The detailed mapping, with the baseline and the candidate line numbers, is in
`counterexample-mapping.md`. The preparation is in `preparation-checklist.md`
(40 lines, the limit is 80).

## What was preserved

* The M1-closed public driver of the zero round, its values, its order and its
  oracles; only the shared cleanup of that region changed.
* Every repair of the corrections 15–19 that the 19 review confirmed: the
  guarded terminal writes that leave `ATTEMPTED`, the non-quiescent proof that
  fails the round, the exact child/constructor driver, the coordination
  boundary that encloses the construction and the start, the per-endpoint
  `BaseException` loop of the parent, the durable barrier identity of the
  rewrite and the `NOT_RUN` ordering.
* The exact **189** identifiers, their order and their signatures: 117 + 16 +
  24 + 18 + 14, reconstructed as data and equal to the baseline.
* The assertion predicates: **414 → 414**, **0 removed**, no skip/xfail.
* The six other sources of the correction, byte identical (SHA256 pins in
  `pins.json`).
* The 28-name inventory of the group. The durable summary is a **group**
  artefact and not a 29th phase.
* The thresholds, the contracts, the root packets, the control documents, the
  manifest, the production code and the other tests.

## The evidence root of the module

`EVIDENCE_DIR` moves to the NEW directory of the correction 20, exactly as
the corrections 17, 18 and 19 did. The documents of the correction 19 stay
where they are: they are never overwritten, never deleted and never replaced
by a summary.

## The static checks

`static-checks/check_correction20.py` is a **static** instrument: it reads the
candidate and the frozen baseline as **data** (`ast`, `hashlib`, read-only
`git show`). It never imports the candidate, never collects it, never runs a
test, never opens a socket, a database, a model or a native library and never
starts a product process. Ten checks, ten passed, exit code `0`; the machine
readable result is `static-checks/static-checks-report.json` and the summary is
`static-checks/static-checks-summary.md`.

## The requested validation — REQUEST ONLY, NOT EXECUTED

`execution-request.md` asks the root for a separate, frozen and finite runtime
authorisation: three commands, one attempt each, **≤ 300 s** in total, the
189-node batch, the group of the counterexamples and the durable evidence of
the group. It must not be run before that ACK.

Stop rules: a `429` stops with `WAIT_BUDGET` and ends the turn — no retry, no
switch of route, no takeover of the root; an approval refusal or a timeout
stops the route without a bypass and without an edit of a configuration file;
any failure of a command is reported as it is.

## Honest limits

Static equality, AST counts and shape checks **cannot** replace execution.
They prove that the seven repairs have the required shape and that the
denominator did not regress; they prove **nothing** about the runtime
behaviour of the candidate, about the native API, about the product
acceptance or about the Stage gate. The actual raw results, the events, the
oracles, the negatives, the returned states and the bounded cleanup evidence
remain required after a separately frozen runtime ACK and an independent
review of the actual source.

## Delivered artefacts

| File | Content |
|---|---|
| `preparation-checklist.md` | the counterexample → control flow checklist (40 lines) |
| `counterexample-mapping.md` | the mapping of all seven counterexamples, with the baseline and the candidate line numbers |
| `pins.json` | the SHA256 pins of the six unchanged sources, of the changed module and of the delivered reports |
| `execution-request.md` | the finite three command validation plan, **REQUEST ONLY** |
| `static-checks/check_correction20.py` | the static instrument (no execution) |
| `static-checks/static-checks-report.json` | the machine readable result of the ten checks |
| `static-checks/static-checks-summary.md` | the human readable summary of the ten checks |
| `static-implementation-receipt.json` | the delivery receipt |
