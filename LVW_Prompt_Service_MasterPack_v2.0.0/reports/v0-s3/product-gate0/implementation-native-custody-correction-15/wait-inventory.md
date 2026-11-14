# N1 correction 15 — the wait and admission inventory of the correction

Coordinate `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.
The correction changes **no** wait of the production and **no** bound of
the production.  This document names every wait, every gate and every
thread that the three Majors touch, the **domain** of its clock and the
fact that the correction observes.

## 1. The waits that the correction touches

| Site | Production owner (file:symbol) | The argument that the production really uses | The clock of its domain | What the correction observes |
|---|---|---|---|---|
| the read of the channel of the **zero round** | `v0_s3_native_broker.py:StreamChannel.read` (`5496-5529`) | `min(CHANNEL_POLL_SECONDS, the remaining of the channel)`, and **0** when the bound arrived | the clock of the channel (`_remaining`, `5352-5357`) — the clock of the **round** | M1: the **attached** pump of the round really asks the queue of the round for **nothing** (`queue.get(timeout=0.0)`) and the recorded argument is the argument that the production really passed |
| the admission of the read of an endpoint | `_WindowsPipeEndpoint._admission_locked` (`4621-4643`) | the earliest of the call, of the bound of the endpoint, of the absolute deadline and of the published cleanup deadline | the clock of the endpoint (`_clock`) — the clock of the **round** | M1: the zero round is built in **one** clock domain, so the admission of the read of the endpoint is decided in the same domain as the deadline of the round |
| the wait of the reply of the parent (the zero expiry) | `v0_s3_native_custody.py:_ChannelPump.take` (`887-928`) | `min(the deadline of the call, the current effective deadline of the ORIGINAL context)` | the clock of the pump (`_clock`, the clock of the session) | M1: the recorded argument of the event of the reply is `0.0`; the wait is bounded by the **original context** of the round and not by the timeout of the call |
| the end of the pump of the round | `_ChannelPump.run` (`835-867`) | the current effective deadline of the original context | the clock of the pump | M1: the pump of the zero round really ends after the bound arrived and it never spins on a round that is over |
| the wait of the outcome of a generation | `_WindowsPipeWorker._complete` (`4142-4179`) → `_WindowsPipeEndpoint._await` (`4709-4784`) | the outcome of the **named** generation, read before and after the coordination | the clock of the worker | M2: the barrier of the test waits, bounded, for the outcome of that **specific** generation before the cancel primitive returns; the selection point of the production then really sees the published fault |
| the **checked** barrier of the publication | the barrier of the fixture of the test (`_M09TimeoutApi.cancel_synchronous_io`) | the immutable outcome of the **exact** generation, the expected kind of the failure and the **exact** original error object | the wall of the host (the order of the barrier is checked with `time.monotonic`) | M2: a missing outcome, an outcome of another generation, another kind of failure and another error object **refuse** the premise; the cancel primitive never returns `REQUESTED` as if the barrier had passed |
| the wait of a **missing** outcome (the negative subcase) | the wait of the fixture of the test (`_wait_for_missing_outcome`) | a generation that was never published | the wall of the host | M2: the wait is bounded (1 s), it ends with `None` and it never decides or writes an outcome |
| the bounded join of the coordination | `_WindowsPipeEndpoint._cancel` (`4899-4909`) → `worker.join_bounded(self._remaining(deadline))` | the current remaining of the endpoint | the clock of the endpoint | M2: the join still **FAILS** in the failed coordination (the worker is held inside its own final close and release tail) and the failure is a parallel fact of the original error |
| the wait of the fault of the seam | `_M09TimeoutApi.read_stream` (`_outcomes.get(timeout=30.0)`) | the bounded wait of the synthetic primitive | the wall of the host | M2: the fault is delivered to the worker and the immutable outcome of the generation really exists before the cancel primitive returns |
| the join of an owner of a round | the salvage of the fixture of the test (`_salvage_threads`) | an explicitly bounded wait of **10 s** per owner | the wall of the host | M3: every owner that **really** started is joined and its liveness is asserted; an owner without an identity is **never** joined |

## 2. The gates and the threads that the correction owns

| Owner of the test | Kind | Release | Join |
|---|---|---|---|
| the gate of the admission of the **positive** scenario | an event of the test | `finally: admission_gate.set()` — **unconditional** (unchanged) | the pump of the parent is a thread of the production and it is joined by the session and by the salvage |
| the gate of the admission of the **zero round** | an event of the test | `finally: zero_gate.set()` — **unconditional**, in the inner and in the outer `finally` | the attached pump of the round is a thread of the production; it is joined by the salvage of the zero round |
| the gate of the admission of the **controlled failures** | an event of the test | `finally: gate.set()` — **unconditional** | the pump of the round is a thread of the production; it is joined by the salvage of the subcase |
| the primitive of the **zero round** | an event of the synthetic table | `zero_api.frames_ready.set()` — **unconditional** | the worker of the read of the round is joined by the salvage of the zero round |
| the primitive of the **controlled rounds** | an event of the synthetic table | `controlled_api.frames_ready.set()` — **unconditional**, before and after the stop | the worker of the read of the round is joined by the salvage of the subcase |
| the fresh pump of the zero expiry of the **original** round | a thread of the production that is never started | `finally: zero_pump.stop()` — **unconditional** (unchanged) | it is never started and it therefore owns no thread |
| the hold of the worker of M2 | the event of the seam of the test | `api.release_the_worker.set()` in the `finally` of the phase — **unconditional** | the worker of the read is joined with a bounded wait in the `finally` of the phase |
| the transport of the **child** | the **production** channel of the child | the inner `finally` calls `transport.close()` — **unconditional** | its drain thread and the workers of its two endpoints are joined by the salvage of the parent |

## 3. The bounds that the correction does **not** touch

* No production deadline, timeout, poll slice or budget changes.
* No production clock changes: the correction binds the **supported**
  clock argument of the production channel and the production session to
  the clock of the round that it starts, and it changes nothing else.
* No lease of the round is renewed: the zero expiry **shortens** the
  absolute deadline of the ORIGINAL context of the zero round
  (`_CustodyContext.bind_absolute_deadline` only shortens).
* The salvage of the test owner never calls
  `publish_cleanup_deadline`, never writes into the context of a round
  and never erases a retained resource of the product: it only joins the
  owners that really started and it records what it found.
* The counter, the ledger and the shared state of the original are never
  read; the three commands of the request observe the **absence** of the
  counter around the batch.
