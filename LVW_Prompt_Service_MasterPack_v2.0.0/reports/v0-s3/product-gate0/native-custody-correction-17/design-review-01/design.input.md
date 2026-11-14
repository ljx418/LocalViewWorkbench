# Correction17 — bounded static design for the three open Majors of correction16

**DESIGN ONLY.** This document changes **no** product source and **no** test
source. It is the causal design that correction17 requires **before** any
source edit is permitted (correction17 `contract.md` §"CURRENT AUTHORITY IS
DESIGN ONLY", `decision.json` = `DESIGN_REVIEW_REQUIRED_BEFORE_CORRECTION17_SOURCE_EDIT`).

* Coordinate: **V1 / R1 / WP-R1-U3 / S3_P4**.
* Candidate baseline: **`4dafa1f316242d8bd348b81c52f375aa37254754`**
  (the correction16 static candidate; `git rev-parse HEAD` of the implementer
  worktree `ljx418/lvw-v1-d0-implement`).
* Authoritative defect input: the **independent** review of that candidate —
  `reports/v0-s3/product-gate0/native-custody-correction-16/test-review-01/review-result/`
  (`review.md`, `receipt.json`, evidence `01`–`06`) — together with the
  correction16 contract, the correction17 contract/scope/decision, and the
  root pack `AGENTS.md`, `.agent-governance/`, `plans/execution-control.json`,
  `docs/24_EXECUTION_MASTER_PLAN.md`.
* Denominator: the **189** frozen node identities and their order are
  untouched. No production change, no schema change, no threshold change, no
  contract change is proposed here.

## 0. What this document does and does not claim

* It **maps each of the 16 open residual items** of the correction17 contract
  (M1 ×4, M2 ×7, M3 ×5) to a numbered, local, bounded change item (C1…C22)
  with an exact call site, an exception boundary, a maximum wait and a precise
  negative oracle.
* It **maps every removed / weakened assertion** of the correction16 candidate
  (seven predicate units, eight prior occurrences — evidence01) to an
  **equivalent or stronger** predicate. No predicate is weakened anywhere in
  this design, and the exact controlled-failure predicates are restored in a
  stronger form (§5).
* It does **not** claim that any Major is closed, that any node passes, that
  the native component is proven, that the Stage passes, or that any budget is
  reset. `dynamic15 = NOT_RUN`, `dynamic16 = NOT_RUN`, `native = NOT_PROVEN`,
  `stage_pass = false`.
* It does **not** authorise execution. No runtime plan is requested here; the
  implementation scope (which files may then be edited) needs an explicit root
  design ACK, and a *separate* frozen runtime plan needs its own ACK.

### 0.1 Bound inputs (sha256, byte exact)

| input | sha256 | note |
|---|---|---|
| `tools/test_v0_s3_native_custody_correction10.py` | `3c1c89e660cf79f1d51b5153de457aa6089d69d077db5d1d9b576f965659b74a` | candidate blob, 263082 bytes / 5371 lines |
| `tools/v0_s3_native_broker.py` | `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` | production, **unchanged** |
| `tools/v0_s3_native_custody.py` | `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581` | production, **unchanged** |

Line references below use `T10:<line>` for the candidate test module,
`B:<line>` for `tools/v0_s3_native_broker.py` and `C:<line>` for
`tools/v0_s3_native_custody.py`, exactly as the independent review does.

---

## 1. Residual → change-item map

| residual (contract17 §M1/M2/M3) | independent-review trigger | change items |
|---|---|---|
| **M1-a** correct the actual class-method patch signature | review M1 trigger 1 (`T10:2676-2677` patches the module attribute `BrokerProcess` with the string `'read'`) | **C1** |
| **M1-b** separate the actual `None`/error from its display `repr` | review M1 trigger 2 (`T10:2650-2651`, `T10:2705-2706` store `repr(pump.error)`; `T10:2733` demands `is None`) | **C2** |
| **M1-c** capture the **actual public start return** | review M1 "remaining oracle issue" (`start_round` discards the return at `T10:2347`/`2352`; `T10:2689` re-reads `evidence()`) | **C3**, **C4** |
| **M1-d** exact cause / state / **actual retained resource identity+value** | review M1 (`T10:2772` asserts only that the key `broker_retained` exists; `evidence()` always supplies it at `C:2361`) | **C5** |
| **M1-e** actual start/pump/queue/reply/gate ordering, bounded checked no-EOF/timeouts | review M1 "remaining oracle issue" + `C:887-929` (`take`), `C:1744-1756` (start returns a structured failure), `B:5496-5529` (`read` crops to the current bound) | **C6**, **C7** |
| **M2-a** complete inventory installed **before any** setup or earlier r10 assertion | review M2 residual trigger 2 (`T10:4743-4890` precedes the inventory at `T10:4903`) | **C12** |
| **M2-b** attempted state before every construction / phase / stop | review M2 residual trigger 2 (`_chain` at `T10:4097`, `T10:4447` before the local guards) | **C8**, **C10**, **C11**, **C12** |
| **M2-c** durable barrier facts **before** the relevant assertions | review M2 (`T10:4122-4169` precede the barrier snapshot at `T10:4174-4191`) | **C10** (and **C11** for the published-fault schedule) |
| **M2-d** explicit final **FAIL** even if the raw document was already written | review M2 residual trigger 1 (`T10:4296-4299` skips every name already in `written`) | **C9**, **C10**, **C11**, **C12** |
| **M2-e** an attempted stop that raises is **FAIL**, not `NOT_RUN` | review M2 residual trigger 1 (`T10:4316-4318`) | **C10**, **C11** |
| **M2-f** a document is marked *written* only **after** persistence succeeded | review M2 (`record()` at `T10:4104-4116` marks before `write_phase`) | **C9** |
| **M2-g** every main and negative schedule covered; no inventory overwrite; no fabricated facts | review M2 + `write_phase_not_run` at `T10:180-188` | **C12**, **C13** |
| **M3-a** outer owner cleanup encloses `start_round` **and** the RUNNING assertion | review M3 residual trigger 1 (`T10:3221-3224` before the inner guard at `T10:3233`; outer `finally` at `T10:3388` sets only the frame) | **C14** |
| **M3-b** deliberate sentinel / ordinary / constructor failures caught **outside** the whole cleanup region | review M3 residual trigger 2 (`T10:3308-3326`, `T10:3280-3296`) | **C14**, **C15** |
| **M3-c** constructor seam: original `Thread.start` takes effect **then** raises **inside** the constructor | review M3 residual trigger 2 (`controlled_failing_channel` calls the whole constructor first, `T10:3275-3277`) | **C16** |
| **M3-d** transparent seam forwards actual starts/identity, retains partial channel custody | review M3 "full helper limitations" (`_RegistryCustody` at `T10:257-289`, `B:5256-5283`) | **C16**, **C17** |
| **M3-e** every started owner enumerated **promptly**, quiescence before the final snapshot | review M3 "full helper limitations" + "the fixture registry nevertheless registers containers, not every actual thread at its start" | **C17** |
| **M3-f** original deadline preserved; stop exception **plus** live state/retention recorded before salvage | review M3 (`_capture_stop` at `T10:396-412` omits state/retained on exception) | **C20** |
| **M3-g** salvage attempts **ALL** owners even when a join/liveness query fails; errors kept as UNKNOWN/failure; bounded; not swallowed | review M3 (`_salvage_threads` at `T10:326-360` catches only `RuntimeError` from `join`) | **C18**, **C19** |
| **M3-h** ident-less owner: `NEVER_STARTED` only with proven provenance, otherwise `UNKNOWN` | review M3 (`_owner_start_state` at `T10:292-323`, fallback at `T10:323`) | **C19** |
| **M3-i** reversed fallback helper arguments | review M3 (`_registry_owners` at `T10:537-541`) | **C21** |
| **M3-j** exact type/token assertions; reject unrelated close/endpoint errors | review M3 residual trigger 3 (`T10:3398`, `T10:3411-3413`) | **C15**, **C22** |

---

## 2. M1 — the public zero-admission chain (test module only)

### 2.1 C1 — the malformed patch (the review's trigger 1)

**Current (T10:2676-2677):**

```python
with unittest.mock.patch.object(broker_module, 'BrokerProcess',
                                'read', zero_gated_broker_read), \
     unittest.mock.patch.object(custody_module, '_ReplyWaiter',
                                ZeroTighteningWaiter):
```

`unittest.mock.patch.object(target, attribute, new, spec, ...)` — the third
positional argument is **`new`**, not a spec. The call therefore assigns the
**string** `'read'` to the *module* attribute `BrokerProcess`; the real class
is never patched, `B:7896` then tries to call that string, the launcher
failure is swallowed by `C:1744-1756` and the round returns a structured
failure — so **no** attached pump and **no** public reply admission is ever
created for the zero round. This is a static control/data-flow conclusion; no
runtime failure is claimed here.

**Proposed (C1):** patch the **class method** with the class as the target:

```python
with unittest.mock.patch.object(broker_module.BrokerProcess, 'read',
                                zero_gated_broker_read), \
     unittest.mock.patch.object(custody_module, '_ReplyWaiter',
                                ZeroTighteningWaiter):
```

* `zero_gated_broker_read(self, timeout)` (`T10:2610-2624`) keeps the
  **original signature** of `BrokerProcess.read` (`B:6467-6468`:
  `def read(self, timeout): return self._channel.read(timeout)`), so the
  replacement is a plain function installed on the class and it is called as
  `broker.read(timeout)` → `zero_gated_broker_read(broker, timeout)`.
* The replacement **forwards** the original unbound method
  (`zero_original_broker_read = broker_module.BrokerProcess.read`, captured
  at `T10:2590` **before** the patch) → `zero_original_broker_read(self, timeout)`.
  The original result is returned unchanged.
* The gate is **round-scoped**: it only holds the broker whose
  `self._context is zero_session._context`; every other broker keeps the
  original behaviour (`T10:2618-2619`).
* The `_ReplyWaiter` patch is unchanged: `custody_module._ReplyWaiter`
  (`C:764`) is looked up at **call time** inside `_ChannelPump.take`
  (`C:895`), so the patch really intercepts the waiter that the **public**
  start builds (`C:1784`, `C:1793`).

**Scope / max wait / negative oracle:** the patch lives only inside the
zero-round `with` block (`T10:2675-2685`) and is removed by the context
manager. The gate wait is bounded by `ZERO_GATE_SECONDS = 30.0`
(`T10:145`); the admission wait is bounded by `ZERO_ADMISSION_SECONDS = 15.0`
(`T10:146`). Negative oracle: if the gate is never reached, `zero_gate_facts`
is empty → `C7`/`Z10` fails with *"the admission of the zero round never
reached the gate"*; if the gate timed out, `zero_gate_facts[0]['released'] is
False` → *"the gate of the admission of the zero round timed out"*.

### 2.2 C2 — the actual error value vs. its display `repr`

**Current:** `T10:2650-2651` stores `repr(pump.error)` into
`zero_premise['pump_error_at_admission']` and `T10:2705-2706` stores
`repr(zero_pump.error)` into the facts; `T10:2733` then requires that stored
value to `is None`. A healthy pump has `error is None`, so `repr(None)` is the
**string** `'None'` and the premise can never hold.

**Proposed (C2):** keep the *display* form for the human-readable document but
store the **actual** value separately, and assert on the actual value:

| key | value | use |
|---|---|---|
| `pump_error_is_none` | `pump.error is None` (a real `bool`) | the assertion oracle |
| `pump_error_type` | `type(pump.error).__name__` or `None` | the failure name |
| `pump_error_repr` | `repr(pump.error)` or `None` | the display form only, **never** an oracle |

`T10:2733` becomes
`assert zero_premise['pump_error_is_none'] is True` (plus
`assert zero_premise['pump_error_repr'] is None` as the redundant display
check). The same split is applied to the facts document at `T10:2705-2706`
(`zero_pump_error_is_none`, `zero_pump_error_type`, `zero_pump_error_repr`).

### 2.3 C3/C4 — the **actual** public start return

`NativeCustodySession.start()` (`C:1709-1818`) **returns** `self.evidence()`
(`C:1808`, `C:1750`, `C:1754`, `C:1780`, `C:1798`) and never raises for an
ordinary failure. The fixture's `start_round` (`T10:2314-2352`) calls
`round_session.start()` at `T10:2347` and **discards** the return, returning
the session object instead (`T10:2352`); `T10:2689` then re-reads
`zero_session.evidence()` — a *later* evidence object, not the one the public
operation returned.

**Proposed (C3):** `start_round` keeps its arguments and captures the public
return value:

```python
start_return = round_session.start()      # the ACTUAL return of the public start
...
return start_return                        # the return of the helper
```

All three call sites bind it:

* `T10:2371` → `parent_start_return = start_round(session, api, clock, parent_registry)`
* `T10:2682` → `zero_start_return = start_round(zero_session, zero_api, zero_clock, zero_registry)`
* `T10:3221` → `controlled_start_return = start_round(controlled_session, controlled_api, controlled_clock, controlled_registry)`

(The helper returns the start result instead of the session; the session
object itself is already in scope at every call site, so no other use is
lost.)

**Proposed (C4):** the zero round uses the **captured return** as the returned
state of the product — `zero_returned = zero_start_return` — and the later
`zero_session.evidence()` is used only as a **cross-check** that the state
did not change after the return (`zero_session.evidence()['state'] ==
zero_start_return['state']`). The original failure is never overwritten by the
later read.

### 2.4 C5 — the actual public start / retention oracle

`evidence()` always supplies the key `broker_retained` (`C:2361`), so a
key-presence check (`T10:2772`) proves nothing. The **value** of the
retention and the **identity** of the retained resource are the oracle.

| id | oracle (exact predicate) | fact source | failure message |
|---|---|---|---|
| **Z1** | `zero_start_return['state'] == 'UNKNOWN_RETAINED'` | the value returned by the public `start` | *the public start of the zero round did not latch its state* |
| **Z2** | `'CUSTODY_CHANNEL_TIMEOUT' in zero_start_return['failures']` | same return (`C:1812-1813`) | *the public start of the zero round did not name the timeout of the admission* |
| **Z3** | `'CUSTODY_CHANNEL_EOF' not in zero_start_return['failures']` | same return | *the round ended at the end of the stream instead of the timeout* |
| **Z4** | `zero_start_return['broker_retained'] is True` | same return (`C:2361`) | *the round did not retain its broker* |
| **Z5** | `zero_broker is not None and zero_session.broker is zero_broker` | the live attribute (`C:991`, `C:1741`) and the object of the round | *the retained original resource is not the object of the round* |
| **Z6** | `zero_start_return['broker']['identity_source'] == 'PARENT_ORIGINAL_HANDLE'` **and** `zero_start_return['broker']['pid'] == zero_broker.pid` | same return (`C:1755-1761`) | *the identity of the broker is a claim and not the original handle* |
| **Z7** | `zero_start_return['pump_error'] is None` | same return (`C:2365-2367`) | *the pump of the round failed before the admission* |
| **Z8** | `zero_pump is zero_session._pump` **and** `zero_pump._context is zero_session._context` **and** `zero_pump.finished is True` | the **attached** pump (`C:1772`, `C:1782`) | *the attached pump of the zero round is not the pump of the session / did not end / has another context* |
| **Z9** | `zero_queue_waits[-1] == 0.0` **and** `zero_reply_waits[-1] == 0.0` | the **actual arguments** the production passed (`T10:2604`, `T10:2663`) | *the round asked for a wait after the expiry* |
| **Z10** | `zero_gate_facts` non-empty **and** `zero_gate_facts[0]['released'] is True` **and** `zero_gate_facts[0]['timeout'] == ZERO_GATE_SECONDS` | the recorded gate facts (`T10:2622-2623`) | *the gate of the admission of the zero round timed out* |
| **Z11** | the recorded order of §2.5 | the order trace | *the order of the start, the pump, the queue, the reply and the gate was not the required one* |
| **Z12** | `_assert_salvage_proved(zero_salvage, 'the round of zero')` | the salvage facts | *an owner of the zero round was left behind* |

Z1–Z3 are the **exact cause** of the failure (the timeout, not the EOF, not a
launcher refusal); Z4–Z6 are the **actual retention** (value + identity of
the retained original resource); Z8–Z10 are the **bounded, checked**
no-EOF / timeout facts; Z11 is the ordering; Z12 is the bounded cleanup.

### 2.5 C6/C7 — the actual ordering, with the bounded checked no-EOF/timeouts

A single ordered trace is recorded during the zero round. Every event is
appended **at the moment it happens**, by the transparent seam, with its
actual argument:

| id | event | recorded at | recorded argument |
|---|---|---|---|
| **E1** | `START_CALLED` | `start_round`, immediately **before** `round_session.start()` | — |
| **E2** | `PUMP_READ_ENTERED` | `zero_gated_broker_read`, before the gate wait (`T10:2620`) | the `timeout` the production passed |
| **E3** | `REPLY_WAIT_ENTERED` | `ZeroTighteningWaiter.recording_wait`, before the original wait (`T10:2664`) | the `timeout` the production passed |
| **E4** | `REPLY_WAIT_RETURNED` | immediately **after** the original wait returned and **before** `zero_gate.set()` (`T10:2665-2670`) | the original result (`False` at the zero expiry) |
| **E5** | `GATE_RELEASED` | `zero_gated_broker_read`, after `zero_gate.wait(...)` returned (`T10:2621-2623`) | `released` / `timeout` |
| **E6** | `QUEUE_GET_ENTERED` | `zero_recording_get` (`T10:2604-2606`) | the **actual** `timeout` the production passed to the queue |
| **E7** | `PUMP_ENDED` | the observation loop (`T10:2696-2700`) | `zero_pump.finished` |

**Required order (the assertion of Z11):**
`E1 < E2 < E3 < E4 < E5 < E6 < E7`.

* `E2 < E3` — the waiter of the reply is built by the admission of the public
  start (`C:895`) and its constructor waits for `zero_held`
  (`T10:2644-2645`), which is set inside the held read (`T10:2620`).
* `E4 < E5` — the gate is released by the reply waiter **after** the reply
  wait returned (`T10:2666-2670`); the pump is therefore still held while the
  reply admission completes, and the end of the stream / the error of the
  pump can never preempt the reply the round owes.
* `E5 < E6` — the attached pump performs its real read of the channel
  (`B:5496-5529`) only after the gate was released.
* `E6 < E7` — the pump really ends.

**Bounded, checked no-EOF / timeout facts (recorded and asserted):**

| id | check | source | bound |
|---|---|---|---|
| **N1** | `zero_premise['pump_eof_at_admission'] is False` — the pump was **not** at the end of its stream when the admission began | `T10:2648-2649` (`pump._eof`) | — |
| **N2** | the failure cause is the **timeout** and not the EOF (Z2 + Z3) — the round really failed on the admission, not on an early end of stream | `C:1874-1890` (the code of the failure) | — |
| **N3** | every queue wait recorded **after** `E5` has `timeout == 0.0` — a round whose bound arrived asks for nothing (`B:5513-5520`) | `T10:2604-2606` | ≤ the recorded arguments |
| **N4** | the reply wait of the admission asked for `0.0` (`C:910-921`: `remaining = limit - clock()`) | `T10:2663-2664` | — |
| **N5** | the gate wait is bounded by `ZERO_GATE_SECONDS` and the recorded `released` flag proves it did not time out | `T10:2621-2623` | 30.0 s |
| **N6** | the admission wait is bounded by `ZERO_ADMISSION_SECONDS` | `T10:2644-2645` | 15.0 s |
| **N7** | the observation loops are bounded (`T10:2696-2700`, `T10:2814-2818`) | — | 15.0 s each |

### 2.6 Exception boundaries of the zero block (M1)

The zero block keeps **one** `try/finally` whose `finally` owns the salvage
(`T10:2775-2796`), and the boundary is explicit:

* **Inside** the `try`: the public start, the observation of the attached
  pump, the durable document `r07-zero-public-chain` and the assertions Z1–Z11.
* **Inside** the `finally`: `zero_gate.set()` and `zero_api.frames_ready.set()`
  (the gates are released **unconditionally**), then `_capture_stop`,
  `_registry_owners`, `_salvage_threads`, `_prove_salvage`, the durable
  document `r07-zero-salvage`, and the raising of the proof failure **only**
  when no other failure is unwinding (`sys.exc_info()[0] is None`).
* **Never** inside: a `try/except` that swallows the failure of the public
  start. The public start returns a structured failure instead of raising
  (`C:1744-1756`, `C:1806-1817`) — the design therefore asserts on the
  **returned** value, and it does not convert a refusal into a skip.

---

## 3. M2 — truthful phase inventory, FAIL vs NOT_RUN, durable barrier

### 3.1 C8 — the attempt ledger (one small local helper)

A module-level ledger, used by the two M09 phase helpers and by the outer
`test_n10_r10` test:

```
_PHASE_STATES = ('PLANNED', 'ATTEMPTED', 'PASSED', 'FAIL', 'NOT_RUN')

class _PhaseLedger:
    def plan(self, name):        # named before it runs
    def attempt(self, name):     # AT THE MOMENT the operation is entered
    def pass_(self, name):       # only after every assertion of it held
    def fail(self, name, reason):# it was attempted and it failed
    def state(self, name):       # PLANNED / ATTEMPTED / PASSED / FAIL
    def names(self):             # in the frozen order
```

The ledger is **not** a framework: it is one small class next to
`_OwnerRegistry` (`T10:214-254`) with the same shape (a lock + a list) and
the same purpose (remembering, never deciding).

### 3.2 State-transition table

| from | event | to | durable document |
|---|---|---|---|
| `PLANNED` | the operation is **entered** (`attempt()` — called *before* the construction, the phase body or the stop call) | `ATTEMPTED` | none yet |
| `PLANNED` | the end of the test, the operation was never entered | `NOT_RUN` | `{'status': 'NOT_RUN', 'reason': <type of the first failure>}` — **no facts of the phase** |
| `ATTEMPTED` | the raw facts are written (durable, before the assertions) | `ATTEMPTED` (unchanged) | `{'status': 'EXECUTED', ...raw facts...}` |
| `ATTEMPTED` | every assertion of the operation held | `PASSED` | rewrite of the same path: `{'status': 'PASSED', ...raw facts...}` |
| `ATTEMPTED` | an assertion raised **or** the operation itself raised | `FAIL` | rewrite of the same path: `{'status': 'FAIL', 'executed': True, 'reason': <type>, 'detail': <str>, ...raw facts...}` |
| `PASSED` / `FAIL` / `NOT_RUN` | anything | unchanged (**terminal**) | never overwritten by the inventory |

### 3.3 Document lifecycle table

| document | written when | final status written by |
|---|---|---|
| `<phase>-barrier` | **before** the first assertion that depends on the barrier | the phase (PASSED) or the failure handler (FAIL) |
| `<phase>` | the raw facts, **before** the assertions | the phase (PASSED) or the failure handler (FAIL) |
| `<phase>-first` / `<phase>-second` | right after the corresponding **actual** stop returned | the phase (PASSED) or the failure handler (FAIL) — an **attempted** stop that raises is FAIL, never NOT_RUN |

`write_phase` (`T10:149-155`) overwrites the file at the same path, so the
"raw facts" write and the "final status" write are the **same** document:
the final status never erases the raw facts, it adds the verdict.

### 3.4 C9 — a document is marked *written* only **after** persistence succeeded

**Current (`T10:4104-4116` and `T10:4458-4463`):**

```python
def record(name, facts):
    written.add(name)                 # marked BEFORE the write
    if inventory is not None:
        inventory.add(name)            # marked BEFORE the write
    return write_phase(name, facts)
```

A `write_phase` that raises (disk error, encoding error) leaves the name
marked as written although no document exists.

**Proposed (C9):**

```python
def record(name, facts):
    path = write_phase(name, facts)    # the persistence FIRST
    written.add(name)                  # marked only after it succeeded
    if inventory is not None:
        inventory.add(name)
    ledger.pass_or_fail(name, ...)     # the ledger follows the same rule
    return path
```

The `written` set and the inventory are then a **reliable** membership test
for "a document exists on disk".

### 3.5 C10 — `_m09_timeout_phase` (`T10:4032-4329`)

Proposed shape (pseudocode; the production is untouched):

```python
def _m09_timeout_phase(document, plan, tmp_path, *, phase, confirm_the_worker,
                        hold_the_worker, barrier_probe='EXACT',
                        expect_barrier='PASSED', inventory=None, ledger=None):
    ledger.plan(phase); ledger.plan(phase+'-barrier')
    ledger.plan(phase+'-first'); ledger.plan(phase+'-second')
    api = _M09TimeoutApi(confirm_the_worker=confirm_the_worker,
                         hold_the_worker=hold_the_worker)
    api.barrier_probe = barrier_probe
    ledger.attempt(phase + '-construction')          # BEFORE the construction
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path, clock=clock)
    worker = None
    raw = {}                                          # the raw facts per document
    try:
        ledger.attempt(phase)
        session.start()
        # -- a WAIT, not an assertion: the barrier announces itself ----
        if expect_barrier in ('PASSED', 'REFUSED'):
            api.barrier_entered.wait(15.0)             # bounded wait
        barrier = dict(api.barrier)                   # the ACTUAL facts
        raw[phase + '-barrier'] = {...}                # the facts of the barrier
        record(phase + '-barrier', {'status': 'EXECUTED', 'barrier': barrier,
                                     'barrier_expectation': expect_barrier, ...})
        # -- only NOW the assertions of the phase ------------------------
        assert api.read_waiting.wait(15.0), ...
        ...
        record(phase, {'status': 'EXECUTED', **raw[phase]})
        assert <the assertions of the phase>
        ledger.pass_(phase)
        record(phase, {'status': 'PASSED', **raw[phase]})     # the rewrite
        # -- the FIRST real stop ----------------------------------------
        ledger.attempt(phase + '-first')
        first = session.stop()                        # a raise here => FAIL
        raw[phase+'-first'] = {...}
        record(phase+'-first', {'status': 'EXECUTED', **raw[phase+'-first']})
        assert first_facts.get('channel_reader_error') == 'RuntimeError', ...
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
        ledger.pass_(phase+'-first')
        record(phase+'-first', {'status': 'PASSED', **raw[phase+'-first']})
        # -- the SECOND real stop ---------------------------------------
        ledger.attempt(phase+'-second')
        second = session.stop()
        ...
    except BaseException as error:
        for name in (phase, phase+'-barrier', phase+'-first', phase+'-second'):
            state = ledger.state(name)
            if state == 'PASSED':
                continue                              # a passed document is final
            if state == 'ATTEMPTED':
                # it was EXECUTED and it failed: an explicit FAIL that keeps
                # the raw facts and the barrier facts
                record(name, {'status': 'FAIL', 'executed': True,
                              'reason': type(error).__name__,
                              'detail': str(error),
                              'barrier': dict(api.barrier),
                              **raw.get(name, {})})
                ledger.fail(name, type(error).__name__)
            # a PLANNED name is left to the outer inventory (NOT_RUN)
        raise
    finally:
        ... # the bounded teardown of the phase (unchanged)
```

**The three residual triggers are closed by construction:**

* **Trigger 1 (executed failure without FAIL):** the failure handler now
  rewrites the document of **every attempted** name as `FAIL`, including a
  name whose raw document was already written (`raw[name]` keeps the facts).
  A name in state `PASSED` is skipped — a passed document is terminal.
* **Trigger 2 (attempted stop ⇒ NOT_RUN):** `ledger.attempt(phase+'-first')`
  runs **before** `session.stop()`. If the stop raises, the name is
  `ATTEMPTED` → the handler writes **FAIL** (with the exception type and the
  live facts), never `NOT_RUN`.
* **Pre-inventory failures:** C12 moves the inventory to the top of the test.

### 3.6 C10a — the durable barrier facts **before** the relevant assertions

* `_M09TimeoutApi.cancel_synchronous_io` (`T10:3899-3994`) sets a new event
  `barrier_entered` **at the top of the barrier block** (before the wait for
  the outcome). The event is a *wait*, not an assertion: a phase that waits
  for it and then writes the barrier document cannot lose the barrier facts
  to an earlier assertion.
* The phase waits for it with a bounded 15 s wait **only** when the barrier
  is expected to run (`expect_barrier in ('PASSED','REFUSED')`). For
  `NOT_APPLICABLE` (the confirmed coordination) the barrier document is
  written immediately with the (empty) barrier snapshot, exactly as today
  (`T10:4227-4232`).
* The barrier document is written **before** the assertions at `T10:4192-4232`
  — this ordering already exists and is kept.
* The barrier snapshot of the failure path (`T10:4304-4306`) is **kept** — it
  is the salvage of the barrier facts into the FAIL record.

### 3.7 C11 — `_m09_published_fault_phase` (`T10:4414-4619`)

The same three rules, with the same call sites:

* `ledger.attempt(phase + '-construction')` before `_chain(...)`
  (`T10:4447-4449`);
* `ledger.attempt(phase)` before `session.start()` (`T10:4467`);
* `ledger.attempt(phase+'-first')` / `attempt(phase+'-second')` before the two
  real stops (`T10:4554`, `T10:4564`);
* the failure handler (`T10:4575-4597`) rewrites every **attempted** name as
  `FAIL` with the raw facts and the trace; the names that were never entered
  stay `PLANNED` for the outer inventory.

### 3.8 C12 — the outer inventory of `test_n10_r10` (`T10:4622-4963`)

**Current:** the inventory (`T10:4904-4912`) and the `try/except` that
installs it (`T10:4913-4963`) are installed **after** the earlier r10 real
checks (`T10:4745-4816`) and after the coordination block (`T10:4817-4888`).
A failure there exits the test before the inventory guard is entered, and the
five later schedule documents stay **absent** — ambiguous, not `NOT_RUN`.

**Proposed (C12):** the complete document list and the ledger are installed
at the **very top** of the test, before *any* setup and before *any*
assertion, and the **whole** body is inside the guard:

```python
def test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation(...):
    ledger = _PhaseLedger()
    r10_documents = []
    for r10_name in ('r10-timeout-confirmed', 'r10-timeout-failed',
                      'r10-barrier-absent', 'r10-barrier-wrong-generation'):
        r10_documents.extend([r10_name, r10_name + '-barrier',
                               r10_name + '-first', r10_name + '-second'])
    r10_documents.extend(['r10-published-before-timeout',
                           'r10-published-before-timeout-first',
                           'r10-published-before-timeout-second'])
    # EVERY document is named BEFORE anything runs
    for r10_name in r10_documents:
        ledger.plan(r10_name)
    try:
        document = _live_plan_document()          # the setup of the test
        plan = validate_launch_plan(document, now=time.time())
        ...
        session.start()                            # the earlier r10 checks
        ...
        _m09_timeout_phase(..., ledger=ledger)     # the five schedules
        ...
    except BaseException as error:
        raise                                      # the original failure wins
    finally:
        # every document that was never entered is NOT_RUN; a document that
        # was entered and failed was already written as FAIL by its phase
        for r10_name in r10_documents:
            if ledger.state(r10_name) == 'PLANNED':
                write_phase(r10_name, {'status': 'NOT_RUN',
                                       'reason': <the type of the first failure>})
```

Properties:

* The inventory is complete **before** any setup, construction or assertion.
* A document that a phase already wrote is never rewritten by the inventory
  (the ledger state is the authority, and the ledger is updated only after a
  successful persistence — C9).
* A `NOT_RUN` document carries **no fact** of a phase that was not
  established (`write_phase_not_run`, `T10:180-188`, keeps exactly that
  shape).
* The `finally` never replaces the original failure: the `except` re-raises
  first, and a write failure inside the `finally` is recorded in the receipt
  of the test instead of replacing the original exception.

### 3.9 C13 — no fabricated facts

* The `NOT_RUN` document of the outer inventory carries only `status` and
  `reason`.
* The `FAIL` document carries the **raw facts that were really observed**
  (`raw[name]`), the barrier facts and the exception type/detail — never an
  expectation.
* The inventory never writes a `PASSED` document.

---

## 4. M3 — the owner cleanup region, the genuine unwinding, the bounded salvage

### 4.1 C14 — the cleanup region encloses `start_round` **and** the RUNNING assertion

**Current (`T10:3220-3390`):** the inner `try` whose `finally` owns the
cleanup starts at `T10:3233`; `start_round(...)` (`T10:3221-3222`) and the
RUNNING assertion (`T10:3223-3224`) are **outside** it, and the outermost
`finally` (`T10:3388-3389`) releases only the frame. A controlled start
failure or a RUNNING assertion therefore leaves the subcase without the
fixture joins, without the proof and without the captured stop state.

**Proposed (C14) — the region is moved *outward* (one nesting level):**

```python
def controlled_failure(checkpoint):
    ...setup (session, registry, gates, holders)...
    try:                                     # (A) OUTER: the catch is OUTSIDE
        try:                                 # (B) the cleanup region
            controlled_start_return = start_round(controlled_session, ...)
            # the RUNNING assertion is made on the RETURNED evidence of the
            # public start (C3) and it is INSIDE the cleanup region
            assert controlled_start_return['state'] == 'RUNNING', ...
            ... build the child objects ...
            ... the deliberate failure is RAISED here (C15) ...
        finally:                             # (C) the cleanup region
            gate.set(); controlled_api.frames_ready.set()
            ... close the transport and the endpoints (each in its own try) ...
            controlled_stop = _capture_stop(controlled_session)   # C20
            owners, hints = _registry_owners(...)
            salvage = _salvage_threads(owners, states=hints)      # C18
            proof = _prove_salvage(salvage, 'the controlled round')
            facts = {... 'cleanup_ran_while_unwinding':
                        sys.exc_info()[0] is not None, ...}
            write_phase('r07-controlled-failure-%s' % checkpoint.lower(), facts)
            if proof is not None and sys.exc_info()[0] is None:
                raise AssertionError(proof)
    except <the exact expected type> as error:   # (D) caught OUTSIDE (B) and (C)
        raised = {'type': type(error).__name__, 'token': str(error)}
    return facts
```

Properties:

* `start_round` and the RUNNING assertion are inside the cleanup region: a
  failure of either is cleaned up, joined and proved.
* The deliberate exception **propagates through** the cleanup region (C) and
  is caught in (D) — **outside** the entire cleanup region. The cleanup
  demonstrably runs **while the exception is unwinding**: the region records
  `cleanup_ran_while_unwinding = (sys.exc_info()[0] is not None)` inside its
  `finally`, which is a **fact**, not an assumption.
* The proof failure of the cleanup never replaces the failure that is already
  unwinding (`sys.exc_info()[0] is None` guard, preserved from `T10:3386`).
* The frames/gates are released **unconditionally** in the outer `finally`
  (`T10:3388-3389`).

### 4.2 C15/C22 — genuine exception-unwind negative tests, exact type and token

The caller (`T10:3392-3413`) asserts the **exact** type and the **exact**
token of the deliberate failure, per checkpoint:

| checkpoint | deliberate failure | exact type assertion | exact token assertion |
|---|---|---|---|
| `PARENT_ADMISSION` | `raise _R07Sentinel(checkpoint)` inside the region | `type(error) is _R07Sentinel` | `str(error) == 'PARENT_ADMISSION'` |
| `CHILD_TRANSPORT` | `raise _R07Sentinel(checkpoint)` inside the region | `type(error) is _R07Sentinel` | `str(error) == 'CHILD_TRANSPORT'` |
| `ORDINARY_ASSERTION` | `assert controlled_session.state == 'NOT_A_STATE'` inside the region | `type(error) is AssertionError` | the message of the assertion is the group's own message |
| `CONSTRUCTOR_FAILURE` | the seam raises inside the constructor (C16) | `type(error) is _R07ConstructorFailure` | `str(error) == 'CONSTRUCTOR_FAILURE'` |
| `CLOSE_FAILURE` | the close seam raises inside the cleanup | the recorded close failure has `type == 'RuntimeError'` | `'controlled_close_failure' in detail` |

Every one of these is **raised inside** the cleanup region and **caught
outside** it (C14). The current code catches them **inside** the region
(`T10:3317-3321`, `T10:3323-3326`, `T10:3290-3291`) and therefore only proves
a *normal* `finally` after a caught error — not the cleanup *while
unwinding*.

**C22 — the close oracle rejects unrelated failures.** The current oracle
(`T10:3411-3413`) only asks whether *some* record has
`owner == 'controlled:transport'`. Proposed (strictly stronger):

```
close_failures = controlled_results['CLOSE_FAILURE']['close_failures']
assert len(close_failures) == 1                       # exactly one failure
assert close_failures[0]['owner'] == 'controlled:transport'
assert close_failures[0]['type'] == 'RuntimeError'     # the EXACT type
assert 'controlled_close_failure' in close_failures[0]['detail']   # the EXACT token
# and NO unrelated failure is tolerated:
assert not [f for f in close_failures if f['owner'] != 'controlled:transport']
assert not [f for f in close_failures if f['type'] != 'RuntimeError']
```

and, for **every** checkpoint, the ordinary-failure oracle of the *main* child
block (`child_close_failures`, `T10:2929-2964`) is asserted to be **empty**
except for the one intended failure — an unrelated close/endpoint error is a
failure of the test, never a tolerated extra.

### 4.3 C16 — the constructor seam: the original `Thread.start` takes effect, **then** raises **inside** the constructor

**Current (`T10:3273-3291`):** `controlled_failing_channel` calls the whole
real constructor and raises **after** it returned. It therefore tests a lost
assignment after a *successful* construction — not the partial-start trigger.

**Proposed (C16):** the seam wraps the **original** `threading.Thread.start`
and raises **after** the real start returned, so the thread really takes
effect and the exception is raised **inside** the constructor
(`B:5278`, inside the constructor's `try` at `B:5268-5283`):

```python
original_thread_start = threading.Thread.start

def start_then_raise(thread, *args, **kwargs):
    if thread.name != 'lvw-native-custody-channel' or not armed:
        return original_thread_start(thread, *args, **kwargs)   # forwarded
    registry.mark_starting(thread)                 # immediate registration
    original_thread_start(thread, *args, **kwargs) # the thread REALLY starts
    registry.mark_started(thread)
    raise _R07ConstructorFailure('CONSTRUCTOR_FAILURE')  # inside the constructor

with unittest.mock.patch.object(threading.Thread, 'start', start_then_raise):
    transport = broker_module.StreamChannel(...)     # the constructor raises
```

Properties:

* The **original** start is called and its result is honoured — the thread
  really runs; the seam only decides **when** the constructor fails.
* The seam is **round-scoped** by the thread name (`'lvw-native-custody-channel'`,
  `B:5257`) and by the `armed` flag: every other thread of the test is
  forwarded untouched.
* The patch is installed **only** around the constructor call and is removed
  by the context manager (no leak into the rest of the module).
* The **partial channel custody** is preserved: `B:5266-5267` retains the
  channel with its custody **before** it builds anything, and the fixture's
  `_RegistryCustody` (`T10:257-289`) forwards the original call
  (`self._original.retain(kind, resource, detail)` — the original signature
  of `B:7436`). The registry therefore holds the partially constructed channel
  and the fixture's cleanup can close it and join its drain thread.
* Because the drain thread really started, its start provenance is
  `STARTED` (C17) — not `UNKNOWN` — and the cleanup must really end it.

### 4.4 C17 — prompt owner registration and the quiescence condition

**Current:** the registry registers **containers** (a session, an endpoint, a
channel) — `T10:2242`, `T10:2336`, `T10:2877-2885`, `T10:3253-3263` — and the
actual threads are discovered **later** from a product that may already have
dropped them (`_session_owners` `T10:415-446`, `_endpoint_owners`
`T10:449-471`, `_channel_owners` `T10:474-496`). There is **no** proof that
every start had returned when the final snapshot is taken.

**Proposed (C17) — a transparent start-registration seam:**

* A module-level holder `start_registry = {'value': None}` (the same pattern
  as `api_table` / `round_clock` / `round_registry` at `T10:2250`, `T10:2274`,
  `T10:2280`).
* The seam wraps `threading.Thread.start` and forwards the original start.
  It registers the thread **immediately before** the original start (state
  `STARTING`) and marks it `STARTED` right after the original start returned
  (state `STARTED`); if the original start raises, the state is `FAILED` and
  the error is kept.
* Only the **named** production threads of this package are registered, so
  the seam is transparent for everything else:
  `'lvw-native-custody-channel'` (`B:5257`), `'lvw-native-custody-pipe-read'`
  / `'lvw-native-custody-pipe-write'` (`B:4680`),
  `'lvw-native-custody-channel-pump'` (`C:791`),
  `'lvw-native-custody-heartbeat'` (`C:1390`),
  `'lvw-native-custody-closer'` (`C:1531`).
* The registry gains three small methods: `mark_starting(thread)`,
  `mark_started(thread)`, `pending_starts()`.

**Quiescence condition (asserted before the final snapshot):**

```
assert registry.pending_starts() == 0, \
    'a start of the round had not returned when the owners were enumerated'
```

The final owner snapshot is taken **only after** the quiescence condition
holds; a non-zero pending count is a failure of the cleanup proof (the owner
is `UNKNOWN`), never a silent omission.

### 4.5 C18 — the salvage attempts **ALL** owners, even when a join or a liveness query fails

**Current (`T10:326-360`):** only `RuntimeError` from `join` is caught; **any
other** exception from `join`, and **any** exception from `is_alive()`,
aborts the iteration — the remaining owners are never joined and the proof
document is never written.

**Proposed (C18):**

```python
def _salvage_threads(owners, *, seconds=10.0, states=None, total_seconds=30.0):
    facts = []
    hints = states or {}
    deadline = time.monotonic() + total_seconds
    for name, thread in owners:
        state = _owner_start_state(thread, hints.get(name))
        if state != 'STARTED':
            facts.append({'name': name, 'start_state': state,
                          'started': None if state == 'UNKNOWN' else False,
                          'alive': None, 'joined': None, 'error': None})
            continue
        error = None; alive = None; joined = False
        try:
            wait = max(0.0, min(seconds, deadline - time.monotonic()))
            thread.join(wait)
        except BaseException as exc:                 # ANY failure of the join
            error = {'type': type(exc).__name__, 'detail': str(exc)}
        try:
            alive = bool(thread.is_alive())
            joined = not alive
        except BaseException as exc:                 # ANY failure of the query
            error = error or {'type': type(exc).__name__, 'detail': str(exc)}
            alive = None; joined = False
        facts.append({'name': name, 'start_state': state, 'started': True,
                      'alive': alive, 'joined': joined, 'error': error})
    return facts
```

Properties:

* **Every** owner is attempted — a failing `join` or a failing `is_alive` is
  recorded and the iteration continues.
* The failure is **retained**, not swallowed: it is in the facts of the owner
  and it **fails the proof** (`_prove_salvage` must return a failure for an
  owner with `alive is None` or `error is not None`).
* The cleanup is **bounded**: at most `seconds` (10 s) per owner and at most
  `total_seconds` (30 s) for the whole salvage; the wait of an owner is
  cropped by the remaining total.
* The salvage is **separate** from the product: it renews no deadline of the
  round, it erases no retained resource and it never claims that the product
  released anything (the docstring of `T10:326-339` is kept).

### 4.6 C19 — the start state needs **proven provenance**

**Current (`T10:292-323`):** an owner without an identity that is not alive
is mapped to `NEVER_STARTED` (`T10:323`) — a guess, not a proof.

**Proposed (C19):**

```python
def _owner_start_state(thread, hint=None):
    if thread is None:
        return 'NEVER_STARTED'
    ident = getattr(thread, 'ident', None)      # guarded by try/except
    if ident is not None:
        return 'STARTED'
    if hint in ('STARTED', 'NEVER_STARTED', 'UNKNOWN'):
        return hint                              # proven provenance (C17)
    return 'UNKNOWN'                             # no provenance => UNKNOWN
```

`NEVER_STARTED` is now returned **only** when the registry proves that the
start was never invoked (or when the thread object does not exist at all).
An ident-less owner without provenance is `UNKNOWN` and **fails the proof**.

### 4.7 C20 — the stop: the exception **plus** the live state and the retention, before the salvage

**Current (`T10:396-412`):** on an exception the capture keeps only the type
and the detail; the live state and the retained resources of the moment are
lost.

**Proposed (C20):**

```python
def _capture_stop(session):
    captured = {'returned': None, 'exception': None, 'live_state': None,
                'retained': None, 'retained_broker_id': None,
                'background_threads': None}
    if session is None:
        return captured
    try:
        captured['returned'] = session.stop()
    except BaseException as error:
        captured['exception'] = {'type': type(error).__name__,
                                 'detail': str(error)}
        # the live state and the retention are read NOW, before the salvage
        try:
            captured['live_state'] = session.state
            captured['retained'] = session.broker is not None
            captured['retained_broker_id'] = id(session.broker)
            captured['background_threads'] = session.evidence().get(
                'background_threads')
        except BaseException:                     # the facts stay visible
            captured['live_state'] = 'UNKNOWN'
    else:
        captured['retained'] = session.broker is not None
        captured['retained_broker_id'] = id(session.broker)
    return captured
```

The stop exception is never discarded, and the live state / retention of the
moment are recorded **before** the salvage of the fixture.

### 4.8 C21 — the reversed fallback arguments

**Current (`T10:537-541`):**

```python
if session is not None and 'session' not in kinds:
    add(_session_owners('%s:session' % prefix, session, hints))   # reversed
if channel is not None and 'channel' not in kinds:
    add(_channel_owners('%s:channel' % prefix, channel, hints))   # reversed
```

`_session_owners(session, prefix='session', hints=None)` and
`_channel_owners(channel, prefix, hints)` take the **object first**; the
fallback passes the **name string** as the object and the object as the
prefix. The dedup key (`id(thread)`) is then computed over a string.

**Proposed (C21):**

```python
if session is not None and 'session' not in kinds:
    add(_session_owners(session, '%s:session' % prefix, hints))
if channel is not None and 'channel' not in kinds:
    add(_channel_owners(channel, '%s:channel' % prefix, hints))
```

(the registry-loop calls at `T10:529-534` are already in the correct order and
are unchanged).

### 4.9 The deadline of the product is preserved

Every wait of the fixture is the **fixture's** own bounded wait (≤ 10 s per
owner, ≤ 30 s per salvage, ≤ 15 s per observation, ≤ 30 s per gate). None of
them renews, extends or publishes a deadline of the round; the product's own
cleanup deadline (`C:2121-2133`) and the original `STOP_CLEANUP_SECONDS`
budget are untouched. The salvage is the work of the **test** and it is
recorded separately from the returned state of the product.

---

## 5. The removed / weakened assertions → equivalent or stronger predicates

The independent review (evidence01 / `receipt.json`) records **seven** removed
predicate units with **eight** prior occurrences, all in
`tools/test_v0_s3_native_custody_correction10.py` at the correction15
candidate `ee9715679276c2af8d8d1b445734f5102ac613fa`. Every one of them is
mapped here to a predicate that is **equal or stronger**. **No predicate is
weakened, and none is dropped without a replacement.**

| # | prior line | removed predicate (prior15) | replacement predicate in this design | strictly stronger because |
|---|---|---|---|---|
| **A1** | 2225 | `zero_session.state == 'RUNNING'` | **Z1** `zero_start_return['state'] == 'UNKNOWN_RETAINED'` **and** **Z2** `'CUSTODY_CHANNEL_TIMEOUT' in zero_start_return['failures']` **and** **Z3** `'CUSTODY_CHANNEL_EOF' not in ...` **and** **Z4/Z5** the retention value + the identity of the retained broker | the removed predicate was a **transient** state of a round that could fail right after it; the replacement is the **terminal** state **returned by the public operation**, it names the **exact cause** and it proves the **actual retained resource**. It is not comparable to a live attribute any more: it is the value the public `start` returned. |
| **A2** | 2231 | `zero_attached_pump is not None` | **Z8** `zero_pump is zero_session._pump` (identity) **and** `zero_pump._context is zero_session._context` **and** `zero_pump.finished is True` | identity instead of mere presence, plus the context and the proven end of the pump. |
| **A3** | 2233 | `zero_attached_pump.is_alive()` (a point-in-time liveness) | **Z8** `zero_pump.finished is True` **and** **Z9** `zero_queue_waits[-1] == 0.0` (the pump really performed the round's own read at the zero expiry) | a liveness **snapshot** is replaced by a **completed lifecycle** with the actual argument of the read. |
| **A4** | 2273 | `zero_held.wait(15.0)` | **N1** `pump_eof_at_admission is False` **and** **Z10** `zero_gate_facts[0]['released'] is True` **and** `timeout == ZERO_GATE_SECONDS` **and** **Z11** the recorded order `E1<E2<E3<E4<E5<E6<E7` | a bare "the event fired" is replaced by "the event fired **and** the gate did not time out **and** the order of the start, the pump, the reply and the queue is the required one". |
| **A5** | 2349 | `item['alive'] is False` (zero round) | **Z12** `_assert_salvage_proved(zero_salvage, ...)` — for **every** owner: `start_state != 'UNKNOWN'`, and for every started owner `alive is False` **and** `joined is True` **and** `error is None` | the per-item check becomes a **whole-round** proof that also rejects an unknown start state, an unjoined owner and a recorded join/query error. |
| **A6** | 2495 | `item['alive'] is False` (parent round) | the same whole-round proof over `parent_salvage` (C18/C19/C21), **plus** the stop exception with the live state and the retention captured before the salvage (C20), **plus** the quiescence condition (C17) | the parent round gains the same (and stronger) proof, plus the stop facts and the quiescence that the removed predicate did not have. |
| **A7** | 2788 | `controlled['sentinel'] == '_R07Sentinel'` | **C15**: `type(error) is _R07Sentinel` (the **class object**, not its name) **and** `str(error) == checkpoint` (the **token**), **and** `cleanup_ran_while_unwinding is True` (the cleanup really ran while the exception was unwinding) | a **string** equality on a type *name* becomes an **identity** check on the type **plus** the exact token **plus** the proof that the cleanup ran during the unwinding. The exact controlled-failure predicate is **restored** in a stronger form. |
| **A8** | 2796 | `item['alive'] is False` (controlled subcases) | the whole-round proof over the salvage facts of **every** controlled checkpoint (C18/C19), **plus** the exact close-failure oracle (C22) | the per-item check becomes a whole-round proof for every checkpoint, and the close oracle rejects unrelated failures. |

Two further weakenings that the review names explicitly are also repaired:

| # | weakened form in the correction16 candidate | replacement |
|---|---|---|
| **A9** | `assert controlled['failure'] is not None` (`T10:3398-3400`) — any non-`None` failure satisfies it | **C15**: the **exact** type **and** the **exact** token per checkpoint (`_R07Sentinel`/`AssertionError`/`_R07ConstructorFailure`/`RuntimeError`), plus the proof that the cleanup ran while unwinding. |
| **A10** | `assert any(item['owner'] == 'controlled:transport' ...)` (`T10:3411-3413`) — an unrelated failure may sit next to the intended one | **C22**: exactly one failure, exact owner, exact type, exact token, and **no** unrelated close/endpoint failure anywhere. |

**Restored count:** 7 removed predicate units / 8 occurrences → 10 explicit
replacements (A1…A10), of which A9 and A10 restore the two predicates that the
review names as weakened. **No blanket weakening; no assertion is removed by
this design.**

---

## 6. Proposed helper changes (summary)

| id | file / symbol | current lines | change | scope | max wait | negative oracle |
|---|---|---|---|---|---|---|
| C1 | T10 zero-round `patch.object` | 2676-2677 | patch the **class** `BrokerProcess.read` | the zero-round `with` block | gate 30 s | the gate facts are empty / `released is False` |
| C2 | T10 `ZeroTighteningWaiter` + facts | 2650-2651, 2705-2706, 2733 | store the actual error value separately from the `repr` | the zero block | — | `pump_error_is_none is not True` |
| C3 | T10 `start_round` | 2314-2352, 2371, 2682, 3221 | return the **actual** public start return | 3 call sites | — | the returned state is not the expected one (Z1) |
| C4 | T10 zero block | 2689 | use the captured return as the returned state | the zero block | — | the later `evidence()` disagrees with the returned state |
| C5 | T10 zero block | 2772 (+ 2723-2774) | the retention oracle Z4/Z5/Z6 | the zero block | — | the retention value is not `True` / the identity differs |
| C6 | T10 zero block | 2580-2586, 2610-2624, 2604-2606, 2663-2670 | the order trace E1…E7 | the zero block | 15 s per observation | the required order is violated |
| C7 | T10 zero block | 2644-2649, 2696-2700 | the bounded no-EOF/timeout checks N1…N7 | the zero block | 30 s / 15 s | N1…N7 fail → the named message |
| C8 | T10 `_PhaseLedger` (new, next to `_OwnerRegistry` 214-254) | new | the attempt ledger | the M09 phases and the r10 test | — | a name that was entered but has no final document |
| C9 | T10 `record()` | 4104-4116, 4458-4463 | write first, mark after | the two phase helpers | — | a document that is marked but does not exist |
| C10 | T10 `_m09_timeout_phase` | 4032-4329 | the attempt ledger, the durable barrier before the assertions, the FAIL rewrite | that helper | 15 s per wait | the FAIL document of an attempted name |
| C11 | T10 `_m09_published_fault_phase` | 4414-4619 | the same three rules | that helper | 15 s per wait | idem |
| C12 | T10 `test_n10_r10` | 4622-4963 (inventory at 4904-4963) | the inventory at the top, the whole body guarded | that test | — | a document of a later schedule stays ambiguous |
| C13 | T10 `write_phase_not_run` | 180-188 | unchanged in shape; the NOT_RUN document carries no fact | — | — | a NOT_RUN document that carries a fact |
| C14 | T10 `controlled_failure` | 3174-3390 | the cleanup region moves **outward** (encloses `start_round` + the RUNNING assertion) | that helper | — | `cleanup_ran_while_unwinding is not True` |
| C15 | T10 the controlled loop | 3392-3413 | the exact type + token per checkpoint | that loop | — | the type is not the expected class / the token differs |
| C16 | T10 the constructor seam | 3273-3291 | the original `Thread.start` takes effect and **then** raises inside the constructor | the `CONSTRUCTOR_FAILURE` subcase | — | the drain thread is not registered / the exception is not `_R07ConstructorFailure` |
| C17 | T10 `_OwnerRegistry` + a start seam | 214-254, new | the immediate start registration and the quiescence condition | the zero block and the controlled subcases | — | `pending_starts() != 0` |
| C18 | T10 `_salvage_threads` | 326-360 | attempt **all** owners; retain the errors; bounded total | every salvage | 10 s / owner, 30 s total | an owner with `alive is None` / `error is not None` fails the proof |
| C19 | T10 `_owner_start_state` | 292-323 | `NEVER_STARTED` only with proven provenance, else `UNKNOWN` | every salvage | — | an ident-less owner without provenance is `UNKNOWN` and fails the proof |
| C20 | T10 `_capture_stop` | 396-412 | the exception **plus** the live state and the retention | every salvage | — | the capture has no live state / retention |
| C21 | T10 `_registry_owners` | 537-541 | the fallback arguments in the right order | every salvage | — | a fallback owner is not enumerated |
| C22 | T10 the close oracle | 3398-3413, 2929-2964 | the exact close failure; no unrelated failure | the controlled loop | — | an extra / wrong-typed close failure |

**Nothing outside `tools/test_v0_s3_native_custody_correction10.py` changes.**
No production file, no schema, no contract, no threshold, no node id, no node
order, no historical report, no root packet / control / MANIFEST.

---

## 7. Constraint compliance and execution audit

| constraint (contract17 / AGENTS) | status in this task |
|---|---|
| Design only; no test/product source edit before the root design ACK | **honoured** — this task wrote only `design.md` and `design-receipt.json` |
| No implementation source edit / commit before the root design ACK | **honoured** — no commit, no source edit |
| 189 identities and order frozen | **honoured** — no test file was touched |
| No candidate import / collect / pytest / ctypes / runtime / native / OS business process / model / GPU / service / network / media / DB / ledger / counter | **honoured** — see the audit in the receipt: only text reads, `sha256sum`, `wc -l`, `git show` (read-only blob), `grep`/`sed` reads and **stdlib `ast.parse` of the candidate text** (static AST, explicitly allowed). The candidate module was **never imported**; no implementer verification script was executed |
| No execution until a separately root-pinned finite plan / ACK | **honoured** — no execution requested or performed |
| First 429 → WAIT_BUDGET / end / no retry / no switch / no root takeover | **not triggered** (no 429) |
| First approval refusal → stop / no bypass / no config edit | **not triggered** (no approval refusal) |
| No self-declared Major closure, no Stage PASS, no native PASS | **honoured** — the receipt states `major_closure_claimed: false`, `stage_pass: false`, `native: NOT_PROVEN`, `dynamic15/16: NOT_RUN` |
| No keep-open | **honoured** — the worker ends its turn after the root ask |
| Minimal and local; no generic framework | **honoured** — one small ledger class, one seam, four helper fixes; the existing module structure is reused |

---

## 8. What is asked of root

1. **ACK (or reject) this design** — the concrete call sites (C1…C22), the
   exception boundaries (§2.6, §3.5, §4.1, §4.2), the state tables (§3.2,
   §3.3) and the assertion mapping (§5).
2. **On ACK only:** the implementation scope is
   `tools/test_v0_s3_native_custody_correction10.py` plus the **new**
   `reports/v0-s3/product-gate0/implementation-native-custody-correction-17/`
   directory (the same shape as correction16: report, source pins, node
   identity, static checks, static receipt, validation-plan **request**).
3. **A separate** frozen runtime plan / ACK is required before any execution;
   this design does not request one and no run has been performed.
4. The dynamic15 / dynamic16 states stay **NOT_RUN** and the native state
   stays **NOT_PROVEN** until a separately ACKed run produces real evidence.

**Not requested here:** any human approval, any budget change, any Stage or
native claim, any change of the 189 denominator, any production change.

---

## 9. Ten-field status and the development outline

| field | value |
|---|---|
| current coordinate | **V1 / R1 / WP-R1-U3 / S3_P4** |
| completed this round | the **static design** of correction17 for the three open Majors (M1, M2, M3) of the correction16 independent review |
| last passed gate | `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW` (candidate `621b1bf…`, unchanged) |
| blocking gate | `S3_P4_N1_CORRECTION17_STATIC_RESIDUALS` — the root design ACK, then the static implementation, then an independent review, then a separately ACKed dynamic run |
| global route | V1 preparation; the frozen `S3_P4` offline integration packet is unchanged |
| remaining work | (1) root design ACK; (2) the static implementation of C1…C22 in the test module only; (3) an independent static review of that candidate; (4) a separately frozen, ACKed finite dynamic run; (5) the human sign-off that the Stage requires |
| next owner | the coordinator / root (design review), then the independent reviewer |
| authorization | **no runtime requested and none used**; this task is static design only under the correction17 contract; no 429 and no approval refusal occurred |
| evidence | `reports/v0-s3/product-gate0/implementation-native-custody-correction-17/design.md` and `design-receipt.json` (this directory) |
| exact stop reason | `DESIGN_REVIEW_REQUIRED_BEFORE_CORRECTION17_SOURCE_EDIT` — the design is delivered and the turn ends **awaiting the root ACK**; dynamic15 = **NOT_RUN**, dynamic16 = **NOT_RUN**, native = **NOT_PROVEN**, `stage_pass = false`; no self-declared Major closure |

**Development outline (from `plans/execution-control.json`, completed/total):**
V0-S0 1/2 · V0-S1 5/5 · R0 1/2 · R1a 5/5 · V0-S2 7/8 · **V0-S3 0/6** ·
**R1 0/4 (current)** · V1-M1 0/3 · R2 0/4 · R3 0/4 · R4 0/4 · R5a 0/4 ·
R5b 0/4 · R5c 0/4. These counts do not promote implementation, machine or
independent results to human acceptance.
