# N1 correction 09, attempt01: the one frozen batch, FAILED

Stage: R1.  Workpack: WP-R1-U3 / S3-P4-N1.  Gate:
`S3_P4_N1_CORRECTION_09_DETERMINISTIC_EXTERNAL_CANCEL_PUBLICATION`.

Plan of the root:
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-09/validation-plan-01/plan.json`
(SHA256 `02f06ac7b43ad1e5ff401b4c4b442149e0ef3e21dd1bbe3c5ca5c00d80d05303`, checked).
ACK of the root: `ACK_ONE_175_NODE_OFFLINE_BATCH_WITH_EXPLICIT_ORIGINAL_COUNTER_ABSENCE`
(`msg_806e6970083e`).  Candidate: `39f803730e09673eb1b74fa51e1f0919f2606a71`.

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
| duration | 40.22 s (the bound of the batch is 300 s) |
| cleanup proven for the batch | **true** |

The receipt of the inherited runner of the root is
`attempt01/native-custody-correction-03.receipt.json`.  That is the file
name that the inherited runner writes and it is **not** the receipt of the
correction 03, which lives in the **own** report directory of the
correction 03.  The two documents are never mixed.

## 2. The one failure

```
tools/test_v0_s3_native_custody_correction07.py:1876:
    raise external_owner.error
tools/test_v0_s3_native_custody_correction07.py:429: in run
    raise AssertionError(
E   AssertionError: the reader of the chain was never inside its read
```

The failing node is `N07-R15`
(`tools/test_v0_s3_native_custody_correction07.py::test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner`),
its duration is **15.54 s** and it failed **inside the second bounded sub
scenario**, before the first public stop of that sub scenario.

The failure is the **new** observation of the external owner and it is the
**honest** consequence of it: the owner of the test waits for the explicit
event that the reader of the chain is really inside its read, the wait is
bounded and its **return is checked**.  The bounded wait of **15 s** of the
owner **expired** and the owner reported the failure to the owner of the
test, which re-raised it.  The group therefore stopped before it drove any
close of that sub scenario.

### The cause, read from the frozen source of the façade

`_F5Api.read_stream` of the test module is the **only** place where the
event `api.reader_blocked` is published:

```python
def read_stream(self, handle, size):
    with self.lock:
        if self.frames:
            return self.frames.pop(0)     # the two published frames
    self.ready.wait(30.0)                 # the FIRST bounded wait of the round
    with self.lock:
        if self.final: ...                # the final frame of the round
        if self.partial_pending is not None: ...
    if self.read_fault is not None: ...
    if self.block_the_reader:
        self.reader_blocked.set()         # <-- the event that the owner waits for
        self.release.wait(30.0)
    return b''
```

The reader of the chain consumes the two frames that the round published
before it and it then waits for the **explicit notification of the stop of
the round** (`api.ready`) before it reads the final frame, and it waits for
it **again** before it reaches the blocking read that publishes
`api.reader_blocked`.  The notification is set by a write of the round or by
the cancellation of the read in flight (`cancel_synchronous_io`), and the
round of this group writes nothing.  The event that the owner of the test
waits for is therefore published about **sixty seconds** after the reader
of the chain started, while the bounded wait of the owner is **15
seconds**.  The owner expired and it reported the failure.

This is a **preparation gap of the test**, not a defect of the production:
the production was never asked the question of this sub scenario, because
the group stopped before its first public stop.

### The relation to the failure of the correction 08

The owner of the correction 08 waited for the **same** event with a
bounded wait of **10 s** and it did **not** check the return value: it
proceeded to set the flag of the cancel after the timeout.  The premise of
the sub scenario (a cancellation of **another** owner) was therefore never
established there either, and the raw facts of that batch show the close
of the channel winning the flag.  The correction 09 fixed the **order**
(the owner of the test now waits for the confirmation of the owner and it
checks the flag and its unknown origin before the first public stop) and it
replaced the unchecked wait by a checked one; the **event** that it waits
for is the wrong one.

### The relation between the two error codes and the oracle of the root

The oracle of the root accepts the code `BROKER_PIPE_CANCELLED` for the
error of the reader of a cancellation of another owner.  The production can
name **two** different codes for a cancellation of the channel and the code
depends on **where the flag is observed**:

| The place that observes the flag | The code that the production raises | The source |
|---|---|---|
| `_await` of the read endpoint of the channel, while the drain of the channel is polling the flag | `BROKER_PIPE_CANCELLED` | `tools/v0_s3_native_broker.py` |
| `_check_wait` of the channel, while the drain of the channel is between two reads and it puts a frame into the queue | `BROKER_CHANNEL_CANCELLED` | `tools/v0_s3_native_broker.py` |

The **drain of the channel** is the thread that observes the flag and the
**worker of the read end** is the thread that blocks inside the read.  The
drain of the channel polls the flag while the worker is inside a read, and
it observes the flag between two reads only while it puts a frame of the
round into its queue.  The accepted set of the root was **not** changed by
this delivery: the evidence and the relation are reported here and the
choice belongs to the root.

## 3. The documents of the fifth failure

The group writes **ten** bounded JSON documents before every assertion.
The group stopped at the failure of the owner of the second bounded sub
scenario, so **four** of them were written and they are the raw evidence of
the batch:

| The document | The state |
|---|---|
| `f5-first.json` | written |
| `f5-second.json` | written |
| `f5-salvage.json` | written |
| `f5-close-cancellation.json` | written |
| `f5-unrelated-cancellation.json` | **not written**: the group stopped before the first public stop of that sub scenario |
| `f5-unrelated-cancellation-second.json` | **not written** |
| `f5-read-fault.json` | **not written**: the group stopped before that sub scenario |
| `f5-read-fault-second.json` | **not written** |
| `f5-partial-frame.json` | **not written** |
| `f5-partial-frame-second.json` | **not written** |

The documents that are missing are missing because the batch stopped: they
are not deleted and they are not replaced by a summary.  The **five** real
documents of the correction 08 stay in the directory of the correction 08
and they were not touched.

The facts of the main oracle of the group are on the disk and they are
unchanged by this correction: the targeted fault fired on the one original
handle, the worker of the read endpoint was retained after the first public
stop, the second public stop released the handle, retained no worker and
released the broker without a double close and without a new deadline.

## 4. The boundary of the batch

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
  `(dev 2112, ino 2593860 / 2593861, mode 33188)` before and after.  The
  descriptor `3` was filtered, there is **no** unknown descriptor and there
  is **no** new or reused descriptor.
* The threads before and after the batch are `['MainThread']` and
  `['MainThread']`: no thread of the round was left behind, and the exact
  thread of the external owner was joined by the `finally` of the group.

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
The old grant stays **`EXPIRED_NO_REPLAY`**: it was not revived, not
refunded, not reset and no new counter was created.  No business process,
no model action and no ledger action was allowed in this batch and none
happened.

## 5. The state of the delivery

* The candidate `39f803730e09673eb1b74fa51e1f0919f2606a71` stands exactly
  as it was verified by the root.  It was **not** overwritten and it was
  **not** repaired: the ACK forbids the self repair and the rerun and the
  correction of the one failure belongs to the root.
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

## 6. The next step

The batch failed and the contract forbids a rerun, a wrapper and a self
repair.  The correction of the one failure is the choice of the **event**
that the external owner waits for (and it is a change of the test module
only): the event that the owner waits for is published about sixty seconds
after the reader of the chain started, while the bounded wait of the owner
is fifteen seconds.  The correction of that belongs to the root: it decides
whether the next round carries it and it freezes the next plan.  The next
step is therefore the decision of the root, the corrected candidate and the
next frozen plan, and nothing else.

## 7. The files of this attempt

* `commands.json` — the three commands with their original argv, their
  original cwd and their exit codes.
* `counter-absence-before.json` / `counter-absence-after.json` — the two
  outer observations of the absence of the counter.
* `native-custody-correction-09.guard.json` — the guard, its self test, its
  runtime denials and the preload window.
* `guarded-validation.stdout.log` / `guarded-validation.stderr.log` — the
  raw output of the batch.
* `native-custody-correction-03.receipt.json` — the receipt of the runner
  of the root, with the result of every one of the 175 nodes, the identity
  of the file descriptors and the state of the threads.
* `pytest-temp/` — the temporary directory of the batch.
* `../../f5-evidence/f5-*.json` — the bounded facts of the fifth failure
  that the group really wrote before its assertions.
