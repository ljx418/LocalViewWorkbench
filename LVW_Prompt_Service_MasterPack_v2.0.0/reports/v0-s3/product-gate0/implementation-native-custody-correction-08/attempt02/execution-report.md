# N1 correction 08, attempt02: the one frozen batch, FAILED

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_08_CORRECTION_OF_THE_FIVE_FAILURES`.

Plan of the root:
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-08/validation-plan-02/plan.json`
(SHA256 `0e6c5fceaf017618dc53ab5b42f4d44bace38879c374a193fc30ff151a169696`, checked).
ACK of the root: `ACK_ONE_175_NODE_OFFLINE_BATCH_WITH_EXPLICIT_ORIGINAL_COUNTER_ABSENCE`
(`msg_2a1c15d82975`).
Candidate: `66600a1bd692c0149fc7724b624997bf2f40dcc1`.

**The batch was executed exactly once and it FAILED.**  There was no rerun,
no wrapper, no self repair, no deleted case and no overwritten candidate.
The candidate and the evidence of this batch stand exactly as they are.

## 1. The result of the batch

| Fact | Value |
|---|---|
| the frozen node ids | 175 (the 157 inherited in their original order and the 18 new ones) |
| collected | 175 — the order is **identical** to the frozen plan (`collected == selected`) |
| passed | **174** |
| failed | **1** |
| skipped | 0 |
| functional pass count | 172 (the two integrity only nodes are counted apart) |
| pytest exit | **1** |
| duration | 35.37 s (the bound of the batch is 300 s) |
| cleanup proven for the batch | **true** |

The receipt of the inherited runner of the root is
`attempt02/native-custody-correction-03.receipt.json`.  That is the file
name that the inherited runner writes and it is **not** the receipt of the
correction 03, which lives in the **own** report directory of the
correction 03
(`implementation-native-custody-correction-03/native-custody-correction-03.receipt.json`).
The two documents are never mixed.

## 2. The one failure

```
tools/test_v0_s3_native_custody_correction07.py:1787:
    assert facts.get('channel_reader_error') == 'BROKER_PIPE_CANCELLED'
E   AssertionError: the cancellation of another owner was swallowed
E   assert None == 'BROKER_PIPE_CANCELLED'
```

The failing group is `N07-R15` and the failing part of it is the **second**
bounded sub scenario, the one that drives a cancellation with the **same
code** whose owner is **another** one.

**The raw facts of the failure are on the disk**:
`f5-evidence/f5-unrelated-cancellation.json`.  They say:

* the close of the channel **initiated** the cancellation:
  `close_cancellation = {code: BROKER_PIPE_CANCELLED, source: CHANNEL_CLOSE,
  sequence: 1}` and `reader_error = None`;
* the reader of the channel really stopped and every strict fact of the
  close was confirmed (`channel_closed`, `read_end_closed`,
  `write_end_closed`, `channel_retained_workers = 0`,
  `worker_thread_handle_released = True`), so the session released the
  broker and the round is `UNKNOWN_RETAINED` because of another failure of
  the round (`BROKER_DEADLINE_EXTENDED`), not because of the reader.

**The cause is the preparation of the test, not a production defect.**  The
owner thread of the test sets the cancel flag of the channel **after** it
observed the reader really inside its read, and that observation only
happens **during** the exchange of the stop, i.e. **concurrently** with the
close of the channel.  The close and the owner therefore compete for the
flag: the **first** owner wins, and the close won it in this run.  The
production then behaved exactly as it is designed to behave — a
cancellation that the close of the channel really initiated is a named fact
of the close and not an error of the reader — and the premise of the sub
scenario (an **unrelated** owner with the same code) was therefore never
established.

The test did not observe what it wanted to observe: it asserted a premise
that it did not order.  The correction of that ordering is a change of the
test module and it is **not** made here: the ACK of the root forbids the
self repair of the candidate and the automatic rerun of the batch
(`msg_2a1c15d82975`), and the contract of the correction 08 keeps the
candidate of a failed batch as it is.

## 3. What the batch proves about the fifth failure

The **main** oracle of the group `N07-R15` — the real chain, the targeted
fault of **one** original handle of the thread of **one** named worker and
the **two** convergences — **passed**, and its raw facts are on the disk:

| The phase | The document | The facts |
|---|---|---|
| the first public stop | `f5-evidence/f5-first.json` | the targeted fault really fired (2 attempts on the **one** handle `701`), the worker of the read endpoint was **retained**, its thread handle was **not** released, the channel was closed **once**, the broker was **kept** and the round was `UNKNOWN_RETAINED` |
| the explicit release of the fault and the second public stop | `f5-evidence/f5-second.json` | the channel was closed **twice**, the handle `701` was closed **exactly once** (the ledger holds three attempts, the closed handles hold one), the retained worker is gone, `worker_thread_handle_released = True`, the broker was **released** by the facts of the close |
| the salvage of the owner of the test | `f5-evidence/f5-salvage.json` | the same facts, no double close and no extra attempt |
| the first sub scenario, the local close cancellation | `f5-evidence/f5-close-cancellation.json` | the cancellation that the close really initiated is a **named fact** of the close with its code, its source and its order, the reader error is `None`, the strict facts hold and the broker is released |

The **original deadline of the cleanup was never reset**: it is
`1602.747824924` in the first attempt and in the second attempt.

**The diagnosis of the fifth failure is therefore advanced and it is not
closed.**  The real chain of the round converges in **two** public stops
with a targeted fault, without a double close and without a new budget, and
the production that was suspected in the last batch does release the broker
when the facts of the close confirm it.  The **complete** root cause of the
failure of the last batch is **not** claimed here: the two statically
confirmed defects of the previous round are local ones, and the raw facts
of this batch show a **test** that did not order its premise.  The five
groups of the correction 08 and the six majors of the independent review
stay as they are.

## 4. The documents of the fifth failure

The group writes **ten** bounded JSON documents before every assertion.  The
group stopped at the failed assertion of the second sub scenario, so **five**
of them were written and they are the raw evidence of the batch:

| The document | The state |
|---|---|
| `f5-first.json` | written |
| `f5-second.json` | written |
| `f5-salvage.json` | written |
| `f5-close-cancellation.json` | written |
| `f5-unrelated-cancellation.json` | written (it holds the facts of the failure) |
| `f5-unrelated-cancellation-second.json` | **not written**: the group stopped at the first assertion of that sub scenario |
| `f5-read-fault.json` | **not written**: the group stopped before that sub scenario |
| `f5-read-fault-second.json` | **not written** |
| `f5-partial-frame.json` | **not written** |
| `f5-partial-frame-second.json` | **not written** |

The documents that are missing are missing because the batch stopped: they
are not deleted and they are not replaced by a summary.

## 5. The boundary of the batch

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
  `(dev 2112, ino 1039954 / 1039955, mode 33188)` before and after.  The
  descriptor `3` was filtered, there is **no** unknown descriptor and there
  is **no** new or reused descriptor.
* The threads before and after the batch are `['MainThread']` and
  `['MainThread']`: no thread of the round was left behind.

### The counter of the root: `MISSING`, the continuity is `UNAVAILABLE_NOT_PROVEN`

The outer observation of the new plan only **lstat**ed the exact counter
and its parent.  It did **not** read the content, it did **not** scan
anything, it did **not** rebuild, reset, refund or revive anything:

* `counter-absence-before.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`;
* `counter-absence-after.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`.

The two observations agree with each other and they prove **one** thing:
the counter was absent before the batch and it is absent after it.

**The historical continuity of the counter is `UNAVAILABLE_NOT_PROVEN`.**
Nothing here states that a digest is equal to the expected one and nothing
here states that a balance was verified: the counter could not be read, so
the history of the budget of the round cannot be re-proved on this machine.
The facts of the **old** receipt — `starts_total = 28`,
`reserved_wall_seconds = 240.0`, `spent_wall_seconds = 12.362` and the
same charges — remain the facts of that receipt and they are **not** the
facts of this batch.  The old grant stays **`EXPIRED_NO_REPLAY`**: it was
not revived, not refunded, not reset and no new counter was created.  No
business process, no model action and no ledger action was allowed in this
batch and none happened.

## 6. The state of the delivery

* The candidate `66600a1bd692c0149fc7724b624997bf2f40dcc1` stands exactly
  as it was verified by the root.  It was **not** overwritten and it was
  **not** repaired.
* The six majors of the independent review stay **open**.  This batch
  proves neither their closure nor their persistence.
* The claims of this delivery stay **READY_FOR_REVIEW**.  They are **not**
  Stage PASS, they are not a native execution, they are not a native
  cleanup, they are not a released GPU, they are not a released port, they
  are not a sampler, they are not a parent crash recovery, they are not a
  Windows stdin EOF, they are not an admission and they are not a product
  gate 0.
* The N2 work was **not** started and no real service, model or GPU was
  touched.

## 7. The next step

The batch failed and the contract forbids a rerun, a wrapper and a self
repair.  The correction of the one failure is a change of the test module
that orders the cancellation of the unrelated owner **before** the close
of the channel, and that correction belongs to the root: it decides whether
the next round carries it and it freezes the next plan.  The next step is
therefore the decision of the root, the corrected candidate and the next
frozen plan, and nothing else.

## 8. The files of this attempt

* `commands.json` — the three commands with their original argv, their
  original cwd and their exit codes.
* `counter-absence-before.json` / `counter-absence-after.json` — the two
  outer observations of the absence of the counter.
* `native-custody-correction-08.guard.json` — the guard, its self test, its
  runtime denials and the preload window.
* `guarded-validation.stdout.log` / `guarded-validation.stderr.log` — the
  raw output of the batch.
* `native-custody-correction-03.receipt.json` — the receipt of the runner
  of the root.  **This is the name that the inherited runner writes**; it
  is not the receipt of the correction 03, which lives in the report
  directory of the correction 03.
* `pytest-temp/` — the temporary directory of the batch.
* `../../f5-evidence/f5-*.json` — the bounded facts of the fifth failure
  that the group really wrote before its assertions.
