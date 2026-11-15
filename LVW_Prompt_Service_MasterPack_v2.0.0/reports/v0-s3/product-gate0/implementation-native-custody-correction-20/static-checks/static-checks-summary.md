# Correction 20 — static shape checks (summary)

**These are STATIC checks. They are not an execution.** The instrument
`check_correction20.py` reads the candidate source and the frozen baseline
source as **data** (`ast`, `hashlib`, read-only `git show`). It never imports
the candidate, never collects it, never runs a test, never opens a socket, a
database, a model or a native library and never starts a product process.

Reproduce (read only, no product side effect):

```sh
cd <PACK_ROOT> && python3 \
  reports/v0-s3/product-gate0/implementation-native-custody-correction-20/static-checks/check_correction20.py \
  --root . --baseline 7bf0c53822b396be3ea2091bdd6d3e18df0bf7b4 \
  --json reports/v0-s3/product-gate0/implementation-native-custody-correction-20/static-checks/static-checks-report.json
```

Exit code `0` means every check below passed. The machine readable result is
`static-checks-report.json`.

## Result

| Check | Result | What it proves |
|---|---|---|
| `denominator` | **ok** | The candidate reconstructs exactly **189** unique identifiers in the same order as the baseline: 117 + 16 + 24 + 18 + 14. The identifiers, their order and their per-module counts are equal to the baseline of the correction 19. |
| `assertions` | **ok** | The multiset of the assertion predicates of the candidate is **equal** to the baseline of every one of the five modules: 361 / 222 / 317 / 357 / 414 predicates, **0 removed**. No assertion of the baseline was dropped and no skip/xfail was introduced. |
| `unchanged_sources` | **ok** | The six sources of the correction are byte identical to the frozen pins: broker `06cfc951…`, custody `7f26e927…`, base test `fe96d2ff…`, regressions `03250ea0…`, correction05 `8563989f…`, correction07 `dc74cf7f…`. |
| `M2.1_original_plan_binding` | **ok** | `document` is bound **once** (the launch plan) and it reaches the chain and the five schedules unchanged; the coordination evidence has its own binding `coord_document` and its own entry of the shared store. The check is a **scope/dataflow** check, not a key/name presence check. |
| `M2.2_shared_recovery_facts` | **ok** | Both phase helpers take `store` and bind `raw` to it; the five schedule calls pass `store=r10_raw`; the recovery document is `dict(r10_raw.get(r10_name, {}))` — the **full** facts, not a generic `FAIL` over an empty document. |
| `M2.3_early_final_verdict` | **ok** | The verdict of the earlier work tests `early_original['type'] is not None`, and both evidence writes (`early_write_failure`, `coord_write_failure`) close the evidence after the cleanup. |
| `M2.4_durable_final_inventory` | **ok** | The durable summary `r10-final-summary` carries `states`, `written`, `not_persisted`, `incomplete`, `facts`, `original_failure`, `write_errors` and it is written **after** the `NOT_RUN` write of the inventory. |
| `M3.1_interruption_priority` | **ok** | In the three evidence writers the pending list is consulted **before** the current cancellation (`pending_at < bare_raise_at` for `zero_interrupts`, `parent_interrupts` and `controlled_interrupts`) and the phase raises the **exact** object `api.barrier_interruption` instead of a synthesised assertion. |
| `M3.2_every_initial_gate_guarded` | **ok** | **No** bare `.set()` remains in any `finally` of the module (`bare_releases_in_finally = []`) and **22** releases go through `_release_gate`. |
| `M3.3_independent_observed_fallback` | **ok** | The helper of the observed owners never calls `registry.entries()` and the drain seeds its owners from it: the fallback does not depend on the query that can fail. |

## Honest limits

Static equality, AST counts and shape checks **cannot** replace execution.
They prove that the seven repairs have the required shape and that the
denominator did not regress; they prove **nothing** about the runtime
behaviour of the candidate, about the native API, about the product
acceptance or about the Stage gate.

* Dynamic correction 20: `NOT_RUN` (no runtime ACK exists).
* Dynamic corrections 15–19: `NOT_RUN` in this route.
* The historical 189 PASS of the correction 14 stays **historical**.
* Native evidence: `NOT_PROVEN`. Product and Stage: **no PASS**.
