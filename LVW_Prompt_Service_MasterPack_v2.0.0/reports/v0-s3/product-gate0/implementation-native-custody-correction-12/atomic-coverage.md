# N1 correction12 — the atomic coverage of the repaired subpaths

Every row names the **production** owner that carries the subpath, the
**event** that the frozen node drives, the **oracle** that the node asserts,
the **negative** that the node forbids, the **returned state** that the node
inspects and the **salvage** that the owner of the test performs afterwards.

No row is closed here: every row is a **static** disposition and the dynamic
evidence is the batch that the root pins and runs.

## M07-A — the executable recovery of an unresolved original raw stream

| Field | Value |
|---|---|
| Subpath | M07-A (the residual of the Major M07) |
| Production | `tools/v0_s3_native_broker.py`: `_LaunchAggregate.__init__` (`raw_streams`), `retain_raw_stream`, `forget_raw_stream`, `pending_raw_streams`, `_LaunchAggregate.release`, `_LaunchAggregate._release_raw_streams`, `_LauncherCustody.release` |
| Event | The production `launch_broker` creates the process of the round and the hash of the executable is interrupted: the channel of the round never exists. The release of the launcher terminates the process, confirms its exit, releases its original handle and the close of the raw file of its standard output fails. |
| Oracle | The first release returns the **retained original reference** of the raw stream; the second release of the **same** owner really closes it; the confirmed close happens **exactly once**; the table of the launcher names the stream no more; the process, its exit and its original handle are never released a second time. |
| Negative | The table of the launcher never releases a raw stream of a launch behind the back of the launch; the launch never closes a raw file that a live or partial channel endpoint owns; an expired bound never starts a new close; a failed retry never forgets the owner; a cancelled retry never forgets the owner and never replaces the original failure. |
| Returned state | `aggregate.raw_streams`, the items of `_launcher_custody_items()`, the counters of the raw stream (attempts, confirmed closes) and the counters of the process (terminated, waited, handle closes). |
| Salvage | The owner of the test releases the event of the read and joins the thread of the reader with a bounded wait; the table of the launcher is drained. |
| Nodes | `test_n07_r09_...` (the confirmed retry), `test_n05_r10_...` (the failed retry), `test_n10_r05_...` (the cancelled retry) |

## M08-A — the current context at the actual worker dispatch

| Field | Value |
|---|---|
| Subpath | M08-A |
| Production | `_WindowsPipeWorker.run` (the decision of the dispatch), `_WindowsPipeWorker._effective_deadline`, `_WindowsPipeEndpoint._await` (the wait of the endpoint) |
| Event | The request of a generation is really submitted and the worker is paused **before** the decision of the dispatch; the **original** context of the round is cancelled — or its published cleanup deadline arrives — while the flag of the call and the flag of the channel stay unset; the worker is released. |
| Oracle | The number of the real primitive calls is **zero**; the outcome of **that** generation carries the refusal (`BROKER_PIPE_CANCELLED` / `BROKER_PIPE_TIMEOUT`) and the generation is the one that was submitted; the await of the endpoint notices the cancellation of the original context. |
| Negative | The captured request of the call is never the authority of the decision; no permissive `__new__` fallback is introduced; the initial admission and the admission after the readiness stay closed. |
| Returned state | The ledger of the primitive calls, the outcome of the generation (error, error object, sequence) and the error that the await raised. |
| Salvage | The event that releases the read is set and the worker is stopped and joined with a bounded wait. |
| Nodes | `test_n10_r07_...` (the dispatch of the worker and the await of the endpoint) |

## M08-B — the current bound of the normal `BrokerProcess.close`

| Field | Value |
|---|---|
| Subpath | M08-B |
| Production | `BrokerProcess.close`, `BrokerProcess._cleanup_deadline` |
| Event | The close of the channel publishes a **shorter** cleanup deadline of the round while the absolute lease of the round stays in the future; the process of the broker is still alive. |
| Oracle | The wait of the process receives the time that is really left under the **new** bound (0.5 s in the fixture) and the retry of the wait receives the remaining of the same bound (0.0 s). |
| Negative | The bound that was copied before the channel was closed is never used by a later wait; no new budget of 5 s is opened. |
| Returned state | The ledger of the waits (the clock, the requested timeout) and the facts of the close. |
| Salvage | The core of the fixture releases its own resources. |
| Nodes | `test_n03_r08_...` |

## M08-C — one current-context wait bound and no positive floor

| Field | Value |
|---|---|
| Subpath | M08-C |
| Production | `_StartupOwner.__init__`/`_remaining`/`await_result`, `_WindowsPipeEndpoint._wait_slice`, `StreamChannel._put_wait`, `BrokerLoop._loop` |
| Event | The deadline of the round is tightened while a wait of the owner is running: the absolute deadline of the original context, the published cleanup deadline or the bound of the layer is shortened. |
| Oracle | Every requested wait is the **poll cap of the package** cropped to the current remaining: the wait of the queue of the startup owner, the wait of the worker of the endpoint, the put of the reader of the channel and the read of the transport of the loop.  The read of the transport of the loop asks for 5 ms and not for the 10 ms floor of the package. |
| Negative | No wait asks for more than the remaining; no positive floor beyond the remaining is used anywhere; an expired round refuses at once and never starts a wait. |
| Returned state | The ledger of the requested wait values before and after the tightening. |
| Salvage | The event that releases the read is set; the owner of the startup step is settled and its thread is joined with a bounded wait. |
| Nodes | `test_n10_r09_...` (the wait of the startup owner), `test_n05_r14_...` (the wait of the endpoint and the put of the reader of the channel), `test_n03_r08_...` (the read of the transport of the loop) |

## M08-D — a real join after an interrupted start

| Field | Value |
|---|---|
| Subpath | M08-D |
| Production | `_StartupOwner.start`, `_StartupOwner._thread_facts_started`, `_StartupOwner.settle`, `BrokerLoop._run_startup` |
| Event | The thread of the startup step really comes up and the **start raises afterwards** (`KeyboardInterrupt`); the thread of the step stays alive for a while (the active tail).  In the second direction the start raises **before** the thread exists. |
| Oracle | The facts of the thread decide: the owner joins the thread that it really has, the owner is **not** released while the thread is alive and a later settle of the **same** owner converges after the real exit; a start that never came up keeps the owner and the join is never attempted. |
| Negative | The private flag of the owner is never the authority; no false release, no busy wait and no replacement thread; the original interruption object survives. |
| Returned state | `owner._started`, `owner.in_flight`, `loop._startup_in_flight` and the owners that are in flight in the context of the round. |
| Salvage | The event that releases the tail is set and every thread of the round is joined with a bounded wait, unconditionally. |
| Nodes | `test_n10_r09_...` |

## M08-E — the launch honours the public stop and the published cleanup

| Field | Value |
|---|---|
| Subpath | M08-E |
| Production | `_check_launch_budget`, `launch_broker`, `NativeCustodySession.stop`, `_CustodyContext.publish_cleanup_deadline` |
| Event | The launch is paused in its preparation, **before** the creation of the process; the **public stop** of the round publishes the cleanup deadline while the absolute lease stays in the future; the launch resumes.  In the second direction the published cleanup of the round expired while the absolute lease is still in the future. |
| Oracle | No process is created (`popen == 0`), no executable is hashed and no channel is built; the launch is refused with a named startup code. |
| Negative | The absolute deadline alone is never the authority; the stop, the cancel and the unknown state of the round are honoured; no platform flag and no `PROVEN` flag is set to manufacture an acceptance. |
| Returned state | The number of the created processes and the failures of the session. |
| Salvage | The table of the launcher is drained; the refused launch keeps no resource. |
| Nodes | `test_n07_r13_...` |

## N10-R02 — the claim of the recovery and the handover

| Field | Value |
|---|---|
| Subpath | the M05 sub-scenario of the birth query and the recovery |
| Production | `WindowsApi.create_process_suspended`, `WindowsApi._process_creation_time`, `WindowsApi._decide_entries`, `WindowsApi.release_retained`, `WindowsApi.handover` |
| Event | The birth query of the created process blocks; the recovery of the façade claims the original entries of the process and of its thread while the creation is in flight; the creation returns. |
| Oracle | A stale claimed handle is never delivered to the core: the creation refuses with `BROKER_PROCESS_HANDOVER_REFUSED` and there is exactly **one** closer of the original handle of the process and of the original handle of its thread. |
| Negative | The setup of the group may not raise before the race: the birth query writes through the **structure** behind the reference (`structure_of`), never on the reference itself. |
| Returned state | The code of the refusal, the ledger of the closes and the report of the recovery. |
| Salvage | The event that releases the birth query is set and the thread of the creation is joined with a bounded wait. |
| Nodes | `test_n10_r02_...` |

## N10-R04 — the aggregate finds the partial channel

| Field | Value |
|---|---|
| Subpath | the M07 sub-scenario of the partial channel |
| Production | `_adopt_broker_process`, `_LaunchAggregate.retain`/`release`, `StreamChannel.__init__`, `StreamChannel.close`, `_WindowsPipeEndpoint.close` |
| Event | The reader thread of the channel really starts and its start does not return; the channel is half built and the reader stays inside its read. |
| Oracle | The aggregate found the partial channel **through the aggregate**; the channel was coordinated **before** the process; the process of the launch was terminated and waited for by the aggregate that owns it; the raw files of the process were never closed by the process helper; the read end was never closed under a live reader; the incomplete start kept its owner and the **same** owner closed the read end exactly once. |
| Negative | The process helper never closes the files of a process whose channel took them; the termination and the wait of the process never happen a second time; the table of the launcher never resurrects a released item. |
| Returned state | The facts of the aggregate, the ledger of the closes of the two ends and the items of the table of the launcher. |
| Salvage | The event that releases the read is set and the thread of the reader is joined with a bounded wait. |
| Nodes | `test_n10_r04_...` |

## N10-R10 — the outcome of the generation wins over the cancellation (M09)

| Field | Value |
|---|---|
| Subpath | M09 (published generation error versus timeout) |
| Production | `_WindowsPipeWorker.outcome`/`published_before_cancel`/`_complete`, `_WindowsPipeEndpoint._await`/`_raise_cancellation`/`_parallel_timeout`, `BrokerProcess._keep_reader_error_history`, `NativeCustodySession.stop` |
| Event | A real ordinary fault is published for the **current** generation of the read of the real chain; the effective timeout of the round arrives **before** the endpoint consumes the outcome; the coordination of the round is a confirmed one in the first subcase and a failed one in the second. |
| Oracle | The **exact original error object** and its code are the error of the round; the timeout and the failure of the coordination are **parallel** facts (`lvw_parallel_timeout`, with the name of the coordination error when it failed) and they never replace the published failure; the history of the error keeps it across the channel, the handle of the broker and the **two public stops** of the round; the round stays `UNKNOWN_RETAINED`. |
| Negative | A cancellation may never rewrite a published failure; a generic `outcome_published` event may never be taken for the fault of the generation; the generation is never a hard coded number; no expected phase is synthesized. |
| Returned state | The outcome of the generation (error, error object, sequence, generation), the parallel facts of the error, the facts of the close of the broker and the evidence of the two stops. |
| Salvage | The event that holds the worker is set and the worker is joined with a bounded wait; the round is stopped in every case. |
| Nodes | `test_n10_r10_...` (the cancellation after the publication, the coordination of the cancellation and the **two** dynamic subcases of the timeout after the publication) |

## The obligations that stay closed and untouched

M05 (the transfer of the pipes and the direct cleanup of a failed creation),
M09 (the original error selection and the overflow schedules of N10-R11), m03
(the live predicate of the pending resources), M06 (the common notification of
a confirmed close) and M03 (the confirmed exit safety) are **not** touched by
this batch.  Their static dispositions stay as they were and their dynamic
status stays `NOT_RUN` until the batch of the root runs.
