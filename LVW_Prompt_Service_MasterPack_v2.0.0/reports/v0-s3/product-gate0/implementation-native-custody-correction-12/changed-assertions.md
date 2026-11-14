# N1 correction12 — the changed assertions

Every row names the frozen node, the kind of the change, the assertion
**before** and the assertion **after**.  No node id, no order and no
denominator changed: the list of the 189 node ids was compared statically
against the frozen list of the plan of the root and the two lists are
identical.

`ADDED` — a new assertion of an existing node.
`CHANGED` — an assertion of an existing node whose object or whose oracle
changed.
`REMOVED` — an assertion that this batch replaced by a stronger one.

## 1. The three observed test defects

### N10-R02 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive`

| Kind | Before | After |
|---|---|---|
| CHANGED | the scripted `GetProcessTimes` wrote `creation.dwLowDateTime` on the **reference** (`args[1]`), which raises `AttributeError` before the race is reached | the scripted `GetProcessTimes` writes through the **structure** behind the reference: `structure_of(args[1])` |
| CHANGED | the shared default of `SyntheticKernel32` wrote `args[1]._obj` directly | the shared default writes `structure_of(args[1])` — the same helper, so that a typed pointer that is already the structure is handled as well |
| ADDED | — | the helper `structure_of` is documented: the reference supports neither the assignment nor the reading of a field and the structure is the `_obj` of the reference |
| KEPT | the refusal code `BROKER_PROCESS_HANDOVER_REFUSED`, the single closer of the original handle of the process and of its thread, the event gated race | unchanged — they are now really exercised |

### N10-R04 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r04_the_launch_aggregate_finds_the_partial_channel`

| Kind | Before | After |
|---|---|---|
| CHANGED | the node built a `StreamChannel` directly; the **original process was never bound to the aggregate**, so the release coordinated `self.process`, which was `None`, and `process.terminated == 1` could not hold | the node drives the **production adoption** `_adopt_broker_process(process, channel_factory=..., aggregate=aggregate, custody=custody)`: the process is bound to the aggregate and registered with the table of the launcher **before** the partial channel is built |
| ADDED | — | the order of the coordination is `channel-write`, `terminate`, `wait`: the channel of the launch is coordinated **before** the process |
| ADDED | — | `process.closed == []`: the raw files of the process are never closed by the process helper |
| ADDED | — | `read_file.closes == 0` while the reader is alive: the read end is never closed under a live reader |
| ADDED | — | the incomplete start keeps its owner in the aggregate and in the table of the launcher |
| ADDED | — | the **same** owner closes the read end exactly once (`read_file.closes == 1`, `write_file.closes == 1`) and the table of the launcher is empty at the end |
| ADDED | — | the termination, the wait and the close of the original handle of the process happen **exactly once** |
| REMOVED | — | the old assertion `read_file.closes == 1` after the **first** release: the read end is not closed while the reader is alive |

### N10-R10 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`

| Kind | Before | After |
|---|---|---|
| CHANGED | `outcome = reader.outcome(1)` — the **hard coded** generation 1, which is not the generation of the blocked read of the real chain | `generation = reader._submitted` at the moment the reader is really inside its read, and `outcome = reader.outcome(generation)` |
| ADDED | — | `outcome['generation'] == generation`: the outcome that is read belongs to the generation that was really in flight |
| CHANGED | the coordination subcase read `endpoint._reader.outcome(1)` | the coordination subcase reads `endpoint._reader.outcome(endpoint._reader._submitted)` |
| REMOVED | the auxiliary **static AST** proof of the ordering of `_await` (the count of `worker.outcome(generation)` and the positions of the timeout and of the coordination) | the static proof is **replaced** by the dynamic schedule below; it is no longer the evidence of the group |
| ADDED | — | the dynamic subcase `r10-timeout-confirmed`: a real ordinary fault is published for the current generation of the **real chain**, the effective timeout arrives **before** the endpoint consumes the outcome and a **confirmed** coordination preserves the exact original error object; the timeout is a parallel fact (`lvw_parallel_timeout`, `coordination_error is None`) |
| ADDED | — | the dynamic subcase `r10-timeout-failed`: the same schedule with a **failed** coordination; the original error object is still the error that leaves and the failure of the coordination is a parallel fact (`coordination_error == 'BrokerError'`) |
| ADDED | — | both dynamic subcases assert the history of the error across the channel and the handle of the broker, the **two public stops** of the round (`channel_reader_error == 'RuntimeError'`, the source `REPEATED_CLOSE`) and the state `UNKNOWN_RETAINED` |
| ADDED | — | the phase documents `r10-timeout-confirmed`, `r10-timeout-confirmed-first`, `r10-timeout-confirmed-second`, `r10-timeout-failed`, `r10-timeout-failed-first`, `r10-timeout-failed-second` |

## 2. M07-A — the executable recovery of an unresolved original raw stream

### N07-R09 — `tools/test_v0_s3_native_custody_correction07.py::test_n07_r09_the_launcher_keeps_the_owner_of_the_process_and_the_channel`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the production launch whose **hash is interrupted**: the process of the round keeps its owner in the table of the launcher |
| ADDED | — | the first release returns the **retained original reference** of the raw stream: `stdout.attempts == 1`, `stdout.confirmed == 0` and the table of the launcher names the stream |
| ADDED | — | the **same** owner retries it: `stdout.attempts == 2`, `stdout.confirmed == 1`, `stdout.closed is True` and the table of the launcher names the stream no more |
| ADDED | — | the launch owns the stream: `aggregate.raw_streams == ['stdout']` before the retry and `[]` after it |
| ADDED | — | the successful process and handle operations are never repeated: `terminated == 1`, `waited == 1` and the number of the closes of the original handle does not change |
| ADDED | — | the phase documents `r09-raw-stream-first` and `r09-raw-stream-second` |

### N05-R10 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources`

| Kind | Before | After |
|---|---|---|
| ADDED | — | a **failed** retry keeps the owner of the raw stream: `stdout.confirmed == 0` and the table of the launcher still names the stream |
| ADDED | — | the launch never forgets a raw stream that was not closed: `aggregate.raw_streams == ['stdout']` |

### N10-R05 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel`

| Kind | Before | After |
|---|---|---|
| ADDED | — | a **cancelled** retry: the original `KeyboardInterrupt` is the error that leaves and the stream keeps its owner (`stdout.confirmed == 0`, the table of the launcher still names the stream) |

## 3. M08-A — the current context at the actual worker dispatch

### N10-R07 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the dispatch of the worker consults the **current** original context: the request is really submitted, the dispatch is paused, the context is cancelled, the worker is released — the number of the real primitive calls is **zero** and the outcome of **that** generation carries `BROKER_PIPE_CANCELLED` |
| ADDED | — | the same schedule with an **expired published cleanup** of the round: the primitive calls are zero and the outcome carries `BROKER_PIPE_TIMEOUT` |
| ADDED | — | the await of the endpoint notices the cancellation of the **original** context: the error that leaves is `BROKER_PIPE_CANCELLED` and not a timeout |
| ADDED | — | the phase documents `r07-dispatch-cancel`, `r07-dispatch-expire` and `r07-await-context` |

## 4. M08-B — the current bound of the normal `BrokerProcess.close`

### N03-R08 — `tools/test_v0_s3_native_custody_regressions.py::test_n03_r08_the_cleanup_of_the_broker_uses_one_absolute_deadline`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the channel publishes a **shorter** cleanup deadline while it is closed: the wait of the process receives `0.5` (the new bound) and the retry receives `0.0` — the bound that was copied before the channel was closed is never used |
| KEPT | `waits[0][2] == 1.0` and `waits[1][2] == 0.0` of the original subcase (the shared five seconds of the original fixture) | unchanged |

## 5. M08-C — one current-context wait bound and no positive floor

### N10-R09 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the wait of the owner of a startup step is cropped to the current remaining: the first wait is the poll cap of the package and no wait ever exceeds the remaining of the round |
| ADDED | — | the phase document `r09-await-wait` |

### N05-R14 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the wait of the endpoint asks for the poll cap and is cropped to the remaining when the deadline of the round is tightened while the read runs |
| ADDED | — | the put of the reader of the channel asks for the wait of the package (0.5 s) and is cropped to the remaining (0.02 s) after the tightening |

### N03-R08 — `tools/test_v0_s3_native_custody_regressions.py::test_n03_r08_the_cleanup_of_the_broker_uses_one_absolute_deadline`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the read of the transport of the loop asks for the remaining (5 ms) and **not** for the positive floor of the package (10 ms) |

## 6. M08-D — a real join after an interrupted start

### N10-R09 — `tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`

| Kind | Before | After |
|---|---|---|
| ADDED | — | a start that raised **after** the thread of the step really came up: the facts of the thread decide (`owner._started is True`), the owner is **not** released (`loop._startup_in_flight is owner`, `owner.in_flight is True`) and a later settle of the **same** owner converges after the real exit of the thread |
| ADDED | — | a start that never came up stays **unknown**: `owner.settle(5.0) is False` and the owner is never released |
| ADDED | — | the phase document `r09-interrupted-start` |

## 7. M08-E — the launch honours the public stop and the published cleanup

### N07-R13 — `tools/test_v0_s3_native_custody_correction07.py::test_n07_r13_every_side_effect_checks_the_shared_context`

| Kind | Before | After |
|---|---|---|
| ADDED | — | the **public stop** of the round while the launch is paused in its preparation: no process is created (`popen == 0`) and the launch is refused with `BROKER_STARTUP_CANCELLED` |
| ADDED | — | a **published cleanup** of the round that expired while the absolute lease is still in the future: the launch is refused with `BROKER_STARTUP_DEADLINE_EXCEEDED` and no process is created |
| ADDED | — | the table of the launcher is clean again: the refused launch keeps no owner |
| ADDED | — | the phase documents `r13-launch-stop` and `r13-launch-cleanup` |

## 8. The diagnostics of the frozen nodes

| Kind | Before | After |
|---|---|---|
| CHANGED | `tools/test_v0_s3_native_custody_correction10.py`: the phase documents were written in `implementation-native-custody-correction-11/evidence` | they are written in `implementation-native-custody-correction-12/evidence`; the documents of the failed batch of the correction 11 stay where they are |
| CHANGED | `tools/test_v0_s3_native_custody_correction07.py`: the documents of the real chain were written in `implementation-native-custody-correction-11/f5-evidence` | they are written in `implementation-native-custody-correction-12/f5-evidence`; the documents of the failed batch of the correction 11 stay where they are |

## 9. The assertions that this batch did **not** touch

No assertion of the closed obligations of the correction 11 was weakened,
removed or relaxed: the M05 transfer and direct cleanup claims, the M09
original error selection, the m03 live predicate, the M06 identity
notification and the M03 confirmed exit safety keep their assertions and
their oracles.  No threshold, no schema, no protocol and no denominator moved.
