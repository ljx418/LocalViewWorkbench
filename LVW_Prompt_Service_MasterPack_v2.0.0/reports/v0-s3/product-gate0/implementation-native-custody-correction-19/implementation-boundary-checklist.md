# Correction19 — implementation-boundary checklist (M2/M3 residuals of the independent 18)

Each line: counterexample of the independent review 18 -> the exact try boundary /
state transition -> the negative oracle that fails closed.  Static only; the
boundaries are read from the **actual AST nesting**.

## The three root checks

R1 first channel selects the parent, not the child
   -> `controlled_custody_channel()` selects the entry named `controlled:channel`
   (the **newly retained** owner of the custody of the child); the fallback
   selects the channel whose owner `is not controlled_parent_channel` and the
   parent is the entry named `launch:channel` -> the parent is never injected.
R2 a failed terminal write advances the ledger
   -> every `ledger.fail`/`ledger.pass_` is **inside** the guard of the result of
   the write (`written_result is not None`, `document['status']`, the `else` of
   the write) -> a failed write leaves the name `ATTEMPTED` and is recovered
   once by the outer inventory.
R3 the coordination try begins after the start
   -> the cleanup owning `Try` of the coordination **contains** the endpoint
   construction and `reader.start()` in its **body** -> a start that took effect
   and raised is still closed, joined and proved.

## M2 — terminal evidence against persistence and cleanup

1. failed terminal persistence advances the ledger (18-M2.1)
   -> `record_guarded` returns `None` and the caller advances the ledger only
   when the result `is not None`; the phase result is written **before**
   `ledger.pass_`/`ledger.fail` -> a failed write stays `ATTEMPTED`.
2. early barrier persistence diagnostics disappear (18-M2.2)
   -> the final document of the phase carries `barrier_persisted`,
   `barrier_write_error` and the identity boolean/type/detail of the original
   object; the rewrite of the barrier document carries them too -> an assertion
   that fails after the seam ran never loses the fault of the seam.
3. the earlier coordination passes before its cleanup (18-M2.3)
   -> the terminal document of `r10-coordination` and the terminal document of
   `r10-early-salvage` are written in the `finally` that owns the drain -> no
   terminal `PASSED` before the cleanup; the cleanup diagnostics are durable.
4. a nonquiescent drain passes the test (18-M2.4)
   -> the drain returns a proof failure when it is not quiescent; every caller
   requires proof `None` **and** quiescence `True` **and** no cleanup error ->
   a durable `FAIL` of a phase always fails the test with it.

## M3 — all-owner cleanup and exact cancellation propagation

1. the constructor driver is unreachable (18-M3.1)
   -> the child is selected by the **exact** retained custody entry, the seam
   compares `owner is child` and the original `Thread.start` is called **before**
   the exact `_R07ConstructorFailure` is raised inside the constructor.
2. the traversal aborts and empties the owners (18-M3.2)
   -> `_registry_owners` guards the entries, the per container query, the
   session, the channel and the provenance **one by one**; the exact observed
   thread objects are retained as an independent fallback and the owners are
   never emptied -> one failing query never skips the other owners.
3. the reads of the drain and the release of the gates are unguarded (18-M3.2)
   -> the generation, the pending starts and the final resnapshot are guarded
   reads and the release is **one action per gate** -> a failed gate never skips
   the next one and every failure keeps the exact interruption.
4. the cancellation identity is lost or never rethrown (18-M3.3)
   -> every caller keeps the **exact** object in its own list and rethrows it
   **before** the proof assertion -> the priority is the unwinding failure, then
   the exact interruption, then the ordinary assertion.
5. the coordination start is outside the cleanup (18-M3.4)
   -> the cleanup owning `Try` starts before the endpoint construction and
   before `reader.start()` -> a partial construction is still closed and joined.
6. the main child close catches only `Exception` (18-M3.5)
   -> every close of the child endpoint catches `BaseException` and records the
   exact cancellation -> the first cancellation never skips the second close.
7. the quiescence is recorded but not enforced (18-M3.6)
   -> the final exact owner resnapshot of the drain is a **proof failure** when
   it is not quiescent and every caller asserts it -> a late owner is never
   certified as exited.

## What is preserved

- M1 `CLOSED_STATIC`: the public start, the zero admission, the returned
  `UNKNOWN_RETAINED` state and the retention oracle are untouched; the twelve
  counterexamples of the correction 17 stay closed; no assertion is removed; the
  189 node ids keep their order; the six other modules are byte identical and
  no new framework, manager or product obligation is added.
