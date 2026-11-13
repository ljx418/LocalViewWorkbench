# N1 correction 08: the correction of the five failures of the frozen batch of the correction 07, pending the new frozen batch and the new independent review

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_08_CORRECTION_OF_THE_FIVE_FAILURES`.

Failed candidate (frozen by the root): `23e27898253683164e7cb2918661b54258a29ce0`.
Evidence of the failed batch (frozen by the root): `b9347b688299d601c40eccd734b506f559b2bb79`
(`175 calls / 170 pass / 5 fail / 0 skip / pytest exit 1 / cleanup proven for the
batch = true`).

Root package: `reports/v0-s3/product-gate0/native-custody-correction-08`
(`contract.md`, `decision.json`, `failed-attempt01/execution-report.md`).
Parent package: `native-custody-correction-07` (the 18 frozen groups of the
new module) and its two parents `native-custody-correction-05` (24 frozen
groups) and `native-custody-correction-03` (16 frozen groups), both inherited
unchanged.

**This delivery is a static implementation.**  The candidate was **not**
imported, **not** collected, **not** run by pytest and no dynamic probe of
any kind was made.  No counter was read and no ledger was touched.  The
claims of this delivery stay **READY_FOR_REVIEW**.  They are **not** Stage
PASS, they are not a native execution, they are not a native cleanup, they
are not a released GPU, they are not a released port, they are not a
sampler, they are not a parent crash recovery, they are not a Windows stdin
EOF, they are not an admission and they are not a product gate 0.

**The six majors of the isolated review stay OPEN.**  This delivery corrects
five test groups and it diagnoses the fifth failure; it closes nothing by
itself.

## 1. What was read

The root package of the correction 08 was read in full before the first
edit: `contract.md`, `decision.json`, `implementation-prompt.md`,
`capacity.json`, `launch.json`, `predecessor-release.json`,
`temporary-retry-env.json`, `archive-index.json` and
`failed-attempt01/execution-report.md` together with the two counter
snapshots, the guard snapshot and the receipt of the inherited runner.

The governance layer was read before the sources: `AGENTS.md`,
`.agent-governance/README.md`, `plans/execution-control.json` and the
execution index `docs/24_EXECUTION_MASTER_PLAN.md`.  The three test modules
and the two production sources of the candidate were read in full.

The predecessor candidate was **not** changed, the passed batch of the
correction 06 was **not** reproduced and the failed batch of the correction
07 was **not** rerun.  The five failures are corrected statically, from the
frozen source and from the frozen report of the batch.

## 2. The erratum of the summary of the five failures

The report of the failed batch of the correction 07 closed with the summary
"four of the five failures are in the preparation of the tests and one of
them (F2) is a conflict between the design decision of the root and a
frozen oracle".  That summary is **not** the classification of the root and
it is corrected here, as the contract of the correction 08 requires:

| The failure | The classification of the correction 08 |
|---|---|
| **F1** `test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api` | a **clear preparation problem of the test**: the fault of the test was armed on the wrong moment of the lifecycle of the handle |
| **F3** `test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed` | a **clear preparation problem of the test**: the second scenario of the group reused the state of the first one |
| **F4** `test_n07_r06_the_cancellation_of_a_wait_reaches_the_top` | a **clear preparation problem of the test**: the group asserted an internal stage that the production does not publish |
| **F2** `test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` | a **conflict with the old oracle of the test**, not a preparation problem: the old group armed the round and refused only the launch, and the product obligation of the root has always been that **every** creation is refused before the deadline arrived |
| **F5** `test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner` | an **unlocated real combination failure**: the second public stop of the round did not release the broker and the raw evidence of the batch does not name the incomplete fact |

Three clear preparation problems of the tests, one conflict with an old
oracle and **one unlocated real combination failure**.  F5 is **not**
classified as a preparation problem: the conclusion "it is only a test
preparation error" is **not** adopted, the group stays **UNRESOLVED**, and
this delivery does **not** pretend that looking at the facts is a fix and it
does **not** pre-fill any missing fact.

The bytes of the report of the failed batch are sealed by the root and they
are **not** rewritten by this delivery; the erratum lives here.  The
receipt of the inherited runner of the root keeps its **inherited** file
name (`native-custody-correction-03.receipt.json`) and it is written into
the **new** run directory of this correction
(`implementation-native-custody-correction-08/attempt01/`).  The receipt of
the correction 03 stays in the report directory of the correction 05 and the
two documents are never mixed.

## 3. The four corrections of the tests

### 3.1 F1 — the first failing close of the control handle moves to the confirmed exit

`tools/test_v0_s3_native_custody_regressions.py`,
`test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api`.

The rule of the correction 07 keeps the **control handle** of a process
while its exit is not confirmed (`v0_s3_native_broker.py:900`
`_confirm_process_exit`, `:1379` the `if not confirmed:` branch of
`_release_created`).  The old group armed the first failing close of that
handle while the exit was still unproven, so the first attempt of the close
could not happen where the group expected it: the handle was still closed
by the confirmed recovery and the group failed on the second attempt.

The group now has three **named and bounded** phases and the number of the
attempts of the close of every handle is counted and asserted in every
phase:

| Phase | The trigger | The facts that are asserted |
|---|---|---|
| one | the exit is not confirmed | the original handle is kept, the close of the control handle was **never attempted** (the count of the attempts is `0`), the handle is still live |
| two | the exit is confirmed and the first close fails | the original handle keeps its owner, the failure of the close is **named** (`CloseHandle:...`), the count of the attempts is `1`, the handle is still live |
| three | the next close, inside the **same** original deadline | the handle is forgotten, it is not live any more, the count of the attempts is `2` |

The deadline of the recovery is published once and the group asserts that
the three phases share **one** deadline: the group can therefore never pass
because a retry happened to succeed, and it never needs an unbounded number
of retries.

### 3.2 F2 — the arm of an expired round is refused with nothing created

`tools/test_v0_s3_native_custody_correction05.py`,
`test_n05_r11_no_role_is_created_or_resumed_after_the_deadline`.

The decision of the root is kept: **the expired arm has no side effect**
(`v0_s3_native_broker.py:2128`, `check_startup_budget('ARM:JOB')` runs
before the creation of the job, and `:2158` checks the budget again after
it).  The **production check was not removed and the production bytes were
not touched**: the check of the budget before the creation of the job is
the behaviour that the root requires.

The **oracle of the old group** was corrected.  The old group armed the
round first and refused only the launch; that contradicts the obligation
that every creation is refused before the deadline of the round arrived,
and the arm of a round is a creation like every other one.  The group now
drives three named scenarios:

1. an arm whose deadline is still valid succeeds and the job of the round
   is created;
2. the **late create takeover** is kept exactly as it was: the creation of
   the role consumes the whole lease, the launch is refused, the process is
   never assigned and never resumed and the late resource is only cleaned
   up;
3. the arm of a round whose deadline already arrived is refused **inside**
   `pytest.raises` with the stable code `BROKER_STARTUP_DEADLINE_EXCEEDED`,
   and the group asserts that `create_job`, `set_job_kill_on_close`,
   `create_pipe`, `create_process_suspended`, `assign_process_to_job` and
   `resume_thread` were **never called**, that the façade of the primitives
   holds **no live handle**, that nothing was closed and that the run root
   of the round holds **no output**.

The identity, the order, the trigger and the number of the groups are
unchanged: 16, 24 and 18 test functions are still the exact functions of
the frozen plan and the 175 node ids of the plan are unchanged.

### 3.3 F3 — the cancellation scenario is an independent scenario

`tools/test_v0_s3_native_custody_correction07.py`,
`test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed`.

The second scenario of the group reused the `state` of the first one.  The
first scenario had already confirmed the exit of the process, so the
control handle was closed inside the creation and the recovery of the
façade had nothing left to coordinate: the cancellation of the recovery
could not be raised at all.

The second scenario now has **its own state, its own closures and its own
kernel**, and the group asserts three facts that the old group did not
assert at all:

* the injected cancellation of the termination **really happened**: the
  number of the terminations is counted and it is not zero;
* the cancellation that stays next to the primary error is the
  **original object** of the cancellation (`is`, not a copy of its
  message) and the primary error is still the error that leaves the
  creation (`BROKER_PROCESS_BIRTH_QUERY_FAILED`);
* the **control handle of the process is still recoverable**: it is named
  by the façade, it is the original handle of the process and it is still
  live after the recovery of the façade raised the cancellation.

### 3.4 F4 — the origin of the cancellation is proved, the internal stage is not invented

`tools/test_v0_s3_native_custody_correction07.py`,
`test_n07_r06_the_cancellation_of_a_wait_reaches_the_top`.

The contract froze the **propagation** of the cancellation and the fact that
its origin is verifiable.  It did **not** freeze the internal stage of the
failure: the production names the stage of the **group** of the processes
(`v0_s3_native_broker.py:2779`, the `except (KeyboardInterrupt, SystemExit)`
of `_wait_the_processes`) and the stage of the origin is not a stage that
the production publishes.

The group therefore names the stage that the production really publishes
(`wait`) and it proves the origin of the cancellation in three further
ways, so that the assertion is **not** weakened into "any cancellation is
acceptable":

* the number of the injections of the `exit_code` is recorded and it is
  not zero;
* the error that leaves the stop is the **original `SystemExit` object**
  that the façade injected (`is`, not a copy of its message);
* the order of the ledger of the façade proves that the wait of the
  process really completed **before** the exit code was read, so the origin
  is the exit code and not the wait;
* the processes that follow the cancelled one were still waited for and
  their original handles were really released.

The two sub paths drive **the actual production methods**
(`wait_process` and `exit_code`) separately, exactly as the frozen
obligation asks.

## 4. F5 — the real chain, a deterministic fault and the persisted facts

`tools/test_v0_s3_native_custody_correction07.py`,
`test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner`.

### 4.1 What the group does now

The **fault** of the group is deterministic now.  The old group armed a
global counter of two failing closes (`self.close_failures = 2`) and the
two workers of the two ends of the channel **competed** for it: the group
could not name the original handle that the round was not able to close
and the outcome depended on the order in which the two workers happened to
be scheduled.  The group now:

1. builds the **real** chain (`NativeCustodySession` -> `BrokerProcess` ->
   `StreamChannel` -> `_WindowsPipeEndpoint` -> `_WindowsPipeWorker`) with
   the in-process façade of the primitives, exactly as the frozen
   obligation asks; the real chain is never replaced by a hard coded set of
   facts and the `COMPLETE_CLOSE_FACTS` of the correction 05 are **not**
   used here;
2. designates **one definite original handle of the thread** of **one
   named worker** (the reader of the read end of the channel).  The handle
   is the first handle that the round allocated and the round really used
   it: the `READY` reply of the round was delivered through it.  The group
   asserts that the façade really allocated exactly that one handle
   before the fault was armed;
3. binds the fault to that **one** handle.  Before the owner of the test
   releases it, **only that handle** fails its close, with the stable code
   of the production façade (`BROKER_HANDLE_CLOSE_FAILED`).  Every attempt
   is written in a **ledger** of the façade;
4. runs the **first** public stop and asserts the facts of the first
   attempt: the fault really fired and it fired on the designated handle,
   the **unconfirmed item** is the original handle of the thread of the
   reader and it **kept its owner** (the endpoint still retains the worker
   and the worker still holds the original handle), the broker was not
   released, the incomplete facts are named and the items that were
   confirmed were closed exactly once;
5. **releases the fault** with an explicit act of the owner of the test
   (only the condition of the fault is cleared and nothing else of the
   round changes);
6. runs the **second** public stop and asserts the convergence: the
   channel was closed twice, the item that was not confirmed really
   succeeded, the items that were confirmed were **never closed twice**,
   the endpoint retains no worker any more, the **original deadline** of
   the cleanup was not reset and the broker is released by the facts of the
   close.

The oracle of the two convergences is kept exactly as the root froze it:
there is **no third stop and no loop of stops** in the oracle.  The only
other stop of the round is the **bounded salvage** of the owner of the
test in the `finally`, and it happens **after** the assertions.

### 4.2 The facts are persisted before every assertion

The contract requires the facts of the first attempt, of the second attempt
and of the salvage to be persisted as a bounded JSON document, and it
requires them to be written **before** the assertions, so that a group that
fails never depends on the representation of a failure of pytest.

The group writes three documents in
`reports/v0-s3/product-gate0/implementation-native-custody-correction-08/f5-evidence/`:

* `f5-first.json`, written before the assertions of the first attempt;
* `f5-second.json`, written before the assertions of the second attempt;
* `f5-salvage.json`, written by the `finally`, whatever the outcome was.

Every document is bounded and every value of it is the value that the
production returned.  Each document names:

* the whole **evidence of the round** (`session.evidence()`), with its
  failures, its state, its cleanup deadline and its generation of the
  close;
* the **facts of the close of the broker**, both the ones of the round
  (`broker_close_facts`) and the own ones of the handle (`close_facts`);
* the **facts of the close of the channel**, one document per close of the
  channel;
* the **facts of the read and of the write endpoint**, with the state of
  every worker (`alive`, `joined`, `state`, `error`) and with the identity
  of the **retained original handle of the thread** of every retained
  worker;
* the **ledger of the closes** of the façade, with the handle of every
  attempt and the fact that the attempt was the targeted fault, the number
  of the **targeted faults** that really fired and the handles that were
  really closed;
* the **original deadline** of the cleanup, before and after the second
  attempt.

### 4.3 The static reading of the fifth failure and the candidate production gap

The contract asks for the **static** reading of the chain and for the
facts to be made deterministically controllable, and it forbids the
conclusion "it is only a test preparation error".  The static reading of
the frozen source gives **one candidate** for the incomplete fact of the
second attempt.  It is a **candidate**: no dynamic observation was made
and it is **not** proven.

**The candidate.**  The reader of the channel is a **background thread**
(`StreamChannel._drain`, `v0_s3_native_broker.py:4084`).  When the round is
closed while the reader is still inside its read, the endpoint cancels the
read of its worker and the read leaves with the code
`BROKER_PIPE_CANCELLED` (`:3779`, the `raise` of `_await`) or with the code
`BROKER_CHANNEL_CANCELLED` (`:4137`, the `_check_wait`).  The drain thread
catches it and stores it **permanently** in the channel
(`:4125`, `self._error = getattr(error, 'code', None) or type(error).__name__`).
The close of the channel then reports it (`:4207`, `facts['reader_error'] =
self._error`), the handle of the broker copies it (`:4977`) and the round
of the parent treats **any** non empty reader error as an incomplete fact
(`v0_s3_native_custody.py:2053`, `if facts.get('channel_reader_error'):`).
The fact is **sticky**: the channel never clears `self._error`, so every
later close of the same channel reports the same reader error and the
parent can never release the broker.

**Why this is a plausible cause of the failed batch.**  The failed batch
proved that the channel was closed **twice** and that the second close was
still incomplete.  Under this candidate, the second close is incomplete
for exactly the same reason as the first one: the reader error of the
channel was set during the first close and it is never cleared.  The
cancellation of the read during a close is an **expected** fact of a close
and not an error of the round.

**The minimal proposal** (it is **not** applied by this delivery, the
production bytes are frozen and the current round does not authorise a
production modification): let the close of the channel distinguish the
cancellation of the round from an ordinary failure of the reader.  The
smallest change is in `StreamChannel.close`
(`v0_s3_native_broker.py:4170`): the reader error that is only the
cancellation of the close (`BROKER_PIPE_CANCELLED` and
`BROKER_CHANNEL_CANCELLED`) is **not** an error of the round and it is
reported as a named fact of the close instead of as the error of the
reader.  A second and even smaller candidate is in `StreamChannel._drain`
(`:4124`): the cancellation of the round is not caught as an ordinary
error of the reader.

**What this delivery does with this candidate.**  It does **not** fix it,
it does **not** weaken the oracle of the group to hide it and it does
**not** pre-fill any fact.  The group keeps the two-convergence oracle of
the root, and the three persisted documents name the **exact** incomplete
fact of the second attempt if the chain still does not converge.  The
adjudication of this candidate belongs to the root and it is asked together
with the frozen plan of the next batch.

**If the second attempt is still incomplete**, the delivery keeps the
complete evidence, reports the real production gap and it does **not**
repair the production to make the group green.

## 5. The static self-review

The static review of this delivery is a source review.  It is **not** a
measurement and it is **not** a native claim.

* The three changed modules were parsed with the abstract syntax tree of
  the host.  The parse succeeded for every file.
* A static name check of the three files (the module level names, the
  local names, the arguments, the comprehension variables, the exception
  names and the builtins) reports **no undefined name** in any file.
* The number of the test functions of the three modules is **16**, **24**
  and **18**: the identity, the order and the number of the frozen groups
  are unchanged and the 175 node ids of the frozen plan are unchanged.
* The three changed modules add **no** `time.sleep` and **no** polling
  loop: every wait of the corrected groups is an event wait or a bounded
  join of the production code.
* The production sources `tools/v0_s3_native_broker.py` and
  `tools/v0_s3_native_custody.py` keep their bytes: the candidate of this
  delivery changes **only** the three test modules and the new report
  directory.

What this delivery does **not** claim and what it did **not** do:

* the candidate was **not** imported, **not** collected and **not** run;
* no pytest, no runner, no guard and no dynamic probe of any kind was
  executed;
* no Windows API, no job object, no process, no service, no socket, no
  database, no network, no download, no media and no GPU was touched;
* the budget ledger and the shared counter were **not** read, **not**
  written and **not** reset;
* no agent was derived and no owner of another round was changed;
* the native claims of the package stay `NOT_PROVEN`.

## 6. The ten fields

* **Current coordinate**: R1 / WP-R1-U3 / RUNNING; the blocking gate of
  the round is `S3_P4_OFFLINE_INTEGRATION_AND_MACHINE_FIXTURE_BINDING_PENDING`
  and the gate of this correction is
  `S3_P4_N1_CORRECTION_08_CORRECTION_OF_THE_FIVE_FAILURES`.
* **What this batch completes**: the static correction of the five failures
  of the frozen batch of the correction 07 and the preparation of the
  deterministic diagnosis of the fifth one.  It closes **no** major.
* **The last passed gate**: `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`
  (candidate `621b1bf`), unchanged by this delivery.
* **The position in the global route**: V0-S0 1/2, V0-S1 5/5, R0 1/2, R1a
  5/5, V0-S2 7/8, V0-S3 0/6, R1 0/4, V1-M1 0/3, R2 0/4, R3 (V2) 0/4, R4
  (V2) 0/4, R5a (V3) 0/4, R5b (V3) 0/4, R5c (V3) 0/4.  The progress comes
  from the `development_outline` of `plans/execution-control.json` and from
  the real receipts; it is not a subjective percentage.
* **The remaining work**: the frozen batch of the root, the isolated
  review, the human signature, the native Windows run, I24, the twelve
  product cases and A06.  The N2 work is not started.
* **The next owner**: the gate owner of the root and the independent
  review.
* **The required authorization**: the static implementation of this
  delivery is the work of the frozen workpack.  The **dynamic** execution
  is not authorized and it is requested from the root by the finite plan of
  the delivery.
* **The evidence directory**:
  `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/`.
* **The exact reason of the stop**: the static implementation, the static
  self-review and the persisted evidence of the fifth failure are
  complete.  No dynamic execution was performed, no ACK was requested and
  no rerun, no wrapper, no self repair and no overwrite of a candidate
  happened.
* **The claims**: READY_FOR_REVIEW.  Not Stage PASS.  The six majors of the
  independent review stay **OPEN**.

## 7. The frozen plan that is asked of the root

The delivery asks for exactly **one** finite dynamic batch and it is
described in the plan request of this directory.  It carries the candidate
SHA, the pins of the sources and of the tools, the ordered and frozen set
of the node ids (the 157 inherited ones in their original order and the 18
new ones), the guard and the runner of the root, the absolute argv and the
absolute cwd, a single batch of at most 300 seconds, the raw output of
every node, the exit code, the real identity of the file descriptors and
the state of every thread before and after the batch.

The **tools** of the next batch are the ones of the **new** directory
`native-custody-correction-08/validation-plan-01` that the root places with
the same bytes as the tools of the correction 07.  The plan request points
at that directory and it never points at the plan of the correction 05 or
of the correction 07, which are never overwritten and never executed
again.

The boundary of the batch is the one of the predecessor: the guard precedes
the candidate and pytest, the only permitted preload is the single
`ctypes.dlopen(None)` of the trusted standard library and it is closed
before the candidate, the counter is read once before and once after the
batch and it is neither written, nor reset, nor refunded, nor revived, and
the FIRST approval that is refused or that times out stops the batch
without a wrapper.  The runtime denials of the guard, the identity of the
file descriptors and the state of the threads are **expectations** of the
batch: they are written in the report of the batch and nowhere else,
because they were not observed.

The ask carries **two** items for the root: the frozen plan of the single
batch of the 175 node ids in their original order, and the **adjudication
of the candidate production gap** of the fifth failure with the minimal
proposal of the section 4.3.  The production bytes are frozen and this
delivery did not touch them.

## 8. The files of this delivery

* `tools/test_v0_s3_native_custody_regressions.py` (changed) — the group
  **F1** with the three named and bounded phases.
* `tools/test_v0_s3_native_custody_correction05.py` (changed) — the group
  **F2** with the three named scenarios and the corrected oracle.
* `tools/test_v0_s3_native_custody_correction07.py` (changed) — the groups
  **F3**, **F4** and **F5**, the helpers of the persisted facts and the
  evidence directory of the fifth failure.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/report.md`
  (new) — this report.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/execution-plan.request.json`
  (new) — the frozen plan request.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/SHA256SUMS`
  (new) — the pins of the delivery.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/f5-evidence/README.md`
  (new) — the note of the directory in which the facts of the fifth
  failure are written by the group itself.

No controller, no worker, no runtime, no driver, no supervisor, no
authorization record, no public schema, no threshold, no control document,
no manifest and no historical evidence was changed.  The refusal points of
the native path are kept and the N2 work is not started.
