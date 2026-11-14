# N1 correction 08: the correction of the five failures of the frozen batch of the correction 07, the two minimal production classifications that the root authorised, pending the new frozen batch and the new independent review

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_08_CORRECTION_OF_THE_FIVE_FAILURES`.

Failed candidate (frozen by the root): `23e27898253683164e7cb2918661b54258a29ce0`.
Evidence of the failed batch (frozen by the root): `b9347b688299d601c40eccd734b506f559b2bb79`
(`175 calls / 170 pass / 5 fail / 0 skip / pytest exit 1 / cleanup proven for the
batch = true`).

Root packages: `reports/v0-s3/product-gate0/native-custody-correction-08`
(`contract.md`, `decision.json`, `failed-attempt01/execution-report.md`),
`reports/v0-s3/product-gate0/native-custody-correction-08/close-cancellation-decision-01/decision.json`
(`AUTHORIZE_MINIMAL_LOCAL_CLOSE_CANCELLATION_CLASSIFICATION_STATIC_ONLY`, message
`msg_228a371bfcb9`) and
`reports/v0-s3/product-gate0/native-custody-correction-08/error-evidence-preservation-01/decision.json`
(`STATIC_FIX_CONFIRMED_READER_ERROR_LOSS_BEFORE_TEST_ACK`, message
`msg_acdc1649d945`).  The two **reply bodies** of those two decisions are part
of the package and they were read in full: the second one appends the
minimal correction of the **loss of the reader error** and the counter
examples that prove it.
Parent packages: `native-custody-correction-07` (the 18 frozen groups of the
new module) and its two parents `native-custody-correction-05` (24 frozen
groups) and `native-custody-correction-03` (16 frozen groups), both inherited
unchanged.

**This delivery is a static implementation.**  The candidate was **not**
imported, **not** collected and **not** run by pytest **by the
implementation**.  The batch that the root authorised afterwards ran
**exactly once** under the guard of the root and it **FAILED** with one
failure; the report of that batch is section 11 and the raw evidence of it
is in `attempt02/`.  The counter of the root was **not** read: it was
**MISSING** before the batch and it is **MISSING** after it, its historical
continuity is `UNAVAILABLE_NOT_PROVEN` and no ledger was touched.  The
claims of this delivery stay **READY_FOR_REVIEW**.  They are **not** Stage
PASS, they are not a native execution, they are not a native cleanup, they
are not a released GPU, they are not a released port, they are not a
sampler, they are not a parent crash recovery, they are not a Windows stdin
EOF, they are not an admission and they are not a product gate 0.

**The six majors of the isolated review stay OPEN.**  This delivery corrects
five test groups and it applies the two minimal production classifications
that the root authorised; it closes nothing by itself.

## 1. What was read

The root package of the correction 08 was read in full before the first
edit: `contract.md`, `decision.json`, `implementation-prompt.md`,
`capacity.json`, `launch.json`, `predecessor-release.json`,
`temporary-retry-env.json`, `archive-index.json` and
`failed-attempt01/execution-report.md` together with the two counter
snapshots, the guard snapshot and the receipt of the inherited runner.  The
decision of the root on the close cancellation was read in full before the
first production edit, together with its whole reply.  The **second**
decision of the root, on the preservation of the reader error, was read in
full before the second production edit, together with its whole reply and
with its `decision.json`: it authorises the minimal correction of the loss
of the reader error and it adds the counter examples that prove it.

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
the correction 03 itself lives in the **own** report directory of the
correction 03
(`implementation-native-custody-correction-03/native-custody-correction-03.receipt.json`).
The correction of this report: the inherited name of the runner is the name
of the **writer** of the file and it does **not** place the receipt of the
correction 03 in the report directory of the correction 05.  Every run
directory carries its **own** run of the inherited runner and the two
documents are never mixed.

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
it).  The **production check was not removed and the production bytes of
that check were not touched**: the check of the budget before the creation
of the job is the behaviour that the root requires.

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

**These documents do not exist yet.**  Nothing was run: the batch of the
root was not executed and the group was never called.  The table below is
the list of the **expected product paths** of the next batch, not a list of
facts that were observed.  The only file of that directory that exists
today is the note of the directory itself
(`f5-evidence/README.md`).  Every document of the table is written by the
group **during** the next batch and it becomes raw evidence of that batch
only when the batch really ran.

The group writes its documents in
`reports/v0-s3/product-gate0/implementation-native-custody-correction-08/f5-evidence/`:

| The document | It is written |
|---|---|
| `f5-first.json` | before the assertions of the first public stop |
| `f5-second.json` | before the assertions of the second public stop |
| `f5-salvage.json` | by the `finally` of the group, whatever the outcome was |
| `f5-close-cancellation.json` | before the assertions of the first sub scenario |
| `f5-unrelated-cancellation.json` | before the assertions of the second sub scenario |
| `f5-unrelated-cancellation-second.json` | before the assertions of the **second** public stop of the second sub scenario |
| `f5-read-fault.json` | before the assertions of the third sub scenario |
| `f5-read-fault-second.json` | before the assertions of the **second** public stop of the third sub scenario |
| `f5-partial-frame.json` | before the assertions of the fourth sub scenario |
| `f5-partial-frame-second.json` | before the assertions of the **second** public stop of the fourth sub scenario |

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

### 4.3 The four bounded sub scenarios of the reader of the channel

The decision of the root requires at least three **real production
behaviours** of the reader of the channel inside the existing group, and
it forbids the deletion of an original assertion.  The node id of the
group and the order of the 175 node ids are unchanged and every original
assertion of the group is kept.  The four sub scenarios are bounded, each
of them builds its **own** real chain, each of them writes its facts
**before** its assertions and each of them ends with a bounded salvage of
the owner of the test:

| Sub scenario | What it drives | What it proves |
|---|---|---|
| one | the reader is still inside its read when the round is closed and the close cancels it | the cancellation that the close really initiated is a **named fact of the close** with its code, its source and its order; it is **not** the error of the reader; the **strict** facts of the close are the ones that prove the release and the broker is really released |
| two | another owner of the cancel flag of the channel sets it and names no owner | a cancellation with the **same code** whose owner is another one keeps the error of the reader, the close never takes it for its own cancellation and the round stays **unknown** |
| three | the read fails with an ordinary error | the ordinary failure of the read keeps its error and the round stays **unknown** |
| four | the stream ends in the middle of a frame | the partial frame keeps its named error and it is never dropped as a normal end; the round stays **unknown** |

The three sub scenarios that carry a **real error of the reader** drive
**two consecutive public stops** of the round, as the second decision of the
root requires.  The second attempt of the close copies the facts of the
first one: the counter example is the **copy** itself, because a copy that
dropped the error of the reader would release the broker of the round
without a proof.  The group therefore asserts, after the second public
stop and **before** any assertion of it is evaluated against a written
document:

* the error of the reader is **still there**, with the same code
  (`BROKER_PIPE_CANCELLED`, `RuntimeError` and
  `BROKER_CHANNEL_PARTIAL_FRAME` respectively);
* the **source** of the error is named and it is `REPEATED_CLOSE`: the
  second attempt carries the error of the first one instead of observing a
  new one;
* the round is still **unknown** (`UNKNOWN_RETAINED`) and the broker of the
  round is **still kept**: the second attempt may never release the broker
  because it copied the facts of the first one;
* the failure of the second attempt **names** the incomplete fact
  (`CUSTODY_BROKER_CLOSE_INCOMPLETE:channel_reader_error`).

The fault proof of every sub scenario is written on the disk **before** the
salvage of the owner of the test, exactly like the three phases of the
group itself.

## 5. The two minimal production changes that the root authorised

`tools/v0_s3_native_broker.py` is the **only** production file that this
delivery touches, and it is the file that the two decisions of the root
authorised (`additional_allowed_production_file` and
`allowed_files`).  The custody
(`tools/v0_s3_native_custody.py`), the broker core, the launcher, the
owners of the older rounds, the public contract, the strict required facts
and the quality thresholds are **frozen and untouched**.

### 5.1 The defect that the root confirmed statically

The decision of the root confirmed the defect statically:
`StreamChannel.close` sets the cancel flag of the channel, the `except` of
`StreamChannel._drain` writes the corresponding `BrokerError` **permanently**
into the error of the reader, and the sticky reader error then prevents the
release of the round.  The decision of the root states at the same time
that this defect is a **local** one and that it is **not** proven to be the
complete root cause of the failure of the last batch: the new facts of the
first and of the second attempt are the ones that may complete the
diagnosis.  **This delivery does not claim otherwise.**

### 5.2 What the minimal change is

The change is a **classification**, not a relaxation:

* the cancel flag of the channel is a private `_ChannelCancel` that names
  the **owner** that set it.  The owner is written under the lock of the
  flag and it is written **before** the flag is set, so a reader can never
  see the flag set without its owner.  The **first** owner wins: a flag
  that another owner already set is never re-labelled by a later one;
* the close of the channel publishes the **identity** of the close that is
  running now **before** it initiates the cancellation, and it registers
  that identity as the owner of the flag in the same atomic step as the
  setting of the flag;
* the error of the cancellation carries the owner of the flag **at the
  origin of the error**: `_WindowsPipeEndpoint._await` and
  `StreamChannel._check_wait` stamp it on the error they raise.  The
  source is never a claim of a caller and it is never a boolean that a
  test double hands over;
* the reader of the channel classifies an error: a cancellation whose owner
  is the close of this channel is a **named fact of the close** (its code,
  its source and its order) and it is **not** the error of the reader.
  Every other error keeps the original error of the reader;
* the close of the channel publishes the named fact of its own
  cancellation next to the error of the reader, and the handle of the
  broker carries it in its facts so that the evidence of the round names
  it.

### 5.3 What the change explicitly does **not** do

* it does **not** clear a historical error of the reader and it does
  **not** replace it: an error that was already there before the close
  stays and the round stays unknown;
* it does **not** discard the partial buffer of the channel: the
  `finally` of the drain is untouched and a frame that never ends is
  still the named failure `BROKER_CHANNEL_PARTIAL_FRAME`;
* it does **not** force `reader_error` to `None` and it does **not** force
  a close to `True`: the named fact of the close replaces the error of the
  reader **only** when the owner of the cancellation is provably the close
  of this channel, and every strict success fact is still computed from
  the real state of the reader, of the endpoints, of the workers and of
  their handles;
* it does **not** take a cancellation for a normal one because of the name
  of its code and it does **not** take any cancellation of the round for a
  normal one: a cancellation whose owner is unknown or is another owner
  keeps the error of the reader;
* it does **not** change the public error codes, it does not add a new
  platform and it does not change the strict required facts of the
  custody.

### 5.4 The second minimal production change: the error of the reader is a history

The **second** decision of the root
(`STATIC_FIX_CONFIRMED_READER_ERROR_LOSS_BEFORE_TEST_ACK`,
`msg_acdc1649d945`) confirmed **statically** a second, independent defect
of the same major (M09, the anti false green obligation) and it authorised
the minimal correction of it inside the same broker file.

**The defect.**  `BrokerProcess.close` initialises
`channel_reader_error` to `None` and it copies the facts of a previous
attempt of the close with a rule that keeps the facts that are `True`: a
reader error is a **code** and it is therefore not copied.  The second
public stop of a round reaches `BrokerProcess.close` again, the channel was
already closed and `_channel_complete` confirms every **resource** item of
it, so the channel is **not** closed again and no new fact of the reader
is observed.  The facts of the second attempt therefore carry
`channel_reader_error = None` while the reader of the channel really had
an error.  `NativeCustodySession._perform_close` checks that field: an
empty one is not an incomplete fact, the parent releases the broker of the
round and the round leaves the unknown state **without a proof**.  A real
error of the reader of the channel is thus lost by the retry and the round
claims a release that it cannot prove.

**The minimal correction.**  `BrokerProcess.close` keeps the **history** of
the error of the reader:

* the first error that the reader really had is the error of the round and
  every later close keeps it: the copy of the facts of the previous
  attempt is completed by the history itself and a repeated close never
  turns a real error into a `None`;
* a later error is a **secondary** error: it is kept beside the first one
  (`channel_reader_secondary_errors`) and it never replaces it;
* the **source** of the error is published with it
  (`channel_reader_error_source`): `FIRST_CLOSE` when the close that runs
  now is the one that observed the error and `REPEATED_CLOSE` when the
  attempt carries the error of an earlier one;
* the named fact of the cancellation of the close is **independent** from
  this history and it is never merged with it: a cancellation that the
  close of this channel really initiated is still not an error of the
  reader.

**What the change explicitly does not do.**

* it does **not** relax the strict facts of the custody and it does **not**
  clear an error to release a broker: the check of
  `NativeCustodySession._perform_close`
  (`if facts.get('channel_reader_error'):`) is untouched and the round
  stays unknown exactly as it stayed after the first attempt;
* it does **not** force a success: the resource facts of the close are
  still computed from the real state of the reader, of the endpoints, of
  the workers and of their handles;
* it does **not** copy a boolean: the code of the error itself is kept and
  the source of the error is named;
* it does **not** touch the public contract, the error codes, the strict
  required facts and the thresholds.

The observation of the previous revision of this report — that the copy of
the facts of a previous attempt does not keep a reader error that is a
code — is therefore **no longer an observation**: the root adjudicated it
and it is a defect of the production, and this delivery corrects it.

**What this correction does not claim.**  The two defects that the root
confirmed statically are **local** ones.  They are **not** claimed to be
the complete root cause of the fifth failure of the last batch: the
diagnosis of the fifth one is completed by the **raw facts of the first and
of the second attempt** of the next batch, and this delivery does not
pre-fill any of them and it does not claim that the fifth failure is
closed.

## 6. The static self-review

The static review of this delivery is a source review.  It is **not** a
measurement and it is **not** a native claim.

* The three changed modules and the changed production module were parsed
  with the abstract syntax tree of the host.  The parse succeeded for
  every file.
* A static name check of the four files (the module level names, the local
  names, the arguments, the comprehension variables, the exception names
  and the builtins) reports **no undefined name** in any file.
* The number of the test functions of the three test modules is **16**,
  **24** and **18**: the identity, the order and the number of the frozen
  groups are unchanged and the 175 node ids of the frozen plan are
  unchanged.
* The three changed modules add **no** `time.sleep` and **no** polling
  loop: every wait of the corrected groups is an event wait or a bounded
  join of the production code.
* The custody module `tools/v0_s3_native_custody.py` keeps its bytes and
  the change of `tools/v0_s3_native_broker.py` is limited to the
  `StreamChannel`, to the private identity of the cancellation, to the one
  new fact of the handle of the broker and to the history of the error of
  the reader inside `BrokerProcess.close`.

What this delivery does **not** claim and what it did **not** do:

* the implementation itself did **not** import, **not** collect and **not**
  run the candidate: the batch of section 11 is the one that the root
  authorised and it ran under the guard of the root;
* no pytest, no runner, no guard and no dynamic probe of any kind was
  executed **by the implementation**;
* no Windows API, no job object, no process, no service, no socket, no
  database, no network, no download, no media and no GPU was touched;
* the budget ledger and the shared counter were **not** read, **not**
  written and **not** reset: the counter was **MISSING** before the batch
  and it is **MISSING** after it and the old grant stays
  `EXPIRED_NO_REPLAY`;
* no agent was derived and no owner of another round was changed;
* the native claims of the package stay `NOT_PROVEN`.

## 7. The ten fields

* **Current coordinate**: R1 / WP-R1-U3 / RUNNING; the blocking gate of
  the round is `S3_P4_OFFLINE_INTEGRATION_AND_MACHINE_FIXTURE_BINDING_PENDING`
  and the gate of this correction is
  `S3_P4_N1_CORRECTION_08_CORRECTION_OF_THE_FIVE_FAILURES`.
* **What this batch completes**: the static correction of the five failures
  of the frozen batch of the correction 07, the two minimal production
  corrections that the root authorised (the classification of the close
  cancellation and the preservation of the history of the error of the
  reader) and the deterministic diagnosis of the fifth one.  It closes
  **no** major.
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
  delivery is the work of the frozen workpack and the two production
  changes are the ones that the two decisions of the root authorised.  The
  **dynamic** execution is not authorized and it is requested from the root
  by the finite plan of the delivery.
* **The evidence directory**:
  `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/`.
* **The exact reason of the stop**: the static implementation, the two
  minimal production corrections, the static self-review and the
  preparation of the persisted evidence of the fifth failure are complete,
  and the batch that the root authorised ran **exactly once** and **failed**
  with one failure (section 11).  There was no rerun, no wrapper, no self
  repair and no overwrite of a candidate, and the correction of the one
  failure belongs to the root.
* **The claims**: READY_FOR_REVIEW.  Not Stage PASS.  The six majors of the
  independent review stay **OPEN**.

## 8. The frozen plan that is asked of the root

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

The ask carries the frozen plan of the single batch of the 175 node ids in
their original order.  It carries **no** new production request: the two
production changes of this delivery are the ones that the two decisions of
the root already authorised, and the candidate of the previous round
(`a9183e6`), the candidate of the round before it (`ada50e3`), the
candidate of the failed batch (`23e2789`) and the receipts of the failed
batch are all preserved and none of them is overwritten.

## 9. The files of this delivery

* `tools/v0_s3_native_broker.py` (changed) — the two minimal production
  corrections that the root authorised: the private `_CloseSource`, the
  private `_ChannelCancel`, the source of the cancellation at the origin of
  the error, the named fact of the close in the facts of the channel and of
  the handle of the broker, and the **history of the error of the reader**
  inside `BrokerProcess.close`.
* `tools/test_v0_s3_native_custody_regressions.py` (changed) — the group
  **F1** with the three named and bounded phases.
* `tools/test_v0_s3_native_custody_correction05.py` (changed) — the group
  **F2** with the three named scenarios and the corrected oracle.
* `tools/test_v0_s3_native_custody_correction07.py` (changed) — the groups
  **F3**, **F4** and **F5**, the helpers of the persisted facts, the
  evidence directory of the fifth failure, the four bounded sub scenarios of
  the reader of the channel and the **second public stop** of the three sub
  scenarios that carry a real error of the reader.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/report.md`
  (new) — this report.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/execution-plan.request.json`
  (new) — the frozen plan request.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/SHA256SUMS`
  (new) — the pins of the delivery.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/f5-evidence/README.md`
  (new) — the note of the directory in which the facts of the fifth
  failure are written by the group itself.  The **ten** documents of that
  directory are **expected product paths** of the next batch: they are
  written by the group when the batch really runs and they do **not** exist
  today.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/attempt01-not-run-01.md`
  and `attempt01-not-run-01.commands.json` (new) — the record of the first
  plan of the correction 08, whose three commands were **NOT RUN** because
  the exact temporary counter of its argv was missing.  The ACK of that
  plan was withdrawn before any valid batch began.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/attempt02/`
  (new) — the raw evidence of the batch that ran: the three commands with
  their argv, their cwd and their exit codes, the two outer observations of
  the absence of the counter, the guard snapshot, the raw output of the
  batch, the receipt of the inherited runner and the report of the batch.
* `reports/v0-s3/product-gate0/implementation-native-custody-correction-08/f5-evidence/f5-*.json`
  (new) — the five bounded documents of the fifth failure that the group
  really wrote before its assertions.  The five documents that are missing
  are missing because the batch stopped at the failed assertion.

No controller, no worker, no runtime, no driver, no supervisor, no
authorization record, no public schema, no threshold, no control document,
no manifest and no historical evidence was changed.  The refusal points of
the native path are kept and the N2 work is not started.

## 10. The batch that the root authorised: it ran once and it FAILED

Plan of the root:
`native-custody-correction-08/validation-plan-02/plan.json` (SHA256
`0e6c5fceaf017618dc53ab5b42f4d44bace38879c374a193fc30ff151a169696`), ACK
`ACK_ONE_175_NODE_OFFLINE_BATCH_WITH_EXPLICIT_ORIGINAL_COUNTER_ABSENCE`.
The batch ran **exactly once** under the guard of the root and it
**FAILED** with **one** failure: no rerun, no wrapper, no self repair, no
deleted case, no overwritten candidate.  The report of the batch is
`attempt02/execution-report.md`; the raw evidence is in `attempt02/` and in
`f5-evidence/`.

| Fact | Value |
|---|---|
| collected | 175, in the frozen order (`collected == selected`) |
| passed / failed / skipped | **174** / **1** / 0 |
| pytest exit | 1 |
| duration | 35.37 s (bound 300 s) |
| cleanup proven for the batch | **true** |
| the failing node | `tools/test_v0_s3_native_custody_correction07.py::test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner` |

**Location.**  The failure is in the **second bounded sub scenario** of that
group, at `tools/test_v0_s3_native_custody_correction07.py:1787`: the one
that drives a cancellation with the **same code** whose owner is **another**
one.

**Cause.**  The raw facts of the phase
(`f5-evidence/f5-unrelated-cancellation.json`) say that the **close of the
channel initiated** the cancellation (`close_cancellation =
{code: BROKER_PIPE_CANCELLED, source: CHANNEL_CLOSE, sequence: 1}` and
`reader_error = None`).  The owner thread of the test sets the cancel flag
only after it observed the reader inside its read, and that observation
happens **during** the exchange of the stop, i.e. **concurrently** with the
close: the close and the owner compete for the flag and the close won it.
The external cancellation therefore **never arrived first**, and the raw
fact `CHANNEL_CLOSE` **cannot** prove that an external cancellation was
swallowed.  The premise of the negative case was not ordered by the test.

**What the batch does prove.**  The **main** oracle of the group — the
real chain, the targeted fault of **one** original handle of the thread of
**one** named worker and the **two** convergences — **passed**: the fault
fired on that one handle, the worker was retained and its handle was not
released after the first public stop, and after the explicit release of
the fault the second public stop released the handle, retained no worker
and released the broker, without a double close and without a new
deadline.  The complete root cause of the failure of the last batch is
**not** claimed.

**The sub scenarios that did not run** stay `NOT_RUN`: the second stop of
the unrelated cancellation, the read fault and its second stop, and the
partial frame and its second stop.  The group stopped at the failed
assertion; the five documents that were written are the raw evidence and
the five that are missing are missing because the batch stopped.

**The boundary held**: the guard preceded the candidate and pytest, the
runtime denials are empty, the single trusted preload is one
`ctypes.dlopen(null)` closed before the candidate, the file descriptors
before and after are the same three with no new or reused descriptor, and
the threads are `MainThread` only.  The counter of the root was **MISSING**
before the batch and it is **MISSING** after it, its historical continuity
is `UNAVAILABLE_NOT_PROVEN`, no digest is claimed to be equal and no
balance is claimed to be verified, the facts of the old receipt stay the
facts of that receipt and the old grant stays `EXPIRED_NO_REPLAY`.

**Next step.**  The correction of the ordering of that negative case is a
change of the test module and it belongs to the root: no repair and no
rerun was made here.  The six majors stay **OPEN**, the claims stay
**READY_FOR_REVIEW**, they are not Stage PASS, no N2 work was started and
no real run happened.
