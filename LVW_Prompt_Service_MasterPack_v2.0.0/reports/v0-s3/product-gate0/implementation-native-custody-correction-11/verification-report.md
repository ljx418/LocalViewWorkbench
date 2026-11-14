# N1 correction 11: the outcome of the one frozen batch

**This document is the handoff of the dynamic phase of the correction 11.**  The
static delivery of the correction 11 is `report.md`, `changed-assertions.md`,
`residual-mapping.md`, `atomic-coverage.md`, `source-pins.json`,
`f5-phase-status.json`, `static-implementation-receipt.json` and
`validation-plan-request.json`; those documents are the record of the static
phase and they are left byte for byte as the root pinned them.  The attempt
itself is `attempt01/` and its report is `attempt01/report.md`.

## The outcome

The one frozen batch of the plan of the root
(`native-custody-correction-11/validation-plan-01/plan.json`, SHA256
`dc65bba97f6b86a6745bd6a1848dad380987a964dbcde0b08f7f10b34bc48f86`, ACK
`ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH`) was executed **exactly once**, in the
order of the plan, with the three absolute argv, the two cwds and the
explicitly bound environment of the plan.  There was no rerun, no wrapper, no
extra node, no self repair and no deleted case.

| Fact | Value |
|---|---|
| the frozen node ids | 189, `collected == selected`, the order is identical |
| passed / failed / skipped | **186 / 3 / 0** |
| pytest exit | **1** |
| duration | 30.95 s (the bound of the batch is 300 s) |
| cleanup proven for the batch | **true** |
| the commands | three, exit 0 / 1 / 0 |
| the guard | preceded the candidate and pytest, the eight prohibited events were denied by its self test, the runtime denials are empty, the single preload was `ctypes.dlopen(None)` and the window is **CLOSED** |
| the descriptors | the same three (`0`, `1`, `2`) with the same identity before and after, `new_or_reused_fds: []` |
| the threads | `["MainThread"]` before and after |
| the counter | **MISSING** before and after (exact `lstat` only), the content was never read, the historical continuity is `UNAVAILABLE_NOT_PROVEN`, the expired grant was not revived |

## The three failures

They are classified in `attempt01/report.md` (section 3) by the static reading
of the sources and of the raw output of the batch:

1. **`test_n10_r02`** — the defect is in the **test seam** of the M05
   sub-scenario that the correction 11 itself added: the scripted
   `GetProcessTimes` of the synthetic kernel assigns to a `ctypes.byref`
   object, which supports neither the assignment nor the reading of an
   attribute, so the birth query raised before the race was reached.  The phase
   document of the node still shows the recovery closing the original handle
   of the process and of its thread **exactly once** and the creation
   delivering **no** handle.
2. **`test_n10_r04`** — a **latent defect of the frozen node** of the
   correction 10: the node never binds a process to the aggregate, so the
   release of the aggregate coordinates `self.process`, which is `None` in that
   node.  The predecessor candidate `cdac445` has the very same structure.  The
   node was masked until now because it failed earlier, with the
   `writer_endpoint` `NameError` that the correction 11 repaired.
3. **`test_n10_r10`** — a **latent defect of the frozen node** of the
   correction 10: the node reads the outcome of the **first** generation of
   the reader while the ordinary failure of the round is published in the
   **third** one (the reader consumed the READY and the STATUS frames first).
   The barrier of the node passed and the group of the fifth failure, that
   drives the same fault, reached its document with
   `reader_error = RuntimeError`.  The node was masked until now for the same
   reason as the node above.

No failure names a defect of the production code of the four Majors or of the
one Minor, and the candidate was **not** repaired and **not** rerun: the
correction of the three failures belongs to the root.

## The auxiliary action

One auxiliary action was executed after the batch: a standalone `python3 -c`
probe of the standard library module `ctypes` alone, used to classify the
failure of the node `n10_r02` from an observation instead of a guess.  It is
listed with its exact command, its output and its exit code in
`attempt01/auxiliary-actions.json`.  It is **not** accepted evidence and it is
**not** part of the guarded batch.  **No module of the candidate was imported
by it**: the command names `ctypes` and nothing else, and it started no
process, no collection and no test.

## The states of the phases

* The ten documents of the fifth failure group were **all** reached and
  **all** written: `attempt01/f5-phase-status.json` names every one of them
  with its digest.
* The bounded facts of the groups of the correction 10 are in `evidence/`; the
  status of every document is in `attempt01/n10-phase-status.json`: 35 written
  and **three** `NOT_RUN` with their actual cause (the node `n10_r10` failed
  in its first phase).

## The claims that this delivery does **not** make

The four Majors and the one Minor stay **OPEN**.  This batch proves neither
their closure nor their persistence.  The Stage is not passed, the product
gate 0 is not produced, no admission was produced and no native behaviour is
proven.  The M09 timeout branch carries an **auxiliary static** proof of the
order of the two facts; the presence of that proof is **not** a dynamic proof
of the branch, and this batch did not execute it in any case.  The root owns
the correction of the three failures, the independent review and the
acceptance.
