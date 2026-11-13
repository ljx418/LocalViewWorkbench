# The one frozen batch of the N1 correction 05: it FAILED

This is the execution report of the one batch that the root acknowledged
(`msg_40e621f0f945`, decision `ACK_ONE_FROZEN_157_NODE_OFFLINE_BATCH`) for the
frozen plan `dbd2e7991013fc3a6ff3a7a025e9a0bbf185724534400665eee31a812b569f63`.

**The batch failed.**  157 nodes were collected, 151 passed, 6 failed, 0 skipped,
pytest exit 1 and `cleanup_proven_for_batch` false.  The batch was run **once**,
in the order of the three frozen commands, with their original argv and their
original cwd.  There was **no rerun**, there was **no wrapper** around the
candidate, the candidate was **not overwritten** and **no self repair** was
applied: the six failures are reported below exactly as they happened.

This report claims **READY_FOR_REVIEW** and **not** Stage PASS.  The candidate
`0e83077321186b52c7e3826efbbf92c143737b0f` did **not** pass its own frozen
verification and it may not be presented as a release.

## 1. The batch

| label | exit | wall | raw |
|---|---|---|---|
| counter-before | 0 | not measured | `counter-before.stdout.log`, `counter-before.stderr.log` |
| guarded-validation | 1 | 21 s | `native-custody-correction-05.stdout.log`, `native-custody-correction-05.stderr.log` |
| counter-after | 0 | not measured | `counter-after.stdout.log`, `counter-after.stderr.log` |

The receipt of the runner is `native-custody-correction-03.receipt.json` in this
NEW `attempt01` directory.  The name is inherited from the root runner and it is
the receipt of **this** run.  The receipt of the correction 04 lives in another
directory; it was not read, not copied and not overwritten.

`pytest_exit 1 / call_count 157 / pass_count 151 / fail_count 6 / skip_count 0 /
functional_pass_count 149 / cleanup_proven_for_batch false`.

## 2. The evidence of the boundary

* **The counter.**  The read before and the read after are byte identical
  (`7338b51fd39a78203a59a9942984fdd182c9645936d0bc7df0bc5aa114838eb3`) and the
  shared counter itself still carries the expected digest
  `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`.  The read
  record says `written_by_this_run false`, `refunded_by_this_run false`,
  `reset_by_this_run false`, `new_counter_created false`,
  `old_grant_revived false`.
* **The guard.**  `guard_precedes_candidate_and_pytest true`, the self test denied
  the eight prohibited events (`subprocess.Popen`, `socket.__new__`, `os.fork`,
  `os.exec`, `os.system`, `sqlite3.connect`, `ctypes.dlopen`, `ctypes.dlsym`),
  `runtime_denials` is empty, the preload window holds exactly one
  `ctypes.dlopen` with a null name and its final state is `CLOSED`.
* **The file descriptors.**  Three descriptors before and three after, no new and
  no reused descriptor, the `EBADF` descriptor filtered in both snapshots and no
  unknown descriptor in either snapshot.
* **The threads.**  `["MainThread"]` before and
  `["MainThread", "lvw-native-custody-late", "lvw-native-custody-closer"]` after.
  **Two threads were retained by the batch.**  They are the threads of the two
  new tests that failed before their explicit salvage (`R08` and `R23`): the
  stand-in thread `lvw-native-custody-late` of R08 and the closer thread
  `lvw-native-custody-closer` of R23.  They are threads of the **test owner**,
  they are not threads of a round of the product, and they are the reason why
  `cleanup_proven_for_batch` is false.  They died with the batch process.

## 3. The six failures

Three of the six failures are **defects of the production code** of the candidate
and three are **defects of the new test module** of the candidate.  Nothing below
was changed; the candidate stands as it was verified.

### F1 — `tools/test_v0_s3_native_custody_regressions.py::test_n03_r06_the_start_cleans_up_everything_that_it_acquired` — **PRODUCTION**

`assert holder['peer'].closed == 1` — the peer was closed **twice**.

The reader of the channel fails before the heartbeat of the round is built.  The
bounded close of the round closes the peer once.  The start of the round then
fails and it calls `_close_broker()` a second time.  The new recovery of the
unconfirmed items lives **inside** `_close_broker()`: the branch that handles the
state `FINISHED` calls `_recover_close()`, and the recovery closes the peer again.

The recovery belongs to the **public stop** of the round and not to an internal
close that follows the closer's own attempt.  The frozen group R06 asks that the
peer of that case is closed exactly once, and the correction of the oracle of R14
asks that the items that were not confirmed may be coordinated again **through the
public stop**.  The two are compatible when the recovery is reached through the
repeated public `stop()` and not through `_close_broker()`.

*Minimal correction:* remove the `_recover_close()` call from the `FINISHED`
branch of `_close_broker()` and call the recovery from the repeated public
`stop()` instead.  The repeated stop of the groups R14 and R19 keeps its meaning
and the internal close of the start keeps closing the peer exactly once.

### F2 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation` — **TEST**

`assert retained[0]['handle'] in kernel32.live` — `TypeError: unhashable type`.

The façade keeps the **original** object of the handle: for a pipe the handle is a
`ctypes.c_void_p` instance, and that type is not hashable in CPython.  The
membership test of the new node used the object where every other place of the
package uses the integer value (`getattr(handle, 'value', handle)`).

*Minimal correction:* compare the integer value of the handle in the node.  The
production behaviour that the node checks is correct: the end that could not be
closed is with its owner and the end that was closed left the table.

### F3 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup` — **PRODUCTION (bookkeeping) and TEST (expectation)**

`assert core.job in win32.live` — the table of the live handles is empty.

The close of the job handle of the round raises the cancellation of the node.
The job handle stays in the pending table of the round with its owner and the
**pending pass of the same cleanup retries the close and succeeds**: the handle
is really closed.  The product does not learn from that retry: `core.job` still
names the handle and `core.retained_resources` still names it as retained, so the
evidence of the round reports a handle that is closed and that is also retained.

Two defects are mixed here: the expectation of the node does not describe the
state that the product reaches, and the bookkeeping of the core after a
successful retry of the pending pass is stale.

*Minimal correction:* the pending pass has to tell the core that it closed a
handle, so that the job, the records and the retained resources no longer name a
handle that is closed; the node has to assert the facts that the product really
returns.

### F4 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread` — **TEST**

`session.evidence()` — `AttributeError: 'StartedThenFailed' object has no
attribute 'error'`.

The evidence of the round reads the interface of the reader of the channel
(`error`, `alive`).  The stand-in thread of the node did not implement it.  The
production code of the round always registers a real reader there.

*Minimal correction:* the stand-in of the node has to implement the interface
that the evidence reads.  The behaviour that the node checks is correct: the
thread that really runs keeps the reference of the session.

### F5 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` — **PRODUCTION**

`assert not win32.live` — the original process handle and the original thread
handle of the role that was created after the deadline arrived are still open.

The creation of the role consumes the whole lease of the round.  The check of the
shared budget **after** the creation raises, and the exception leaves
`_launch_role()` before the original handles of the created process enter the
pending table of the round and before they enter its record.  The two handles are
therefore owned by nobody: the cleanup of the round never sees them and they stay
open.

This is exactly the case that the contract names: a role that is created after
the deadline arrived may only be cleaned up, and the late original resources
have to keep their owner.

*Minimal correction:* the original handles of a created process have to enter
the pending table of the round and its record **in the moment of the creation**,
before the check of the shared budget that follows it.

### F6 — `tools/test_v0_s3_native_custody_correction05.py::test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts` — **PRODUCTION**

`assert thread.is_alive()` — the waiter of the close returned before the closer
ended.

The end of the **attempt** of the close is published before the closer thread
returns.  A waiter that arrives after the attempt ended sees the state
`FINISHED` and returns at once, even though the thread that performs the close
is still alive.  The end of the attempt and the end of the thread are two facts
and the second one is not observed by the waiter.

*Minimal correction:* a waiter that arrives when the attempt ended waits for the
real exit of the closer inside the same deadline and names the closer that is
still alive when the deadline arrives.

## 4. What the batch proves and what it does not

The batch proves that 149 of the 157 nodes pass and that the boundary of the
package held: the guard denied the eight prohibited events, the preload window
held exactly one `ctypes.dlopen(None)` and it was closed before the candidate,
the counter was read once before and once after and it did not change, no
descriptor was created or lost and no prohibited event was attempted at runtime.

The batch does **not** prove a release of the resources of a round.  Six nodes
failed, three of them on defects of the production code of the candidate, and two
threads of the test owner were retained by the batch.  The candidate is therefore
**not** a release, and the six open majors of the review of the predecessor are
**not** closed by this batch: this batch found three new defects of the candidate
in the very areas that the correction 05 wanted to close (the recovery entry of
the release, the owner of a late created process and the real exit of the
closer).

The independent review has to keep its own verdict on the six majors, and the
review notes of the root on this package already name the three points that this
batch did not settle either: the interleaving of the concurrent initialization of
the deadline, the recovery of the retained resources and the difference between
the end of the attempt and the exit of the thread.

## 5. The state of the delivery

* The candidate `0e83077321186b52c7e3826efbbf92c143737b0f` stands as it was
  verified.  It was not overwritten and it was not repaired.
* The four allowed sources and the new test module are the only files that the
  candidate changed.
* No other route was taken: no second batch, no other node, no relaxed
  assertion, no deleted case and no other platform.
* The delivery is **READY_FOR_REVIEW** and it is **not** Stage PASS.  No native
  execution, no native cleanup, no released GPU, no released port, no sampler, no
  parent crash recovery, no Windows stdin EOF, no admission and no product gate 0
  is claimed.  N2 was not started.
