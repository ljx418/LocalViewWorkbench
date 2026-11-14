# Correction18 — implementation-boundary checklist (M2 1–5, M3 1–7)

Each line: independent-17 counterexample -> the exact try boundary / state
transition of the candidate -> the negative oracle that must fail closed.
Static only; the boundaries are checked on the **actual AST nesting**.

## M2 — attempted inventory, durable identity, final accounting

1. successful construction has no terminal document / later failure rewrites it
   -> `ledger.attempt(phase)` and `ledger.attempt(phase+'-construction')` happen
   **before** `_chain(...)`; the construction writes `EXECUTED` then `PASSED`
   (terminal) before `ledger.pass_` -> a construction that fails half way is
   `FAIL` with its own facts and the phase is `FAIL` after cleanup, never
   `NOT_RUN`.
2. coordination attempted after the operation / `_chain` outside its guard
   -> `ledger.attempt('r10-coordination')` moves **before** the endpoint is
   created; the earlier `_chain` moves **inside** the try whose `finally` owns
   the teardown and the drain -> an executed operation is never `NOT_RUN`.
3. barrier attempt/seam ordering, lost identity boolean, unconsumed write error
   -> the seam marks the barrier attempt **in the seam**; the seam persists the
   document **before** it publishes the completion; the phase consumes
   `api.barrier_write_error`; every rewrite of the barrier document carries
   `barrier_observed_object_is_original` -> a barrier whose document was not
   written is `FAIL`, and the identity is a **boolean**, never a `repr`.
4. phase finalized before cleanup / cleanup errors lost
   -> the phase result is written **in the `finally`**, after the teardown, and
   it carries the original failure **and** every cleanup diagnostic; `PASSED`
   needs proof **and** quiescence **and** zero cleanup/evidence errors ->
   a failed stop keeps the earlier checks `PASSED` and the result is `FAIL`.
5. worker join outside the guard / single overwritten cleanup error
   -> `worker.join_bounded` and `worker.is_alive()` run in their own guards
   **before** the drain; the cleanup errors are a **list** -> one exception
   never skips the owners nor the result document.

## M3 — controlled paths, owner snapshot, lost errors

1. start / `RUNNING` assertion outside the cleanup `finally`
   -> the cleanup region is the `Try` whose `finalbody` owns the drain; the
   start and the assertion are in its **body** -> a start failure is cleaned,
   joined and proved.
2. constructor seam reads `target` instead of `_target`
   -> the seam reads `getattr(thread, '_target', None)` and the owner is the
   **exact** custody-registered channel (`owner is controlled_custody_channel()`)
   -> a similarly named parent thread is never injected into.
3. `CLOSE_FAILURE` raises the generic sentinel
   -> the sentinel is raised only for the checkpoints that are **not**
   `CLOSE_FAILURE` and **not** `CONSTRUCTOR_FAILURE` -> the close case has
   `failure is None` and `cleanup_ran_while_unwinding is False`.
4. unrelated close failures tolerated next to the intended failure
   -> every non-close subcase asserts its **own** `close_failures == []` ->
   an unrelated `RuntimeError` of a child endpoint fails the subcase.
5. enumeration / generation race
   -> the generation is read **before** the enumeration, **after** it and
   **after** the joined producers; a **final** exact-owner resnapshot must
   agree -> a late owner is never certified as quiescent and never left behind.
6. earlier errors erased / cancellation identity lost
   -> **every** iteration is kept (`all_salvage`), the classification error
   keeps its exact diagnostic, the **exact** `KeyboardInterrupt`/`SystemExit`
   object is retained and re-raised when nothing else unwinds -> an earlier
   error stays a proof failure.
7. unguarded cleanup call sites
   -> the enumeration, the release of the gates, the joins, the liveness
   queries, the endpoint closes and the writing of the evidence are guarded and
   their errors are **lists** -> one exception never skips the remaining owners
   nor the result, and an unknown identity is never a proved exit.
