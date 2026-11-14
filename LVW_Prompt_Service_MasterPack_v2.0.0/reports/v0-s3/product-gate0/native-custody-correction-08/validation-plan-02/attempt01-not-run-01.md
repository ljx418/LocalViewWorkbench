# N1 correction 08, attempt01: NOT RUN

The frozen batch of the correction 08 was **not executed**.  Nothing was run,
nothing was imported, nothing was collected, no pytest ran, no guard ran and
no counter was read.  This document records the exact state of the attempt.

## 1. The plan and the ACK

| Fact | Value |
|---|---|
| the plan of the root | `/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-08/validation-plan-01/plan.json` |
| its SHA256 | `8ebe597a526261396c27f26b270f22d04721f4c91f005bdfc6a4dfc373c077d4` (checked, it matches the ACK) |
| the candidate | `66600a1bd692c0149fc7724b624997bf2f40dcc1` |
| the ACK of the root | `ACK_ONE_FROZEN_175_NODE_OFFLINE_BATCH` (`msg_ded054b81a83`) |
| the withdrawal of the ACK | `msg_a161eaec16cc`, **before any valid batch began** |

## 2. The reason of the non execution

The counter of the frozen argv is **missing**:

* the exact path `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`
  does not exist;
* the directory `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/` does not exist either.

The boundary of the batch requires the counter to be read **once before and
once after** the batch, read only, with the expected digest
`acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`.  The
first outer observation of the counter therefore cannot succeed, and the
counter can no longer prove anything: the **history** of the budget of the
round is not re-provable on this machine.

The counter was **not** created, **not** written, **not** refunded, **not**
reset, **not** replaced and no old grant was revived.  The observation of the
missing state is a **stat of the exact path** of the frozen argv; the
content of the counter was not read, because there is nothing to read.

The root withdrew the ACK before any valid batch began and forbade the
execution of the guarded batch.  The batch was therefore not started.

## 3. The three commands of the frozen plan

All three commands are **NOT RUN**.  Their argv and their cwd are the frozen
ones and they are kept verbatim in
`attempt01-not-run-01.commands.json`.

| The command | The state | The exit code |
|---|---|---|
| `counter-before` | NOT RUN (the counter of the argv is missing) | `NOT_RUN` |
| `guarded-validation` | NOT RUN (the ACK was withdrawn before the batch began) | `NOT_RUN` |
| `counter-after` | NOT RUN (the counter of the argv is missing) | `NOT_RUN` |

There is no raw log, no receipt, no guard snapshot and no `pytest-temp` of
this attempt: nothing produced them.  The directory `attempt01/` was **not**
created, so that the directory of the next plan of the root is empty and
uncontaminated; this record and its companion are named with the suffix
`not-run-01` for that reason.

## 4. The state of the candidate and of the boundary

* the candidate `66600a1bd692c0149fc7724b624997bf2f40dcc1` was **not**
  imported, **not** collected and **not** executed; it was **not** modified
  by this attempt;
* the pinned report, the pinned sources and the pinned dependencies were
  **not** changed: the report of the delivery, its `SHA256SUMS` and the plan
  request keep their bytes;
* no Windows API, no job object, no process, no service, no socket, no
  database, no network, no download, no media and no GPU was touched;
* no agent was derived and no owner of another round was changed;
* the native claims of the package stay `NOT_PROVEN`, the claims of the
  delivery stay `READY_FOR_REVIEW` and they are **not** Stage PASS;
* the six majors of the independent review stay **OPEN** and the fifth
  failure stays **UNRESOLVED**: the batch that may produce its first and
  second raw facts did not run.

## 5. The disclosure of the path search that was started and stopped

Before the message of the root arrived, a read only **path enumeration** of
the file name of the counter was started (`find / -name shared-counter.json`).
It was stopped immediately when the message of the root arrived and it
printed **no** result.  No private file was opened or read by it, and no
path was taken from it.  The enumeration was not repeated and the path of
the counter was not widened: the only fact that is used is the missing state
of the **exact** path of the frozen argv, which the root confirmed with the
same precision.

## 6. The next step

The next step belongs to the root: it freezes another finite, side effect
free and offline plan in which the counter is **MISSING** and the history of
the budget is not re-provable, while the hard guard of the batch still
refuses every business process, socket, sqlite and general `dlopen`.  This
delivery does not retry, does not rerun, does not wrap and does not repair
the candidate on its own.
