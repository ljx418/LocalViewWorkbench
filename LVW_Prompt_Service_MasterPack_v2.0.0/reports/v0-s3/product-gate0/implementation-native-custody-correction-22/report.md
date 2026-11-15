# Correction 22 — static implementation of the six residual counterexamples

**Coordinate** V1/R1/WP-R1-U3/S3_P4.
**Baseline** report delivery `08e2096ed67a3c0a158dfa2239bdbc549b6fba12`, source
candidate `ed4afb50e3d6c12e8784d05dc40b9beb501a3668`.
**Independent review** `reports/v0-s3/product-gate0/native-custody-correction-21/
test-review-01/review-result` — `CHANGES_REQUIRED`, Fatal 0 / Major 2 / Minor 0,
M1 `CLOSED_STATIC`, M2 `OPEN`, M3 `OPEN`.
**Candidate** `tools/test_v0_s3_native_custody_correction10.py`, SHA256 in
`pins.json`.

**This delivery is STATIC. Nothing was executed.** No candidate import, no
collection, no pytest, no ctypes, no runtime, no native call, no OS business
process, no model, no GPU, no service, no network, no media, no database, no
ledger or counter action. The dynamic correction 22 is `NOT_RUN`, the dynamic
15–21 stay `NOT_RUN`, the native behaviour is `NOT_PROVEN` and the historical
189 PASS of the correction 14 stays historical. **No Major is closed by this
delivery and no Stage, native or product PASS is claimed.**

## What was repaired

One narrowly scoped static correction of **all six** residual counterexamples
of the 21 review **and of the same-root-cause call sites** that the review
cited and that the audit of this correction found, in one file, with narrow
local control flow. No new manager, no new generic framework, no new product
obligation, no new threshold and no 189th node.

The **central rule** of the correction is the order of the cleanup:

```
ALL the actions of the cleanup  ->  the COMPLETE facts and a durable
evidence attempt  ->  the priority of the failures: the original that is
unwinding > the FIRST exact pending interruption > the ordinary error
```

A deliberate failure that was already **caught** is **not** a failure that is
unwinding: it never exempts a **new** unexpected error of the cleanup from
failing the round.

| # | Counterexample | The repair | The static proof |
|---|---|---|---|
| M2.a | the **last** write of the controlled subcase can fail silently: the error is appended **after** the copied facts, the proof is not recomputed and the caller still passes | the outer `finally` of the subcase reads the state of the unwinding **first**, the facts are **complete** (every error and every interruption), the verdict is **recomputed** with them, the **last** write is attempted and the write error is an **actual** error that updates the facts **in memory** and rejects the success of the subcase | `M2.a_final_controlled_verdict` — a **real AST order** check of the `finally` |
| M2.b | the errors of the post-drain query of the registry of the zero round are only in the proof string and only while the proof is still `None`; the document has **no field** for them | the errors of the query are an **explicit durable field** of the document (`registry_errors`) and the verdict of the round is **recomputed** with them, so a query error survives next to a proof that already failed | `M2.b_zero_registry_durable` — a **real AST** check |
| M3.a | R12 raises the pending `K` and asserts the liveness **before** the public stop of the round: the stop is skipped and its ordinary exception is silently swallowed | the guarded join, **then** the **guarded** public stop with its exact type, its exact detail and its returned state, **then** the durable facts, **then** the priority — the original unwinding, the **first** exact `K`, the ordinary proof and the ordinary error of the cleanup | `M3.a_r12_all_actions_before_priority` — a **real AST order** check |
| M3.b | the close of the awaited endpoint is unguarded: it replaces the original failure or the **first** pending `K1` and it bypasses the priority | the close is guarded, its failure is retained as a secondary diagnostic, the **complete** facts are written before the priority and the priority is enforced **outside** the cleanup region | `M3.b_guarded_closes` — a **real AST** check of every direct close |
| M3.c | the errors of the guarded joins of the fixture are recorded locally and **nobody** reads them; the follow-up `is_alive` query is unguarded and can escape; the query of the owners in flight and the lookup of the thread of the owner are unguarded | **every** collected list has a consumer: the errors feed the verdict of the cleanup and they fail the round; the liveness of an owner is the fact of the **guarded** join; the queries of the cleanup are guarded and the priority is deferred **after** every action | `M3.c_error_list_consumers` — a **real AST dataflow** check — and `M3.c_deferred_priority` — a **real AST nesting** check |
| M3.d | a late ordinary error of the release, of the disarm or of the stop of the patch is appended **after** the proof was finalised; the `not raised` clause exempts the pending `K` when a deliberate failure was caught | the verdict of the subcase is recomputed with **every** actual error of the last actions and it is enforced before the return; the exemption is **gone** and the exact expected `CLOSE_FAILURE` singleton stays the only allowed injected fault | `M2.a_final_controlled_verdict` — the check of the absence of the exemption |

The detailed mapping, with the baseline and the candidate line numbers, is in
`counterexample-mapping.md`. The preparation and the **call-site inventory of
the same root cause** are in `preparation-checklist.md` (68 lines, the limit is
80).

## The same-root-cause call-site inventory (audited once)

Fifteen cleanup regions of the module had the same defect of the class: a
collected error list without a consumer, an unguarded follow-up query, a
direct close that can replace the failure that is unwinding, a priority that
is raised before the actions that follow it, or a cleanup action whose
ordinary failure is silently swallowed. **All** of them now retain their
errors, publish their facts and enforce their verdict after every action of
the cleanup; the list is the table of `preparation-checklist.md`. The joins
that remain in the module are **scenario** steps of a `try` body: they skip no
cleanup and no owner, and they are classified as such in the checklist.

## What was preserved

* The M1-closed public driver of the zero round, its values, its order and its
  oracles; only the shared cleanup of that region changed.
* Every repair of the corrections 15–20 that the 21 review confirmed: the
  guarded terminal writes that leave `ATTEMPTED`, the non-quiescent proof that
  fails the round, the exact child/constructor driver, the coordination
  boundary that encloses the construction and the start, the per-endpoint
  `BaseException` loop of the parent, the durable barrier identity of the
  rewrite, the `NOT_RUN` ordering, the shared LAST ACTUAL store, the durable
  final summary and the independent observed fallback.
* The exact **189** identifiers, their order and their signatures: 117 + 16 +
  24 + 18 + 14, reconstructed as data and equal to the baseline.
* The assertion predicates: **414 → 414**, **8 moved**, **0 added**,
  **0 removed**, no skip/xfail. Every moved predicate is the requery of the
  liveness of an owner and its replacement is the fact of the **guarded**
  join: an **unknown** liveness is treated as alive, so a moved predicate can
  only fail **more** often and never passes where the baseline failed. The
  messages of the moved predicates are **unchanged**.
* The six other sources of the correction, byte identical (SHA256 pins in
  `pins.json`).
* The 28-name inventory of the group. The facts of a cleanup are a **key set
  of the existing documents** and not a 29th phase.
* The thresholds, the contracts, the root packets, the control documents, the
  manifest, the production code and the other tests.

## The evidence root of the module

`EVIDENCE_DIR` moves to the NEW directory of the correction 22, exactly as the
corrections 17, 18, 19, 20 and 21 did. The documents of the correction 21 stay
where they are: they are never overwritten, never deleted and never replaced
by a summary.

## The static checks

`static-checks/check_correction22.py` is a **static** instrument: it reads the
candidate and the frozen baseline as **data** (`ast`, `hashlib`, read-only
`git show`). It never imports the candidate, never collects it, never runs a
test, never opens a socket, a database, a model or a native library and never
starts a product process. Ten checks, ten passed, exit code `0`; the machine
readable result is `static-checks/static-checks-report.json` and the summary is
`static-checks/static-checks-summary.md`. The checks of the denominator, of
the assertions and of the six unchanged sources are the checks of the
correction 21, kept unchanged.

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
They prove that the six repairs have the required shape and that the
denominator did not regress; they prove **nothing** about the runtime
behaviour of the candidate, about the native API, about the product
acceptance or about the Stage gate.

The correction also takes a **real** risk that only the dynamic run can
settle: a round now **fails** when the stop of the round, the close of an
endpoint or of a channel, the join of an owner or the write of the evidence
raises an ordinary error. The repeated stop of the round is exercised by the
body of the tests of R11, R12, R13 and R14 **before** the salvage stop of the
`finally`, so the repeated path of the production is already known to return;
a failure of the run is a failure of the candidate and it is reported as it
is, without a repair in this route.

The actual raw results, the events, the oracles, the negatives, the returned
states and the bounded cleanup evidence remain required after a separately
frozen runtime ACK and an independent review of the actual source.

## Delivered artefacts

| File | Content |
|---|---|
| `preparation-checklist.md` | the counterexample → control flow checklist and the call-site inventory of the same root cause (68 lines) |
| `counterexample-mapping.md` | the mapping of all six counterexamples and of the fifteen same-class regions, with the baseline and the candidate line numbers, and the equivalence of the moved assertions |
| `pins.json` | the SHA256 pins of the six unchanged sources, of the changed module and of the delivered reports |
| `execution-request.md` | the finite three command validation plan, **REQUEST ONLY** |
| `static-checks/check_correction22.py` | the static instrument (no execution) |
| `static-checks/static-checks-report.json` | the machine readable result of the ten checks |
| `static-checks/static-checks-summary.md` | the human readable summary of the ten checks |
| `static-implementation-receipt.json` | the delivery receipt |

## Ten-field status

Current coordinate V1/R1/WP-R1-U3/S3_P4; this batch delivered the **static**
implementation of the six residual counterexamples of the independent review
of the correction 21; last passed gate
`UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`; current blocking gate the
static M2/M3 of the correction 21 plus the actual S3_P4 integration evidence;
global route V1 preparation; remaining work an independent static review of
this candidate, then a separately frozen and ACKed finite runtime execution
and the required product acceptance; next owner the coordinator; required
authorisation static only, no runtime requested or used; evidence this report
directory; exact stop `CHANGES_REQUIRED` F0/M2/m0 of the **21** review —
closed **statically** here, dynamic 22 `NOT_RUN`, native `NOT_PROVEN`.

## Complete V0–V3 development outline (completed/total)

V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; **current R1
0/4**; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. The
counts do not combine implementation, machine acceptance, independent review
and human acceptance: they come from the unique `plans/execution-control.json`
and from the real receipts.
