# Correction 22 — the summary of the static checks

Ten checks, ten passed, exit code `0`. The machine readable result is
`static-checks-report.json`; the instrument is `check_correction22.py`.

The instrument is **static**: it reads the candidate and the frozen baseline
as **data** (`ast`, `hashlib`, read-only `git show`). It never imports the
candidate, never collects it, never runs a test, never opens a socket, a
database, a model or a native library and never starts a product process.

| # | Check | What it proves | Result |
|---|---|---|---|
| 1 | `denominator` | the exact **189** identifiers, in the order, of the five modules of the frozen denominator: 117 + 16 + 24 + 18 + 14, all unique and equal to the baseline | PASS |
| 2 | `assertions` | the **414 → 414** predicates: **8 moved**, **0 added**, **0 removed**, and every moved predicate is the requery of the liveness of an owner | PASS |
| 3 | `unchanged_sources` | the six other sources of the correction are **byte identical** (the SHA256 pins of the frozen baseline) | PASS |
| 4 | `evidence_root` | the evidence root of the module is the **NEW** directory of the correction 22 and the name of the correction 21 is gone from the module | PASS |
| 5 | `M2.a_final_controlled_verdict` | a **real AST order** check of the `finally` of the controlled subcase: the guarded actions, then the complete facts and the durable write, then the priority; the `not raised` exemption is **gone** and the verdict is enforced | PASS |
| 6 | `M2.b_zero_registry_durable` | a **real AST** check: the document of the round of the zero expiry carries the errors of the query of the registry as an **explicit durable field** and the verdict is recomputed with them | PASS |
| 7 | `M3.a_r12_all_actions_before_priority` | a **real AST order** check: the public stop of the round is attempted **before** the priority, its failure is retained and never silently swallowed, and the ordinary errors of the cleanup are consumed | PASS |
| 8 | `M3.b_guarded_closes` | a **real AST** check: **no** direct close of an endpoint, of a transport or of a channel in a cleanup region is unguarded, and the priority of the await is **not** a statement of its `finally` | PASS |
| 9 | `M3.c_error_list_consumers` | a **real AST dataflow** check: every list of the errors of a cleanup of the module is read somewhere else than in its own `append` — the list of the unconsumed lists is **empty** | PASS |
| 10 | `M3.c_deferred_priority` | a **real AST nesting** check: no loop over the owners of a round re-raises inside its body, the guarded join records the failure and the exact object of a cancellation and never raises, and the liveness of an owner is the fact of the guarded join | PASS |

## The limits of these checks

The checks read the **shape** of the candidate. They prove that the six
repairs have the required shape, that the denominator did not regress, that
the six other sources are untouched and that no collected error list is left
without a consumer. They prove **nothing** about the runtime behaviour of the
candidate, about the native API, about the product acceptance or about the
Stage gate. A **real AST** check is not an execution: the actual raw results,
the events, the oracles, the negatives, the returned states and the bounded
cleanup evidence remain required after a separately frozen runtime ACK and an
independent review of the actual source.

The checks of the denominator, of the assertions and of the six unchanged
sources are the checks of the correction 21 and of the correction 20: they
are kept **unchanged** so that the regression guard of the correction 22 is
the regression guard of the correction 21.
