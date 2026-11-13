# The one frozen batch of the N1 correction 06: it PASSED

This is the execution report of the one batch that the root acknowledged
(`msg_80589155e219`, decision `ACK_ONE_FROZEN_157_NODE_OFFLINE_BATCH`) for the
frozen plan
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-06/validation-plan-01/plan.json`,
SHA256 `65e9df9904e297d0f5c76f756b5d6070f2437375f3b6a65eb2f9d0a0b85a2251`.

**The batch passed.**  157 nodes were collected, 157 passed, 0 failed, 0
skipped, pytest exit 0 and `cleanup_proven_for_batch` **true**.  The batch was
run **once**, in the order of the three frozen commands, with their original
argv and their original cwd.  There was **no rerun**, there was **no wrapper**
around the candidate, the candidate was **not overwritten** and **no self
repair** was applied.

This report claims **READY_FOR_REVIEW** and **not** Stage PASS.  The candidate
`4287090b464d16f398b92797d8f5595359fcb442` passed its own frozen verification;
it is still **not** a release and it may not be presented as one.

## 1. The batch

| label | exit | wall | raw |
|---|---|---|---|
| counter-before | 0 | 0.047 s | `counter-before.stdout.log`, `counter-before.stderr.log` |
| guarded-validation | 0 | 21.656 s | `native-custody-correction-06.stdout.log`, `native-custody-correction-06.stderr.log` |
| counter-after | 0 | 0.029 s | `counter-after.stdout.log`, `counter-after.stderr.log` |

The total wall of the batch is **21.73 s** and the bound of the plan is 300 s
for the single batch.  The three commands are the frozen ones: their argv, their
cwd and their order are the ones of the frozen plan and they were executed
exactly once.  The executed commands are recorded in `commands.json` of this
directory.

The receipt of the runner is **`native-custody-correction-03.receipt.json`** in
this NEW `attempt01` directory.  **That is the actual file name**: it is
inherited from the root runner and it is the receipt of **this** run.  It was
written only into this directory of the correction 06; the receipt of the
correction 05 lives in another directory and it was not read, not copied and
not overwritten.  The guard record of this run is
`native-custody-correction-06.guard.json`.

`pytest_exit 0 / call_count 157 / pass_count 157 / fail_count 0 / skip_count 0 /
functional_pass_count 155 / cleanup_proven_for_batch true`.

The **155** functional passes are the 157 calls without the two integrity only
nodes of the frozen plan
(`test_the_old_owners_are_unchanged` and
`test_the_old_refusal_points_are_still_declared`).

## 2. The evidence of the boundary

* **The counter.**  The read before and the read after are **byte identical**:
  the two read records have the same digest
  (`7338b51fd39a78203a59a9942984fdd182c9645936d0bc7df0bc5aa114838eb3`) and the
  shared counter itself still carries the expected digest
  `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`.  The read
  record says `written_by_this_run false`, `refunded_by_this_run false`,
  `reset_by_this_run false`, `new_counter_created false`,
  `old_grant_revived false`.  The counter is read **only** outside of the
  guarded batch, it is never written and no descriptor of it entered the
  candidate.
* **The guard.**  `guard_precedes_candidate_and_pytest true`, the self test
  denied the eight prohibited events (`subprocess.Popen`, `socket.__new__`,
  `os.fork`, `os.exec`, `os.system`, `sqlite3.connect`, `ctypes.dlopen`,
  `ctypes.dlsym`), `runtime_denials` is empty, the preload window holds exactly
  one `ctypes.dlopen` with a null name and its final state is `CLOSED`.
* **The file descriptors.**  Three descriptors before and three after, no new
  and no reused descriptor (`new_or_reused_fds` is empty), the `EBADF`
  descriptor filtered in both snapshots and no unknown descriptor in either
  snapshot.
* **The threads.**  `["MainThread"]` before and `["MainThread"]` after.  **No
  thread was retained by the batch.**  The two threads that the failed batch of
  the correction 05 retained - `lvw-native-custody-late` of R08 and
  `lvw-native-custody-closer` of R23 - are gone: the salvage of the test owner
  of those two nodes released the gate and joined the thread in its `finally`.
* **The order.**  The collected nodes are **identical** to the selected nodes
  of the frozen plan and to the order of the failed batch of the correction 05:
  157 node ids, no node added, no node removed, no node renamed.

## 3. The six failures of the predecessor

The six nodes that failed in the batch of the correction 05 pass in this batch.
They are the six nodes that carry the erratum of the classification of
`implementation-native-custody-correction-06/report.md`: four production related
paths (F1, F3, F5, F6), two test only paths (F2, F4) and one node that carried a
wrong expectation as well (F3).

| node | before | after |
|---|---|---|
| `tools/test_v0_s3_native_custody_regressions.py::test_n03_r06_the_start_cleans_up_everything_that_it_acquired` (F1) | FAIL - the peer was closed twice | **passed** (0.255 s) |
| `tools/test_v0_s3_native_custody_correction05.py::test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation` (F2) | FAIL - `TypeError: unhashable type` | **passed** (0.000 s) |
| `tools/test_v0_s3_native_custody_correction05.py::test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup` (F3) | FAIL - the table of the live handles was empty | **passed** (0.003 s) |
| `tools/test_v0_s3_native_custody_correction05.py::test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread` (F4) | FAIL - `AttributeError: 'StartedThenFailed' object has no attribute 'error'` | **passed** (0.001 s) |
| `tools/test_v0_s3_native_custody_correction05.py::test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` (F5) | FAIL - the original process and thread handles were still open | **passed** (0.001 s) |
| `tools/test_v0_s3_native_custody_correction05.py::test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts` (F6) | FAIL - the waiter returned before the closer ended | **passed** (0.554 s) |

The per node result of every one of the 157 calls, with its outcome and its
duration, is in the `reports` array of the receipt.

## 4. What the batch proves and what it does not

The batch proves that the candidate `4287090b464d16f398b92797d8f5595359fcb442`
passes the **157 frozen nodes** in their frozen order, that the six failures of
the predecessor are corrected, and that the boundary of the package held: the
guard denied the eight prohibited events, the preload window held exactly one
`ctypes.dlopen(None)` and it was closed before the candidate, the counter was
read once before and once after and it did not change, no descriptor was
created or lost, no prohibited event was attempted at runtime and **no thread
was retained by the batch**.

The batch does **not** prove a release of the resources of a round on
Windows.  The native claims of the package stay `NOT_PROVEN`: no native
execution, no native cleanup, no released GPU, no released port, no sampler, no
parent crash recovery, no Windows stdin EOF, no admission and no product gate 0
is claimed.  N2 was not started.

The six open majors of the isolated review of the predecessor are **not** closed
by this batch.  The independent review keeps its own verdict and it has to
check, item by item, the 24 groups and their oracles - in particular the
concurrency of the initialisation of the deadline, the recovery of the retained
resources, the owner of a background start that did not return, the difference
between the end of the attempt and the exit of the thread, the determinism of
R16 and the public consumption of the reservation in R18, as the review notes of
the root require.  A green batch is **not** a closed major.

## 5. The state of the delivery

* The candidate `4287090b464d16f398b92797d8f5595359fcb442` stands as it was
  verified.  It was not overwritten and it was not repaired.
* The three changed sources are the only files that the candidate changed.
  `tools/test_v0_s3_native_custody.py` and
  `tools/test_v0_s3_native_custody_regressions.py` are **unchanged**.
* No other route was taken: no second batch, no other node, no relaxed
  assertion, no deleted case and no other platform.
* The delivery is **READY_FOR_REVIEW** and it is **not** Stage PASS.  The
  independent review, the native execution, I24, the product gate 0, the
  quality thresholds, the budget balance and the human signature all stay
  unproven.
