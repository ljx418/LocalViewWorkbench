# N1 correction 07: the one frozen batch of the correction 07, FAILED

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_07_LIFECYCLE`.

Candidate: `23e27898253683164e7cb2918661b54258a29ce0`.
Frozen plan of the root:
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-07/validation-plan-01/plan.json`
(SHA256 `0fe1bea3c447444539d69d9ffc6a01c79cdc133b1594b7257c7c7b40085467db`).
Root ACK: `ACK_ONE_FROZEN_175_NODE_OFFLINE_BATCH` (`msg_552383887526`).

**The batch was executed exactly once and it FAILED.**  There was no rerun,
no wrapper, no self repair, no deleted case and no overwritten candidate.  The
candidate and the evidence of this batch stand exactly as they are.

## 1. The result of the batch

| Fact | Value |
|---|---|
| the frozen node ids | 175 (the 157 inherited in their original order and the 18 new ones) |
| collected | 175 — the order is **identical** to the frozen plan (`collected == selected`) |
| passed | 170 |
| failed | **5** |
| skipped | 0 |
| functional pass count | 168 (the two integrity only nodes are counted apart) |
| pytest exit | **1** |
| duration | 24.51 s (the bound of the batch is 300 s for the whole batch) |
| cleanup proven for the batch | **true** |

**The receipt of this batch is written into
`reports/v0-s3/product-gate0/implementation-native-custody-correction-07/attempt01/native-custody-correction-03.receipt.json`.**
That is the file name that the inherited runner of the root writes and it is
**not** the receipt of the correction 03: the receipt of the correction 03
lives in the report directory of the correction 05 and it is a different
document.  The two are never mixed here.

## 2. The five failures and their cause

The five failures are analysed **statically**, from the frozen source and
from the report of the node.  Nothing was rerun to find them.

### F1 — `tools/test_v0_s3_native_custody_regressions.py::test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api`

```
tools/test_v0_s3_native_custody_regressions.py:578: assert report[0]['released'] is True
E   assert False is True
```

**Cause (test side).**  The group drives the script `fail_close`, which makes
the **first** close attempt of the process handle and of the thread handle
fail.  The rule of the correction 07 keeps the control handle of the process
until its exit is confirmed, so the **first** close attempt of that handle now
happens inside `release_retained` instead of inside `_release_created`.  The
second recovery of the group therefore still meets the failing first attempt
and it does not release the handle: a third recovery (the second attempt of
the close) releases it.  The oracle of the group itself holds — the handle is
kept while the exit is not confirmed and it is released by a confirmed exit —
but the number of the recoveries that the group drives is one too small.

### F2 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r11_no_role_is_created_or_resumed_after_the_deadline`

```
tools/test_v0_s3_native_custody_correction05.py:925: core.arm()
tools/v0_s3_native_broker.py:2128: in arm → self.check_startup_budget('ARM:JOB')
E   tools.v0_s3_native_broker.BrokerError: BROKER_STARTUP_DEADLINE_EXCEEDED
```

**Cause (a conflict between the design decision of the root and the frozen
oracle of the group).**  The second part of the frozen group binds the
absolute deadline to `999.0` — a deadline that has already passed — and then
calls `core.arm()` **outside** of `pytest.raises`, so the arm of the round
has to succeed; only the **launch** may be refused afterwards.  The design
decision of the root says that every side effect is checked **before** and
after it happens and it names `arm` explicitly.  The check that the
correction 07 added before the creation of the job therefore refuses the arm
of a round whose deadline has already passed.

The two rules cannot both hold.  The decision belongs to the root: either the
frozen group is strengthened (the arm is refused as well and **nothing at all**
is created, which is strictly stronger than the frozen oracle) or the check
before the creation of the job is dropped from `arm` and the arm is checked
only after the job exists.  This delivery did **not** choose: the batch failed
and the correction of the next round belongs to the root.

### F3 — `tools/test_v0_s3_native_custody_correction07.py::test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed`

```
tools/test_v0_s3_native_custody_correction07.py:246: with pytest.raises(KeyboardInterrupt):
E   Failed: DID NOT RAISE <class 'KeyboardInterrupt'>
```

**Cause (test side).**  The second part of the group reuses the closure
`timeout_wait`, whose flag `state['exited']` was set to `True` by the first
part of the same group.  The exit of the process is therefore **confirmed**
in the second part, the control handle is closed inside `_release_created`
and the holding table of the façade is empty when the recovery runs: the
recovery has nothing to coordinate and it raises no cancellation.  The flag
of the group has to be reset before its second part.

### F4 — `tools/test_v0_s3_native_custody_correction07.py::test_n07_r06_the_cancellation_of_a_wait_reaches_the_top`

```
tools/test_v0_s3_native_custody_correction07.py:547:
    assert any(item['stage'] == 'exit_code' for item in cancellations)
E   assert False
```

**Cause (test side).**  The cancellation of the exit code **reaches the top**
— that is the oracle of the group and it holds: `BrokerCore.stop` raises the
`SystemExit` and the group sees it.  But the failure is named by
`_wait_the_processes` with the stage `wait` (the stage of the **group** of
the processes) and not with the stage of its origin.  The assertion of the
group names a stage that the production never produces.

### F5 — `tools/test_v0_s3_native_custody_correction07.py::test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner`

```
tools/test_v0_s3_native_custody_correction07.py:1331: assert session.broker is None
E   assert <BrokerProcess object> is None
```

**Cause (to be observed).**  The second public stop of the round **did**
coordinate the channel again — the group proved it: the channel was closed
twice and the assertion of the group on the number of the closes passed.  The
facts of that second close were nevertheless **incomplete**, so the parent
kept the broker with its owner and the round stayed unknown.  The receipt of
the runner carries the reports of the nodes and **not** the evidence of the
session, and the evidence of the session is where the name of the incomplete
fact lives: it is **not** in the evidence of this batch and this report does
not invent it.

From the static reading, the fact that is still missing is the one of the
**original handle of the thread of a worker of an endpoint**: the stand-in
fails the first two closes of a handle of a thread and the order of the
closes of the read worker and of the write worker is decided by two threads
(the drain of the channel and the stop of the round), so the group cannot
assume which worker keeps its handle.  The next correction has to **observe**
the name of the incomplete fact — for example by reading the evidence of the
session inside the group — and it must not assume it.

## 3. The boundary of the batch

The boundary held and it is proven by the evidence of the batch.

* The guard of the root **preceded** the candidate and pytest
  (`guard_precedes_candidate_and_pytest: true`).  Its self test denied the
  eight prohibited events and the **runtime denials are empty**: no
  `subprocess.Popen`, no socket, no fork, no exec, no system, no
  `sqlite3.connect`, no `dlopen` and no `dlsym` happened during the batch.
* The single trusted preload is the one that the plan allows:
  `ctypes.dlopen` with the name `null`, **one** event, and the window was
  `CLOSED` before the candidate and before pytest
  (`window_closed_before_candidate: true`).  It was never reopened.
* The file descriptors before and after the batch are the **same three**:
  `0` is `(dev 6, ino 4, mode 8630)` and `1` and `2` are
  `(dev 2112, ino 2921804 / 2921805, mode 33188)` before and after.  The
  descriptor `3` was filtered, there is **no** unknown descriptor and there
  is **no** new or reused descriptor.
* The threads before and after the batch are `['MainThread']` and
  `['MainThread']`: no thread of the round was left behind.
* The counter of the root was read **once** before and **once** after the
  batch, outside of the guarded batch.  The two reads are byte identical:
  the digest is still
  `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`,
  `active` is `false`, `starts_total` is 28, `reserved_wall_seconds` is
  240.0, `spent_wall_seconds` is 12.362 and the charges are the same.  The
  counter was **not** written, **not** refunded, **not** reset, **not**
  replaced and no old grant was revived.

## 4. The state of the delivery

* The candidate `23e27898253683164e7cb2918661b54258a29ce0` stands exactly as
  it was verified by the root.  It was **not** overwritten and it was **not**
  repaired.
* The six majors of the independent review stay **open**.  This batch proves
  neither their closure nor their persistence: four of the five failures are
  in the preparation of the tests and one of them (F2) is a conflict between
  the design decision of the root and a frozen oracle that the root has to
  arbitrate.
* The claims of this delivery stay **READY_FOR_REVIEW**.  They are **not**
  Stage PASS, they are not a native execution, they are not a native cleanup,
  they are not a released GPU, they are not a released port, they are not a
  sampler, they are not a parent crash recovery, they are not a Windows
  stdin EOF, they are not an admission and they are not a product gate 0.
* The N2 work was **not** started and no real service, model or GPU was
  touched.

## 5. The files of this attempt

* `commands.json` — the three commands with their original argv, their
  original cwd and their exit codes.
* `counter-before.json` / `counter-before.stdout.log` /
  `counter-before.stderr.log` — the first, read only observation.
* `counter-after.json` / `counter-after.stdout.log` /
  `counter-after.stderr.log` — the second, read only observation.
* `native-custody-correction-07.guard.json` /
  `native-custody-correction-07.stdout.log` /
  `native-custody-correction-07.stderr.log` — the guard, its self test, its
  runtime denials and the preload window.
* `native-custody-correction-03.receipt.json` — the receipt of the runner of
  the root.  **This is the name that the inherited runner writes**; it is
  not the receipt of the correction 03, which lives in the report directory
  of the correction 05.
* `pytest-temp/` — the temporary directory of the batch.

## 6. The next step

The batch failed and the contract forbids a rerun, a wrapper and a self
repair.  The next round has to carry the correction of the five failures:
four of them are in the tests (F1, F3, F4 and the observation of F5) and one
of them (F2) needs a decision of the root between the design decision and a
frozen oracle.  The decision of the root, the corrected candidate and the
next frozen plan are the only things that may follow.
