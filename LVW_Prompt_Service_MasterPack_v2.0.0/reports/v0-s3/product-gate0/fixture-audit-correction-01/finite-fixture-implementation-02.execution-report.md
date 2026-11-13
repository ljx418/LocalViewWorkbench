# S3-P4 finite fixture execution report — finite-fixture-implementation-02 (corrected exact 13)

Role: implementation (Claude Code continuation instance). Result: **FAIL** — machine gate not passed.
No stage PASS claim, no product Gate0 claim, no re-run, no source/threshold/denominator/counter change.

## 1. Pre-execution read-only verification (all satisfied, nothing changed)

| Check | Expected | Observed |
|---|---|---|
| worktree HEAD | `763f3d561772ec8efa7aafe597b62ac77a3b7969` | `763f3d561772ec8efa7aafe597b62ac77a3b7969` (unchanged after the run) |
| 11 source pins | binding `source_pins` hashes | all 11 match byte-for-byte (executor.py, run_guarded_checks.py, fixture, 8 tools/tests) |
| Python | `/usr/bin/python3.12`, sha256 `e50d468e…4f`, 8020928 bytes | match |
| new binding | `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation-nodeid-corrected-02.binding.json`, sha256 `940d5e3c…7b7` | match (also equal to root's `corrected-02.binding.json` copy) |
| counter before | 1 SETTLED session / starts_total 0 / reserved 60 | match |
| inherited retry env | `CLAUDE_CODE_MAX_RETRIES=0`, `CLAUDE_CODE_RETRY_WATCHDOG=0` | both 0 in the live process env (natural inheritance, no config change by this instance) |
| temporary env | workspace-root `.claude/settings.local.json`, sha256 `7e6320a5…1b0` | unchanged after the run; left in place for root's restore |

Authorisation read: `reports/v0-s3/product-gate0/fixture-nodeid-correction-01/decision.json`,
frozen `s3-integration-offline-contract-01.md`, user `integration-fixture-explicit-retry-01.approval.json`.
No approval was bypassed; the harness approval ran normally and the command was accepted.

## 2. Execution (exactly once, from the package directory, verbatim `decision.argv`)

Command = `decision.json.argv` verbatim, `cwd` = the package directory
`/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`.
No loop, no wrapper script, no retry, no model/provider/account switch, no Codex handover.

- Outer exit code: **1**
- Runner label: `finite-fixture-implementation-02`
- Duration: 2.194 s (runner), pytest wall 2.07 s
- Receipt: `finite-fixture-implementation-02.receipt.json` (14 820 bytes)
- Raw stdout: `finite-fixture-implementation-02.stdout.log` (57 116 bytes, sha256 `f8f5a748…19f8`)
- Raw stderr: `finite-fixture-implementation-02.stderr.log` (0 bytes, sha256 `e3b0c442…b855`)
- `cleanup_proven = true`, `owned_root_removed = true`, `source_unchanged_during_run = true`,
  `runner_unchanged_during_run = true`, `outcome = FAIL`, `stage_pass_claim = false`, `product_gate0 = false`

## 3. The 13 exact nodes — collected exactly, all executed, all FAILED

Collection: `collected_count = 13`, and the collected nodeids are byte-identical to the 13 nodeids in
`decision.json.argv` (the root correction of the 9 double-parameter nodeids is confirmed effective;
the previous run collected 0 because of the omitted second parameter segment).

Result line in the raw log: `13 failed in 2.07s` (13 × `F`, zero passed, zero skipped, zero not-run).

| # | nodeid | result | failure reason (raw) |
|---|---|---|---|
| 1 | `test_the_fixture_clean_terminal_is_verified_by_the_parent` | FAIL | `offline boundary violation: subprocess.Popen (…)` |
| 2 | `test_a_blocking_callback_is_actually_stopped` | FAIL | `offline boundary violation: subprocess.Popen (…)` |
| 3 | `test_a_blocking_persistence_is_actually_stopped` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 4 | `…[history_replay-MESSAGE_HISTORY_STARTED_REPEATED]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 5 | `…[sequence_reversal-MESSAGE_SEQUENCE_NOT_INCREASING]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 6 | `…[duplicate_sequence-MESSAGE_SEQUENCE_NOT_INCREASING]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 7 | `…[oversize_message-MESSAGE_TOO_LARGE]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 8 | `…[foreign_identity-MESSAGE_RUN_ID_MISMATCH]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 9 | `…[unexpected_field-MESSAGE_KEY_SET_INVALID]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 10 | `…[nonfinite_number-MESSAGE_NONFINITE_NUMBER]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 11 | `…[early_exit-WORKER_EXITED_WITHOUT_TERMINAL]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 12 | `…[message_flood-MESSAGE_COUNT_EXCEEDED]` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |
| 13 | `test_a_bad_terminal_reference_is_refused` | FAIL | `finite cpu gate refused: CPU_CONCURRENCY_LIMIT` |

Raw log: exactly 2 × `offline boundary violation: subprocess.Popen` and exactly 11 ×
`finite cpu gate refused: CPU_CONCURRENCY_LIMIT`.

## 4. Root cause of the FAIL (candidate defect, not an authorisation problem)

`tools/test_v0_s3_supervisor.py` loads the guarded runner a **second** time at import time
(`load_runner_module()`, line 1281-1291: `importlib.util.spec_from_file_location('lvw_s3_guarded_runner', …)` +
`spec.loader.exec_module(module)` → `RUNNER_MODULE = load_runner_module()`). Executing that module body a second
time runs `sys.addaudithook(_audit_hook)` (run_guarded_checks.py:270) again, this time with the *second* module
instance's `PROCESS_GATE["executor"] is None`.

Consequence in this run:

1. Hook #1 (the runner instance, `PROCESS_GATE["executor"] = executor`) admitted nodes 1 and 2, charged the shared
   counter (2 PENDING charges) and returned.
2. Hook #2 (the duplicate instance) then hit the generic branch `if event in BLOCKED_EVENTS:` and raised
   `offline boundary violation: subprocess.Popen` **before the fork** — so the fixture child was never started
   (`pid: null`, `settled: false` on both charges).
3. Because the two charges were never settled, the executor's `_occupied()` counted 2 ≥ `max_concurrent = 2`, so
   every following start (nodes 3-13) was refused with `CPU_CONCURRENCY_LIMIT` before the fork.

This is a genuine defect of the frozen candidate under test (duplicate module execution ⇒ duplicate audit hook);
it is not a test-selection, budget, authorisation or harness-approval problem. The previous run never reached it
because it collected 0 nodes. Fixing it belongs to the candidate owner under the existing COMPLETE03 scope; this
instance did not touch the candidate, the tests, the thresholds, the fixed denominator, the binding or the counter.

## 5. Global counter after the run (not reset, not reduced, not extended)

`/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`, budget `s3-p4-9618f7c7bf12403b8877c90b92ed99a7`:

- `sessions`: 2 — the old failed session `session-5cc6f255f8b579ae5cb94931d71379eb` (SETTLED, 0.708 s, retained)
  and the new `session-a1c075996f29bcac7e48dabd0ef9eed3` (SETTLED, 2.188 s).
- `starts_total`: 2, `starts_by_role`: implementation 2 / independent_review 0.
- `charges`: 2 entries (clean_terminal, blocking_callback), both `state PENDING`, `pid null`, `settled false`
  (never started, never settled — retained as-is, not zeroed).
- `spent_wall_seconds`: 2.896; `reserved_wall_seconds`: 120.0; `active: true`; `suspended_at_utc` unchanged.
- No new counter, no reset, no additional start count, no denominator shrink.

## 6. Cleanup / own processes / tree state

- Owned runner root `/tmp/lvw-s3-integration-tyh547ez` removed; no `/tmp/lvw-s3-integration-*` remains.
- No fixture child was ever forked; no stray `v0_s3_supervisor_fixture.py` / `run_guarded_checks.py` process.
- No network, no GPU, no model, no Pillow/productionquality_worker child, no Windows service, no product ledger.
- Git tree unchanged: HEAD still `763f3d5…`, the only tracked modification is the pre-existing
  `implementation-integration-01/report.md` (preserved untouched); new files are the untracked
  `finite-fixture-implementation-02.*` artefacts plus this report.
- Temporary env `.claude/settings.local.json` left untouched (hash `7e6320a5…1b0`) for root's phase-end restore.

## 7. State to report to root

Machine gate **FAIL**, 13/13 collected and 13/13 failed; the finite verification is NOT satisfied.
Next action belongs to root: adjudicate the duplicate-audit-hook defect in the candidate (owner-side fix under
COMPLETE03), re-seal the 11 source pins and the binding, and issue a new bounded reservation for one more
exact-13 attempt. This instance performed no re-run and claims neither stage PASS nor product Gate0.
