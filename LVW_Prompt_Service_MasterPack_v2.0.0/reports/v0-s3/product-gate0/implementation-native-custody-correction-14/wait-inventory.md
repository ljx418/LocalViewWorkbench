# N1 correction 14 — the wait and admission inventory of the correction

Coordinate `V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION`.
The correction changes **no** wait of the production.  This document
names every wait and every admission that the five corrections touch,
the **domain** of its clock and the fact that the correction observes.

## 1. The waits that the correction touches

| Site | Production owner (file:symbol) | The argument that the production really uses | The clock of its domain | What the correction observes |
|---|---|---|---|---|
| the release of a launch | `v0_s3_native_broker.py:_LauncherCustody.release` → `_LaunchAggregate.release` | the **caller** deadline and the deadlines of the original context, read again at every release | the clock of the domain of that deadline (`_effective_bound`, `7415-7434`) | F1: the first release, the recovery and the convergence use the **same** positive deadline.  The convergence asks for **no** wait at all: the counters of the process, of the HANDLE and of the two original files are compared before and after it |
| the retry of the original raw streams | `_LaunchAggregate._release_raw_streams` (`7281-7369`) | `min(caller, original context, published cleanup)` read **before every close** | the clock of that domain (`_release_bound`) | F1: the close that the retry performs is the one that the recovery performs; the convergence never repeats it |
| the wait of the process of a launch | `_release_budget` (`7635-7655`) → `process.wait(timeout=budget)` | the **current** minimum of the caller and of the original context | the clock of the domain of that deadline | F1: the convergence performs **zero** terminate and **zero** wait (the counters are compared) |
| the read of the channel | `StreamChannel.read` (`5496-5529`) | `min(CHANNEL_POLL_SECONDS, the remaining of the channel)`, and **0** when the bound arrived | the clock of the channel (`_remaining`, `5352-5357`) | F3: the channel is bound to the clock of the round, so the crop is the **actual remaining** of the original context and not a number of another domain |
| the admission of the read of an endpoint | `_WindowsPipeEndpoint._admission_locked` (`4621-4643`) | the earliest of the call, of the bound of the endpoint, of the absolute deadline and of the published cleanup deadline | the clock of the endpoint (`_clock`) | F3: the endpoint is bound to the clock of the round through the channel; before the correction the deadline of the round (the domain of the facade) was compared with the clock of the host and the admission was refused |
| the dispatch of a generation of a worker | `_WindowsPipeWorker.run` (`4059-4117`) | the guard of the generation: the cancel flag and the current absolute deadline of the round | the clock of the worker (`_clock`) | F3: the worker inherits the clock of its endpoint and therefore the clock of the round |
| the wait of the reply of the parent | `v0_s3_native_custody.py:_ChannelPump.take` (`887-928`) | `min(the deadline of the call, the current effective deadline of the original context)` | the clock of the pump (`_clock`, the clock of the session) | F3: the timeout of the call is now **longer** than the published cleanup deadline, so the recorded argument is the bound of the **original context** and not the timeout of the call |
| the wait of the reply of the parent (the zero expiry) | `_ChannelPump.take` | the absolute deadline of the round, which is now in the past | the clock of the pump | F3: the recorded argument is `0.0` and the pump of the round really ends |
| the wait of the result of a startup step | `_StartupOwner.await_result` (`5828-5865`) | the current effective deadline of the original context, cropped to the poll slice of the package | the clock of the owner | untouched by the correction |
| the settle of a startup step | `_StartupOwner.settle` (`5867-5899`) | the bounded wait of the thread of the step | the clock of the owner | F4: the settle of an **unproved** start still returns `False` and the owner is never released |
| the join of a thread of a startup step | the fixture of the group (`thread.join`) | the bounded wait of the fixture | the wall of the host | F4: the join is attempted only for a thread that **really started**; the join of a thread that never started is impossible (`RuntimeError`) |
| the wait of the outcome of a generation | `_WindowsPipeWorker._complete` (`4142-4179`) → `_WindowsPipeEndpoint._await` (`4709-4784`) | the outcome of the **named** generation, read before and after the coordination | the clock of the worker | F5: the cancel primitive of the failed coordination waits, bounded, for the outcome of that **specific** generation before it returns; the selection point of the production then really sees the published fault |
| the bounded join of the coordination | `_WindowsPipeEndpoint._cancel` (`4899-4909`) → `worker.join_bounded(self._remaining(deadline))` | the current remaining of the endpoint | the clock of the endpoint | F5: the join still **FAILS** in the failed coordination (the worker is held inside its own final close and release tail) and the failure is a parallel fact |
| the wait of the fault of the seam | `_M09TimeoutApi.read_stream` (`_outcomes.get(timeout=30.0)`) | the bounded wait of the synthetic primitive | the wall of the host | F5: the fault is delivered to the worker and the immutable outcome of the generation really exists before the cancel primitive returns |

## 2. The gates and the threads that the correction owns

| Owner of the test | Kind | Release | Join |
|---|---|---|---|
| the gate of the admission of F3 | an event of the test | `finally: admission_gate.set()` — **unconditional** | the pump of the parent is the thread of the production and it is joined by the session |
| the fresh pump of the zero expiry of F3 | a thread of the production that is never started | `finally: zero_pump.stop()` — **unconditional** | it is never started and it therefore owns no thread |
| the wait of the outcome of F5 | the bounded wait of the seam of the test | it is bounded by 15 s and it never decides the outcome | the worker of the read is stopped and joined with a bounded wait in the `finally` of the phase |
| the hold of the worker of F5 | the event of the seam of the test | `api.release_the_worker.set()` in the `finally` of the phase | the worker of the read is joined with a bounded wait in the `finally` of the phase |
| the threads of the startup steps of F4 | the threads of the production | the release event of the test | the unconditional bounded join stays for every thread that really started |

## 3. The bounds that the correction does **not** touch

* No production deadline, timeout, poll slice or budget changes.
* No production clock changes: the correction binds the clock of the
  round to the channel of the round **in the fixture** and it does not
  change a single byte of the production.
* No new lease: the extra release of F1 uses the **same** deadline
  value as the two releases before it.
* No wait is replaced by a counter: the original queue method, the
  original event wait, the original wait of the worker and the original
  join of the worker really execute in every phase.
