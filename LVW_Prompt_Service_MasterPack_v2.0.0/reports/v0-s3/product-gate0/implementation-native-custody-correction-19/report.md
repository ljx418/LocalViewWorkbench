# Correction19 — the static implementation of the M2 and M3 residuals of the correction 18

**V1 / R1 / WP-R1-U3 / S3_P4.** Baseline `208f0c604345fd417f98f3a86e5a65835179d175`
(the delivery of the static evidence of the correction 18); the source candidate of
the review is `0f532a7d86e390dc093b7d78aa5fc36103bdff23`. The design is the
**approved** one: `implementation-native-custody-correction-17/design.md` with its
authoritative **section 10** and the six binding clarifications of the root design
ACK (`native-custody-correction-17/design-review-02/ack.md`). The independent review
of the correction 18 candidate
(`native-custody-correction-18/test-review-01/review-result/`) closed **M1**
(`CLOSED_STATIC`) and left **M2 (points 1–4)** and **M3 (points 1–6)** OPEN. This
candidate closes every one of those ten concrete residuals together with the three
root checks of the decision of the root. It adds **no new generic framework** and
**no new product obligation**.

**One file of the product changed:**
`tools/test_v0_s3_native_custody_correction10.py`. No production source, no other
test module, no contract, no threshold, no root packet / control / MANIFEST, no
historical report and no prior evidence directory was touched. The **189** node
identities and their order are unchanged, the six other sources are byte identical
to the baseline, and the evidence of this correction is written in the **new**
directory of the correction 19.

**Nothing was executed.** The candidate was never imported, never collected, never
run with pytest, and no ctypes, runtime, native, operating system business process,
model, GPU, service, network, medium, database, ledger or counter action was
performed. The checks of this delivery are a text / AST / symtable /
in-memory-compile / sha256 reading of the sources plus a read-only `git show` of the
baseline blobs.

---

## 1. The files of this delivery

| file | what it is |
|---|---|
| `implementation-boundary-checklist.md` | the ≤ 80 line boundary checklist: every review counterexample → the exact try boundary / state transition → the negative oracle |
| `static_checks.py` / `static-checks.json` | the static checks; they read the **actual AST try nesting**, the real attribute and signature shapes and the real finalisation ordering |
| `node_identity.py` / `node-identity.json` | the identity of the **189** nodes in the frozen order and the comparison with the frozen order of the correction 18 |
| `source_pins.py` / `source-pins.json` | the sha256 of the seven sources before and after the candidate |
| `validation_plan_request.py` / `validation-plan-request.json` | the **finite three command** validation plan, **REQUEST only** |
| `static_implementation_receipt.py` / `static-implementation-receipt.json` | the receipt: the actual Git identity of the candidate, the `source_sha256` of the changed module and the mapping of every counterexample |
| `report.md` | this document |

The candidate Git commit is the commit of the changed module and of the static
tooling; it is recorded in `static-implementation-receipt.json` as
`candidate_git_commit` (and it is the **parent** of the commit that carries this
delivery). The content hash of the module is named `source_sha256` in the receipt
and is **never** called `candidate_sha`: the Git commit is the identity of the
candidate and the sha256 is the identity of the source.

---

## 2. The mapping of every counterexample of the independent review 18

### The three root checks of the decision of the root

| # | the counterexample | the intended boundary / state transition of the candidate | the negative oracle that fails closed | where |
|---|---|---|---|---|
| R1 | the first channel of the registry is the channel of the **parent** and it is never the child | `controlled_custody_channel()` selects the entry named `controlled:channel` — the **newly retained** owner of the custody of the child — and its fallback selects the channel whose owner `is not controlled_parent_channel`; the parent is the entry named `launch:channel` and it is captured **before** the child is constructed | the identity of the child is proved different from the parent (`child is not controlled_parent_channel`) and the injected start records `target_owner_is_parent is False` | `controlled_failure` |
| R2 | a failed terminal write advances the ledger | `record_guarded` returns an explicit result and **every** `ledger.pass_` / `ledger.fail` / `ledger.finish` follows a **successful** terminal write; a failed write leaves the name `ATTEMPTED` and the outer inventory recovers it, bounded, once | a terminal `FAIL` without a durable document is never asserted as a terminal state of the ledger; the outer inventory finalises a name as `NOT_RUN` only after its durable write succeeded | `_m09_timeout_phase`, `_m09_published_fault_phase`, `test_n10_r10_…` |
| R3 | the coordination try begins after the start | the cleanup owning `Try` of the coordination **contains** the construction of the endpoint and `reader.start()` in its **body** and owns the close, the join and the drain in its `finally` | a start that took effect and that raised still obtains the release of the gates, the close of the endpoint, the join of the observed threads and the proof of the round | `test_n10_r10_…` |

### M2 — the terminal evidence against the persistence and the cleanup

| # | the counterexample of the independent review | the intended boundary / state transition of the candidate | the negative oracle that fails closed | where |
|---|---|---|---|---|
| M2‑1 | `record_guarded` returns `None` after a failed terminal write and the handler calls `ledger.fail` unconditionally; the outer handler retries only `ATTEMPTED` and then only `PLANNED` | the terminal state of the ledger follows the **successful** terminal write at every site; a failed write leaves the name `ATTEMPTED`; the outer inventory attempts one bounded best effort recovery per name and never retries a name that is already terminal | a failed terminal write never produces a durable `FAIL` that was never written; a name that was never entered is `NOT_RUN` only after its durable write succeeded; a passing group carries **no** persistence diagnostic | `_m09_timeout_phase`, `_m09_published_fault_phase`, `test_n10_r10_…` |
| M2‑2 | the initial `_persist_barrier` catches the failure into `barrier_write_error` and the phase consumes it only **after** the fault / outcome / channel-thread assertions; an assertion that fails in between loses the diagnostic | the final document of the phase and the rewrite of the barrier document both carry `barrier_persisted`, `barrier_write_error` and the identity boolean / type / detail of the original object; the seam also retains the **exact** object of a cancellation of its write | a durable seam failure is never lost to a later assertion and never replaced by a `repr`-only rewrite; a barrier whose document was not written is a `FAIL` with the premise `BARRIER_DOCUMENT_NOT_WRITTEN` | `_M09TimeoutApi._persist_barrier`, `_m09_timeout_phase` |
| M2‑3 | the coordination writes its terminal `PASSED` **before** its cleanup and the earlier real chain keeps its `early_cleanup_errors` and its drain facts in no durable document | the terminal document of `r10-coordination` and the new terminal document `r10-early-salvage` are written in the `finally` that owns the drain, **after** the cleanup, and they carry the original failure, the cleanup errors, the quiescence and the exact interruptions | there is **no** pre-cleanup terminal `PASSED`; the passed subchecks keep their own documents; a cleanup error that happens while another assertion unwinds is durably recorded next to the original failure | `test_n10_r10_…` |
| M2‑4 | both phase finalizers require `quiescent=True` for a clean `PASSED` but their final raises never reject `quiescent=False`; a durable `FAIL` is written and no exception is raised, so the outer test has no terminal-state assertion to reject it | the drain returns a **proof failure** when it is not quiescent; every caller requires proof `None` **and** quiescence `True` **and** no unexpected cleanup error; a durable `FAIL` of a phase always raises with its own document | a nonquiescent drain fails the actual test, the phase and the caller — not only the JSON; a durable phase `FAIL` never returns a successful test | `_drain_owners`, `_m09_timeout_phase`, `_m09_published_fault_phase`, the parent / zero / controlled / early / coordination regions |

### M3 — the all-owner cleanup and the exact cancellation propagation

| # | the counterexample of the independent review | the intended boundary / state transition of the candidate | the negative oracle that fails closed | where |
|---|---|---|---|---|
| M3‑1 | `controlled_custody_channel()` returns the **first** channel entry — the already registered parent `launch:channel` — so `owner is not controlled_custody_channel()` compares the child against the parent, the injection never happens and the required constructor failure is never raised | the lookup selects the **exact newly retained** child (`controlled:channel`, or the channel whose owner is not the parent) and proves that it differs from the parent; the seam compares the `__self__` of `_target` with that exact child, calls the **original** `Thread.start` and raises the exact `_R07ConstructorFailure` **inside** the constructor | the injection takes effect on exactly one drain — the drain of the child — and never on the channel of the parent; the exact child is proved different from the parent | `controlled_failure` |
| M3‑2 | `_registry_owners` has one whole-enumeration catch: one failing container query aborts the traversal and replaces the owners with an empty list; the readings of the generation and of the pending starts are unguarded; the release of the gates is one call | every query — the entries, the per container, the session, the channel and the provenance — is guarded **on its own**; the exact thread objects that the start registry observed are retained as an **independent fallback** and the owners are never emptied; the generation, the pending starts and the final resnapshot are guarded reads; the release is **one action per gate** | one failing query never skips the other owners and never loses an observed thread; a failed gate never skips the gate that follows it; every catch retains the error and the **exact** interruption object; the generation-stable final snapshot, the joined producer evidence and the one 30 s total drain (≤ 10 s per owner) are preserved | `_registry_owners`, `_drain_owners` |
| M3‑3 | the main parent and zero finalizers create the interruption lists and never rethrow them; the controlled cleanup raises the proof `AssertionError` **before** its intended `raise controlled_interrupts[0]`, which renders the exact rethrow unreachable; the evidence writers convert a cancellation into an `AssertionError` | every caller keeps the **exact** object of the cancellation in its own list, does all the possible cleanup first and rethrows it **before** the ordinary proof or evidence assertion; the priority is the unwinding failure, then the exact interruption, then the ordinary assertion | a cancellation of a join, of a stop, of a snapshot or of a write is rethrown **as itself**; an exact interruption is never reduced to a type and a detail; the additional diagnostics are never discarded next to an original error | every cleanup region of the module |
| M3‑4 | the construction of the endpoint and the start of the reader of the independent coordination precede the inner `try` whose `finally` owns the cleanup | the cleanup owning `Try` starts **before** the construction of the endpoint and **before** `reader.start()`; the holders are `None` before it; the `finally` releases the gates, closes the endpoint, joins the observed threads and drains the owners, and it disarms the observer **last** | a start that took effect and that then raised, and a partially failing endpoint constructor, still obtain the release, the close, the join and the proof | `test_n10_r10_…` |
| M3‑5 | the main child cleanup catches `Exception` only: a `KeyboardInterrupt` of the first `endpoint.close()` skips the second close | every close of the transport and of **each** child endpoint catches `BaseException` and records the exact cancellation in the list of the parent; the parent final salvage keeps the exact objects | the first cancellation never skips the second close; the product retention is never erased by the salvage | `test_n10_r07_…` |
| M3‑6 | the main parent and zero finalizers reject only the proof and never `drain.quiescent=False`; the final exact-owner resnapshot at the bound can reveal an unjoined owner while the earlier salvage has `proof=None` | the quiescence is part of the proof of **every** caller — the parent, the zero, the controlled, the M09 phases, the earlier chain and the coordination — and the drain itself fails its proof when it is not quiescent | a late owner that the final resnapshot found is never certified as exited and never left behind; a durable `FAIL` never returns a successful test | every caller of `_drain_owners` |

---

## 3. The removed assertions and their equivalent or stronger predicates

**No assertion was removed.** The candidate has **414** `assert` statements against
the **407** of the baseline `208f0c6`: the **seven** new ones are

| the added predicate | the residual that it closes |
|---|---|
| `child is not controlled_parent_channel` | M3‑1 — the exact child differs from the parent |
| `controlled['injected_starts'][0]['target_owner_is_parent'] is False` | M3‑1 — the injection took effect on the child and not on the parent |
| `len(children) == 1` | M3‑1 — the custody retained exactly one child channel |
| `first_failure['type'] is None` | M2‑1 / M2‑4 — the group really passed |
| `not first_failure.get('write_errors')` | M2‑1 — a passing test carries no persistence diagnostic |
| `ledger.state(r10_name) in ('PASSED', 'FAIL', 'NOT_RUN')` | M2‑1 — the terminal accounting is complete |
| `r10_name in r10_inventory` | M2‑1 — every name of the inventory was really written |

The seven predicate units that the independent reviews of the correction 16 and of
the correction 17 found removed stay removed and their replacements stay present;
`static_checks.py` verifies both the absence of the removed forms and the presence
of their replacements.

The **behaviour** that was corrected is the terminal accounting of the group, the
quiescence of the cleanup and the priority of the cancellation — not the oracles of
the M1 closure. The predicates of the M1 closure (the public zero admission, the
returned state and the retention of the original broker) are **untouched**.

---

## 4. The denominator, the pins and the checks

* the **189** nodes keep their names, their signatures, their decorators and their
  frozen order: `117 + 16 + 24 + 18 + 14`. The order is compared with the frozen
  order of the correction 18 and it is **identical** (`order_unchanged: true`). No
  node was added, removed, renamed, skipped or xfailed.
* the changed file: `tools/test_v0_s3_native_custody_correction10.py`. The two
  production sources and the four other test modules are **byte identical** to the
  baseline `208f0c6`. The import list of the module is **unchanged**: no new
  framework, no new dependency and no new module level definition.
* the static checks: **160** checks, **0** failed. They inspect the actual AST try
  nesting (the construction of the endpoint and the start of the reader are in the
  body of the `Try` whose `finally` owns the drain; the terminal verdict of the
  earlier work is in the `finally` that owns its drain), the real attribute shapes
  (the `_target` of the stdlib thread and the exact custody-retained child), the
  real ordering of the terminal transitions (every `ledger.pass_` / `ledger.fail` /
  `ledger.finish` follows a successful write) and the real priority of the
  cancellation (the exact rethrow precedes the ordinary assertion in every caller).

---

## 5. What is **not** claimed

The dynamic verification of the correction 19 is **NOT_RUN**: the frozen three
command plan is a **REQUEST** and nothing of it was executed. The corrections 15,
16, 17, 18 and 19 stay dynamic **NOT_RUN** and the native behaviour stays
**NOT_PROVEN**. The historical green of the correction 14 stays historical. This
delivery claims **no** Major closure, **no** Stage PASS, **no** product acceptance
and **no** human signoff; the isolated review of the candidate decides whether the
ten residuals and the three root checks are really closed.

The outline of the development is unchanged: V0‑S0 1/2; V0‑S1 5/5; R0 1/2; R1a 5/5;
V0‑S2 7/8; V0‑S3 0/6; **R1 0/4**; V1‑M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4;
R5b 0/4; R5c 0/4. The counts do not combine implementation, machine results,
independent review and human acceptance.
