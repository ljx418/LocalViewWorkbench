# Correction 21 — static shape checks (summary)

**These are STATIC checks. They are not an execution.** The instrument
`check_correction21.py` reads the candidate source and the frozen baseline
source as **data** (`ast`, `hashlib`, read-only `git show`). It never imports
the candidate, never collects it, never runs a test, never opens a socket, a
database, a model or a native library and never starts a product process.

Reproduce (read only, no product side effect):

```sh
cd <PACK_ROOT> && python3 \
  reports/v0-s3/product-gate0/implementation-native-custody-correction-21/static-checks/check_correction21.py \
  --root . --baseline 206a7fe7f21343d89ca83e03a0e4dc7e670cd381 \
  --json reports/v0-s3/product-gate0/implementation-native-custody-correction-21/static-checks/static-checks-report.json
```

Exit code `0` means every check below passed. The machine readable result is
`static-checks-report.json`.

## Result

| Check | Result | What it proves |
|---|---|---|
| `denominator` | **ok** | The candidate reconstructs exactly **189** unique identifiers in the same order as the baseline: 117 + 16 + 24 + 18 + 14. The identifiers, their order and their per-module counts are equal to the baseline of the correction 20. |
| `assertions` | **ok** | The multiset of the assertion predicates of the candidate is **equal** to the baseline of every one of the five modules: 361 / 222 / 317 / 357 / 414 predicates, **0 removed**. No assertion of the baseline was dropped, none was added and no skip/xfail was introduced. |
| `unchanged_sources` | **ok** | The six sources of the correction are byte identical to the frozen pins: broker `06cfc951…`, custody `7f26e927…`, base test `fe96d2ff…`, regressions `03250ea0…`, correction05 `8563989f…`, correction07 `dc74cf7f…`. |
| `evidence_root` | **ok** | The evidence root of the module is the **NEW** directory of the correction 21; the directory of the correction 20 is no longer referenced by the module. |
| `M2.a_full_drain_facts` | **ok** | The helper `_drain_facts` returns the **complete** bundle (`drain_salvage`, `drain_all_salvage`, `drain_owner_errors`, `drain_attempts`, `drain_errors`, `drain_quiescent`, `drain_proof`) and **nine** call sites unpack it with the **actual** drain of their round (the zero round, the parent, the controlled round, the two branches of the timeout phase, the two branches of the published phase, the final verdict of the earlier work and the coordination). The drain keeps the per owner errors of every iteration and the outer recovery still rebuilds its document from the shared store. The check is a **dataflow** check on the real AST. |
| `M2.b_incomplete_barrier_persistence` | **ok** | The terminal document of the barrier that never completed carries the **actual** `barrier_persisted`, the **actual** `barrier_write_error`, `barrier_snapshot_present`, `barrier_observed`, `barrier_observed_generation`, `barrier_observed_error` and `barrier_return_state`; its status is `FAIL`, it stays `executed=True` and it is never relabelled `NOT_RUN`. The check reads the **real AST** of the branch. |
| `M3.a_no_late_controlled_release` | **ok** | In the real AST of the `finally` of the controlled subcase the restore of the observer and of the patch comes **first**, the last release of the gate of the round comes **after** them, the final write of the evidence comes **before** the priority and the priority (`raise controlled_interrupts[0]`) comes **after** the release: no pending interruption is added after the last check and ignored. |
| `M3.b_every_owner_attempted` | **ok** | The **four** loops of the module that traverse the owners of a round contain **no** `raise` and **no** `_raise_first_interruption` in their body and every owner action of their body is guarded; the helper `_join_owner` guards the join and the liveness query, records the failure with its exact type and detail and the **exact** object of a cancellation, and it never raises itself. **No** direct join, query or stop of an owner in a cleanup region is unguarded (the query of the ordinary proof is classified apart: it runs after every cleanup action). |
| `M3.c_guarded_registry_queries` | **ok** | The only call of `facts()` of a registry in the whole module is the one of the guarded helper `_registry_snapshot`; the helper retains the actual error and the exact object of a cancellation, returns **unknown** (`None`) for a failed query and never raises. |

## Honest limits

Static equality, AST counts and shape checks **cannot** replace execution.
They prove that the five repairs have the required shape and that the
denominator did not regress; they prove **nothing** about the runtime
behaviour of the candidate, about the native API, about the product
acceptance or about the Stage gate.

* Dynamic correction 21: `NOT_RUN` (no runtime ACK exists).
* Dynamic corrections 15–20: `NOT_RUN` in this route.
* The historical 189 PASS of the correction 14 stays **historical**.
* Native evidence: `NOT_PROVEN`. Product and Stage: **no PASS**.
