# N1 correction12 — the inventory of the waits that this batch touched

Every wait that the owners of the round perform is **bounded**.  This
inventory names the owners that this batch touched, the bound that each of
them used **before**, the bound that it uses **now** and the frozen node that
records the **actual requested value** of the wait before and after a
tightening.

A requested value is an **argument** of a wait.  Nothing here claims a
scheduler precision and nothing here claims that an operating system call that
already began is shortened atomically.  The native convergence of every one of
these waits stays `NOT_PROVEN`.

## 1. The four waits of the obligation

| # | Owner (production site) | Wait | Before | Now | Node that records the requested value |
|---|---|---|---|---|---|
| 1 | `_StartupOwner.await_result` → `queue.Queue.get` | the wait of the owner of a startup step | `POLL_SLICE_SECONDS` (0.05 s) against a **copied** number of the deadline | `min(POLL_SLICE_SECONDS, current remaining)`, where the current remaining is the minimum of the **current** absolute deadline of the original context, the **published** cleanup deadline and the deadline that the owner received | `test_n10_r09_...` (`r09-await-wait`) |
| 2 | `_WindowsPipeEndpoint._await` → `_WindowsPipeWorker.wait_done` | the wait of the endpoint for its worker | `POLL_SLICE_SECONDS` (0.05 s) against the effective deadline of the endpoint | `min(POLL_SLICE_SECONDS, current remaining)` (`_wait_slice`) | `test_n05_r14_...` |
| 3 | `StreamChannel._drain` → `queue.Queue.put` | the put of the reader of the channel | `0.5` s against the deadline of the channel | `min(0.5, current remaining)` (`_put_wait`); an expired round refuses before the put (`_check_wait`) | `test_n05_r14_...` |
| 4 | `BrokerLoop._loop` → `transport.read` | the read of the transport of the loop | `min(POLL_SECONDS, max(0.01, remaining))` — the **positive floor** of 0.01 s | `min(POLL_SECONDS, remaining)`; an expired lease stops the round before the read | `test_n03_r08_...` |

## 2. The waits that this batch also touched

| # | Owner (production site) | Wait | Before | Now | Node |
|---|---|---|---|---|---|
| 5 | `BrokerProcess.close` → `process.wait` (and the retry after the termination) | the wait of the process of the broker | one copy of `_cleanup_deadline` for both waits | the bound is read **again** immediately before **every** wait: the deadline of the caller, the absolute deadline of the round, the **published** cleanup deadline and the bound of the handle, each of them read at the moment of the wait | `test_n03_r08_...` |
| 6 | `_WindowsPipeWorker.request_cancel` → `_pause.wait` | the pause of the retry of a cancellation | `min(POLL_SLICE_SECONDS, effective - clock)` with the effective read again — **unchanged** by this batch | unchanged (the repair of the correction 11) | `test_n10_r08_...` (unchanged) |
| 7 | `_WindowsPipeEndpoint._write_block` → the segments of a partial write | the segment of a partial write | the **current** effective deadline before every segment — **unchanged** by this batch | unchanged (the repair of the correction 11) | `test_n07_r12_...` (unchanged) |
| 8 | `BrokerCore._close_one_reader` → `finished.wait` and `reader.join` | the coordination of a reader | `min(READER_JOIN_SECONDS, remaining)` — **unchanged** by this batch | unchanged | `test_n05_r13_...` (unchanged) |
| 9 | `_LauncherCustody.release` → `_release_launch_process` → `process.wait` | the wait of the recovery of the launcher | the deadline of the caller together with the **current** deadlines of the original context — **unchanged** by this batch | unchanged | `test_n07_r13_...` (unchanged) |
| 10 | `_StartupOwner.settle` → `Thread.join` | the join of the thread of a startup step | the budget that the loop computes **after** the await — **unchanged** in its budget, **changed** in its **precondition**: the join is now attempted when the facts of the thread prove that it really started | the same budget, the join is attempted for a thread that really started and it is never attempted for a thread that never started | `test_n10_r09_...` (`r09-interrupted-start`) |
| 11 | `_LaunchAggregate._release_raw_streams` → `stream.close` | the close of an unresolved original raw stream | the close of the raw stream happened **once** inside `_release_launch_process` and the stream was then stranded | the retry happens under the **current** bound of the release; an expired bound never starts a new close | `test_n07_r09_...`, `test_n05_r10_...`, `test_n10_r05_...` |

## 3. The waits that this batch did **not** touch

The idle service polling of the package, the heartbeat of the session, the
wait of the pump of the channel and the bounded wait of the reader of the
channel keep their bounds.  They are not a part of the residual of the
contract and they were not audited by this batch.

## 4. The measurement that this inventory claims

* The requested value of a wait is recorded by the frozen node **before** and
  **after** a tightening: the ledger of the requested values is in the phase
  documents of the correction 12 (`r09-await-wait`, `r07-dispatch-*`,
  `r04-*`, `r10-*`).
* The measurement is an **argument**: it says what the owner asked for.  It
  does not say that the wait ended at that moment and it does not say that
  the operating system honoured it.
* An expired round is refused **before** a wait starts.  There is no wait
  with a zero or a negative argument anywhere in the touched owners.

## 5. The gate of the M09 schedule (a seam, not a bound)

The required order of the M09 obligation (the root preflight PF12-01) is
driven with a transparent wrapper of the **production** wait of the worker
(`_WindowsPipeWorker.wait_done`):

| Item | Value |
|---|---|
| What it wraps | the production wait of the worker — the original function is called and its result is returned unchanged |
| What it changes | **when** the endpoint continues: it holds the endpoint after the wait returned and before the endpoint rechecks or consumes its generation |
| What it never changes | the requested timeout (the original argument is passed through), the outcome of the generation, the selection of the error of the endpoint, the history of the error and the facts that the node asserts |
| Which worker it holds | one named worker — the read worker of the round — and only while the read is really in flight |
| Bounded | the hold is bounded (30 s) and the teardown of the node releases it unconditionally and restores the production wait |
| Evidence | the ledger of the gated waits (`gate_calls`) and the trace of the publication, the timeout and the consumption are in the phase document `r10-published-before-timeout` |

The gate does not touch any bound of the package: the timeout that the
endpoint receives is the one that the production computed.

