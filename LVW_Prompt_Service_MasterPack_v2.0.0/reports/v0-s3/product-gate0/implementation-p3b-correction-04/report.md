# P3B aggregate correction 04 — implementation receipt — READY_FOR_REVIEW

Candidate: `5de09478a4af6e3dd91410d4dde90c9020a77bfd` (final; binds every acceptance check below).
Root adjudication merged: `55a6bc005fb4e44c0ad7e5b937f786a1b5c05f14`
(`ROOT_P3B_CORRECTION04_AGGREGATE_DISPOSITION`,
`CHANGES_REQUIRED_FOUR_CODE_ROOT_CAUSES_AND_APPEND_ONLY_EVIDENCE_CORRECTION`,
0 fatal / 5 major / 1 minor).
Independent review merged: `0d5c023712651b20f3554ed4f0feb2b56b974bd6` (correction-03 review,
0 fatal / 5 major / 1 minor) with its findings, focused probes, supplement and context
observations.
Append-only historical erratum merged with the adjudication:
`reports/v0-s3/product-gate0/correction03-historical-execution-erratum.json`
(sha256 `8a7722ce5a078f6ec9d6415f67446badf27b19e2a1016d4ab5fef15cca89014d`).
Frozen contract: `reports/v0-s3/product-gate0/p3b-quality-contract.md`
(sha256 `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`).
Frozen input projection: `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`
(sha256 `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`).
Root adjudication file: `reports/v0-s3/product-gate0/p3b-correction-04.adjudication.json`
(sha256 `1aa132b565803c6caa873b7ee9f4be022eda76668bbd5680aa342243446d15dc`).

`contract_changes=none` — no public API, schema, quality threshold, denominator, prompt,
workflow, owner, package, P3A, authority, ledger, contract, quality set, prelabel, sample,
projection, coordinate, MANIFEST, frozen-packet file, old report, old log, old probe, old
checksum or old runner was modified. The scoring thresholds are exactly the frozen ones:
8 of 10 images, 5 of 6 videos, a per sample score of at least 8, zero global critical
hallucinations, the fixed sixteen row denominator, and no extra all-technical-success
requirement. The scope does include the new **internal** source-plan evidence that the root
adjudication froze; that is internal evidence, not a product scope change.

## Source of this candidate

| File | sha256 | role |
|---|---|---|
| `tools/v0_s3_quality_phase.py` | `db78f5314df765aa4b27efec4e0fb1f13faf8e47fdc516c55f4f3a6fe4b6973d` | QD execution phase + QS independent score recomputation |
| `tools/test_v0_s3_quality_phase.py` | `8469e072d92efc15110bd634f781878241a0bcc7b86925f3d840ec98d7c41751` | 175 offline checks (145 preserved + 30 new regressions) |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-04/run_guarded_checks.py` | see `SHA256SUMS` | guarded runner for every check in this batch |
| `reports/v0-s3/product-gate0/implementation-p3b-correction-04/replay_correction03_counterexamples.py` | see `SHA256SUMS` | one replay of the correction-03 counterexamples as observations |

The hashes above are the hashes of the **committed** candidate. The final acceptance run
records them again as the before and after hashes of the run and as the hash of the module
that was really imported (`full-final.receipt.json`), so the `--candidate-sha` argument is
never the attestation.

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

Copied unchanged from `plans/execution-control.json` `development_outline`. **No completion
count was advanced.** V0-S3 stays 0/6: this is offline wiring only.

## Ten required fields

1. 当前坐标: R1 / WP-R1-U3 / `S3_P3B_QUALITY_INTEGRATION_IMPLEMENTATION`; this batch is the
   fourth aggregate correction of S3-P3B under the frozen internal contract, the
   correction-03 independent review and the root correction-04 adjudication.
2. 本批完成: the four remaining code root causes — M01 the public consumer loads the
   actually published canonical evidence, M08 the original source identity is sealed and the
   bound context is typed, NM01 every controlled driver value is resolved before the final
   guard and NM02 one final latest clock sample decides both the deadline and the parent
   interval — fixed together in one round. The findings the correction-03 review closed stay
   closed and all of their obligations are retained. The original 145 checks are preserved and
   pass; 30 new regression cases were added, 175 in total. The correction-03 counterexamples
   were replayed once as observations. Implementation self-check only; independent review
   pending; no machine product acceptance and no human signature is claimed.
3. 最后通过门禁: unchanged `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, scoped existing human acceptance.
4. 当前阻塞门禁: `S3_QUALITY_EXECUTOR_A06_COORDINATOR_AND_GATE0_PENDING`, and additionally the
   mandatory parent hard process supervision, which this batch records as
   `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`.
5. 全局路线位置: corrected offline quality integration → independent verification of this
   candidate → root gate decision → frozen complete product Gate0 → bounded same-source real
   run → independent scoring → necessary human/release gates.
6. 剩余工作: independent isolated review of candidate `5de0947`; the thin parent coordinator
   with the enforceable process watchdog and the owned cleanup; the parent integration that
   produces the typed capacity proof and the authentic provider debit; the production
   `video_snapshot_residue` adapter; A06 network enforcement; the real finite sixteen-row run;
   the independent scoring pass on the real raw artifacts; the product Gate0 and the required
   human signature.
7. 下一责任人: separate independent reviewer instance, then root (Codex) as architecture and
   gate owner.
8. 所需授权: none additional for the completed offline scope. No real service, model, media,
   GPU, network, download, ledger, Windows/WSL/PowerShell, parser or host-exe hashing action
   was performed, and nothing here authorizes one.
9. 证据目录: `reports/v0-s3/product-gate0/implementation-p3b-correction-04/` (receipt.json,
   report.md, SHA256SUMS, the guarded check receipts with their raw stdout and stderr, the
   guard self-test, the replayed correction-03 observations and the retained editing
   diagnostics).
10. 精确停止原因: the frozen QD + QS contract and all four accepted code root causes are
    implemented, the 175-check suite is green with its real exit code, and the correction-03
    counterexamples were replayed as observations. The implementer stops at
    **READY_FOR_REVIEW**. No Stage PASS, no product Gate0, no machine product acceptance and
    no human signature is declared or implied, and this batch does not claim that the hard
    full-phase timing is closed.

## Finding-by-finding mapping

Each row names the public path, the check, the oracle, the negative case, the terminal
behaviour and the cleanup.

| Finding | Public path | Change | Check | Oracle | Negative case | Terminal behaviour | Cleanup |
|---|---|---|---|---|---|---|---|
| **M01** | `tools/v0_s3_quality_phase.py` → `recompute_scores` → `load_published_execution_receipt` → `load_canonical_receipt` | The public scorer no longer trusts the publication booleans of the supplied dictionary. It loads the real canonical document from the real artifact root with a bounded, redirect-rejecting loader that reads at most 8MiB + 1 byte, verifies the actual `<run root>/temp/s3-quality` location and the run-root binding, and refuses a missing, corrupt, staged-only, foreign or redirected document. The supplied execution content must reproduce the published document field by field (`_verify_execution_content`). | `test_correction04_m01_a_missing_canonical_receipt_fails_closed`, `…_a_corrupt_canonical_receipt_fails_closed`, `…_a_foreign_canonical_receipt_fails_closed`, `…_a_staged_only_receipt_is_not_authority`, `…_a_redirected_artifact_root_is_refused`, `…_an_oversized_canonical_receipt_is_refused`, `…_the_supplied_execution_content_must_be_the_published_one`, `…_a_forged_provider_counter_is_refused`, `…_a_forged_verdict_can_only_be_stricter`, `…_the_published_receipt_is_the_only_authority` | the real public `recompute_scores` over a genuine `QualityPhase.run()` | `missing_canonical_retained_stage` → `CANONICAL_RECEIPT_ABSENT`; `corrupt_canonical` → `CANONICAL_RECEIPT_UNREADABLE`; `foreign_canonical` → `QS_EXECUTION_RECEIPT_BINDING_MISMATCH:run_id`; a forged provider counter → `QS_EXECUTION_CONTENT_MISMATCH` | the consumer refuses the whole verdict; it never returns an aggregate from favourable in-memory flags | every negative case owns its own run root and removes it; the shared fixture of the other checks is never touched |
| **M08** | `tools/v0_s3_quality_phase.py` → `QualityPhase._persist_source_plan` → `validate_source_evidence(sealed=…)` → `load_source_plan` → `_row_evidence_complete` | After the initial bounded sixteen-source validation and **before the first public send**, an exclusive, bounded, ordered source-plan artifact is persisted under the owned artifact root. It binds the run, the candidate, the child authorization and the projection and records every source's asset, ordinal, kind, reference, hash, byte count and original five-component descriptor identity; its actual path, hash and byte count are bound into the canonical receipt. The shared source validator now really runs inside the execution phase, the bound run root and the bound baseline are mandatory typed contexts, and the scoring compares every row's evidence identity, size, hash and path with the seal. | `test_correction04_m08_the_source_plan_seals_all_sixteen_original_identities`, `…_a_changed_source_identity_is_unknown_in_the_scoring`, `…_a_changed_source_size_is_unknown_in_the_scoring`, `…_a_changed_source_hash_is_unknown_in_the_scoring`, `…_a_changed_source_path_is_unknown_in_the_scoring`, `…_a_tampered_source_plan_is_refused`, `…_a_missing_source_plan_is_refused`, `…_a_replayed_source_plan_is_refused`, `…_a_source_plan_from_another_run_is_refused`, `…_the_source_media_need_not_stay_on_disk`, `…_a_source_plan_failure_produces_zero_sends`, `…_the_bound_context_must_be_typed`, `…_the_execution_uses_the_same_shared_validators` | the public scorer over a genuine run; the shared validators are traced (`shared_validator_calls`: QD source 48, QD release 16, QS source 32, QS release 32) | identity → `SOURCE_SEAL_IDENTITY_MISMATCH`; size → `SOURCE_SEAL_BYTES_MISMATCH`; hash → `SOURCE_SEAL_HASH_MISMATCH`; path → `SOURCE_SEAL_PATH_MISMATCH`; tampered seal → `QS_SOURCE_PLAN_HASH_MISMATCH`; missing seal → `QS_SOURCE_PLAN_MISSING`; replayed seal → `QS_SOURCE_PLAN_HASH_MISMATCH`; a seal of another run → `QS_SOURCE_PLAN_BINDING_MISMATCH`; a float, boolean, string, negative or absent baseline → `RELEASE_EVIDENCE_BASELINE_INVALID`; an absent, null or non-string run root → `SOURCE_RUN_ROOT_INVALID` | a seal that cannot be persisted is a storage failure: **zero sends** and all sixteen rows terminal (`BLOCKED`, `storage_unproven: true`); a row whose evidence does not reproduce the seal is unknown and can never be usable or resolved, so the aggregate never passes | the seal is one more retained artifact of the batch and is counted honestly in the frozen 8MiB / 128MiB / 256 bounds; the live source media may be deleted or archived afterwards and the scoring still closes |
| **NM01** | `tools/v0_s3_quality_phase.py` → `QualityPhase._resolve_driver_state` → `QualityPhase._send_admission_guard` → `QualityPhase._execute_row` | The public submission counter, the public submission limit and the submit callable are read and bound **before** the final guard. Between the guard and the send there is no `getattr`, no property access, no authorize, no observer and no clock read; the reservation, the attempt charge and the cached submit follow immediately, with no refund and no retry. The admitted capacity is re-validated and may never exceed the frozen 34. | `test_correction04_nm01_a_diminishing_limit_accessor_refuses_every_send`, `…_an_advancing_clock_accessor_refuses_every_send`, `…_a_diminishing_submit_binding_refuses_every_send`, `…_the_driver_state_is_resolved_before_the_final_guard` | a conforming driver whose public limit and submit callable are observable properties with side effects | the limit accessor diminishes the admitted capacity → `PARENT_BUDGET_CAPACITY_INSUFFICIENT`; the accessor advances the clock to 10801 → `PHASE_DEADLINE_EXCEEDED`; the submit binding diminishes the capacity → the same refusal, with `submit_calls == 0` | **zero sends**, all sixteen rows `BLOCKED`, the earlier attempts and charges are preserved | the property callbacks are the fixture's own; no real driver, service or process is involved |
| **NM02** | `tools/v0_s3_quality_phase.py` → `QualityPhase._send_admission_guard` → `QualityPhase._parent_proof_is_fresh(now=…)` | The guard takes exactly **one** final latest trusted monotonic sample and uses it for the 10800s phase deadline and for the parent proof interval together. `_parent_proof_is_fresh` never reads the clock again when the caller already has the sample, so the second-clock-crossing counterexample no longer has a mechanism. | `test_correction04_nm02_the_guard_reads_the_clock_exactly_one`, `test_correction04_nm02_the_phase_boundary_is_exact_and_one_over`, `test_correction04_nm02_the_hard_supervision_blocker_is_still_recorded` | the real public run with a deterministic clock; the guard's clock readings are counted | the correction-03 counterexample that advanced the clock from inside `_parent_proof_is_fresh` no longer fires at all (`final_guard_second_clock_crosses_phase_deadline`: the clock never moves, `clock_now: 0.0`, and the run is the legitimate 16/16) | exactly 10800 is accepted, 10801 is refused with `PHASE_DEADLINE_EXCEEDED` and all sixteen rows refused; a later expiry still preserves the earlier charged attempts | the cooperative guard is not a preemption of a synchronous callback; the mandatory parent watchdog stays `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER` |

## Old and new assertion coverage audit

No failing assertion was erased and no check was deleted. The following existing
expectations changed, each for a stated reason, and each replacement keeps or strengthens the
original obligation:

| Existing check | Old expectation | New expectation | Why |
|---|---|---|---|
| `test_the_artifact_budget_is_exact_and_one_over` | the file ceiling was `7`, the first row fits and the second row is refused | the file ceiling is `8`, the first row fits and the second row is refused | The sealed source plan is one more retained artifact of the batch, so the exact ceiling is one file higher. The exact and the one-over behaviour, the single public submission and the fifteen blocked rows are asserted exactly as before. |
| `test_correction02_m02_a_temp_ancestor_redirect_writes_nothing_into_the_old_root` | the file set below the renamed ancestor was empty | the file set below the renamed ancestor is **the same before and after the redirect** | The sealed source plan was written through the legitimate owned handle *before* the redirect. The new assertion is the precise statement of the original obligation — nothing was written *through* the renamed ancestor — and it is strictly stronger than an empty-set check, because it compares the exact file set before and after. The "no receipt was persisted" obligation is unchanged. |

All other 143 original checks are byte-identical in their assertions; the 30 new cases only
add coverage. The known-failure semantics are preserved: a known ordinary failure with
complete evidence still resolves without being usable, an independently verified critical
count of 3 is still visible in the global total and still fails the aggregate, and the
frozen thresholds are unchanged.

## Actual checks and real exit codes

Every acceptance check was executed through one guarded runner whose `sys.addaudithook` guard
is installed **before** pytest and before any product module is imported. Plugin autoload,
the cache provider and bytecode writing are disabled, and socket connect/bind/name
resolution and every host process creation are blocked. The raw stdout and stderr bytes are
captured at the file-descriptor level and the true process exit code is stored next to them;
the shell captured the process exit code directly with no pipeline masking it.

| Run | Label | Exit | Result | Denominator | Evidence |
|---|---|---:|---|---:|---|
| guard self-test | guard-selftest | 0 | 4 attempts, 4 blocked (connect/bind/Popen/system) | 4 | `guard-selftest.stdout.log`, `guard-selftest.receipt.json` |
| the combined suite on the committed final candidate | full-final | 0 | 175 passed | 175 | `full-final.stdout.log`, `full-final.receipt.json` |
| the replayed correction-03 counterexamples | replay-correction03-counterexamples | 0 | 29 observations | 29 | `replay-observations.json`, `replay-correction03-counterexamples.receipt.json` |

The final suite ran **once** on the committed candidate `5de0947`, and the guard self-test
ran **once**. `full-final.receipt.json` records the before and after hashes of both bound
source files, the actual imported module path and hash of `tools.v0_s3_quality_phase` and of
the test module, the 175 collected node ids, the raw stream hashes and byte counts, the true
exit code and the removal of the owned fixture root. The replay receipt records the same
before/after source hashes and the same imported module hashes, so the replay is bound to the
committed candidate by source hash rather than by a `--candidate-sha` argument.

### The retained editing diagnostics

The focused `--select` regressions that were used while editing are retained with their real
exits, including the ones that failed. No failure was repaired by a cosmetic rerun.

| Label | Exit | Collected | Purpose |
|---|---:|---:|---|
| edit-01 | 0 | 1 | first focused check of the new consumer wiring |
| edit-02 | 0 | 67 | the QS and evidence groups |
| edit-03 | 1 | 17 | the admission, timing and budget groups — **failed**: the artifact file ceiling |
| edit-04 | 0 | 20 | the same groups after the ceiling was adapted |
| edit-05 | 1 | 86 | the execution groups — **failed**: the ancestor redirect expectation |
| edit-06 | 0 | 18 | the ownership and publication groups after the expectation was adapted |
| edit-07 | 1 | 27 | the first run of the new correction-04 checks — **failed**: four fixture defects in the new checks |
| edit-08 | 1 | 30 | the new checks — **failed**: the submit binding fixture |
| edit-09 | 0 | 30 | the new checks after the fixtures were corrected |
| edit-10 | 0 | 80 | the evidence groups after the seal comparison was reordered |
| edit-11 | 0 | 114 | the execution, ownership, admission, timing and budget groups |

The full 175-check suite was **not** run while editing; only the focused selections above
were used.

### Guard compliance, and the two historical findings

* The current batch's scope: every run in this batch installed the audit hook **before**
  pytest and before any product import, with plugin autoload, the cache provider and
  bytecode writing disabled, and it recorded the raw streams, the true exit and the removed
  owned root. This is the *observed scope of this batch only*.
* **E01 is accepted as written.** The historical ten piped pytest rounds and two ad-hoc debug
  imports of the correction-03 batch have **unknown** exits, and the absence of forbidden
  external actions in those twelve attempts is **NOT_PROVEN**. Nothing in this batch
  re-certifies them, nothing in this batch repeats the "zero external action" claim for them,
  and the old report was not modified. The fourteen guarded edit attempts of that batch stay
  separate runs and are not replacements for the historical twelve.
* **E02 is accepted as written.** The correction-03 replay really has 22 unique observations
  and the earlier replay 21; the earlier focused 18 and the final gap 4 are separate. This
  batch replays the *relevant* counterexample subset once — 29 observations — and does not
  repeat the broad matrix, the full suite or the P3A 121 / P2B 237 sets.
* The `actual_*` cap labels of the earlier replays reduced the configured limits; they never
  proved the actual frozen 8MiB / 128MiB / 256 limits, and nothing here claims otherwise. The
  real caps remain proven by the independent correction-03 review's six real-cap
  observations, which this batch did not repeat.

### Evidence staging note

The evidence is text only: JSON receipts, Markdown, plain logs and the two runner scripts.
No binary media, no database, no archive and no copied source is in the repository. The only
fixtures that exist at runtime are the synthetic 4x4 PNG images and the tiny synthetic video
bytes that the existing test module already creates behind the real production nodes, the
real `BridgeOwner` and the public oracles; they are created inside the pytest temporary root
and removed with it.

## Retained fixture state and cleanup

Every run owns exactly one temporary root (`lvw-c04-<label>-*`), which the runner creates and
removes in its own `finally` block; the receipts record `owned_root_removed: true`. The
replay owns exactly one root (`lvw-c04-replay-*`) and removes it in its own `finally` block;
`replay-observations.json` records `removed: true`. No earlier root, no shared fixture
directory and no earlier evidence directory was modified or removed. The destructive negative
cases (removed, corrupted, replaced canonical receipt and seal) each ran in a private root of
their own and never touched the shared `completed_run` fixture of the other checks.

## Limits, and what this batch does NOT prove

* The **parent hard process supervision is still `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`.** The
  cooperative guard is a pre-send check, not a preemption of a synchronous callback that never
  returns. No new ledger API, thread or worker platform was added.
* **A consistent forgery of the published canonical receipt *and* of the seal is beyond this
  offline component.** There is no signature: the seal is bound into the canonical receipt
  and the receipt into the artifact root, so an attacker who rewrites *both* consistently
  still produces a self-consistent pair. What this batch does prove is that a changed
  dictionary, arbitrary disk data, a removed, corrupt, foreign or staged-only canonical
  receipt, and a changed source identity cannot produce an aggregate pass. The independent
  reviewer and the parent archive remain the authority for the real media.
* The supplied verdict fields can only make a row **stricter** than the published document.
  The one preserved exception is the frozen 145 obligation that a supplied known-failure
  error code may resolve a row the published document recorded as a pass; that can never
  create a usable row and never lowers the eight-image, five-video or zero-critical
  thresholds.
* The scoring consumer must be given the artifact root of the run it scores: a copy of the
  tree at a different path is refused with `QS_CANONICAL_RECEIPT_RUN_ROOT_MISMATCH`, because
  the location binding is part of the proof.
* **Not proven and not claimed by this batch:** the parent supervision, the native
  residue/admission integration, the A06 enforcement and attempt observation, the real
  quality run and the full twelve, the product Gate0, the human signature and the release
  signature. No real Windows, WSL, PowerShell, parser, host-exe hashing, real media,
  FFmpeg, model, GPU, service, network, download or real ledger action was performed.
