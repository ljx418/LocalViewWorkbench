# N1 correction13 — implementation report (STATIC, not validated)

Coordinate: `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.
Starting candidate `29c5215ad44721c60145bad61165b99580cc1898` (product) and
`e2d2831c852c5155d71a0d37700b8a99e640dd2d` (failed evidence of the correction 12,
preserved and unchanged).
Scope: the seven files of `native-custody-correction-13/scope.json` and the NEW
`implementation-native-custody-correction-13/` report root.

**This report signs no Major and no Stage.**  It reports what the source now
does and what the frozen nodes now assert.  The batch of 189 nodes has **not**
been executed by this implementation: the root pins the candidate, runs the
three commands of the plan request and reviews the result.  Dynamic evidence
is `NOT_RUN`, native behaviour stays `NOT_PROVEN`, the historical counter
continuity stays `UNAVAILABLE_NOT_PROVEN`.

## 0. What the implementation did and did not do

* It read the root pack `AGENTS.md`, `.agent-governance/README.md`,
  `plans/execution-control.json`, `docs/24_EXECUTION_MASTER_PLAN.md`, the
  correction-13 `contract.md` / `scope.json` / `decision.json` and the **full**
  independent production review of the correction 12
  (`native-custody-correction-12/production-review-01/review-result/review.md`
  and `receipt.json`).
* It edited **only** the six allowed source/test files (the seventh allowed
  file, `tools/test_v0_s3_native_custody.py`, is **unchanged**) and it wrote
  **only** into the NEW `implementation-native-custody-correction-13/` root.
* It executed **no** candidate import, **no** collection, **no** pytest,
  **no** ctypes, **no** native call, **no** runtime or helper probe, **no**
  service, **no** GPU, **no** model, **no** network, **no** database, **no**
  media, **no** ledger and **no** counter access.  The only commands that
  touched the candidate were `compile(source_text, name, "exec")` in memory,
  `ast.parse`, `symtable` resolution, `sha256sum` of the source text and the
  extraction of the node ids with the AST.
* It did **not** re-run the batch of the correction 12.  The three commands of
  the trusted guard/runner/absence policy are **requested** for the newly
  sealed candidate only.

## 1. The six open production subpaths

### 1.1 M07-A.1 — one route per original resource (no repeated confirmed close)

Before: the helper of the process enumerated **all** the original streams of
the process again on every release and the retry of the raw streams closed the
**same** original a second time.  A stream whose close had already been
confirmed was closed again, and the helper and the retry acted on one and the
same original file.

Now (`tools/v0_s3_native_broker.py`):

* `_LaunchProgress` is the **monotonic progress record** of the original
  resources of one launch.  Every confirmed fact — the exit of the process,
  the release of its original handle and the confirmed close of each original
  raw stream — is written into it **immediately** after its confirmation and it
  is never rewritten (the first value of a fact is the only value of it).
* `_LaunchAggregate.progress` owns that record and it belongs to the **owner**
  of the launch.
* `_release_launch_process` receives the record (`progress`), the streams that
  the **owner** already owns (`owned_streams`) and the clock of the domain of
  the bound (`clock`).  It
  * skips a stream whose confirmed close is in the record,
  * skips a stream that the **owner** owns (the retry of the owner closes it),
  * records the confirmed close of every stream it really closed.
* `_LaunchAggregate.release` hands the owned streams to the helper as
  `owned_streams`, so the helper route and the raw-retry route can never close
  the same original, and the raw retry records the confirmed close before it
  forgets the stream.

The cross-product of the original review is therefore covered by **one** owner:
process exit, HANDLE release and each raw close are independent facts, each
recorded once, each retried only while it is unresolved.

### 1.2 M07-A.2 — an interruption does not lose the confirmed facts

Before: the helper returned an aggregate.  A `KeyboardInterrupt`/`SystemExit`
at a raw close escaped the helper (the helper catches only `Exception`), so the
return value never arrived: the confirmed exit, the confirmed HANDLE release
and the confirmed stream closes were lost and the next recovery repeated them.

Now:

* The confirmed facts live in the progress record of the **owner** and not in
  the return value of the helper.  `_LaunchAggregate.release` reads
  `self.progress.fact('process')` **after** the helper and derives
  `process_exit_confirmed` and `handle_released` from it.  A helper that was
  interrupted before it returned does not lose the work that it really did.
* The **unconfirmed** references that the helper could not confirm are handed
  to the owner through `retained_out` **before** the cancellation leaves: a
  helper that does not return does not return its report either.
* The exact original cancellation object is still the error that leaves: the
  aggregate collects it in `cancellations` and raises it at the end, after
  every safe step of the release.

### 1.3 M07-A.3 — the bound is read again before **each** close, in its own domain

Before: the initial raw closes of the helper were unconditional and the retry
snapshotted the minimum of the context **once**, before the loop.  A context
that was tightened between two closes was not observed, and a deadline of the
round was compared with the clock of another domain.

Now:

* `_release_launch_process` checks the bound **before each** initial raw close
  and refuses the close when the bound arrived
  (`BROKER_RAW_STREAM_DEADLINE_EXCEEDED`); the stream keeps its owner and its
  original reference.
* `_LaunchAggregate._release_raw_streams` reads the bound **again before each
  retry** (the value is no longer snapshotted outside the loop).
* The clock of the domain travels with the deadline:
  `_LaunchAggregate._release_bound`, `_LauncherCustody._effective_bound` and
  `_release_budget(..., clock=)` return the clock of the context that owns the
  deadline, and `_LaunchAggregate` shares the clock of its own context.  A
  deadline of the round is never compared with the clock of another domain.

### 1.4 M08-C.1 — every next wait is cropped by the current original minimum

Before: the transport read of the broker loop used the cached lease
`_deadline_mono` only; the parent pump passed the fixed `CHANNEL_POLL_SECONDS`
through `BrokerProcess.read` to `StreamChannel.read`, which passed it to
`queue.get` unchanged; and the reply event of the parent waited on a numeric
deadline that was constructed earlier.

Now:

* `StreamChannel.read` crops the requested timeout to the **current**
  effective deadline of the round (the bound of the channel, the absolute
  deadline and the **published** cleanup deadline).  There is no positive
  floor: an expired round asks for **nothing** and the read becomes a non
  blocking inspection.  This covers the child loop (the transport of the loop
  **is** the channel) and the parent pump (the pump reads the same channel).
* `BrokerLoop._loop` reads the current minimum of the original context of the
  round before every transport read (`_context_remaining`) and ends the round
  with `LEASE_EXPIRED` — the lease of the round, not a failure of the channel —
  when that minimum arrived.  A `BROKER_CHANNEL_TIMEOUT` of the transport is
  mapped to the same lease.
* `_ChannelPump` (parent side, `tools/v0_s3_native_custody.py`) holds the ONE
  context of the round.  `take` re-reads the **current** effective deadline of
  that context immediately before the actual wait, so a number that was
  constructed earlier is never the authority of a wait.  The pump also ends
  itself when the bound of the round arrived: it never waits with a lease of
  its own and it never spins on a round that is over.

The service-idle polls stay separate from the round completion waits: the
heartbeat slice and the pump poll keep their own budgets and are never used as
a proof of the convergence of the round.

### 1.5 M08-C.2 — the millisecond adapters floor and never round up

Before: `WindowsApi._wait_timeout_ms`, `WindowsApi._recovery_timeout_ms` and
`BrokerCore._wait_timeout_ms` returned `max(1, min(WAIT_MILLISECONDS,
int(remaining * 1000)))`: a remainder of a fraction of a millisecond asked the
primitive for **one** millisecond, which is more than the remaining of the
round.

Now: the three adapters return `min(WAIT_MILLISECONDS, int(remaining * 1000))`.
A positive remainder below the representable unit is **zero**: the adapter asks
for no wait at all.  The exit of a process is never inferred from a requested
zero — `WaitForSingleObject` with a zero budget is the named
`WaitForSingleObject:no_budget` refusal and the control handle of the process
is retained; the exit-before-HANDLE-close safety is untouched.

### 1.6 M08-E — the next distinct effect of the launch is refused

Before: the launcher checked the public stop, the cancel, the unknown state
and the effective minimum **before** the process; after the process was
admitted, the hash of the executable and the creation of the channel followed
without any further admission.

Now (`launch_broker`):

* `_check_launch_budget(context, 'LAUNCH:BEFORE_HASH')` is asked immediately
  before the read of the executable, and
  `_check_launch_budget(context, 'LAUNCH:BEFORE_CHANNEL')` is asked inside the
  `channel_factory`, immediately before the channel is built.  A stop that was
  published while the hash of the executable was really in flight refuses the
  channel.
* The process of the round is registered with the table of the launcher
  **before** any refusal (`launch.bind_process` + `_LAUNCHER_CUSTODY.retain`),
  so it keeps its owner and it stays reachable and recoverable.
* A **refusal of the admission** is not a failure of the resources of the
  launch: `_is_startup_refusal` tells the adoption apart from an ordinary
  failure and the adoption does **not** release the launch in that case.  The
  admitted operating system work is never pretended to be undone and the
  registration of the original resource is never skipped.
* The bounded recovery of the launcher releases the retained process and the
  owner of the launch converges.

## 2. The six actual failed nodes — the cause from the actual source

The causes below were derived from the production source and from the raw
output of the failed batch, not from a fixture-only assumption.  The output of
the failed batch is preserved unchanged in
`implementation-native-custody-correction-12/attempt01/guarded-validation.stdout.log`.

### 2.1 N05-R14 — the instrumentation raced the first frame (test premise)

Cause: `StreamChannel` starts its reader **inside its constructor**.  The
group installed `recording_put` on the queue **after** the channel was built,
so the first frame (`b'one\n'`) was put before the instrumentation existed.
Only the second put was recorded: `puts == [0.5]`, `len(puts) >= 2` failed
with `assert 1 >= 2`.  The old `SlowReader` also returned the end of the file
when its single `released` flag was already set, so the second frame could
disappear entirely.

Repair (test only, `tools/test_v0_s3_native_custody_correction05.py`): the
reader of the group now publishes an explicit `first_entered` event when it is
really inside its first read and a `second_entered` event when it is really
inside its second read.  The group waits for `first_entered`, installs the
recorder, releases the first frame, tightens the bound of the round and only
then releases the second frame — which is delivered **exactly once**.  The
assertion is unchanged in strength (`len(puts) >= 2`); the values that are
asserted are the values that the production requested.  The teardown releases
both frames and joins the reader thread with a bounded wait, unconditionally.

### 2.2 N07-R13 — the assertion was global and the owner was not scoped

Cause: the assertion asked for **no** aggregate in the **whole** table of the
launcher, which is shared by the whole batch, and the refused launch keeps an
**empty** bookkeeping owner until the bounded recovery converges it.  The
assertion therefore read the leftovers of another check of the batch as the
resources of this one.

Repair (test only, `tools/test_v0_s3_native_custody_correction07.py`): the
group takes a **baseline** of the identities of the aggregates before its own
launch, finds **its own** owner afterwards and asserts that this launch has
no process, no channel and no raw stream of its own.  The bounded recovery is
then asked to converge and the group asserts that **its own** owner is gone.
The table is never emptied by hand and the launches that another check
retained are never touched.

### 2.3 N10-R04 — the premise did not prove that a read primitive was active

Cause (from the source, not from the fixture alone): `StreamChannel.close`
sets the cancel flag of the channel **before** it joins the reader thread.
The patched `threading.Thread.start` raised the `RuntimeError` immediately
after the reader thread really started, so the drain thread had not reached
its read yet.  When the close set the cancel flag, the drain thread entered
`StreamChannel._drain`, called `self._reader.read(...)`, and the admission of
the endpoint saw the cancel flag that the close had just published.  The read
was refused with `BROKER_PIPE_CANCELLED`, the drain thread ended **before** the
cleanup and the channel was released **correctly**: the reader was really
finished, both ends were closed and no worker was retained.  The product was
right and the premise of the group was wrong: a start that returned does not
prove that a read primitive is still active.

Repair (test only, `tools/test_v0_s3_native_custody_correction10.py`): the
worker of the read publishes an explicit event (`worker_inside`) **before** it
waits inside the primitive, and the group waits for that event **before** it
injects the interruption of the start.  The group then really observes the
partial channel: it is retained, the channel is coordinated **before** the
process, the read end is never closed under the live worker, the process is
terminated and waited exactly once, the files of the process are never closed
by the process helper, and the **same** owner recovers the channel after the
explicit release of the read.

### 2.4 N10-R05 — the cancellation never fired because another round's bound refused the retry

Cause (from the source): the table of the launcher of this package is shared
by the whole batch and it holds the **context** that the last launch bound to
it (`_LauncherCustody.bind_context`).  The check of the correction 12 binds a
context whose published cleanup deadline (`999.0`) is already expired in the
clock of that context (`ManualClock(1000.0)`).  The bounded recovery of the
launcher therefore handed the aggregate a bound that had arrived, and
`_LaunchAggregate._release_raw_streams` refused the retry of the raw stream
**before** it started: the close was never attempted, the
`KeyboardInterrupt('raw_stream_close_cancelled')` of the original stream never
fired and the group saw `DID NOT RAISE`.  The product was right: an expired
bound refuses a new close and retains the original ownership.

Repair (test only, `tools/test_v0_s3_native_custody_correction10.py`): the
phase runs on a **scoped** table of the launcher — a real
`_LauncherCustody` that the group installs for the phase with
`unittest.mock.patch.object(broker_module, '_LAUNCHER_CUSTODY', scoped)`.  The
production table is used, it is never emptied by hand and the context of
another round of the batch never reaches this launch.  The assertion is
**unchanged** (`pytest.raises(KeyboardInterrupt)`): the cancellation is never
read as a swallowed one.  The phase ends with the explicit final recovery of
the **same** owner after the test released its fault seam (`stdout.cancel =
False`): the stream is really closed, the owner is released and the table
converges.

The production side of M07-A.2 was repaired as well (§1.2): the confirmed exit
and the confirmed HANDLE release now survive an interruption of the release
and the original cancellation is still the error that leaves.

### 2.5 N10-R09 — the recorder did not implement the signature of `queue.get`

Cause: `_StartupOwner.await_result` observes its result with a **non
blocking** `get_nowait()` (the correction 12 repair) and `queue.get_nowait`
calls `self.get(block=False)`.  The recorder of the group had the signature
`recording_get(timeout=None)` and raised
`TypeError: recording_get() got an unexpected keyword argument 'block'`.

Repair (test only, `tools/test_v0_s3_native_custody_correction10.py`): the
recorder implements the **whole** signature of `queue.get`
(`block=True, timeout=None`), forwards the arguments to the original and
records the **non blocking observation** apart from the **bounded positive
waits**.  The production `get_nowait` is not altered and the interrupted-start
subcase is not skipped.  The schedule is strengthened: a dedicated thread
tightens the deadline of the round **between** two waits and the group proves
that the next wait received the time that was really left.

### 2.6 N10-R10 — the publication of the outcome is not the consumption of it

Cause: the group waited for `worker.outcome_published` and then read
`outcome['error_object'].lvw_parallel_timeout`.  The **publication** of the
outcome happens in the worker; the **attachment** of the parallel timeout
happens later, in the endpoint, when the endpoint raises the original error
object (`_WindowsPipeEndpoint._parallel_timeout`).  The group therefore read
the attribute before the endpoint had consumed the outcome: `parallel` was
`None` and the assertion `isinstance(parallel, dict)` failed.

Repair (test only, `tools/test_v0_s3_native_custody_correction10.py`): the
group waits for the **real** termination of the reader thread of the channel
before it asserts the attached facts.  That termination is the barrier of the
consumption: it is a real join of a real thread and never a sleep that proves
it.  The three schedules stay distinct inside the same node id:

1. `r10-published-before-timeout` — the ordinary failure is published
   **first**, the outcome of **that** generation really exists, the effective
   timeout arrives **afterwards** and the endpoint consumes the outcome only
   after the timeout was decided (the gate is a transparent wrapper of the
   production wait of the worker).
2. `r10-timeout-confirmed` — the timeout is decided first and the fault is
   published **during** a **confirmed** coordination of the round.
3. `r10-timeout-failed` — the same with a **failed** coordination whose
   failure is a parallel fact.

The generation is the fact of the worker itself (`worker._submitted`), never a
hard coded number; the original error object and its code are preserved; the
two real `Session.stop` histories are asserted in every subcase; the later
phases are `NOT_RUN` when an earlier assertion fails.

## 3. The M09 schedules and the interrupted-start join are reachable

The three M09 schedules above are **reachable through explicit barriers**:

* the gate of the published-before-timeout schedule is a transparent wrapper
  of the production wait of the worker: it calls the original wait and it
  holds the endpoint between that wait and the recheck of its generation.  The
  publication, the timeout and the consumption are recorded in their order;
* the two coordination schedules are driven through the real chain of the
  round (the session, the handle of the broker, the channel and the worker of
  its read endpoint) and the only seam is the primitive table;
* the interrupted-start join of N10-R09 is driven by a start that raises
  **after** the thread of the step really came up: the facts of the thread
  (`_thread_facts_started`) decide, the owner joins the thread that it really
  has and a later settle of the **same** owner converges after the real exit
  of the thread.

Written code is **not** counted as coverage.  Every one of these facts is
`NOT_RUN` until the root runs the finite batch of the 189 nodes.

## 4. What is delivered

| Deliverable | File |
|---|---|
| this report | `report.md` |
| the atom → production → event → oracle → negative → returned state → salvage matrix | `atom-matrix.md` |
| the changed assertions | `changed-assertions.md` |
| the wait inventory and the dynamic current-wait boundaries | `wait-inventory.md` |
| the digests of the seven allowed files | `source-pins.json` |
| the identity and the order of the 189 nodes | `node-identity.json` |
| the static receipt of this implementation | `static-implementation-receipt.json` |
| the REQUEST of the finite batch | `validation-plan-request.json` |
| the runtime diagnostics of the group | `evidence/` and `f5-evidence/` |

The exact identity and the exact order of the 189 nodes are unchanged: the
node ids were extracted with the AST from the five modules and compared with
the frozen list of the plan of the root — **189 = 189 and the two lists are
identical**.  No node was added, renamed, removed or moved, no denominator
changed and no product threshold changed.

## 5. What is explicitly **not** claimed

* No Major is closed by this implementation.  The closure of M07-A, M08-C and
  M08-E belongs to the isolated independent review and to the gate owner.
* No Stage PASS, no final independent acceptance, no N2 admission and no
  native proof follows from this report.  `native_execution`,
  `native_cleanup`, `gpu_released`, `port_released`, `sampler`,
  `parent_crash_recovery` and `windows_stdin_eof` stay `NOT_PROVEN`.
* The dynamic coverage of the batch is `NOT_RUN`: this implementation did not
  import, collect or run the candidate.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`: nothing
  was reconstructed, refunded or reset and the counter was never read.
* The historical reports, the pinned evidence of the corrections 08 to 12, the
  root packets, the execution control and the MANIFEST were not touched.

---

# Static follow-up 01 of the correction 13 (the residual M07 and the PF13 drivers)

Baseline `a69170c446ff4af2955ddac1707af91d00c5dfcd`.  Independent review:
**F0 / M1 / m0**, 58 CLOSED_STATIC / 5 OPEN / 9 UNCERTAIN, **M08 CLOSED_STATIC**,
M07 OPEN with the three residual paths A.1, A.2 and A.3.  Root static preflight:
**PF13-01**, **PF13-02** and **PF13-03**.  This section is the delivery of the
static follow-up of the root packet
`native-custody-correction-13/static-correction-01/contract-addendum.md`.
The exact `a69170c` static delivery is archived in
`native-custody-correction-13/static-correction-01/static-candidate-a69170c.zip`
and the git history preserves it.  **STATIC only**: no import, no collection,
no pytest, no ctypes, no native call, no counter and no helper probe.

## 6. The three residual paths of M07

### 6.1 M07-A.1 — the durable ownership history of the channel

Before: the eligibility of a raw close was decided from the **presence** of
the channel in the active slot.  A channel that **completed** was forgotten
and the slot was cleared, so the next release of the same owner became the
raw closer of the original files that the channel had really closed: the
process exit was skipped correctly and the original HANDLE was retried, but
the original standard input and the original standard output were closed a
second time.

Now (`tools/v0_s3_native_broker.py`):

* `_LaunchAggregate._channel_owns_raw` and `_LaunchAggregate._channel_owned_raw`
  are the **durable ownership history** of the launch.  They are written at the
  **actual registration** of the channel - `retain('channel', ...)` and
  `bind_channel(...)` - and they are **never revoked**: clearing the active
  slot does not give the ownership back and it never creates a new raw closer.
* The history keeps the **identity** of the original files that the channel
  took (the name and the object), not a label and not a summary.
* `release()` decides the eligibility of a raw close with the history and not
  with the presence of the channel: `close_pipes = channel is None and not
  self._channel_owns_raw`.
* `_release_raw_streams` refuses the raw close of an original that the
  channel took (`BROKER_RAW_STREAM_OWNED_BY_CHANNEL`).

A failed original HANDLE is now retried **alone**: the confirmed exit is
skipped, the original HANDLE is the only thing that is closed again, no
original file is closed a second time and no new owner or PID is looked up.

### 6.2 M07-A.2 — every unconfirmed original keeps an executable owner

Before: the ordinary failure of a raw close was kept in the **local** report
of the helper.  A `KeyboardInterrupt`/`SystemExit` at the next raw close
escaped the helper, the report never arrived and the earlier ordinary failure
was lost: the launch kept only the interrupted original and the original that
was **never visited** was not known at all.  The confirmed exit and the
confirmed HANDLE allowed the process to be removed, so the remaining original
had no executable recovery route.

Now:

* `_LaunchAggregate._register_pending_raw` registers the **original
  identities** of the process with the owner **before** the first
  interruptible raw step.  An original that is never visited is known and it
  keeps its owner.
* `_release_launch_process` exports every ordinary failure **as it happens**
  through `retained_out` and it writes the failures into the shared
  `failures_out` dictionary of the owner.  A helper that is interrupted
  before it returns no longer loses the failure that happened before the
  interruption.
* `_LaunchAggregate._reconcile_pending_raw` reconciles the registered
  originals with the progress record after the helper: a confirmed close is
  forgotten by the owner and by the table of the launcher, and every other
  original - the one whose close **failed** and the one that was **never
  visited** - keeps its identity and its owner (`close_failed` and
  `close_unconfirmed` are labels; the identity is the authority).
* The original `KeyboardInterrupt`/`SystemExit` object is still the error
  that leaves, after the safe independent cleanup.

### 6.3 M07-A.3 — the current minimum before every **initial** raw close

Before: the aggregate computed the bound once before the helper and the
helper compared every initial raw close with that earlier number.  A context
that was tightened by the wait of the process or by a previous close of an
original was not observed: the next close was admitted against a stale
minimum.

Now: `_release_minimum(deadline, context, clock)` returns the **current**
minimum of the release - the deadline of the caller, the absolute deadline of
the original context and the **published** cleanup deadline of the round -
together with the clock of its domain.  `_release_launch_process` calls it
**before every initial raw close**: an expired bound starts no new close, the
original keeps its owner and its identity and the failure is named
(`BROKER_RAW_STREAM_DEADLINE_EXCEEDED`).  The already-owned retry loop reads
the bound again on every iteration and it is unchanged.  The finite
no-context facade keeps its bounded wait.

## 7. The executable test drivers of PF13

Every driver is inside an **existing** node id.  No node was added, renamed,
removed or moved and the exact 189 identities and their order are unchanged.

| Preflight | Driver | Node | What it drives |
|---|---|---|---|
| PF13-01 (1) | the completed channel owns and closes the originals, the original HANDLE fails once, the same owner retries | `N07-R09` | the channel really closes the original files once, the HANDLE is attempted twice (one failure, one success), the exit is waited for once and the table converges only when every fact is true |
| PF13-01 (2) | the ordinary failure of the input followed by the exact `KeyboardInterrupt` of the output, and the companion with the `KeyboardInterrupt` at the **first** raw close | `N05-R10` | the persistent original references before the salvage, the original error identity, the counts of the successful operations, the release fault and the same-owner recovery of **all** the originals; the process has **no** standard error, exactly like the default `Popen` |
| PF13-01 (3) | the earlier success with a failing original HANDLE | `N05-R10` | the confirmed close is never repeated, the exit is never confirmed again and only the HANDLE and the unresolved original are retried |
| PF13-01 (4) | the round is tightened during the wait of the process and between two initial raw closes, with the exact expired and positive cases, the **repeated** release of the expired round and the successful unresolved-only retry of a separate original round that is still positive | `N10-R05` | the next close is **zero** (it is never attempted) and the original is retained with its identity; a repeated release of the expired round starts no new close and the one way deadline of the round is never renewed; the successful retry keeps the same owner, the same original context and the same original deadline |
| PF13-02 | the millisecond boundary with a common **zero** clock origin through the API adapter, the **recovery** adapter and the Core adapter | `N07-R02` | the requested primitive arguments at the exact zero, below the unit, at the unit and one over it; the expected values are derived from the **actual** remaining; the finite no-positive-floor rule is unchanged |
| PF13-03 (a) | the real parent pump through the BrokerProcess and the queue of the channel, and the parent reply event, after the original context was tightened | `N10-R07` | the **actual** requested arguments of the queue wait and of the event wait, with the zero expiry included; the recorders are transparent and they call the original owner of the wait |
| PF13-03 (b) | the public `Session.stop` while the process of the round is **admitted** | `N07-R13` | no read of the executable, no digest and **zero** channel constructor attempts, while the admitted process keeps its owner and stays recoverable; the separate stop-during-hash schedule is preserved |

The fixtures are honest about what they observe: the counters of the seams
(the digest, the read of the executable and the constructor of the channel)
are the evidence - the absence of a channel is never a proof that no
constructor was attempted - and the millisecond fixture no longer depends on
the subtraction of an epoch.

## 8. What is preserved

* **M08-A, M08-B, M08-C.1, M08-C.2, M08-D and M08-E** stay CLOSED_STATIC:
  none of the paths that the independent review closed was altered.  The
  production delta of this follow-up touches the ownership of the original
  resources of a launch and the admission of their closes.
* **M05, M06, M09, m03** and the **M03 exit-before-HANDLE-close** safety stay
  CLOSED_STATIC.
* The six obligations of the failed nodes of the correction 12 and the three
  M09 schedules with the interrupted-start join stay inside the same node ids.
* The exact 189 node identities and their order, the product thresholds, the
  public schema and the denominator are unchanged.

## 9. What is still not claimed

* No Major is closed by this implementation, no Stage PASS, no native proof
  and no human signature.
* The dynamic coverage of the batch is `NOT_RUN`: the implementation did not
  import, collect or run the candidate.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`.

---

# Static preflight 04 of the correction 13 — the expired round is never renewed

Baseline `41df626f395172d75791892ba439df5f3924bbce`.  Root static preflight
**PF13-04**: the N10-R05 driver of the static follow-up tried to make the
**expired** round of the first case positive again with
`context_one.bind_absolute_deadline(clock_one.value + 10.0)` and expected the
owned retry to close the refused originals.  `_RoundContext.bind_absolute_deadline`
only **shortens**: the later call does not extend the expired value, so the
correct production behaviour is the continued refusal and the continued
retention of the originals.  The fixture, not the product, was wrong.

**The production of `41df626` is unchanged.**  The repair is **test only** and
it does not weaken the deadline monotonicity, replace the original context,
rewind a clock, reset a private field, introduce a fresh lease or change any
product contract or threshold.

## 10. What the driver now proves

| Case | What it drives | What it asserts |
|---|---|---|
| the round tightened during the wait of the process | the original round expires while the process is coordinated | no close is attempted, the original keeps its identity and its owner |
| the round tightened between two initial closes | the first close shortens the original deadline | the **second** close is not attempted, the first one is confirmed |
| the positive case | the original round stays positive | every initial close is really attempted and confirmed |
| the **repeated** release of the expired round | the **same** owner is released again while the one way deadline of the round is expired | **zero** additional closes, the exact originals keep their identity and their owner and the current bound of the round is the expired one; the deadline of the round is **not** renewed |
| the successful unresolved-only retry | a **separate** original round that is positive from the start, with a controlled **ordinary** close failure whose fault seam is released by its own first attempt | the first attempt retains the original with its identity, the **same** owner really closes it under the **same** original context and the **same** original deadline, and the table of the launcher converges |

The expired round is never counted as renewed: the group asserts the value of
the absolute deadline of the round after the repeated release, and it never
calls `bind_absolute_deadline` with a later value on an expired round.

## 11. What is preserved

* All 189 node identities and their order are unchanged; the repair is inside
  the existing node `N10-R05`.
* The expiry negatives of the M07-A.3 paths stay: the refusal of a close at
  an expired bound, the retention of the original with its identity and the
  naming of `BROKER_RAW_STREAM_DEADLINE_EXCEEDED`.
* Every other schedule of the group, the six obligations of the failed nodes
  of the correction 12, the three M09 schedules and the interrupted-start
  join stay inside their node ids.
* The production of `41df626` is unchanged while its independent immutable
  source review runs; the historical evidence, the root packets, the control,
  the MANIFEST and the trusted runner and guard were not touched.

## 12. What is still not claimed

No Major is closed, no Stage PASS, no native proof and no human signature.
The dynamic coverage of the batch is `NOT_RUN` and the historical counter
continuity stays `UNAVAILABLE_NOT_PROVEN`.
