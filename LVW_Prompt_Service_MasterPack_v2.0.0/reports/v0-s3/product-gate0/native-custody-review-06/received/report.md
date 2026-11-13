# N1 correction 06: the six failures of the one frozen batch of the correction 05

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate: `S3_P4_N1_CORRECTION_06_CONSOLIDATED`.

Baseline (the failed candidate): `0e83077321186b52c7e3826efbbf92c143737b0f`.
Evidence of the predecessor: `4693c12d414fd0d8b632945535bd10b1b8d59797`.
Root package: `reports/v0-s3/product-gate0/native-custody-correction-06`
(`contract.md`, `decision.json`, `failed-attempt01/execution-report.md`).
Parent package: `reports/v0-s3/product-gate0/native-custody-correction-05`
(`contract.md`, `regression-obligations.json`).

This delivery claims **READY_FOR_REVIEW**.  It claims **not** Stage PASS, not a
native execution, not a native cleanup, not a released GPU, not a released port,
not a sampler, not a parent crash recovery, not a Windows stdin EOF, not an
admission and not a product gate 0.  The six open majors of the isolated review
of the predecessor stay open: this delivery corrects the six failures of the one
frozen batch and it closes none of them.

## 1. What was read

The root package was read in full before the first edit: `contract.md`,
`decision.json` and `failed-attempt01/execution-report.md`.  The parent package
was read as well: `contract.md` and `regression-obligations.json` (the 24 frozen
groups and their oracles).  The governance layer was read before the sources:
`AGENTS.md`, `.agent-governance/README.md`, `plans/execution-control.json` and the
execution index `docs/24_EXECUTION_MASTER_PLAN.md`.

The failed candidate was **not** changed and the failed batch was **not**
reproduced: the six failures are read from the frozen execution report of the
root and they are corrected statically.

## 2. The erratum of the classification of the six failures

The report of the failed batch of the root says that "three of the six failures
are defects of the production code of the candidate and three are defects of the
new test module".  **That classification is wrong and it is corrected here.**
The classification that the root verified independently is the one that this
delivery implements:

| Failure | Node | The path that was wrong |
|---|---|---|
| F1 | `tools/test_v0_s3_native_custody_regressions.py::test_n03_r06_the_start_cleans_up_everything_that_it_acquired` | **production** — the internal `_close_broker` coordinated the unconfirmed items again and it closed the same peer a second time |
| F2 | `tools/test_v0_s3_native_custody_correction05.py::test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation` | **test only** — the membership of an unhashable `ctypes` handle |
| F3 | `tools/test_v0_s3_native_custody_correction05.py::test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup` | **production and test** — the bookkeeping of the core after a successful retry of the pending pass was stale, **and** the expectation of the node described a state that the product never reaches |
| F4 | `tools/test_v0_s3_native_custody_correction05.py::test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread` | **test only** — the stand-in of the reader did not implement the interface that the evidence reads |
| F5 | `tools/test_v0_s3_native_custody_correction05.py::test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` | **production** — the original handles of a late created process entered no table and no owner |
| F6 | `tools/test_v0_s3_native_custody_correction05.py::test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts` | **production** — a waiter that arrived after the end of the attempt confirmed the close while the closer thread was still alive |

There are therefore **four production related paths** (F1, F3, F5, F6), **two
test only paths** (F2, F4) and **one node that carried a wrong expectation as
well** (F3).  The report of the failed batch of the root is **not** overwritten
and it is not corrected in place: this report carries the erratum.  The old
owner, the contracts, the 24 obligations, `control`, `MANIFEST` and every
historical report are untouched.

## 3. The one root cause and the four corrections of the production

The four production defects are one root cause: **the round had more than one
truth about the same resource.**  The end of an *attempt* was read as the end of
the *release*, a *closed* handle was still named by the owner of the round, a
handle that was created was not owned by anybody and the end of the *attempt* of
a close was read as the end of the *thread* that performed it.  The corrections
are therefore one correction of the ownership and of the facts, and they are
corrected together.

### 3.1 F1 — the recovery belongs to the public stop (`tools/v0_s3_native_custody.py`)

* The internal `_close_broker` **never** coordinates the unconfirmed items any
  more.  Its branch for the state `FINISHED` returns without a second close: a
  close that follows the attempt of a background thread - the close of a start
  that failed, for instance - closed the same peer a second time and it broke
  the oracle of R06, which asks for exactly one close of that peer.
* The recovery is driven by the **explicit intent of the public stop**.  The new
  `_public_stop_recovery` is the only entry that reaches `_recover_close`:
  * the **first** stop that finds the state `FINISHED` - a background attempt
    that completed before it - **takes over** the unconfirmed items inside the
    **original** deadline of the cleanup;
  * a **repeated** stop sends no second `STOP`, opens no second budget and
    coordinates the unconfirmed items only;
  * a stop that was itself the owner of the close performs **no** recovery, so a
    peer is never closed twice by the same stop and a confirmed release is never
    touched again;
  * a competitor never opens a second close at the same time: a close that is in
    flight is waited for and the items that it did not confirm may be
    coordinated by a **later** public stop.  The recovery is therefore never
    locked out.
  * a recovery that arrives after the deadline keeps the resources of the round
    with their owner, names `CUSTODY_CLOSE_RECOVERY_EXPIRED` and latches the
    unknown state.  The deadline is never renewed.
* `_close_broker` now returns the role of its caller (`PERFORMED`,
  `ALREADY_FINISHED`, `WAITED`, `OWNER`, `NOTHING_TO_CLOSE`) so that the
  decision of the recovery is taken on a **fact** and not on a guess.

### 3.2 F3 — the pending pass tells the core what it really closed (`tools/v0_s3_native_broker.py`)

* `_PendingResources.close_all` reports every handle that it closed with a
  **confirmed** close to the owner of the table (`on_closed`).  The report
  happens **before** a cancellation is raised: the bookkeeping of the core is
  never left behind the error that left the cleanup.
* The new `BrokerCore._note_closed_handle` is that notification: a handle that
  is really closed is no longer named by `core.job`, by the `*_handle_closed`
  flags and the handles of the records, nor by `core._retained_resources`.
  `core.job_closed` becomes true and `core.job` becomes `None` when the job
  handle was the one that was closed.
* Only the handle that was really closed is forgotten.  A handle that could not
  be closed keeps its owner, it stays in the pending table and it stays named in
  the retained resources with its original reference.  The retained list is
  **never** cleared to make a check green.
* The cancellation still propagates and the primary and the secondary errors
  still coexist: the cancellation of the close of the job handle is still the
  error that leaves `BrokerCore.stop` and it is still named with
  `'cancellation': True`.
* A handle that was closed with a confirmed close is never closed a second
  time: it left the pending table at the confirmed close and the pending pass
  never sees it again.

### 3.3 F5 — a late created process is owned before it may be refused (`tools/v0_s3_native_broker.py`)

* `BrokerCore._launch_role` registers the **original** process handle and the
  **original** thread handle in the pending table of the round and takes their
  ownership (`CORE`) **in the moment of their creation**.  The registration is
  now **before** the check of the shared budget that follows the creation and
  before every other step that may raise.
* A process that was created after the deadline arrived is therefore never
  owned by nobody: the lease of the round may end, the ownership of the handles
  may not.  It is never assigned, never resumed and never followed by another
  role; only the late original resources are cleaned up, through the ordinary
  release of the records and of the pending table.
* The parent API keeps its own owner for a handover that failed and the core
  keeps the de-duplication of a takeover that succeeded: both guarantees of the
  predecessor are preserved and neither of them was weakened.

### 3.4 F6 — the end of the attempt and the end of the thread are two facts (`tools/v0_s3_native_custody.py`)

* `_await_close` no longer confirms a close because the *attempt* ended.  A
  waiter that arrives when the state is already `FINISHED` waits for the
  **real exit** of the closer thread, inside the **same** absolute deadline of
  the cleanup, and the remaining budget is recomputed before every single wait.
* The confirmation of the exit is a **real join** of the original thread, not
  the event that the thread sets in its own `finally`: the event is published
  while the thread is still alive.  The waiter asks the thread itself
  (`is_alive`) after the join.
* The two execution modes are explicit: a close that has **no closer thread of
  its own** and **no cleanup in flight** may be confirmed at once; a close that
  has a closer thread is only confirmed when that thread really ended.
* The round never joins itself, a closer never waits for a waiter and a waiter
  never holds the lock of the owner while it waits: there is no cycle of waits.
* A closer that is still alive when the deadline arrives keeps its owner and
  its reference, names `CUSTODY_CLOSER_NOT_FINISHED` and latches the unknown
  state.  The original deadline is not extended.
* The evidence of the round carries the two facts: `closer_alive` asks the
  thread and `closer_exited` is true only when the event was published **and**
  the thread is really gone.

## 4. The two corrections of the tests and the salvage of the test owner

### 4.1 F2 — the original handle of an end of a pipe

The façade keeps the **original** object of the end of a pipe: a
`ctypes.c_void_p`, which is not hashable in CPython.  The node compares the
**number** that the kernel knows (`getattr(handle, 'value', handle)`) with the
live table of the synthetic kernel, and it proves **more** than before: the
retained object is the very object of the façade (`is`, not a copy), the owner of
the end is the façade (`WINDOWS_API`) and its recovery is the entry that
releases it.  The production was **not** changed to replace the original handle
by a hashable copy.

### 4.2 F4 — the stand-in of the reader is a reader

The stand-in of the node now implements the **whole** interface of the reader of
the channel: `error`, `alive`, `finished`, `stop`, `join` and `join_bounded`.
It drives the real `_start_background_thread` and the real `evidence()` of the
round and it reports the **true** facts of the thread: the node asserts that the
reader is alive, that it has no error and that the record of the background
thread says `started` and `alive`.  The production evidence was **not**
weakened to hide the facts of a valid reader.

### 4.3 The two nodes that were corrected against the product, not against the expectation

* **R04 (F3).**  The old expectation (`core.job is not None` and
  `core.job in win32.live`) described a state that the product never reaches:
  the pending pass really closed the job handle.  The node was **not** weakened
  and the assertion was **not** deleted: it now checks the facts of the product
  at the moment the product returned them - the handle is really closed, the
  core does not name it any more, `job_closed` is true, the pending table is
  empty and the retained resources do not name it.  The node carries the two
  scenarios of the contract in the same node: a close that fails **temporarily**
  and that the pending pass retries successfully, and a close that keeps
  failing and that keeps its owner and its name.
* **R23 (F6).**  The node now drives the waiter **before** the end of the
  attempt and **after** it, and it drives the two execution modes: the closer
  thread and the calling thread.  The waiter that arrives after the attempt
  ends waits for the real exit of the closer and it is named unknown when the
  deadline arrives; the waiter that arrives before the attempt ends waits for
  the attempt and then for the real exit of the closer.

### 4.4 The salvage of the test owner

Every new or affected node releases its own resources in a `finally`, whatever
the assertions above did:

* **R08** releases the gate of the stand-in and joins its thread.  The thread
  `lvw-native-custody-late` of that node was one of the two threads that the
  failed batch retained.
* **R23** releases the gate of the closer and joins the closer thread.  The
  thread `lvw-native-custody-closer` of that node was the other one.
* **R04** releases the handles of the synthetic façade that the product could
  not close.

The fact of the product is recorded **before** the salvage and the salvage never
turns a product that returned unknown into a product that returned clean.  A
thread name filter, a daemon thread and the garbage collector are never used
as a proof of a cleanup.

## 5. The frozen denominator

The **157** node ids and their order are unchanged.  No node was added, no node
was removed, no node was renamed and no assertion was deleted.  The corrections
are inside the four existing nodes and they add scenarios to them; the order
of the batch stays the order of the failed batch.

The plan of the one batch is in `execution-plan.request.json` of this
directory:

* the new candidate and its five source pins plus the pins of the old owners;
* the same **223** named dependency pins and the same **three** stdlib pins,
  re-verified against the bytes of this host before the request was written;
* the guard, the runner and the outer counter reader of the root, with the
  bytes of the frozen package of the correction 05;
* one batch of at most **300** seconds, the three absolute commands of the
  predecessor and the same counter policy (read once before and once after,
  never written, never reset, never refunded).

## 6. The execution boundary of this delivery

The implementation itself was **static**: the sources were written, parsed with
`ast` and reviewed statically.  There was **no** import of the candidate, **no**
collection, **no** pytest and **no** probe before the acknowledgement of the
root.  No real process, no GPU, no model, no service, no media, no database, no
socket, no network, no download and no original ledger were touched.  The
counter of the package was not read, not written, not reset and not refunded.

The failed candidate `0e83077321186b52c7e3826efbbf92c143737b0f` and the failed
batch of the root are **not** overwritten and the receipt of the root is not
touched.

The root acknowledged the plan (`msg_80589155e219`,
`ACK_ONE_FROZEN_157_NODE_OFFLINE_BATCH`, plan SHA256
`65e9df9904e297d0f5c76f756b5d6070f2437375f3b6a65eb2f9d0a0b85a2251`) and the one
frozen batch was executed **once**, in the order of the three frozen commands,
with their original argv and their original cwd.  **The batch passed**: 157
collected, 157 passed, 0 failed, 0 skipped, pytest exit 0 and
`cleanup_proven_for_batch` **true**.  There was no rerun, no wrapper, no
overwritten candidate and no self repair.

The evidence of the batch, the receipt of the runner (whose file name is
inherited from the root runner and is
`native-custody-correction-03.receipt.json`, written **only** into the NEW
`attempt01` directory of this correction), the guard record, the two read only
observations of the counter and the per node results are in
`attempt01/execution-report.md` and in `attempt01/commands.json` of this
directory.

The six open majors of the isolated review of the predecessor stay open: a
green batch is **not** a closed major, and the independent review keeps its own
verdict on the four points that the review notes of the root name - the
concurrency of the initialisation of the deadline, the recovery of the retained
resources, the owner of a background start that did not return and the
difference between the end of the attempt and the exit of the thread.

## 7. The files of this delivery

* `tools/v0_s3_native_custody.py` — the parent side: the public stop and its
  recovery, the two facts of the end of the close and the real exit of the
  closer.
* `tools/v0_s3_native_broker.py` — the broker side: the ownership of the
  original handles in the moment of their creation and the notification of the
  confirmed closes of the pending pass.
* `tools/test_v0_s3_native_custody_correction05.py` — the corrected R03, R04,
  R08 and R23 with the salvage of the test owner.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-06/` —
  this report and the plan request.

`tools/test_v0_s3_native_custody.py` and
`tools/test_v0_s3_native_custody_regressions.py` are **unchanged**: the frozen
oracle of R06 of the regressions and the 133 frozen nodes keep their identity,
their order and their bytes.  Nothing outside these files was changed: the
controller, the worker, the runtime, the driver, the supervisor, the sampler,
the authorization, the public schemas, the quality thresholds, `control`,
`MANIFEST`, the contracts, the 24 obligations and every historical report are
frozen and untouched.  N2 was not started.
