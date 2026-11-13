# N1 correction 05: the six open majors of the isolated review

Stage: R1.  Workpack: S3-P4-N1.  Gate: `S3_P4_N1_CORRECTION_05_SIX_MAJOR_CONSOLIDATED`.

Candidate: `0e83077321186b52c7e3826efbbf92c143737b0f`.  Baseline: `d751bced75cdc1d21cee072892860a7c4f8ac542`.
Evidence of the predecessor: `bc1a27d9d18faedc15797d3153cd0fe8a4cb3d8a`.
Root package: `reports/v0-s3/product-gate0/native-custody-correction-05`.

This delivery claims **READY_FOR_REVIEW**.  It claims **not** Stage PASS, not a native
execution, not a native cleanup, not a released GPU, not a released port, not a
sampler, not a parent crash recovery, not a Windows stdin EOF, not an admission and
not a product gate 0.

## 1. What was read

The root package was read in full before the first edit: `contract.md`,
`regression-obligations.json`, `root-decision.json` and `received-review/review.md`.
The governance layer was read before the sources: `AGENTS.md`,
`.agent-governance/anti-false-green.md`, `docs/24_EXECUTION_MASTER_PLAN.md` and
`plans/execution-control.json`.

The review accepted the frozen specification and left **six majors** open: M03, M05,
M06, M07, M08 and M09.  M04 and M11 stay closed, M01, M02, M10 and m01 stay closed.
The six majors are one lifecycle of the N1 and they were corrected here in two
ordered work packs inside the same frozen N1, the lower layer first.

## 2. The two work packs

### WP-A: the resources of the round and the context of the startup and of the cleanup

* **The owner of a resource from the moment of its creation.**  The null device of
  the child (`WindowsApi.create_process_suspended`) and the two ends of a pipe
  (`WindowsApi.create_pipe`) enter the holding table of the façade in the moment of
  their creation.  A handle that could not be closed keeps its **original**
  reference and its recovery entry point (`release_retained`).  The façade forgets a
  handle only after a confirmed close (`WindowsApi.close_handle`).
* **Independent finalizers.**  The deletion of the attribute list, the close of the
  null device, the birth query, the release of a created process, the wait of a
  process, the release of a record, the close of a reader and the close of the
  pending resources run on their own.  A cancellation in the middle of a cleanup
  never skips the cleanup that follows it: it is named as a cancellation
  (`'cancellation': True`) and it is raised after every safe step was executed.  The
  primary error of the round is never replaced by a later one.
* **The readers.**  A reader whose thread never started is never joined (the join of
  a thread that was not started is an error of the caller and not a fact of the
  round), and the read end of a reader that is still alive is never closed under it.
* **The background of the round.**  The state of every background thread is recorded
  while it is started: `STARTING`, `RUNNING` or `FAILED`.  A thread whose start did
  not return keeps its owner, is never joined and may only wind up.  A thread that
  really runs keeps the reference of the session even when its start raised; the
  local flag of the start never took it for a thread that never started.  A closer
  that could not be built or started is named, it does not latch the round for ever
  and the original broker stays recoverable through the public stop.
* **The launcher.**  A launch that could not be handed over keeps the original
  process, its handles, its pipes and its endpoint in the table of the launcher
  (`_LAUNCHER_CUSTODY`), with their original objects; the recovery entry point is
  finite and explicit (`release_retained_launches`).  No pid is ever used to find a
  process of the round again.

### WP-B: the session, the recovery and the budgets

* **One context of the round.**  `_CustodyContext` (parent) and `_RoundContext`
  (broker) hold the clock, the absolute deadline, the **one** cleanup deadline and
  the three one way latches (cancel, stop, unknown).  The cleanup deadline is
  published **once**, atomically, by the first caller that enters the cleanup, and
  every later caller reuses that very value.  Every layer of the round holds that
  one object and not a copy of a number.
* **The startup.**  The shared cancel and the shared deadline are checked before and
  after every create, every assign, every resume and every reader start, and before
  every role.  A role that is created after the deadline arrived is never assigned,
  never resumed and never followed by another role; the late resource is only
  cleaned up.  The supervision publishes the cancel of the round when the deadline
  arrived.  The settle of a startup step uses the shared cleanup deadline and no
  settle budget of its own.
* **The endpoint.**  An await that is already running reads the deadline that was
  tightened after it began.  The worker of an endpoint coordinates its submissions
  and its cancellation by the same generation; a request that is submitted after the
  cancellation is refused.  Every segment of a partial write checks the cancel flag
  and the deadline.  The handle of the thread of a worker that could not be closed
  keeps its owner.
* **The unknown state.**  The latch of the unknown state and the application of a
  state share one lock: a late reply never turns an unknown round into a running
  one.
* **The frame budget.**  The frames that the parent sends and the frames that it
  receives share one counter under one lock; the check and the commit are one
  atomic step.  The frames of the terminal exchange **consume** the reservation that
  was kept for them, on both sides of the channel, and a frame that is not terminal
  never borrows the reservation.
* **The release.**  The parent requires the strict facts of the close: the channel,
  the process and its original handle, the reader that really stopped without an
  error, the two ends that are closed and the original handles of the workers that
  are released.  An attempt that ended is not a release: the items that were not
  confirmed are coordinated again by the public stop of the round, inside the
  **original** deadline, and the broker process never closes the files of the
  channel behind the endpoint that owns them.

## 3. The 24 obligation groups and their owner

| Group | Major | The production owner that carries it | The node of the new module |
|---|---|---|---|
| R01 | M03 | `WindowsApi.create_process_suspended`, `WindowsApi.release_retained` | `test_n05_r01_the_null_device_has_an_owner_from_the_moment_of_its_creation` |
| R02 | M03 | `WindowsApi.create_process_suspended` | `test_n05_r02_a_cancellation_in_the_cleanup_never_skips_the_other_finalizers` |
| R03 | M05 | `WindowsApi.create_pipe` | `test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation` |
| R04 | M06 | `BrokerCore.stop`, `BrokerCore._close_handle` | `test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup` |
| R05 | M06 | `BrokerCore._wait_the_processes` | `test_n05_r05_one_process_never_skips_the_wait_of_the_next_one` |
| R06 | M06 | `BrokerCore._start_reader`, `BrokerCore._close_readers` | `test_n05_r06_a_reader_that_never_started_is_never_joined` |
| R07 | M07 | `NativeCustodySession._start_background_thread`, `._stop_background` | `test_n05_r07_a_background_start_that_did_not_return_keeps_its_owner` |
| R08 | M07 | `NativeCustodySession._start_background_thread` | `test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread` |
| R09 | M07 | `NativeCustodySession._start_bounded_close` | `test_n05_r09_a_closer_that_could_not_start_does_not_latch_the_round` |
| R10 | M07 | `_adopt_broker_process`, `release_retained_launches` | `test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources` |
| R11 | M08 | `BrokerCore.check_startup_budget`, `BrokerCore._launch_role` | `test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` |
| R12 | M08 | `NativeCustodySession._cleanup_deadline_for`, `BrokerCore.cleanup_deadline` | `test_n05_r12_the_cleanup_deadline_is_published_once_and_never_extended` |
| R13 | M08 | `BrokerCore._close_readers`, `BrokerCore._wait_timeout_ms` | `test_n05_r13_the_remaining_budget_is_recomputed_before_every_wait` |
| R14 | M08 | `_WindowsPipeEndpoint._await`, `.bind_deadline` | `test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline` |
| R15 | M08 | `_WindowsPipeWorker.submit`, `.request_cancel`, `.release_thread_handle` | `test_n05_r15_the_worker_coordinates_by_generation_and_keeps_its_handle` |
| R16 | M08 | `NativeCustodySession._apply_state`, `._latch_unknown_state` | `test_n05_r16_the_unknown_state_is_latched_atomically` |
| R17 | M08 | `NativeCustodySession._reserve_frame` | `test_n05_r17_the_frame_budget_has_one_owner_in_both_directions` |
| R18 | M08 | `NativeCustodySession._reserve_frame`, `BrokerLoop._check_frame_budget` | `test_n05_r18_the_terminal_exchange_consumes_its_reservation` |
| R19 | M09 | `NativeCustodySession.stop`, `._recover_close` | `test_n05_r19_the_unconfirmed_items_are_coordinated_again` |
| R20 | M09 | `_WindowsPipeEndpoint.close`, `_PosixPipeEndpoint.close` | `test_n05_r20_the_closed_fact_is_committed_only_when_it_is_confirmed` |
| R21 | M09 | `BrokerProcess.close` | `test_n05_r21_the_endpoint_is_the_only_owner_of_the_files_of_the_channel` |
| R22 | M09 | `NativeCustodySession._perform_close` | `test_n05_r22_the_strict_facts_of_the_close_are_required` |
| R23 | M09 | `NativeCustodySession._await_close`, `._closer_main` | `test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts` |
| R24 | compatibility | the validators of the plan, the declarations, the command of the sampler | `test_n05_r24_the_closed_items_and_the_frozen_groups_are_kept` |

Every group names in its docstring the obligation, the production entry, the
trigger, the oracle, the negative case, the state that the product returned with
and the salvage of the test owner.  The salvage of the test owner is always
explicit and bounded and it never changes the fact of the product.

## 4. The frozen denominator

The 133 frozen nodes keep their identity and their order.  The 24 new nodes are
appended after them and the order is binding.  The frozen plan is in
`execution-plan.request.json` of this directory:

* the candidate `0e83077321186b52c7e3826efbbf92c143737b0f` and its four source
  pins plus the new module;
* the same 223 named dependency pins and the same three stdlib pins, all verified
  against the files of this host before the request was written;
* the guard, the runner and the outer counter reader of the root, with the bytes of
  the frozen package of the correction 04;
* one batch of at most 300 seconds, the three absolute commands of the predecessor
  and the same counter policy (read once before and once after, never written,
  never reset, never refunded).

## 5. The change of the oracle of R14

The root approved the correction of the oracle of R14 in this package: a peer that
was not released is retried inside the original deadline of the cleanup and a close
that misses the facts of the reader, of the endpoints and of the workers is
refused.  The node of R14 keeps its name and its place in the order; its body now
drives the corrected oracle.  The positive stand-ins of the package now report the
facts that they really own instead of the three facts of the old oracle, and no
other case was weakened.

## 6. The execution boundary of this delivery

The implementation itself was static: the candidate was written, parsed with `ast`
and reviewed statically; the dependency, the stdlib and the guard pins were
verified by reading the bytes of the files.  There was **no** import of the
candidate, **no** collection, **no** pytest and **no** probe before the
acknowledgement of the root.  No real process, no GPU, no model, no service, no
media, no database, no socket, no network and no original ledger were touched.

The root acknowledged the plan (`msg_40e621f0f945`,
`ACK_ONE_FROZEN_157_NODE_OFFLINE_BATCH`) and the one frozen batch was executed
once, in the order of the three frozen commands, with their original argv and
their original cwd.  **The batch failed**: 157 collected, 151 passed, 6 failed,
pytest exit 1 and `cleanup_proven_for_batch` false.  There was no rerun, no
wrapper, no overwritten candidate and no self repair.

The evidence of the batch and the analysis of every one of the six failures are in
`attempt01/execution-report.md`.  Three of the six failures are defects of the
production code of the candidate and three are defects of the new test module.
The candidate is **not** a release and the six open majors of the review of the
predecessor are **not** closed by this batch.

## 7. The files of this delivery

* `tools/v0_s3_native_custody.py` — the parent side: the context of the round, the
  atomic cleanup deadline, the background records, the latch of the unknown state,
  the atomic frame budget, the strict facts of the release and the recovery entry.
* `tools/v0_s3_native_broker.py` — the broker side: the context of the round, the
  owners of the resources, the independent finalizers, the startup budget, the
  endpoint and the worker, the launcher custody.
* `tools/test_v0_s3_native_custody.py` — the facts of the stand-in of the broker.
* `tools/test_v0_s3_native_custody_regressions.py` — the facts of the stand-in of
  the peer and the corrected oracle of R14.
* `tools/test_v0_s3_native_custody_correction05.py` — the 24 new groups.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-05/` — this
  report and the plan request.

Nothing outside these files was changed.  The controller, the worker, the runtime,
the driver, the supervisor, the sampler, the authorization, the public schemas, the
quality thresholds, `control`, `MANIFEST` and every historical report are frozen and
untouched.
