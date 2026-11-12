# Independent S3-P3B QD/QS review

**F0 / M9 / m1 — CHANGES_REQUIRED for the offline component.** All67 existing checks pass, but independent counterexamples prevent acceptance. No candidate, test, frozen contract, prelabel, quality-set or historical evidence was edited. Author: ljx418 <1173696783@qq.com>.

Candidate `cea5bf328ea35a5aa1d1feb51ac3ef8946a964fa`; evidence `e0e54a4b889050de218d483a36532cec9127dd0a`; authority `35f1ee4df74e3a6054e021ee9cbbd066eaba5490`. Initial status was clean. Requested merge --no-edit fast-forwarded53a8ac8 to e0e54a4; no reset. Root coordinate215c60f was read with Git, not merged. Governance/AGENTS/routing, production-quality packet (all files), p3b contract, docs24/30–32, docs06 and original production owners govern. Full quality prelabels, testSource and human holdouts were not read.

## Actual execution and assurance

| Run (each once) | Actual result | Exit |
|---|---|---:|
| Required full file |67 collected,67 passed,0 failed,0 skipped,0 deselected;7.39s|0|
| Guard selftest |4 attempts,4 blocked: connect/bind/Popen/system|0|
| Independent probes |12 observations, including baseline and11 adversarial observations; defect observations are not product PASS|0|
| Additional boundary observations |4 groups: actual8MiB/128MiB/256-file limits and existing-directory replay|0|
| Read-only Git/hash audit |5 file bindings match,6 Git commands exit0|0|

No duplicate39+28 directed runs, P3A121, P2B237 or full-project run. The existing suite's historical directed counts are39 passed/28 deselected and28 passed/39 deselected (not skipped); independent combined coverage includes them once. Commands, stdout/stderr, actual exits and hashes are adjacent. Synthetic probe baseline is16/16 execution,16 submissions/34 provider calls; it is not semantic quality evidence.

`audit_runner.py` loads the independently inspected immutable implementation runner via runpy before importing pytest or product modules. The audit hook blocks Python socket connect/bind/DNS, subprocess.Popen, system, exec/spawn/posix_spawn/fork/forkpty. Plugin autoload, cache and bytecode are off; wrapper clears external pytest options/plugins. The four selftests demonstrate those four boundaries only. This is a Python audit guard, not an OS-wide sandbox or a proof against arbitrary native extensions/direct syscalls; no actual Windows/WSL/PowerShell/Parser/spawned host process, service/model/GPU/real media/network/download/ledger/old runtime/claims/full checkpoint operation was performed. Git binding audit is separate read-only repository access. Shell orchestration and Python/Git are the authorized local tooling, not product actions.

All fixtures are new4x4 PNGs and small synthetic video bytes. Main suite owns `/tmp/lvw-independent-p3b-139573-suite`; other unique roots are recorded by probes and deleted by those probes. Cleanup registry records only this review's own roots; original pytest roots were neither scanned nor deleted. No binary/DB/ZIP/copied source is committed. Test cleanup is not production OwnedArchive proof.

## Aggregate findings

### M01 — Major

Location: `tools/v0_s3_quality_phase.py:549-581, 808-827, 1101-1133`. Trigger: Artifact write fails with the production error suffix :rows/...; receipt follows a full total-byte allowance.

Expected: Storage UNPROVEN, stop subsequent sends, retain all 16 rows; include receipt in total/file limits.

Actual: HALT_ERROR_CODES compares whole strings, whereas write/size/replay errors append paths. Injected raw-write failure sends all16/reserves34 with zero raw preserved and no storage_unproven. _write_receipt never checks total bytes: a counter at134217728 accepts76 additional bytes; receipt counters also describe pre-receipt totals.

Evidence: probes.stdout.log:raw_persistence_failure,receipt_total_cap; boundaries.stdout.log.

### M02 — Major

Location: `tools/v0_s3_quality_phase.py:549-581, 1101-1162`. Trigger: rows ancestor is a symlink while immediate target parent does not yet exist; or phase directory already exists.

Expected: Every artifact/receipt confined to the original owned phase directory; reject replay without writing into old roots.

Actual: _artifact checks only immediate parent and target. rows/asset/raw.txt writes through a rows symlink to a sibling target. Existing directory rejection still invokes _finish and creates qd-receipt.json there if absent; receipt open has no equivalent ancestor guard. Constructor resolves root without retaining original inode identity.

Evidence: probes.stdout.log:artifact_ancestor_redirect; boundaries.stdout.log:existing_directory; static receipt path.

### M03 — Major

Location: `tools/v0_s3_quality_phase.py:739-771`. Trigger: quality_public_submit authorize callback replaces source after _validate_source.

Expected: Revalidate source/root identity after controlled callbacks and before sending; changed source must not be sent.

Actual: Callback replaces the first PNG with another 4x4 generated PNG. All16 sends occur; only later output metadata detects first-row mismatch. _validate_source closes descriptor before callback and performs no final path identity check after read.

Evidence: probes.stdout.log:source_mutation_in_authorize.

### M04 — Major

Location: `tools/v0_s3_quality_phase.py:830-856, 1210-1248`. Trigger: video_snapshot_residue raises ordinary OSError rather than QualityContractError.

Expected: Unknown cleanup stops sends and returns/persists all16 terminal rows; release still attempted.

Actual: Exception escapes the first finally handler before release_evidence; run raises after one submission, phase.receipt remains null, and no full16 terminal receipt is produced.

Evidence: probes.stdout.log:residue_exception.

### M05 — Major

Location: `tools/v0_s3_quality_phase.py:767-773, 1064; tools/v0_s2_driver.py:381-395`. Trigger: Public submit reserves a driver attempt then raises (failed/unknown HTTP outcome).

Expected: Attempt count must stay charged, never report zero for a permitted attempted send.

Actual: Driver attempt=1, provider reserved=1, phase public_submissions=0 because increment follows successful return. Later rows halt correctly, but the public receipt understates attempted sends. Existing S2 driver correctly precharges, so phase should preserve that distinction.

Evidence: probes.stdout.log:failed_submit_counter.

### M06 — Major

Location: `tools/v0_s3_quality_phase.py:1286-1339, 1403-1433`. Trigger: Independent receipt lists A/SA and B/SB; score claims A/SB.

Expected: Validate exact reviewer/session pairs.

Actual: Separate membership sets accept cross-pair A/SB and aggregate_pass=true for all16. This is a schema/binding failure independent of real identity attestation.

Evidence: probes.stdout.log:cross_paired_reviewer_session.

### M07 — Major

Location: `tools/v0_s3_quality_phase.py:1471-1484`. Trigger: QD raw_bytes changed from244 to367 while actual bytes and score length remain244.

Expected: Recompute actual hash AND byte length against both bound execution and scoring records.

Actual: Aggregate remains true; execution row raw_bytes is never checked. Optional score raw_bytes does not substitute QD length binding.

Evidence: probes.stdout.log:execution_raw_length_mismatch.

### M08 — Major

Location: `tools/v0_s3_quality_phase.py:1452-1462, 1504-1523`. Trigger: Technically failed row still has independently reviewed actual raw and critical_hallucinations=3.

Expected: Keep failed row unusable, retain/validate its independent critical evidence; do not erase global critical evidence.

Actual: Immediate execution!=PASS continue discards score/raw verification and reports total critical0/knownfalse instead of the supplied3. Aggregate is false (no demonstrated false aggregate PASS). A known failed row with verified raw and zero critical also forces unresolved and aggregatefalse despite9/10+6/6 usable. Root must adjudicate this extra all-technical-success prerequisite against docs06 and original frozen quality rules; this review makes no scoring policy edits.

Evidence: probes.stdout.log:failed_row_critical_evidence,known_failed_independently_scored; docs/06_ACCEPTANCE.md business scoring; p3b contract QS.

### M09 — Major

Location: `tools/v0_s3_quality_phase.py:784-790, 886-908, 937-942; bridge/core.py:381-399,515-522; bridge/nodes.py:50-53`. Trigger: Real BridgeOwner rejects provider JSON/refusal before public UI text exists, or video raw shape parsing fails in persistence.

Expected: Persist available exact raw failure envelopes and full before/after provider evidence independently of parsing success.

Actual: BridgeError carries raw_response/prior_frame_raw_responses in its serialized history exception; QD only extracts outputs[node].text, so failure history is stored but separate original raw/frames are not extracted. _persist_row can raise before after-snapshot, leaving provider_after absent and observed calls0 despite attempted calls. Existing bad-raw tests mutate successful UI output, and SyntheticDriver catches BridgeError into a code-only message, so they do not exercise real error-detail preservation.

Evidence: Static production chain: core.BridgeError.__str__,call_one_frame,analyze_video; QD _persist_row/_execute_row; test SyntheticDriver.submit:264-270 and faults:296ff.

### m01 — Minor

Location: `tools/v0_s3_quality_phase.py:659-678`. Trigger: Release elapsed or monotonic sample is NaN.

Expected: Reject non-finite numeric evidence before declaring release proven.

Actual: _release_evidence accepts NaN due to comparison semantics. This helper probe does not establish whole-run success: canonical JSON allow_nan=False would later reject persisted NaN elapsed. Still, intermediate cleanup validation is weaker than existing finite-number oracle.

Evidence: probes.stdout.log:nonfinite_release.

## Production-chain and coverage audit

- **Input/model separation:** exact projection bytes/hash checked; strict row key set,16 ordered rows/10image+6video, unique IDs/source hashes/aliases, source size/hash bounded1MiB chunks plus one-byte growth check, no full quality-set/prelabel import. All-source prevalidation precedes first submission. Workflow bytes are compared with caller source_identity; candidate and child authorization strings are bound. Top-level denominator keys are not strictly closed and numeric10.0 can compare equal10, a structural gap masked by a trusted exact frozen projection hash; no model-label leak demonstrated.
- **Actual endpoint and graph:** NativeRuntime inherits S2SystemDriver.submit, which precharges and POSTs base.COMFY_URL `/prompt`; quality history uses the same imported base URL,8191. Image graph preserves ControlledImageInput→ImagePromptBridge and adds the existing CumulativePhase manual metadata observation node; video uses original VideoPromptOwner. Actual graph/prompt ID/status equality, unique prompt IDs, model gemma4:26b/mode realistic/empty user instruction/120s checked. Real ControlledImageOwner, image/video node classes, BridgeOwner and PromptSpec/public_video_oracle execute in the synthetic suite. The synthetic video owner fabricates decoder/source-frame manifests; this is neither real VideoOwner snapshot cleanup nor real Comfy scheduling/HTTP proof.
- **Profiles/resources:** parent still owns frozen profile/model digest, child authority, runtime installation, process lineage, GPU resource worker and archive. Existing observer is called through snapshots and HTTP; existing release_preload performs owned Ollama PID/birth comparison, unload, inventory and three physical baseline samples. No replacement private inference or release marker path is added. Quality constructor validates only a subset of binding (candidate/auth/PID/birth/nonnegative baseline), not model digest/profile or full runtime child identity; production admission remains a required parent-bound integration proof. Same8191 is source-verified, not live-verified.
- **Missing production adapter:** NativeRuntime has no video_snapshot_residue; phase constructor requires a parent adapter and rejects unadapted runtime. This remains explicit integration limitation, not an invented existing runtime method or production-wiring acceptance. The tests' fake accessor does not close it.
- **Evidence/actions:** full history record and original raw UTF8/suggestion/metadata/frame raws are separate on successful outputs. Before/after logs are persisted and count recomputed with existing count; prefix rewriting, ID reuse, graph/source metadata faults and wrong1/4 calls are rejected by suite. Raw is saved before suggestion/schema validation when UI output exists. M01/M04/M09 expose failure-path gaps. Reservations charge expected1/4 before attempt and no retry/refund occurs; M05 distinguishes local reported submissions from true driver reservation. Observed0 is not proof of zero actions when evidence is unknown.
- **Finite time:**600s/sample,10800s/phase,6000 polls and interval are encoded and timeout/phase-stop tests pass. _await_history checks the clock after the HTTP response and only when history is absent; a late successful response can be accepted without a post-response deadline check. Finite upper bound is therefore not exhaustively established (including time spent in authorize/persistence/release). Before first send there is no phase-level check that parent capacity covers the entire34 actions; actual authority remains external. These are remaining timing/admission coverage gaps, not permission to retry or expand budget.
- **Bounds and persistence:** direct independent actual byte/file probes confirm _artifact accepts8MiB, total128MiB,256 files and rejects each one-over. They do not validate receipt accounting or send-stop behavior; M01/M02 show those defects. Source read limits20MiB/256MiB are statically enforced, but no actual256MiB source was created. Existing small-file growth and hash/symlink negatives pass. Root/path replacement after callbacks is not proved safe (M03).
- **QS:** strict five0..2 integer dimensions and nonnegative integer critical count reject bool; thresholds8/10images,5/6videos,critical0 encoded; no model or keyword self-scoring.16 rows remain in denominator and missing/failed rows stay unusable. Actual raw path and SHA are checked for successful rows, but M06/M07/M08 remain. Isolation booleans and identity strings only validate a supplied schema; no trust-bound launch/role attestation is verified here. Real independent provenance must come from coordinator/session evidence, not verify_independence's docstring assertion. Projection/source identity binding relies on authentic QD receipt; QS does not re-read the frozen projection itself.

M08's all_rows_resolved/critical_known currently imposes all technical rows PASS, beyond merely8/10+5/6 usable. The root scoring-reviewpoint delivery was UNPROVEN under WSL transport failure; it is not evidence of implementer receipt or a contract amendment. Root should adjudicate known failed-but-raw-available rows using docs06 and frozen quality-set rules. Genuine unknown source/persistence/missing review must never pass. Critical evidence on any unusable row must remain visible regardless of that decision. No suggested policy change here rescues failed rows into usable rows.

## Evidence rebind and history

`binding-results.json` confirms current source/test/runner bytes against final Git candidate and implementation receipt; contract/projection also match frozen authority. Projection SHA47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3; QD/QS source SHA7211f23d4fe2dc7f840c13ba0a9db1535c78f480b4f39bf0cbeadd50f23b2c26; test SHA372555acfcef7b55bbd00dbb6edb6ad16e796a7e25c3a0dfb408a1fbeea28c48; implementation runner SHAd1261c15c58d6b5e5bd16b7e5a683112d2746a09f432ade836022078dda183f6. All three implementation raw stream hashes/lengths and final candidate strings match receipts.

cea5bf3 removes only unused tempfile import. e0e54a4 changes receipt binding and raw timing (combined8.04→7.96s), plus associated hashes; source behavior stays unchanged. This is consistent with reported fresh checks, not merely a candidate-string edit. Git preserves both versions. Local log text alone cannot cryptographically prove when commands ran, so no fraud or independently attested implementation rerun is inferred; this review's fresh67 check binds actual final source. The stale667da62 report paragraph is nonblocking navigation, not reason for another rerun. Earlier four diagnostics remain exit UNKNOWN with truncated streams/no pre-pytest guard, never retroactively certified or counted. No original failures were rewritten.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_IMPLEMENTATION / PREPARING_NEXT_STAGE from215c60f.
2. 本批完成: independent read-only review;67 existing checks pass,4 guard attempts blocked,16 independent observation groups; F0/M9/m1, offline CHANGES_REQUIRED. Implementation remains supplied READY_FOR_REVIEW, not accepted.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW,621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped human acceptance only.
4. 当前阻塞门禁: S3_QUALITY_EXECUTOR_A06_COORDINATOR_AND_GATE0_PENDING; this report adds concrete offline findings, no coordinate mutation.
5. 全局路线位置: root adjudication → one aggregate authorized correction → independent verification → remaining production coordinator/A06/Gate0 → bounded same-source quality16/cumulative execution → independent scoring → necessary human/release gates.
6. 剩余工作: all9 Major findings,1 Minor and listed coverage/integration gaps; actual quality16, A06/network/rollback/full12/productGate0/human/release all NOT_PROVEN by this review.
7. 下一责任人: root architecture/gate owner for aggregate disposition and scoring ambiguity; authorized implementation owner for any correction, separate reviewer afterward.
8. 所需授权: none additional for completed offline task; no real-run authorization inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3b/, report/receipt/findings/probes/raw commands/hashes.
10. 精确停止原因: assigned independent review complete with actionable defects; candidate untouched, return once to coordinator and retain visible window.

## Complete unchanged V0–V3 outline

Extracted from root215c60f, not advanced by this review. Current product coordinate R1; S3 quality work is offline preparation. Full original substeps and statuses are in coordinate.json.

| Delivery | Stage | Done/total | Implementation | Machine | Independent | Human | Boundary |
|---|---|---:|---|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|已签仅V0-Min|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|仅R1a前置单图子集可确认；不把完整视频/Q01算通过|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|已签仅单图切片；完整V1未完成|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain.|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|已有设计，未完成正式交付；存在代码需进入时复用审计|

Review procedure note: setup briefly created and immediately removed an empty `reports/v0-s3/product-gate0/independent-p3b-tmp.txt` outside the allowed new subtree; no candidate or historical bytes changed. This is disclosed as a reviewer scope deviation, not candidate behavior. Actual outer command lines are in commands.json; implementation receipt command arrays are reconstructed by its runner. Production owner/workflow Git bindings and all10 packet checksum entries also match (production-bindings.json).

Evidence capture correction: initial candidate-change/rebind-diff commands used cwd-relative pathspecs and returned empty exit0 streams; preserved as failed evidence selection, not substantive proof. Corrected top-anchored commands and full raw diffs are candidate-change-top/rebind-diff-top logs with git-pathspec-correction.json. No acceptance test was repeated.
