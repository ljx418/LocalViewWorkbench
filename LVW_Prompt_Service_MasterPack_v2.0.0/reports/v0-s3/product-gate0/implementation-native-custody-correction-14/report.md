# N1 correction 14 — implementation report (STATIC, not validated)

Coordinate: `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.
Baseline candidate `5ad9c159d2bc6960b4d847ac6bae7073edf86cd1` (the
product `b5e92af41ba6d27a0a2a52c5442de4f95df1a8e3`), the evidence of
the failed batch of the correction 13 (`184 PASS / 5 FAIL / 0 skip`,
cleanup proven, guard denials empty, counter absent before and after).
Scope: the three allowed test modules of
`native-custody-correction-14/scope.json` and the NEW
`implementation-native-custody-correction-14/` report root.

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
  the correction-14 `contract.md` / `scope.json` / `decision.json` /
  `implementation-prompt.md`, the **full** independent production review
  of the correction 13
  (`native-custody-correction-13/production-review-02/review-result/review.md`)
  and the **actual** failed evidence of the batch
  (`native-custody-correction-13/validation-outcome.md`, the receipt, the
  phase documents and the raw logs).
* It edited **only** the three allowed test modules
  (`tools/test_v0_s3_native_custody_correction05.py`,
  `..._correction07.py`, `..._correction10.py`) and it wrote **only**
  into the NEW `implementation-native-custody-correction-14/` root.  The
  two production modules, the parent regressions, the three other test
  modules and **every** historical report are byte identical to the
  baseline commit.
* It executed **no** candidate import, **no** collection, **no** pytest,
  **no** ctypes, **no** native call, **no** runtime or helper probe, **no**
  service, **no** GPU, **no** model, **no** network, **no** database, **no**
  media, **no** ledger and **no** counter access.  The only operations
  that touched the candidate were `ast.parse` of the source text, the
  extraction of the node ids with the AST, the extraction of the
  signatures with the AST and the SHA256 of the source text.
* It did **not** re-run the batch of the correction 13 and it did **not**
  replay any old batch.  The three commands of the trusted
  guard/runner/absence policy are **requested** for the newly sealed
  candidate only.

## 1. The five actual failures — the cause from the actual source

### 1.1 F1 — N05-R10: the table of the launcher converges one release later

**What really happened.**  The cross-product of the group (an ordinary
failure of the input, then the exact `KeyboardInterrupt` of the output)
closes the original HANDLE and the original raw streams on the recovery:
the report of the recovery is `released: [process, stdout]` and
`retained: [stdout]`.  The reconciliation of the registered originals
(`_LaunchAggregate.release`, `v0_s3_native_broker.py:7235-7249`) appends
the unresolved originals to the retained list **before** the retry of the
same release closes them (`7270`), so the report of that release names a
retained name that is **already closed** when the report is read.  The
table of the launcher keeps the name of the aggregate because of that
name (`_LauncherCustody.release`, `7490-7511`).

**The adjudication of the root** is exact and the current source agrees
with it: the independent review 02 traces this conservative residue and
its next-empty-release convergence; it does not resurrect a resource and
it does not repeat a close.  The previous report's phrase "never
converges" is not supported by the source.

**The correction.**  The group now proves the **empty bookkeeping owner**
(the aggregate has no process, no channel, no original raw stream, no
worker and no endpoint; every original file is really closed and the
close is **confirmed** by the progress record of the owner; the original
HANDLE is closed exactly once), records the intermediate table honestly
(`n05-<phase>-empty-owner.json`) and then permits **ONE** further
explicit release of the **same** owner under the **same** original
positive deadline.  That release converges the table to the empty state
and it performs **zero** close, terminate and wait: the six counters of
the process, of its HANDLE and of its two original files are compared
before and after it.  The table is never emptied by hand, the deadline is
never renewed, the loop is never repeated until the table is green and no
check of a retained resource is relaxed.

### 1.2 F2 — N07-R02: the millisecond boundary of the core never ran

**What really happened.**  The millisecond subcase of the group built
the **production** core with `run_root=None` and the production
constructor does `Path(run_root)`
(`v0_s3_native_broker.py:2348`): the constructor raised `TypeError` and
the boundary of the group never executed.

**The correction.**  The subcase drives the core with the **real**
controlled run root of the test.  The fixture parameter `tmp_path` is
added to the node and it does **not** change the identity of the node
(the node id is the file and the name of the function): the exact 189
identity and order are proved below.  The production is not changed, no
permissive `None` fallback is added to it and no assertion of the
boundary is skipped.

### 1.3 F3 — N10-R07: the round was driven in two clock domains

**What really happened.**  The group drove the parent of the round with
the clock of the session (a `ManualClock`), while the channel of the
round and its two endpoints are built by the **production** launcher and
keep the **default** clock of the host (`time.monotonic`,
`v0_s3_native_broker.py:5234` and `4510`).  A deadline of the round was
then compared with a clock of **another** domain: the absolute deadline
of the round (in the domain of the facade) was in the past for the clock
of the endpoint, so the admission of the read was refused
(`_admission_locked`, `4641`), the reader of the channel failed, the
channel was at the end of its stream and the pump of the parent **ended
before the recorder was installed**.  The phase document of the failed
batch recorded `queue_waits: []` and `reply_waits: []` — the two empty
lists are the proof that **no** admission of the parent was observed, not
that the parent did not wait.

**The correction.**  The channel of the round is built with the clock of
the round: the production class is used unchanged and only its
**supported** `clock` argument is bound.  The channel, its two
endpoints, their workers, the pump of the parent, the context of the
round and the aggregate of the launch then read every deadline of the
round in **ONE** domain.  The group then

* proves the **liveness** of the owner of the read: the next real read
  of the broker is **held** at a transparent seam and the group waits
  for that hold (a fact, not an assumption);
* publishes the **original** cleanup deadline of the round and only then
  releases the admission, so the admission that is observed is the one
  that **follows** the publication;
* records the **actual remaining** of the round at the admission
  (`session._context.effective_deadline() - clock()`) and asserts that
  the requested argument of the original queue method is that value (and
  not a nominal number);
* bounds the reply of the parent by the **published cleanup deadline of
  the original context** (the timeout of the call is now longer, so the
  two bounds are distinguishable) and asserts the same actual remaining;
* keeps the **zero expiry** as a second, distinct real owner schedule:
  the absolute deadline of the round is shortened, the queue wait is
  `0.0`, the reply wait is `0.0` and the pump of the round really ends.

Every gate of the test owner is released **unconditionally** in a
`finally`, the production is never changed to satisfy an inert fixture
and no counter ever fabricates an admission.

The round is really alive now, so the synthetic reader of the channel is
really inside its read when the round is closed: the cancellation of the
synthetic primitives releases that read, so the reader of the channel
really ends and **no thread of the round is left behind** after the
test.  The cleanup of the batch stays provable.

### 1.4 F4 — N10-R09: a thread that never started is not a thread to join

**What really happened.**  The group joined the thread of the startup
step **unconditionally**.  In the subcase that proves an interrupted
start, the seam raises **before** the original start of the thread, so
the thread really never came up and `threading.Thread.join` raised
`RuntimeError: cannot join thread before it is started`.  The production
owner already refuses to release an unproved start
(`_StartupOwner.settle`, `5886-5899`).

**The correction.**  The **facts** of the start decide: the start did not
return, the thread has **no identity** and it is not alive.  The fixture
skips **only** that impossible join and it asserts those facts
explicitly; an object without an identity is never read as a physical
exit of a thread.  The unconditional bounded join stays for every thread
that really started (the established start and the interrupted start of
the two phases above), and the causal negative of the group (an unproved
start is never released) is unchanged.  A new phase document
(`n10-r09-never-started.json`) distinguishes the **no-start object** from
the **active interrupted start**.

### 1.5 F5 — N10-R10: the failed coordination had no published fault

**What really happened.**  The cancel primitive of the round enqueued
the fault of the read and returned **immediately**.  The coordination of
the round could therefore reach its selection point
(`_WindowsPipeEndpoint._await`, `4763-4784`) **before** the worker had
published the immutable outcome of its generation
(`_WindowsPipeWorker._complete`, `4142-4179`): there was no
already-published fault at the selection point, the parallel fact of the
timeout could not be read and the phase of the failed coordination
stopped there.  The later observation of the fault does not prove
anything about the selection point.

**The correction.**  The seam of the **failed** coordination publishes
the real primitive fault and then waits, bounded, for the **immutable
outcome of that specific generation** before the cancel primitive
returns.  The worker of the round is held inside its own final close
and release tail, so the real bounded join of the coordination still
**FAILS** and the coordination error stays a **parallel** fact of the
original error of the round.  The outcome, the history of the error, the
selection of the error, the public stop of the round and the attributes
of the original error object are **not** patched, and the **confirmed**
coordination and the required order of the schedule stay separate and
unchanged.

## 2. The three schedules of M09 and the never-started join

| Schedule | Driver | Status in the failed batch of the correction 13 | Status after the correction |
|---|---|---|---|
| `r10-timeout-confirmed` (a **confirmed** coordination) | the real chain of the round | **REAL EVIDENCE** | unchanged |
| `r10-timeout-failed` (a **failed** coordination) | the real chain of the round | **NOT_RUN** (no published fault at the selection point) | the fault is published and the outcome of the specific generation really exists before the cancel primitive returns; the join still fails and the coordination error is a parallel fact |
| `r10-published-before-timeout` (the **required** order) | the transparent gate of the production wait of the worker | **NOT_RUN** (it follows the failed schedule) | unchanged |
| the never-started join of N10-R09 | the seam of the start of the thread | the node failed in the join of a thread that never started | the facts of the start decide; only the impossible join is skipped |

## 3. The static proofs of this delivery

### 3.1 The exact identity and the exact order of the 189 nodes

`node_identity.py` extracts the node ids of the five modules of the
batch with the **AST** (no collection, no import, no execution) in the
order of the definitions and compares them with the frozen list of the
plan of the root of the correction 13.

```
{"added": [], "derived_count": 189, "frozen_count": 189,
 "identical": true, "order_preserved": true, "removed": []}
```

No node was added, renamed, removed or moved, the denominator is 189 and
the order is binding.  The fixture parameter that F2 adds does not
change the identity of its node.

### 3.2 The static namespace and signature checks

`static_checks.py` parses the two production modules with the AST and
reads the names, the signatures and the attributes that the correction
relies on: **48 checks, 48 passed, 0 failed** (`static-checks.json`).
The check covers the launcher, the aggregate of a launch, the progress
record of the owner, the table of the launcher, the channel, the
endpoints, the workers, the broker process, the core, the session, the
pump, the reply waiter and the context of the round.

### 3.3 The production is unchanged

`source-pins.json` compares the bytes of the working tree with the bytes
of the baseline commit `5ad9c15`:

| File | SHA256 of the baseline | Identical |
|---|---|---|
| `tools/v0_s3_native_broker.py` | `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` | **yes** |
| `tools/v0_s3_native_custody.py` | `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581` | **yes** |
| `lvw/backend/app/native_runtime.py` | `16bf3e6396f9548312f92007eebbda55a448f0bdc6bab4a10afd71179b231a85` | **yes** |
| `tools/test_v0_s3_native_custody.py` | `fe96d2ffd353d3f3f6df4da2b023dd6cfaf58fe730ab6655afbca723ed507d32` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_regressions.py` | `03250ea0ac64519c57edfbe1be965eb2827b46fc7f2d80b47146e4a5e6e7cb93` | yes (unchanged) |
| `tools/test_v0_s3_native_custody_correction05.py` | `8563989f078fcd45d44c496a0bea16c1ecf5005513543f6f4e00792e4ed7e130` | **changed** (F1) |
| `tools/test_v0_s3_native_custody_correction07.py` | `dc74cf7f92e8be6cc2b69c602b9fc0b3fdd765ec8b9b48c4f061dde7bdcd6cdf` | **changed** (F2) |
| `tools/test_v0_s3_native_custody_correction10.py` | `e6ea479e74621f9092457078f6ac58b26757f43192177e6d23ac5ffef4c1a217` | **changed** (F3, F4, F5) |

The two production modules keep the digests of the independent review 02
of the correction 13, byte for byte.

## 4. What is delivered

| Deliverable | File |
|---|---|
| this report | `report.md` |
| the atom → production → event → oracle → negative → returned state → salvage matrix | `atom-matrix.md` |
| the changed assertions | `changed-assertions.md` |
| the wait and admission inventory | `wait-inventory.md` |
| the digests of the pinned files and the proof that the production is unchanged | `source-pins.json` |
| the identity and the order of the 189 nodes | `node-identity.json` (and `node_identity.py`) |
| the static namespace and signature checks | `static-checks.json` (and `static_checks.py`) |
| the static receipt of this implementation | `static-implementation-receipt.json` |
| the REQUEST of the finite batch | `validation-plan-request.json` |
| the runtime diagnostics of the group | `evidence/` and `f5-evidence/` |

The three commands of the request are the ones of the plan of the root
of the correction 13, with the **new** attempt directory of the
correction 14 and the **new** evidence directories: the counter absence
before, the guarded validation of the 189 nodes and the counter absence
after.  One batch of at most 300 s, no wrapper, no extra test, no rerun
and no replay of an old batch.

## 5. What is explicitly **not** claimed

* No Major is closed by this implementation.  The closure of the Majors
  belongs to the isolated independent review and to the gate owner.
* No Stage PASS, no final independent acceptance, no product gate and no
  native proof follows from this report.  `native_execution`,
  `native_cleanup`, `gpu_released`, `port_released`, `sampler`,
  `parent_crash_recovery` and `windows_stdin_eof` stay `NOT_PROVEN`.
* The dynamic coverage of the batch is `NOT_RUN`: this implementation did
  not import, collect or run the candidate.  The five failures of the
  correction 13 are **not** declared repaired by this report; the report
  states the cause in the source and the correction of the fixture.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`:
  nothing was reconstructed, refunded or reset and the counter was never
  read.
* The historical reports, the pinned evidence of the corrections 08 to
  13, the root packets, the execution control, the MANIFEST and the
  trusted guard/runner/absence tools were not touched.
* The pre-existing modification of `implementation-integration-01/report.md`
  was not touched by this implementation.

## 6. The stop report

1. **当前坐标**: `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`, the
   static correction 14 of the test-only package of the S3_P4.
2. **本批完成**: the static correction of the five actual failures of the
   batch of the correction 13 (F1 N05-R10, F2 N07-R02, F3 N10-R07, F4
   N10-R09, F5 N10-R10) with the cause in the actual source, the
   corrected fixtures, the exact 189 identity proof, the static
   namespace/signature checks and the proof that the production is
   unchanged.
3. **最后通过门禁**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`,
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b` (unified slice only); the
   S3_P4 batch of 189 nodes has **not** passed.
4. **当前阻塞门禁**: `S3_P4_N1_CORRECTION14_CONSOLIDATED189_VALIDATION` —
   the root has to pin the new candidate, to seal the guard/runner and
   to run the three commands once.
5. **全局路线位置**: the full remaining V1; the accepted V0-Min, R1a and
   the early unified slice stay scoped; the full R1/M1/R2 and the later
   V2/V3 remain pending.
6. **剩余工作**: the finite guarded batch of the 189 nodes, the
   independent review of the test delta, the native acceptance and the
   required human gates.
7. **下一责任人**: the root / the gate owner (pin the candidate, seal the
   runner, run the batch, review the evidence).
8. **所需授权**: none for the completed static work; no runtime
   permission is issued by this implementation.
9. **证据目录**: `reports/v0-s3/product-gate0/implementation-native-custody-correction-14/`
   (this report, the matrix, the assertions, the waits, the pins, the
   identity, the checks, the receipt and the request) and the NEW
   `evidence/` and `f5-evidence/` roots of the next batch.
10. **精确停止原因**: the static correction of the five actual failures
    is delivered, the production is unchanged, the batch was **not**
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
