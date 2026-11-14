# The changed assertions of the correction 14

Candidate base `5ad9c159d2bc6960b4d847ac6bae7073edf86cd1` (the product
`b5e92af41ba6d27a0a2a52c5442de4f95df1a8e3`).  The correction is
**test only**: three test modules change and **no** production source,
no schema, no threshold, no denominator and no historical report
changes.  Every assertion that is **removed** is named here with the
reason and with the assertion that replaces it.  No oracle is weakened:
every removed assertion is replaced by a **stronger** one that reads the
same production fact.

## F1 — N05-R10 (`tools/test_v0_s3_native_custody_correction05.py`)

The node: `test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | `scoped.release()` (no deadline) | `scoped.release(deadline=deadline)` with **one** positive deadline of the scenario (`time.monotonic() + 30.0`) that is used by the first release, by the recovery and by the final convergence | The extra release must run under the **same** original positive deadline.  The deadline is never renewed and the behaviour of the two first releases is unchanged (the bound was never expired). |
| 2 | `assert scoped.items() == []` **directly after the recovery** | the same assertion is kept, but it is moved **after** the proof of the empty owner and after **one** further explicit release of the **same** owner under the **same** deadline | The reconciliation of the registered originals names the unresolved ones as retained **before** the retry of the same release closes them; the report of that release therefore names a retained name that is already closed.  The owner that the table keeps is an **empty bookkeeping owner**. |
| 3 | — (new) | `assert [item['kind'] for item in scoped.items()] in ([], ['aggregate'])` | The table may keep **only** the name of the aggregate.  A table that still held a real original would fail here. |
| 4 | — (new) | `assert aggregate.process is None`, `assert aggregate.channel is None`, `assert aggregate.raw_streams == []`, `assert aggregate.workers == [] and aggregate.endpoints == []` | The retained aggregate is proved to be an **empty** owner: no live resource requires any action. |
| 5 | — (new) | `assert process.stdin.closed is True`, `assert process.stdout.closed is True`, `assert empty_facts['stdin_confirmed'] is True`, `assert empty_facts['stdout_confirmed'] is True`, `assert process._handle.closed == 1` | All the original files are really closed, the close is **confirmed** by the progress record of the owner and the original HANDLE of the process is closed **exactly once**. |
| 6 | — (new) | `assert (converged or {}).get('retained') == []` | The convergence retains nothing. |
| 7 | — (new) | six assertions that compare the counters **before** and **after** the convergence (`stdin_attempts`, `stdout_attempts`, `handle_attempts`, `handle_closed`, `terminated`, `waited`) | The convergence performs **ZERO** primitive work: no close, no terminate and no wait. |
| 8 | — (new) | two phase documents: `n05-<phase>-empty-owner.json` (the table and the facts **before** the salvage) and `n05-<phase>-converge.json` (the report and the counters of the convergence) | The intermediate state is recorded **honestly** before the salvage. |

**Nothing is removed.**  The original reference, count and fact checks of
the group (the identity of the originals, the number of the attempts,
the number of the terminations and of the waits, the exact original
error objects and the phase documents of the first release and of the
recovery) are unchanged.

## F2 — N07-R02 (`tools/test_v0_s3_native_custody_correction07.py`)

The node: `test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | `def test_n07_r02_...():` | `def test_n07_r02_...(tmp_path):` | The fixture parameter does **not** change the identity of the node (the node id is the file and the name of the function).  The group needs a **real** controlled run root. |
| 2 | `BrokerCore(win32=win32, plan=sealed_plan(), run_root=None, clock=clock)` | `BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path, clock=clock)` | The production constructor does `Path(run_root)` and it refuses a `None`: the boundary of the group never ran at all.  The production is **not** changed and no permissive `None` fallback is added to it. |
| 3 | — | the default of `F5_EVIDENCE_DIR` is the **new** directory of the correction 14 (the environment variable of the batch still wins) | The documents of the failed batch of the correction 13 stay in the directory of the correction 13. |

**No assertion of the boundary is skipped and none is relaxed.**  The
four cases (zero, below the unit, exactly the unit, one over the unit),
the floor of the adapters, the refusal of a requested zero and the
number of the primitive calls are unchanged.

## F3 — N10-R07 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r07_the_context_of_the_round_reaches_every_layer`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | the channel of the round was built by the production launcher with the **default** clock of the host while the context of the round carried the deadlines of the **session** clock | the channel of the round is built with the clock of the round (the production class is used unchanged and only its supported `clock` argument is bound) | The channel, its two endpoints, their workers, the pump of the parent, the context of the round and the aggregate of the launch must read every deadline of the round in **ONE** domain.  A deadline of the round was compared with a clock of another domain: the admission of the read of the endpoint refused the round, the reader of the channel failed and the pump of the parent ended before the recorder was installed. |
| 2 | the recorder was installed and the group waited for a value in `(0, 0.05]` | the recorder is installed, the **next real read of the broker** is held at a transparent seam, the group waits for the **liveness** of the pump (`admission_held`), the **original** cleanup deadline is published and only then the admission is released | The admission that is observed must be the one that **follows** the publication and not one that was already in flight.  The liveness of the owner of the read becomes a **fact** of the phase and not an assumption. |
| 3 | `session._read_reply(('READY',), timeout=0.05)` | `session._read_reply(('READY',), timeout=10.0)` | The reply of the parent must be bounded by the **published cleanup deadline of the original context** and not by the timeout of the call.  With a timeout of `0.05` the two bounds were indistinguishable. |
| 4 | `assert queue_waits[-1] == pytest.approx(0.05)` | `assert 0.0 < queue_waits[-1] <= 0.05 + 1e-9` **and** `assert queue_waits[-1] == pytest.approx(remaining)` with `remaining = session._context.effective_deadline() - clock()` | The assertion reads the **actual remaining of the round at the admission** (the original context and the clock of the round) instead of a nominal number. |
| 5 | `assert reply_waits[-1] == pytest.approx(0.05)` | `assert 0.0 < reply_waits[-1] <= 0.05 + 1e-9` **and** `assert reply_waits[-1] == pytest.approx(remaining)` | The same, for the reply event of the parent. |
| 6 | — (new) | the phase document `n10-r07-pump-current-minimum.json` also names the liveness of the pump, the error of the pump, the state of the session and the remaining at the admission | The phase records the actual returned state before the salvage. |
| 7 | — (new) | the gate of the admission is released in a `finally` and the fresh pump of the zero expiry is stopped in a `finally` | Every gate and every thread of the test owner is released **unconditionally**. |
| 8 | the evidence directory of the correction 13 | the evidence directory of the correction 14 | The documents of the failed batch stay where they are. |
| 9 | the synthetic cancel primitive of the group did not release the synthetic reader | the synthetic cancel primitive releases the reader that is really inside its read | The round is really alive after the correction, so the reader of the channel has to end when the round is closed: no thread of the round may be left behind and the cleanup of the batch stays provable. |

**The zero expiry is unchanged**: the absolute deadline of the round is
shortened to the clock of the round, the queue wait is `0.0`, the reply
wait is `0.0` and the pump of the round really ends.  The positive
admission and the zero expiry stay two distinct real owner schedules.

## F4 — N10-R09 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | `thread.join(5.0)` was called on the thread of the step that **never started** | the join is attempted only when the thread **really started** (`thread.ident is not None or thread.is_alive()`) | `threading.Thread.join` raises `RuntimeError` for a thread that never started.  The **facts** of the start decide: the start did not return, the thread has no identity and it is not alive. |
| 2 | — (new) | `assert owner._started is False`, `assert thread.ident is None`, `assert thread.is_alive() is False` | An object without an identity is never read as a physical exit of a thread. |
| 3 | — (new) | the phase document `n10-r09-never-started.json` (the facts of the start, the settle of the owner and the flight of the owner) | The phase distinguishes the **no-start object** from the **active interrupted start** of the phase above. |
| 4 | — | the unconditional bounded joins of the two phases **above** (the established start and the interrupted start) | Every thread that really started is still joined **unconditionally**. |

**The oracle of the group is unchanged**: `owner.settle(5.0) is False`
(the unproved start is never released) and `owner.in_flight is False`
are still asserted, and the causal negative of the group is retained.

## F5 — N10-R10 (`tools/test_v0_s3_native_custody_correction10.py`)

The node: `test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`.

| # | Before | After | Reason |
|---|---|---|---|
| 1 | the cancel primitive of the round enqueued the fault of the read and returned **immediately** | the cancel primitive of the **failed** coordination publishes the real primitive fault and then waits, bounded, for the **immutable outcome of that specific generation** before it returns | The coordination could reach its selection point before the worker had published the outcome of its generation.  The selection point then had no published fault and the parallel fact of the timeout could not be read at all. |
| 2 | the phase did not name the generation of the read to the seam | the phase gives the **specific** generation of the read that is in flight to the seam of the primitive | The outcome that the coordination waits for is the outcome of **that** generation and never a generic event of the worker. |
| 3 | — (new) | the phase document `n10-r10-timeout-failed.json` also names `published_before_cancel_return` | The phase records that the fault of the round was really published **before** the cancel primitive returned. |

**Nothing is weakened.**  The parallel fact of the timeout, the exact
original error object, the code of the error, the generation, the
sequence, the history of the error across the channel, the handle of
the broker and the two public stops of the round, the `UNKNOWN_RETAINED`
state and the `REPEATED_CLOSE` source are all still asserted.  The
outcome, the history, the selection, the public stop and the attributes
of the original error object are **not** patched by the fixture.  The
**confirmed** coordination and the required order of the schedule (the
fault published before the timeout, the outcome consumed after it) stay
separate and unchanged.
