# N1 correction12 — implementation report (STATIC, not validated)

Coordinate: V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION.
Starting candidate `b05020a`, failed evidence `a9660eb` (preserved, unchanged).
Scope: the seven files of `native-custody-correction-12/scope.json` and the NEW
`implementation-native-custody-correction-12/` report root.

**This report signs no Major and no Stage.**  It reports what the source now
does and what the frozen nodes now assert.  The batch of 189 nodes has **not**
been executed by this implementation: the root pins the candidate, runs the
three commands of the plan request and reviews the result.

## 1. What was repaired

### 1.1 M07-A — the executable recovery of an unresolved original raw stream

Before: a launch whose channel was never built (the hash of the executable was
interrupted) released its process and its original handle, and the raw file of
its standard output that could not be closed was registered in the table of the
launcher **with the launch as its owner**.  The table coordinates only the
resources that belong to no launch, so the stream was skipped by every later
release: the reference was observable and there was no working cleanup route.

Now (`tools/v0_s3_native_broker.py`):

* `_LaunchAggregate` owns the **original raw streams** of the launch
  (`raw_streams`, `retain_raw_stream`, `forget_raw_stream`,
  `pending_raw_streams`).  The launch is the only owner that may retry them.
* `_LaunchAggregate.release` retries the streams that a **previous** release
  could not confirm (`_release_raw_streams`): it closes them under the
  **current** bound of the release (`_release_deadline`, the deadline of the
  caller together with the absolute and the published cleanup deadline of the
  original context), it records the confirmed close and it forgets the stream
  **before** it leaves the table of the launcher.  A stream that is owned by a
  channel — a live channel or a partial one — is never closed by the launch.
  An expired bound never starts a new close.  A cancelled retry keeps the
  owner and the original cancellation is the error that leaves.
* `_LauncherCustody.release` never resurrects a resource that the launch
  released while the release was running: the stale snapshot of the table
  neither names it as retained nor keeps it.
* The process, its exit and its original handle are never released twice: the
  launch forgets the process only when its exit was confirmed and its handle
  was released, and the retry of a raw stream never touches the process.

### 1.2 M08-A — the current context at the actual worker dispatch

Before: the worker decided the admission of a generation from the **captured**
request of the call — the flag of the call and the numeric deadline that the
endpoint had copied — and from its own cancel flag.  A cancellation or an
expiry that was published on the original context of the round **before** the
dispatch was not consulted, and the primitive of the round ran.

Now:

* `_WindowsPipeWorker.run` consults the **current** original context at the
  moment of the decision of the dispatch: the cancel of the context refuses
  the admission and the effective minimum of the context (the bound of the
  call, the **current** absolute deadline and the **published** cleanup
  deadline) refuses it when it arrived.  The refused generation performs
  **zero** primitive calls and the outcome of that very generation carries the
  refusal.
* `_WindowsPipeEndpoint._await` notices the cancellation of the original
  context as well and not only the flag of the call.  No promise of an atomic
  undo of an operating system call that already began is made.

### 1.3 M08-B — the current bound of the normal `BrokerProcess.close`

Before: `_cleanup_deadline` was read **once** at the top of the close and the
value was used by every wait of the process, although the close of the channel
may publish a shorter cleanup deadline in the meantime.

Now: the bound is read **again** immediately before **every** wait of the
process, including the retry after the termination.  The aggregate helper of
the launcher already reread the context and it is preserved.

### 1.4 M08-C — one current-context wait bound and no positive floor

Before: the owner of a startup step compared a **copied** number, the wait of
the endpoint always asked for the poll slice, the put of the reader of the
channel always asked for 0.5 s and the read of the transport of the loop was
floored at 0.01 s.

Now:

* `_StartupOwner` holds the **original context** of the round (and the
  deadline it received).  `await_result` asks the current absolute deadline
  and the published cleanup deadline before every next wait and the wait of
  the queue is `min(poll cap, remaining)`.  There is no positive floor beyond
  the remaining: an expired round refuses at once and a cancellation of the
  original context is named.
* `_WindowsPipeEndpoint._await` asks `min(poll cap, current remaining)` for
  every wait of its worker (`_wait_slice`).
* `StreamChannel._drain` asks `min(0.5 s, current remaining)` for the put of
  the reader (`_put_wait`); an expired round refuses before the put.
* `BrokerLoop._loop` asks `min(poll cap, remaining)` for the read of the
  transport; the positive floor of 0.01 s is gone and an expired lease stops
  the round.

The bound of the wait is an **argument** of the wait: no claim of a scheduler
precision and no claim of an atomic shortening of an operating system call
that already began is made.  Native convergence stays `NOT_PROVEN`.

### 1.5 M08-D — a real join after an interrupted start

Before: the owner of a startup step decided from a private flag that was
written **after** `Thread.start` returned.  A start that raised after the
thread really came up left the flag unset and the owner never joined the
thread that it really had.

Now: the facts of the thread itself (its identity and its liveness) decide
(`_thread_facts_started`).  A thread that really started is joined for real,
even when the start raised afterwards; a thread that never came up stays
**unknown**, the owner is never released, no join of a thread that never
started is attempted, no replacement thread is built and the original
interruption object survives.  A later settle of the **same** owner converges
after the real exit of the thread.

### 1.6 M08-E — the launch honours the public stop and the published cleanup

Before: `_check_launch_budget` consulted the cancel and the **absolute**
deadline only.  A round that published its cleanup deadline — the public stop
of the round does exactly that — and whose cleanup expired was still allowed
to create a process.

Now: the check uses the **effective minimum** of the original context (the
absolute deadline **and** the published cleanup deadline) and it honours the
stop, the cancel and the unknown state of the round.  A launch that is
prepared after the public stop of the round creates no process, it hashes no
executable and it builds no channel.

### 1.7 The three observed test defects — reconciled, not weakened

1. **N10-R02** (`test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive`):
   the scripted `GetProcessTimes` wrote its fields on the *reference* that
   the production hands to the birth query (`ctypes.byref`) instead of on the
   structure behind it; the group raised an `AttributeError` before the race
   was ever reached.  The seam writes through the structure
   (`structure_of(...)` in the shared module, the `_obj` of the reference) and
   the shared `SyntheticKernel32` default uses the same helper.  The
   event-gated race, the refusal code and the single closer of the original
   handles are unchanged and are now really exercised.
2. **N10-R04** (`test_n10_r04_the_launch_aggregate_finds_the_partial_channel`):
   the node built a channel without ever binding the **original process** to
   the aggregate that owns it, so the release of the aggregate coordinated
   `self.process`, which was `None`.  The node now drives the **production
   adoption** (`_adopt_broker_process`) with the production `channel_factory`:
   the process is bound to the aggregate and registered with the table of the
   launcher **before** the partial channel is built.  The release coordinates
   the channel **before** the process, the raw files of the process are never
   closed under a live channel endpoint, the incomplete start keeps its owner
   and the **same** owner closes the read end exactly once later.
3. **N10-R10** (`test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`):
   the node read the outcome of the **hard coded** generation 1, which is not
   the generation of the blocked read of the real chain (the two frames of
   the round are read before it).  The generation is now the fact of the
   worker itself (`worker._submitted` at the moment the reader is really
   inside its read) and the node asserts that the outcome belongs to that
   generation.

### 1.8 M09 — the dynamic coverage replaces the auxiliary static proof

The auxiliary AST ordering proof of N10-R10 has been **removed** and replaced
by the dynamic schedule of the obligation, inside the same node id:

* a real ordinary fault is published for the **current** generation of the
  read of the **real chain** (`Session` → `BrokerProcess` → `StreamChannel` →
  endpoint → worker);
* the effective timeout of the round arrives **before** the endpoint consumes
  the outcome;
* a **confirmed** coordination and a **failed** coordination of the round are
  both driven and both preserve the **exact original error object** and its
  code: the timeout and the failure of the coordination are **parallel**
  facts (`lvw_parallel_timeout`) and they never replace the published
  failure;
* the history of the error keeps it across the channel, the handle of the
  broker and the **two public stops** of the round, and the round stays
  `UNKNOWN_RETAINED`.

The close-token and the exact/one-over overflow schedules stay separate
subcases of N10-R11 and are unchanged.

### 1.9 PF12-01 — the required order of the M09 schedule

The static preflight of the root (PF12-01, candidate `025146b`) found that
the dynamic schedule of the correction 12 drove the **late** fault: the
effective timeout of the round was decided **first** and the ordinary failure
of the read was published by the cancellation of the operating system
**during** the coordination of that timeout.  The distinct order that the
contract requires — the fault is **already published**, and the effective
timeout arrives **before** the endpoint consumes the outcome — was not
driven.

The follow-up is a **test only** correction inside the same node id
(`test_n10_r10_...`).  The production blobs of `025146b` are **unchanged**.

The new subcase (`_m09_published_fault_phase`, phase
`r10-published-before-timeout`) drives the required order with a transparent
gate at the actual await wait/selection boundary:

* the gate (`_M09Gate`) is a wrapper of the **production** wait of the
  worker (`_WindowsPipeWorker.wait_done`): it calls the **original** wait and
  it holds the endpoint **after** that wait returned and **before** the
  endpoint rechecks or consumes the outcome of its own generation.  It never
  decides the outcome, never rewrites the history of the error, never touches
  the selection of the error of the endpoint and never returns a fact of its
  own — it only decides **when** the endpoint continues.  It holds **one
  named worker** (the read worker of the round) and only while the read is
  really in flight: the frames of the start of the round and the write of the
  round are never held.
* the ordinary failure of the read is published **independently** of the
  timeout of the round (`api.publish_read_fault()`), and the **specific**
  outcome of the **named** generation is waited for (`_wait_for_outcome`): the
  generic event of the worker is only a wake up, because it may be stale.
* only then the effective timeout of the round arrives (the bound of the
  round is advanced), and only then the endpoint is released: it rechecks the
  timeout, it finds the **published** outcome of its own generation and it
  raises the **exact original error object** with the timeout as a
  **parallel** fact.
* the order that was driven is recorded: `GATE_ENTERED` →
  `FAULT_PUBLISHED` (with the generation and the sequence of the completion)
  → `TIMEOUT_ARRIVED` (with the clock and the effective deadline) →
  `RELEASED` → `OUTCOME_CONSUMED` (with the parallel fact), and the node
  asserts that the publication precedes the timeout and that the timeout
  precedes the consumption.
* the history of the error is checked across the channel, the handle of the
  broker and the **two public stops** of the round: `channel_reader_error`
  is `RuntimeError`, the source of the second attempt is `REPEATED_CLOSE`
  and the state is `UNKNOWN_RETAINED`.
* the teardown is bounded and unconditional: the gate is released, the read
  of the round is ended, the production wait of the worker is restored and
  the worker is joined with a bounded wait.

The two **coordination** subcases of the correction 12 are **kept**: they are
the ones that drive a **confirmed** and a **failed** coordination of the
round, and the failure of the coordination is a parallel fact there.  The
required order and the coordination orders are now three **distinct**
schedules inside the same node id:

| Subcase | Order | Coordination |
|---|---|---|
| `r10-published-before-timeout` | the fault is published, **then** the timeout, **then** the consumption | none is needed: the outcome was already published when the timeout was decided |
| `r10-timeout-confirmed` | the timeout is decided, **then** the fault is published **during** the coordination | confirmed: the worker really ended |
| `r10-timeout-failed` | the timeout is decided, **then** the fault is published **during** the coordination | failed: the join was not confirmed and the failure of the coordination is a parallel fact |


## 2. What was preserved

* The closed static obligations of the correction 11 stay closed: the M05
  transfer and direct cleanup claims, the M09 original error selection, the
  m03 live predicate, the M06 identity notification and the M03 confirmed exit
  safety are **not** touched by this batch.
* The **exact 189 node ids and their order** are unchanged.  The list was
  compared statically (AST of the five modules against the frozen
  `nodeids` of the plan of the root): 189 = 189 and the two lists are
  identical.
* No public schema, protocol, threshold, Stage or product denominator changed.
* The historical reports of the corrections 11/10/09/08 are unchanged and the
  failed evidence `a9660eb` is preserved.  The diagnostics of the frozen
  nodes are written in the **new** root of the correction 12
  (`implementation-native-custody-correction-12/evidence` and
  `.../f5-evidence`); the documents of the failed batch of the correction 11
  stay where they are.

## 3. The static boundary of this implementation

Executed, and nothing else:

* `compile()` of the source text of the seven files **in memory** (no import,
  no execution, no bytecode written);
* an AST/`symtable` global-resolution check of the same seven files;
* a static comparison of the 189 node ids against the frozen list of the root;
* `git status`, `git diff --stat` and `sha256sum` of the seven files.

**Not** executed: no candidate import, no collection, no pytest, no ctypes,
no native call, no runtime probe, no helper probe, no service, no GPU, no
model, no network, no database, no media, no ledger and no counter.  The
old authorisation of the correction 11 is terminal and it was not replayed.

## 4. The limits of this report

* Every native claim of this package stays `NOT_PROVEN`: no Windows API, no
  job object, no GPU, no port and no service was executed.
* The repairs above are **static** until the root pins the candidate and runs
  the batch of 189 nodes.  A failure of that batch is a failure of the batch
  and it is reported as such.
* No Major is closed by this report and no Stage is passed by it.
* The goal of the batch stays the remaining V1 to the next human gate and not
  the local 189 nodes.

## 5. The handoff

* `atomic-coverage.md` — the map of every subpath to its production owner,
  its event, its oracle, its negative, its returned state and its salvage.
* `changed-assertions.md` — every assertion that this batch added, changed or
  replaced.
* `wait-inventory.md` — the complete inventory of the waits that this batch
  touched, with the requested values before and after the tightening.
* `source-pins.json` — the digests of the seven files and of this report root.
* `static-implementation-receipt.json` — the static receipt of this batch.
* `validation-plan-request.json` — the request for the **exact three
  commands** of one finite batch of at most 300 s, with the 189 frozen node
  ids, the inherited pins of the root and the stop rules.
