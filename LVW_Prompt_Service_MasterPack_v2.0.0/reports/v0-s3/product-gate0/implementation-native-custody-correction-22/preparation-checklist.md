# Correction 22 — preparation checklist (counterexample → control flow)

Static preparation only. No candidate import, no collection, no pytest, no
ctypes, no runtime, no native call, no OS business process, no model, no GPU,
no service, no network, no media, no DB, no ledger/counter side effect.
Scope: `tools/test_v0_s3_native_custody_correction10.py` only, plus this NEW
report directory. Baseline delivery `08e2096…`, baseline candidate `ed4afb5…`.

## The six residual counterexamples of the review of the correction 21

| # | Counterexample (21 review) | Concrete defect in the baseline blob | Narrow local control flow of the correction | Baseline → candidate lines |
|---|---|---|---|---|
| 1 | **M2.a** — the **last** write of the controlled subcase can fail silently: the error is appended **after** the copied facts, the proof is not recomputed and the caller still passes | `5062–5075` append the error of the write after `5065–5067` copied the facts; `5083–5085` only look at the interruptions with `not raised`; `5198` asserts `proof_failure is None` | the outer `finally` reads the state of the unwinding **first**; the facts are **complete** (every error and every interruption) and the verdict is **recomputed** with them; the **last** write is attempted; the write error is an **actual** error that updates the facts **in memory** and rejects the success | `5062–5086` → `5252–5329`, caller `5195–5205` → `5444–5454` |
| 2 | **M2.b** — the errors of the post-drain query of the registry of the zero round are only in the proof string and only when the proof is still `None`; the document has no field for them | `3912–3915` guard the proof with `zero_proof is None`; `3916–3926` has no `registry_errors` field | the errors of the query are an **explicit durable field** of the document (`registry_errors`) and the verdict is **recomputed** with them, so a query error survives next to a proof that already failed | `3909–3926` → `4079–4100` |
| 3 | **M3.a** — R12 rethrows the pending `K` and asserts the liveness **before** the public stop of the round; the stop is skipped and its ordinary exception is silently swallowed | `8598` raises the `K`, `8601–8603` asserts, `8604–8607` stops and swallows | the guarded join, **then** the guarded public stop (the exact type, the exact detail and the returned state are retained), **then** the durable facts, **then** the priority: the original unwinding, the **first** exact `K`, the ordinary proof and the ordinary error of the cleanup | `8594–8607` → `8976–9016` |
| 4 | **M3.b** — the close of the awaited endpoint is unguarded: it replaces the original failure or the **first** pending `K1` and it bypasses the priority | `4516` is a bare `endpoint.close()` and `4519` is the priority | the close is guarded, its failure is retained with its exact type and detail, the **complete** facts are written before the priority and the priority is enforced **outside** the cleanup region | `4507–4519` → `4700–4737` |
| 5 | **M3.c** — the errors of the guarded joins of the fixture are recorded locally and **nobody** reads them; the follow-up `is_alive` query is unguarded; the query of the owners in flight and the lookup of the thread of the owner are unguarded | `1622`, `1732`, `2103`, `4420`, `4512`, `5279`, `5425`, `5503`, `5591`, `5599`, `8606` | **every** collected list has a consumer: the errors feed the verdict of the cleanup and they fail the round; the liveness of an owner is the fact of the **guarded** join (an unknown liveness is never read as the end of an owner); the queries of the cleanup are guarded and the priority is deferred **after** every action | `1622`→`1695`, `1732`→`1823`, `2103`→`2217`, `4420`→`4594`, `4512`→`4707`, `5279`→`5523`, `5425`→`5688`, `5503`→`5783`, `5591`→`5888`, `5599`→`5913`, `8606`→`8989` |
| 6 | **M3.d** — a late ordinary error of the release, of the disarm or of the stop of the patch is appended **after** the proof was finalised; a caught deliberate failure exempts it through `not raised` | `5034–5067` append the late errors, `4968` already froze the proof, `5083–5085` skip the pending `K` when `raised` is not empty | the verdict of the subcase is recomputed with **every** actual error of the **last** actions and it is enforced before the return; a deliberate failure that was already **caught** is not an unwinding failure and it never exempts a new unexpected error; the expected `CLOSE_FAILURE` singleton stays the only allowed injected fault | `5034–5086` → `5252–5329` |

## The callsite inventory of the **same** root cause (audited once)

Every list of the errors of a cleanup of the module has a consumer, and every
owner action loop defers the priority **after** all its actions. The
inventory is the table of `counterexample-mapping.md`; the **new** consumers
are the `raise AssertionError('the cleanup of … met %s')` of the twelve
regions and the `registry_errors` field of the round of the zero expiry.

| # | Region (baseline → candidate) | Same-class repair |
|---|---|---|
| 1 | the recovery of the façade `1617` → `1695` | the liveness of the owner is the fact of the guarded join; the errors are durable and consumed |
| 2 | the creation of the child `1727` → `1823` | the facts of the join are durable; the errors are consumed |
| 3 | the reader of the launch `2094` → `2198` | the lookup of the thread is guarded; the priority is **outside** the `if`; the errors are consumed |
| 4 | the endpoints of the admission `3469` → `3637` | the errors of the release are consumed |
| 5 | the endpoints of the linearization `2816`/`2907`/`2936` → `2910`/`2948`/`2963` | the three direct closes are guarded; the priority and the ordinary error follow the last close |
| 6 | the worker of the dispatch `4404` → `4594` | the liveness is the fact of the guarded join; the facts are durable; the errors are consumed |
| 7 | the endpoint of the await `4507` → `4700` | the close is guarded; the facts are durable; the priority is outside |
| 8 | the controlled subcase `4849` → `5252` | the verdict is recomputed with the late errors; the `not raised` exemption is gone |
| 9 | the worker of the retry `5276` → `5523` | the liveness is the fact of the guarded join; the facts are durable; the errors are consumed |
| 10 | the owners of the startup `5404` → `5668` | every owner is attempted; the facts are durable; the liveness is the fact of the join; the errors are consumed |
| 11 | the tightener of the deadline `5503` → `5783` | the liveness is the fact of the guarded join; the facts are durable; the errors are consumed |
| 12 | the interrupted start `5585` → `5886` | the query of the owners and the lookup of the thread are guarded; the priority is **outside** the `if`; the errors are consumed |
| 13 | the round of R12 `8592` → `8976` | the stop is attempted before the priority; the facts are durable; the errors are consumed |
| 14 | the rounds of R11, R13 and R14 `8430`/`8665`/`8697`/`8763` → `8770`/`9079`/`9122`/`9205` | the four salvage stops are guarded and never **silently pass** an ordinary exception; the errors are consumed |
| 15 | the channels of R11 `8450`/`8472` → `8805`/`8838` | the two direct closes are guarded; the errors are consumed |

**Inspected and classified, not repaired** (they are **scenario** steps of a
`try` body: they skip no cleanup and no owner): the `creator.join` of the
scenario at `1813`, the `reader_thread.join` of the scenario at `2161`, the
`reader.join` of the scenario at `4688`, the `owner.settle` and the
`thread.join` of the never-started subcase at `5986`/`5998` and the join of
the coordination of the barrier at `6241`.  The joins of the helpers
(`_join_owner`, `_salvage_threads`) are the **guarded** ones by construction.

## Boundary rules that were held

* The M1-closed public driver, its values, its order and its oracles are
  untouched; only the shared cleanup of the regions changed.
* The 189 identifiers, their order and their signatures are unchanged; the
  assertion predicates are **414 → 414** with **8 moved** and **0 added** and
  **0 removed**.
* The six other sources of the correction are byte identical (SHA256 pins).
* The 28-name inventory of the group is unchanged: the facts of a cleanup
  are a **key set of the existing documents** and not a 29th phase.
* No new manager, no new framework, no new product obligation, no new
  threshold and no 189th node.
* The evidence root of the module moves to the NEW correction-22 directory;
  the documents of correction 21 stay where they are and are never
  overwritten, never deleted and never replaced by a summary.
