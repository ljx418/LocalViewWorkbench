# Correction 21 — mapping of the five residual counterexamples of the 20 review

Source of the counterexamples: the independent STATIC review of the
correction 20 (`reports/v0-s3/product-gate0/native-custody-correction-20/
test-review-01/review-result/review.md` and `receipt.json`, F0/M2/m0,
M1 `CLOSED_STATIC`, M2 `OPEN`, M3 `OPEN`).

Baseline: report delivery `845b78615f50141fd1c9029501a382b52efa9f44`,
source candidate `206a7fe7f21343d89ca83e03a0e4dc7e670cd381`.
Candidate of this correction: the single file
`tools/test_v0_s3_native_custody_correction10.py` plus this NEW report
directory.

The line numbers of the **baseline** are the ones of the review; the line
numbers of the **candidate** are the ones of this correction.

---

## M2.a — the final recovery could not preserve all cleanup facts

* Baseline: `_salvage_threads` (561–627) returns the per-owner error
  lists and `_drain_owners` keeps every iteration in `all_salvage`
  (1233), but `_prove_salvage` (758–776) returns only the **first**
  failed owner. The timeout final document (6380–6459) and the
  published-fault final document (6974–7050) exported only
  `drain['attempts']`, `drain['proof']` and the quiescence; the
  coordination (7694–7707) exported the attempts and the proof. The
  error list of the drain is taken **before** the last attempts snapshot
  (1210/1211), so an error of the **final resnapshot** (1242–1250) was
  only in `drain['errors']`; the outer recovery (7840–7869) and the
  final summary (7936) read only `r10_raw` and could not restore what
  the callers had dropped.
* Trigger: two distinct registered started owners meet ordinary
  join/liveness failures `E1` and `E2` in the same drain iteration and
  every evidence write succeeds. `proof_failure` names only `E1`; `E2`
  survives only in the local `all_salvage` and never reaches the raw
  store, a written document or the recovery.
* Candidate: the drain keeps the **per owner** errors of **every**
  iteration in a new `owner_errors` list, each of them named with the
  iteration that produced it (1340–1347, returned at 1394). One helper
  `_drain_facts(drain)` (790) returns the **complete** bundle — the
  final salvage, the salvage of every iteration, the per-owner errors,
  the attempts, the **complete** error list of the drain, the
  quiescence and the proof — and **every** durable final document of a
  round unpacks it: the zero round (3926), the parent (4263), the
  controlled round (4974), the timeout phase in its `PASSED` (6747) and
  its `FAIL` (6802) branch, the published-fault phase in its `PASSED`
  (7350) and its `FAIL` (7403) branch, the final verdict of the
  earlier work (7820) and the coordination (8069). The **actual**
  returned state of the public stop of the phase (`phase_stop`, 6671 and
  7275) and the **original failure** join the same documents, so the
  shared LAST ACTUAL store and the recovery carry the stop, the
  original failure and the writer diagnostics next to the complete
  history of the drain. The first proof string is never used as the
  error list.
* Static proof: `static-checks/static-checks-report.json` →
  `M2.a_full_drain_facts`: the helper returns the seven keys and the
  nine call sites unpack it with the **actual** drain of their round.

## M2.b — the incomplete-barrier terminal rewrite omitted the persistence fields

* Baseline: at 5980–6003 the branch of the barrier that never completed
  built `barrier_failed_facts` with the identity booleans,
  `completion=False` and the timeout, but **without**
  `barrier_persisted` and **without** `barrier_write_error`. The
  terminal write then closed the barrier as `FAIL` (6004–6005), so the
  exception handler (6251–6291) **skipped** that name — its state was
  no longer `ATTEMPTED` — and the normally complete barrier rewrite
  (6262–6274) never ran for it.
* Candidate: the terminal document of the not-completed barrier carries
  the **actual** `barrier_persisted`, the **actual** `barrier_write_error`
  and the **observed** snapshot of the barrier — `barrier_observed`,
  `barrier_observed_generation`, `barrier_observed_error`,
  `barrier_return_state` and `barrier_snapshot_present` — even when
  they are absent or incomplete (6313–6343). The identity stays the
  **boolean** of `barrier_identity()`; the object itself never enters a
  document and the repr of an object is never taken for an identity.
  The status stays `FAIL` with `executed=True`, the premise stays
  `BARRIER_NOT_COMPLETED`, the timeout stays `15.0` and the name is
  never relabelled `NOT_RUN`. The same facts are stored in the shared
  store **before** the terminal write (6344), so the terminal state of
  the ledger still follows the **successful** write and the later
  recovery of the group reuses exactly these fields.
* Static proof: `M2.b_incomplete_barrier_persistence`: the branch of the
  real AST carries `barrier_persisted`, `barrier_write_error`,
  `barrier_observed`, `barrier_observed_generation`,
  `barrier_snapshot_present`, `status='FAIL'`, `executed=True` and no
  `NOT_RUN`.

## M3.a — a late controlled release swallowed the exact interruption

* Baseline: the cleanup region of the controlled subcase checked the
  pending interruptions and the proof (4781–4784), the outer handlers
  recorded the deliberate failure and rewrote the evidence (4785–4807)
  and only **after** them the outer `finally` (4808–4815) disarmed the
  observer, stopped the patch and called `_release_gate(controlled_api.
  frames_ready.set, …)`. `_release_gate` records an exact
  `KeyboardInterrupt`/`SystemExit` and returns normally; no later
  interruption check, evidence rewrite or proof check existed and the
  next statement (4816) returned the facts. The assertions
  4831–4935 then inspected the **old** facts and could all pass.
* Trigger: the `CLOSE_FAILURE` subcase meets its exact singleton close
  oracle and its physical cleanup, the earlier releases succeed and the
  **last** `frames_ready.set` raises an exact `K`.
* Candidate: the outer `finally` (5032–5085) restores the observer and
  the patch **unconditionally** — they are never skipped and their
  failures are recorded with their exact type and detail — releases the
  gate of the round **last** and then performs a **guarded final
  update**: the facts receive the complete cleanup history
  (`cleanup_errors`, `interrupts`) and the evidence of the subcase is
  closed with it. Only **then** the priority is applied: the failure
  that is already unwinding wins, then the **first** exact pending
  interruption of the cleanup, then the ordinary proof. A cancellation
  of the last release is therefore re-raised as **itself** when the
  subcase has no deliberate failure of its own (the close-only case
  stays cleanup-only and its exact singleton fault is not a sentinel),
  and it is an **additional diagnostic** next to the deliberate failure
  of the other subcases. No pending interruption is ever added after the
  last check and ignored.
* Static proof: `M3.a_no_late_controlled_release`: in the real AST of
  the `finally`, the release of the gate comes **after** the restore of
  the observer, the final write of the evidence comes **before** the
  priority and the priority comes **after** the release.

## M3.b — the deferred cancellation was rethrown inside the startup-owner loop

* Baseline: the finalization of the startup owners joined the first
  owner and called `_raise_first_interruption(startup_interrupts)`
  (5136) **inside** the `for owner in owners` loop (5130–5138): a
  `K1` raised there skipped every later owner, an unguarded join that
  raised replaced `K1`, and an original assertion that was unwinding
  was replaced by both. The same class was live at 1506–1510, at
  4223–4228 (`stop_accepting`, `join_bounded`) and at 4305–4306, where
  a failing `reader.join` skipped the `endpoint.close` that follows it.
* Candidate: one helper `_join_owner(label, thread, errors, interrupts,
  seconds=…, join=…)` (845) joins **one** owner and reads its liveness
  under a guard; a failure of either is retained with its exact type,
  its exact detail and the **exact** object of a cancellation
  (`_note_interruption`), and the helper itself never raises. Every
  owner of a round is attempted — the startup loop (5405–5436) guards
  the read of the thread of every owner, joins **all** of them and
  keeps them — and the priority is enforced **after** the whole
  traversal: the failure that is already unwinding wins, then the
  **first** exact pending interruption, then the ordinary proof, which
  itself runs **after** the traversal so that a failure of it never
  skips an owner. The same repair is applied to the audited sites of the
  same class (see the inventory of the preparation checklist): the
  recovery (1622), the creation (1732), the launch (2103), the
  dispatch (4409), the await (4512), the retry (5279), the startup
  owners (5405), the tightener (5500), the interrupted start (5586) and
  the owner of the round (8594). The bounded total of the drain and the
  deadlines of the product are untouched.
* Static proof: `M3.b_every_owner_attempted`: the real AST of the four
  loops over the owners of a round contains **no** raise and **no**
  `_raise_first_interruption` in its body, every owner action of a loop
  is guarded, and no direct join, query or stop of an owner in a
  cleanup region is unguarded.

## M3.c — the post-drain registry query could replace the original or the pending K1

* Baseline: `registry.facts()` (363–368) calls the very `entries()`
  query that the independent fallback of the drain tolerates. The facts
  of the zero round (3575 and 3762) and of the controlled round (4748)
  were built **before** the guarded writer, so a failure of the query
  aborted the round outside of the guard: it skipped the evidence and
  the priority and it replaced the failure that was unwinding or the
  pending `K1`.
* Candidate: one helper `_registry_snapshot(registry, errors,
  interrupts, label)` (817) guards the query. The failure is retained
  with its exact type and its exact detail, the **exact** object of a
  cancellation is retained and it never replaces the failure that is
  already unwinding and never replaces the **first** exact pending
  interruption. The snapshot of a failed query is **unknown** (`None`)
  and it is never a fabricated empty registry that looks successful:
  it is an explicit diagnostic that **fails the proof** of the round
  (the zero round at 3910, the parent at 4238, the controlled round at
  4951). The independent observed references of the drain remain the
  actual fallback of the owners and are unchanged. Every fact building
  **after** the drain and **before** the verdict was inspected: the
  parent (4235) builds its snapshot **before** the writer, so the
  evidence of the cleanup is never lost because of the query.
* Static proof: `M3.c_guarded_registry_queries`: the only call of
  `facts()` of a registry in the whole module is the one of the guarded
  helper, and the helper never raises.

---

## The denominator and the assertions

| Item | Baseline | Candidate |
|---|---|---|
| identifiers of the 189 nodes, in the order | 117 + 16 + 24 + 18 + 14 | **equal** (static AST reconstruction) |
| assertion predicates of the five modules | 414 | **414** — 0 removed, 0 added |
| skip / skipif / xfail calls | 0 | 0 |
| the six other sources | byte identical | byte identical (SHA256 in `pins.json`) |
| the 28-name inventory of the group | 28 | 28 |
| production B / C | unchanged | unchanged |

The repaired control flow never touches an oracle: the proof of a round
keeps the **exact** predicates of the baseline (`not worker.is_alive()`,
`not thread.is_alive()`, `not tightener.is_alive()`, …) and they are only
evaluated **after** the whole traversal of the owners, so a failure of a
proof never skips an owner and never replaces the failure that is
already unwinding.
