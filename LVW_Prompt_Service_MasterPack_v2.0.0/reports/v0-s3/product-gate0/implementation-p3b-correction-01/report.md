# P3B aggregate correction 01 — implementation receipt — READY_FOR_REVIEW

Candidate: `376ea9283cb7096c2fc35f6eab561919c07b6d1f` (final; binds every check below).
Root adjudication merged: `0c7d27b436abb81042e6ef160ef663ff3e1c4d22`
(`CODEX_P3B_AGGREGATE_CORRECTION_DISPOSITION`, 0 fatal / 9 major / 1 minor, all accepted).
Independent review merged: `e2294724463efcab1a202a25563f76a24eea798f`
(findings `reports/v0-s3/product-gate0/independent-p3b/findings.json`, probe and boundary observations).
Frozen contract: `reports/v0-s3/product-gate0/p3b-quality-contract.md`
(sha256 `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`).
Frozen input projection: `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`
(sha256 `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`).

`contract_changes=none` — no public API, schema, threshold, denominator, prompt, workflow, owner,
authority, ledger, quality-set, prelabel, sample, template, coordinate, MANIFEST or frozen-packet
file was modified. The scoring thresholds are exactly the frozen ones: 8 of 10 images, 5 of 6 videos,
zero critical hallucinations, fixed sixteen row denominator.

## Source of this candidate

| File | sha256 | role |
|---|---|---|
| `tools/v0_s3_quality_phase.py` | `941432c730a4cc6758b54dacb0a44e4000ac847dccbfc4aee492f2b13baa2dd3` | QD execution phase + QS independent score recomputation |
| `tools/test_v0_s3_quality_phase.py` | `82fd901ea060ec17b4cbb4e54940214fed8a574f9300481314d650e35924fd57` | 95 offline checks (67 preserved + 28 new regressions) |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-01/replay_review_probes.py` | `05e2a4355440146c2ba47dc487208d95c7943dee9b46bc529649c37394eeeeb0` | replay of the review's counterexamples as observations |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-01/run_guarded_probe.py` | `93b67413d8d7958274eebb41732cde602070eec5df89937b966076fa10857ef4` | guarded runner for that replay |

The original implementation runner
`reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py` is reused **without any
edit**; the new guarded runner in this directory exists only because the replay is not a pytest
run. Neither the original report, logs nor runner were modified.

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

1. 当前坐标: R1 / WP-R1-U3 / `S3_P3B_QUALITY_INTEGRATION_IMPLEMENTATION`; this batch is the one
   aggregate correction of S3-P3B under the frozen internal contract and the root adjudication.
2. 本批完成: all nine major findings and the one minor finding of the independent review are fixed
   together in one round, plus the already-frozen timing and parent-admission gaps. The original 67
   checks are preserved and pass; 28 new regression checks were added, 95 in total. The review's
   counterexamples were replayed once as observations. Implementation self-check only; independent
   review pending; no machine product acceptance and no human signature is claimed.
3. 最后通过门禁: unchanged `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, scoped existing human acceptance.
4. 当前阻塞门禁: `S3_QUALITY_EXECUTOR_A06_COORDINATOR_AND_GATE0_PENDING` — the independent review of
   this corrected candidate, the real product Gate0, the real run, A06 and the required human
   signature are all still open.
5. 全局路线位置: corrected offline quality integration → independent verification of this candidate →
   root gate decision → frozen complete product Gate0 → bounded same-source real run → independent
   scoring → necessary human/release gates.
6. 剩余工作: independent isolated review of candidate `376ea92`; the real runtime staging (actual
   profile, model digest, media preparation, child authorization, single GPU); the parent integration
   that produces the bounded capacity proof this phase now demands; the production
   `video_snapshot_residue` adapter; A06 network enforcement; the real finite sixteen-row run; the
   independent scoring pass on the real raw artifacts; and the required human signature.
7. 下一责任人: separate independent reviewer instance, then root (Codex) as architecture and gate owner.
8. 所需授权: none additional for the completed offline scope. No real service, model, media, GPU,
   network, download, ledger, Windows/WSL/PowerShell, parser or host-exe hashing action was performed,
   and nothing here authorizes one.
9. 证据目录: `reports/v0-s3/product-gate0/implementation-p3b-correction-01/` (receipt.json, report.md,
   SHA256SUMS, the three guarded check receipts, their raw stdout/stderr, the guard self-test and the
   replayed review observations).
10. 精确停止原因: the frozen QD + QS contract and every accepted finding are implemented, the
    directed regressions and the full 95-check suite are green with their real exit codes, and the
    review's counterexamples were replayed as observations. The implementer stops at
    **READY_FOR_REVIEW**. No Stage PASS, no product Gate0, no machine product acceptance and no human
    signature is declared or implied.

## Finding-by-finding mapping

Each row names the change, the regression check that covers it and the observation that shows the
reviewed counterexample no longer holds.

| Finding | Change | New regression check | Replayed observation |
|---|---|---|---|
| **M01** | The classification uses the stable base code, so a `:<path>` suffix no longer hides a storage failure. A storage failure sets `storage_unproven`, halts every later submission and keeps all sixteen rows. The terminal receipt counts itself inside the 8MiB / 128MiB / 256 bounds, reports the honest post-write totals (`receipt_bytes`, `artifact_files_including_receipt`, `artifact_bytes_including_receipt`) and refuses an impossible receipt as `TERMINAL_RECEIPT_NOT_PERSISTED` instead of truncating or overwriting. | `test_correction_m01_a_storage_failure_marks_unproven_and_stops_the_sends`, `test_correction_m01_the_error_classification_ignores_the_path_suffix`, `test_correction_m01_the_terminal_receipt_counts_inside_the_storage_bounds`, `test_correction_m01_a_receipt_over_the_total_budget_is_refused_explicitly` | `raw_persistence_failure`: 1 submission, 15 BLOCKED, `storage_unproven: true`. `receipt_total_cap`: `persisted: false`, accounted stays at the cap. |
| **M02** | The run root and the phase directory are pinned by inode identity; every ancestor between them and a target is checked for a redirect; the artifact and the receipt are written with `O_EXCL\|O_NOFOLLOW`; a preexisting phase directory is refused and nothing at all is written into it. | `test_correction_m02_an_ancestor_redirect_cannot_escape_the_owned_directory`, `test_correction_m02_a_preexisting_phase_directory_is_refused_without_writing`, `test_correction_m02_a_replaced_phase_directory_is_refused`, `test_correction_m02_a_replaced_run_root_is_refused`, `test_correction_m02_an_old_root_replay_is_refused` | `artifact_ancestor_redirect`: `escaped: false`, rejected. `existing_directory`: 16 BLOCKED rows, `files_written_into_the_old_root: []`, `receipt_persisted: false`. |
| **M03** | After the controlled callbacks the source and the owned root are re-verified immediately before the send, and the descriptor identity is compared with the path identity after the bounded read. A changed source produces zero sends and zero charges for that row and blocks the later rows. The code states that this is an in-process observation, not a universal filesystem race guarantee. | `test_correction_m03_a_source_replaced_in_a_callback_produces_zero_sends` | `source_mutation_in_authorize`: `sent: 0`, `public_submissions: 0`, first error `SOURCE_REPLACED`, 15 BLOCKED. |
| **M04** | An ordinary residue, read or cleanup exception no longer escapes the row. The release proof is still attempted, the original failure and the cleanup diagnostics are both kept, the unknown cleanup stops the later sends, and the phase still returns and persists the full sixteen row terminal receipt. | `test_correction_m04_an_ordinary_cleanup_exception_never_bypasses_the_release` | `residue_exception`: the phase returned a receipt, 16 rows, `cleanup_unproven: true`, cleanup diagnostics present, 1 submission, 15 BLOCKED. |
| **M05** | The public submission attempt is charged before the send, so a failed or unknown outcome stays charged and is never refunded or retried. `public_submissions_attempted` and `public_submissions_succeeded` are reported separately; the provider reservation never exceeds 34. | `test_correction_m05_a_failed_submit_stays_charged`, `test_correction_m05_the_provider_reservation_never_exceeds_thirty_four` | `failed_submit_counter`: `public_submissions: 1`, `public_submissions_succeeded: 0`, driver attempts 1. |
| **M06** | The reviewer and the session are only ever accepted as the exact pair the isolation receipt lists; a cross pair is rejected. The supplied identities stay a schema and binding check; genuine provenance stays parent evidence. | `test_correction_m06_a_cross_paired_reviewer_session_is_rejected`, `test_correction_m06_an_exact_reviewer_session_pair_is_accepted` | `cross_paired_reviewer_session`: rejected `QS_SCORE_REVIEWER_SESSION_PAIR_UNKNOWN`. |
| **M07** | The actual raw hash **and** the actual raw length are bound to both the execution record and the scoring record, and the safe path is applied to every applicable row. | `test_correction_m07_a_wrong_execution_raw_length_is_rejected` | `execution_raw_length_mismatch`: rejected `QS_RAW_ARTIFACT_LENGTH_MISMATCH`. |
| **M08** | Per the adjudication: an execution failure stays a quality FAIL in the fixed sixteen row denominator; the independently reviewed, verified raw of an unusable row still contributes its critical findings and is never erased; a known ordinary refusal or structure failure with verified raw and proven cleanup is resolved without being usable; the aggregate gate stays 8/10 + 5/6 + global critical zero with no extra all-technical-success prerequisite; an unknown source, storage, cleanup, missing raw or missing review can never pass. | `test_correction_m08_a_known_failed_row_keeps_its_critical_evidence`, `test_correction_m08_a_known_failed_row_with_zero_critical_may_resolve`, `test_correction_m08_an_unknown_failed_row_can_never_resolve`, `test_correction_m08_a_failed_row_without_proven_cleanup_cannot_resolve` | `failed_row_critical_evidence`: total critical 3, row FAIL and not usable, row resolved, aggregate false. `known_failed_independently_scored`: 9 images and 6 videos usable, total critical 0, row resolved but not usable, aggregate true. |
| **M09** | The exact raw evidence of a failed public execution is preserved: the production `BridgeError` serializes its raw response and the raw responses of the frames already analysed, and those envelopes and frame strings are kept independently of any parse success. The provider after evidence is taken **before** the persistence, so it exists even when the persistence or the parsing fails. The synthetic driver now serializes the real `BridgeError`, and the new tests drive the real owner failure rather than a mutated success UI. | `test_correction_m09_the_real_bridge_error_raw_response_is_preserved`, `test_correction_m09_the_real_video_frame_raws_are_preserved`, `test_correction_m09_the_provider_after_evidence_survives_a_persistence_failure` | the new checks assert the exact rejected envelope bytes, the prior frame raw strings and the surviving provider-after artifact. |
| **m01** | The release evidence must be finite: NaN, infinity and a boolean are rejected before a release can be proven. | `test_correction_m01_a_non_finite_release_is_rejected` | `nonfinite_release`: rejected `RELEASE_EVIDENCE_ELAPSED_INVALID`. |
| timing / admission | A late successful history now fails the deadline; the authorize, observation, persistence and release steps each have an explicit elapsed ceiling; and the phase refuses to start without a known parent capacity proof, because an unknown parent budget may never be assumed to be sufficient. The proof is an internal bounded input, not a ledger API, and the parent integration that produces it stays pending. The phase still never creates a model preload and never starts a service. | `test_correction_timing_a_late_successful_history_fails_the_deadline`, `test_correction_timing_a_slow_authorize_callback_is_bounded`, `test_correction_admission_an_unknown_parent_budget_is_refused`, `test_correction_admission_an_insufficient_parent_capacity_refuses_every_send` | — |

The replayed observations are observations of the correction, not passing tests: the review's defect
expectations were never turned into green cases, and the old expectation text was not edited.

## Actual checks and real exit codes

Every check was executed through the original immutable runner
(`reports/v0-s3/product-gate0/run_offline_checks.py`, reused without edits) except the replay, which
uses the new guarded runner in this directory. Both install their `sys.addaudithook` guard **before**
pytest or any product module is imported, disable plugin autoload, the cache provider and bytecode
writing, and block socket connect/bind/name resolution and every host process creation. The raw
stdout and stderr streams and the actual exit code are stored next to each other; the shell captured
the process exit code directly with no pipeline masking it.

| Run | Label | Exit | Result | Denominator | Evidence |
|---|---|---:|---|---|---|
| guard self-test | guard-selftest | 0 | 4 attempts, 4 blocked (connect/bind/Popen/system) | 4 | `guard-selftest.guard-selftest.json` |
| directed new regressions | correction-directed | 0 | 28 passed, 67 deselected | 28 | `correction-directed.stdout.log`, `correction-directed.receipt.json` |
| full suite on the final candidate | full-final | 0 | 95 passed | 95 | `full-final.stdout.log`, `full-final.receipt.json` |
| replayed review counterexamples | review-probe-replay | 0 | 13 observations, baseline plus 12 counterexamples | 13 | `review-probe-replay.stdout.log`, `review-probe-replay.receipt.json` |

The 39 + 28 directed duplicates of the original implementation were **not** re-run, and the P3A 121,
P2B 237 and full-project suites were not re-run, as the task requires. The 95-check full run includes
the 67 preserved checks and the 28 new regressions in one pass.

### Failed attempts during this round, retained honestly

The two interactive debugging rounds below were executed as
`python3 -B -m pytest tools/test_v0_s3_quality_phase.py -q -p no:cacheprovider 2>&1 | grep ...`.
Their **exit codes are UNKNOWN**: the pipeline masked the pytest exit status. They are not acceptance
evidence and are not counted as passing.

| Round | Exit | Observed | What it was |
|---|---:|---|---|
| 1 | UNKNOWN | 7 failed, 60 passed | The intentional behaviour changes had not yet been applied to the affected existing expectations: the parent budget proof was not yet a constructor argument, the cleanup diagnostic lost its stable base code, the deadline now fails a late history, and the reviewer/session pair and the failed-row reasons had changed. |
| 2 | UNKNOWN | 2 failed, 65 passed | The cleanup diagnostic still carried a `:QualityContractError` suffix, which changed the stable base code of two rows. |

Both rounds produced new evidence and located a different defect each time, so this is not the
prohibited two-same-route-repairs-without-evidence pattern. No failed run was rewritten or deleted.

A third correction was needed in the evidence itself: the first replay of the m01 counterexample did
not inject the non finite release evidence and therefore observed the unperturbed driver. The probe
script was corrected (`376ea92`), the observation was re-executed, and every check was then re-run so
that all evidence binds the final candidate. No evidence metadata was rebound without a rerun.

## Retained fixture state and cleanup

- The synthetic fixtures (ten generated 4x4 PNGs, six small synthetic video byte blobs, the
  synthetic provider log and the phase artifacts) live only in pytest's own temporary roots under
  `/tmp/pytest-of-administrator/` and in the replay's own bounded root, which the replay deletes
  itself before it exits. They are outside the repository and nothing binary is committed.
- **No cleanup is claimed as a product property.** The parent `OwnedArchive` owns the real raw
  archive and deletion; the pytest temporary retention is a harness fact.
- The repository contains no generated phase directory.
- The pre-existing untracked `__pycache__` directories were neither deleted nor committed.
- The replay's own fixture root is removed by the replay itself (`own_fixture_cleanup`), and its path
  is recorded in the observation document.

## Limits, and what this batch does NOT prove

- Offline only. No real ComfyUI, no real Ollama, no model, no GPU, no real media, no network, no
  download, no ledger mutation, no Windows/WSL/PowerShell, no host-exe hashing, no parser probe and
  no full checkpoint was executed.
- The native HTTP/provider boundary and the media bytes are synthetic. The suite proves the wiring,
  the refusals and the evidence binding; it proves **no** product quality result.
- The parent capacity proof the phase now demands is an internal bounded input. The parent
  integration that produces it — and the production `video_snapshot_residue` adapter — are still
  pending; until they exist no real run can be admitted.
- `public_video_oracle` still requires independent decoder recomputation of the frame bytes, and four
  sampled frames still cannot prove full motion continuity or physical camera movement. This phase
  does not score either.
- The quality set, the prelabels and the frozen projection are never read by the execution or the
  scoring module; the projection carries no label, caption or expected answer, and the five scoring
  dimensions remain embedded constants of the frozen rubric.
- A06 network enforcement, the product Gate0, the real finite sixteen-row run, the independent
  scoring pass on real raw artifacts, the independent review of this candidate and the human
  signature are all **not proven** here.
- No machine product acceptance, no independent review verdict, no Stage PASS and no human signature
  is produced or implied by this receipt.
