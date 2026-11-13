# The finite fixture implementation run 05 — execution report

Label: `finite-fixture-implementation-05` — role `implementation` — mode `suite`.

Candidate commit before the run (and after the run): `07277a6f2f6f730dc7b9383bfeaf8c412126fe16`.
This is **not** a StagePASS and **not** a product gate 0 acceptance. It is the single
thirteen scenario implementation fixture run that the root grant
`reports/v0-s3/product-gate0/fixture-resume-05/grant.json` (parent authority
`AUTH-PROGRAM-V1-COMPLETE-03`, operational envelope revision 2) allowed exactly once.

## 1. The exact command

The argv of the root `fixture-resume-05/execution-argv.json` was executed once, verbatim,
with the cwd of the product pack of this worker:

```
/usr/bin/python3.12 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode suite --label finite-fixture-implementation-05 --binding /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation-final-05.binding.json --binding-sha256 3ae86ac3ce5fa5afff95770145717181fc1d380956fdfdd4b684deffb4f972c2 --role implementation --candidate-sha 07277a6f2f6f730dc7b9383bfeaf8c412126fe16 --modules 'tools/test_v0_s3_supervisor.py::test_the_fixture_clean_terminal_is_verified_by_the_parent,tools/test_v0_s3_supervisor.py::test_a_blocking_callback_is_actually_stopped,tools/test_v0_s3_supervisor.py::test_a_blocking_persistence_is_actually_stopped,tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[history_replay-MESSAGE_HISTORY_STARTED_REPEATED],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[sequence_reversal-MESSAGE_SEQUENCE_NOT_INCREASING],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[duplicate_sequence-MESSAGE_SEQUENCE_NOT_INCREASING],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[oversize_message-MESSAGE_TOO_LARGE],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[foreign_identity-MESSAGE_RUN_ID_MISMATCH],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[unexpected_field-MESSAGE_KEY_SET_INVALID],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[nonfinite_number-MESSAGE_NONFINITE_NUMBER],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[early_exit-WORKER_EXITED_WITHOUT_TERMINAL],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[message_flood-MESSAGE_COUNT_EXCEEDED],tools/test_v0_s3_supervisor.py::test_a_bad_terminal_reference_is_refused' --outdir reports/v0-s3/product-gate0/finite-fixture-implementation-05
```

* the outer capture tokens equal the root list element by element: **True**
* the `orig_argv` of the machine receipt equals the root list element by element: **True**
* the binding digest was verified before and by the executor: `3ae86ac3ce5fa5afff95770145717181fc1d380956fdfdd4b684deffb4f972c2` = expected `3ae86ac3ce5fa5afff95770145717181fc1d380956fdfdd4b684deffb4f972c2` → **True**
* the interpreter was the pinned one, `/usr/bin/python3.12`, digest `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` → **True**
* the outer wall of the one run: **3.987 s** (start `2026-11-13T09:20:15.639632590Z`, end `2026-11-13T09:20:19.627290968Z`)
* the **outer return code: 0** (raw file `finite-fixture-implementation-05.outer.returncode.txt`)
* the outer stdout/stderr are captured in `*.outer.stdout.log` / `*.outer.stderr.log` and are **separate files** from the runner's own `finite-fixture-implementation-05.stdout.log` / `.stderr.log`; no file was overwritten by the other

## 2. The read only pre flight (before the run)

| check | value | result |
|---|---|---|
| HEAD of the worktree | `07277a6f2f6f730dc7b9383bfeaf8c412126fe16` | equals the candidate of the grant and of the binding |
| source pins | 11 of 11 | every pinned file digest of `machine-binding.json` matched |
| python | `/usr/bin/python3.12` | digest matched |
| binding | `implementation-final-05.binding.json` | digest matched |
| shared counter | 3 sessions, all `SETTLED`; 15 charges; 180.0 s reserved; 8.446 s spent | clean terminal state, no live session |
| stray fixture processes | none | no `v0_s3_supervisor_fixture` and no `run_guarded_checks` process was alive |
| outdir | `reports/v0-s3/product-gate0/finite-fixture-implementation-05` | did not exist before the run |

No commit was made before the run, no source, test, contract, runner, executor, budget or
counter was modified, and no collect or guard mode was executed (those would consume a
session of the shared pool). The natural environment was used: no retry, no watchdog, no
model, no GPU, no network, no service, no native code, no browser, no FFmpeg, no user
media and no access to the original product ledger. The guard of the runner blocked
`socket.connect`, `socket.bind`, `socket.getaddrinfo`, `subprocess.Popen`, `os.system`,
`os.exec`, `os.spawn`, `os.posix_spawn`, `os.fork` and `os.forkpty`; the only process
creations were the thirteen bound fixture children of the sealed plan.

## 3. The thirteen results

pytest collected **13** node ids and the runner exit code is **0**;
the inner pytest stream of the runner is verbatim:

```
.............                                                            [100%]
13 passed in 3.34s
```

| # | node id | scenario | admitted | handle proven | pid / birth (linux start ticks) | child exit | counter state | settled |
|---|---|---|---|---|---|---|---|---|
| 1 | `tools/test_v0_s3_supervisor.py::test_the_fixture_clean_terminal_is_verified_by_the_parent` | clean_terminal | True | True | 3134767 / 10993923 | 0 | STOPPED | True |
| 2 | `tools/test_v0_s3_supervisor.py::test_a_blocking_callback_is_actually_stopped` | blocking_callback | True | True | 3134771 / 10993932 | -15 | STOPPED | True |
| 3 | `tools/test_v0_s3_supervisor.py::test_a_blocking_persistence_is_actually_stopped` | blocking_persistence | True | True | 3134784 / 10994036 | -15 | STOPPED | True |
| 4 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[history_replay-MESSAGE_HISTORY_STARTED_REPEATED]` | history_replay | True | True | 3134790 / 10994140 | -15 | STOPPED | True |
| 5 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[sequence_reversal-MESSAGE_SEQUENCE_NOT_INCREASING]` | sequence_reversal | True | True | 3134793 / 10994148 | -15 | STOPPED | True |
| 6 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[duplicate_sequence-MESSAGE_SEQUENCE_NOT_INCREASING]` | duplicate_sequence | True | True | 3134796 / 10994157 | -15 | STOPPED | True |
| 7 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[oversize_message-MESSAGE_TOO_LARGE]` | oversize_message | True | True | 3134858 / 10994167 | -15 | STOPPED | True |
| 8 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[foreign_identity-MESSAGE_RUN_ID_MISMATCH]` | foreign_identity | True | True | 3134870 / 10994176 | -15 | STOPPED | True |
| 9 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[unexpected_field-MESSAGE_KEY_SET_INVALID]` | unexpected_field | True | True | 3134873 / 10994184 | -15 | STOPPED | True |
| 10 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[nonfinite_number-MESSAGE_NONFINITE_NUMBER]` | nonfinite_number | True | True | 3134876 / 10994192 | -15 | STOPPED | True |
| 11 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[early_exit-WORKER_EXITED_WITHOUT_TERMINAL]` | early_exit | True | True | 3134879 / 10994201 | 0 | STOPPED | True |
| 12 | `tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[message_flood-MESSAGE_COUNT_EXCEEDED]` | message_flood | True | True | 3134882 / 10994209 | -15 | STOPPED | True |
| 13 | `tools/test_v0_s3_supervisor.py::test_a_bad_terminal_reference_is_refused` | bad_terminal_reference | True | True | 3134885 / 10994219 | -15 | STOPPED | True |

The eleven children that ended with `-15` are the **expected** SIGTERM of the bounded
stop of the protocol, blocking and flood scenarios: an expected kill of a child is not a
pytest failure. Two children (`clean_terminal` and the charge 25 of `early_exit`) ended
with `0` on their own. The pytest verdict of the run is `13 passed`; the pytest exit
code 0 alone is **not** treated as a product acceptance anywhere in this report.

### Admitted versus proven created

* admission attempts of this session: **13**
* child handles obtained: **13**
* child handles **proven** (pid plus `linux_start_ticks` birth, persisted in the shared counter): **13**
* charges without a handle: **[]**, refusals: **[]**, settlement failures: **[]**, uncertain custody: **False**

So admitted = 13 and proven created = 13 in this run; nothing was admitted without a
proven creation and nothing was created without an admission.

## 4. The cleanup

* owned root `/tmp/lvw-s3-integration-a68jkcw8` removed: **True** (the directory no longer exists on disk)
* cleanup proven: **True**, failure reasons: **[]**
* admissions revoked at the end of the session: **True**
* no fixture process and no runner process survived the run (`ps` shows none)
* the worker did not touch the `active` flag, the counter, the cleanup environment or
  the reservation; the sealing of this grant and the restoration of the counter by hash
  remain the root terminal action

## 5. The shared counter (the same counter, no refund, no new pool)

| counter field | before | after |
|---|---|---|
| starts_total | 15 | 28 |
| starts_by_role.implementation | 15 | 28 |
| starts_by_role.independent_review | 0 | 0 |
| reserved_wall_seconds | 180.0 | 240.0 |
| spent_wall_seconds | 8.446 | 12.362 |
| sessions | 3 | 4 |
| charges | 15 | 28 |

* the new session `session-97acf02d9448f7312b973d6ab0d5e12a` reserved **60.0 s**
  (30.0 s admission + 60.0 s cleanup) and spent **3.916 s**, state **SETTLED**
* the thirteen new charges are the indices 15..27; every one of them is `settled` with a recorded birth
* the 15 historical charges and the three historical sessions are preserved verbatim; no reservation and no spent second was refunded: **True**
* the remaining shared pool after this run is 0.0 s of the 240 s pool; the cumulative ceilings are total 28, implementation 28, independent review 8
* the counter digest moved from `c4839b0d7a5561ad9dfa9cd0e07899a5b4872682c87a72db19a92109dc0b7690` to `b928dd406165c2c1be15f6067bdcb8b09cb593a46579c2f6d9a24fd803a6e263`

## 6. What this run does **not** prove

The following stay **NOT_PROVEN** after this run and are out of its scope: the complete
fixed 24/28 checkpoint set, the product gate 12, Windows, native, GPU, A06, the original
product ledger, real product quality and the root migration. No StagePASS is claimed and
the product gate 0 is not accepted. The counter is at its cumulative ceiling: no further
implementation start is available under the revision 2 envelope, and this grant must be
sealed by the root after the terminal state.

## 7. The files of this evidence directory

| file | content |
|---|---|
| `finite-fixture-implementation-05.receipt.json` | the raw machine receipt of the runner |
| `finite-fixture-implementation-05.stdout.log` / `.stderr.log` | the inner pytest stream of the runner |
| `finite-fixture-implementation-05.outer.argv.txt` | the outer argv capture |
| `finite-fixture-implementation-05.outer.start.txt` / `.outer.end.txt` | the outer start and end wall clock |
| `finite-fixture-implementation-05.outer.returncode.txt` | the true outer return code |
| `finite-fixture-implementation-05.outer.stdout.log` / `.outer.stderr.log` | the outer streams, separate from the runner logs |
| `finite-fixture-implementation-05.outer-execution.json` | the consolidated outer evidence |
| `finite-fixture-implementation-05.node-results.json` | the thirteen node results |
| `finite-fixture-implementation-05.outer.counter-before.json` / `.after.json` | the counter before and after the run |

