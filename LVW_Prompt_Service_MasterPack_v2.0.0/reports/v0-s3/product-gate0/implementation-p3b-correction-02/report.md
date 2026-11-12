# P3B aggregate correction 02 — implementation receipt — READY_FOR_REVIEW

Candidate: `9ed09513eac35636175b24a514b05d9d0c180717` (final; binds every check below).
Root adjudication merged: `237760b99501db316ed4328088dd8365992b0f9d`
(`ROOT_P3B_CORRECTION02_AGGREGATE_DISPOSITION`, `CHANGES_REQUIRED_WITH_MANDATORY_PARENT_TIMING_INTEGRATION`,
0 fatal / 5 major, all requiring a local correction).
Independent review merged: `5894419833fb2ffab5aadb4cffc6881066befb4c` (correction-01 review, 0 fatal / 5 major /
0 minor) with its findings, targeted probes and replayed observations.
Original historical report bytes restored at `7a14f62`.
Frozen contract: `reports/v0-s3/product-gate0/p3b-quality-contract.md`
(sha256 `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`).
Frozen input projection: `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`
(sha256 `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`).

`contract_changes=none` — no public API, schema, quality threshold, denominator, prompt, workflow,
owner, package, P3A, authority, ledger, contract, quality set, prelabel, sample, projection, coordinate,
MANIFEST, frozen-packet file, old report, old log, old probe, old checksum or old runner was modified.
The scoring thresholds are exactly the frozen ones: 8 of 10 images, 5 of 6 videos, zero critical
hallucinations, fixed sixteen row denominator, and no extra all-technical-success prerequisite.

## Source of this candidate

| File | sha256 | role |
|---|---|---|
| `tools/v0_s3_quality_phase.py` | `d2c12745dcb56230175f2ac6b113dd9beac956f4e6fb0d6be598b7dcfc8db0b4` | QD execution phase + QS independent score recomputation |
| `tools/test_v0_s3_quality_phase.py` | `a721d75ec70581d875bf22fb5f182b249e94a7bf68e0a3abc70f5a9e83fce8ab` | 112 offline checks (95 preserved + 17 new regressions) |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-02/replay_correction01_probes.py` | `b59a3dcf3d68ca97c2eb137a0cc594354fd70e9099e17a9a1aa7b990de8ae97b` | replay of the correction-01 review's counterexamples as observations |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-02/run_guarded_probe.py` | `4eea0989e4ba51a130a24ed0498af9c7993fa63705a7cb5c12531512339ccb77` | guarded runner for that replay |

The immutable original runner `reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py` is
reused **without any edit**. Only the two tools and the new correction-02 subtree differ from the merged
adjudication commit.

## Complete V0–V3 outline (unchanged coordinate)

| Delivery | Stage | Completed / declared | Boundary |
|---|---|---:|---|
| V0 | V0-S0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-Min | V0-S1 | 5/5 | 已签仅V0-Min |
| V1前置 | R0 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| V1早期切片 | R1a | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0.1 | V0-S2 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0.2 | V0-S3 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V1 | R1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1 | V1-M1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| V1 | R2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R4 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5a | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5b | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5c | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

Copied unchanged from `plans/execution-control.json` `development_outline`. **No completion count was
advanced.** V0-S3 stays 0/6: this is offline wiring only.

## Ten required fields

1. 当前坐标: R1 / WP-R1-U3 / `S3_P3B_QUALITY_INTEGRATION_IMPLEMENTATION`; this batch is the second
   aggregate correction of S3-P3B under the frozen internal contract, the correction-01 independent
   review and the root correction-02 adjudication.
2. 本批完成: the five remaining major findings — M01 persisted receipt accounting, M02 original ancestor
   ownership and descriptor relative writes, M08 unknown evidence fail closed on every row, NM01 parent
   proof identity and freshness, NM02 monotonic clock and honest timing assurance — fixed together in
   one round. The seven findings the correction-01 review closed stay closed and all of their
   obligations are retained. The original 95 checks are preserved and pass; 17 new regression cases were
   added, 112 in total. The correction-01 counterexamples were replayed once as observations.
   Implementation self-check only; independent review pending; no machine product acceptance and no
   human signature is claimed.
3. 最后通过门禁: unchanged `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, scoped existing human acceptance.
4. 当前阻塞门禁: `S3_QUALITY_EXECUTOR_A06_COORDINATOR_AND_GATE0_PENDING`, and additionally the mandatory
   parent hard process supervision, which this batch records as
   `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`.
5. 全局路线位置: corrected offline quality integration → independent verification of this candidate →
   root gate decision → frozen complete product Gate0 → bounded same-source real run → independent
   scoring → necessary human/release gates.
6. 剩余工作: independent isolated review of candidate `9ed0951`; the parent integration that produces
   the typed capacity proof and the enforceable process watchdog; the production
   `video_snapshot_residue` adapter; A06 network enforcement; the real finite sixteen-row run; the
   independent scoring pass on the real raw artifacts; the product Gate0 and the required human
   signature.
7. 下一责任人: separate independent reviewer instance, then root (Codex) as architecture and gate owner.
8. 所需授权: none additional for the completed offline scope. No real service, model, media, GPU,
   network, download, ledger, Windows/WSL/PowerShell, parser or host-exe hashing action was performed,
   and nothing here authorizes one.
9. 证据目录: `reports/v0-s3/product-gate0/implementation-p3b-correction-02/` (receipt.json, report.md,
   SHA256SUMS, the two guarded check receipts, their raw stdout/stderr, the guard self-test and the
   replayed correction-01 observations).
10. 精确停止原因: the frozen QD + QS contract and all five remaining accepted findings are implemented,
    the 112-check suite is green with its real exit code, and the correction-01 counterexamples were
    replayed as observations. The implementer stops at **READY_FOR_REVIEW**. No Stage PASS, no product
    Gate0, no machine product acceptance and no human signature is declared or implied, and this batch
    does not claim that the hard full-phase timing is closed.

## Finding-by-finding mapping

| Finding | Change | New regression check | Replayed observation |
|---|---|---|---|
| **M01** | The persisted receipt states its own final bytes and files. The size is computed to a bounded fixed point: the self-inclusive fields are filled with the assumed length, the document is serialized, and a padding field absorbs the remaining difference, so the recorded length is exactly the length on disk. The file is read back and the recorded bytes, file count and total agree with the disk. The 8MiB / 128MiB / 256 caps stay exact, the write stays exclusive, and an impossible receipt is an explicit `TERMINAL_RECEIPT_NOT_PERSISTED` status rather than a truncation, an overwrite or an erasure. | `test_correction02_m01_the_persisted_receipt_states_its_own_final_totals`, `test_correction02_m01_the_receipt_caps_are_exact_and_one_over` (artifact / total / files) | `persisted_receipt_totals`: stored 49741 bytes = actual, stored 137 files = actual, stored 166835 bytes = actual, `agrees: true`. `receipt_*_exact` persisted, `receipt_*_over` refused with `RECEIPT_OVER_ARTIFACT_CAP` / `RECEIPT_TOTAL_BUDGET_EXCEEDED` / `RECEIPT_FILE_BUDGET_EXCEEDED`. |
| **M02** | The run root, the temp directory, the phase directory and every nested artifact directory are opened relative to their pinned parent handle with `O_DIRECTORY\|O_NOFOLLOW`, and every file is created exclusively against the pinned handle of its own directory. The identities are compared after every controlled callback, before the send and before the cleanup handoff, so a renamed, replaced or symlinked ancestor is detected and never adopted. An initial temp symlink creates zero foreign entries, a temp ancestor redirect inside a callback writes no file into the old root, and a deterministic `os.open` interposition cannot write into a foreign root. The identity check follows the accepted protected directory pattern in `tools/v0_s3_stage_runtime.py`, which was read as a reference only; P3A was not modified. Every owned handle is closed on failure and on a refused replay, and no write can happen after the root closure. | `test_correction02_m02_a_temp_ancestor_redirect_writes_nothing_into_the_old_root`, `test_correction02_m02_an_initial_temp_symlink_creates_no_foreign_entry`, `test_correction02_m02_a_deterministic_open_interposition_cannot_write_into_a_foreign_root`, `test_correction02_m02_the_owned_handles_are_closed_after_the_run` | `temp_ancestor_callback_redirect`: 0 submissions, no file in the old directory, receipt not persisted. `artifact_open_ancestor_race`: foreign files `[]`, 0 submissions, `ARTIFACT_REDIRECT_FORBIDDEN:rows`. `initial_temp_redirect`: foreign entries `[]`, 0 submissions, `ARTIFACT_REDIRECT_FORBIDDEN:temp`. `existing_directory`: 16 BLOCKED rows, nothing written into the old root. |
| **M08** | The public scoring validates the source, storage and cleanup evidence of every row, pass or fail. A passed row with a missing release proof, a missing or non-empty residue observation, source evidence that does not match the row identity, or an explicit storage or cleanup uncertainty can never become usable or resolved. A known failure with missing source evidence or unproven storage stays unresolved. The independent raw critical findings stay visible whenever their binding can actually be verified. The frozen 8/10 + 5/6 + global critical zero are unchanged and a known verified refusal or structure failure is resolved but never usable. | `test_correction02_m08_a_pass_row_with_unknown_cleanup_cannot_aggregate_pass`, `test_correction02_m08_a_known_fail_row_with_unknown_storage_cannot_aggregate_pass`, `test_correction02_m08_a_known_fail_row_with_unknown_source_cannot_aggregate_pass`, `test_correction02_m08_a_valid_known_failure_resolves_with_complete_evidence` | `PASS_cleanup_unknown`, `known_FAIL_storage_unknown` and `known_FAIL_source_unknown` all stop the aggregate PASS with `EVIDENCE_UNKNOWN:RELEASE_EVIDENCE_MISSING` / `EVIDENCE_UNKNOWN:STORAGE_UNPROVEN` / `EVIDENCE_UNKNOWN:SOURCE_EVIDENCE_MISSING`. The valid known failure fixture demonstrates the *complete* real evidence (source identity match, proven release, empty residue) and resolves without becoming usable. |
| **NM01** | The parent capacity proof is a typed internal document (`LVW_PARENT_CAPACITY_PROOF/1`) that binds the exact run id, candidate and child authorization and carries a finite, non boolean issue and expiry in the phase monotonic clock. The validity interval and a sufficient finite action capacity are checked before the first send. A missing, unknown, untyped, foreign, stale, non-finite or diminished proof produces zero sends and all sixteen rows refused. The proof never claims a real reservation: the authentic provider and the actual debit stay with the parent coordinator, and no ledger API was invented. | `test_correction02_nm01_a_proof_for_another_run_is_refused`, `test_correction02_nm01_a_stale_proof_is_refused`, `test_correction02_nm01_a_proof_with_a_non_finite_interval_is_refused`, `test_correction_admission_an_unknown_parent_budget_is_refused`, `test_correction_admission_an_insufficient_parent_capacity_refuses_every_send` | `parent_proof_wrong_identity`, `parent_proof_stale`, `parent_proof_diminished` and `parent_proof_non_finite`: 0 submissions, 16 rows, the matching refusal code. |
| **NM02** | The phase clock must be finite and monotonic; a decreasing reading is refused before any public action. The cooperative pre and post checks are kept and the receipt states plainly that a synchronous callable cannot be preemptively bounded by a post-return elapsed check. The mandatory enforceable parent process supervision and owned cleanup are recorded as `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER` with the frozen 600s and 10800s limits unchanged. No timeout thread that could keep side effects running after the terminal state and no separate worker platform was introduced, and this batch does not claim hard full-phase timing closed. | `test_correction02_nm02_a_decreasing_clock_is_refused`, `test_correction02_nm02_the_hard_supervision_blocker_is_recorded` | `decreasing_phase_clock`: 0 submissions, `CLOCK_NOT_MONOTONIC`. `post_return_elapsed_only`: the callback returns only after the phase deadline and is then rejected, with `hard_timing_blocker: UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER` and `synchronous_callables_preemptively_bounded: false` recorded. |

The replayed observations are observations of the correction, not passing tests: the correction-01
defect expectations were never turned into green cases and the original probe files were only read.

## Actual checks and real exit codes

Every check was executed through a guarded runner whose `sys.addaudithook` guard is installed **before**
pytest or any product module is imported. Plugin autoload, the cache provider and bytecode writing are
disabled, and socket connect/bind/name resolution and every host process creation are blocked. The raw
stdout and stderr streams and the actual exit code are stored next to each other; the shell captured the
process exit code directly with no pipeline masking it.

| Run | Label | Exit | Result | Denominator | Evidence |
|---|---|---:|---|---|---|
| guard self-test | guard-selftest | 0 | 4 attempts, 4 blocked (connect/bind/Popen/system) | 4 | `guard-selftest.guard-selftest.json` |
| full suite on the final candidate | full-final | 0 | 112 passed | 112 | `full-final.stdout.log`, `full-final.receipt.json` |
| replayed correction-01 counterexamples | correction01-probe-replay | 0 | 21 observations | 21 | `correction01-probe-replay.stdout.log`, `correction01-probe-replay.receipt.json` |

The 39 + 28 directed duplicates of the original implementation and the directed 28 of correction-01 were
**not** re-run, and the P3A 121, P2B 237 and full-project suites were not re-run, as the task requires.
The 112-check full run includes the 95 preserved checks and the 17 new regressions in one pass.

### Failed attempts during this round, retained honestly

The interactive debugging rounds below were executed as
`python3 -B -m pytest tools/test_v0_s3_quality_phase.py -q -p no:cacheprovider 2>&1 | grep ...`.
Their **exit codes are UNKNOWN**: the pipeline masked the pytest exit status. They are not acceptance
evidence and they are not counted as passing.

| Round | Exit | Observed | What it was |
|---|---:|---|---|
| 1 | UNKNOWN | 46 failed, 60 passed | The typed parent capacity proof and the descriptor relative ownership had not yet been applied to the test fixtures, so every phase construction was refused. |
| 2 | UNKNOWN | 6 failed, 89 passed | Six existing expectations still used the previous ownership and admission model: the ancestor redirect test opened the directory by hand, the replaced root and phase expectations used the old error names, and the admission tests expected an exception instead of a refused receipt. |
| 3 | UNKNOWN | 1 failed, 111 passed | The parent proof helper could not express an explicitly missing proof, because `None` selected the default proof. |

Every round produced new evidence and located a different defect each time, so this is not the
prohibited two-same-route-corrections-without-progress pattern. No failed run was rewritten or deleted.

One correction was needed in the evidence itself: the first replay of the m01 receipt caps computed the
padding without the new self-inclusive fields, so the "exact" case overshot the cap. The probe was
corrected to derive the actual serialized length, and the observation was re-executed. Every check was
then re-run against the final candidate, so no evidence metadata was rebound without a rerun.

## Retained fixture state and cleanup

- The synthetic fixtures (ten generated 4x4 PNGs, six small synthetic video byte blobs, the synthetic
  provider log and the phase artifacts) live only in pytest's own temporary roots under
  `/tmp/pytest-of-administrator/` and in the replay's own bounded root, which the replay deletes itself
  before it exits. They are outside the repository and nothing binary is committed.
- **No cleanup is claimed as a product property.** The parent `OwnedArchive` owns the real raw archive
  and deletion; the pytest temporary retention is a harness fact.
- The repository contains no generated phase directory, and the pre-existing untracked `__pycache__`
  directories were neither deleted nor committed.
- The replay's own fixture root is removed by the replay itself (`own_fixture_cleanup`), and its path
  is recorded in the observation document.

## Limits, and what this batch does NOT prove

- Offline only. No real ComfyUI, no real Ollama, no model, no GPU, no real media, no network, no
  download, no ledger mutation, no Windows/WSL/PowerShell, no host-exe hashing, no parser probe, no
  full checkpoint and no hung process was executed.
- The native HTTP/provider boundary and the media bytes are synthetic. The suite proves the wiring, the
  refusals and the evidence binding; it proves **no** product quality result.
- **The mandatory hard end-to-end process supervision and owned cleanup are not implemented here.**
  A synchronous callable cannot be preemptively bounded by a post-return elapsed check, so the phase
  performs cooperative pre and post checks only and records
  `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`. The authentic parent watchdog belongs in the upcoming thin
  coordinator and must be demonstrated on a controlled blocked operation before any real run or the
  product Gate0. This batch does not claim hard full-phase timing closed; the frozen 600s and 10800s
  limits are unchanged.
- The parent capacity proof is an internal typed document. It proves that the phase was admitted; it
  does not prove that a real reservation exists. The authentic provider and the actual debit stay with
  the parent coordinator.
- The production `video_snapshot_residue` adapter is still pending. Until the parent supplies it, no
  real video row can be shown clean, which is the intended fail closed behaviour.
- The ownership guarantee is an in-process inode observation of the owned directories. It detects a
  renamed, replaced or symlinked ancestor and refuses to write through it; it does not claim immunity
  against a hostile kernel or a filesystem that moves inodes underneath the process.
- The quality set, the prelabels and the frozen projection are never read by the execution or the
  scoring module; the projection carries no label, caption or expected answer, and the five scoring
  dimensions remain embedded constants of the frozen rubric.
- `public_video_oracle` still requires independent decoder recomputation of the frame bytes, and four
  sampled frames still cannot prove full motion continuity or physical camera movement.
- **Not proven:** the parent timing supervision, the production residue adapter, the parent admission
  integration, A06 network enforcement, the real finite sixteen-row run and the real product quality,
  the product Gate0 and its fixed twelve items, the independent review of this candidate, and the human
  signature.
- No machine product acceptance, no independent review verdict, no Stage PASS and no human signature is
  produced or implied by this receipt.
