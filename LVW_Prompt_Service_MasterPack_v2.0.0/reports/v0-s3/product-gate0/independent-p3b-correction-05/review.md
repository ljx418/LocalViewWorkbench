# Independent P3B correction05 aggregate review

**CHANGES_REQUIRED — Fatal0 / Major2 / Minor0.** Independent component recommendation only; no StagePASS or productPASS. Code44ad8c7a30ee418af41834de6cc87685f80d42fa and evidenceafb12e2a136b4a1bed05f1f766084c2b279e07b0 were integrated as instructed. Current root intake/outline came only from gitshow1da15dee4c1f944aed0e40bbc00eb93a536cd1b1. Implementation claims were used to navigate, not to establish closure.

The inspected immutable runner installs its audit hook before pytest/plugins/product/test imports. It disables plugin autoload, pytest cache and bytecode; named Python audit events block connect/bind/DNS/Popen/system/exec/spawn/fork. All validation below used it. This is not a native/direct-syscall immunity claim.

| Invocation | Once-only result | Inner / outer true exit |
|---|---|---|
| Combined suite |206/206 passed,53.45s; original175 plus31 new|0 / 0|
| Guard selftest |4/4 blocked before external actions|0 / 0|
| Immutable correction05 replay |21 observations, output adapter only|0 / 0|
| Independent focused |32 observations|0 / 0|
| Supplementary small seal/read boundaries |10 observations; no replay rerun|0 / 0|

Raw streams and exact commands are in commands.json and each invocation receipt/outer JSON. “Observation” counts are not additional product tests. Script exit0 means successful observation capture; it does not turn a reproduced defect into a passing obligation. All source/runner/probe hashes before/after, actual imported module absolute paths/hashes and stream hashes are retained. Product6229569649fde3a5542a4d5c1ced95ea0268cb885baae3a9f18b4a69cc41fbaf; test052502d17bfb462b3831c75c8135a1384422a28b978880e68b4d1a98681e102a; runner016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8; original replay202b14adc23c773896b85de503bac1ea19a047184fd1f28c2abf4580160f6ffa. The adapter changes only the in-memory OUT assignment, verifies immutable original replay hash before and after, and writes exclusively here. No copied product/test source is committed.

## M01 — PARTIALLY_FIXED_REMAINS_OPEN

**Location:** tools/v0_s3_quality_phase.py:595 validate_source_evidence;2812 _verify_seal_row_alignment;2979 _row_evidence_complete;3051 _verify_execution_content

**Trigger:** After a genuine complete public-owner run, change supplied rows[0].public_submission_attempted from true to integer1, or provider_calls from integer1 to true; alternatively append a caller-only source_evidence fact or top-level receipt fact. Leave canonical/seal/raw unchanged. A companion seal-only ordinal1->true probe updates only source-plan bytes/hash/length, keeping all execution rows unchanged.

**Expected:** Actual fact bindings distinguish typed booleans and integers where truth/accounting matters; source evidence and new facts cannot be fabricated outside explicitly restrictive overlays. Seal ordinals reproduce the original integer order.

**Actual:** Each caller-only substitution returns aggregate_pass=true/all_rows_resolved=true with10usable images/6videos/critical0. source_evidence is exempt from exhaustive row comparison, and its validator ignores added fields. Top-level added fields are never checked. Python equality accepts true==1 for row facts and seal ordinal; the seal-only boolean ordinal also aggregates true.

**Prerequisites:** Caller controls supplied dictionary for primary reproductions; no artifact edits. Companion ordinal reproduction requires seal write plus canonical/supplied hash-length update, but no execution-row rewrite. Arbitrary coherent rewrite of both trusted original records is not the finding.

**Fixed Portion:** Published unknown failure remains unresolved after caller-only known substitution. KnownFAIL suppliedPASS stays unusable/resolved; publishedPASS supplied knownFAIL can be resolved/unusable. Well-typed different release vectors are unresolved, changed baseline/counts/false attempt/run context reject. Unknown cleanup/storage/source and independently scored critical3 cannot be hidden.

**Recommendation:** Use type-aware equality or explicit field validation for authoritative facts; compare complete source evidence conservatively or consume it canonically while rejecting unsupported additions. Close top-level extra-field handling and require integer seal ordinal, preserving restrictive evidence declarations and knownFAIL semantics.

**Evidence:** `focused-observations.json:attempt_true_to_int1`, `focused-observations.json:counter_one_to_bool`, `focused-observations.json:source_extra_fact`, `focused-observations.json:receipt_extra_fact`, `boundary-observations.json:seal_only_ordinal`.

## NM03 — PARTIALLY_FIXED_REMAINS_OPEN

**Location:** tools/v0_s3_quality_phase.py:2510 _ArtifactBoundary;2632 verify;2647 read;2760 _verify_run_root_binding

**Trigger:** During the first bounded canonical os.read, after boundary descriptors have opened, rename the owned run_root, temp or phase directory and replace the original entry with a symlink to the retained directory. Keep all genuine canonical/seal/raw bytes unchanged; perform public QS in the same call.

**Expected:** Pinned ancestry is revalidated against the actual directory entries after reads. A redirected/replaced ancestor during read refuses; the selected original path must still name the pinned hierarchy.

**Actual:** All three deterministic in-process handoffs return aggregate_pass=true/all_rows_resolved=true while the selected run_root/temp/phase entry remains a symlink at return. verify() only fstats already-open descriptors and compares them to their own original identities. It never re-stats the run-root path or temp/phase entries relative to pinned parents. Literal declared run-root equality returns early. Descriptors keep reading original genuine bytes, but the path-to-hierarchy invariant is no longer true.

**Prerequisites:** Bounded mutation of only the owned fixture during an audited Python read; no concurrent native adversary, hostile kernel, universal immunity or Windows reparse guarantee is assumed.

**Fixed Portion:** Already-redirected run_root/temp/phase/canonical/source-plan/raw entries refuse. One descriptor-relative owner supplies canonical, source-plan and raw reads; bounded caps and common refusal cleanup work. Redirected raw parent before opening it refuses.

**Recommendation:** Compare pinned directory handles with their current named entries at the anchored parent levels after reads and at completion; include child directory/leaf identity observations required by the existing boundary. Preserve descriptor-relative no-follow reads and exception cleanup.

**Evidence:** `focused-observations.json:redirect_during_read_run_root`, `focused-observations.json:redirect_during_read_temp`, `focused-observations.json:redirect_during_read_phase`, `focused-observations.json:redirect_during_read_raw_parent`.

## Verified closures and remaining boundaries

The original unknown-error counterexample is fixed: the injected failure occurs after the real oracle with complete raw/release evidence; both original and caller-known substitution remain UNKNOWN_EXECUTION_FAILURE/unresolved/aggregatefalse. Published knownFAIL suppliedPASS stays FAIL/resolved/notusable. PublishedPASS supplied knownFAIL is resolved/notusable and may still meet9/10images+6/6videos; independently scored critical3 remains3 and blocks aggregate. Null/omitted source or typed run context/baseline, storage0 and cleanupnull remain unresolved. Different well-typed release vectors remain unresolved; baseline+release changes, terminal counts, false attempts and run-root changes reject. This preserves the original obligation without imposing all-technical-success.

M08 contradictory asset/kind/reference, whole-row and descriptor swaps reject in replay; independent seal-only bytes/hash/path/full identity contradictions reject with the intended alignment reason. Execution rows remain unchanged. Shared validators actually execute: QD source48/release16, then QS adds source32/release32. The seal is exclusive and bounded, written after initial16-source validation and before sends, with canonical length/hash binding. QS does not require original media to remain on disk. Boolean ordinal acceptance is recorded with the shared typed-equality residual under M01, not counted again.

NM04 is closed for tested cooperative accessor handoffs. All submissions/limit/submit getters bind before final bounded source validation against the original seal. Then one coherent finite clock/proof/ownership guard precedes reservation, attempt charge and cached submit. No extra driver getter/callback/clock appears in that interval. First mutations (mtime replay, ctime via mode change, content or path replacement) yield0sends/charges/reservations and16terminal rows(1FAIL/15BLOCKED). Later mutations preserve actual5sends/charges/reservations, stop at row6, and retain1FAIL/10BLOCKED; no refunds/retries. Unchanged original capacity0/clock10801 accessor cases, single finalclock, exact10800/oneover10801 and laterproof refusal execute within the one206 suite. A callback that never returns is not preempted: parent hard watchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER.

The reader call graph in static-audit.json shows canonical, source plan and raw all routed through _ArtifactBoundary.read, with no legacy resolved-path reader fallback. Initial run_root/temp/phase/leaf/source-plan/raw redirects reject. Canonical missing with staging retained, corrupt and foreign-run documents reject. Tiny exact4-byte read succeeds; cap3 refuses4bytes, and growth4->5 after initialfstat is refused by the final max+1 check. Observed normal/missing/oversize/escaping/growth paths close all controlled descriptors; constructor exception cleanup and public finally-close are present. The residual is specifically path-to-pinned-hierarchy revalidation during reads, not evidence that redirected arbitrary bytes were consumed. No universal hostile-host requirement is introduced.

AST/nodeid audit independently confirms130/130 old test definitions including decorators/assertions identical,0adapted/0deleted, all175 old collected nodeids retained, all old helper/class definitions unchanged.25 added definitions collect31 cases. The new destructive tests use private genuine runs and assert intended stable refusal reasons; mutation counters/earlier-pass counts establish that handoff cases reach the target. The malformed-value exhaustive fact test only proves malformed declarations are rejected/unknown; it does not prove type-aware equality, extra-field or during-read race coverage. The closed-overlay helper and source-inspection tests are structural checks, supplemented by real public-entry observations, not counted as further production integration. Real nodes, ControlledImageOwner, BridgeOwner and original oracles execute with synthetic HTTP/provider/tinydecoder only. Fixed16/34calls,8/10images,5/6videos,total>=8,critical0,raw preservation,cleanup,attempt reservation and original mandatory negatives remain. No separate175/31, old broad29/38 matrices, actual-cap matrix, P3A121/P2B237 or full project suite ran. Prior actual8MiB/128MiB/256 proofs remain unchanged; small bounded checks here do not recertify those historical runs.

## Closure mapping

|Prior|Current scoped disposition|
|---|---|
|M02|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M03|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M04|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M05|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M06|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M07|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M09|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|m01|CLOSED_SCOPED_OFFLINE_PRESERVED — All original175 nodeids retained;130 old definitions and all old helpers AST-identical; once206 pass plus static call graph audit.|
|M01|PARTIALLY_FIXED_REMAINS_OPEN — Unknown-error laundering and ordinary fabricated facts fixed; residual typed equality/extra fact gaps in current finding.|
|M08|ORIGINAL_LABEL_DESCRIPTOR_COUNTEREXAMPLES_CLOSED_WITH_TYPE_RESIDUAL — Replay label/swap refusals; independent bytes/hash/path/identity seal-only contradictions reject; integer1->boolean true seal ordinal accepted, shared type-equality defect included in M01, not double-counted.|
|NM03|PARTIALLY_FIXED_REMAINS_OPEN — Initial redirects refused; deterministic redirects during canonical read still aggregate true.|
|NM04|CLOSED_SCOPED_COOPERATIVE_ONLY — Limit mtime replay, independent submissions/content, submit/path and limit/ctime first changes all0send/0charge/0reserved,1FAIL+15BLOCKED; later submit/content and submissions/path preserve5send/5charge/5reserved with1FAIL+10BLOCKED.|
|NM01|CLOSED_ORIGINAL_CAPACITY_TIME_ACCESSORS_PRESERVED — Unchanged collected tests2641/2661 and related dynamic accessors pass; capacity0 and clock10801 refuse.|
|NM02|CLOSED_SCOPED_COOPERATIVE_ONLY — Unchanged single-clock/exact10800/oneover10801/later-proof obligations pass; final source check then coherent guard then reservation/charge/cached submit, no unchecked driver getter/callback/extra clock in between. Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER.|
|E01|HISTORY_UNCREDITED_UNCHANGED — Original correction03 unguarded12 remain UNKNOWN and zero-external-actions NOT_PROVEN under append-only erratum; current guarded evidence provides no retroactive certification.|
|E02|COUNT_ERRATA_PRESERVED — Current replay21 observations, independent focused32 plus supplementary10; none relabeled as extra product tests or historical reruns.|

## Evidence integrity, cleanup and limits

All36 implementation checksum entries independently match. Final suite/guard/replay six raw streams bind correctly and final imported source hashes match the supplied pins. Editing diagnostics retain exits1,0,1,0 and the earlier observation/debug invocations retain their distinct source/runner/probe digests and actual0 exits. Historical diagnostic receipts retain original output path strings after their files were moved into editing-diagnostics: those literal paths may now be absent or point to the final output. Static audit explicitly records declared-path matches separately from retained-file matches; all retained stdout/stderr hashes match after exact-label relocation. The early debug stdout and observation JSON differ and are kept distinct; they are not relabeled final replay. Source/probe edits between diagnostics and final are visible, never retroactively certified. Current guarded runs cannot credit original correction03 unguarded12; UNKNOWN exits and zero-external-actions NOT_PROVEN remain unchanged under the append-only erratum. Settled implementer and undelivered guidance were not reopened.

All owned fixture roots are registered in observation JSON and removed in finally; all five enclosing runner roots report removed (immutable runner does not emit their absolute names, so only nested roots have exact paths). No earlier roots were scanned/deleted. Bounded temporary4x4PNG/tinyfakevideo only; no real decoder/server. Only this new text subtree was authored/committed. Read-only Git/source operations were separate; initial prefixed merge-token failures had no effect, followed by successful actual-SHA merges. The authorized evidence ancestry already includes unrelated metadata; no separate root intake/V2 merge or authored metadata change occurred.

Root08e6fbe accepts that coherent rewriting of BOTH trusted originals is not a new cryptographic-signature obligation. The coherent-rewrite replay still aggregates true with that explicit prerequisite, and is not an additional finding. Before real consumption the parent must bind an owned original archive or independently retained original attestation and the selected run/root. Actual integration is NOT_PROVEN; an arbitrary unbound archive is not accepted as truth. Internally contradictory records, caller-only facts and source handoff invariants remain enforceable.

Zero actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/real ledger/claims/fullcheckpoint actions; no testSource/holdout/fullprelabel reads, binaries/DB/ZIP, permanentconfiguration, push or history rewrite. Parent archive/attestation, hardwatchdog, native residue/admission/A06, registration/installrollback, authentic ledger debit, realquality/full12/Gate0/human-release remain NOTPROVEN. This review cannot sign productGate0.

## Ten-field handoff

1 current coordinate: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY_FOR_REVIEW"}

2 this batch: Independent component recommendation CHANGES_REQUIRED; Fatal0/Major2/Minor0;206 product cases once,guard4 once,replay21 once,focused32 once,supplementary10 once

3 last passed gate: {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}

4 current blocking gate: S3_P3B_CORRECTION05_ISOLATED_REVIEW_PENDING

5 route position: Root aggregate disposition -> bounded correction -> separate review -> parent/native/A06/Gate0 -> finite real quality and human/release gates

6 remaining work: ["M01", "NM03", "Parent owned original archive or retained independent attestation and selected root binding NOT_PROVEN", "Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; synchronous callbacks not preempted", "Native Windows/WSL deployment, residue/admission and A06 enforcement/attempt observation NOT_PROVEN", "Actual registration baseline, installation and rollback NOT_PROVEN", "Authentic parent ledger debit NOT_PROVEN", "Real quality16, full12, productGate0, human and release acceptance NOT_PROVEN", "No claim of hostile-kernel, native Windows reparse, native extension/direct-syscall immunity", "Parent archive/crash durability and external process cleanup remain integration obligations"]

7 next owner: Root architecture/gate owner for disposition; any implementation remains separate from independent review

8 authorization: Completed authorized offline review only; no new human approval needed; no real-runtime authority inferred

9 evidence directory: reports/v0-s3/product-gate0/independent-p3b-correction-05/

10 exact stop reason: Assigned independent aggregate review completed; hand off current findings and commitSHA, keep terminal visible. Root snapshot older next_owner/stop text is preserved as navigation, not new review instruction.

## Full V0–V3 outline from current root

Source: gitshow1da15de only; current Stage **R1**. Counts and implementation/machine/independent/human statuses are unchanged. Full evidence references also appear in root-current-control.json and receipt.json.

|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|
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

Full declared substeps:

- **V0-S0**: 盘点与探索记录 [DONE]; 完整生产基线 [FAILED_HISTORICAL].
- **V0-S1**: 独立人工稿与导出 [DONE]; 真实图片与预处理 [DONE]; 四输出与草稿保护 [DONE]; 固定证据及独立审查 [DONE]; 人工签署 [DONE].
- **R0**: 独立单图路径在R1a验证 [DONE]; 完整复用/许可清单单独闭合 [NOT_VERIFIED].
- **R1a**: 正式合同子集与前后端 [DONE]; 真实单图链路 [DONE]; 失败/服务控制与人工稿保护 [DONE]; 独立审查七项 [DONE]; 人工体验签署 [DONE].
- **V0-S2**: WP-S2-00 冻结准备 [DONE]; WP-S2-01 媒体owner [DONE]; WP-S2-02 公开视频路径 [DONE]; WP-S2-03 安全/资源/取消 [DONE]; WP-S2-04 离线集中收口 [DONE]; WP-S2-05 完整真实验收 [DONE]; WP-S2-06 独立审查 [DONE]; S2 人工签署与Git同步 [PENDING].
- **V0-S3**: 包/清单/使用说明 [PENDING]; 安装诊断与回滚 [PENDING]; 独立质量集与标注 [PENDING]; 离线集中收口 [PENDING]; 真实十二项及质量 [PENDING]; 独审/人工签署/同步 [PENDING].
- **R1**: 受控媒体与人工镜头 [PENDING]; 六模式四目标 [PENDING]; SQLite/修订/导入 [PENDING]; 组合回归及阶段审查 [PENDING].
- **V1-M1**: M1-A detection/PTS/boundaries/timeline [PENDING]; M1-B per-shot evidence and serial child jobs [PENDING]; M1-C per-shot drafts/exports/fixed8 full validation [PENDING].
- **R2**: 异步任务/CAS/取消 [PENDING]; 真实图视频及质量 [PENDING]; CLI/导出/便携包 [PENDING]; V1累计独审及人工签署 [PENDING].
- **R3**: 真实PTS/切镜 [PENDING]; 资产/FTS5/配方 [PENDING]; 对比/QC/JSONL [PENDING]; 阶段验收 [PENDING].
- **R4**: MCP真客户端 [PENDING]; 批量/lease/幂等 [PENDING]; 备份恢复 [PENDING]; V2累计验收签署 [PENDING].
- **R5a**: 对端握手 [PENDING]; Navia证据 [PENDING]; Narralens建议/冲突 [PENDING]; 阶段真实验收 [PENDING].
- **R5b**: Comfy allowlist/映射 [PENDING]; 收据/outbox [PENDING]; GPU/取消协作 [PENDING]; 阶段真实验收 [PENDING].
- **R5c**: 集成UI [PENDING]; 升级回滚 [PENDING]; 三系统E2E [PENDING]; V3独审及人工签署 [PENDING].
