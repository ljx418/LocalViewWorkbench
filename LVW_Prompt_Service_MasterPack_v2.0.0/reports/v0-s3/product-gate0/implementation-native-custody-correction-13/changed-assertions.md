# N1 correction13 — the changed assertions

Coordinate `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.  Every
change below is **inside an existing node id**: no node was added, renamed,
removed or moved and the frozen list of 189 node ids and its order are
unchanged (`node-identity.json`).

The column "kind" says whether the change is a **strengthening** (the
obligation is asserted harder), a **premise repair** (the group did not
establish the obligation before it asserted it) or an **isolation** (the group
read the resources of another check of the batch).

## 1. N05-R14 — `tools/test_v0_s3_native_custody_correction05.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | premise repair | the reader of the group returned `b'one\n'` on its first read and `b'two\n'` after a single `released` flag was set; the end of the file was returned when the flag was already set | the reader publishes `first_entered` **before** it waits for the first frame and `second_entered` before it waits for the second one; the frames are delivered one after the other | the channel starts its reader inside its constructor: the first frame was put **before** the group installed its recorder, so only one put was ever observed (`assert 1 >= 2`) |
| 2 | premise repair | the recorder was installed after the construction of the channel | the group waits for `first_entered`, installs the recorder and only then releases the first frame | the instrumentation must exist before the first frame exists, otherwise the first put is invisible |
| 3 | strengthening | the second frame was released through the single `released` flag | the second frame is released **after** the bound of the round was tightened and after `second_entered` was observed | the second frame is delivered exactly once and after the tightening; the assertion of the cropped timeout is now about a frame that really exists |
| 4 | strengthening | none | `assert len(puts) >= 2` (unchanged in strength), `assert puts[0] == pytest.approx(0.5)`, `assert min(puts) <= 0.02 + 1e-9`, `assert max(puts) <= 0.5 + 1e-9` | the values that are asserted are the values that the production requested; nothing is fabricated and the assertion is **not** shrunk to one put |
| 5 | teardown | `channel._reader.released.set(); channel.close()` | both frames are released, the reader thread is joined with a bounded wait (10 s) and the thread is proven to be gone, then the channel is closed | the teardown of the owner of the test is unconditional and bounded |

## 2. N07-R13 — `tools/test_v0_s3_native_custody_correction07.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | isolation | `assert not [item for item in _launcher_custody_items() if item['kind'] == 'aggregate']` — the **whole** table of the launcher | the group takes a baseline of the identities of the aggregates before its own launch and asserts that **its own** owner is gone after the bounded recovery | the table is shared by the whole batch and a launch that another check retained was read as the resources of this one |
| 2 | strengthening | none | `assert len(own) == 1`, `assert owner.process is None`, `assert owner.channel is None`, `assert owner.raw_streams == []` | a launch that was refused before its process kept **only** an empty bookkeeping owner; the group proves that it kept no process, no channel and no raw stream of its own |
| 3 | strengthening (new subcase) | none | the group drives a **public stop** of a real session while the hash of the executable is really in flight and asserts: the hash ran exactly once, the channel was never built (`owner.channel is None`), the admitted process kept its owner (`owner.process is not None`), the process is in the table of the launcher, and the bounded recovery releases it and converges the owner | M08-E: the next distinct effect of the launch must be refused and the admitted operating system work must stay reachable and recoverable |
| 4 | isolation | the table of the launcher kept the context of the round that the check above stopped | the table is bound to a **current** context of the round after the subcase | the published cleanup deadline of the round that was stopped must not refuse the recovery of a later check of the batch |

## 3. N10-R04 — `tools/test_v0_s3_native_custody_correction10.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | premise repair | the interruption of the start was injected **immediately** after the reader thread started | the worker of the read publishes `worker_inside` **before** it waits inside the primitive and the group waits for that event **before** it injects the interruption | a start that returned does not prove that a read primitive is still active: the close of the channel publishes its cancel flag **before** it joins the reader, so the reader that had not reached its read was refused and the channel was released **correctly** |
| 2 | strengthening | none | the group asserts that the partial channel is retained (`aggregate.channel is channel`), that the channel is coordinated **before** the process (`order == ['channel-write', 'terminate', 'wait']`), that the read end is never closed under the live worker (`read_file.closes == 0`), that the files of the process are never closed by the helper (`process.closed == []`), that the process is terminated and waited exactly once and that the **same** owner recovers the channel after the explicit release of the read | the obligation of the node is the ownership of the partial channel; the premise now establishes that a read primitive really is active |

## 4. N10-R05 — `tools/test_v0_s3_native_custody_correction10.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | isolation | the phase used the table of the launcher of the package, whose bound context was the one that another check of the batch published | the phase runs on a **scoped** production table (`unittest.mock.patch.object(broker_module, '_LAUNCHER_CUSTODY', scoped)` with a real `_LauncherCustody`) | the bound of another round refused the retry of the raw stream **before** it started: the close was never attempted and the `KeyboardInterrupt` of the original stream never fired (`DID NOT RAISE`) |
| 2 | unchanged in strength | `with pytest.raises(KeyboardInterrupt): release_retained_launches()` | the **same** assertion | the cancellation may never be read as a swallowed one and the assertion is not weakened |
| 3 | strengthening | none | the group asserts that the retried stream was really attempted twice (`stdout.attempts == 2`), that it was not confirmed (`stdout.confirmed == 0`), that the owner of the original survived the cancelled retry and that the launch still owns it | the exact error path through the helper, the aggregate and the custody is now observable |
| 4 | strengthening (new) | none | the fault seam of the test is released (`stdout.cancel = False`) and the **same** owner recovers: the stream is really closed (`stdout.confirmed == 1`, `stdout.closed is True`), the owner of it is released and the table of the launcher converges | the final same-owner recovery after the release of the fault seam |

## 5. N10-R09 — `tools/test_v0_s3_native_custody_correction10.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | premise repair | `def recording_get(timeout=None)` | `def recording_get(block=True, timeout=None)`; the arguments are forwarded to the original and the **non blocking observation** is recorded apart from the **bounded positive waits** | the owner observes its result with `get_nowait()`, which calls `self.get(block=False)`: the recorder raised `TypeError: recording_get() got an unexpected keyword argument 'block'` |
| 2 | strengthening | the wait of the owner was only observed against the poll cap | the schedule tightens the deadline of the round **between** two waits and the group proves that the next wait received the time that was really left (`min(requested[1:]) <= 0.01 + 1e-9`) | the obligation is the crop to the **current** effective deadline; the strengthening drives it |
| 3 | strengthening | none | `assert observed` (the observation is not a wait) and `assert requested` (the bounded waits exist) | the two are different facts and the group tells them apart |
| 4 | teardown | none | the thread that tightens the deadline is joined with a bounded wait and it is proven to be gone | the teardown of the owner of the test is unconditional and bounded |

## 6. N10-R10 — `tools/test_v0_s3_native_custody_correction10.py`

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | premise repair | the group waited for `worker.outcome_published` and then read `lvw_parallel_timeout` of the original error object | the group waits for the **real** termination of the reader thread of the channel (a bounded join of a real thread) before it reads the attached fact | the publication of the outcome happens in the worker; the **attachment** of the parallel timeout happens in the endpoint when it raises the original error object.  Waiting on the publication is not a consumption barrier |
| 2 | unchanged in strength | `assert isinstance(parallel, dict)` and the two coordination subcases | the **same** assertions | the three schedules stay distinct inside the same node id and the later phases are `NOT_RUN` when an earlier assertion fails |

## 7. N07-R02 — `tools/test_v0_s3_native_custody_correction07.py` (new subcase, M08-C.2)

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | strengthening | none | the group drives the **production** adapter of the façade (`WindowsApi._wait_timeout_ms` + `_confirm_process_exit`) with the four exact remainders — exactly 0, below one millisecond, exactly one millisecond and just above one millisecond — and asserts the requested value (`0`, `0`, `1`, `1`), that the exit is **never** inferred and that the primitive is **not** called at all when the requested value is zero (`recorded == [1, 1]`) | M08-C.2: the millisecond adapters floor their value and never round it up |
| 2 | strengthening | none | the same four remainders are driven through the **production** adapter of the core (`BrokerCore._wait_timeout_ms` + `_wait_one_process`) with the recorded argument of `wait_process` and with the assertion that the exit of the process is never inferred from a requested zero | the same obligation on the second production adapter |

## 8. N03-R08 — `tools/test_v0_s3_native_custody_regressions.py` (new subcase, M08-C.1)

| # | Kind | Before | After | Why |
|---|---|---|---|---|
| 1 | strengthening | the read of the transport was only observed against the cached lease of the loop | the group publishes a cleanup deadline of the round that is **shorter** than the poll cap and proves that the requested argument of the transport is cropped to it (`<= 0.05` and `< 0.25`) | M08-C.1: the next read is cropped by the **current** minimum of the original context and not only by the cached lease |
| 2 | strengthening | none | the group lets the bound of the round arrive and proves that the loop asks for **nothing** at all and that it ends with `LEASE_EXPIRED` (the lease of the round and not a failure of the channel) | the expired bound ends the round with the lease and it never opens a new positive wait |

## 9. The production owners that changed

| Owner | The change |
|---|---|
| `v0_s3_native_broker.py:_LaunchProgress` (new) | the monotonic progress record of the original resources of one launch |
| `v0_s3_native_broker.py:_LaunchAggregate` | the record, the bound with its clock, the owned streams, the facts that are read from the record |
| `v0_s3_native_broker.py:_release_launch_process` | the record, the owned streams, the clock, the bound before each close, the unconfirmed references that leave with the cancellation |
| `v0_s3_native_broker.py:_release_raw_streams` | the bound is read again before each close, the confirmed closes are never repeated |
| `v0_s3_native_broker.py:_LauncherCustody` | the bound travels with its clock |
| `v0_s3_native_broker.py:_release_budget` | the clock of the domain of the deadline |
| `v0_s3_native_broker.py:WindowsApi._wait_timeout_ms` / `_recovery_timeout_ms` / `BrokerCore._wait_timeout_ms` | the millisecond value is floored and never rounded up |
| `v0_s3_native_broker.py:StreamChannel.read` | the wait is cropped to the current effective deadline; an expired bound asks for nothing |
| `v0_s3_native_broker.py:BrokerLoop._loop` / `_context_remaining` | the current minimum of the original context is part of the bound of the next read |
| `v0_s3_native_broker.py:launch_broker` | the admission is asked again before the hash and before the channel |
| `v0_s3_native_broker.py:_is_startup_refusal` (new) | a refusal of the admission keeps the admitted process owned and recoverable |
| `v0_s3_native_custody.py:_ChannelPump` | the ONE context of the round; the reply event re-reads it before the wait; the pump ends when the bound arrived |

---

# Static follow-up 01 — the changed assertions of the residual M07 and of PF13

Baseline `a69170c`.  Every change is **inside an existing node id**: the exact
189 node ids and their order are unchanged (`node-identity.json`).

| # | Node | Kind | Before | After | Why |
|---|---|---|---|---|---|
| 1 | N07-R09 | strengthening | the ordinary raw-failure path of a launch that never built its channel | a new phase: a **real** channel of the launch completes and closes the original files of the process, the original HANDLE fails once and the **same** owner is released again | M07-A.1: the ownership history of the channel must survive its completion; the assertions are the counts of the closes (`== 1`), of the HANDLE attempts (`== 2`), of the successful HANDLE closes (`== 1`), of the terminate and wait calls (`== 1`) and the convergence of the owner |
| 2 | N05-R10 | strengthening | the ordinary raw-failure path of a launch that could not be handed over | three new scenarios on a **scoped** production table: the ordinary failure of the input followed by the exact `KeyboardInterrupt` of the output, the companion with the `KeyboardInterrupt` at the **first** raw close and the cross-product with the earlier success and a failing original HANDLE | M07-A.2: the persistent references before the salvage, the identity of the original error, the counts of the successful operations and the same-owner recovery of **all** the originals; the process has **no** standard error, exactly like the default `Popen` |
| 3 | N10-R05 | strengthening | the cancelled retry of an unresolved original raw stream | a new phase with five cases: the round tightened during the wait of the process, the round tightened between two initial closes, the positive case, the **repeated** release of the expired round and the successful unresolved-only retry of a **separate** original round that is still positive | M07-A.3: the next close is **zero** (it is never attempted) and the original is retained with its identity; a repeated release of the **expired** round starts no new close and the one way deadline of the round is never renewed; the successful retry happens under the same owner, the same original context and the same original deadline of a round that was positive from the start |
| 4 | N07-R02 | premise repair | the millisecond boundary used `1000.0 + remaining` and subtracted `1000.0`: a float labelled one millisecond need not remain exactly one millisecond after the subtraction of an epoch | the boundary uses a common **zero** clock origin and the expected values are derived from the **actual** remaining; the **recovery** adapter joins the API and the Core adapters | PF13-02: the fixture may not demand a value that the production floor may refuse correctly; the finite no-positive-floor rule is unchanged |
| 5 | N10-R07 | strengthening | the context of the round reached every layer of the chain | a new phase: the **real** parent pump reads the channel through the BrokerProcess and the queue of the channel, and the parent waits for its replies on the event of the round, after the original context was tightened; the zero expiry is included | PF13-03: the actual requested arguments of the queue wait and of the event wait; the recorders are transparent and they call the original owner of the wait |
| 6 | N07-R13 | strengthening | the stop during the hash refuses the channel | a new phase: the public `Session.stop` while the process of the round is **admitted**; the counters of the seams prove that the executable was never read, never digested and that the channel was never constructed | PF13-03: the absence of a channel is never a proof that no constructor was attempted; the admitted process keeps its owner and stays recoverable |
| 7 | the shared fixture | extension | `m07a_interrupted_launch` always built its own process | it accepts a **process** argument: the production launch is used unchanged and the group hands its own process with its named fault seams over | the groups that drive a named fault of the original files need the production launch and their own originals |
| 8 | correction05 | extension | the module had no evidence writer | the module writes its bounded facts in the **NEW** directory of the correction 13 | the new diagnostics of the module are written in the root of this correction and never in the historical directories |

## The production owners that changed in this follow-up

| Owner | The change |
|---|---|
| `v0_s3_native_broker.py:_LaunchAggregate` | the durable ownership history of the channel, the registration of the pending originals, the reconciliation of the registered originals and the eligibility of a raw close |
| `v0_s3_native_broker.py:_release_launch_process` | the export of the ordinary failures as they happen, the shared failures of the owner and the current minimum before every initial raw close |
| `v0_s3_native_broker.py:_release_minimum` (new) | the current minimum of a release and the clock of its domain |
| `v0_s3_native_broker.py:_release_budget` | it reads the minimum through `_release_minimum` |
| `v0_s3_native_broker.py:_release_raw_streams` | the originals that the channel took are never closed by the launch |
