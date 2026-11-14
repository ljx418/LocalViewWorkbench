# Correction 16 — the three residual STATIC Majors of correction 15

Coordinate **V1/R1/WP-R1-U3/S3_P4**. Candidate base
`ee9715679276c2af8d8d1b445734f5102ac613fa`. Workpack **S3-P4-N1**.
Implementation root
`reports/v0-s3/product-gate0/implementation-native-custody-correction-16/`.

**This delivery is STATIC.** The candidate was never imported, never
collected, never run: no pytest, no ctypes, no native call, no runtime
probe, no operating system business process, no model/GPU/service, no
network/media/database/ledger/counter. Only the AST, the symtable, an
in-memory compile, the SHA256 of the source text and read-only Git
operations touched the candidate. **No Major is closed by this
delivery** and no Stage, native or product acceptance is claimed: the
closure of a Major belongs to a new independent review and to the gate
owner. The dynamic batch of the correction 15 stays **NOT_RUN** and the
189 PASS of the correction 14 stays the historical machine fact.

The independent review of the correction 15
(`native-custody-correction-15/test-review-01/review-result/review.md`,
F0/M3/m0, `CHANGES_REQUIRED`) is the **authoritative defect input**.
Its three Majors are **residual**: the substantial corrections of the
correction 15 are kept, only the exact remaining paths are closed.

---

## 1. The static causal design (the two seams and their exact owners)

The contract asks for a short static causal design **before** the
implementation: the public startup gate and the partial-owner
registration must be mapped to exact production locations, or the root
must be asked. Both seams exist in the production and they are
**supported** seams: no production code, no production outcome and no
public contract was changed.

### 1.1 The public startup gate

| Step | Production owner and location | What the fixture does |
| --- | --- | --- |
| the round is really started | `tools/v0_s3_native_custody.py:1709` `NativeCustodySession.start` | `start_round()` (test file `:2314`) calls the **production** `start()` through the production default launcher (`launcher=None` → `_default_launcher` → `launch_broker`) |
| the pump of the round is really started | `v0_s3_native_custody.py:1782` `self._start_background_thread('pump', pump)` → `:1393` | the pump is the **attached** pump of the round; the fixture never builds a replacement |
| the pump reaches its next admission | `v0_s3_native_custody.py:846` `raw = self._broker.read(CHANNEL_POLL_SECONDS)` → `v0_s3_native_broker.py:6467` `BrokerProcess.read` → `:5496` `StreamChannel.read` | the fixture holds that read at a transparent gate: the **class** method `BrokerProcess.read` is wrapped (test file `:2610`) and the wrapper forwards the original signature and the original result and decides only the schedule |
| the reply admission of the **public** start | `v0_s3_native_custody.py:1784` `ready = self._read_reply(('READY', 'REFUSED'))` → `:1270` `_read_reply` → `:1292` `pump.take(kinds, deadline)` | this is the admission that must observe the zero expiry |
| the seam that is **before** the current bound | `v0_s3_native_custody.py:895` `waiter = _ReplyWaiter(kinds)` — it is built **before** `:911-916`, where the admission reads `context.effective_deadline()` | the fixture subclasses `_ReplyWaiter` (test file `:2626`): the waiter tightens the **ORIGINAL** context of the round **at that exact moment** and records the actual wait |
| the reply wait of the public caller | `v0_s3_native_custody.py:917` `waiter.event.wait(max(0.0, remaining))` | the recorder of the fixture forwards the original wait and records the **actual** argument; the gate of the pump is released **after** that wait returned |
| the tightening itself | `v0_s3_native_custody.py:248` `_CustodyContext.bind_absolute_deadline` (it may only **shorten**) and `:292` `effective_deadline` | the fixture binds the absolute deadline of the round to the value of the clock of the round; the context of the round, the pump, the channel, the endpoints and the aggregate of the launch all read **that one** context |
| the queue of the attached pump | `v0_s3_native_broker.py:5513-5523` `StreamChannel.read` computes the current minimum and calls `self._queue.get(timeout=limit)` | the recorder of the fixture is installed on the queue of the round **at the construction of the channel** (test file `:2593`), i.e. before the pump of the round was started |
| the end of the pump | `v0_s3_native_custody.py:818` `_ChannelPump._remaining` and `:835` `run` | the pump ends when the bound of the round arrived; the fixture observes it and never infers it |

**The order of the schedule is forced by the production and not by the
fixture:**

1. the pump computes its remaining **before** the tightening (the round
   is alive) and it enters the read of the broker, where the gate holds
   it — the pump is therefore **inside** its read and its end of stream
   and its error cannot preempt the reply that the round owes;
2. the main thread reaches the reply admission of the **public** start;
   the waiter of the reply is built (`:895`), the fixture tightens the
   ORIGINAL context there, and the admission then calculates the
   current bound (`:911-916`) against the tightened context;
3. the reply wait really asks for **nothing** (`wait(0.0)`) and the
   admission really raises `CUSTODY_CHANNEL_TIMEOUT`;
4. the gate is released **after** that wait returned, so the attached
   pump really performs its next read and the queue of the round is
   really asked for **nothing**;
5. the public `start()` catches the failure, latches the unknown state
   and **returns** the evidence of the round — the returned state, the
   expected error cause and the retention are read from that returned
   evidence and never from a previous successful start.

The old correction 15 oracle (a private `_read_reply` after a
completed start, `test file :2289-2292` of the correction 15 blob) is
**gone**: it is not a public operation and it did not own the
admission. The direct helper of the group stays a **supplement** and
it is never the oracle.

### 1.2 The partial-owner registration

| Owner that may be lost | Production owner and location | The seam of the fixture |
| --- | --- | --- |
| a channel whose construction failed **after** its drain thread was started | `v0_s3_native_broker.py:5220` `StreamChannel.__init__`; the drain is started at `:5278` (`self._thread.start()`), **inside** the constructor | the channel registers itself with its custody at `:5265-5267` (`custody.retain('channel', self, 'constructing')`) **before** it builds anything: the custody of the fixture (`_RegistryCustody`, test file `:257`) registers the channel at that moment and forwards every call to the **original** custody of the round |
| the endpoints of the round | `v0_s3_native_broker.py:4505` `_WindowsPipeEndpoint.__init__` | the endpoints of the fixture are registered **immediately** after their construction (test file `:2220` for the launcher, `:2877`/`:3253` for the child) |
| a worker whose start did not return | `v0_s3_native_broker.py:4669` `_WindowsPipeEndpoint._start`: the worker is registered with the endpoint **before** it is started (`:4690`, `:4692`) and a failed start is **retained** (`:4699`) | the endpoint is registered with the fixture, so its workers and its retained workers are found at the salvage; a retained worker whose start did not return is **UNKNOWN** |
| the background threads and the closer threads of the round | `v0_s3_native_custody.py:1393` `_start_background_thread` (the record of the thread is written **before** the start, `:1424`) and `:1507` `_start_bounded_close` | the session is registered **immediately** (test file `:2314`); the state of every background thread and of the closer is read from the **records of the session** |
| the channel of the parent after the product dropped it | `v0_s3_native_custody.py:2183` `self.broker = None` (a complete close drops the reference) | the registry of the fixture keeps the channel **before** the close: the salvage never discovers the owner late from the product |

The registry is `_OwnerRegistry` (test file `:214`); the enumeration is
`_registry_owners` (`:499`); the expansion of a channel, of an endpoint
and of a session is `_channel_owners` (`:474`), `_endpoint_owners`
(`:449`) and `_session_owners` (`:415`).

---

## 2. The per-residual mapping (event, oracle, failure, cleanup)

### 2.1 M1 — the zero expiry of a **public** operation that is really in flight

| Item | Correction 16 |
| --- | --- |
| **event** | the public `NativeCustodySession.start` of a round that is really launched through the production default launcher; the reply admission of that start (`:1784`) is the admission that observes the zero expiry |
| **driver** | the gate of `BrokerProcess.read` (test file `:2610`) holds the **attached** pump of the round inside its real read; the waiter of the reply (`:2626`) tightens the ORIGINAL context **before** the current bound is calculated |
| **oracles** | `zero_reply_waits[-1] == 0.0` (the reply wait of the **public** caller) and `zero_queue_waits[-1] == 0.0` (the queue of the **attached** pump); both recorders forward the original signature and the original result |
| **premise** | `zero_premise['pump_at_admission'] is True` (the pump was really inside its read), `pump_eof_at_admission is False` and `pump_error_at_admission is None` (no EOF and no error preempted the reply), and `zero_gate_facts[0]['released'] is True` (the gate did not time out) |
| **expected error cause** | `'CUSTODY_CHANNEL_TIMEOUT' in zero_failures` and `zero_state == 'UNKNOWN_RETAINED'`, both read from the **returned** evidence of the public start (`zero_session.evidence()`) |
| **returned state / retention** | the whole returned evidence of the public start is captured **before** the salvage (`r07-zero-public-chain`), the retention of the round is the `broker_retained` fact of that evidence and it is never claimed by the fixture |
| **cleanup** | the gate of the test and the primitive of the round are released **unconditionally** in the `finally`; the **returned** state of the public stop is captured (`_capture_stop`, `:396`) **before** the salvage; the salvage joins every owner of the registry with a bounded wait and the proof of the cleanup runs in the `finally` |
| **negative** | the private helper of the group stays a supplement; the identity of the context and a previous successful start are **never** used as a coverage claim |

### 2.2 M2 — the evidence of the barrier, FAIL vs NOT_RUN and the outer inventory

| Item | Correction 16 |
| --- | --- |
| **event** | the checked barrier of the publication of the outcome of the **exact** generation (the predicate of the correction 15 is **kept** unchanged) |
| **persistence** | the facts of the barrier are written in their **own** document `phase + '-barrier'` (test file `:4180`) **before** the main assertions of the phase: the failure, the order, the observed generation, the observed kind and the observed **object** are durable even when the main assertions fail afterwards |
| **executed failure** | a phase that was **executed** and that failed is written as `{'status': 'FAIL', 'executed': True, ...}` with the facts that it really observed (the barrier record, the cancel calls, the expected generation, the published outcome, the state) — it is **never** written as `NOT_RUN` (`:4302` for the timeout schedules, `:4585` for the published-fault schedule) |
| **genuinely unreached** | only the documents that were **not** written are `NOT_RUN`: the local `except` writes them for its own phase and the **outer** inventory of the group (`:4904`) writes them for the schedules that were never reached |
| **outer inventory** | every main schedule and both negative barrier subcases are named **before** they run (`r10_documents`): `r10-timeout-confirmed`, `r10-timeout-failed`, `r10-barrier-absent`, `r10-barrier-wrong-generation` (each with `-barrier`, `-first`, `-second`) and `r10-published-before-timeout` (with `-first`, `-second`); an earlier failure can never leave the evidence of a later one ambiguous |
| **preserved** | the three distinct main schedules, the exact original error object, the actual parallel `BrokerError`, the two real stops with their original reader history and the held worker tail are **unchanged**; the checked predicate still fails closed and the two negative subcases are still explicit refusals |
| **external assertions** | the external assertions of the premise (success/refusal, the returned value, the exact generation, the exact kind, the exact object and the monotonic order) are **kept** and they are read from the record of the barrier |

### 2.3 M3 — the immediate registry, the unconditional cleanup and the proof that runs while a failure unwinds

| Item | Correction 16 |
| --- | --- |
| **registry** | `_OwnerRegistry` (`:214`): every owner is registered **immediately** (the session, the endpoints, the channel through the custody seam) and it is never discovered later from a product that may have dropped it |
| **partial construction** | the custody seam (`_RegistryCustody`, `:257`) registers the channel at `custody.retain('channel', ...)` — **before** the drain thread of the channel is started — so a construction that failed after the start of the drain still owns its drain |
| **parent launch failures** | a channel that the aggregate of the launch holds is registered by the same seam; the session is registered before the launcher runs |
| **endpoint retained workers** | `_endpoint_owners` (`:449`) enumerates the read worker, the write worker **and** the retained workers of the endpoint |
| **unknown start/liveness** | `_owner_start_state` (`:292`) returns `STARTED`, `NEVER_STARTED` or **UNKNOWN**. A liveness query that raises is UNKNOWN; an owner whose start did not return (the session says so in its record, the endpoint says so in its `_retained`) is UNKNOWN. An UNKNOWN owner **fails the proof** (`:363`, `:379`) and it is never taken for a never-started owner |
| **gates** | every gate of the fixture is released in the **outermost** `finally`: `api.frames_ready` of the parent, `zero_gate` and `zero_api.frames_ready` of the zero round, `gate`, `controlled_api.frames_ready` and the held primitive of the controlled subcases |
| **child close** | the close of the transport of the child runs in its own `finally` and the close of each endpoint runs in its own `try`: a close that failed never prevents the cleanup of the **other** endpoint, and every failure of a close is **recorded** (`child_close_failures`, `close_failures`) and never discarded |
| **salvage during unwinding** | the bounded joins **and** the liveness checks run inside the `finally` of the round, of the zero round and of every controlled subcase. The proof is computed by `_prove_salvage` (`:379`) as a **fact**: it runs while an ordinary failure is already unwinding and it only raises when nothing else is failing, so it never replaces the failure that is unwinding and it is never discarded |
| **returned state** | `_capture_stop` (`:396`) captures the **returned** evidence of the public stop — or the exception of the stop — **before** the salvage; the salvage never replaces it and the original deadline of the product is never renewed |
| **sentinel subcases** | the two sentinel subcases of the correction 15 are **kept** and three subcases are added: an **ordinary** `AssertionError` of the group, a close of the transport of the child that **fails**, and a construction of the transport of the child that fails **after** its drain thread was really started. Each of them is caught by **its own** type — never by a broad `Exception` — and each of them proves that the gates were released and that every owner that really started was joined |
| **negative** | no broad swallowing: the failures of a close are recorded and the proof of the cleanup fails on an unknown owner and on a left-behind owner |

---

## 3. The changed assertions, signatures and names

Only `tools/test_v0_s3_native_custody_correction10.py` was changed.

**New module level names** (all private to the module):

| Name | Line | Kind |
| --- | --- | --- |
| `_R07ConstructorFailure` | `:202` | exception (test only) |
| `_OwnerRegistry` | `:214` | class: the registry of the owners that the fixture starts |
| `_RegistryCustody` | `:257` | class: the custody seam of the fixture |
| `_owner_start_state` | `:292` | function: `STARTED` / `NEVER_STARTED` / `UNKNOWN` |
| `_assert_salvage_proved` | `:363` | function: the proof of the cleanup |
| `_prove_salvage` | `:379` | function: the proof as a fact |
| `_capture_stop` | `:396` | function: the returned state of the public stop |
| `_endpoint_owners` | `:449` | function: the owners of one endpoint |
| `_registry_owners` | `:499` | function: every owner of the round |
| `ZERO_GATE_SECONDS`, `ZERO_ADMISSION_SECONDS` | `:145` | the bounded waits of the fixture |

**Changed module level names:**

| Name | Change |
| --- | --- |
| `_started_owner` | **removed**: it mapped a liveness-query exception to "never started". It is replaced by `_owner_start_state`, which distinguishes UNKNOWN |
| `_salvage_threads` | the signature gained the keyword `states=None` (the start-state hints) and every fact gained the key `start_state`; the `started` key of an UNKNOWN owner is `None` and not `False` |
| `_session_owners` | the signature gained the keyword `prefix='session'` and the keyword `hints=None`; the names of the owners are now prefixed |
| `_channel_owners` | the signature gained the keyword `hints=None`; the retained workers of the two endpoints are enumerated and the drain of a channel is registered as UNKNOWN when it has no identity |
| `EVIDENCE_DIR` | points at the **NEW** directory of the correction 16; the documents of the correction 15 stay where they are |

**Changed inside the two nodes:**

* `start_round(round_session, round_api, round_clock_value, registry)` gained
  the keyword `registry`; it registers the session **immediately** and it
  restores the registry of the round in its `finally`.
* `clocked_stream_channel` installs the custody seam and the recorder of
  the queue of the round.
* `fake_make_endpoint` registers the endpoint **immediately**.
* `_m09_timeout_phase` gained the keyword `inventory=None`.
* `_m09_published_fault_phase` gained the keyword `inventory=None`.
* `controlled_failure` drives five checkpoints instead of two.

**No assertion was removed.** The predicates of the correction 15 are
kept; the new predicates are listed in the sections above. The
assertions that were **moved** from the end of the round into its
`finally` (the liveness of the owners) keep their predicate and they now
also run while a failure is unwinding.

---

## 4. The unchanged source proof

`source-pins.json` binds the bytes of the seven bound sources and
compares them with the candidate base `ee97156` (read-only
`git show`):

* `tools/v0_s3_native_broker.py` — **unchanged** (production)
* `tools/v0_s3_native_custody.py` — **unchanged** (production)
* `tools/test_v0_s3_native_custody.py` — **unchanged**
* `tools/test_v0_s3_native_custody_regressions.py` — **unchanged**
* `tools/test_v0_s3_native_custody_correction05.py` — **unchanged**
* `tools/test_v0_s3_native_custody_correction07.py` — **unchanged**
* `tools/test_v0_s3_native_custody_correction10.py` — **changed** (the
  only source file that the correction 16 changed)

`production_changed: false`. The public contract, the thresholds, the
189 node ids and their order, the root packets, the control documents
and the MANIFEST are **unchanged**. The reports of the corrections 14
and 15 are **untouched**.

---

## 5. The 189 node identities and their order

`node-identity.json` (produced by `node_identity.py`, AST only, no
collection, no import, no execution) compares the node ids of the five
modules of the batch with the frozen list of the plan of the root
(carried by the proved list of the correction 15):

```
frozen_count 189, derived_count 189, identical true, order_preserved true,
added [], removed []
```

117 original + 16 regressions + 24 correction05 + 18 correction07 +
14 correction10. **No node was added, renamed, removed or moved.** The
three residuals live **inside** the existing node ids
`tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer`
and `::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`.

`static-checks.json` (produced by `static_checks.py`, AST only) reads
the names, the signatures and the attributes of the production that the
correction uses — including the **read** of the handle of the broker,
the **custody** of the channel, the **retained** workers of an
endpoint, the **state** of the start of a background thread and the
waiter of the reply: **69 passed / 0 failed**.

---

## 6. The finite validation REQUEST (not an execution)

`validation-plan-request.json` is the **REQUEST** of the implementation.
It is not a plan of the root and it grants no authority. It asks the
root to pin the candidate, to write its own `plan.json` in its own
`validation-plan-01` directory of the correction 16, to copy the
trusted guard/runner/absence tools there byte for byte and to run
**three** commands **once**, in one batch of at most **300 s**:

1. `outer_counter_observe.py` — the absence of the counter **before**
   the batch;
2. `guard.py` + `runner.py` — the guarded batch of the **189** nodes;
3. `outer_counter_observe.py` — the absence of the counter **after**
   the batch.

The three commands are the inherited trusted tools of the
`validation-plan-01` of the correction 14; they are read only here and
they are never written, patched or replaced by the implementation.
The environment, the counter policy, the stdlib preload window, the
external guard, the stop rules and the `nodeids` are inherited byte for
byte from the REQUEST of the correction 15 and they are bound to the
**NEW** paths of the correction 16.

**Stop rules (unchanged):** the first HTTP 429 stops the batch with
`WAIT_BUDGET` — no retry, no other route, no takeover by the root. The
first refusal or timeout of an approval stops the batch — it is never
wrapped, never bypassed and never dressed up as a pass. A denial of the
guard at runtime is a FAILURE of the batch.

**The batch was NOT run.** No runtime plan of the correction 16 is
ACKed and none is requested beyond this REQUEST.

---

## 7. What is left

* the **root** pins the candidate, freezes the tools and ACKs the
  finite batch;
* the **independent** review of the test delta decides whether the
  three residuals are closed — this delivery never claims that they are;
* the **dynamic** evidence of the 189 nodes (the real queue and event
  arguments, the scheduling and barrier negative cases, the two-stop
  histories, all the returned states and the complete cleanup of the
  fixture) is only produced by that ACKed batch;
* the native claims stay `NOT_PROVEN`, the product Gate 0 stays open
  and no budget or checkpoint slot is reset.

## 8. The documents of this root

| File | Content |
| --- | --- |
| `report.md` | this report |
| `source-pins.json` | the pins of the seven bound sources and the proof that the production is unchanged |
| `source_pins.py` | the script of the pins (read-only git, no execution of the candidate) |
| `node-identity.json` | the exact 189 node ids and their order |
| `node_identity.py` | the script of the node identity (AST only) |
| `static-checks.json` | the 69 names, signatures and attributes of the production that the correction uses |
| `static_checks.py` | the script of the static checks (AST only) |
| `validation-plan-request.json` | the finite three-command REQUEST (≤300 s, one batch) |
| `static-implementation-receipt.json` | the receipt of the static delivery |
| `evidence/` | the directory in which the batch of the root writes the phase documents of the nodes |
