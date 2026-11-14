# N1 correction 09: the deterministic order of the cancellation of another owner; the batch of the root ran exactly once and it FAILED

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_09_DETERMINISTIC_EXTERNAL_CANCEL_PUBLICATION`.

Candidate of this delivery: `39f803730e09673eb1b74fa51e1f0919f2606a71`.
Production baseline (frozen by the root): `66600a1bd692c0149fc7724b624997bf2f40dcc1`.
Evidence of the failed batch of the correction 08 (frozen by the root):
`fb44ff7ac9ffa52163236fc1eb7ecc85ea6682aa`
(`175 calls / 174 pass / 1 fail / 0 skip / pytest exit 1 / cleanup proven for the
batch = true`).

Root package: `reports/v0-s3/product-gate0/native-custody-correction-09`
(`contract.md`, `decision.json`, `implementation-prompt.md`, `received/execution-report.md`,
`capacity.json`, `launch.json`, `predecessor-release.json`,
`temporary-retry-env.json`, `archive-index.json`).  Parent package:
`native-custody-correction-08` (`contract.md`, `decision.json`,
`validation-plan-02/plan.json`, `attempt02/execution-report.md`) and the
obligations of the correction 07 (the 18 frozen groups of the new module)
and of its parents (16 + 24 groups), all inherited unchanged.

**This delivery is a static implementation.**  The candidate was **not**
imported, **not** collected and **not** run by pytest **by the
implementation**.  The batch that the root authorised afterwards ran
**exactly once** under the guard of the root and it **FAILED** with one
failure; the report of that batch is section 11 and the raw evidence of it
is in `attempt01/`.  The counter of the root was **not** read by the
implementation: it was **MISSING** before the batch and it is **MISSING**
after it, its historical continuity is `UNAVAILABLE_NOT_PROVEN` and no
ledger was touched.  The claims of this delivery stay **READY_FOR_REVIEW**.
They are **not** Stage PASS, they are not a native execution, they are not a
native cleanup, they are not a released GPU, they are not a released port,
they are not a sampler, they are not a parent crash recovery, they are not a
Windows stdin EOF, they are not an admission and they are not a product
gate 0.

**The six majors of the isolated review stay OPEN.**  This delivery corrects
the **ordering** of one negative scenario of one test module and it closes
nothing by itself.

## 1. What was read

The frozen package of the root was read in full before the first edit:
`contract.md`, `decision.json`, `implementation-prompt.md` and
`received/execution-report.md` (the report of the failed batch of the
correction 08) together with the two outer observations of the absence of
the counter and the guard snapshot of that batch.  The plan of the root of
the correction 08 (`validation-plan-02/plan.json`) and its three tools
(`guard.py`, `runner.py`, `outer_counter_observe.py`) were read in full:
the absence mode and the hard guard of the next batch are inherited from
them.

The governance layer was read before the sources: `AGENTS.md`,
`.agent-governance/README.md`, `plans/execution-control.json` and the
execution index `docs/24_EXECUTION_MASTER_PLAN.md`.  The changed test
module and the two production sources were read in full.

The predecessor candidate was **not** changed, the failed batch of the
correction 08 was **not** rerun and its five real documents were **not**
touched.

## 2. The diagnosis: the test did not order its premise

The failed batch of the correction 08 stopped at the **first** assertion of
the second bounded sub scenario of the group `N07-R15`:

```
tools/test_v0_s3_native_custody_correction07.py:1787:
    assert facts.get('channel_reader_error') == 'BROKER_PIPE_CANCELLED'
E   AssertionError: the cancellation of another owner was swallowed
E   assert None == 'BROKER_PIPE_CANCELLED'
```

The raw facts of that failure are on the disk
(`implementation-native-custody-correction-08/f5-evidence/f5-unrelated-cancellation.json`):
the close of the channel **initiated** the cancellation
(`close_cancellation = {code: BROKER_PIPE_CANCELLED, source: CHANNEL_CLOSE,
sequence: 1}`) and the error of the reader was `None`.

**What the raw facts prove**: the close won the race for the flag of the
cancel.  The flag of the channel names the owner that set it and the
**first** owner wins (`_ChannelCancel.set` registers the owner only while
the event is not set), so the close of the channel was the owner of that
cancellation and the production behaved exactly as it is designed to
behave: a cancellation that the close of the channel really initiated is a
named fact of the close and not an error of the reader.

**What the raw facts do NOT prove**: that the production swallowed a
cancellation of another owner.  The old owner of the test waited for the
reader of the chain to be really inside its read, and that observation only
happens **during** the exchange of the stop, i.e. **concurrently** with the
close of the channel.  The premise of the sub scenario (a cancellation of
**another** owner with the same code) was therefore never established.  The
root classified it as a **preparation gap of the order of the test** and it
did not conclude that the production is entirely correct.

The consequence of the stop: the five bounded documents that the group
writes before its assertions were written only up to the failure.  The
second public stop of that sub scenario and the two sub scenarios of the
ordinary failure of the read and of the frame that never ends were **never
executed**.

## 3. The correction: one explicit event and one order

Only **one** file of the product changes:
`tools/test_v0_s3_native_custody_correction07.py`.  No production source is
changed and no other test module is changed.

The external owner of the cancel flag is now a **named object** of the
test (`_F5ExternalCancelOwner`) and not a lambda of a thread:

* it waits for the **explicit** event that the reader of the chain is
  really inside its read (`api.reader_blocked`), the wait is bounded and
  its **return is checked**: a timeout is a failure of the owner and never
  a silent guess;
* it sets the **same** cancel flag of the **same** channel
  (`channel._cancel.set()`) **without naming an owner**;
* it publishes an **explicit confirmation** (`external_cancel_published`)
  and it records what the flag really names (`flag_set`, `flag_owner`).

The owner of the test waits for that confirmation, it checks that the flag
is **really set** and that the origin of the cancellation is really
**unknown** (`channel._cancel.owner() is None`) and **only then** it drives
the **first** public stop of the round.  The order of the two facts is
therefore the order of the test and not the order of the scheduler.

The failure of the owner is **reported** to the owner of the test and it is
never swallowed: the owner never asserts and never raises into its own
thread, the confirmation is published in **every** case (the `finally` of
the owner), and the owner of the test re-raises the failure of the owner
instead of driving the close after a failed owner.  The **exact** thread of
the owner is joined in the `finally` with a bounded join and the group
asserts that it is not alive: the round is never closed under a live worker
and the exit of the process is never the end of a thread (the thread is not
a daemon any more).

There is **no** sleep, **no** polling loop and **no** probabilistic rerun
in the changed module, and **no** benign interface was added to the
production.

## 4. What did NOT change

* Every original assertion of the group is kept: the error of the reader
  is not empty and its origin is not a normal close, the broker stays
  `UNKNOWN`, the two public stops do not lose the first error and the
  original deadline of the cleanup does not change.
* The two public stops of the three sub scenarios that carry a real error
  of the reader are kept, and the sub scenario of the unrelated owner now
  really drives its **second** public stop.
* The identity and the order of the **175** node ids are unchanged: no
  node was added, removed or renamed, and the name of the group is
  unchanged.
* The successful scenarios (the cancellation that the close really
  initiated, the targeted fault of the original handle of the thread of
  one named worker with its first retained and its second released, the
  scenarios that do not close twice) are unchanged.
* The two production sources are **byte equal** to the candidate
  `66600a1` of the failed batch:

| The source | The SHA256 of `66600a1` and of the candidate of this delivery |
|---|---|
| `tools/v0_s3_native_broker.py` | `06cf8da96b681cc7430d48cad6187790aea132e738896f29345e3ec3b41e1913` |
| `tools/v0_s3_native_custody.py` | `f8191be1ce25b9b859a3471a3c91e61a1f5821a16a4096989b9c24d76e691e34` |

  The only changed file of the whole tree of the product is
  `tools/test_v0_s3_native_custody_correction07.py`.

## 5. The static self-review

The static review of this delivery is a source review.  It is **not** a
measurement and it is **not** a native claim.

* The changed module was parsed with the abstract syntax tree of the host:
  the parse succeeded.
* A static name check (the module level names, the local names, the
  arguments, the comprehension variables, the exception names and the
  builtins) reports **no undefined name**.
* The module still declares the **18** frozen groups of the correction 07
  and the identity and the order of the node ids are unchanged.
* The changed module contains **no** `time.sleep` and **no** `while` loop
  and **no** `async for` loop: every wait of the corrected scenario is an
  event wait or a bounded join.
* The diagnostics of the group are written in the **new** directory
  `implementation-native-custody-correction-09/f5-evidence/`.  The five
  real documents of the correction 08 stay in their own directory and they
  are never overwritten.

What this delivery does **not** claim and what it did **not** do:

* the implementation did **not** import, **not** collect and **not** run
  the candidate: no pytest, no runner, no guard and no dynamic probe of
  any kind was executed **by the implementation**;
* the implementation did **not** run the guard and it did **not** read the
  counter of the root: the absence of the counter is a fact of the failed
  batch of the correction 08 and it is not re-observed here;
* no Windows API, no job object, no process, no service, no socket, no
  database, no network, no download, no media and no GPU was touched;
* the budget ledger and the shared counter were **not** read, **not**
  written and **not** reset: the old grant stays `EXPIRED_NO_REPLAY` and
  the historical continuity of the counter stays `UNAVAILABLE_NOT_PROVEN`;
* no agent was derived and no owner of another round was changed;
* the native claims of the package stay `NOT_PROVEN`.

## 6. The ten phases of the fifth failure

The group writes **ten** bounded JSON documents and it writes each of them
**before** the assertions of its phase.  The batch of the root ran **once**
(section 11) and it stopped inside the second bounded sub scenario, so
**four** of the ten documents were written and they are the raw evidence of
the batch; the other **six** are `NOT_RUN` and they are not pre-created.

| The document | The failed batch of the correction 08 | This attempt |
|---|---|---|
| `f5-first.json` | written | **written** |
| `f5-second.json` | written | **written** |
| `f5-salvage.json` | written | **written** |
| `f5-close-cancellation.json` | written | **written** |
| `f5-unrelated-cancellation.json` | written (it holds the facts of the failure) | **not written**: the group stopped before the first public stop of that sub scenario |
| `f5-unrelated-cancellation-second.json` | **not written**: the group stopped at the first assertion of that sub scenario | **not written** |
| `f5-read-fault.json` | **not written**: the group stopped before that sub scenario | **not written** |
| `f5-read-fault-second.json` | **not written** | **not written** |
| `f5-partial-frame.json` | **not written** | **not written** |
| `f5-partial-frame-second.json` | **not written** | **not written** |

**The erratum of the count**: the missing phases are **five documents** and
not the four sub scenarios of the group.  The second public stop of the sub
scenario of the unrelated owner is a document of its own, therefore five
documents are missing and not four.  The five documents of the correction
08 that were really written are evidence and they are never overwritten:
the diagnostics of the correction 09 are written in the **new** directory
and the two directories are never mixed.

## 7. The ten fields

* **Current coordinate**: R1 / WP-R1-U3 / RUNNING; the gate of this
  correction is
  `S3_P4_N1_CORRECTION_09_DETERMINISTIC_EXTERNAL_CANCEL_PUBLICATION`.
* **What this batch completes**: the static correction of the **ordering**
  of the one failure of the frozen batch of the correction 08 and the
  preparation of the ten bounded documents of the next batch.  It closes
  **no** major.
* **The last passed gate**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`
  (candidate `621b1bf`), unchanged by this delivery.
* **The position in the global route**: the coordinate of
  `plans/execution-control.json` is unchanged (`R1 / WP-R1-U3`, state
  `READY`).  The progress comes from the `development_outline` of that
  plan and from the real receipts; it is not a subjective percentage.
* **The remaining work**: the correction of the one failure of the batch of
  section 11, the next frozen batch, the isolated review, the human
  signature, the native Windows run and the N2 work, which is not started.
* **The next owner**: the gate owner of the root and the independent
  review.
* **The required authorization**: the static implementation of this delivery
  is the work of the frozen workpack and it changes **no** production
  source.  The dynamic execution was authorized by the ACK
  `ACK_ONE_175_NODE_OFFLINE_BATCH_WITH_EXPLICIT_ORIGINAL_COUNTER_ABSENCE`
  (`msg_806e6970083e`) and it was used **once**.
* **The evidence directory**:
  `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/`.
* **The exact reason of the stop**: the static correction, the static
  self-review and the preparation of the plan request are complete and the
  batch of the root ran **exactly once** and **failed** with one failure
  (section 11).  There was no rerun, no wrapper, no self repair and no
  overwrite of a candidate; the correction of the one failure belongs to the
  root.
* **The claims**: READY_FOR_REVIEW.  Not Stage PASS.  The six majors of the
  independent review stay **OPEN**.

## 8. The frozen plan that is asked of the root

The delivery asks for exactly **one** finite dynamic batch and it is
described in `execution-plan.request.json` of this directory.  It carries:

* the candidate SHA and the baseline SHA, the pins of the **22** sources
  (only the one changed test module has a new digest) and the pins of the
  **223** dependency files and of the **3** stdlib pins;
* the ordered and frozen set of the **175** node ids and the two
  integrity only nodes;
* the **three** commands with their absolute argv and their absolute cwd,
  the guard of the root, the runner of the root and the outer observation
  of the absence of the counter, all of them in the **new** directory
  `native-custody-correction-09/validation-plan-01` that the root places
  with the same bytes as the tools of `validation-plan-02`;
* **one** batch of at most **300** seconds, the raw output of every node,
  the exit code, the real identity of the file descriptors before and
  after the batch and the state of every thread before and after it;
* the **ten** diagnostics of the fifth failure and the directory in which
  they are written.

The **absence mode** of the correction 08 is inherited as it is: the outer
observation only **lstats** the exact counter and its parent and it
requires both of them to be **MISSING** (`errno 2`); it does not read the
content, it does not scan anything, it does not rebuild, reset, refund or
revive anything.  The shape of the old counter **read** of the attempt 01
of the correction 08 is **not** copied.  The historical continuity of the
counter stays `UNAVAILABLE_NOT_PROVEN` and the old grant stays
`EXPIRED_NO_REPLAY`.

The hard guard of the root precedes the candidate and pytest, its self
test denies the eight prohibited events and the **runtime denials are
empty**: no real process, no socket, no `sqlite3.connect`, no `dlopen` and
no `dlsym` happen during the batch.  The only permitted preload is the
**one** trusted `ctypes.dlopen(None)` and its window is `CLOSED` before
the candidate and before pytest; it is never reopened.  The real Win32
API, the job objects, the processes, the GPU, the models, the network, the
downloads, the media and the original ledger are refused.  **A denial of
the guard at runtime is a failure of the batch and it is never read as a
pass.**

The stop rules are the ones of the predecessor: the **first** `429` stops
the batch with `WAIT_BUDGET` (no retry, no other route, no takeover by the
root) and the **first** refusal or timeout of an approval stops the batch
without any wrapper and without any bypass.

## 9. The files of this delivery

* `tools/test_v0_s3_native_custody_correction07.py` (changed) — the group
  `N07-R15`: the external owner of the cancel flag is a named object with
  an explicit confirmation, the owner of the test waits for it and checks
  the flag and its unknown origin before the first public stop, the failure
  of the owner is reported and the exact thread of the owner is joined.
  The evidence directory of the group is the new one of the correction 09.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/report.md`
  (new) — this report.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/execution-plan.request.json`
  (new) — the frozen plan request.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/SHA256SUMS`
  (new) — the pins of the delivery.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/f5-evidence/README.md`
  (new) — the note of the directory in which the ten documents are written
  by the group itself.  The four documents that the batch of the root
  really wrote are in it.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/attempt01/`
  (new) — the raw evidence of the batch that ran: the three commands with
  their argv, their cwd and their exit codes, the two outer observations of
  the absence of the counter, the guard snapshot, the raw output of the
  batch, the receipt of the inherited runner and the report of the batch.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-09/f5-evidence/f5-*.json`
  (new) — the four bounded documents of the fifth failure that the group
  really wrote before its assertions.  The six documents that are missing
  are missing because the batch stopped.

No controller, no worker, no runtime, no driver, no supervisor, no
authorization record, no public schema, no threshold, no control document,
no manifest and no historical evidence was changed.  The five real
documents of the correction 08 were not touched and the refusal points of
the native path are kept.  The N2 work is not started.

## 10. The state of the delivery

* The claims of this delivery are **READY_FOR_REVIEW**.  They are not Stage
  PASS, not a native execution, not a native cleanup, not a released GPU,
  not a released port, not a sampler, not a parent crash recovery, not a
  Windows stdin EOF, not an admission and not a product gate 0.
* The six majors of the independent review stay **OPEN**.  This delivery
  proves neither their closure nor their persistence.
* The batch of the root ran **once** and it **failed** (section 11).  The
  next step is the decision of the root, the corrected candidate and the
  next frozen plan, and nothing else.

## 11. The batch that the root authorised: it ran once and it FAILED

Plan of the root:
`native-custody-correction-09/validation-plan-01/plan.json` (SHA256
`02f06ac7b43ad1e5ff401b4c4b442149e0ef3e21dd1bbe3c5ca5c00d80d05303`), ACK
`ACK_ONE_175_NODE_OFFLINE_BATCH_WITH_EXPLICIT_ORIGINAL_COUNTER_ABSENCE`
(`msg_806e6970083e`).  The batch ran **exactly once** under the guard of the
root and it **FAILED** with **one** failure: no rerun, no wrapper, no self
repair, no deleted case, no overwritten candidate.  The report of the batch
is `attempt01/execution-report.md`; the raw evidence is in `attempt01/` and
in `f5-evidence/`.

| Fact | Value |
|---|---|
| the frozen node ids | 175 (the 157 inherited in their original order and the 18 new ones) |
| collected | 175 — the order is **identical** to the frozen plan |
| passed | **174** |
| failed | **1** |
| skipped | 0 |
| pytest exit | **1** |
| duration | 40.22 s (the bound of the batch is 300 s) |
| cleanup proven for the batch | **true** |
| the runtime denials of the guard | **empty** |
| the preload | one `ctypes.dlopen(null)`, the window `CLOSED` before the candidate |
| the file descriptors before and after | the same three, no new, no reused, no unknown |
| the threads before and after | `['MainThread']` and `['MainThread']` |
| the counter of the root | `MISSING` before and after, the continuity `UNAVAILABLE_NOT_PROVEN` |

The one failure is the **new** observation of the external owner of the
cancel flag:

```
tools/test_v0_s3_native_custody_correction07.py:429: in run
    raise AssertionError(
E   AssertionError: the reader of the chain was never inside its read
```

The external owner waits for the explicit event that the reader of the
chain is really inside its read, the wait is bounded and its **return is
checked**.  The event `api.reader_blocked` is published by the façade of
the test only after the reader consumed the two published frames **and**
after the two bounded waits of the notification of the stop of the round
(`api.ready`, 30 s each, and the round of this group writes nothing), so it
is published about **sixty seconds** after the reader of the chain
started, while the bounded wait of the owner is **15 seconds**.  The owner
expired, it reported the failure to the owner of the test and the group
stopped **before** the first public stop of that sub scenario.  This is a
**preparation gap of the test** and not a defect of the production: the
production was never asked the question of the sub scenario.

The **order** that the correction 09 fixed is really fixed: the owner of
the test now waits for the confirmation of the owner and it checks the
flag and its unknown origin before the first public stop, the failure of
the owner is reported instead of being swallowed, and the exact thread of
the owner is joined.  The **event** that the owner waits for is the wrong
one and the choice of the right one belongs to the root.

The main oracle of the group is unchanged and it passed: the targeted
fault fired twice on the one original handle, the worker of the read
endpoint was retained after the first public stop, the second public stop
released the handle, retained no worker, released the broker without a
double close and **without a new deadline** (`2489.401969684` in the first
attempt, in the second attempt and in the salvage).
