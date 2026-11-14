# N1 correction 10, attempt 01: the one frozen batch, FAILED

**Stage** R1 / **Workpack** WP-R1-U3 / S3-P4-N1.  **Gate**
`S3_P4_N1_CORRECTION10_CONSOLIDATED_ATOMIC_REGRESSION`.  **Candidate**
`cdac445434ed129ca6c5fa8acc830f1f13261a6f`.  **Plan**
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-10/validation-plan-01/plan.json`
(SHA256 `61077309264afc30e0084960e9e1bef68a40f1c0e877e73b933e74b0d30eb88c`),
ACK `ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH` (`msg_74f8181a2572`).

**The batch was executed exactly once and it FAILED.**  There was no
rerun, no wrapper, no extra node, no self repair, no deleted case and
no overwritten candidate.  The candidate and the evidence of this batch
stand exactly as they are.

## 1. The result of the batch

| Fact | Value |
|---|---|
| the frozen node ids | 189 (the 175 inherited in their original order and the 14 new ones) |
| collected | 189 — the order is **identical** to the frozen plan (`collected == selected`) |
| passed | **172** |
| failed | **17** |
| skipped | 0 |
| functional pass count | 170 (the two integrity only nodes are counted apart) |
| pytest exit | **1** |
| duration | 81.58 s (the bound of the batch is 300 s) |
| cleanup proven for the batch | **true** |
| the commands | three, in the order of the plan, exit 0 / 1 / 0 |

The receipt of the inherited runner of the root is
`attempt01/native-custody-correction-03.receipt.json`.  That file name
is the name that the inherited runner writes and it is **not** the
receipt of the correction 03, which lives in the report directory of
the correction 03.  The two documents are never mixed.

## 2. The seventeen failures, by cause

The failures are the honest observation of the batch.  They are
grouped here by their cause; no cause is hidden and no assertion is
reconstructed.

### 2.1 A defect of the candidate: the name of the parameter of the channel (8 failures)

`StreamChannel.__init__` of the candidate reads `writer_endpoint`
where the parameter of the constructor is `write_endpoint`.  Every
construction of a channel of the package therefore raises a
`NameError` and the channel of the round is never built.

The failures that follow from it: `test_n03_r13`, `test_n07_r15`,
`test_n10_r04`, `test_n10_r07`, `test_n10_r10`, `test_n10_r11`,
`test_n10_r12`, `test_n10_r13`.

### 2.2 A defect of the candidate: the lock of the admission (1 failure)

`_WindowsPipeEndpoint._admission` uses `self._admission_lock` and the
attribute is only created by the constructor.  An endpoint that the
old node builds without its constructor (`__new__`) has no such
attribute and the call raises an `AttributeError`.

The failure that follows from it: `test_n03_r09`.

### 2.3 The close eligibility of the control handle against three old nodes (3 failures)

The correction closes the control handle of a process **only** after
the exit of that process was really confirmed (the obligation
N10-R01).  Three old nodes of the correction 05 assert the opposite
behaviour of the pre candidate: they require the handle of a process
whose wait did not confirm the exit to be closed by the pending pass
(`test_n05_r04`, `test_n05_r05`, `test_n05_r11`).

The old assertions and the new obligation cannot both hold.  The three
nodes were not corrected in this candidate and they are the three old
nodes that the batch reports as failed.

### 2.4 A regression of the candidate: the pipes that could not be closed (1 failure)

The rewrite of `_adopt_broker_process` of the candidate coordinates the
process through the aggregate of the launch and it **lost** the
registration of the streams of the process whose close failed: the
table of the launcher named `['aggregate', 'aggregate', 'process']`
instead of the process and its two streams.  The old node
`test_n05_r10` requires the streams that could not be closed to keep
their owner and it fails.

### 2.5 The admission against one old node (1 failure)

The admission of a generation refuses a call that enters when the round
is already expired (the obligation N10-R06).  The old node
`test_n05_r14` requires the read to be inside its operation while the
deadline is tightened afterwards, and the read is now refused before it
enters the operation.

### 2.6 A gap of the candidate that a new node exposed (1 failure)

`_terminate_owned` returns **without waiting** when the termination of
the process fails.  The exit of a process whose termination failed can
therefore never be confirmed, its control handle is never closed and the
round stays unknown for ever.  The new node `test_n10_r01` drives that
path and it fails on the second stop.

### 2.7 Two defects of the new nodes (2 failures)

* `test_n10_r05`: the expectation of the group was wrong - the process
  of the launch is already released by the adoption phase, so the
  recovery of the launcher coordinates the channel only;
* `test_n10_r09`: the deadline of the step of the group is shared by
  its three phases and the first phase consumed it, so the second phase
  was refused by the deadline of the round before its result was read.

## 3. The boundary of the batch

The boundary held and it is proven by the evidence of the batch.

* The guard of the root **preceded** the candidate and pytest
  (`guard_precedes_candidate_and_pytest: true`).  Its self test denied
  the eight prohibited events (`subprocess.Popen`, `socket.__new__`,
  `os.fork`, `os.exec`, `os.system`, `sqlite3.connect`,
  `ctypes.dlopen`, `ctypes.dlsym`) and the **runtime denials are
  empty**: no prohibited event happened during the batch.
* The single trusted preload is the one that the plan allows:
  `ctypes.dlopen` with the name `null`, **one** event, and the window
  was **CLOSED** before the candidate and before pytest
  (`preload_window_final_state: CLOSED`).  It was never reopened.
* The file descriptors before and after the batch are the **same
  three**: `0`, `1` and `2`.  The descriptor `3` was filtered, there is
  **no** unknown descriptor and there is **no** new and **no** reused
  descriptor (`new_or_reused_fds: []`).
* The threads before and after the batch are `["MainThread"]` and
  `["MainThread"]`: no thread of the round was left behind.
* The pins were verified by the runner itself before the batch: the
  26 source pins, the 223 dependency files, the 3 stdlib pins and the
  3 tool pins of the plan.  The owner of the batch verified them a
  second time before the batch and found **no** drift.

### The counter of the root: `MISSING`, the continuity is `UNAVAILABLE_NOT_PROVEN`

The outer observation of the plan only **lstat**ed the exact counter
and its parent.  It did **not** read the content, it did **not** scan
anything, it did **not** rebuild, reset, refund or revive anything:

* `counter-absence-before.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`;
* `counter-absence-after.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`.

The two observations agree with each other and they prove **one** thing:
the counter was absent before the batch and it is absent after it.

The **historical continuity of the counter is `UNAVAILABLE_NOT_PROVEN`**.
Nothing here states that a digest is equal to the expected one and
nothing here states that a balance was verified: the counter could not
be read, so the history of the budget of the round cannot be re-proved
on this machine.  The old grant stays **`EXPIRED_NO_REPLAY`**: it was
not revived, not refunded, not reset and no new counter was created.  No
business process, no model action and no ledger action was allowed in
this batch and none happened.

## 4. The bounded documents of the batch

* The ten expected documents of the fifth failure group: **one** was
  written (`f5-salvage.json`) and **nine** are `NOT_RUN` - the group
  never reached them because the channel of the round was never built
  (2.1).  The status of every document is in `f5-phase-status.json`.
  A phase that was not reached is `NOT_RUN`: it is not reconstructed,
  not summarised and not replaced by a document of the owner.
* The bounded facts of the new groups are in `../evidence/n10-*.json`;
  the status of every document is in `n10-phase-status.json`.
* The raw output of the batch is `guarded-validation.stdout.log` and
  `guarded-validation.stderr.log`; the guard is
  `native-custody-correction-10.guard.json` and the runner is
  `native-custody-correction-03.receipt.json`.
* The three commands with their argv, their cwd, their environment and
  their exit codes are in `commands.json`.
* The temporary directory of the batch is `pytest-temp/`.  It is the
  scratch directory of the fixtures of the tests: it holds the empty
  scratch directories, the ten terminal receipts that the tests wrote
  and the symbolic links that pytest keeps for the last run of every
  test.  It is **not** committed: it is a temporary directory and its
  symbolic links carry the absolute path of this worktree.  It stays on
  the disk of the batch.

## 5. The state of the delivery

* The candidate `cdac445434ed129ca6c5fa8acc830f1f13261a6f` stands
  exactly as it was verified by the root.  It was **not** overwritten
  and it was **not** repaired: the ACK forbids the self repair and the
  rerun and the correction of the seventeen failures belongs to the
  root.
* The six Majors of the read only pre review stay **open**.  This batch
  proves neither their closure nor their persistence.
* The claims of this delivery stay `READY_FOR_REVIEW`.  They are **not**
  Stage PASS, they are not a native execution, they are not a native
  cleanup, they are not a released GPU, they are not a released port,
  they are not a sampler, they are not a parent crash recovery, they
  are not a Windows stdin EOF, they are not an admission and they are
  not a product gate 0.
* The N2 work was **not** started and no real service, model or GPU was
  touched.

## 6. The ten fields

| Field | Value |
|---|---|
| the current coordinate | R1 / WP-R1-U3 / `S3_P4_N1_CORRECTION10_CONSOLIDATED_ATOMIC_REGRESSION` |
| what this batch did | the one frozen 189 node offline batch of the candidate `cdac445` under the hard guard of the root |
| the last passed gate | `621b1bf` `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW` (10/10) |
| the current blocker | the seventeen failures of this batch and the six open Majors |
| the place in the global route | R1 / WP-R1-U3 / S3-P4-N1; the outline of V0 - V3 is unchanged (V0-S0 1/2, V0-S1 5/5, R0 1/2, R1a 5/5, V0-S2 7/8, V0-S3 0/6, R1 0/4, V1-M1 0/3, R2 0/4, R3/V2 0/4, R4/V2 0/4, R5a/V3 0/4, R5b/V3 0/4, R5c/V3 0/4) |
| the remaining work | the correction of the seventeen failures, a new candidate, a new frozen 189 node plan and a new independent review of the six Majors |
| the next owner | the gate owner of the root (the decision on the correction of the seventeen failures) |
| the required authorisation | none is requested here: this batch was authorised and it ran; no dynamic permission is asked for |
| the evidence directory | `reports/v0-s3/product-gate0/implementation-native-custody-correction-10/attempt01` |
| the exact stop reason | the one frozen batch of the correction 10 ran exactly once and it FAILED with seventeen failures; the candidate is preserved, there was no rerun and the correction of the failures belongs to the root |
