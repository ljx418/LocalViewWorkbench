# N1 correction12 — the evidence of the one finite 189-node batch

Candidate: `29c5215ad44721c60145bad61165b99580cc1898` (the production blobs of
`025146bc41c914b870ffe991c2e0b6dd3a49c160`, the test-only follow-up of
`29c5215`).
Root plan: `native-custody-correction-12/validation-plan-01/plan.json`,
sha256 `098e8e9394be5e98fa7d44b47acba17fac49e09bebd5fadd8f5cd7f63711c369`,
decision `ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH`.

**The batch FAILED.**  pytest exit 1: 189 collected, 183 pass, 6 fail, 0 skip,
cleanup proven for the batch true.  This document is the **evidence only** of
that single batch.  Nothing was replayed, nothing was repaired, nothing was
re-run and no source byte was changed: the seven pinned source/test files and
the seven pinned reports of the correction 12 are exactly as they were when
the root pinned them.

No Major is closed by this document and no Stage, product or native PASS is
claimed by it.  The independent production review of `025146b`
(`native-custody-correction-12/production-review-01/review-result/review.md`)
remains **CHANGES_REQUIRED, Fatal 0 / Major 2 / Minor 0** (M07 and M08) and
the consolidated design draft of the root is architecture input only — no
implementation admission follows from this evidence.

## 1. The command audit

Exactly the three commands of the plan were executed, exactly once each, in
the order of the plan.  Nothing else was executed: no wrapper, no extra test,
no fourth command, no retry and no self repair.  The machine readable audit
is `attempt01/commands.json`.

| # | Label | Exit | Raw output | Result |
|---|---|---|---|---|
| 1 | `counter-absence-before` | 0 | `attempt01/counter-absence-before.stdout.log` / `.stderr.log` | the parent **and** the counter are MISSING (errno 2); `accepted_absence` true; the content was never read |
| 2 | `guarded-validation` | 1 | `attempt01/guarded-validation.stdout.log` / `.stderr.log` | 189 collected == selected, 183 pass, 6 fail, 0 skip, functional 181, pytest exit 1, runner duration 52.32 s, guard wall 52.43 s, stderr empty |
| 3 | `counter-absence-after` | 0 | `attempt01/counter-absence-after.stdout.log` / `.stderr.log` | the parent **and** the counter are MISSING (errno 2); `accepted_absence` true; the content was never read |

* the absolute argv, the cwd and the environment of every command are the
  ones of the plan; each command was executed with **exactly** the two bound
  environment variables of the plan and with nothing else inherited;
* the batch took 52.48 s of a bound of 300 s and it was one batch
  (`batches_max` 1);
* a 429 interruption of the session happened after the three commands had
  run exactly once and before this audit was written.  The user resumed the
  task and **no command was replayed**: the raw logs, the receipt, the guard
  document and the two counter observations of that one batch are the only
  inputs of this document.

The raw artefacts of the batch are in `attempt01/`:

| Artefact | sha256 (first 16) |
|---|---|
| `native-custody-correction-03.receipt.json` (the inherited runner) | see `commands.json` |
| `native-custody-correction-12.guard.json` (the trusted guard) | see `commands.json` |
| `counter-absence-before.json` / `counter-absence-after.json` | see `commands.json` |

## 2. The result of the batch

| Fact | Value |
|---|---|
| nodes collected | 189 |
| nodes selected by the plan | 189 (collected == selected, the runner exits on a mismatch) |
| pass | 183 |
| fail | 6 |
| skip | 0 |
| functional pass (the two integrity-only nodes excluded) | 181 |
| pytest exit | 1 |
| runner duration | 52.32 s |
| guard wall | 52.43 s |
| batch bound | 300 s (one batch) |

The six failed nodes:

1. `tools/test_v0_s3_native_custody_correction05.py::test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline`
2. `tools/test_v0_s3_native_custody_correction07.py::test_n07_r13_every_side_effect_checks_the_shared_context`
3. `tools/test_v0_s3_native_custody_correction10.py::test_n10_r04_the_launch_aggregate_finds_the_partial_channel`
4. `tools/test_v0_s3_native_custody_correction10.py::test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel`
5. `tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`
6. `tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`

## 3. The boundary of the batch

| Fact | Value | Source |
|---|---|---|
| the guard preceded the candidate and pytest | true | `attempt01/native-custody-correction-12.guard.json` |
| the self test of the guard denied the eight prohibited events | `subprocess.Popen`, `socket.__new__`, `os.fork`, `os.exec`, `os.system`, `sqlite3.connect`, `ctypes.dlopen`, `ctypes.dlsym` | the guard document |
| the runtime denials of the guard during the batch | **empty** | the guard document |
| the trusted stdlib preload | exactly **one** event, `ctypes.dlopen` with `name: null` | the guard document |
| the preload window | final state **CLOSED**, never reopened | the guard document |
| the file descriptors before the batch | 3 rows, no unknown | the receipt |
| the file descriptors after the batch | 3 rows, no unknown | the receipt |
| new or reused file descriptors | **none** | the receipt |
| the threads before the batch | `MainThread` | the receipt |
| the threads after the batch | `MainThread` | the receipt |
| the cleanup of the batch | **proven** (`cleanup_proven_for_batch: true`) | the receipt |
| the counter before the batch | the parent and the counter are MISSING (errno 2) | `counter-absence-before.json` |
| the counter after the batch | the parent and the counter are MISSING (errno 2) | `counter-absence-after.json` |
| the content of the counter | never read, never created, never written, never reset, never refunded | both counter observations |
| the historical continuity of the counter | `UNAVAILABLE_NOT_PROVEN` | both counter observations |
| the expired grant | not revived | both counter observations |

**The limitations of the counter evidence.**  The two observations are exact
metadata observations (`lstat`) of the counter and of its parent.  They prove
continued **absence** only.  They do not prove the historical content of the
counter, they do not prove a ledger balance, they do not prove that a grant
was or was not issued in the past and they do not reconstruct, refund or
reset anything.

**The limitations of the guard evidence.**  The guard denies the eight
prohibited events and its runtime denials were empty during this batch.  It
does not prove that the candidate never touched the operating system outside
of the audited events, and it does not prove anything about a native
execution: every native claim of this package stays `NOT_PROVEN`.

## 4. The phase status of the batch

Every phase document is written by the group itself, before the assertions
of its phase.  The documents that exist are `RUN`; the documents that the
implementation declares and that do **not** exist are `NOT_RUN` — their
phase was never reached because an earlier assertion of the same node
failed.  Nothing was synthesized and no phase JSON was written by hand.

### 4.1 The real chain group (`f5-evidence`)

| Phase | Status |
|---|---|
| the ten documents that the plan of the root expects (`f5-first`, `f5-second`, `f5-salvage`, `f5-close-cancellation`, `f5-unrelated-cancellation`, `f5-unrelated-cancellation-second`, `f5-read-fault`, `f5-read-fault-second`, `f5-partial-frame`, `f5-partial-frame-second`) | **RUN** (10 of 10) |
| `f5-r09-raw-stream-first`, `f5-r09-raw-stream-second` (the M07-A subcases of N07-R09) | **RUN** |
| `f5-r13-launch-stop`, `f5-r13-launch-cleanup` (the M08-E subcases of N07-R13) | **RUN** |

### 4.2 The phase documents of the correction 10 group (`evidence`)

36 of the 49 declared phases are **RUN**; the 13 that follow the failing
assertions of their node are **NOT_RUN**:

| Phase | Status | Why |
|---|---|---|
| `n10-r04-partial`, `n10-r04-release` | **NOT_RUN** | the node failed at its first assertion, before the first phase document |
| `n10-r09-await-wait`, `n10-r09-interrupted-start` | **NOT_RUN** | the node failed inside `await_result`, before both documents |
| `n10-r10-timeout-confirmed`, `-first`, `-second` | **NOT_RUN** | the node failed in the first dynamic M09 subcase |
| `n10-r10-timeout-failed`, `-first`, `-second` | **NOT_RUN** | the node failed before them |
| `n10-r10-published-before-timeout`, `-first`, `-second` | **NOT_RUN** | the node failed before them |

**The M09 dynamic evidence of this batch is therefore NOT_RUN.**  The three
schedules of the M09 obligation — the required order (the fault published,
then the timeout, then the consumption), the confirmed coordination and the
failed coordination — produced no evidence in this batch, and no M09 dynamic
claim is made from it.  The earlier phases of the same node
(`n10-r10-first`, `n10-r10-second`, `n10-r10-coordination`) are **RUN** and
they are the facts of the cancellation after the publication and of the
coordination of the cancellation — not of the timeout schedules.

The correction 05 group writes no phase document at all (its node has no
`write_phase`), so there is nothing of that group to list.

## 5. What the batch proved

The following facts are read from the phase documents that the batch really
wrote.  They are evidence of the **behaviour of the production owners in
this batch** and nothing more.

| Fact | Evidence |
|---|---|
| **M07-A (the ordinary no-channel path).**  The first release of the launcher returns the **retained original reference** of the raw stream (`stdout_attempts: 1`, `stdout_confirmed: 0`, the stream is still owned by the table and by the launch, `raw_streams: ["stdout"]`), and the **same owner** retries it and closes it **exactly once** (`stdout_attempts: 2`, `stdout_confirmed: 1`, `owned: 0`, `raw_streams: []`) while the successful process work is **not** repeated (`terminated: 1`, `waited: 1` in both releases). | `f5-evidence/f5-r09-raw-stream-first.json`, `f5-evidence/f5-r09-raw-stream-second.json` |
| **M08-A (the dispatch).**  With the request really submitted and the dispatch held, a cancellation of the **original context** and an **expired published cleanup** of the round both refuse the admission of the generation and the number of the real primitive calls is **zero** (`calls: []`, the error `BROKER_PIPE_CANCELLED` / `BROKER_PIPE_TIMEOUT`, the generation named). | `evidence/n10-r07-dispatch-cancel.json`, `evidence/n10-r07-dispatch-expire.json` |
| **M08-A (the await).**  The await of the endpoint notices the cancellation of the **original** context and the primitive calls are zero (`calls: []`, the code `BROKER_PIPE_CANCELLED`). | `evidence/n10-r07-await-context.json` |
| **M08-E (the public stop).**  The launch that is prepared after the **public stop** of the round creates **no** process (`popen: 0`) and the refusal is `BROKER_STARTUP_CANCELLED` together with `CUSTODY_BROKER_NOT_STARTED`. | `f5-evidence/f5-r13-launch-stop.json` |
| **M08-E (the expired cleanup).**  The launch that is prepared after the **published cleanup** of the round expired, while the absolute lease is still in the future, creates **no** process (`popen: 0`) and the refusal is `BROKER_STARTUP_DEADLINE_EXCEEDED`. | `f5-evidence/f5-r13-launch-cleanup.json` |

The counter, the guard, the file descriptors, the threads and the cleanup of
the batch are the facts of section 3.

## 6. The six failures — what the raw evidence says

The six failures are **not** all the same kind of thing and they are **not**
all test-only.  Three of them are established defects of the test fixtures
of this implementation, one is an assertion that is not scoped to the
resources of its own node, and two of them are **UNKNOWN** from the evidence
of this batch.  None of them contradicts the production review and none of
them closes a Major.

### 6.1 N05-R14 — the drain put subcase (`AssertionError: the reader of the channel never put a frame`)

The recorded puts were `[0.5]` — exactly one put, the unbounded one.  The
fixture of the subcase delivers its first frame, waits for the release of
the owner and delivers its second frame; the owner sets that release **after**
the tightening, so the second frame is only delivered when the release is
already set.  The reader of the fixture can therefore return the end of the
stream instead of the second frame, the drain of the channel ends and the
second put never happens.  The instrumentation of the put was installed
after the channel had already autostarted, so the first frame may also have
been put before the ledger existed.

**Classification: a defect of the test fixture of this implementation.**  The
premise of the subcase (a second frame delivered after the tightening) was
not established, and the assertion is right to fail.  The endpoint wait
subcase of the same node — the same fixture family, the cropped wait of the
worker — passed, and the node wrote no phase document of its own.

### 6.2 N07-R13 — the launcher table assertion

The two M08-E subcases of the node **passed** and their phase documents exist
(section 5).  The failing assertion is the last one of the node: that the
**global** table of the launcher carries no aggregate any more.  That table
is shared by the whole session: the nodes of the corrections 03 and 05 adopt
their launches through it, and their aggregates are its content as well.
The assertion does not inspect which entries are the ones of this node, and
the evidence of this batch does not name the entry that remained.

**Classification: a defect of the assertion of this implementation** (it is
not scoped to the resources of its own node) — and the exact remaining
entry is **UNKNOWN** from this batch.  The M08-E behaviour of the node
itself is proven by its two phase documents.

### 6.3 N10-R04 — the partial channel

The node failed at its first assertion: the aggregate did not hold the
half-built channel after the adoption, which means that the close of the
partial channel returned **complete** facts and the aggregate forgot it.  The
fixture of the node injects the interruption of the return of `Thread.start`
**after** the thread really started; that interruption does **not** prove
that the reader of the channel is still inside its read: the reader of the
fixture waits for the release of the owner, and the thread of the channel
may therefore complete (and release the channel correctly) before the
cleanup runs.  The node wrote no phase document, so the evidence of this
batch does not show whether the reader was inside its read at the close.

**Classification: UNKNOWN from the evidence of this batch.**  A defect of the
premise of the fixture and a production behaviour of the aggregate cannot be
distinguished by the artefacts that this batch produced.  The production code
of the aggregate is the code that the independent review bound, and that
review finds M07 **OPEN** with the residuals M07-A.1 (two routes to the same
original stream), M07-A.2 (a raw close cancellation discarding the already
confirmed facts) and M07-A.3 (the admission of each raw close); the
forgetting of a partial channel is not one of them, and this evidence does
not close any of them either.

### 6.4 N10-R05 — the cancelled raw recovery

The first release of the raw stream of the node really happened
(`stdout.attempts == 1`, `stdout_confirmed == 0` — the close was attempted
once and it failed).  The **second** release is the one that should have
retried the stream and propagated the original `KeyboardInterrupt`; it
returned normally instead.

**Classification: UNKNOWN from the evidence of this batch.**  The node wrote
no phase document for the subcase, so the exact error path through the
helper, the aggregate and the table is not established by the artefacts of
this batch.  Two production paths of the review are candidates and neither
is proven here: the production refuses a **new** raw close when the current
bound is expired (M07-A.3) — and the bound of that release is the **global**
table's context, which the session of an earlier node had already published
— and the review's M07-A.2 residual states that a cancellation inside the
helper discards the already confirmed facts.  The obligation of the node is
to preserve the original cancellation identity and the retained original
stream; this batch did not establish either.

### 6.5 N10-R09 — the wrapper of the queue of the startup owner

`TypeError: recording_get() got an unexpected keyword argument 'block'` —
the wrapper that the test installed on `queue.Queue.get` did not implement
the signature of the queue: the production calls `get_nowait()`, which calls
`get(block=False)`.  The wrapper broke the production's own non-blocking
observation of the queue of the startup owner.

**Classification: a defect of the test fixture of this implementation** (the
wrapper must forward the `block` argument and distinguish the non-blocking
observation from a bounded positive wait).  The three original phases of the
node are **RUN** (`n10-r09-brokererror`, `n10-r09-keyboardinterrupt`,
`n10-r09-systemexit`); the two new subcases of the node — the cropped wait
of the startup owner (M08-C) and the real join after an interrupted start
(M08-D) — are **NOT_RUN**.

### 6.6 N10-R10 — the parallel fact of the timeout

`AssertionError: the timeout did not stay a parallel fact of the failure` —
the group read the parallel fact of the error **before** the endpoint had
consumed the outcome: the published outcome of the worker is earlier than
the moment at which the endpoint attaches the parallel fact, so waiting for
the outcome is not a consumption barrier.  The earlier phases of the node
are **RUN** (`n10-r10-first`, `n10-r10-second`, `n10-r10-coordination`).

**Classification: a defect of the test fixture of this implementation** (the
consumption of the outcome by the endpoint and the end of the reader of the
channel must be established before the attached facts are asserted).

**All three dynamic M09 schedules are NOT_RUN** (section 4.2).  The M09
dynamic obligation of the correction 12 therefore has **no** evidence in this
batch.

## 7. The limits of this evidence

* The batch **FAILED** (pytest exit 1).  It is reported as a failed batch and
  the candidate of the batch is not overwritten.
* **The two Majors stay OPEN.**  The independent production review of the
  production blobs of `025146b` is **CHANGES_REQUIRED, Fatal 0 / Major 2 /
  Minor 0**: M07-A is partially repaired but OPEN (M07-A.1, M07-A.2,
  M07-A.3), M08-C and M08-E are partially repaired but OPEN (M08-C.1,
  M08-C.2, M08-E), and M08-A, M08-B and M08-D are CLOSED_STATIC.  The
  dynamic status of every atom of that review stays `NOT_RUN` where this
  batch did not execute it and the native status stays `NOT_PROVEN`.
* **No Stage PASS, no product gate, no native proof and no N2 admission**
  follows from this batch.  The stage pass claim of the receipt is `false`
  and the native claim is `false`.
* The M09 dynamic obligation is **NOT_RUN**; the close-token and the
  exact/one-over overflow schedules of N10-R11 are **RUN** (`n10-r11-*`).
* The evidence of this batch says nothing about the **implementation
  admission** of the consolidated correction: the design draft of the root
  is architecture input only.
* The counter evidence proves continued absence only; the historical
  continuity is `UNAVAILABLE_NOT_PROVEN` and the expired grant was not
  revived.

## 8. The handoff

The root freezes the consolidated correction after this evidence.  This
implementation delivered the evidence only: the raw artefacts of the batch,
the command audit, the phase status and the honest classification of the six
failures.  No source byte of the candidate and no pinned report of the
correction 12 was changed by this delivery.
