# Independent P3B correction-01 review

**F0 / M5 / m0 — CHANGES_REQUIRED_OFFLINE_COMPONENT.** Candidate remains unaccepted despite95 passing checks. This is an independent offline review, not product acceptance, quality certification, human signing or release.

Candidate `376ea9283cb7096c2fc35f6eab561919c07b6d1f`; implementation evidence `e16274256509078f6a94182196539eb7a43a5dc5`; original independent review `e2294724463efcab1a202a25563f76a24eea798f`; root disposition `0c7d27b436abb81042e6ef160ef663ff3e1c4d22`. Initial worktree was clean; requested `git merge --no-edit e16274256509078f6a94182196539eb7a43a5dc5` succeeded, merge head `ed00535dd4b94b524d6cfe4318a27a3e6569983d`. Root `b1a9386` coordinate was read with git show only. Author ljx418 <1173696783@qq.com>.

The sole authored subtree is this new review directory. Candidate source/tests/old reports/logs/probes/packet/quality/prelabels are untouched by this reviewer. Candidate diff contains the two tools, new correction report files, and two cosmetic edits in the old implementation report/SHA256SUMS; that is recorded rather than hidden as a two-tools-only diff. The runner-path/projection prose typo is nonblocking because actual command paths/imports are correct; no cosmetic rerun. Root message msg_fcaa6c30bbc5 confirms the cosmetic old-report deviation is nonblocking: root7a14f62 restores exact original implementation-p3b/report.md and SHA256SUMS at integration and records correction01-history-scope-disposition.json, preserving supplied commits; no raw failure log changed. This review continues to bind immutable376ea92/e162742, with no metadata merge or additional test round. No testSource, human holdouts or full prelabels were read. The quality-set file was byte-hashed only; Git blob outputs are recorded by byte count/hash rather than retained as copied source or prelabels.

## Execution and bindings

| Batch | Fresh result | Exit |
|---|---|---:|
| Combined95 once |95 passed,0 failed/skipped/deselected,10.74s|0|
| Guard selftest once |4/4 blocked connect/bind/Popen/system|0|
| Updated original counterexamples |13 replayed observations, not product PASS|0|
| Independent targeted probes |17 additional bounded observations, not product PASS|0|

Inspected implementation-p3b/run_offline_checks.py and correction run_guarded_probe.py before execution: audit hook precedes pytest/product imports; blocks Python connect/bind/DNS/subprocess/system/exec/spawn/posix_spawn/fork/forkpty events. External pytest plugins/options cleared, autoload/cache/bytecode off, unique owned /tmp basetemp recorded. This is not an OS sandbox or assurance against native extensions/direct syscalls. Genuine local logs preserve observed commands, stdout/stderr/exit/hash/count but do not cryptographically attest runtime. Actual runner commands/environment and child receipts are adjacent; original12 probes plus existing-directory boundary are replayed with changed expectations through the inspected correction harness, never by editing old reports or counting defect observations as PASS.

AST count independently recomputes67 original parametrized cases plus28 new functions/cases=95; no original test removed. Five original test bodies changed: binding adds new proof argument, failed-row reason/exact-pair code align with disposition, unscored run still rejects, and deadline expected statuses now include late-success rejection. Original proof obligations remain, but the suite does not cover the open conditions below; the unscored test no longer directly asserts critical_known=false, which the missing-score implementation still computes. No separate28,39+28,P3A121,P2B237 or full-project run.

binding-results.json verifies source/test/runner/probes/contract/projection against candidate and final e162 evidence, all10 production-quality packet hashes and unchanged baseline bytes, implementation final14 SHA256SUMS entries, and raw receipt stream hashes/lengths. The directed28 and combined95 implementation logs are inspected historical evidence only; this review independently runs95 once. Contract d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3 and projection47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3 match. Both early piped diagnostics remain UNKNOWN; no retrocertification or replacement.

## Aggregate findings (one disposition)

### M01 — Major

Location: `tools/v0_s3_quality_phase.py:1490-1534`. Trigger: Complete QualityPhase.run and read persisted qd-receipt.json.

Expected: Persist honest final bytes/files including the receipt itself.

Actual: In-memory counts are 137 files/165510 bytes, but disk has only pre-receipt counts 136/117094; receipt_bytes and both *_including_receipt keys are absent. Serialization precedes adding final fields. Caps now reject one-over, but persistent terminal accounting is still incomplete.

Evidence: probes.stdout.log:persisted_receipt_totals; receipt_artifact_exact/over, receipt_total_exact/over, receipt_files_exact/over. Disposition: PARTIALLY_FIXED_REMAINS_OPEN: suffix classification, halt,16-row retention, exact/oneover caps and honest nonpersistence fixed; stored totals not fixed.

### M02 — Major

Location: `tools/v0_s3_quality_phase.py:510-551,794-842,1490-1534,1548-1579`. Trigger: quality_row_begin moves temp to old-temp and replaces temp with symlink to old-temp; alternatively substitute rows at final os.open.

Expected: Pin all original ancestors across callbacks and actual writes; write zero into old/foreign paths and stop on redirect.

Actual: Temp ancestor redirect accepts all16 submissions and COMPLETE_ALL_16_PASS while persisting receipt in old-temp. Deterministic final-open interposition writes SYN-I00/provider-before.log into a foreign root and still permits one send before later rejection. Initial temp symlink creates foreign s3-quality before detecting escape. Leaf O_NOFOLLOW and prechecks do not protect ancestor traversal.

Evidence: probes.stdout.log:temp_ancestor_callback_redirect,artifact_open_ancestor_race,initial_temp_redirect; targeted_probes.py. Disposition: PARTIALLY_FIXED_REMAINS_OPEN: existing-directory replay and direct root/phase replacement tested refusals fixed; all-ancestor pinning/write confinement not fixed.

### M08 — Major

Location: `tools/v0_s3_quality_phase.py:1824-1991`. Trigger: QS input has PASS row with missing release proof, or known FAIL with storage_unproven=true, or missing source_evidence.

Expected: Unknown source/storage/cleanup cannot aggregate PASS; known failed rows may resolve only with proven evidence, always remain unusable.

Actual: All three public recompute_scores probes aggregate_pass=true. PASS row has cleanup_proven=false yet becomes usable/resolved. Known FAIL rows with explicit unknown storage or missing source still resolve. Critical3 now survives and ordinary known FAIL with valid evidence correctly yields9/10+6/6 usable, so original scoring policy improvements are retained.

Evidence: probes.stdout.log:PASS_cleanup_unknown,known_FAIL_storage_unknown,known_FAIL_source_unknown; replayed-observations.json:failed_row_critical_evidence,known_failed_independently_scored. Disposition: PARTIALLY_FIXED_REMAINS_OPEN: critical evidence and no extra all-technical-success requirement fixed; evidence-resolution fail-closed incomplete.

### NM01 — Major

Location: `tools/v0_s3_quality_phase.py:458-473,1585-1593`. Trigger: Parent proof known=true/capacity34 but wrong run/candidate/authorization or expired timestamp.

Expected: Internal admission rejects stale and wrong-identity proofs as well as unknown/insufficient capacity before any send; authentic provider remains pending integration.

Actual: Both stale and explicitly wrong identity dictionaries permit all16 submissions and COMPLETE_ALL_16_PASS. Only known and numeric capacity are checked; no freshness or identity is bound. This is internal validation, not a request to create a ledger API or infer guaranteed34 capacity.

Evidence: probes.stdout.log:parent_proof_wrong_identity,parent_proof_stale; suite95 admission checks. Disposition: ADDITIONAL_ORIGINAL_OBLIGATION_NOT_CLOSED.

### NM02 — Major

Location: `tools/v0_s3_quality_phase.py:554-582,1003-1090,1155-1175,1490-1534; tools/v0_s2_http.py:56-78,100-148`. Trigger: Callback/observer/persistence/release callable does not return; or finite phase clock decreases.

Expected: Original600s history/10800s phase bounds require actual bounded calls or enforceable parent admission, not only post-return rejection; clock evidence must be monotonic.

Actual: _authorize and _bounded invoke callables synchronously and check elapsed only after return/finally; persistence and receipt writes also have no preemptive bound. A bounded synthetic callback returns only after simulated10801s before rejection. Decreasing finite clock allows all16 to PASS. No intentionally hung process was launched. Native HTTP has absolute request/socket deadlines in _request and owned cancellation, but observer callbacks in request are synchronous; these semantics do not bound arbitrary callbacks or guarantee the entire phase.

Evidence: probes.stdout.log:post_return_elapsed_only,decreasing_phase_clock; static production source locations. Disposition: ADDITIONAL_ORIGINAL_OBLIGATION_PARTIAL: late SUCCESS history rejection fixed, hard callable bounds/monotonic phase clock not proved.

## Every original finding disposition

| Original | Disposition | Evidence/reason |
|---|---|---|
|M01|OPEN_PARTIALLY_FIXED|PARTIALLY_FIXED_REMAINS_OPEN: suffix classification, halt,16-row retention, exact/oneover caps and honest nonpersistence fixed; stored totals not fixed See open finding above.|
|M02|OPEN_PARTIALLY_FIXED|PARTIALLY_FIXED_REMAINS_OPEN: existing-directory replay and direct root/phase replacement tested refusals fixed; all-ancestor pinning/write confinement not fixed See open finding above.|
|M03|CLOSED_SCOPED_OFFLINE|Final source validation follows authorize, compares descriptor/path identity after bounded read, and changed source yields zero sends; does not promise universal hostile OS race immunity. replayed-observations.json:source_mutation_in_authorize; suite95 source replacement/growth tests|
|M04|CLOSED_SCOPED_OFFLINE|OSError produces full16 terminal rows, attempts release, persists diagnostics and blocks later sends. replayed-observations.json:residue_exception; suite95 test_correction_m04|
|M05|CLOSED_SCOPED_OFFLINE|Attempt precharged even when submit fails, successful returns counted separately; reservation maximum34 retained. replayed-observations.json:failed_submit_counter; suite95 reservation test|
|M06|CLOSED_SCOPED_OFFLINE|Exact reviewer/session pairs enforced; string identity alone still is not independent provenance. replayed-observations.json:cross_paired_reviewer_session; suite95 exact pair|
|M07|CLOSED_SCOPED_OFFLINE|Reads actual raw and checks execution hash/length plus score hash/path/declared length. replayed-observations.json:execution_raw_length_mismatch; suite95 hash/path substitution cases|
|M08|OPEN_PARTIALLY_FIXED|PARTIALLY_FIXED_REMAINS_OPEN: critical evidence and no extra all-technical-success requirement fixed; evidence-resolution fail-closed incomplete See open finding above.|
|M09|CLOSED_SCOPED_OFFLINE|Synthetic provider returns invalid exact envelope into actual production image/video nodes and BridgeOwner; str(BridgeError) is serialized into execution_error history, raw_response and prior_frame_raw_responses are extracted before validation; provider-after snapshot/count taken before persistence. These assertions execute in combined95 once, not rerun as a separate directed batch. suite95 test_correction_m09_*; source test SyntheticDriver.submit/BridgeError.__str__; production-bindings.json|
|m01|CLOSED_SCOPED_OFFLINE|NaN/inf/bool elapsed and nonfinite/bool GPU moments refused; strict increasing gap-bounded release samples. Global clock defect separately NM02. replayed-observations.json:nonfinite_release; suite95 test_correction_m01_a_non_finite_release_is_rejected; source892-943|

## Scope and remaining integration

M02 probes demonstrate reachable old/foreign writes under controlled handoffs and deterministic final-open interposition; they do not impose universal OS race protection beyond accepted P3A limitations. M08 probes enter actual public QS with modified evidence documents, establishing missing validator checks rather than claiming the producer emitted those precise combinations. No failed row is rescued into usability. Fixed8/10 images+5/6 videos, sample>=8 and critical0 stay unchanged; all technical rows PASS is not an added prerequisite.

M09 is exercised by actual image/video production owner failures from synthetic provider envelopes, not old success mutation or code-only fake. History, exact error raw and prior-frame evidence flow through public node semantics; provider-before/after full logs/counts are retained before parsing/persistence. Native HTTP driver uses bounded request/socket semantics and8191 remains owned; offline inspection is not actual native HTTP verification. Profile/modeldigest/lineage/resource sampler/PID-birth and provider reservations remain with original owners. A dict capacity flag is not authentic parent admission, and a fake residue accessor is not the NativeRuntime adapter.

All synthetic media are fresh4x4 PNG/tiny fakevideo behind real node/BridgeOwner/oracle; no real decoder/server. Suite/replay/targeted roots were uniquely created, recorded and deleted only by their owner. Other/original pytest roots were not scanned or deleted. Retained artifacts are bounded text harnesses/logs/reports only, no binary/DB/ZIP/source copy. Fixture teardown is not parent OwnedArchive proof.

Authentic parent proof provider, production residue adapter, integration/A06/network/rollback/real16 quality/full12/productGate0/human/release all NOT_PROVEN. Zero actual nativeWindows/WSL/PowerShell/parser/hostexe hashes/model/GPU/realmedia/FFmpeg/service/networktest/download/realledger/claim/fullcheckpoint actions. Recommend root aggregate correction disposition for the five open Major findings; no candidate fix or selfsigning here.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE from read-only b1a9386.
2. 本批完成: independent review complete;95/95, guard4/4,13 replay+17 additional observations;F0/M5/m0 offline CHANGES_REQUIRED.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped human acceptance only.
4. 当前阻塞门禁: S3_P3B_INDEPENDENT_REVIEW_AND_COMPLETE_PRODUCT_GATE0_PENDING; no coordinate mutation.
5. 全局路线位置: root aggregate disposition → authorized correction → independent review → coordinator/A06/Gate0 → bounded real16/cumulative execution → independent scores → required human/release gates.
6. 剩余工作: M01/M02/M08 partially open plus NM01/NM02; all listed real integration/quality gates NOT_PROVEN.
7. 下一责任人: root architecture/gate owner; authorized visible implementation owner for any correction, separate independent reviewer afterward.
8. 所需授权: none additional for completed offline checks; no real-run authorization inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3b-correction-01/; report/receipt/findings/bindings/probes/commands/streams/hashes.
10. 精确停止原因: assigned review completed with independently reproduced defects; return once to coordinator; visible window retained.

## Full unchanged V0–V3 outline

Read-only b1a9386; full substeps/status/evidence retained in coordinate.json. Current product Stage R1; this review does not advance any substage.

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
