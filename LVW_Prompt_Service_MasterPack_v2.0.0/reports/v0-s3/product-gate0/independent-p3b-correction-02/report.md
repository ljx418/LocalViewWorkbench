# Independent P3B correction02 review

Candidate `9ed09513eac35636175b24a514b05d9d0c180717`; evidence `18c950e6e3497c425ddb11fcbb85b75da4ded4b1`. **CHANGES_REQUIRED — Fatal0 / Major4 / Minor0.** This is a completed independent offline review, not an implementation or a Stage/product Gate0 acceptance.

## Authority, scope and immutable bindings

Initial worktree was clean at5894419833fb2ffab5aadb4cffc6881066befb4c; requested `git merge --no-edit 18c950e6e3497c425ddb11fcbb85b75da4ded4b1` fast-forwarded successfully. Only this new review subtree is authored. Root237760b adjudication and correction01 review/findings/probes govern; root8bb9701 coordinate and37f1b2d parent-supervision responsibility were read through Git without metadata merges. Read AGENTS, governance/routing, execution index, frozen production-quality packet and unique p3b-quality-contract. Implementation prose was navigation only; findings below come from production source and captured raw execution.

`bindings.json` binds68 source/test/runner/probe/frozen/old-review files byte-for-byte to candidate and evidence head. Candidate-vs-root237760b diff is exactly two allowed tool files and two correction02 text harnesses. Candidate-vs18c950e adds only ten implementation evidence files. Ancestor root metadata was not attributed to implementation changes. Original implementation report/checksum restoration matches the root history-scope disposition (report406d8dde… and checksum37f8a9b3…); old failures, review artifacts and raw logs remain unchanged. Frozen payload/spec hashes verified in frozen-manifest-verification.json; no quality-set/prelabels/holdout content was read.

| Binding | SHA256 |
|---|---|
|tools/v0_s3_quality_phase.py|d2c12745dcb56230175f2ac6b113dd9beac956f4e6fb0d6be598b7dcfc8db0b4|
|tools/test_v0_s3_quality_phase.py|a721d75ec70581d875bf22fb5f182b249e94a7bf68e0a3abc70f5a9e83fce8ab|
|reports/v0-s3/product-gate0/p3b-quality-contract.md|d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3|
|reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json|47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3|
|reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py|d1261c15c58d6b5e5bd16b7e5a683112d2746a09f432ade836022078dda183f6|
|reports/v0-s3/product-gate0/implementation-p3b-correction-02/run_guarded_probe.py|4eea0989e4ba51a130a24ed0498af9c7993fa63705a7cb5c12531512339ccb77|
|reports/v0-s3/product-gate0/implementation-p3b-correction-02/replay_correction01_probes.py|b59a3dcf3d68ca97c2eb137a0cc594354fd70e9099e17a9a1aa7b990de8ae97b|

## Bounded verification and denominator audit

Run only combined112 once, guardselftest4 once, replay21 once, focused18 and final-gap4 observations once. No duplicate95/new17/39+28, P3A121/P2B237 or full project. The focused actual-cap observations close the replay/test gap from monkeypatched small limits; they exercise real8MiB/128MiB/256 on owned disk. Final-gap observations check the distinct whole-phase pre-send boundary and actual terminal receipt error path. All are finite synthetic operations; no deliberate hang. Counterexample observations are not passing product tests.

| Run | Real child exit | Raw stdout bytes | Raw stderr bytes | Interpretation |
|---|---:|---:|---:|---|
|suite|0|13628|0|112/112 passing assertions;95 preserved obligations+17 new|
|replay|0|6075|0|21 observations, not product tests|
|focused|0|13291|0|18 independent observations|
|final-gap|0|1626|0|4 independent observations|
|guard|0|1101 (runner)|0|4/4 blocked before effects|

Commands, environment, stdout/stderr SHA256, exact byte lengths and real outer/inner exits are retained in *.command.json, *.receipt.json, raw streams and bindings.json; no pipeline masks status. Earlier implementation piped debugging remains UNKNOWN (46failed/60passed,6failed/89passed,1failed/111passed); no reconstruction or rerun solely for cosmetics.

Pre-pytest/product import audit guards block Python connect/bind/DNS/Popen/system/exec/spawn/fork; external plugin autoload, pytest cache and bytecode are off. Four attempted guard operations are actually rejected. Read-only Git bindings run separately. This does not certify native extensions/direct syscalls.

Static AST audit in test-obligation-audit.json reconciles all actual112 collected IDs: prior76 functions still generate95 cases;15 new functions generate17 (receipt caps parameterized3).72 prior assertion sets are identical;4 changed sets were explicitly reviewed. Ancestor redirect now opens/closes pinned handles and adds empty-foreign-root assertion; root/phase replacement expectations change only to OWNED_PATH_REPLACED while preserving zero sends; missing/unknown proof changes from constructor exception to full16 BLOCKED/zero sends and additionally covers untyped input. One further preserved function only supplies the new typed insufficient-capacity fixture; assertions are identical. All original source/storage/scoring/public-owner obligations remain tested. Count preservation is not described as all assertions untouched.

## Aggregate remaining findings (one disposition)

### M01 — Major: PARTIALLY_FIXED_REMAINS_OPEN

Location: `tools/v0_s3_quality_phase.py:1794-1840 (_write_receipt),1842-1854 (_finish)`.

Trigger: Run actual QualityPhase.run with os.fsync raising only on the exclusively opened final qd-receipt.json FD.

Expected: A failed terminal persistence must not leave an authoritative-looking success receipt contradicting the returned terminal evidence; preserve failure and do not overwrite old evidence.

Actual: All16 sends finish, then returned decision is QUALITY_EXECUTION_BLOCKED, receipt_persisted=false, storage_unproven=true; readable on-disk receipt says COMPLETE_ALL_16_PASS, persisted=true, storage_unproven=false. A retry refuses overwrite and retains those misleading bytes.

Fixed portion: Canonical self-inclusive successful disk/returned receipt and real 8MiB/128MiB/256 exact/oneover caps independently verified.

Evidence: `final-gap.stdout.log:actual_run_receipt_fsync_failure`, `focused.stdout.log:receipt_fsync_failure`.

### M08 — Major: PARTIALLY_FIXED_REMAINS_OPEN

Location: `tools/v0_s3_quality_phase.py:2113-2149 (_row_evidence_complete),2269-2348 (QS callers)`.

Trigger: On public recompute_scores with verified real synthetic raw artifacts, remove global storage_unproven or cleanup_unproven, set storage_unproven=null, omit source_evidence.identity or substitute source_evidence.path, or retain only the two favourable release booleans.

Expected: Unknown source/storage/cleanup remains unresolved and cannot aggregate PASS; source and release evidence must retain their bound identity and complete proof.

Actual: Every focused variant yields aggregate_pass=true and row usable=true/resolved=true/evidence_complete=true. Only explicit True uncertainty is rejected, source path/identity are never examined, and a two-boolean release dictionary suffices.

Fixed portion: Original three concrete unknown cases now refuse; complete known failure stays resolved/not usable, critical3 stays visible and aggregate fails.

Evidence: `focused.stdout.log:storage_flag_missing`, `focused.stdout.log:storage_flag_null`, `focused.stdout.log:cleanup_flag_missing`, `focused.stdout.log:source_identity_missing`, `focused.stdout.log:source_path_foreign`, `focused.stdout.log:release_details_missing`.

### NM01 — Major: PARTIALLY_FIXED_REMAINS_OPEN

Location: `tools/v0_s3_quality_phase.py:758-773,1250-1278,1898-1910`.

Trigger: Admit a valid typed proof expiring at clock2; during the first quality_public_submit callback advance clock0 to2 (under30s callback ceiling). Separate observation diminishes the internal capacity to0 at that same handoff.

Expected: Freshness and sufficient remaining capacity must hold after preparation/authorization immediately before the first send; invalid proof gives zero sends/full16 refused.

Actual: Both observations permit16 sends and COMPLETE_ALL_16_PASS. _parent_proof_is_fresh runs only once at phase entry; expiry/capacity is not rechecked at the actual send.

Fixed portion: Initial missing/untyped/foreign/stale/nonfinite/insufficient proofs refuse; no authentic provider/reservation/debit attestation inferred.

Evidence: `focused.stdout.log:proof_expires_before_first_send`, `focused.stdout.log:proof_diminishes_before_first_send`.

### NM02 — Major: LOCAL_COOPERATIVE_DEADLINE_GAP_PLUS_SEPARATE_PARENT_INTEGRATION_BLOCKER

Location: `tools/v0_s3_quality_phase.py:792-806,1250-1278,1405-1427,1948-1963`.

Trigger: Bounded fake clock: source/workflow preparation returns at10799; first submit authorization consumes2s and returns normally at10801, within its30s ceiling. Parent proof expiry20000 isolates the phase deadline.

Expected: Cooperative whole-phase deadline refusal before the next send after callback return. Actual preemption of hung calls remains mandatory parent responsibility.

Actual: One request is sent at10801 after deadline10800; only the later history check rejects with HISTORY_TIMEOUT (FAIL1/BLOCKED15). This is a missing cooperative pre-send check, not a demand for a local worker platform.

Fixed portion: Finite/nonbool/monotonic clock enforcement and late history rejection work; synchronous callbacks explicitly not preemptively bounded. Mandatory parent watchdog/owned cleanup is still UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER.

Evidence: `final-gap.stdout.log:cooperative_phase_deadline_before_send`, `replay.stdout.log:post_return_elapsed_only`, `final-gap.stdout.log:clock_nonfinite`, `final-gap.stdout.log:clock_boolean`.

## All prior finding dispositions

| Finding | Disposition | Current evidence/reason |
|---|---|---|
|M02|CLOSED_SCOPED_OFFLINE|Descriptor-relative O_DIRECTORY|O_NOFOLLOW parent handles and exclusive dir_fd writes cover all artifact and receipt paths; initial temp symlink creates zero foreign entries, callback temp redirect gives zero sends/no files in old root, rows-open swap zero foreign entries/zero sends; original root/phase replacements and replay rejection retained. replay.stdout.log; suite.stdout.log:test_correction_m02_*,test_correction02_m02_*; focused.stdout.log:receipt_final_open_ancestor_swap|
|M03|CLOSED_SCOPED_OFFLINE|Final bounded source read follows authorization, checks prior inode/hash and descriptor/path identity; source callback mutation yields zero sends. suite.stdout.log:test_correction_m03_a_source_replaced_in_a_callback_produces_zero_sends; source growth/hash/symlink checks|
|M04|CLOSED_SCOPED_OFFLINE|Ordinary cleanup error preserves16 terminal rows, attempts release, records unknown cleanup, stops later sends. suite.stdout.log:test_correction_m04_an_ordinary_cleanup_exception_never_bypasses_the_release|
|M05|CLOSED_SCOPED_OFFLINE|Submission attempts and1/4 provider reservations charged before actual send, no retries, max34 unchanged. suite.stdout.log:test_correction_m05_a_failed_submit_stays_charged,test_correction_m05_the_provider_reservation_never_exceeds_thirty_four|
|M06|CLOSED_SCOPED_OFFLINE|Exact reviewer/session pairs required, cross-pair refused; authentic independent isolation remains external evidence. suite.stdout.log:test_correction_m06_*|
|M07|CLOSED_SCOPED_OFFLINE|Actual raw path/hash/bytes checked against QD and scoring evidence; suggestion substitution and escapes refused. suite.stdout.log:test_correction_m07_a_wrong_execution_raw_length_is_rejected; original QS binding/path tests|
|M09|CLOSED_SCOPED_OFFLINE|Actual production BridgeOwner invalid envelope generates BridgeError; public image/video nodes expose error history; exact raw_response/prior frame raw retained. Provider-after evidence precedes persistence. suite.stdout.log:test_correction_m09_*; bindings.json production owner hashes|
|m01|CLOSED_SCOPED_OFFLINE|Release elapsed/GPU evidence finite/nonbool, strictly increasing/gap-bounded and stable at baseline; original tests retained. suite.stdout.log:test_correction_m01_a_non_finite_release_is_rejected|
|M01|PARTIALLY_FIXED_REMAINS_OPEN|See remaining finding above. ['final-gap.stdout.log:actual_run_receipt_fsync_failure', 'focused.stdout.log:receipt_fsync_failure']|
|M08|PARTIALLY_FIXED_REMAINS_OPEN|See remaining finding above. ['focused.stdout.log:storage_flag_missing', 'focused.stdout.log:storage_flag_null', 'focused.stdout.log:cleanup_flag_missing', 'focused.stdout.log:source_identity_missing', 'focused.stdout.log:source_path_foreign', 'focused.stdout.log:release_details_missing']|
|NM01|PARTIALLY_FIXED_REMAINS_OPEN|See remaining finding above. ['focused.stdout.log:proof_expires_before_first_send', 'focused.stdout.log:proof_diminishes_before_first_send']|
|NM02|LOCAL_COOPERATIVE_DEADLINE_GAP_PLUS_SEPARATE_PARENT_INTEGRATION_BLOCKER|See remaining finding above. ['final-gap.stdout.log:cooperative_phase_deadline_before_send', 'replay.stdout.log:post_return_elapsed_only', 'final-gap.stdout.log:clock_nonfinite', 'final-gap.stdout.log:clock_boolean']|

M01 successful receipt is canonical and byte-identical in memory/disk; self-inclusion reaches the bounded fixed point. Actual exact/oneover: receipt8388608/8388609 bytes, total134217728/134217729 bytes, files256/257. All exact cases persist with honest disk totals; every over case refuses before receipt creation. Replay/exclusive creation protects old bytes. The independent fsync failure exposes a distinct terminal-state mismatch; it does not negate the successful accounting correction.

M02: inspected `_OwnedDirectory`, `_open_owned_directories`, `_artifact`, `_write_receipt`, initialization refusal, per-row exception/finally and final closure. Actual directory opens use O_DIRECTORY|O_NOFOLLOW and dir_fd, creations use exclusive O_EXCL, nested handles close in finally, root/temp/phase close on success/refusal/failure, and after-close writes refuse. Initial temp symlink and nested open swap produce zero foreign entries; callback temp redirect stops all sends and writes no old-root files. A separate final-receipt-open swap after the last identity check writes through the already owned phase FD to its moved original inode, with zero foreign entries; this is documented as the accepted inode-moving observation limit, not a newly imposed universal-race defect. No replaced foreign descriptor is adopted.

QS checks use actual raw artifact paths/hashes/lengths; M07 closed. Original PASS_cleanup_unknown/known_FAIL_storage_unknown/known_FAIL_source_unknown now cannot aggregatePASS. Verified known FAIL is resolved/not usable; critical3 remains3 and aggregate fails at9/10+6/6. Original >=8/10,>=5/6, per-row>=8, critical0 policy remains, with no requirement that all execution rows technically PASS. M08 additional field-deletion/tamper probes are inputs to the real public validator, not a claim the producer generated those precise combinations.

Production paths remain the same8191 publicgraph -> S2SystemDriver/NativeRuntime submit/history surface -> real controlled-image node/image BridgeOwner and video public node/BridgeOwner -> original public oracle/PromptSpec. SyntheticDriver substitutes HTTP/provider, ownership/resource observations and tiny fake-video decoding only; 4x4 images go through actual production owner. Invalid synthetic provider envelopes produce real BridgeError/str(error) raw failure/prior-frame evidence; this is not mutation of old success into a claimed real failure. Graph equality, prompt identity, provider-before/after prefix/hash/bytes/count, reservations, no retry, listener PID/birth, source identity and release semantics remain audited in original95 within combined112. No private inference path was used.

## Local recommendation versus pending global integration

Local component: CHANGES_REQUIRED, F0/M4/m0. M02 plus the seven already closed original findings remain CLOSED_SCOPED_OFFLINE; M01/M08/NM01/NM02 retain the precise local gaps above. No candidate fix or implementation self-signing occurred.

Global: mandatory actual external parent process supervision/watchdog, pending-I/O proof and owned cleanup remain UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER. Honest constants/dictionaries and post-return checks do not implement it. Root37f1b2d design only assigns responsibility; actual controlled-blocking enforcement must later be proven before productGate0/real acceptance. No separate worker platform is required or implemented by this local review.600/10800 limits are unchanged. Authentic parent provider/debit/reservation and native video-residue adapter are still pending; shaped internal proof is not reservation attestation. Native residue/admission/watchdog/A06/network/rollback/real16quality/full12/Gate0/human/release all NOT_PROVEN.

Zero actualWindows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint. Only bounded synthetic fixtures and text outputs: unique suite/replay/focused/final-gap roots and the short-lived coordinate capture are registered and removed by their owner (receipt.json). Original fixture roots were never scanned or deleted. Focused cap filler binaries were never added to Git and were deleted with their exact owned roots; no binaries/DB/ZIP/copied source retained. Pytest fixture deletion is not parent OwnedArchive/product cleanup proof. No push or permanent config.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE from read-only8bb9701; unchanged.
2. 本批完成: independent correction02 review complete;112/112, guard4/4, replay21 and22 focused observations; Fatal0/Major4/Minor0.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b; scoped human acceptance only.
4. 当前阻塞门禁: unchanged S3_P3B_INDEPENDENT_REVIEW_AND_COMPLETE_PRODUCT_GATE0_PENDING; local CHANGES_REQUIRED and mandatory parent timing integration.
5. 全局路线位置: root aggregate disposition → bounded authorized correction → separate independent review → thin coordinator/A06/Gate0 → bounded real16/cumulative execution → independent quality scores → required human/release gates.
6. 剩余工作: four exact local Major findings and all listed native/global integration and acceptance obligations; no stage advancement.
7. 下一责任人: root architecture/gate owner for aggregate disposition; authorized visible implementation owner for correction; separate reviewer afterward.
8. 所需授权: none additional for completed authorized offline checks; no real execution authorization inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3b-correction-02/; report/receipt/findings/dispositions/bindings/harnesses/raw commands/streams/hashes.
10. 精确停止原因: assigned read-only review delivered with reproducible remaining defects; return once to coordinator with full commit SHA, keep visible.

## Full unchanged V0–V3 outline

Read-only8bb9701; full substeps/status/evidence are retained in coordinate.json and receipt.json. Current product Stage **R1**; this review changes none of them.

| Delivery | Stage | Done/total | Implementation | Machine | Independent | Human |
|---|---|---:|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
