# N1 correction 14 — the actual outcome of the frozen batch

Candidate `63b490ae8b5678113fc13ed16fb2a8a54e5ca39c` (the product of the
correction 14, the commit of the static delivery).  Root plan
`native-custody-correction-14/validation-plan-01/plan.json` SHA256
`05ef1549f42bd34d7759959c5409000b9dc1b8344e9d296351a2a213edb409fb`,
root ACK `ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH` (`ack.json` SHA256
`cd612a883e78fead7b0d2d37ef1afa70612af5014e7542627a481e88962ed885`).

**This is the outcome of one finite batch.  It is NOT a Stage PASS, it is
not a product acceptance and it is not a native proof.**  The Majors of the
production stay source-closed (F0/M0/m0, independent production review 02
of the correction 13); this batch supplies the actual fixture, event and
cleanup evidence, and the **independent evidence review** of that evidence
still belongs to the gate owner.  No repair, no rerun and no self repair
was performed: the candidate and every artefact of the batch are preserved
exactly as they are.

## 1. The three commands

Each command was executed **exactly once** with the absolute argv, the cwd
and the per-command environment of the plan of the root.  No wrapper, no
extra test, no retry, no fourth command.

| # | Label | Exit | Wall |
|---|---|---|---|
| 1 | counter-absence-before | 0 | 0.037 s |
| 2 | guarded-validation | 0 | 35.720 s (the runner: 35.487 s; the guard: 35.647 s) |
| 3 | counter-absence-after | 0 | 0.031 s |

The environment of the three commands is exactly the bound environment of
the plan: `LVW_N1_F5_EVIDENCE_DIR` names the **new**
`implementation-native-custody-correction-14/f5-evidence` directory and
`PYTHONDONTWRITEBYTECODE=1`.  The raw stdout and stderr of every command
are in this directory (`*.stdout.log`, `*.stderr.log`; the three stderr
logs are empty) and their digests are in `outer-execution.json`.

## 2. The batch

| Fact | Value |
|---|---|
| collected / selected | 189 / 189 — the collected order is **identical** to the frozen list |
| call / pass / fail / skip | 189 / 189 / **0** / **0** |
| functional pass (the two integrity-only nodes excluded) | 187 |
| pytest exit | 0 |
| cleanup proven for the batch | **true** |
| threads before / after | `["MainThread"]` / `["MainThread"]` |
| file descriptors before / after | the same three rows with the same (dev, ino, mode); `new_or_reused_fds` is empty; no unknown entry; fd 3 is filtered (EBADF) in both observations |
| stdlib preload | exactly one `ctypes.dlopen(None)`, the window **CLOSED** before the candidate and before pytest |
| guard | precedes the candidate and pytest; the eight self-test denials fired; `runtime_denials` is **empty** |
| duration of the batch | 35.487 s of the 300 s of the plan (one batch, `batches_max` 1) |

The runner wrote its receipt (`native-custody-correction-03.receipt.json`,
SHA256 in `outer-execution.json`) and the guard wrote its document
(`native-custody-correction-14.guard.json`).  The 60 source pins, the 223
named dependencies, the three stdlib pins and the three trusted tools were
verified by the runner itself before the candidate was imported; no
`PIN_DRIFT` was raised.

## 3. The counter

The parent and the counter were **MISSING (errno 2)** in the observation
before the batch and in the observation after it.  The content was never
read, nothing was created, written, reset or refunded and the expired
grant was not revived.  The historical continuity stays
`UNAVAILABLE_NOT_PROVEN`: two exact metadata observations prove the
continued absence only.

## 4. The five nodes that failed in the batch of the correction 13

All five now pass and each of them leaves **real** evidence on the disk.

### `tools/test_v0_s3_native_custody_correction05.py::test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources` (F1)

The table of the launcher converged and the convergence performed **zero**
primitive work.  The three scenarios of the group wrote six new phase
documents (`n05-r10-<scenario>-empty-owner.json` and
`n05-r10-<scenario>-converge.json`).  The empty owner of the
`success-then-handle` scenario is proven: the aggregate has
`process_is_none`, `channel_is_none`, no raw stream, no worker and no
endpoint; both original files are closed **and** confirmed by the progress
record of the owner; the original HANDLE is closed exactly once
(`handle_attempts` 2, `handle_closed` 1) and the process was terminated
and waited exactly once.  The convergence then leaves the table empty
(`owned: []`, `released: []`, `retained: []`) with **unchanged** counters
(`stdin_attempts` 1, `stdout_attempts` 2, `handle_attempts` 2,
`handle_closed` 1, `terminated` 1, `waited` 1).

### `tools/test_v0_s3_native_custody_correction07.py::test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed` (F2)

The boundary of the group really ran: the new phase document
`f5-r02-millisecond-floor-core.json` names the four cases of the core
adapter.  The requested argument is 0, 0, 1 and 1 for the remainders 0,
0.0002, 0.001 and 0.0011; the zero and the below-unit remainder perform
**no** primitive call at all and the two positive remainders ask for
exactly one millisecond.  The exit of the process is never inferred from a
requested zero (`exited: false` for the first two cases).

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer` (F3)

The parent pump of the round was **alive** and it performed a real
admission.  `n10-r07-pump-current-minimum.json` names the requested
argument of the original queue method of the channel
(`0.049999999999954525`), the requested argument of the original reply
event (`0.049999999999954525`) and the **actual remaining of the round at
the admission** (`0.049999999999954525`, the published cleanup deadline
`1000.05` of the original context minus the clock of the round).  The
pump has no error and the session is `RUNNING`: the round really started.
The zero expiry stays a second, distinct schedule:
`n10-r07-pump-zero-expiry.json` names the queue wait `0.0`, the reply wait
`0.0` and `pump_finished: true`.

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread` (F4)

The never-started object is separated from the active interrupted start:
`n10-r09-never-started.json` names `owner_started: false`, `ident: null`,
`alive: false`, `settle: false` and `in_flight: false`.  The owner of the
step is never released and the unconditional bounded join of every thread
that really started is unchanged.

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation` (F5)

The failed coordination now has a published fault at its selection point:
`n10-r10-timeout-failed.json` names `published_before_cancel_return:
true`, the generation `3`, the original `RuntimeError` object and the
parallel fact `{code: BROKER_PIPE_TIMEOUT, generation: 3, sequence: 4,
cancel_sequence: 3, coordination_error: "BrokerError"}`.  The real bounded
join of the coordination still failed and the coordination error stays a
**parallel** fact of the original error of the round.

## 5. The three schedules of M09

| Schedule | Status | Evidence |
|---|---|---|
| r10-timeout-confirmed (a confirmed coordination) | **REAL EVIDENCE** | `n10-r10-timeout-confirmed.json` (parallel timeout, `coordination_error: null`) and its two stop documents |
| r10-timeout-failed (a failed coordination) | **REAL EVIDENCE** | `n10-r10-timeout-failed.json` (parallel timeout, `coordination_error: "BrokerError"`, `published_before_cancel_return: true`) and its two stop documents |
| r10-published-before-timeout (the required order) | **REAL EVIDENCE** | `n10-r10-published-before-timeout.json`: the trace names `GATE_ENTERED` -> `FAULT_PUBLISHED` (clock 1000.0) -> `TIMEOUT_ARRIVED` (clock 1001.0) -> `RELEASED` -> `OUTCOME_CONSUMED` |

All three schedules are driven apart from each other and none of them is
`NOT_RUN`.

## 6. The phase statuses

Every phase document that the failed batch of the correction 13 produced
is present again (**74** of them) and **19** phases that the failed batch
never reached are present too (the three M09 schedules and their stop
documents, the zero expiry and the dispatch phases of N10-R07, the child
phase, the never-started phase of N10-R09, the empty-owner and convergence
phases of the three N05-R10 scenarios and the core boundary of N07-R02).
**93** phase documents are on the disk, **none** is missing and **no** phase
is `NOT_RUN`.  Every document was written **before** the assertions of its
phase and every value in it is a value that the production returned.

## 7. What is not claimed

* No Stage PASS, no product acceptance, no native proof and no human
  signature.  `native_execution`, `native_cleanup`, `gpu_released`,
  `port_released`, `sampler`, `parent_crash_recovery` and
  `windows_stdin_eof` stay `NOT_PROVEN`.
* No Major is closed by this batch: the Majors of the production stay
  source-closed (F0/M0/m0) and the **independent evidence review** of this
  batch is still required.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`.
* The failed candidate `b5e92af` and every artefact of the batch of the
  correction 13 are preserved; there was no repair, no rerun and no self
  repair.  The candidate of this batch, `63b490a`, and every artefact of
  this batch are preserved as they are.
