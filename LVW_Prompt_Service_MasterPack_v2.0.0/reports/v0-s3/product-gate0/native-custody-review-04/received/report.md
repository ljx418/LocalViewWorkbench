# N1 correction 04 — implementation receipt — READY_FOR_REVIEW

Candidate: `d751bced75cdc1d21cee072892860a7c4f8ac542` (static correction 04 of the N1 native
custody; it binds every byte of the three N1 sources below). The candidate is the last commit
that touches a source of the package; the tree that it names is
`5a75eefd399c7df0fa135370db453cb4936818f4`.
Failed candidate that is corrected: `895bfb9cd76c3f5ad714f52a11ed98f8a670fa86`.
Failed evidence commit that is kept: `2c7121dcf412914f5ca7d4f5eb481d712f67d217`.
Root frozen package: `reports/v0-s3/product-gate0/native-custody-correction-04/contract.md` and
`decision.json` (`CHANGES_REQUIRED_STATIC_CORRECTION04_AUTHORIZED`, 133 calls / 130 pass / 3 fail /
0 skip / `cleanup_proven=false` / 2 retained heartbeat threads / `test_execution_authorized=false`).
The 16 frozen obligation groups of the correction 03
(`native-custody-correction-03/regression-obligations.json`, sha256
`8ca7f2ecdec3cf4cb09e66035e80331b42f23280ec8a1bd0c9f100554f73b405`) are unchanged and are not
rewritten by the implementer.

`contract_changes=none` — no public API, schema, quality threshold, denominator, frozen packet,
control, MANIFEST, old report, old log, old evidence, old broker byte, guard or runner was
modified. The only changed files are the three files that the frozen package allows.

## 1. What the failed batch proved and what it did not prove

The second batch of the correction 03 collected 133 nodes, passed 130, failed 3 and kept two
`lvw-native-custody-heartbeat` threads at the end of the batch. The three failures share one
mechanism: `NativeCustodySession._close_broker()` marked the close as *attempted* **before** it
ran, so a second caller returned at once instead of waiting for the close that was in flight.

The root analysis names a second, independent defect that is visible statically: `_start_heartbeat`
**rebuilt** the stop event of the heartbeat, so a heartbeat could start after the close of the
round had already finished. That is the mechanism that produces a heartbeat that nobody stops.

**This receipt does not claim that the two retained heartbeat threads of the failed batch had one
single cause.** The correction closes both mechanisms that are named by the root; the residual
thread count of the next batch is the fact that decides it, and this receipt does not pre-write
that result.

## 2. The correction

### A — the coordination of the close of the round

| requirement of the frozen package | what the candidate does |
|---|---|
| one cleanup owner, one original absolute cleanup deadline | the first caller of `_close_broker` claims the ownership and the deadline is generated once (`_cleanup_deadline_for` caches it and no layer renews it) |
| explicit NOT_STARTED / IN_PROGRESS / FINISHED | `_close_state` with `CLOSE_STATES`; FINISHED means that the *attempt* ended and never that the resources were released |
| a competitor never assumes that IN_PROGRESS is finished | the competitor waits on `_close_done` inside `_await_close`; it never returns early |
| the wait is bounded by the same absolute deadline | `_await_close` recomputes `deadline - clock()` in slices of 50 ms and never regenerates the 5 s budget |
| on expiry: named UNKNOWN, original owner kept | `CUSTODY_CLOSE_NOT_FINISHED`, `state = UNKNOWN_RETAINED`, `self.broker` and the references of the pump, the heartbeat and the closer are kept |
| the event is published in a finally on every path | the owner calls `_finish_close()` in a `finally`: success, ordinary exception, KI and SystemExit all wake the waiters |
| no owner lock held while waiting | the waiter increments `_close_waiters` under the lock and releases it before it waits |
| the owner never waits for itself | `_close_broker` and `_await_close` both refuse the wait when the caller is the owner |
| no cycle between a callback and the closer | the callbacks of the pump and of the heartbeat never wait for the close; the close runs in its own thread and it never joins the thread that runs it |
| the steps of the close are independent | `_perform_close` catches a failure of `_stop_background` and still closes the original handle of the broker |
| a successful close is not closed twice | only the owner closes; a repeated close returns at `FINISHED` |
| the close that failed keeps the original resources | the facts of the close decide; an incomplete fact keeps `self.broker` |
| a thread that could not start leaves nothing stuck | `_start_background_thread` unregisters a thread whose `start()` raised; `_start_bounded_close` names `CUSTODY_CLOSER_START_FAILED` and leaves the close available for the next owner |
| the evidence reflects IN_PROGRESS/UNKNOWN and the real reader/pump/heartbeat/closer | `close_state`, `close_finished`, `close_waiters`, `closer_alive`, `pump_alive`, `heartbeat_alive`, `background_open` |

### B — the race of the background start

| requirement of the frozen package | what the candidate does |
|---|---|
| the stop event of the heartbeat is never rebuilt | the event is created **once** in the constructor of the session and `_start_heartbeat` never replaces it |
| no background thread starts after the close began | `_background_open` is closed under `_background_cv` **before** the snapshot of the threads is taken; a thread that is started after that point is refused (`CUSTODY_BACKGROUND_START_REFUSED`) |
| the registration, the permission and the snapshot have a provable order | `_start_background_thread` registers the thread and counts it as *starting* under the lock before it starts it; `_stop_background` waits for the count to reach zero before it takes the snapshot |
| a startup that races the close is coordinated | the refusal of the start turns the start into a named failure; the close that is in flight is awaited and the original broker is closed by it |
| a late READY/STATUS never turns UNKNOWN into RUNNING | `_apply_state` refuses to overwrite `UNKNOWN_RETAINED` and names `CUSTODY_LATE_STATE_IGNORED` |
| the stop blocks the heartbeat that would follow it | `_stop_background` sets `_stopping` and the stop event of the heartbeat before it joins anything |

### C — the failure of the reader reaches the owner of the round

The start of the round builds the pump, starts it and starts the heartbeat before it reads the
first reply. The reader of the channel may fail in that window and the close that the failure
starts may stop the reader before the owner of the round reads the first reply. The owner of the
round then saw a closed channel instead of the failure that the reader really saw, and a
cancellation of the reader could be lost.

The reader now keeps its failure with the round (`_pump_error`), the own code of that failure
stays visible in the failures of the round (`_on_pump_error` records it) and the owner of the
round raises the cancellation of the reader when the reader is already gone. The start of the
round does not raise on the refusal of a background thread either: it continues to the exchange
of the start and the failure that leaves it is the failure of the reader of the channel. This
keeps the frozen assertions of the correction 03 true in **every** order of the two threads.

### D — the checks

The 133 ordered node ids are **byte for byte the node ids of the frozen plan of the second batch**
(verified by extracting the test functions of the two modules in file order and comparing the two
lists: `133 == 133`, identical order). No node was added, removed, renamed or reordered; no
assertion was weakened.

The new deterministic scenarios live **inside the existing frozen groups** R06, R11, R14 and R16,
so the denominator of 133 does not change and the root does not have to freeze new node ids:

| group | new scenario | what it proves |
|---|---|---|
| R06 | a concurrent closer waits for the close that is in flight | the competitor is inside the wait of the product (`_close_waiter_arrived`), it did not return before the close could finish and the broker was closed exactly once |
| R06 | the shared deadline of the cleanup arrived | `CUSTODY_CLOSE_NOT_FINISHED`, the state is UNKNOWN, the original broker stays with its owner and the deadline is not regenerated |
| R06 | a close that fails still wakes the waiters | the waiter is woken by a close that raised, the original broker is kept and `close_state` is FINISHED |
| R06 | a pump that fails before the heartbeat is built | the heartbeat is refused, no `lvw-native-custody-heartbeat` thread is left behind and the broker is closed exactly once |
| R06 | the close never joins the thread that runs it | the product refuses the self join; the thread that could not be joined keeps its reference and the round stays unknown |
| R11 | the callback and the closer never wait for each other | after a background failure the pump and the heartbeat are joined and dead and the closer finished |
| R14 | a repeated stop closes nothing a second time | the original broker keeps its owner and `broker_retained` stays true |
| R16 | the fact of the product and the salvage of the test | the state that the product returned with is stated, and the salvage of the test owner happens after it |

Every new wait is an **explicit event** (`threading.Event`, `threading.Barrier`-free ordering by
events), never a sleep and never a poll of a count of closes. The poll that the R11 group used
(`for _ in range(50): if peer.closed: break; time.sleep(0.02)`) is removed and replaced by the
`closed_event` of the peer.

The two checks of the existing module that failed in the batch
(`test_the_session_closes_the_broker_on_a_cancellation`,
`test_the_session_closes_the_broker_on_a_parse_error`) now also state that the close of the round
is `FINISHED` when the product returned. Their assertions are strengthened and never weakened.

## 3. The static checks of this candidate

No import of the candidate, no collection and no pytest were run for this candidate: the frozen
package allows the static implementation only until the ACK of the root.

| check | result |
|---|---|
| `ast.parse` of the three N1 sources | OK |
| an instance attribute of a class that shadows a method of the same class | none |
| a subclass of `threading.Thread` that shadows an internal of `threading.Thread` | none |
| every private member of the session that the two check modules use exists in the production class | OK (77 members) |
| the ordered node ids of the two modules against the frozen list of 133 | identical, 133 == 133 |
| the production broker | unchanged, sha256 `627e829d6f4862f4dc098a0b83d6ff9d26a28813e6eb4b11e921593d86f54b36` |

## 4. The bytes of this candidate

| File | sha256 |
|---|---|
| `tools/v0_s3_native_custody.py` | `fee267aed425bcb5c96dcc77609766d01ca1c6ef66f173157de8249502468c39` |
| `tools/test_v0_s3_native_custody.py` | `348aa4ba2775de54a102cd19237642572a1eba118a4bd6aeea0b8b84f38ba4b7` |
| `tools/test_v0_s3_native_custody_regressions.py` | `eb4decc7c773628f6ce5995345f9f2c7998e21d7f7d9acd8fdec5623d6595947` |
| `tools/v0_s3_native_broker.py` (unchanged) | `627e829d6f4862f4dc098a0b83d6ff9d26a28813e6eb4b11e921593d86f54b36` |

## 5. The execution plan that is asked for

The full plan is `execution-plan.request.json` of this directory. It is **derived from** the frozen
plan of the second batch (`native-custody-correction-03/validation-plan-02/plan.json`) and it
inherits its dependency pins, its stdlib pins, its external guard, its counter policy, its
integrity-only nodes and its ordered node ids without a change.

| item | value |
|---|---|
| candidate SHA | `ebe41cb795d2e80c5fa8afe75f659ff4a9e331e6` |
| node ids | the 133 ordered node ids of the frozen plan, unchanged |
| dependency pins | 223 file level pins of the frozen plan, unchanged |
| stdlib pins | 3 pins (`/usr/bin/python3.12`, `ctypes/__init__.py`, `_ctypes…so`), unchanged |
| stdlib preload | exactly one `ctypes.dlopen` with `name=null` in one finite window after the guard and before any candidate or pytest import, closed afterwards and never reopened |
| external guard | the guard, the runner and the outer counter reader of the root, byte identical to `native-custody-correction-03/validation-plan-02/`; the root freezes the new `plan.json` beside them in `native-custody-correction-04/validation-plan-01/` |
| commands | three: `counter-before`, `guarded-validation`, `counter-after`; the absolute argv and the cwd are in the JSON |
| batches | one |
| budget | at most 300 s for the batch |
| output | only the NEW directory `implementation-native-custody-correction-04/attempt01/` |
| counter | read once before and once after by the outer runner, read only outside the guarded batch, expected sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`; not written, not refunded, not reset, not created, not revived |
| real execution | none: no process, no socket, no database, no original ledger, no media, no network, no download, no real Windows API, no job object, no service, no GPU, no model |
| FD identity and thread cleanup | the runner of the root records the dev/inode/mode of every FD before and after and the names of the threads before and after; the batch is only clean when `threads_after == ['MainThread']` and no FD was created, reused or lost |
| failure | every failure is kept; there is no automatic rerun, no other node and no other route; a failed batch is reported as a failed batch and the candidate is not overwritten |

**The batch is not executed until the root freezes this plan and acknowledges it.** A FIRST 429
stops the batch as `WAIT_BUDGET` without a retry, without another route and without the root taking
it over; a FIRST refusal or a timeout of the approval stops the batch without a wrapper and
without a bypass.

### The batch that ran under the ACK of the root

The root froze the plan as
`native-custody-correction-04/validation-plan-01/plan.json` (sha256
`2aead0638c050840e4e8c3b81011b0403dc8c0b67e24e6d3f2346c13918048cb`) and acknowledged it with
`ACK_ONE_FROZEN_133_NODE_OFFLINE_BATCH`. The plan is **the same plan** as the request above: the
same 223 dependency pins, the same three stdlib pins, the same external guard bytes, the same
counter policy and the same 133 ordered node ids.

The batch ran **once**, in the three commands of the plan, in their order, with their absolute
argv and cwd unchanged. The result and the raw evidence are in `attempt01/` and the full account
is in `attempt01/execution-report.md`:

| item | value |
|---|---|
| collected / pass / fail / skip | **133 / 133 / 0 / 0** |
| pytest exit | **0** |
| `cleanup_proven_for_batch` | **true** |
| threads before → after | `['MainThread']` → `['MainThread']` (the two heartbeat threads of the failed batch are gone) |
| FD identity before → after | 3 → 3, dev/inode/mode identical, `new_or_reused_fds=[]`, `unknown=[]` |
| stdlib preload | exactly one `ctypes.dlopen` with `name=null`, window closed before the candidate, final state CLOSED |
| guard | eight selftest denials, **zero** runtime denials |
| counter | byte identical before and after (`acbdb8b1…23b98`), read once before and once after, outside the guarded batch |
| budget | about 15 s of the 300 s of the plan |
| real execution | none |
| the three failed nodes of the failed batch | all **passed** |

**The receipt of the batch is named `native-custody-correction-03.receipt.json`** because the
root's runner inherited that name; the file is written **only** into the NEW directory
`attempt01/` and the receipt of the failed batch, which lives in another directory, was not read,
not copied and not overwritten. The raw stdout and stderr of this batch are kept under the same
inherited basename and are byte identical to `guarded-validation.stdout.log` and
`guarded-validation.stderr.log`.

**133 green does not close the independent review.** The five items that the root named in
`review-notes.md` — the uniqueness and the immutability of the cleanup deadline in the concurrent
paths, the reachability of the recovery of a retained resource by its same owner, the owner that
survives a background start that never returns or that raises and a cleanup that expires, the
difference between the publication of `close_done` and the real exit of the closer thread, the
atomicity of the UNKNOWN latch against a late `_apply_state` and the completeness of the coverage
of the startup before / during / after interleavings — stay open and are recomputed by the
isolated review.

## 6. Complete V0–V3 outline (unchanged coordinate)

| Delivery | Stage | Completed / declared | Boundary |
|---|---|---:|---|
| V0 | V0-S0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-Min | V0-S1 | 5/5 | 已签仅V0-Min |
| V1前置 | R0 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| V1早期切片 | R1a | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0.1 | V0-S2 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0.2 | V0-S3 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V1 | R1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1 | V1-M1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| V1 | R2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R4 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5a | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5b | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5c | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

Copied unchanged from `plans/execution-control.json` `development_outline`. **No completion count
was advanced.** V0-S3 stays 0/6: this is an offline parent-side custody correction only.

## 7. Ten required fields

1. **当前坐标**: R1 / WP-R1-U3 / `S3_P4_OFFLINE_INTEGRATION_PREPARATION`; this batch is the static
   correction 04 of the N1 native custody under the frozen package
   `native-custody-correction-04/contract.md`; the current blocking gate is
   `S3_P4_N1_CLOSE_COORDINATION_AND_BACKGROUND_START_RACE`.
2. **本批完成**: the static correction 04 of the close coordination and of the background start
   race, the deterministic scenarios inside R06/R11/R14/R16, the frozen execution plan request and
   the **one** frozen batch that the ACK of the root authorised: 133 collected / 133 passed /
   0 failed / 0 skipped, pytest exit 0, `cleanup_proven_for_batch=true`, threads
   `['MainThread']` → `['MainThread']`, FD identity identical, counter byte identical.
3. **最后通过门禁**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b`; the N1 subtree now has a **passing** batch of its
   own — 133/133 at candidate `d751bced75cdc1d21cee072892860a7c4f8ac542` — and that batch is a
   machine fact of the subtree, **not** a closed gate: the gate of the N1 custody stays open
   until the isolated review of the eight Majors.
4. **当前阻塞门禁**: the isolated review of the eight open Majors of the N1 review, with the five
   items that the root named in `review-notes.md`; N2, I24, the product 12, Windows, the quality
   set, the balance and the human signature stay open.
5. **全局路线位置**: the parent side custody of one native round is an offline foundation of the
   S3 offline closure; the native execution, the GPU release, the port release, the sampler, the
   parent crash recovery and the Windows stdin EOF semantics stay `NOT_PROVEN`.
6. **剩余工作**: the isolated review that recomputes the five named items, the decision on the
   eight Majors and the unchanged later gates.
7. **下一责任人**: the root (the gate decision) and the isolated review instance (the five named
   items); no further implementation work is pending for this correction.
8. **所需授权**: none for this scope; the batch ran under the ACK of the root
   (`ACK_ONE_FROZEN_133_NODE_OFFLINE_BATCH`) and no human authorization was required.
9. **证据目录**: `reports/v0-s3/product-gate0/implementation-native-custody-correction-04/`
   (this receipt, `execution-plan.request.json`, `SHA256SUMS`) and `attempt01/` of the same
   directory (the receipt of the batch, named `native-custody-correction-03.receipt.json` because
   the root's runner inherited that name, the raw stdout and stderr, the guard record, the two
   counter observations, `commands.json` and `execution-report.md`); no other directory was
   written.
10. **精确停止原因**: the one authorised batch ran once, its exit code was 0, its raw evidence is
    sealed in the NEW directory and nothing was rerun, repaired or overwritten; the receipt
    claims `READY_FOR_REVIEW` and **not** Stage PASS.

## 8. What this receipt does not claim

The native execution, the native cleanup, the GPU release, the port release, the sampler, the
parent crash recovery and the Windows stdin EOF semantics stay `NOT_PROVEN`. `grant_authority =
NOT_VERIFIED` and `admission_produced = false`. The eight open Majors of the N1 review are not
closed by this receipt; the independent review instance decides on them. This receipt is
`READY_FOR_REVIEW` and it is **not** a Stage PASS.
