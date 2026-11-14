# N1 correction13 — the wait inventory and the current-wait boundaries

Coordinate `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.  The
formulas below are **source facts** of the two production blobs of this
candidate.  They are not measurements of the requested values: the dynamic
recordings are `NOT_RUN` until the root runs the finite batch.

## 0. The clock domain

Every deadline of the round is compared in the clock of the domain that owns
it.  The change of this correction added the clock to the two places that
hand a deadline to another layer:

* `_LaunchAggregate._release_bound(deadline, clock)` returns the deadline
  **and** the clock of its domain; the clock of the context of the round wins
  when the context owns the deadline.
* `_LauncherCustody._effective_bound(deadline)` does the same for the table.
* `_release_budget(deadline, context, clock=)` measures the deadline with that
  clock.
* `_LaunchAggregate` shares the clock of its own context when it is built
  without an explicit clock.
* `_ChannelPump` (parent) holds the ONE context of the round and measures the
  deadlines of the round with the clock of that context.

Before this correction the table compared a deadline of a round that was
published by a **manual** clock with the **real** monotonic clock.  That
mismatch is the cause of the observed `DID NOT RAISE` of N10-R05 (see
`report.md` §2.4) and it is repaired on both sides: the production measures
in the right domain and the group isolates its own launch.

## 1. The waits that this correction touched

| Wait site | The requested argument now | The boundary it is cropped by | What changed |
|---|---|---|---|
| `StreamChannel.read` → `self._queue.get(timeout=limit)` (broker 5523) | `min(max(0.0, timeout), current remaining)`; **0** when the remaining arrived | the bound of the channel, the absolute deadline of the round and the **published** cleanup deadline of the round, read again at the moment of the read | the requested timeout of the queue was the caller value unchanged (`max(0.0, timeout)`) |
| `BrokerLoop._loop` → `self.transport.read(timeout)` (broker 6282) | `min(POLL_SECONDS, min(cached lease, current remaining))` | the **current** minimum of the original context (the absolute deadline **and** the published cleanup deadline) in addition to the cached lease | the loop used the cached lease only; an arrived bound now ends the round with `LEASE_EXPIRED` |
| `_ChannelPump.run` → `self._broker.read(CHANNEL_POLL_SECONDS)` (custody 846) | the caller value; the channel crops it (row 1) and the pump ends itself when the bound arrived | the current minimum of the context of the round | the pump passed the fixed poll through unchanged and it could spin on a round that was over |
| `_ChannelPump.take` → `waiter.event.wait(max(0.0, remaining))` (custody 917) | `min(the deadline of the caller, the **current** effective deadline of the context)` | the absolute deadline and the published cleanup deadline of the round, re-read immediately before the wait | the wait used a number that the caller had constructed earlier |
| `WindowsApi._wait_timeout_ms` (broker 862) | `min(WAIT_MILLISECONDS, int(remaining * 1000))` | the bound of the façade | the value was `max(1, ...)`: a remainder below one millisecond asked for one millisecond |
| `WindowsApi._recovery_timeout_ms` (broker 1161) | `min(WAIT_MILLISECONDS, int(remaining * 1000))` | the ONE recovery deadline | the same positive floor |
| `BrokerCore._wait_timeout_ms` (broker 3415) | `min(WAIT_MILLISECONDS, int(remaining * 1000))` | the **current** cleanup deadline of the round | the same positive floor |
| `_release_launch_process` → `process.wait(timeout=budget)` (broker 7546) | `_release_budget(deadline, context, clock=)` in the clock of the domain of the deadline | the deadline of the caller and the deadlines of the original context | the budget was always measured with `time.monotonic` |
| `_release_launch_process` → the raw closes | the bound is read again **before each** close; an arrived bound refuses the close | the same bound, in its own domain | the initial raw closes were unconditional |
| `_LaunchAggregate._release_raw_streams` → `stream.close()` (broker 7199) | the bound is read again **before each** retry; an arrived bound refuses the close | the same bound, in its own domain | the bound was snapshotted **once**, before the loop |

## 2. The waits that this correction did **not** touch (and why they stay)

| Wait site | The requested argument | Why it stays |
|---|---|---|
| `_WindowsPipeWorker.run` → `self._requests.get(timeout=0.1)` (broker 4037) | the fixed service poll of the worker | it is the idle poll of the worker, not a wait of the round; the admission of the generation is decided by the worker itself before the primitive |
| `_WindowsPipeWorker.submit` → `self._requests.put(request, timeout=POLL_SLICE_SECONDS)` (broker 4277) | the fixed bounded submission | it is the submission of the worker, not a wait of the round; the intended path has one slot and one request in flight |
| `_WindowsPipeEndpoint._wait_slice` (broker 4652) | `min(POLL_SLICE_SECONDS, effective - clock)` with no positive floor | the repair of the correction 12; it is already cropped to the current effective minimum |
| `_WindowsPipeEndpoint._await` → `worker.wait_done(generation, slice)` | the slice of the endpoint | the repair of the correction 12; the endpoint re-reads the effective minimum on every slice |
| `StreamChannel._put_wait` → `self._queue.put(raw, timeout=self._put_wait())` (broker 5387) | `min(CHANNEL_QUEUE_PUT_SECONDS, current remaining)` with no positive floor | the repair of the correction 12; the **put** of the reader is already cropped |
| `StreamChannel.close` → `self._thread.join(join_seconds)` (broker 5599) | `CLOSE_JOIN_SECONDS` or the current remaining of the channel | the bounded join of the reader; the reader that did not stop keeps its owner |
| `_StartupOwner.await_result` → `self._results.get(timeout=wait)` (broker 5860) | `min(POLL_SLICE_SECONDS, current remaining)` with no positive floor | the repair of the correction 12; the observation of the result is a non blocking `get_nowait` |
| `_StartupOwner.settle` → `self._thread.join(max(0.0, seconds))` (broker 5894) | the remaining that the caller supplies | the bounded join of the thread of a step; the caller always settles in a `finally` |
| `BrokerProcess.close` → `self._process.wait(timeout=...)` (broker 6580, 6596) | `max(0.0, current cleanup deadline - clock)`, read again before **each** wait | the repair of the correction 12 (M08-B) |
| `BrokerCore` → `reader.join(min(READER_JOIN_SECONDS, remaining))` (broker 3065) | the current remaining of the cleanup | unchanged |
| the parent heartbeat → `event.wait(min(remaining, CLOSE_WAIT_SLICE_SECONDS))` (custody 2242) | the current remaining of the cleanup, cropped to the slice | the heartbeat is a service poll and it is never credited as a proof of the convergence of the round |
| the parent closer → `closer.join(min(remaining, CLOSE_WAIT_SLICE_SECONDS))` (custody 2313) | the current remaining of the cleanup, cropped to the slice | the bounded join of the closer of the round |
| the POSIX poll of the alternate transport | the fixed slice of the package | the alternate path of the package; it is outside the default Windows native launch path and it is not credited as a current-context proof |

## 3. The dynamic current-wait boundaries that the group drives

These are the boundaries that the finite batch of the 189 nodes has to
observe.  They are the **requested** values that the group records; the
recording is `NOT_RUN` until the root runs the batch.

| Boundary | The group that drives it | The requested value that must be observed | The node |
|---|---|---|---|
| the put of the reader of the channel | the first frame is delivered after the recorder was installed; the bound is tightened before the second frame | `0.5` and then `≤ 0.02` | N05-R14 |
| the read of the transport of the loop | the cleanup deadline of the round is published below the poll cap | `≤ 0.05` and `< 0.25` | N03-R08 |
| the read of the transport of the loop after the bound arrived | the bound of the round expires while the lease of the loop is still in the future | **no** read at all and `LEASE_EXPIRED` | N03-R08 |
| the reply event of the parent | the context of the round is shortened between the construction of the number and the wait | the wait of the event is the **current** minimum | N10-R10 and the parent group of the regressions |
| the millisecond adapter of the façade | the remaining is exactly 0, below 1 ms, exactly 1 ms and just above 1 ms | `0`, `0`, `1`, `1`; **no** primitive call for the two zeros | N07-R02 |
| the millisecond adapter of the core | the same four remainders through the cleanup deadline of the round | `0`, `0`, `1`, `1`; the exit is never inferred from a zero | N07-R02 |
| the wait of the owner of a startup step | the deadline of the round is tightened between two waits | the first wait `0.05`, the next wait `≤ 0.01` | N10-R09 |
| the raw close of the retry of an unresolved original | the bound of the round arrives before the retry | the close is **not** attempted and the original keeps its owner | N05-R10 and N10-R05 |

## 4. What this inventory does **not** claim

* It does not claim that an **admitted** blocking call is shortened
  atomically.  The crop bounds the **next** requested wait; a call that
  already began inside the operating system is bounded by its own
  cancellation, never by a promise of preemption.
* It does not claim any native timing, any scheduler duration and any real
  exit.  `native_execution` and `native_cleanup` stay `NOT_PROVEN`.
* The dynamic recordings of the requested values are `NOT_RUN` in this
  delivery: the implementation did not import, collect or run the candidate.

---

# Static follow-up 01 — the wait sites that this follow-up touched

Baseline `a69170c`.  Only the admission of the **closes** of the original
resources of a launch changed.  No wait of the round changed its argument, its
cap or its positive floor, and no wait of the closed paths (M08-A, M08-B,
M08-C.1, M08-C.2, M08-D and M08-E) was altered.

| Wait site | The requested argument now | The boundary it is cropped by | What changed |
|---|---|---|---|
| `_release_launch_process` → the **initial** raw close of an original | the close is **admitted** only when the **current** minimum of the release is positive | the deadline of the caller, the absolute deadline of the original context and the **published** cleanup deadline of the round, read again **before each** close, in the clock of their domain | the helper compared every initial close with the numeric bound that the aggregate had computed **once** before the helper; a context that was tightened by the wait of the process or by a previous close was not observed |
| `_release_launch_process` → the wait of the process | `_release_budget(deadline, context, clock=)` | the same current minimum, now read through `_release_minimum` with the clock of its domain | the value and the clock of the domain now travel together; the finite fallback of the package is unchanged |
| `_release_raw_streams` → the **owned** retry close | the current minimum, read again before every retry (unchanged) | the same current minimum | the loop was already repaired by the correction 12; it is unchanged and it is guarded by a new negative case |
| `_release_raw_streams` → an original that the channel took | **no close at all**: `BROKER_RAW_STREAM_OWNED_BY_CHANNEL` | the durable ownership history of the launch | the eligibility was decided from the presence of the channel in the active slot |

## The dynamic current-wait boundaries that the new drivers observe

| Boundary | The group that drives it | The requested value that must be observed | The node |
|---|---|---|---|
| the initial close of an original after the round expired during the wait of the process | the round publishes an expired cleanup deadline inside the wait of the process | **no close is attempted** (the attempt counter stays zero) and the original is retained with its identity | N10-R05 |
| the initial close of an original after the round expired between two closes | the first close of an original shortens the original deadline | the **second** close is not attempted and the first one is confirmed | N10-R05 |
| the **repeated** release of an expired round | the one way deadline of the round is expired and it may only be shortened | **no** new close is started and the exact originals keep their owner | N10-R05 |
| the successful unresolved-only retry | a **separate** original round that is positive from the start, with a controlled ordinary close failure and the released fault seam | the unresolved original is closed exactly once by the same owner under the same context and the same deadline | N10-R05 |
| the requested argument of the primitive at the millisecond boundary | the zero clock origin with the four exact remainders, through the API, the **recovery** and the Core adapters | `0`, `0`, `1`, `1`; **no** primitive call for the two zeros | N07-R02 |
| the queue wait of the real parent pump after the original context was tightened | the round publishes a cleanup deadline that is shorter than the poll of the pump | the requested argument of the queue wait is the current minimum (0.05 s in the fixture) | N10-R07 |
| the reply event of the parent after the original context was tightened | the same schedule with the real pump and a fresh pump of the same owner | the requested argument of the event wait is the current minimum | N10-R07 |
| the queue wait and the reply event at the zero expiry | the absolute deadline of the round is shortened | the queue wait asks for **0** and the event wait asks for **0**; the pump of the round ends instead of spinning | N10-R07 |
| the read of the executable, its digest and the constructor of the channel after the public stop while the process is admitted | the stop is published while the creation of the process is paused | **zero** reads, **zero** digests and **zero** constructor attempts | N07-R13 |

The written code is not counted as coverage: every one of these facts is
`NOT_RUN` until the root runs the finite batch of the 189 nodes.
