# N1 correction 10: the six Major atomic gaps and the one context

**Stage** R1 / WP-R1-U3 / S3-P4-N1.  **Workpack** the one
implementation owner of the correction 10.  **Status** the static
implementation is complete; the six Majors stay **OPEN** and they need a
new independent review.

Inputs: production `66600a1`, tests `39f8037`, the one frozen batch of
the correction 09 (`a22267d`, 175 call / 174 PASS / 1 FAIL /
cleanup true) and the read only pre review
`received/production-review.md` (CHANGES_REQUIRED, Fatal 0, Major 6).
The failure of the correction 09 and its cause are quoted in
`received/failed-execution-report.md`: the reader of the chain published
the event that it was inside its read only **after** a bounded wait of
30 s, while the owner of the test waited 15 s for it.  Nothing of that
history is repeated here.

This document is the **static** delivery of the correction 10.  No
candidate was imported, collected or executed: the boundary is in the
last section.

## 1. The six Major atomic matrix

Every row names the sub gap of the pre review, the **real entry** that
carries it, the **lifetime** of the resource, the new source of the
correction, the new **combined negative** of the frozen regression and
the honest status.  A row that is not covered says so.

| Major | Sub gap of the pre review | Real entry | Lifetime of the resource | New source | New combined negative | Status |
|---|---|---|---|---|---|---|
| M03 | The Core closes the last control HANDLE of a process whose exit was not confirmed (B2839-2877, B2680-2700) | `BrokerCore._release_the_records`, `BrokerCore._process_closeable`, `_PendingResources.close_all`, `_PendingResources._is_closeable` | The control HANDLE of a process lives from `CreateProcess` until the **exit is confirmed**; a close that would succeed is never a proof of an exit | `v0_s3_native_broker.py`: the eligibility predicate of the pending entry (`closeable`), the skip of the process HANDLE in `_release_the_records`, the failure `BROKER_PROCESS_EXIT_NOT_CONFIRMED` | N10-R01: the wait does not confirm the exit, the close of the HANDLE would succeed; the close is never attempted, the record **and** the pending table keep the HANDLE, the same owner confirms the exit later and the HANDLE is closed exactly once | STATIC_IMPLEMENTED, pending the dynamic batch |
| M03 | A child that was never assigned to the job keeps the original control of the process (B2315-2322) | `BrokerCore._launch_role` -> `_terminate_owned` -> the record | The same: the HANDLE of a suspended child stays with the record of the round until the exit is confirmed | the record of the process carries the eligibility of its own control HANDLE; the pending entry of the process asks the **same** owner | N10-R01 covers the same owner and the same recovery; the suspended child of the assign failure is not a separate node of this correction and is **not** separately counted | STATIC_IMPLEMENTED, the assign failure itself stays covered by the old nodes of the correction 03 and 07 |
| M05 | The recovery of the API owner and the handover of the Core are two owners of one entry (B855-878, B964-995) | `WindowsApi.release_retained`, `WindowsApi.handover`, `WindowsApi._claim_entry`, `WindowsApi._owns_claim` | The entry of the holding table lives from the creation of the handle until a confirmed close; the ownership moves `API_OWNED -> RECOVERY_CLAIMED -> TRANSFER_PENDING -> TRANSFERRED` and never backwards | `v0_s3_native_broker.py`: the claim under the lock of the table, the verification of the claim before the close, the refusal of the handover of a claimed entry (`BROKER_HANDOVER_CLAIMED`), the blocking primitive **outside** of the lock | N10-R02: the recovery blocks inside the close of one end of a pipe, the handover of that end is refused and the end is never registered with a second owner, the handover of the other end succeeds while the recovery waits, and the recovery never closes an end that it handed over | STATIC_IMPLEMENTED, pending the dynamic batch |
| M06 | A pending close that succeeds does not notify the reader that owns the handle (B2724) | `BrokerCore._note_closed_handle`, `BrokerCore._close_handle`, `_PendingResources.close_all` | The handle of a reader lives from the creation of the pipe until its confirmed close; the owner of the handle learns the fact **once** | the one notification of the round: the job, the records, the **owner object** of the handle and the retained resources learn the same fact; the reader handle becomes `None` | N10-R03: the first close of the read end of a stopped reader fails, the pending pass closes it, the reader holds no handle any more and the next stop never closes the same original HANDLE a second time | STATIC_IMPLEMENTED, pending the dynamic batch |
| M07 | The launcher loses the partial channel of a launch (B5433-5489, B5304-5336, B5370-5430) | `_LaunchAggregate`, `StreamChannel.__init__`, `_adopt_broker_process`, `_LauncherCustody.release` | The channel of a launch registers itself with the **aggregate** before it builds anything; the aggregate is the recovery entry of the launch and it coordinates the channel **before** the process | `v0_s3_native_broker.py`: the class `_LaunchAggregate` (the bindings, the custody protocol, the ordered release), the retain of the channel **before** the endpoints, the dependency ordered release of the custody, the process helper that never closes the files of a process whose channel took them | N10-R04: the channel exists and the adoption fails before the local variable was assigned; the aggregate finds the partial channel, the files of the process are closed by the channel and never by the process helper | STATIC_IMPLEMENTED, pending the dynamic batch |
| M07 | A close of the channel that returned is taken for a release (B5333) | `_LaunchAggregate.release` | The channel of a launch lives until **every** fact of it is closed: the reader, the two ends, the workers and the original handles of their threads | the strict facts of the close decide the release of the channel; an incomplete close keeps the channel with its original reference and its owner; the original cancellation of the launch is propagated **after** the safe steps | N10-R05: the close of the channel returns without a confirmed end and the construction of the broker fails with a cancellation; the process was terminated and waited before the cancellation left, the channel kept its owner and the original cancellation object is the one that propagated | STATIC_IMPLEMENTED, pending the dynamic batch |
| M08 | The read and the write start a worker and submit a request before the admission (B3765-3790) | `_WindowsPipeEndpoint._admission`, `_WindowsPipeEndpoint.read`, `_WindowsPipeEndpoint.write` | The worker of an endpoint lives from the admission of the generation until the thread really ended; a refused call never creates one | the admission is asked **before** the start, the submit and the primitive; the check and the admission are one atomic step under the lock of the endpoint | N10-R06: the call enters with an expired deadline and with a cancel flag that is set; the refusal is named, the number of the primitive calls is zero and no worker was started | STATIC_IMPLEMENTED, pending the dynamic batch |
| M08 | The context of the round does not reach the launcher, the channel, the API and the workers (B5496-5547, B5604-5620, B4858-4862) | `NativeCustodySession._call_launcher`, `_default_launcher`, `launch_broker`, `BrokerCore.__init__`, `WindowsApi.bind_context`, `StreamChannel.__init__`, `_WindowsPipeEndpoint._start` | One context per process: the parent owns the context of the parent and the child owns the context of the child; the two are never the same object and never need to be | the context is held **before** the first side effect of the launch and it is handed to the channel, to the endpoints, to the workers and to the API of the primitives; the published cleanup deadline is part of the effective deadline of every layer | N10-R07: the launcher receives the context of the session and the deadline with it; the channel, the endpoint and the worker read the **published cleanup deadline** and not the long lease of the round | STATIC_IMPLEMENTED, pending the dynamic batch |
| M08 | The cleanup deadline that the round published is not read by the lower layers (B3699-3790, B3832-3875) | `_RoundContext.effective_deadline`, `StreamChannel._effective_deadline`, `_WindowsPipeEndpoint._effective_deadline`, `_WindowsPipeWorker._effective_deadline`, `BrokerProcess._cleanup_deadline`, `WindowsApi._effective_deadline` | The ONE cleanup deadline of the round is published once and it may only be shortened; every layer reads it **again** on every call | the effective deadline of every layer is the earliest of the call, the bound deadline, the absolute deadline of the round and the **published** cleanup deadline; the partial write reads it per segment and the join of the transport reads it before it waits | N10-R07 reads the cleanup deadline in the endpoint and in the worker; the STOPPED write of the child and the finally close of the transport read it through the same context of the core | STATIC_IMPLEMENTED, the real transport of the child is **not** run here (no native execution) |
| M08 | The retry of a cancellation does not tighten itself (B3488-3553) | `_WindowsPipeWorker.request_cancel` | The retry of a cancellation lives until the generation completed or the thread of the worker really stopped | every round of the retry reads the latest effective context and the pause of the retry is cropped to the time that is really left | N10-R08: the cancellation reports `NOT_FOUND` and the round publishes a shorter cleanup deadline while the retry runs; the retry stopped at the shorter deadline and it really repeated | STATIC_IMPLEMENTED, pending the dynamic batch |
| M08 | The exit of a startup step does not join its thread (B4674-4727) | `BrokerLoop._run_startup`, `_StartupOwner.settle` | The owner of a startup step lives until the **real** exit of its thread; an attempt that ended is never a proof | every exit of the startup step - the success, the timeout, the ordinary failure, the cancellation and the `SystemExit` - settles the owner in a `finally`; a thread that did not exit keeps its owner in the owners that are in flight | N10-R09: the action raises an ordinary error, a cancellation and a `SystemExit`, and a step that never returns; the owner was released only after the real exit and the owner of the step that did not end kept its place | STATIC_IMPLEMENTED, pending the dynamic batch |
| M09 | A close flag replaces a real IO failure of the generation (B3765-3790, B4235-4263) | `_WindowsPipeWorker.outcome`, `_WindowsPipeWorker.published_before_cancel`, `_WindowsPipeEndpoint._await`, `_WindowsPipeEndpoint._raise_cancellation` | The outcome of a generation lives from the completion of the request until the end of the round: the result, the error, the **original error object**, the source and the order of the completion | the outcome is recorded per generation under the lock of the worker; the endpoint coordinates the outcome of **the same generation** before and after the cancellation; a failure is the first error and the cancellation is a parallel fact | N10-R10: the failure of the read of the generation and the cancellation of the close arrive at the same moment; the original error object is the one that leaves and the code of the error is the code of the real fault | STATIC_IMPLEMENTED, pending the dynamic batch |
| M09 | The overflow of the channel is only an internal flag (B4199-4205, B4305-4402) | `StreamChannel._record_overflow`, `StreamChannel._drain`, `StreamChannel.close`, `BrokerProcess._close_channel` | The overflow of the channel is recorded at the place where it happens and it is **sticky**: the first named failure of the reader stays the error of the channel | the named error `BROKER_CHANNEL_OVERFLOW` with the original facts of the overflow travels with the facts of the close; the limits of the package are unchanged | N10-R11: the frame that is one byte beyond the limit is refused with the named error and the exact frame still fits | STATIC_IMPLEMENTED, pending the dynamic batch |
| test causality | The event of the reader is published after the wait and the negative case depends on the order of the scheduler (the failure of the correction 09) | `_F5Api.read_stream`, `_F5ExternalCancelOwner.run` | The reader of the chain is a state machine: `BOOTSTRAP_FRAMES_CONSUMED -> READ_WAITING -> explicit unlock -> RESULT/EOF` | the event of the reader is published **before** any blocking wait; the terminal frame of the round is published by the **write** of the stop and by nothing else; the ordinary failure and the frame that never ends are published by the **owner of the test** | N10-R12 (the event of the reader, the external owner and the public stop) and N10-R13 (the fault that the owner unlocks and that is observed before the stop) | the fixture of the old node N07-R15 was corrected in place and its node id and its order are unchanged |
| compatibility | The closed obligations of the package (the unknown lock, the two way budget, the terminal reservation, the source of a normal cancellation, the first error across a retry) | `NativeCustodySession._latch_unknown_state`, `_check_frame_budget`, `_send`, `_ChannelCancel` | unchanged | unchanged - the correction does not touch them | N10-R14 checks them on a real session and a real channel | the 175 old node ids and their order are **byte for byte the same** (verified statically, see the receipt) |

### 1.1 What is **not** covered by this correction

* The native claims stay `NOT_PROVEN`: nothing here ran a Windows API,
  a job object, a GPU, a service, a socket, a database or a network.
* The real transport of the child process (the `STOPPED` write and the
  finally close of the transport of the broker) is not driven here: the
  child side of the context is proven by the **unit** of the effective
  deadline of the channel, of the endpoint and of the worker, and not by
  a real child.
* The M03 sub gap of the API owner was already closed by the nodes of
  the correction 03 and 07 and it is not counted a second time here.
* The M07 sub gap of the *recovery* of a launch that was not handed
  over is covered by the nodes of the correction 05 (`N05-R10`); the
  correction 10 adds the **order** (the channel before the process) and
  the partial owner, not a new denominator.

## 2. The one context: the actual transmission edges

The parent and the child own **one context each**.  The two contexts
are never the same Python object and they never have to be: the parent
propagates its context into its own launch and the child builds its own
context from the plan of the round.

### 2.1 The parent

| Edge | Source | Deadline that is read | Every read |
|---|---|---|---|
| session -> context | `NativeCustodySession._fix_deadline` | the absolute deadline of the round | once, before the launcher |
| session -> launcher | `NativeCustodySession._call_launcher` -> `launch_broker(..., context=...)` | the absolute deadline of the round | the launcher holds it **before** the Popen, the hash of the executable, the channel and the endpoints |
| launcher -> aggregate | `launch_broker` -> `_LaunchAggregate(custody=..., context=context)` | the absolute deadline of the round | at the creation of the launch |
| launcher -> channel | `launch_broker` -> `StreamChannel(..., custody=launch, context=context)` and `channel.bind_deadline(deadline)` | the absolute deadline of the round | before the Popen is used and before the endpoints exist |
| channel -> endpoints | `StreamChannel.__init__` -> `_make_endpoint(..., context=context)` | the absolute deadline of the round | at the creation of the endpoints |
| endpoints -> workers | `_WindowsPipeEndpoint._start` -> `_WindowsPipeWorker(..., context=self._context)` | the absolute deadline of the round | at the creation of the worker |
| session -> broker | `NativeCustodySession._bind_deadline` -> `BrokerProcess.bind_channel_deadline` | the absolute deadline of the round | before the first frame of the round |

### 2.2 The child

| Edge | Source | Deadline that is read | Every read |
|---|---|---|---|
| core -> context | `BrokerCore.__init__` | the absolute deadline of the round | the context is created with the core |
| core -> API of the primitives | `BrokerCore.__init__` -> `WindowsApi.bind_context` | the absolute deadline **and** the published cleanup deadline | on every wait of the façade (`_effective_deadline`) |
| core -> transport | `BrokerLoop.run` -> `transport.bind_deadline(self._deadline_mono)` | the absolute deadline of the round | before the job of the round exists |
| core -> transport (the cleanup) | `BrokerCore.stop` publishes the cleanup deadline of the context and `BrokerLoop._stop` writes the `STOPPED` frame | the **published cleanup deadline** | the write of the terminal frame and the finally close of the transport |
| transport -> endpoints | `StreamChannel.__init__` -> `_make_endpoint(..., context=context)` | the absolute deadline and the published cleanup deadline | on every call of the endpoint |

### 2.3 The one effective deadline

Every layer computes the same value with the same rule:

```
effective = min(call deadline, bound deadline of the layer,
                 context.absolute_deadline, context.cleanup_deadline_value())
```

The rule is implemented in `_RoundContext.effective_deadline`,
`StreamChannel._effective_deadline`,
`_WindowsPipeEndpoint._effective_deadline`,
`_WindowsPipeWorker._effective_deadline`, `WindowsApi._effective_deadline`,
`BrokerProcess._cleanup_deadline` and `_LauncherCustody._effective_deadline`.
The published cleanup deadline may only **shorten** the value and it is
read again on every call: a deadline that was published after a wait
started still shortens the wait that is running.

## 3. The causal state machine of the fixture

The facade of the correction 07 (`_F5Api`) was corrected in place.  The
node id of `N07-R15` and the order of the 175 nodes are unchanged.

```
BOOTSTRAP_FRAMES_CONSUMED     the two frames of the round were delivered
        |
        v
READ_WAITING                  the event is published BEFORE any blocking wait
        |
        v
explicit unlock                the owner of the test publishes the outcome
                               (FRAME / FAULT / PARTIAL / EOF)
                               the cancellation of the operating system
                               publishes EOF for the reader of the chain
        |
        v
RESULT / EOF                   the frame, the ordinary failure of the read
                               or the end of the stream
```

* The terminal frame of the round is published by the **write** of the
  stop and by nothing else: a reader that reads a terminal frame before
  the stop was asked for would answer a stop that never happened.
* The ordinary failure of the read and the frame that never ends are
  published by the **owner of the test** and they are never unlocked by
  the write of the stop.
* The bounded wait of the owner of the test is **15 s** and it was not
  enlarged: the event that it waits for is now published immediately.
* The ten bounded documents of the group are written in the **new**
  directory of the correction 10
  (`implementation-native-custody-correction-10/f5-evidence`, or the
  directory that the environment of the batch names).  The four real
  documents of the failed batch of the correction 09 stay in the
  directory of the correction 09 and they are never overwritten, never
  deleted and never replaced by a summary.

## 4. The nodes

* The 175 frozen node ids and their order are unchanged.  The check is
  static and it is in `node-identity-check.json`.
* The 14 new nodes are **appended** in the NEW module
  `tools/test_v0_s3_native_custody_correction10.py`:

| # | node id | obligation | Major |
|---|---|---|---|
| 1 | `test_n10_r01_the_control_handle_is_closed_only_after_the_exit` | N10-R01 | M03 |
| 2 | `test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive` | N10-R02 | M05 |
| 3 | `test_n10_r03_every_confirmed_close_notifies_the_owner_of_the_handle` | N10-R03 | M06 |
| 4 | `test_n10_r04_the_launch_aggregate_finds_the_partial_channel` | N10-R04 | M07 |
| 5 | `test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel` | N10-R05 | M07 |
| 6 | `test_n10_r06_an_expired_or_cancelled_call_performs_no_primitive_call` | N10-R06 | M08 |
| 7 | `test_n10_r07_the_context_of_the_round_reaches_every_layer` | N10-R07 | M08 |
| 8 | `test_n10_r08_the_retry_of_a_cancellation_re_reads_the_context` | N10-R08 | M08 |
| 9 | `test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread` | N10-R09 | M08 |
| 10 | `test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation` | N10-R10 | M09 |
| 11 | `test_n10_r11_the_overflow_of_the_channel_is_a_named_failure` | N10-R11 | M09 |
| 12 | `test_n10_r12_the_reader_publishes_its_wait_before_it_waits` | N10-R12 | test causality |
| 13 | `test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first` | N10-R13 | M09 |
| 14 | `test_n10_r14_the_closed_obligations_of_the_package_do_not_regress` | N10-R14 | compatibility |

175 + 14 = **189** ordered nodes.  The old obligations of the
correction 03 (16), of the correction 05 (24) and of the correction 07
(18) are **not** replaced: they stay in the 175 and they are not
counted a second time.  The product denominator I24/12 does not move.

## 5. The boundary of this delivery

* **Static only.**  The candidate was not imported, not collected and
  not executed: no `pytest`, no `import tools.v0_s3_native_broker`, no
  probe, no script of the author.  The checks that were run are the
  parse of the four sources, the compile of the four sources in memory
  and a static scope check; they are named in
  `static-implementation-receipt.json`.
* No real process, no Windows API, no job object, no GPU, no model, no
  service, no socket, no sqlite, no network, no download and no media
  were used or allowed.
* The original counter was **not** read, rebuilt, reset, refunded or
  revived.  The continuity stays `UNAVAILABLE_NOT_PROVEN` and the old
  grant stays `EXPIRED_NO_REPLAY`.
* The native refusal points are kept: the broker still refuses on every
  platform that is not Windows and the launcher of the package is still
  inert.
* N2 is **not** started.  This delivery claims no Stage PASS, no
  product gate 0 and no closure of the six Majors.

## 6. The correction of the preflight review of the root

The root reviewed the committed candidate `05c58c1` in its read only
preflight review (`preflight-review-01/decision.json`) and it asked for
**nine** corrections (`C10-P01` .. `C10-P09`) before any dynamic
permission.  The review is static, no test was run and the six Majors
stay OPEN.  Every finding was corrected as one batch, in a **new
ordinary commit**; the candidate `05c58c1` and the report of it are
preserved and were not amended.

| Finding | What was wrong | What the new candidate does |
|---|---|---|
| C10-P01 | three of the new groups used `tmp_path` without declaring the fixture and the receipt named the wrong role | the three groups declare `tmp_path`; the receipt names the real implementation identity and the model that carries it |
| C10-P02 | the first group only launched a normal round and let the wait fail; it never drove the frozen assign failure of a suspended child | the group drives the **real** assign failure of the core: the assignment of the process to the job fails, the termination of the child fails and the wait does not confirm the exit; the control HANDLE is kept by the record **and** by the pending table and the same owner closes it exactly once after the exit is confirmed |
| C10-P03 | the thread of the channel was a boolean and the partial channel was read from a local variable that the failed construction never assigned | the thread of the channel is a **real** thread that starts and whose start does not return; the partial channel is read **from the aggregate** and the facts of the release are written before the salvage |
| C10-P04 | the fifth group only covered the cancellation of the construction of the broker and it compared the message of the exception | the group covers the **recovery** of the launcher as well: the cancellation of the recovery, the safe finalizer, the order (the channel before the process), the retained owner and the **identity** of the original object and of the cancellation (`lvw_cancelled`) |
| C10-P05 | the sixth group had no cancelled **write** and the seventh replaced the whole launcher by a peer and built the endpoint and the worker by hand | the sixth group drives the cancelled write; the seventh keeps the production owners - the session, the aggregate, the channel, the endpoints, the core, the loop and the transport of the child - and it proves the context before the side effects of the launch and the cleanup deadline of the child after its STOP |
| C10-P06 | the ninth group let the thread of the startup step end at once, so the frozen negative case (the result is published and the real thread is still alive) was never established | the result of the step is published into the **real** result channel of the production owner while its thread stays alive; the group proves that the owner was not released, that the bounded join ran and that the original exception object is the one that propagated; no sleep is used as the evidence of an exit |
| C10-P07 | the tenth group cancelled before the failure and it only drove the endpoint | the tenth group waits for the **published** outcome of the generation (an event of the production worker), checks the identity of the original error object, then drives the **production close chain**: two real public stops of the session keep the sticky error and the round stays unknown |
| C10-P08 | the eleventh group only closed the channel and it never reached the parent facts; the frame count was missing and the one-over was two bytes | the eleventh group drives the **real** session chain with a complete newline oversize and reads the parent facts of the two stops; the frame count is driven on the production channel and the reason is named; the exact frame and the one byte beyond the limit are strictly adjacent and the threshold of the package did not move |
| C10-P09 | the twelfth group accepted only one of the two codes of the production and the thirteenth group only had the ordinary fault | the twelfth group classifies the code by the **real** observation layer and by the origin of the cancellation and it keeps the origin unknown; the thirteenth group adds the frame that never ends and the end of the stream, writes the bounded document of **every** phase and joins the thread of the test owner unconditionally with a bounded wait |

The 175 frozen node ids and their order and the 14 new node ids and their
order are unchanged (`node-identity-check.json`): 175 + 14 = 189.

The changes of the production that the correction of the preflight
carries are two and they are small:

* the cancellation of the recovery of a launch is attached to the
  original failure of the launch (`lvw_cancelled`), so that the primary
  failure and the cancellation of the recovery coexist and the original
  object is the one that leaves;
* every launch registers its **aggregate** with the table of the
  launcher, so that the recovery of the table coordinates the resources
  of the launch in the dependency order - the channel before the
  process.

## 7. The ten fields

| Field | Value |
|---|---|
| the current coordinate | R1 / WP-R1-U3 / `S3_P4_OFFLINE_INTEGRATION_PREPARATION` |
| what this batch did | the static implementation of the six Major atomic gaps of the correction 10 and the 14 new frozen nodes |
| the last passed gate | `621b1bf` `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW` (10/10) |
| the current blocker | `S3_P4_N1_CORRECTION_09_FAILED_175_CANCEL_ORDERING` and the six open Majors |
| the place in the global route | see the outline below |
| the remaining work | the finite 189 node batch of the root, a new independent review of the six Majors, the dynamic facts of the native paths |
| the next owner | the gate owner of the root (the finite plan and the ACK of the batch) |
| the required authorisation | the static scope of the correction 10; the dynamic scope is **not** requested here |
| the evidence directory | `reports/v0-s3/product-gate0/implementation-native-custody-correction-10/` |
| the exact stop reason | the static implementation is complete and the candidate is committed; the finite plan of the 189 nodes is asked of the root and this owner waits for the reply |

### The outline of V0 - V3 (the numbers of the control, not increased)

V0-S0 1/2 (historical NO_GO), V0-S1 5/5 (only V0-Min), R0 1/2 (the
predecessor subset), R1a 5/5 (the single slice), V0-S2 7/8 (the old
scope is unsigned), V0-S3 0/6, R1 0/4, V1-M1 0/3, R2 0/4, R3/V2 0/4,
R4/V2 0/4, R5a/V3 0/4, R5b/V3 0/4, R5c/V3 0/4.

The implementation, the machine acceptance, the independent review and
the human signature stay four different things: this delivery is the
**implementation** and it is `READY_FOR_REVIEW`.
