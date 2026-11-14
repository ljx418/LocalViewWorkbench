# N1 correction 15 — implementation report (STATIC, not validated)

Coordinate: `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.
Baseline evidence commit `8a6ed7462a69bfa7e29d4d143c2d6fed289a1912`, the
product candidate `63b490ae8b5678113fc13ed16fb2a8a54e5ca39c`.  The
**actual** batch of the correction 14 was `189 PASS / 0 FAIL / 0 SKIP`
(187 functional), `cleanup true`, guard runtime `[]`, counter absent
before and after.  That batch is **not** accepted: the independent
static test/evidence-design review of the correction 14
(`native-custody-correction-14/test-review-01/review-result/`) returned
`F0 / M3 / m0` with the disposition `CHANGES_REQUIRED`.

Scope: the **one** allowed test module
`tools/test_v0_s3_native_custody_correction10.py` and the NEW
`reports/v0-s3/product-gate0/implementation-native-custody-correction-15/`
report root.

**This report signs no Major and no Stage.**  It reports what the source
now does and what the frozen nodes now assert.  The batch of 189 nodes
has **not** been executed by this implementation: the root pins the
candidate, runs the three commands of the plan request and reviews the
result.  Dynamic evidence is `NOT_RUN`, native behaviour stays
`NOT_PROVEN` and the historical counter continuity stays
`UNAVAILABLE_NOT_PROVEN`.

## 0. What the implementation did and did not do

* It read the root pack `AGENTS.md`, `.agent-governance/README.md`,
  `.agent-governance/stage-gates.md`, `.agent-governance/anti-false-green.md`,
  `docs/24_EXECUTION_MASTER_PLAN.md`, `plans/execution-control.json`,
  the correction-15 `contract.md` / `scope.json` / `decision.json` /
  `implementation-prompt.md`, the **full** independent test/evidence-design
  review of the correction 14 (`review-result/review.md`,
  `review-result/receipt.json`, `source-binding.json` and the exact
  source bindings of the five blobs) and the actual facts of the batch
  of the correction 14 (189 PASS / cleanup true).
* It edited **only** the one allowed test module
  (`tools/test_v0_s3_native_custody_correction10.py`) and it wrote
  **only** into the NEW `implementation-native-custody-correction-15/`
  root.  The two production modules, the native runtime, the other four
  test modules and **every** historical report are byte identical to the
  baseline commit (`source-pins.json`).
* It executed **no** candidate import, **no** collection, **no** pytest,
  **no** ctypes, **no** native call, **no** runtime or helper probe, **no**
  service, **no** GPU, **no** model, **no** network, **no** database, **no**
  media, **no** ledger and **no** counter access.  The only operations
  that touched the candidate were `ast.parse` of the source text, the
  `symtable` scope check, the in-memory `compile` of the source text, the
  extraction of the node ids with the AST, the extraction of the
  signatures with the AST and the SHA256 of the source text.
* It did **not** re-run the batch of the correction 14 and it did **not**
  replay any old batch.  The three commands of the trusted
  guard/runner/absence policy are **requested** for the newly sealed
  candidate only.

## 1. The three Majors — the cause in the actual test/evidence design

### 1.1 M1 — F3 N10-R07: the zero expiry was proved on an unstarted helper

**What the review found.**  The zero expiry was observed on a **fresh**,
**unstarted** and **unattached** `custody_module._ChannelPump` that the
group built itself and called directly, after the pump of the round had
already ended.  Its empty pending/error/EOF state reaches
`Event.wait(0)` in `_ChannelPump.take` (`887-928`), so the recorder
could report zero without any public session request and without any
admission of an **attached** pump.  The same context identity does not
establish the missing public entry wiring.

**The correction.**  The acceptance oracle of the zero expiry is now a
**public** chain: a **second, separately bounded** round that is really
started through the production `NativeCustodySession.start` and the
production default launcher (`_default_launcher`, `2454-2470`), with the
ORIGINAL context of **that** round, its own lease (`120 s`) and **one**
clock domain.  The group observes the **attached** pump of that round
(`session._pump` - the pump that the production really started and
really owns):

* the round is really started (the READY and the STATUS really arrive
  through the real chain);
* the **attached** pump reaches its next admission and the admission is
  **held** at a transparent gate (the gate calls the original read of
  the broker and it decides only the schedule);
* the **zero expiry** is published on the ORIGINAL context **before** the
  next current bound of the round is calculated;
* the reply of the parent is really waited for and it asks for
  **nothing** (the recorded argument of the event of the reply is
  `0.0`) - the pump is still held at the gate, so its end of stream and
  its error can never preempt the reply that the round owes;
* the admission is released and the **attached** pump really performs its
  next read: the recorded argument of the original queue method is
  `0.0`.

The **direct** helper of the group stays as a **supplement** (the four
original assertions of the zero expiry of the original round are
unchanged) and it is never the oracle.  No permissive production
fallback was added, no admission is inferred from the identity of a
context or from `owner is None`, and no assertion of the group is
skipped.

### 1.2 M2 — F5 N10-R10: the publication barrier could pass without the outcome

**What the review found.**  `_wait_for_outcome` returns `None` at its
bounded expiry.  The cancel seam of the failed coordination stored that
`None` and still returned `REQUESTED`; the later
`published_before_cancel_return` boolean was written and never asserted.
A reachable interleaving could therefore make every final oracle pass
without the required publication-before-cancel-return premise.

**The correction.**  The wait of the seam is now a **checked** barrier
that **fails closed**.  Before the cancel primitive returns, the barrier
demands

* the immutable outcome of the **exact** generation (never a generic
  event of the worker and never a hard coded number),
* the expected kind of the ordinary failure (`RuntimeError`),
* the **exact** original error object (`outcome['error_object'] is
  fault`),

and it stores the **checked monotonic order** (`entered <= observed <=
left`), the generation and the object.  A missing outcome
(`BARRIER_OUTCOME_MISSING`), an outcome of another generation
(`BARRIER_GENERATION_MISMATCH`), another kind of the failure
(`BARRIER_ERROR_KIND`) and another error object (`BARRIER_ERROR_OBJECT`)
are an **explicit refusal** of the premise of the test: the seam raises
and the cancel primitive **never** returns `REQUESTED` as if the barrier
had passed.

Because the production `request_cancel` catches the ordinary exceptions
of the seam, an exception that the production swallowed is **not** a test
oracle: the outer test reads the premise from the **record of the
barrier**, captures it **before** the main assertions of the phase and
asserts both the premise-success record and the **absence** of a barrier
failure.  Two **negative** subcases drive the **same** failed
coordination with a bounded transparent seam that forces an **absent**
outcome (`r10-barrier-absent`) and an outcome of **another generation**
(`r10-barrier-wrong-generation`); their premise is **refused** and they
are never counted as a successful failed coordination.

The outcome, the history of the error, the selection of the error, the
public stop of the round and the attributes of the original error object
are **not** patched.  The **confirmed** coordination and the required
order of the schedule (`r10-published-before-timeout`) stay separate and
unchanged, together with the exact original object, the two real
`Session.stop` calls, the `UNKNOWN` state and the history checks of the
reader.  A phase that was **not** executed is marked `NOT_RUN` and never
carries a fabricated fact.

### 1.3 M3 — F3 N10-R07: the started owners had no unconditional cleanup

**What the review found.**  The `StreamChannel` constructor of the child
starts its real drain thread and its endpoints can start real worker
threads.  The only `transport.close()` was after all the child
assertions on the success path, and the enclosing `finally` stopped only
the parent session with an **expired** product bound, so the return of
the stop was ignored and its exceptions were swallowed.  A successful
batch cannot prove the cleanup of the negative path.

**The correction.**

* every owner that a round really starts is registered **immediately**:
  the background threads of the session (`_background_threads`), the
  closer threads (`_closer_threads`), the drain thread of the channel
  (`_thread`) and the workers of its two endpoints, and the drain thread
  of the transport of the child with the workers of its endpoints;
* the close of the transport of the child runs in an **inner** `finally`
  and it runs also when an assertion of the group failed; a **partial**
  construction closes the two endpoints that it really built;
* the primitive of the round is released in the `finally` as well;
* the **salvage** of the test owner joins every owner that **really**
  started with an explicitly bounded wait (10 s) and asserts its
  liveness.  An owner **without an identity** is reported as
  `started: False` and is **never** joined - no exit is inferred from an
  object that never ran;
* the salvage is **separate** from the returned state of the product:
  the stop of the product keeps its own deadline and its own returned
  state, the salvage renews no deadline of the round, erases no
  retained resource of the product and never claims that the product
  released it;
* two **controlled assertion failure** subcases inside the existing node
  id fail **on purpose** at an established checkpoint of a real round -
  after the admission of the parent (`PARENT_ADMISSION`) and after the
  start of the transport of the child (`CHILD_TRANSPORT`).  They raise
  and catch only the distinctive sentinel `_R07Sentinel` (never a broad
  `Exception`), and they assert that the `finally` released every gate
  of the test and that every owner that really started is **gone**.  A
  receipt of the happy path cannot substitute this negative-path proof.

## 2. The schedules and the node identity

| Item | Status |
|---|---|
| the 189 node ids and their order | **identical** to the frozen list of the plan of the root (`node-identity.json`: `identical: true`, `order_preserved: true`, `added: []`, `removed: []`) |
| the node that M1 and M3 change | `tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer` |
| the node that M2 changes | `tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation` |
| the three schedules of M09 | `r10-timeout-confirmed`, `r10-timeout-failed` and `r10-published-before-timeout` stay **three distinct schedules**; the two negative subcases of the barrier are **additional** subcases of the same node |
| the positive remaining scenario of N10-R07 | **unchanged** (the actual remaining at the admission and the published cleanup deadline) |
| the zero expiry of the original round | **unchanged** and kept as the **supplement** of the public chain |
| skipped, xfailed, removed assertions, shrunk denominator | **none** |

## 3. The static proofs of this delivery

### 3.1 The exact identity and the exact order of the 189 nodes

`node_identity.py` extracts the node ids of the five modules of the
batch with the **AST** (no collection, no import, no execution) in the
order of the definitions and compares them with the frozen list of the
plan of the root.

```
{"added": [], "derived_count": 189, "frozen_count": 189,
 "identical": true, "order_preserved": true, "removed": []}
```

No node was added, renamed, removed or moved, the denominator is 189
and the order is binding.

### 3.2 The static namespace and signature checks

`static_checks.py` parses the two production modules with the AST and
reads the names, the signatures and the attributes that the correction
relies on: **62 checks, 62 passed, 0 failed** (`static-checks.json`).
The checks of the correction 14 are kept and the owners of the three
Majors are added: the **attached** pump of a round and its context, the
**outcome** of a generation of a worker, the **request_cancel** of the
worker, the **close** of a channel and of its endpoints, the **registry**
of the started owners of a session and the **remaining** of a round.

### 3.3 The production is unchanged

`source-pins.json` compares the bytes of the working tree with the bytes
of the baseline commit `8a6ed74`:

| File | SHA256 of the baseline | Identical |
|---|---|---|
| `tools/v0_s3_native_broker.py` | `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` | **yes** |
| `tools/v0_s3_native_custody.py` | `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581` | **yes** |
| `lvw/backend/app/native_runtime.py` | `16bf3e6396f9548312f92007eebbda55a448f0bdc6bab4a10afd71179b231a85` | **yes** |
| `tools/test_v0_s3_native_custody.py` | `fe96d2ffd353d3f3f6df4da2b023dd6cfaf58fe730ab6655afbca723ed507d32` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_regressions.py` | `03250ea0ac64519c57edfbe1be965eb2827b46fc7f2d80b47146e4a5e6e7cb93` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_correction05.py` | `8563989f078fcd45d44c496a0bea16c1ecf5005513543f6f4e00792e4ed7e130` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_correction07.py` | `dc74cf7f92e8be6cc2b69c602b9fc0b3fdd765ec8b9b48c4f061dde7bdcd6cdf` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_correction10.py` | `e6ea479e74621f9092457078f6ac58b26757f43192177e6d23ac5ffef4c1a217` | **changed** (M1, M2, M3) |

The two production modules keep the digests of the independent production
review of the correction 13, byte for byte.  The changed file is the
**only** file of the package that differs from the baseline.

## 4. What is delivered

| Deliverable | File |
|---|---|
| this report | `report.md` |
| the Major → production → event → oracle → negative → returned state → salvage matrix | `atom-matrix.md` |
| the changed assertions | `changed-assertions.md` |
| the wait and admission inventory | `wait-inventory.md` |
| the digests of the pinned files and the proof that the production is unchanged | `source-pins.json` |
| the identity and the order of the 189 nodes | `node-identity.json` (and `node_identity.py`) |
| the static namespace and signature checks | `static-checks.json` (and `static_checks.py`) |
| the static receipt of this implementation | `static-implementation-receipt.json` |
| the REQUEST of the finite batch | `validation-plan-request.json` |
| the runtime diagnostics of the group | `evidence/` and `f5-evidence/` (written by the next batch) |

The three commands of the request are the ones of the plan of the root,
with the **new** attempt directory of the correction 15 and the **new**
evidence directories: the counter absence before, the guarded validation
of the 189 nodes and the counter absence after.  One batch of at most
300 s, no wrapper, no extra test, no rerun and no replay of an old
batch.

## 5. What is explicitly **not** claimed

* No Major is closed by this implementation.  The closure of the three
  Majors belongs to the isolated independent review and to the gate
  owner; the implementation delivers the **static** correction and the
  evidence design that the review can read.
* No Stage PASS, no final independent acceptance, no product gate and no
  native proof follows from this report.  `native_execution`,
  `native_cleanup`, `gpu_released`, `port_released`, `sampler`,
  `parent_crash_recovery` and `windows_stdin_eof` stay `NOT_PROVEN`.
* The dynamic coverage of the batch is `NOT_RUN`: this implementation did
  not import, collect or run the candidate.  The three Majors are **not**
  declared closed by this report; the report states the cause in the test
  and the correction of the fixture.
* The historical 189 PASS of the correction 14 stays a **historical**
  machine fact of that batch; it is not a fact about this candidate.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`:
  nothing was reconstructed, refunded or reset and the counter was never
  read.
* The historical reports, the pinned evidence of the corrections 08 to
  14, the root packets, the execution control, the MANIFEST and the
  trusted guard/runner/absence tools were not touched.
* The pre-existing modification of `implementation-integration-01/report.md`
  was not touched by this implementation.

## 6. The stop report

1. **当前坐标**: `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`,
   the static correction 15 of the test-only package of the S3_P4.
2. **本批完成**: the static correction of the three test/evidence-design
   Majors of the independent review of the correction 14 (M1 N10-R07 the
   public zero expiry of an **attached** pump, M2 N10-R10 the **checked**
   and **fail closed** barrier of the publication with two negative
   subcases, M3 N10-R07 the **unconditional** bounded cleanup of the
   started owners with two controlled assertion-failure subcases) with the
   cause in the actual test, the corrected fixtures, the exact 189
   identity proof, the static namespace/signature checks and the proof
   that the production is unchanged.
3. **最后通过门禁**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`,
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b` (unified slice only); the
   S3_P4 batch of 189 nodes has **not** passed for this candidate.
4. **当前阻塞门禁**: `S3_P4_N1_CORRECTION15_CONSOLIDATED189_VALIDATION` —
   the root has to pin the new candidate, to seal the guard/runner and
   to run the three commands once.
5. **全局路线位置**: the full remaining V1; the accepted V0-Min, R1a and
   the early unified slice stay scoped; the full R1/M1/R2 and the later
   V2/V3 remain pending.
6. **剩余工作**: the finite guarded batch of the 189 nodes, the
   independent review of the test delta, the native acceptance and the
   required human gates.
7. **下一责任人**: the root / the gate owner (pin the candidate, seal
   the runner, run the batch, review the evidence).
8. **所需授权**: none for the completed static work; no runtime
   permission is issued by this implementation.
9. **证据目录**: `reports/v0-s3/product-gate0/implementation-native-custody-correction-15/`
   (this report, the matrix, the assertions, the waits, the pins, the
   identity, the checks, the receipt and the request) and the NEW
   `evidence/` and `f5-evidence/` roots of the next batch.
10. **精确停止原因**: the static correction of the three Majors is
    delivered, the production is unchanged, the batch was **not**
    executed here (dynamic `NOT_RUN`, native `NOT_PROVEN`); no Major, no
    Stage PASS and no native PASS is claimed.

### The development outline (from `plans/execution-control.json`)

| Stage | Delivery | Done | Implementation | Machine | Independent | Human |
|---|---|---|---|---|---|---|
| V0-S0 | V0 | 1/2 | ARCHIVED | NO_GO_HISTORICAL | COMPLETED_WITH_BLOCKERS | NOT_SIGNED |
| V0-S1 | V0-Min | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| R0 | V1前置 | 1/2 | PARTIAL_REUSED | SINGLE_IMAGE_SUBSET_ONLY | NO_SEPARATE_R0_VERDICT | NO_SEPARATE_R0_SIGNOFF |
| R1a | V1早期切片 | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| V0-S2 | V0.1 | 7/8 | IMPLEMENTED | COMPLETE_FIXED9_PASSED | COMPLETE_FATAL0_MAJOR0_MINOR0 | PENDING |
| V0-S3 | V0.2 | 0/6 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R1 | V1 | 0/4 | EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING | EARLY_SLICE_UM10_ONLY | EARLY_SLICE_FATAL0_MAJOR0 | EARLY_SLICE_APPROVED_FULL_R1_PENDING |
| V1-M1 | V1 | 0/3 | DESIGN_ONLY | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R2 | V1 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R3 | V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R4 | V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5a | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5b | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5c | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
