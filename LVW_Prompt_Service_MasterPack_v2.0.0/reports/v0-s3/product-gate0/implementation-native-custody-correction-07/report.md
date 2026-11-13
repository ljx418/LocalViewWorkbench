# N1 correction 07: the implementation of the lifecycle of the six majors, pending the frozen batch and the new independent review

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate: `S3_P4_N1_CORRECTION_07_LIFECYCLE`.

Candidate (the sources): `23e27898253683164e7cb2918661b54258a29ce0`.
The candidate of the implementation of the six majors is its ancestor
`21cadf9cd5ecd9b5b84e9bda01ac0ca0acbfb6a0`; the difference between the two
is the preflight correction of the root and nothing else.
Baseline candidate (the reviewed one): `4287090b464d16f398b92797d8f5595359fcb442`.
Evidence of the predecessor: `e03648631ed855bcb89245b07f698386859a62a4`.
Root package: `reports/v0-s3/product-gate0/native-custody-correction-07`
(`contract.md`, `decision.json`, `regression-obligations.json`,
`received-review/review.md`).
Root preflight decision: `reports/v0-s3/product-gate0/native-custody-correction-07/preflight-correction-01/decision.json`
(`NO_DYNAMIC_ACK_STATIC_TEST_PREFLIGHT_CORRECTION_ONLY`).
Parent packages: `native-custody-correction-05` (24 frozen groups) and
`native-custody-correction-03` (16 frozen groups), inherited unchanged.

**The state of the six majors.**  The isolated review of the root keeps M03,
M05, M06, M07, M08 and M09 **open**.  This delivery implements the design
decision of the root for the six of them and it delivers the 18 frozen groups
of the new module, but **it closes nothing by itself**: the six majors stay
open until the frozen batch of the root has run and a **new** independent
review has judged the result.  The wording of this report, of the plan request
and of the commit messages never claims the closure of a major.

This delivery claims **READY_FOR_REVIEW**.  It claims **not** Stage PASS, not a
native execution, not a native cleanup, not a released GPU, not a released port,
not a sampler, not a parent crash recovery, not a Windows stdin EOF, not an
admission and not a product gate 0.  Nothing of this delivery was executed: the
candidate was **not** imported, **not** collected, **not** run by pytest and no
dynamic probe of any kind was made.  The whole delivery is a static
implementation and a static self-review.

## 1. What was read

The root package of the correction 07 was read in full before the first edit:
`contract.md`, `decision.json`, `regression-obligations.json` (the 18 frozen
groups) and `received-review/review.md` (the six majors of the isolated review).
The governance layer was read before the sources: `AGENTS.md`,
`.agent-governance/README.md`, `plans/execution-control.json` and the execution
index `docs/24_EXECUTION_MASTER_PLAN.md`.

The five allowed sources and the two inherited test modules were read in full.
The predecessor candidate was **not** changed and the passed batch of the
correction 06 was **not** reproduced: the six majors are read from the frozen
review of the root and they are corrected statically.

## 2. The three ordered workpacks of this delivery

The contract asks for **three ordered workpacks of the same stage**, each with a
static receipt of what it changed and what it risks.  They were executed in this
order and they are separated in the sources as well.

### 2.1 Workpack A — the handover of a resource, the cancellation and the facts of a cleanup

* `tools/v0_s3_native_broker.py`
  * `WindowsApi` gained the **one lock of the holding table** and the
    **atomic handover** (`handover`, `handovers`, `forget_handle`): the receiver
    registers a handle and the façade forgets it under one lock, so that a
    handle never has two independent owners and never has none.
  * `WindowsApi._confirm_process_exit` is the one place that decides whether
    the exit of a process was **confirmed**.  `_release_created` and
    `release_retained` keep the **control handle of a process** whose exit was
    not confirmed: the process may still be alive and the handle is the only
    thing that may stop it.  The thread handle is independent of the exit and it
    is closed on its own.
  * `WindowsApi.release_retained` publishes **one** recovery deadline: a second
    recovery reuses it and never opens a new budget.
  * `WindowsApi.create_pipe` cleans the two ends **independently**, propagates
    the cancellation and keeps the primary error reachable next to it.
  * `WindowsApi.create_process_suspended` uploads the cancellation object of the
    release after every safe step and keeps the primary error.
  * `_PendingResources` carries the **owner object** of a handle and the pending
    pass asks the owner before it closes a handle (`protect`).
  * `BrokerCore` adopted the ends of a pipe from the façade in one step
    (`_adopt_from_api`), protected the read end of a live reader in every
    branch (`_close_one_reader`, `_pending_handle_in_use`), propagated a
    cancellation of a wait and of an exit code (`_wait_one_process`) and
    synchronised the retained resources with a confirmed close (`_close_handle`,
    `_release_resource`).
* `tools/v0_s3_native_custody.py`
  * the close of the round owns **one generation** with **one event**
    (`_close_generation`, `_recover_close`, `_finish_close`, `_await_close`),
    the state of the **start** of the closer is explicit
    (`_closer_start_state`, `_closer_threads`) and the **real** exit of the
    closer is separated from the end of its attempt (`_await_closer_exit`,
    `_join_one_closer`).
  * every exit of the **public stop** coordinates the current owner and the
    real closer (`stop`).

**The risk of this workpack** is the recovery path: a handle that is kept is a
handle that the batch has to release.  The salvage of the test owner is
therefore explicit in every group and the state of the resources is recorded
before the salvage.

### 2.2 Workpack B — the startup, the endpoint, the worker and the one context

* `tools/v0_s3_native_broker.py`
  * `_WindowsPipeWorker.run` performs the **check of the cancellation and the
    publication of the intent to enter the operation under one lock**: the
    interleaving between them is impossible and not improbable.
  * `_WindowsPipeWorker.request_cancel` really **repeats** the cancellation of
    the operating system: it never waits on the stop event that it set itself
    and it never releases itself with the done of an **older** generation.
  * `_WindowsPipeWorker.join_bounded` never pretends that a thread that was
    never started ended.
  * `_WindowsPipeEndpoint` owns its worker **before** the start of the thread,
    reads the **current** remaining budget instead of a fixed five seconds and
    reads the **latest** effective deadline for every segment of a partial
    write (`_current_write_deadline`).
  * the endpoint and the channel carry the **one context** of the round
    (`_RoundContext.remaining_absolute`, `bind_context`); the production entry
    (`main`) hands the context of the core to the transport of the channel.
  * `BrokerCore.arm` and `BrokerCore._launch_role` check the shared budget
    **before and after** every side effect, the second pipe of a role included.
  * `_StartupOwner.settle` and `BrokerLoop._run_startup` separate the end of the
    **attempt** of a step from the end of its **thread**, and the release of the
    owner happens only after a bounded join that never publishes the cleanup
    deadline of the round.

**The risk of this workpack** is the budget: a layer that keeps a deadline of
its own would shorten the round.  The settle of the startup is bounded by the
**remaining** of the absolute deadline of the round and it never publishes the
cleanup deadline.

### 2.3 Workpack C — the end to end recovery, the wait per generation and the real composition

* `tools/v0_s3_native_broker.py`
  * `BrokerProcess.close` does not skip an unfinished item of the low level
    because a close **returned**: `_channel_complete` decides and the channel is
    coordinated again when it did not confirm every item.
  * `BrokerProcess._release_process_handle` closes the original handle of the
    process **only** when its exit was confirmed.
  * `StreamChannel.close` reports the **real** facts of its reader endpoint.
  * `_WindowsPipeEndpoint.close` **recomputes** the state of its workers on
    every close and a closed file never locks the recovery of the handle of a
    thread.
  * `_LauncherCustody`, `_terminate_and_close_process`, `_adopt_broker_process`
    and `launch_broker`: the process is registered with the launcher from the
    moment of its creation, the channel is closed **through the channel** and
    never by closing the files of the process, the recovery uses the **same**
    absolute deadline and the original handle of the process is closed
    explicitly on Windows after the confirmed exit.

**The risk of this workpack** is the double close: a resource that was really
closed is never closed twice and the retained tables converge.  The
`gap-closure-matrix` below names the negative case of every row.

## 3. The gap closure matrix of the 18 frozen groups

Every row names the position of the isolated review, the **real** owner that
carries the fix, the new place of the source, the entry that drives it, the
negative case, the fact that the product returns with and the recovery entry.
The column **carried by** names the owner of the row; it does not claim that
the major is closed.

| # | Group | Original position of the review | Real owner that carries it | New source | Actual entry | Negative | Returned fact | Recovery entry |
|---|---|---|---|---|---|---|---|---|
| 1 | N07-R01 | M03: the control handle of a process was closed and forgotten although the exit was not confirmed | `WindowsApi` owns the control handle of a process until its exit is confirmed | `v0_s3_native_broker.py:900` `_confirm_process_exit`, `:1332` `_release_created` | `WindowsApi.create_process_suspended` with a failing birth, a refusing `TerminateProcess` and a timing out wait | a close that succeeds is never a proof that the process ended | the retained table of the façade names the **process** and only the process; the thread handle is closed; the primary error is the birth query and the secondary errors are named | `WindowsApi.release_retained` keeps the handle and reaches it again |
| 2 | N07-R02 | M03: the recovery closed the handle and forgot it after a wait that timed out | `WindowsApi` publishes one recovery deadline and confirms the exit before it releases | `v0_s3_native_broker.py:938` `release_retained`, `:876` `_recovery_timeout_ms` | the first and the second `WindowsApi.release_retained` of the same round | the deadline of the recovery is published once and it is never renewed | the first report names the handle as **not released**, the second names it as released and the table is empty | the second coordination of the same owner, inside the original deadline |
| 3 | N07-R03 | M05: the API table and the core named the two ends of a pipe at the same time | `WindowsApi.handover` and `BrokerCore._adopt_from_api` share one lock | `v0_s3_native_broker.py:855` `handover`, `:2059` `_adopt_from_api` | the production `WindowsApi` and the production `BrokerCore.launch` with the synthetic kernel 32 | the recovery of the façade never closes an end that a live reader reads from | the table of the façade is empty, the handovers are recorded and the core names the ends with their **reader object** as the owner | the core closes the ends with its own owner |
| 4 | N07-R04 | M05: a cancellation of the inherit flag skipped the safe close and the cancellation was swallowed | `WindowsApi.create_pipe` cleans the two ends independently and uploads the cancellation | `v0_s3_native_broker.py:1461` `create_pipe` | `WindowsApi.create_pipe` with a cancelled inherit flag and with a cancelled close of the read end | a cancellation never becomes a string and it never hides the primary error | both ends are closed, the end that is still open keeps its original reference and the primary error stays reachable as `lvw_primary` | the recovery of the façade closes the end that is still open |
| 5 | N07-R05 | M06: the read end of a live reader was closed by the pending pass after a cancelled wait | `BrokerCore` protects the read end by the **fact** of its owner | `v0_s3_native_broker.py:2485` `_close_one_reader`, `:2680` `_pending_handle_in_use` | `BrokerCore._close_readers` and `BrokerCore._close_pending` with a cancelled wait, a cancelled join and a coordination that fails | the pending pass never closes an end under a live owner | the read ends of the live readers are not closed, the other reader was cleaned up and the refused end is named `BROKER_PENDING_HANDLE_IN_USE` | the owner of the live reader releases it later |
| 6 | N07-R06 | M06: `_wait_one_process` turned a cancellation into an ordinary evidence | `BrokerCore` propagates the cancellation of a wait and of an exit code | `v0_s3_native_broker.py:2789` `_wait_one_process` | `BrokerCore.stop` with a cancelled `wait_process` and with a cancelled `exit_code` | the cancellation never becomes an ordinary evidence | the cancellation is the error that leaves the stop and it is named as a cancellation; the later processes were waited for | the handles of the round are released by their owner |
| 7 | N07-R07 | M06: the recovery of a record closed the handle but the retained table still named it | `BrokerCore._close_handle` releases the retained resource of a confirmed close | `v0_s3_native_broker.py:2415` `_close_handle`, `:2047` `_release_resource` | two `BrokerCore.stop` calls with a job handle whose close fails twice | a handle that was really closed is never named as a resource and it is never closed twice | the pending table, the record of the round and the retained resources agree with the fact of the close | the second stop of the round |
| 8 | N07-R08 | M07: the endpoint owned a worker only after its start returned | `_WindowsPipeEndpoint` registers the worker before the thread exists | `v0_s3_native_broker.py:3720` `_start`, `:3867` `close` | `_WindowsPipeEndpoint.read` with a start that raises before the thread and a start that raises after it | the file is never closed under a worker that is starting | the endpoint names the worker in both cases and the handle of the thread is closed before the file | the owner of the worker stops it later |
| 9 | N07-R09 | M07: the launcher closed the files of the process before it asked the channel | `_LauncherCustody` and `_adopt_broker_process` own the process and the channel | `v0_s3_native_broker.py:5050` `_LauncherCustody`, `:5145` `_terminate_and_close_process`, `:5208` `_adopt_broker_process`, `:5271` `launch_broker` | `_adopt_broker_process` with a failing construction of the handle of the broker | the launcher never closes the files that the channel owns; a pid is never used to find a process again | the channel was closed, the files of the process were not closed by the launcher and the process keeps its original reference | `release_retained_launches` names what it kept |
| 10 | N07-R10 | M07: a closer whose start did not return was taken for a thread that ended | `NativeCustodySession` keeps the state of the start of the closer and every closer thread | `v0_s3_native_custody.py:1430` `_start_bounded_close`, `:2145` `_await_closer_exit`, `:2189` `_join_one_closer` | `NativeCustodySession._start_bounded_close` with a start that raises before the thread | a join that raises because the thread was never started is never read as the end of the closer | the state of the start is `STARTING`, the owner of the closer is kept and the round stays unknown | a later attempt of the close is still possible |
| 11 | N07-R11 | M08: the cancellation of a worker was released by the stop event that it set itself and the done of an older generation | `_WindowsPipeWorker` repeats the cancellation and coordinates the generations | `v0_s3_native_broker.py:3488` `request_cancel`, `:3400` `run` | `_WindowsPipeWorker.request_cancel` with a `NOT_FOUND` of the operating system, driven by four explicit events | the retry never waits on the stop event of the worker and never uses the done of an older generation | the request was really repeated, the queued request was never performed and the completion of the older generation never released the waiter | the owner of the worker releases it |
| 12 | N07-R12 | M08: the partial write used the deadline that it had copied when it started | `_WindowsPipeEndpoint` reads the latest effective deadline for every segment | `v0_s3_native_broker.py:3822` `_current_write_deadline`, `:3842` `_write_block` | `_WindowsPipeEndpoint.write` with the deadline shortened after the first segment | the copy of the deadline of the first segment never lets a further segment through | the write ends with `BROKER_PIPE_TIMEOUT` and only the first segment was written | the owner of the endpoint closes it |
| 13 | N07-R13 | M08: the arm, the pipes, the endpoint and the launcher each had a budget of their own | the **one context** of the round carries the absolute deadline and the endpoint reads it | `v0_s3_native_broker.py:217` `remaining_absolute`, `:3693` `_effective_deadline`, `:2114` `arm`, `:2189` `_launch_role`, `:5145` `_terminate_and_close_process` | `BrokerCore.arm`, `BrokerCore.launch` and the recovery of the launcher around an expired deadline | an expired deadline never starts a new wait and never opens a budget of its own | nothing was created, the endpoint reads the deadline of the context and the recovery waits for the time that is left | the resources of the round are released by their owner |
| 14 | N07-R14 | M08: the event of the attempt released the in-flight owner before the thread ended | `_StartupOwner` and `BrokerLoop` separate the attempt from the thread | `v0_s3_native_broker.py:4326` `settle`, `:4508` `_run_startup`, `:4549` `_startup_settle_seconds` | `_StartupOwner.settle` and `BrokerLoop._run_startup` with a thread that needs one more tick | the event of the attempt never releases the owner | the owner is not released, the step is named `BROKER_STARTUP_IN_FLIGHT_RETAINED` and the cleanup deadline of the round was not published | the thread of the step ends and it may be released |
| 15 | N07-R15 | M09: the high level skipped the unfinished items of the low level because a close returned | `BrokerProcess` coordinates the items that the channel did not confirm | `v0_s3_native_broker.py:4932` `_channel_complete`, `:4952` `_close_channel`, `:4822` `close` | the **real** chain `NativeCustodySession` -> `BrokerProcess` -> `StreamChannel` -> `_WindowsPipeEndpoint` -> worker | a close that returned is never a release | the channel was closed twice, the handle of the thread of the worker was closed by the second attempt and the broker was released | the second public stop of the round |
| 16 | N07-R16 | M09: the retained workers were only appended and a closed file locked the recovery of the handle of a thread | `_WindowsPipeEndpoint` recomputes the state of its workers on every close | `v0_s3_native_broker.py:3867` `close`, `:3586` `join_bounded` | `_WindowsPipeEndpoint.close` twice with a failing close of the handle of the thread | the retained list never names the same worker twice | the first close keeps the worker, the second releases it and the facts are recomputed and not copied | the second close of the owner |
| 17 | N07-R17 | M09: the end of an older attempt released the waiter of the attempt that was running now | `NativeCustodySession` gives every attempt of the close its own event and generation | `v0_s3_native_custody.py:1956` `_recover_close`, `:2068` `_finish_close`, `:2084` `_await_close` | the recovery of the second generation with a competitor that arrives while it is in flight | the old event never releases the waiter of the new generation; the waiter never holds the lock while it waits | the generation of the close is named in the evidence and the deadline of the cleanup was never reset | the release of the second attempt ends the wait |
| 18 | N07-R18 | M09: the first public stop never joined the real closer | `NativeCustodySession.stop` coordinates the real closer on every exit | `v0_s3_native_custody.py:1764` `stop`, `:2145` `_await_closer_exit` | `NativeCustodySession.stop` while the closer published its attempt and is still alive | only a helper or a repeated stop never proves the coordination of the closer | the public stop waited for the real exit of the closer and the evidence names both facts | the closer ends and the round is closed |

## 4. The changes of the inherited frozen groups

The 24 frozen groups of the correction 05 and the 16 frozen groups of the
correction 03 keep their **identity**, their **order** and their **assertions**.
Exactly one assertion of one inherited group had to change, and the change is a
**strengthening** that the design decision of the root requires:

| Group | The change | The reason |
|---|---|---|
| `test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api` (`tools/test_v0_s3_native_custody_regressions.py`) | the assertion `all(entry['released'] for entry in report)` of the recovery was replaced by three exact assertions: the handle of the **thread** is released, the handle of the **process** is **not** released while its exit was not confirmed and it stays in the table of the façade, and a **later** recovery that confirms the exit releases it and empties the table. | The design decision of the root (contract, section "root详细设计裁决") says that the original control handle of a process may not be closed and forgotten while its exit is not confirmed, "even if `CloseHandle` succeeds".  The old assertion would have failed a product that obeys that rule.  The new assertions are **stronger**: they prove that the handle is kept, that it is reachable and that it is released by a confirmed exit.  No assertion was removed and the group did not change its identity, its order or its trigger. |

No other inherited group was changed.  The new file
`tools/test_v0_s3_native_custody_correction07.py` carries exactly **18** test
functions, one per frozen group, and it adds no fixture to an inherited module.

## 5. The preflight correction of the root

The root refused the dynamic batch of the correction 07 with the decision
`NO_DYNAMIC_ACK_STATIC_TEST_PREFLIGHT_CORRECTION_ONLY`
(`native-custody-correction-07/preflight-correction-01/decision.json`).  The
refusal is an executability review of the root and **not** a platform approval
refusal; no new human approval is requested.  The root authorised **no
production edit** and it froze the 175 node ids and their order.

The root found four defects of the preparation of the tests.  All of them are
in the **new** test module and all of them are corrected there; the production
sources of the candidate keep their bytes and the other test modules keep
their bytes.

| The issue of the root | The correction | Why the old group was not executable |
|---|---|---|
| N07-R18: the session was built with the default plan of the frozen fixture, whose lease of `100000` is expired under the wall clock of the host, so the session refused the round before it ever reached the window of the closer. | The group now builds the session with a plan whose lease is live (`_live_plan_document`) and with a controlled clock, and it asserts that the round really runs (`session.state == 'RUNNING'`) and that the closer is really alive when the public stop arrives. | The check of the lease was **not** relaxed: the plan is a valid one, the refusal of an expired plan is untouched and the group would have failed before it reached its own oracle. |
| N07-R18: the release of the closer was driven by a fixed sleep of half a second and by a join of two tenths, so the check depended on the scheduling. | The group now publishes an **explicit event** when the public stop enters the wait for the real closer (`announced_await`), it waits for that event, it checks that the public stop is still running and it only then lets the owner of the round release the closer. | The old group could pass or fail with the speed of the host.  Every wait of the new group is bounded and the salvage of the `finally` is bounded. |
| N07-R15: the channel of the round was built before the frames of the round were published, so the reader of the channel could block on a frame that was never published. | The whole **real** chain is now built inside the launcher and in the order of the production launcher: the frames that match the nonce of the round are published first, then the endpoints, then the channel and then the handle of the broker.  The reader waits for an explicit and bounded notification of the stop of the round. | The old group could block in the handshake of the real chain until the deadline of the round.  The group still drives the real chain and it did **not** fall back on the stand-in of the peer. |
| N07-R11: the group polled a list with sleeps instead of forcing the window of the cancellation. | The group now drives the real worker with four explicit events: the worker entered the operation, the operation may enter the system call, the cancellation of the round was issued and the queued request would have entered the operation.  It proves that the request of the operating system was really repeated, that the completion of the older generation never released the waiter and that the queued request was never performed. | The old group proved nothing about the window itself.  The source check of the critical section stays as the **auxiliary** proof of the group and it is no longer its only oracle. |

The root also required that the wording of this report and of the plan request
claims the **implementation** and not the closure of the six majors, that the
numbers of the plan request are the machine values of the JSON and that no
observation of a batch is written before the batch ran.  Section 0 of this
report, the title and the `claim_limit` of the plan request carry that
correction, and the report of the batch is the only place where an observation
of the guard may be written.

## 6. The static self-review

The static review of this delivery is a source review.  It is **not** a
measurement and it is **not** a native claim.

* Both changed sources and the three test modules were parsed with the
  abstract syntax tree of the host.  The parse succeeded for every file.
* A static name check of the six files (the module level names, the local
  names, the arguments, the comprehension variables, the exception names and
  the builtins) reports **no undefined name** in any file.
* The new test module was checked to carry exactly **18** test functions with
  the names `test_n07_r01_...` to `test_n07_r18_...`.
* The new test module contains **no** `time.sleep` and **no** polling loop:
  every wait of the 18 groups is an event wait or a bounded join of the
  production code.
* The interleaving of the worker of an endpoint is proved by the **behaviour**
  of the real worker and it is backed by the **source**: the check of the
  cancellation and the publication of the intent to enter the operation are
  asserted to be inside **one** critical section of the worker
  (`ast.unparse` of the `with self._condition:` block of
  `_WindowsPipeWorker.run`).  The source check is the auxiliary proof of the
  group N07-R11 and not its oracle.
* Every group of the new module drives the **production** entry and records the
  state of the resources **before** the salvage of the test owner.

What this delivery does **not** claim and what it did **not** do:

* the candidate was **not** imported, **not** collected and **not** run;
* no pytest, no runner, no guard and no dynamic probe of any kind was
  executed;
* no Windows API, no job object, no process, no service, no socket, no
  database, no network, no download, no media and no GPU was touched;
* the budget ledger and the shared counter were **not** read, **not** written
  and **not** reset;
* no agent was derived and no owner of another round was changed;
* the native claims of the package stay `NOT_PROVEN`.

## 7. The ten fields

* **Current coordinate**: R1 / WP-R1-U3 / RUNNING; the blocking gate of the
  round is `S3_P4_N1_CORRECTION_07_LIFECYCLE`.
* **What this batch completes**: the static implementation of the six majors
  M03, M05, M06, M07, M08 and M09 of the correction 07 and the 18 frozen
  groups of its new module, and the preflight correction of the root.
* **The last passed gate**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`
  (candidate `621b1bf`), unchanged by this delivery.
* **The position in the global route**: V0-S0 1/2, V0-S1 5/5, R0 1/2, R1a 5/5,
  V0-S2 7/8, V0-S3 0/6, R1 0/4, V1-M1 0/3, R2 0/4, R3 (V2) 0/4, R4 (V2) 0/4,
  R5a (V3) 0/4, R5b (V3) 0/4, R5c (V3) 0/4.
* **The remaining work**: the frozen batch of the root, the isolated review,
  the human signature, the native Windows run, I24, the twelve product cases
  and A06.  The N2 work is not started.
* **The next owner**: the gate owner of the root and the independent review.
* **The required authorization**: the static implementation of this delivery is
  the work of the frozen workpack.  The **dynamic** execution is not authorized
  and it is requested from the root by the finite plan of the delivery.
* **The evidence directory**: `reports/v0-s3/product-gate0/implementation-native-custody-correction-07/`.
* **The exact reason of the stop**: the static implementation, the static
  self-review and the preflight correction of the root are complete.  No
  dynamic execution was performed, no ACK was requested and no rerun, no
  wrapper, no self repair and no overwrite of a candidate happened.
* **The claims**: READY_FOR_REVIEW.  Not Stage PASS.  The six majors of the
  independent review stay **open**.

## 8. The frozen plan that is asked of the root

The delivery asks for exactly **one** finite dynamic batch and it is described
in the plan request of this directory.  It carries the candidate SHA, the pins
of the sources and of the tools, the ordered and frozen set of the node ids
(the 157 inherited ones in their original order and the 18 new ones), the guard
and the runner of the root, the absolute argv and the absolute cwd, a single
batch of at most 300 seconds, the raw output of every node, the exit code, the
real identity of the file descriptors and the state of every thread before and
after the batch.

The **tools** of the next batch are the ones of the **new** directory
`native-custody-correction-07/validation-plan-01` that the root places with
the same bytes as the tools of the correction 05.  The plan request points at
that directory and it never points at the plan of the correction 05, which is
never overwritten and never executed again.

The boundary of the batch is the one of the predecessor: the guard precedes the
candidate and pytest, the only permitted preload is the single
`ctypes.dlopen(None)` of the trusted standard library and it is closed before
the candidate, the counter is read once before and once after the batch and it
is neither written, nor reset, nor refunded, nor revived, and the FIRST
approval that is refused or that times out stops the batch without a wrapper.
The runtime denials of the guard, the identity of the file descriptors and the
state of the threads are **expectations** of the batch: they are written in
the report of the batch and nowhere else, because they were not observed.

## 9. The files of this delivery

* `tools/v0_s3_native_broker.py` (changed) — the broker of the round.
* `tools/v0_s3_native_custody.py` (changed) — the parent side of the round.
* `tools/test_v0_s3_native_custody_regressions.py` (changed) — the **one**
  strengthened assertion of the inherited group N03-R01.
* `tools/test_v0_s3_native_custody_correction07.py` (new) — the 18 frozen groups.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-07/report.md`
  (new) — this report.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-07/execution-plan.request.json`
  (new) — the frozen plan request.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-07/SHA256SUMS`
  (new) — the pins of the delivery.

No controller, no worker, no runtime, no driver, no supervisor, no
authorization record, no public schema, no threshold, no control document, no
manifest and no historical evidence was changed.  The refusal points of the
native path are kept and the N2 work is not started.
