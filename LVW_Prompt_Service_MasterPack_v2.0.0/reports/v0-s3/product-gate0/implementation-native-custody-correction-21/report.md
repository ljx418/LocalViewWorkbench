# Correction 21 — static implementation of the five residual counterexamples

**Coordinate** V1/R1/WP-R1-U3/S3_P4.
**Baseline** report delivery `845b78615f50141fd1c9029501a382b52efa9f44`, source
candidate `206a7fe7f21343d89ca83e03a0e4dc7e670cd381`.
**Independent review** `reports/v0-s3/product-gate0/native-custody-correction-20/
test-review-01/review-result` — `CHANGES_REQUIRED`, Fatal 0 / Major 2 / Minor 0,
M1 `CLOSED_STATIC`, M2 `OPEN`, M3 `OPEN`.
**Candidate** `tools/test_v0_s3_native_custody_correction10.py`, SHA256 in
`pins.json`.

**This delivery is STATIC. Nothing was executed.** No candidate import, no
collection, no pytest, no ctypes, no runtime, no native call, no OS business
process, no model, no GPU, no service, no network, no media, no database, no
ledger or counter action. The dynamic correction 21 is `NOT_RUN`, the native
behaviour is `NOT_PROVEN`, the historical 189 PASS of the correction 14 stays
historical. **No Major is closed by this delivery and no Stage, native or
product PASS is claimed.**

## What was repaired

One narrowly scoped static correction of **all five** residual counterexamples
of the 20 review **and of the same-root-cause call sites** that the review
cited, in one file, with narrow local control flow. No new manager, no new
generic framework, no new product obligation, no new threshold and no 189th
node.

| # | Counterexample | The repair | The static proof |
|---|---|---|---|
| M2.a | the final recovery still could not preserve all cleanup facts: the timeout, the published and the coordination documents exported only the attempts and the proof, so the second owner error and the final-resnapshot error never reached the durable evidence | the drain keeps the **per owner** errors of **every** iteration; one helper `_drain_facts` returns the **complete** bundle (final salvage, all salvage, owner errors, attempts, the complete error list, quiescence, proof) and **every** durable final document of a round unpacks it, next to the **actual** returned state of the public stop, the **original failure** and the writer diagnostics; the first proof string is never used as the error list | `M2.a_full_drain_facts` — a **dataflow** check on the real AST, not a key-presence check |
| M2.b | the incomplete-barrier terminal rewrite omitted `barrier_persisted` and `barrier_write_error`, and the exception handler skipped the name because the ledger had already closed it | the terminal document of the not-completed barrier carries the **actual** persistence, the **actual** write error and the **observed** snapshot of the barrier — even when they are absent — and the shared store keeps them before the write; the status stays `FAIL`/`executed` and the name is never relabelled `NOT_RUN` | `M2.b_incomplete_barrier_persistence` |
| M3.a | a late controlled cleanup release appended `K` **after** the durable snapshot and the interruption check and the function then returned | the outer `finally` restores the observer and the patch **unconditionally**, releases the gate **last**, then performs a **guarded final update** — the facts get the complete cleanup history and the evidence is closed with it — and only then the priority is applied: the unwinding original, then the **first** exact pending interruption, then the ordinary proof | `M3.a_no_late_controlled_release` — the real AST order of the `finally` |
| M3.b | the deferred cancellation was rethrown **inside** the startup-owner loop and a direct join or query could raise and skip the remaining owners | one helper `_join_owner` guards the join **and** the liveness query of one owner and records the failure with its exact type, its exact detail and the **exact** object of a cancellation; **every** owner is attempted, the priority is enforced **after** the whole traversal and the ordinary proof runs after it | `M3.b_every_owner_attempted` — a **real AST nesting** check: no raise and no priority call inside a loop over the owners |
| M3.c | the post-drain registry query could replace the original unwinding or the pending `K1`, because `registry.facts()` is the very query of the `entries()` that the drain fallback tolerates | one helper `_registry_snapshot` guards every query of the facts of a registry: the failure is retained with its exact type and detail, the **exact** object of a cancellation is retained, the snapshot of a failed query is **unknown** and it is an explicit diagnostic that **fails the proof** — never a fabricated empty registry | `M3.c_guarded_registry_queries` — the only call of `facts()` in the module is the one of the guarded helper |

The detailed mapping, with the baseline and the candidate line numbers, is in
`counterexample-mapping.md`. The preparation and the **call-site inventory of
the same root cause** are in `preparation-checklist.md` (58 lines, the limit is
80).

## The same-root-cause call-site inventory (audited once)

Ten cleanup regions of the module had a **direct** join, query or stop of an
owner that could raise and skip the action that follows it — the two that the
review cited (1506–1510, 4223–4228, 4305–4306) and eight more of the same
class (the creation, the launch, the retry, the startup owners, the
tightener, the interrupted start, the settle loop and the owner of the round
of R12). **All** of them now use the guarded join, the priority is enforced
after the traversal and the ordinary proof — the **exact** predicates of the
baseline — runs after the priority. The remaining joins of the module are
**scenario** steps of a `try` body: they skip no cleanup and no owner, and
they are classified as such in the checklist.

## What was preserved

* The M1-closed public driver of the zero round, its values, its order and its
  oracles; only the shared cleanup of that region changed.
* Every repair of the corrections 15–20 that the 20 review confirmed: the
  guarded terminal writes that leave `ATTEMPTED`, the non-quiescent proof that
  fails the round, the exact child/constructor driver, the coordination
  boundary that encloses the construction and the start, the per-endpoint
  `BaseException` loop of the parent, the durable barrier identity of the
  rewrite, the `NOT_RUN` ordering, the shared LAST ACTUAL store, the durable
  final summary and the independent observed fallback.
* The exact **189** identifiers, their order and their signatures: 117 + 16 +
  24 + 18 + 14, reconstructed as data and equal to the baseline.
* The assertion predicates: **414 → 414**, **0 removed**, **0 added**, no
  skip/xfail. The repaired control flow never touches an oracle.
* The six other sources of the correction, byte identical (SHA256 pins in
  `pins.json`).
* The 28-name inventory of the group. The bundle of the facts of a drain is a
  **key set of the existing documents** and not a 29th phase.
* The thresholds, the contracts, the root packets, the control documents, the
  manifest, the production code and the other tests.

## The evidence root of the module

`EVIDENCE_DIR` moves to the NEW directory of the correction 21, exactly as the
corrections 17, 18, 19 and 20 did. The documents of the correction 20 stay
where they are: they are never overwritten, never deleted and never replaced
by a summary.

## The static checks

`static-checks/check_correction21.py` is a **static** instrument: it reads the
candidate and the frozen baseline as **data** (`ast`, `hashlib`, read-only
`git show`). It never imports the candidate, never collects it, never runs a
test, never opens a socket, a database, a model or a native library and never
starts a product process. Ten checks, ten passed, exit code `0`; the machine
readable result is `static-checks/static-checks-report.json` and the summary is
`static-checks/static-checks-summary.md`. The checks of the denominator, of
the assertions and of the six unchanged sources are the checks of the
correction 20, kept unchanged.

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
They prove that the five repairs have the required shape and that the
denominator did not regress; they prove **nothing** about the runtime
behaviour of the candidate, about the native API, about the product
acceptance or about the Stage gate. The actual raw results, the events, the
oracles, the negatives, the returned states and the bounded cleanup evidence
remain required after a separately frozen runtime ACK and an independent
review of the actual source.

## Delivered artefacts

| File | Content |
|---|---|
| `preparation-checklist.md` | the counterexample → control flow checklist and the call-site inventory of the same root cause (58 lines) |
| `counterexample-mapping.md` | the mapping of all five counterexamples, with the baseline and the candidate line numbers |
| `pins.json` | the SHA256 pins of the six unchanged sources, of the changed module and of the delivered reports |
| `execution-request.md` | the finite three command validation plan, **REQUEST ONLY** |
| `static-checks/check_correction21.py` | the static instrument (no execution) |
| `static-checks/static-checks-report.json` | the machine readable result of the ten checks |
| `static-checks/static-checks-summary.md` | the human readable summary of the ten checks |
| `static-implementation-receipt.json` | the delivery receipt |

## Ten-field status

Current coordinate V1/R1/WP-R1-U3/S3_P4; this batch delivered the **static**
implementation of the five residual counterexamples of the independent
review of the correction 20; last passed gate
`UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`; current blocking gate the
static M2/M3 of the correction 20 plus the actual S3_P4 integration evidence;
global route V1 preparation; remaining work an independent static review of
this candidate, then a separately frozen and ACKed finite runtime execution
and the required product acceptance; next owner the coordinator; required
authorisation static only, no runtime requested or used; evidence this report
directory; exact stop `CHANGES_REQUIRED` F0/M2/m0 of the **20** review —
closed **statically** here, dynamic 21 `NOT_RUN`, native `NOT_PROVEN`.

## Complete V0–V3 development outline (completed/total)

V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; **current R1
0/4**; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. The
counts do not combine implementation, machine acceptance, independent review
and human acceptance: they come from the unique `plans/execution-control.json`
and from the real receipts.
