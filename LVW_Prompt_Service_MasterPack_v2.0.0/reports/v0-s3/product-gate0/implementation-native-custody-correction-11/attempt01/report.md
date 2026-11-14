# N1 correction 11, attempt 01: the one frozen batch, FAILED

**Stage** R1 / **Workpack** WP-R1-U3 / **Gate**
`S3_P4_N1_CONSOLIDATED_OWNER_CONTEXT_AND_IO_OUTCOME_CORRECTION11`.  **Candidate**
`b05020a67f0e54d8584505e6ecac52be214ad7fd`.  **Plan**
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-11/validation-plan-01/plan.json`
(SHA256 `dc65bba97f6b86a6745bd6a1848dad380987a964dbcde0b08f7f10b34bc48f86`),
ACK `ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH` (`ack.json`).

**The batch was executed exactly once and it FAILED.**  There was no rerun, no
wrapper, no extra node, no self repair, no deleted case and no overwritten
candidate.  The candidate and the evidence of this batch stand exactly as they
are.

## 1. The result of the batch

| Fact | Value |
|---|---|
| the frozen node ids | 189 (the 175 inherited in their original order and the 14 new ones) |
| collected | 189 — the order is **identical** to the frozen plan (`collected == selected`) |
| passed | **186** |
| failed | **3** |
| skipped | 0 |
| functional pass count | 184 (the two integrity only nodes are counted apart) |
| pytest exit | **1** |
| duration | 30.95 s (the bound of the batch is 300 s; the wall of the guarded command is 31.13 s) |
| cleanup proven for the batch | **true** |
| the commands | three, in the order of the plan, exit 0 / 1 / 0 |

The receipt of the inherited runner of the root is
`attempt01/native-custody-correction-03.receipt.json`.  That file name is the
name that the inherited runner writes and it is **not** the receipt of the
correction 03.  The two documents are never mixed.

## 2. The boundary of the batch

The boundary held and it is proven by the evidence of the batch.

* The guard of the root **preceded** the candidate and pytest
  (`guard_precedes_candidate_and_pytest: true`).  Its self test denied the eight
  prohibited events (`subprocess.Popen`, `socket.__new__`, `os.fork`,
  `os.exec`, `os.system`, `sqlite3.connect`, `ctypes.dlopen`,
  `ctypes.dlsym`) and the **runtime denials are empty**: no prohibited event
  happened during the batch.
* The single trusted preload is the one that the plan allows: `ctypes.dlopen`
  with the name `null`, **one** event, and the window was **CLOSED** before
  the candidate and before pytest (`preload_window_final_state: CLOSED`).  It
  was never reopened.
* The file descriptors before and after the batch are the **same three**:
  `0`, `1` and `2`, with the same identity.  The descriptor `3` was filtered,
  there is **no** unknown descriptor and there is **no** new and **no** reused
  descriptor (`new_or_reused_fds: []`).
* The threads before and after the batch are `["MainThread"]` and
  `["MainThread"]`: no thread of the round was left behind.
* The pins were verified by the runner itself before the batch: the 34 source
  pins, the 223 dependency files, the 3 stdlib pins and the 3 tool pins of the
  plan.  The owner of the batch verified them a second time before the batch
  and found **no** drift.

### The counter of the root: `MISSING`, the continuity is `UNAVAILABLE_NOT_PROVEN`

The outer observation of the plan only **lstat**ed the exact counter and its
parent.  It did **not** read the content, it did **not** scan anything, it did
**not** rebuild, reset, refund or revive anything:

* `counter-absence-before.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`;
* `counter-absence-after.json`: the parent and the file are **MISSING**
  (`errno 2`), `accepted_absence: true`, `counter_state: MISSING`.

The two observations agree with each other and they prove **one** thing: the
counter was absent before the batch and it is absent after it.

The **historical continuity of the counter is `UNAVAILABLE_NOT_PROVEN`**.
Nothing here states that a digest is equal to the expected one and nothing
here states that a balance was verified: the counter could not be read, so the
history of the budget of the round cannot be re-proved on this machine.  The
old grant stays **`EXPIRED_NO_REPLAY`**: it was not revived, not refunded, not
reset and no new counter was created.

## 3. The three failures, by their cause

The three failures are the honest observation of the batch.  Each of them is
classified here by the **static** reading of the sources and of the raw output
of the batch.  No second execution, no rerun and no repair was made.

### 3.1 `test_n10_r02` — the defect is in the test seam of the new sub-scenario

The raw output names the failure:

```
tools/test_v0_s3_native_custody_correction10.py:450: in test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive
    assert isinstance(error, BrokerError), \
E   AssertionError: the creation did not refuse the refused handover
E   assert False
E    +  where False = isinstance(AttributeError("'_ctypes.CArgObject' object has no attribute 'dwLowDateTime'"), BrokerError)
```

The sub-scenario of the M05 race that the correction 11 added scripts the
primitive `GetProcessTimes` of the synthetic kernel.  The scripted handler
receives the arguments of the primitive and assigns to `args[1]`, which is the
`ctypes.byref(creation)` object of the production call
(`WindowsApi._process_creation_time`).  A `ctypes.byref` object is an opaque
handle of the CArg type: it supports neither the assignment nor the reading of
an attribute of the referenced structure, and the referenced structure is
reachable through its `_obj` member.  The scripted handler therefore raised an
`AttributeError` **inside the birth query**, before the race that the
sub-scenario drives was ever reached.

The same form is in the **default** handler of the shared synthetic kernel
(`SyntheticKernel32._default`, the branch `GetProcessTimes`).  It is a latent
defect of that test helper and it is only reached by a test that really creates
a process through the synthetic table, which is the sub-scenario of the
correction 11.

What the batch nevertheless proves for this node is in its own phase document
`evidence/n10-r02-creation.json`: the closed handles are `[501, 502, 503]`,
that is the null device, the original handle of the process and the original
handle of its thread, **each of them exactly once**; the creation delivered
**no** handle (`created: false`) and the recovery of the facade released the
process and the thread.  The "one closer" and the "no stale claimed handle
delivered to the core" are therefore observed; the **code** of the refusal was
never reached, because the birth query failed first.  The defect is in the
**test seam** and not in the production path.

### 3.2 `test_n10_r04` — a latent defect of the frozen node of the correction 10

The raw output names the failure:

```
tools/test_v0_s3_native_custody_correction10.py:676: in test_n10_r04_the_launch_aggregate_finds_the_partial_channel
    assert process.terminated == 1
E   assert 0 == 1
```

The node builds a `StreamChannel` directly with `custody=aggregate` and it
never binds a process to that aggregate.  The release of the aggregate
coordinates `self.process` (`_LaunchAggregate.release`: `process =
self.process` and `if process is not None:`), and that attribute is `None` in
this node, so the process helper never runs.  The phase documents of the node
show the same fact from the production itself:
`evidence/n10-r04-partial.json` names `terminated: 0`, `waited: 0` and
`custody: []`, and `evidence/n10-r04-release.json` names
`released: ["channel"]` with `read_closes: 1` and `write_closes: 1`.

The static reading of the **predecessor** candidate `cdac445` shows the very
same structure (`process = self.process` / `if process is not None:` in
`_LaunchAggregate.release`), so the expectation of the node was not
satisfiable there either.  The node was masked until now because the same
node failed **earlier**, at the construction of the channel, with the
`writer_endpoint` `NameError` that the correction 11 repaired.  The defect is
in the **frozen node** and not in the production path.

### 3.3 `test_n10_r10` — a latent defect of the frozen node of the correction 10

The raw output names the failure:

```
tools/test_v0_s3_native_custody_correction10.py:1619: in test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation
    assert outcome['error'] == 'RuntimeError'
E   AssertionError: assert None == 'RuntimeError'
```

The node reads `reader.outcome(1)`, that is the outcome of the **first**
generation of the reader of the chain.  The reader of the chain consumes the
READY frame in the first generation and the STATUS frame in the second one
(`_F5Api.read_stream` returns one frame per call and the chain publishes two
frames), and only the **third** generation is the read that blocks and that
receives the published ordinary failure.  The barrier of the node itself
(`reader.outcome_published.wait(15.0)`) **passed**: a generation with an
error was really published.  The node read the wrong generation.

The production published the failure correctly and the group of the fifth
failure, that drives the very same fault, reached its own document in this
batch: `f5-evidence/f5-read-fault.json` names `reader_error = RuntimeError`
and `channel_reader_error = RuntimeError` with
`channel_reader_error_source = FIRST_CLOSE`.

The node was masked until now because the same node failed **earlier**, at the
construction of the channel, with the `writer_endpoint` `NameError` that the
correction 11 repaired.  The defect is in the **frozen node** and not in the
production path.

### 3.4 What the three failures mean together

* **Two** of the three failures are the later assertions of two frozen nodes
  of the correction 10 that the correction 11 made reachable for the first
  time.  They are defects of the **oracle of the nodes** and not of the
  production.
* **One** failure is a defect of the **test seam of the sub-scenario that the
  correction 11 itself added**.  The production path of the sub-scenario was
  not reached and the race was therefore not proven by this batch.
* No failure names a defect of the production code of the four Majors or of the
  one Minor.  The 186 nodes that passed include every node of the frozen plan
  that does not carry one of these three defects.

## 4. The auxiliary action of the owner of the batch

One auxiliary action was executed **after** the batch.  It is listed with its
exact command, its output and its exit code in `auxiliary-actions.json`.  It
is **not** accepted evidence, it is **not** part of the guarded batch and it
changed nothing.

* The command was a standalone `python3 -c` probe of the standard library
  module `ctypes` alone: it declared a `ctypes.Structure` and asked whether a
  `ctypes.byref` object supports the assignment and the reading of an
  attribute.  Its exit code was 1 and its output is in the record.
* **No module of the candidate was imported by it.**  The command text names
  `ctypes` and nothing else; it did not import
  `tools.v0_s3_native_broker`, `tools.v0_s3_native_custody` or any other
  module of the package, and it started no process and no collection and no
  test.
* It was used for one thing only: to classify the failure of the node
  `n10_r02` (the section 3.1) from an observation instead of a guess.

No other auxiliary runtime probe, import, ctypes probe or subprocess probe was
executed after the batch, and none is executed now.

## 5. The bounded documents of the batch

* The ten expected documents of the fifth failure group were **all** really
  reached and **all** were written by the group itself: `f5-phase-status.json`
  names every one of them with its digest.  The document of the static phase
  (`../f5-phase-status.json`) described the state before the batch and it is
  left byte for byte as the pinned record of that phase.
* The bounded facts of the groups of the correction 10 are in `../evidence/`;
  the status of every document is in `n10-phase-status.json`: 35 documents were
  written and **three** are `NOT_RUN` with their actual cause — the node
  `n10_r10` failed in its first phase, so the documents of its two later
  phases and the coordination phase of the correction 11 were never reached.
* The raw output of the batch is `guarded-validation.stdout.log` and
  `guarded-validation.stderr.log`; the guard is
  `native-custody-correction-11.guard.json` and the runner is
  `native-custody-correction-03.receipt.json`.
* The three commands with their argv, their cwd, their environment and their
  exit codes are in `commands.json`.
* The temporary directory of the batch is `pytest-temp/`.  It is the scratch
  directory of the fixtures of the tests: it holds the empty scratch
  directories, the terminal receipts that the tests wrote and the symbolic
  links that pytest keeps for the last run of every test.  It is **not**
  committed: it is a temporary directory and its symbolic links carry the
  absolute path of this worktree.  It stays on the disk of the batch.

## 6. The state of the delivery

* The candidate `b05020a67f0e54d8584505e6ecac52be214ad7fd` stands exactly as
  it was verified by the root.  It was **not** overwritten and it was **not**
  repaired: the ACK forbids the self repair and the rerun and the correction
  of the three failures belongs to the root.
* The four Majors (M05, M07, M08, M09) and the one Minor (m03) stay **OPEN**.
  This batch proves neither their closure nor their persistence.
* The claims of this delivery stay `READY_FOR_REVIEW`.  They are **not** a
  Stage PASS, they are not a native execution, they are not a native
  cleanup, they are not a released GPU, they are not a released port, they
  are not a sampler, they are not a parent crash recovery, they are not a
  Windows stdin EOF, they are not an admission and they are not a product
  gate 0.
* The N2 work was **not** started and no real service, model or GPU was
  touched.

## 7. The limitation that stays named

The M09 timeout branch carries an **auxiliary static** proof of the order of
the two facts (the outcome of the same generation is read before a new timeout
is decided and again after the coordination).  The presence of that proof in
the source is **not** a dynamic proof of the timeout branch, and this batch did
not execute it in any case: the node that carries it failed in its first
phase.  The limitation stays named and the independent review of the root has
to verify the remaining coverage.
