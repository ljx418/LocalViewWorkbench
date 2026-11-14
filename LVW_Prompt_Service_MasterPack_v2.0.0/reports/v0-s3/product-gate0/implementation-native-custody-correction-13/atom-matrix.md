# N1 correction13 — the atom matrix

Coordinate `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.  Candidate
`29c5215` + the repair of this correction.  **Static**: every dynamic column
below is `NOT_RUN` and every native column is `NOT_PROVEN`.

The columns are: the atom of the independent review, the production owner
that carries it, the **event** that the group drives, the **oracle** that it
observes, the **negative** that it refuses, the **returned state** of the
production and the **salvage** that the owner of the test performs.

## 1. The six open production subpaths

| Atom | Production owner (file:symbol) | Event | Oracle | Negative | Returned state | Salvage |
|---|---|---|---|---|---|---|
| M07-A.1 (two routes to one original) | `v0_s3_native_broker.py:_LaunchProgress`, `_LaunchAggregate.release`, `_release_launch_process`, `_LaunchAggregate._release_raw_streams` | the same owner releases the launch twice: the first release confirms the exit and the handle and leaves one raw stream unconfirmed | the second release closes the unresolved original **exactly once**; the confirmed closes are **not** repeated (`stream.close` attempts are counted by the group) | the helper route and the raw-retry route may never close the same original; a confirmed close is never repeated | the facts of the aggregate name the released and the retained resources; the progress record holds the confirmed facts | the same owner retries the unresolved stream and the table of the launcher converges |
| M07-A.2 (an interruption loses the facts) | `_LaunchProgress`, `_LaunchAggregate.release`, `_release_launch_process(retained_out=...)` | a `KeyboardInterrupt`/`SystemExit` fires at a raw close of the helper | the confirmed exit and the confirmed HANDLE release **survive** the interruption and the next recovery does not repeat them; the exact original cancellation object is the error that leaves | the cancellation may never replace the ordinary failure and may never be swallowed | the facts of the aggregate name the released, the retained and the cancelled | the owner of the test releases the fault seam and the same owner recovers |
| M07-A.3 (the bound of each close) | `_LaunchAggregate._release_bound`, `_release_raw_streams`, `_release_launch_process`, `_LauncherCustody._effective_bound`, `_release_budget(clock=)` | the original context is tightened **between** two raw closes; the bound of the round expires during the coordination of the process | the close that follows the tightening is refused; the original keeps its owner and its original reference; the deadline is compared in the clock of its own domain | an expired bound never starts a new close and never opens a cleanup lease of its own | the facts of the aggregate name `BROKER_RAW_STREAM_DEADLINE_EXCEEDED` and the retained original | the same owner retries the retained original after the bound allows it |
| M08-C.1 (the next wait of the loop and of the parent) | `StreamChannel.read`, `BrokerLoop._loop`/`_context_remaining`, `native_custody._ChannelPump.take`/`_remaining` | the published cleanup deadline of the round is shortened while the loop or the pump is between two waits | the requested argument of the next read is the **current** effective minimum; an expired bound asks for nothing and the loop ends with `LEASE_EXPIRED` | a wait may never ask for more than the remaining of the round; a number that was constructed earlier is never the authority of a wait | the requested arguments are recorded by the group; the stop reason of the loop is named | the owner of the test stops the round in every case |
| M08-C.2 (the millisecond floor) | `WindowsApi._wait_timeout_ms`, `WindowsApi._recovery_timeout_ms`, `BrokerCore._wait_timeout_ms` | the remaining of the round is exactly 0, below 1 ms, exactly 1 ms and just above 1 ms | the requested argument is 0, 0, 1 and 1; a remainder below the unit asks for **no** primitive call | the exit of a process is never inferred from a requested zero; the control handle is retained | the requested primitive arguments are recorded | the owner of the test releases the handles of the façade |
| M08-E (the next effect of the launch) | `launch_broker` (`LAUNCH:BEFORE_HASH`, `LAUNCH:BEFORE_CHANNEL`), `_is_startup_refusal`, `_adopt_broker_process` | the public stop of the round is published while the hash of the executable is really in flight | the hash of the executable runs exactly once and the **channel is never built**; the admitted process keeps its owner and it is reachable and recoverable | a refusal of the admission never undoes the admitted operating system work and never skips the registration of the original resource | the facts of the session name `BROKER_STARTUP_CANCELLED`; the owner of the launch keeps its process | the bounded recovery of the launcher releases the retained process and the owner converges |

## 2. The cross-product of the original resources of one launch

The progress record of the owner is the single place where the facts live.
Every cell is a fact that is recorded **once** and that is retried **only**
while it is unresolved.

| Resource of the launch | Fact that is recorded | Who may confirm it | Who may retry it | What happens when it is interrupted |
|---|---|---|---|---|
| the process | the exit was confirmed | the helper of the process | the same owner of the launch | the fact survives: the next recovery never terminates and never waits a second time |
| the original HANDLE of the process | the handle was released | the helper of the process, after a confirmed exit | the same owner of the launch | the fact survives: the next recovery never closes the handle a second time |
| `stdin` of the process | the close was confirmed | the helper of the process (it is not owned by the raw list) | the same owner of the launch | the fact survives: the next recovery never closes it a second time |
| `stdout` / `stderr` of the process | the close was confirmed **or** it failed | the helper of the process while the stream is not owned; the raw retry of the owner once it is owned | the raw retry of the **owner** alone | the unconfirmed original keeps its owner and its reference; the cancellation is the error that leaves |
| the channel of the launch | the reader, the two ends, the workers and the thread handles | the channel itself (`StreamChannel.close`) | the aggregate of the launch, before the process | the incomplete channel keeps its owner; the raw files of the process are never closed under it |

The two routes (the helper of the process and the raw retry of the owner) can
never act on one and the same original: the streams that the owner owns are
named to the helper (`owned_streams`) and the confirmed closes of the record
are never repeated.

## 3. The six actual failed nodes

| Node | Production owner | Event | Oracle | Negative | Returned state | Salvage |
|---|---|---|---|---|---|---|
| N05-R14 (the put of the reader) | `StreamChannel._put_wait`, `StreamChannel._drain` | the reader of the group is really inside its first read; the instrumentation is installed; the first frame is delivered; the bound is tightened; the second frame is delivered exactly once | two puts are observed; the first asked the wait of the package (0.5 s) and the second asked the time that was really left (≤ 0.02 s) | the recorder may never fabricate a value and the assertion may never be shrunk to one put | the requested timeouts are recorded by the group | both frames are released and the reader thread is joined with a bounded wait |
| N07-R13 (the side effects of the launch) | `launch_broker`, `_LauncherCustody` | a launch whose published cleanup deadline is expired | the launch creates no process, hashes no executable and builds no channel; it keeps **only** an empty bookkeeping owner and that owner converges | the owner of **this** launch is never confused with the launches that another check of the batch retained; the table is never emptied by hand | the own owner of the launch is named by its identity | the bounded recovery of the launcher converges the empty owner |
| N10-R04 (the partial channel) | `StreamChannel.__init__`, `_LaunchAggregate.release`, `_adopt_broker_process` | the worker of the read is really inside its primitive (published event) and **then** the start of the reader raises | the partial channel is retained, the channel is coordinated before the process, the read end is never closed under the live worker, the process is terminated and waited exactly once, the files of the process are never closed by the helper | a returned close is never taken for a release; the process helper never closes the files of a channel | the facts of the aggregate name what it released and what it kept | the read is released explicitly and the **same** owner recovers the channel |
| N10-R05 (the cancelled raw retry) | `_LaunchAggregate._release_raw_streams`, `_LaunchProgress` | the raw stream of an interrupted launch is retried by the same owner and its close is cancelled | the exact `KeyboardInterrupt` of the original stream is the error that leaves; the stream keeps its owner; the confirmed facts survive | the cancellation may never be read as a swallowed one and the assertion of the group is not weakened | the facts of the aggregate name the retained original and the cancellation | the fault seam of the test is released and the same owner recovers the original really closed |
| N10-R09 (the wait of the startup owner) | `_StartupOwner.await_result`, `_StartupOwner._remaining`, `_StartupOwner.settle` | the owner observes its result non blocking, then waits; the deadline of the round is tightened **between** two waits | the observation is not a wait; the bounded waits are cropped to the time that is really left; the expired round is refused with `BROKER_STARTUP_DEADLINE_EXCEEDED` | the production `get_nowait` is not altered and the interrupted-start subcase is not skipped | the requested timeouts are recorded by the group | the threads of the steps are joined with a bounded wait in every case |
| N10-R10 (the outcome of the generation) | `_WindowsPipeWorker.outcome`, `_WindowsPipeEndpoint._await`, `_parallel_timeout`, `BrokerProcess._keep_reader_error_history`, `NativeCustodySession.stop` | the fault is published, the effective timeout arrives, the endpoint consumes the outcome and raises the original error object | the original error object and its code are preserved; the timeout and the failure of the coordination are **parallel** facts; the two public stops keep the history of the reader | a cancellation may never rewrite a published failure and the later phases are `NOT_RUN` when an earlier assertion fails | the phase documents of the three schedules are written before their assertions | the owner of the test stops the round in every case and joins the worker with a bounded wait |

## 4. The preserved safety guards

| Guard | Where it lives | Why it is preserved |
|---|---|---|
| the exit is confirmed before the original HANDLE of a process is closed | `WindowsApi._confirm_process_exit`, `BrokerCore._release_the_records`, `_release_launch_process` | the change of the millisecond adapters never infers an exit from a requested zero; the zero budget is the named `no_budget` refusal and the handle is retained |
| the channel owns the files of the process | `_LaunchAggregate.release` (`close_pipes = channel is None`), `_release_raw_streams` (`BROKER_RAW_STREAM_OWNED_BY_CHANNEL`) | the helper and the raw retry never close a file under a live or a partial channel endpoint |
| the pipe transfer has exactly one owner | `WindowsApi.handover`, `_WindowsPipeEndpoint.close` | untouched by this correction |
| the startup effect guards | `_WindowsPipeWorker.run`, `_WindowsPipeEndpoint._admission_locked` | untouched; the correction 12 repair of the dispatch is preserved |
| the current context at the actual dispatch | `_WindowsPipeWorker.run`, `_WindowsPipeEndpoint._await` | untouched; the correction 12 repair is preserved |
| the established interrupted start is joined for real | `_StartupOwner._thread_facts_started`, `_StartupOwner.settle` | untouched; the fact of the thread decides and the owner keeps its owner |
| the common success notification clears the owner | `WindowsApi._note`, `BrokerCore._release_the_records` | untouched |
| the original M09 outcome selection | `_WindowsPipeEndpoint._await`, `_parallel_timeout`, `_parallel_fault` | untouched; the three schedules of §3 exercise it |
| the atomic frame budget and the overflow | `StreamChannel._record_overflow`, `BrokerLoop._loop` | untouched |
