# Correction18 — the static implementation of the M2 and M3 residuals of the correction 17

**V1 / R1 / WP-R1-U3 / S3_P4.** Baseline `058ee9ff0020a1485ee57ddafe23a1d390159c4a`
(the correction 17 static candidate). The design is the **approved** one:
`implementation-native-custody-correction-17/design.md` with its
authoritative **section 10** and the six binding clarifications of the root
design ACK (`native-custody-correction-17/design-review-02/ack.md`). The
independent review of the correction 17 candidate
(`native-custody-correction-17/test-review-01/review-result/`) closed **M1**
and left **M2 (points 1–5)** and **M3 (points 1–7)** OPEN. This candidate
closes every one of those twelve concrete residuals. It adds **no new
generic framework** and **no new product obligation**.

**One file of the product changed:**
`tools/test_v0_s3_native_custody_correction10.py`. No production source, no
other test module, no contract, no threshold, no root packet / control /
MANIFEST, no historical report and no prior evidence directory was touched.
The **189** node identities and their order are unchanged, the six other
sources are byte identical to the baseline, and the evidence of this
correction is written in the **new** directory of the correction 18.

**Nothing was executed.** The candidate was never imported, never collected,
never run with pytest, and no ctypes, runtime, native, operating system
business process, model, GPU, service, network, medium, database, ledger or
counter action was performed. The checks of this delivery are a text /
AST / symtable / in-memory-compile / sha256 reading of the sources plus a
read-only `git show` of the baseline blobs.

---

## 1. The files of this delivery

| file | what it is |
|---|---|
| `implementation-boundary-checklist.md` | the ≤ 80 line boundary checklist: every review counterexample → the exact try boundary / state transition → the negative oracle |
| `static_checks.py` / `static-checks.json` | the static checks; they read the **actual AST try nesting**, the real attribute and signature shapes and the real finalisation ordering |
| `node_identity.py` / `node-identity.json` | the identity of the **189** nodes in the frozen order |
| `source_pins.py` / `source-pins.json` | the sha256 of the seven sources before and after the candidate |
| `validation_plan_request.py` / `validation-plan-request.json` | the **finite three command** validation plan, **REQUEST only** |
| `static_implementation_receipt.py` / `static-implementation-receipt.json` | the receipt: the actual Git identity of the candidate and the `source_sha256` of the changed module |
| `report.md` | this document |

The candidate Git commit is the commit of the changed module and of the
static tooling; it is recorded in `static-implementation-receipt.json` as
`candidate_git_commit` (and it is the **parent** of the commit that carries
this delivery). The content hash of the module is named
`source_sha256` in the receipt and is **never** called `candidate_sha`: the
Git commit is the identity of the candidate and the sha256 is the identity
of the source.

---

## 2. The mapping of every review counterexample

### M2 — the attempted inventory, the durable identity facts and the final accounting

| # | the counterexample of the independent review | the intended boundary / state transition of the candidate | the negative oracle that fails closed | where |
|---|---|---|---|---|
| M2‑1 | a successful construction has no terminal document; a later unrelated failure rewrites an earlier successful construction as `FAIL`; the phase of a failed construction stays `PLANNED` → `NOT_RUN` | `ledger.attempt(phase)` **and** `ledger.attempt(phase + '-construction')` happen **before** `_chain(...)`; a successful construction writes `EXECUTED` and then the terminal `PASSED` document, and only then `ledger.pass_(...)`; the phase result is written **after** the cleanup | a construction that failed half way is an attempted construction with its own `FAIL` document (`construction: FAILED`) **and** an attempted phase whose result is `FAIL` after the cleanup — never `NOT_RUN` | `_m09_timeout_phase`, `_m09_published_fault_phase` |
| M2‑2 | the attempt of the earlier coordination is marked **after** the endpoint creation, the start, the read and the assertions; the earlier `_chain` sits before its local cleanup `try` | `ledger.attempt('r10-coordination')` moves **before** the endpoint is created, before the reader is started and before the first assertion; the earlier `_chain` moves **inside** the `try` whose `finally` owns the teardown and the drain, with the holders initialised to `None` | an executed coordination is never inventoried as `NOT_RUN`; a construction that failed half way still obtains the teardown and the proof of the round | `test_n10_r10_…` |
| M2‑3 | the barrier attempt is marked in the phase and not in the seam; the completion is published before the document is written; the write diagnostic is stored and never consumed; the final rewrite drops the identity boolean | the seam marks the barrier attempt **in the seam** (`self.barrier_ledger.attempt(self.barrier_name)`), writes the **durable document first** and publishes the completion **after** it; the phase **consumes** `api.barrier_write_error`; every rewrite of the barrier document carries `barrier_observed_object_is_original` (a **boolean**), the type and the detail | a barrier whose document was not written is a `FAIL` with the premise `BARRIER_DOCUMENT_NOT_WRITTEN`; the durable identity boolean must be `True` — the `repr` of an object never carries its identity | `_M09TimeoutApi.cancel_synchronous_io`, `_M09TimeoutApi._persist_barrier`, `_m09_timeout_phase` |
| M2‑4 | the phase failure is finalised **before** the cleanup; the later cleanup errors disappear; the success decision omits the quiescence; the ledger is updated before the document is persisted | the **result** of the phase is written **in the `finally`**, after the teardown, and it carries the original failure **and** every cleanup diagnostic; `PASSED` requires the proof **and** the quiescence **and** zero unexpected cleanup or evidence errors; every durable document is written **before** the terminal state of the ledger is updated | a failed stop keeps the earlier checks `PASSED` with their facts and makes the result `FAIL`; the result of a phase is never `PASSED` before the stops and the cleanup; an evidence write that fails never replaces the original failure and the phase fails closed | `_m09_timeout_phase`, `_m09_published_fault_phase` |
| M2‑5 | `worker.join_bounded` and `worker.is_alive()` are outside the guard of the drain; `cleanup_error` is a single overwritten dictionary | the join and the query of the worker run in their **own** guards **before** the drain and their errors are **appended** to `cleanup_errors`; the drain itself is guarded | one exception never skips the other owners, the drain nor the result document of the phase; every cleanup error is retained with its exact type and its exact detail | `_m09_timeout_phase`, `_m09_published_fault_phase` |

### M3 — the controlled paths, the owner snapshot and the lost errors

| # | the counterexample of the independent review | the intended boundary / state transition of the candidate | the negative oracle that fails closed | where |
|---|---|---|---|---|
| M3‑1 | `start_round` and the `RUNNING` assertion are **before** the `try` whose `finally` owns the cleanup | the cleanup region is the `Try` whose `finalbody` owns the drain; the start of the round and the assertion of its state are in its **body**; the three deliberate failures are caught by a `Try` that is an **ancestor** of the cleanup region | a start failure, a partially started parent or a wrong return state is cleaned, joined and proved; the deliberate failure is caught **outside** the cleanup region | `controlled_failure` (checked on the AST nesting by `static_checks.py`) |
| M3‑2 | the constructor seam reads `getattr(thread, 'target', None)` — an ordinary `threading.Thread` has **no** `target` attribute | the seam reads `getattr(thread, '_target', None)` and takes the owner from `__self__`; it requires the owner to be the **exact** channel that the custody of the fixture registered (`owner is controlled_custody_channel()`) and the context of the child | the seam takes effect on **exactly one** drain, the drain of the child; a similarly named parent thread is never injected into; the test fails closed when the injection did not happen | `controlled_failure` |
| M3‑3 | `CLOSE_FAILURE` raises the generic sentinel although the close case asserts `failure is None` and `cleanup_ran_while_unwinding is False` | the sentinel is raised only for the checkpoints that are neither `CONSTRUCTOR_FAILURE` nor `CLOSE_FAILURE`; the close failure is produced **by the cleanup** and is recorded with its exact owner, type and message | the close case has no failure, did not unwind, and carries **exactly one** close failure with the exact owner / type / message | `controlled_failure` |
| M3‑4 | the non-close subcases never require `controlled['close_failures'] == []` | every non-close controlled subcase asserts its **own** list of the close failures to be empty — the list of the main round is a different list and supplies no coverage | an unrelated `RuntimeError` of a child endpoint fails the subcase instead of being tolerated next to the intended failure | `test_n10_r07_…` |
| M3‑5 | the enumeration of the owners and the reading of the generation are not atomic: a producer can start a child between the entries copy and the reading of the generation, and the owner is then never joined | the generation is read **before** the exact owners are enumerated, **again** right after the enumeration, **again** after the joined producers and **again** after the **final** exact-owner resnapshot; all four readings must agree and the final resnapshot must contain every owner of the enumeration | a late owner is never certified as quiescent and it is never left behind; one overall bound of 30 s per round and ≤ 10 s per owner, never reset, never renewing a product deadline | `_drain_owners` |
| M3‑6 | every iteration replaces the salvage, a first join failure is erased by a successful retry, the classification error is suppressed into a bare `UNKNOWN`, the `KeyboardInterrupt` / `SystemExit` identity is lost and never re-raised, the errors of the stop and of the snapshot are ignored | **every** iteration is kept (`all_salvage`); the classification of an owner is **not** swallowed by `_owner_start_state` any more, so the guard of the caller records the exact diagnostic; the **exact** interruption objects are retained and re-raised when no other failure is unwinding; the errors of the stop and of the snapshot fail the proof through `_stop_proof_failure` | an earlier error stays a proof failure even if a retry ended the threads; an unknown identity is never converted into a proved exit; the region never reports a successful cleanup when an interruption occurred | `_owner_start_state`, `_salvage_threads`, `_capture_stop`, `_stop_proof_failure` |
| M3‑7 | the enumeration, the release callbacks, the joins before the drain and the independent coordination are not comprehensively guarded; the endpoint iteration catches `Exception` only, so a cancellation of the first close skips the second | every cleanup call site is guarded and every error is a **list**: the enumeration, the release of the gates, the join and the liveness query of the owner, the close of the transport and of **each** endpoint (now `BaseException`), the join of the worker of the M09 schedules, the close of the endpoint and the join of the reader of the independent coordination | one exception never skips the remaining owners, the other endpoint, the drain nor the result document; the independent coordination has its **own** observer and its own registry and its reader is joined with a bounded wait | every cleanup region of the module |

---

## 3. The removed assertions and their equivalent or stronger predicates

**No assertion was removed.** The candidate has **407** `assert`
statements against the **405** of the baseline `058ee9f`: the two new ones
are the exact durable identity boolean of the barrier and the exact empty
list of the close failures of a non-close controlled subcase. The seven
predicate units that the independent reviews of the correction 16 and of
the correction 17 found removed stay removed and their replacements stay
present; `static_checks.py` verifies both the absence of the removed forms
and the presence of their replacements.

The one **behaviour** of the baseline that was corrected is the
classification of an owner: `_owner_start_state` used to swallow a failure
of the query of the identity of the owner and to return a bare `UNKNOWN`.
It now lets the failure reach the guard of the caller, which records it
with its exact type and its exact detail and fails the proof of the
cleanup. This is **strictly stronger**: the diagnostic of the
classification is kept and an unknown identity is never taken for a
proved exit.

The predicates of the M1 closure (the public zero admission, the returned
state and the retention of the original broker) are **untouched**: the
M1 region of the module was not edited by this correction.

---

## 4. The denominator, the pins and the checks

* the **189** nodes keep their names, their signatures, their decorators
  and their frozen order: `117 + 16 + 24 + 18 + 14`. No node was added,
  removed, renamed, skipped or xfailed.
* the changed file: `tools/test_v0_s3_native_custody_correction10.py`.
  The two production sources and the four other test modules are **byte
  identical** to the baseline `058ee9f`.
* the static checks: **166** checks, **0** failed. They inspect the actual
  AST try nesting (the start and the `RUNNING` assertion are in the body
  of the `Try` whose `finally` owns the drain; the three deliberate
  failures are caught outside of it), the real attribute shapes (the
  `_target` of the stdlib thread and the exact custody-owned channel), the
  real ordering of the generation readings and of the finalisation (the
  document before the terminal state of the ledger) and the real
  signatures of the helpers.

---

## 5. What is **not** claimed

The dynamic verification of the correction 18 is **NOT_RUN**: the frozen
three command plan is a **REQUEST** and nothing of it was executed. The
corrections 15, 16, 17 and 18 stay dynamic **NOT_RUN** and the native
behaviour stays **NOT_PROVEN**. The historical green of the correction 14
stays historical. This delivery claims **no** Major closure, **no** Stage
PASS, **no** product acceptance and **no** human signoff; the isolated
review of the candidate decides whether the twelve residuals are really
closed.

The outline of the development is unchanged: V0‑S0 1/2; V0‑S1 5/5; R0 1/2;
R1a 5/5; V0‑S2 7/8; V0‑S3 0/6; **R1 0/4**; V1‑M1 0/3; R2 0/4; R3 0/4;
R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. The counts do not combine
implementation, machine results, independent review and human acceptance.
