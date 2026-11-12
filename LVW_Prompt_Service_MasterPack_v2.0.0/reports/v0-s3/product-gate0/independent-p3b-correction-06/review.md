# Independent P3B correction06 aggregate review

**CHANGES_REQUIRED — Fatal0 / Major1 / Minor0.** Component recommendation only; no StagePASS or productPASS. M01 is closed within the frozen offline scope; NM03 has concrete progress but still loses custody of earlier-read entries before successful completion.

Candidate code `ba34b1581fc5e8e8b4de6ba469484e8eae416da1` and evidence `b66aebaddedab3eb2bee88dda18d7657b94ff6d4` were integrated using the requested `git merge --no-edit` (fast-forward; both are actual ancestors). Initial worktree was clean. Root intake/current outline was read only with gitshow `08caf9f0e93ff7ff5acee7783c730346fc3c2c9c`; no root metadata/V2 merge was added. AGENTS/routing, contract/projection, independent review1618614 and root adjudicationc05ee01 were inspected. Implementation narrative guided navigation only.

| Invocation | Single result | Inner / outer true exit |
|---|---|---|
| Combined suite |232 passed,81.33s pytest time|0 / 0|
| Guard selftest |4 blocked events|0 / 0|
| Immutable correction06 replay via output-only adapter |22 observations|0 / 0|
| Independent bounded targeted observations |33 observations, including6 reproduced residual custody cases|0 / 0|

All executable product/test observations used the inspected immutable correction05 runner with auditguard installed before pytest/plugins/ANY product/test import, plugin autoload/cache/bytecode disabled. connect/bind/DNS/Popen/system/exec/spawn/fork events are blocked. This is named Python audit coverage, not direct-syscall immunity. Exact argv/cwd and outer exits appear in commands.json; each invocation retains raw stdout/stderr, inner/outer receipts and stream hashes. Observation exit0 means capture completed, including reproduced defects; observations are not additional product tests. No repeated206/26 selections, historical21/32/10 probes, cap matrices, P3A121/P2B237 or project suite.

## NM03 — Major, partially fixed and still open

**Locations:** tools/v0_s3_quality_phase.py:2790 `_ArtifactBoundary.verify`,2809 `read`,3465 final QS verification.

**Trigger:** Start from a genuine completed public-owner synthetic run. During the bounded source-plan read, rename the already-read canonical receipt and replace its entry with a symlink to the untouched original. Alternatively replace the canonical with a different same-byte plain file during raw0 read; remove the already-read seal during raw0 read; replace raw0 leaf with a symlink or its parent with another plain directory during raw1 read. Every mutation is a controlled in-process handoff in this probe's own registered fixture. Supplied receipt and original canonical/seal/raw bytes are unchanged. A sixth companion probe changes canonical at the explicit final verify call.

**Expected:** The frozen correction06 task explicitly requires named-entry comparisons for read child directories/leaves before/after reads and before successful completion, while handles remain held. A removed/replaced evidence name must prevent successful completion, including when previously read bytes were genuine.

**Actual:** All six probes return `aggregate_pass=true/all_rows_resolved=true`,10 usable images/6 videos/critical0 while the selected canonical/raw entry is redirected/replaced, seal missing, or earlier raw directory replaced. All hooks fired once. For file mutations, before hashes and retained original hashes match; plain replacements copy identical bytes. No coherent trusted-original rewrite is involved.

**Cause:** `read()` checks only the current read's child directories and leaf, then closes their handles and discards the entry bindings. `_levels` retains only run_root/temp/phase. Final `verify()` therefore cannot revalidate earlier canonical/seal/raw leaves or their child directories. Pinning the three ancestors fixes the original during-current-read cases but does not fulfill the completion custody obligation.

**Evidence:** targeted-observations.json entries `after_canonical_read_symlink`, `after_canonical_read_plain`, `after_seal_read_missing`, `after_raw_read_leaf_symlink`, `after_raw_read_parent_plain`, `completion_canonical_leaf_redirect`; raw targeted.stdout.log; targeted inner/outer receipts. findings.json contains complete observations, expected/actual/trigger and locations.

**Recommendation:** Extend the existing bounded reader's custody through the final checks: retain the needed child-directory/leaf bindings, verify their current parent-relative names against held object identities/types at completion, then close all descriptors on success and errors. This remains a finite cooperative Python filesystem observation, not a new platform, signing scheme, hostilekernel/nativeWindows or universal concurrency guarantee.

The corrected portion is independently supported: replay rejects run_root/temp/phase symlinks during canonical read and raw parent/leaf redirects; targeted seal-read root symlink/temp plain/leaf plain replacements, canonical leaf plain/temp missing, and raw parent plain/leaf missing refuse with intended canonical/source-plan/raw reasons. Literal run-root equality now invokes verify. Parent descriptors are pinned; current read descriptors stay held through current-entry checks with no absolute-path fallback. Normal close, read-error close and partial constructor failure all return descriptor counts8->8. Tiny exact4 read succeeds; cap3 and growth4->5 refuse. These are bounded observations, not a claim that every OS exception has been simulated.

## M01 — closed within scoped offline review

The shared recursive `_json_fact_equal` distinguishes bool/int/finitefloat and compares full object keysets/list elements. Every actual use was inspected: recursive calls560/566; seal row alignment3019/3026/3029; release/source canonical comparison3220/3222; top/row exhaustive content comparison3307/3316. Call graph details are in static-audit.json. This is an active public QS path, not an unused helper.

The genuine baseline passes16 rows with16 submissions/34 reserved provider calls. Caller attempted true->int1/float1 and providerint1->true/float1 now reject at their content bindings. Nested source identity/bytes and release baseline/elapsed/GPU sample numeric type substitutions unresolve with aggregatefalse. Extra top/row fields reject; source/release/GPU extras unresolve. Optional native evidence fields added only by caller also unresolve. Missing source, null release, storage integer0, cleanupnull and malformed baseline remain unknown. Conservative evidence overlays remain effective, and published observations cannot be replaced by caller observations.

Seal-only ordinal true/1.0 updates only seal bytes and canonical hash/length binding; execution rows remain untouched by `_rewrite_seal`, and QS refuses with QS_SOURCE_PLAN_ORDER_INVALID. The replay's `execution_rows_unchanged` convenience flag compares two different fixture runs and is false; it is not used as proof. Helper body and retained combined test assertions establish the intended unchanged-within-run setup.

Published unknown error cannot become resolved under caller-known error; published knownFAIL suppliedPASS remains resolved/notusable; publishedPASS callerknownFAIL remains resolved/notusable and can retain aggregate when9/10 images+6/6 videos meet fixed thresholds. The original three canonical-verdict cases are AST-identical and present in the232 run. Independently verified critical3 remains visible and forces globalFAIL in replay. No all-technical-success rule or threshold change was introduced. Total coherent rewrite of both trusted originals remains outside signature obligations; parent archive/attestation is still required.

## Prior closures and test obligations

All206 prior collected nodeids remain in the232 collection;155 prior definitions, decorators, bodies and old helpers are AST-identical,0 adapted/0 deleted.25 added definitions produce26 new cases. test-obligation-audit.json records all new assertions/calls/lines and exact nodeid set differences. The new typed tests drive public QS after genuine `_own_run`, assert target reason and unresolved/refused outcome; the seal cases rebuild only seal length/hash, while named-entry tests fire during the selected artifact inode read and verify unchanged bytes. Literal-equality, tiny bounded/growth, FD cleanup and receipt-keyset checks are focused owner checks, not a substitute for public QS evidence. The new cases cover current-read handoffs; they do not cover the earlier-read completion counterexamples above.

M08 complete label/full descriptor alignment remains closed, including strict ordinal residual now fixed under M01. Source row labels, order, full five-part identities, path/bytes/hash and swaps remain checked. NM04 is preserved: all driver submissions/limit/submit getters resolve before final bounded ORIGINAL sealed-source validation, then one coherent clock/proof/ownership guard precedes reservation/attempt charge/cachedsubmit. No extra getter/callback/clock appears in that interval; no refunds/retries. Original NM01 capacity/time accessors and NM02 exact10800/oneover10801/laterproof tests remain AST-identical and pass. Earlier M02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent concrete regression. See closure-map.json.

Real ControlledImageOwner/BridgeOwner/public production nodes and oracles are exercised; only synthetic provider, HTTP and tiny decoder are substituted. Fresh4x4PNG/tinyfakevideo remain bounded and locally owned. Fixed16/34, score>=8,images8/10,videos5/6,critical0, raw/storage/cleanup and production owner source remain unchanged.

## Source, retained history and cleanup bindings

- `tools/v0_s3_quality_phase.py`: `c01b0103dcf436c8604a70234cef21978a0b52c644692db33b2612bd64105c67`
- `tools/test_v0_s3_quality_phase.py`: `9771baf7b68566a9b379de40a1474d821c3e2b3d7de54b796e0dcd6653e53456`
- `reports/v0-s3/product-gate0/p3b-quality-contract.md`: `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`
- `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`: `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`
- `reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py`: `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8`
- `reports/v0-s3/product-gate0/implementation-p3b-correction-06/probe_correction06_counterexamples.py`: `6892409b377a737dd6161f55d33d0067aeceefe5ff6f5ac8f454805229c5a966`

All four independent invocation receipts bind source/runner/probe before+after, actual imported absolute module paths/hashes and raw byte lengths/hashes. Guard mode imports no product module. The replay adapter asserts the immutable original probe hash before compile; static/final binding reads verify it after execution (its SystemExit exits before the adapter's trailing assertion). Runner hashes bind the adapter separately. Candidate argument is not attestation.

Independently verified31 repo-relative checksum entries, all6 final implementation raw streams, and final2 source identities. The earlier root pack-relative resolver mistake was not an artifact defect. static-audit.json additionally retains exact declared historical output paths and moved retained paths, stream hashes,8 diagnostic/final receipt bindings and true exits: dev-focus-1=0,dev-focus-2=1,dev-focus-3=0,dev-focused-1=0,dev-suite-1=0,final focused/guard/suite=0. Earlier test hashes052502… and b12a12… are preserved, not recertified from final9771ba… green. Actual runner/probe hashes and import paths for each historical invocation remain recorded. No historical raw was regenerated or relabeled. Original correction03 unguarded12 stay UNKNOWN/uncredited under immutable erratum; no cosmetic reruns.

All four runner-owned roots were removed. Targeted script registers each fixture root, restores its owned rename handoffs where necessary and removes its own root; replay root is inside the enclosing runner-owned root, whose removal is recorded. No old root was scanned/deleted. Only new text files in this review subtree are authored. No product/tools/tests/contracts/projection/quality/prelabels/coordinate/manifest/old reports modified; no binaries/DB/ZIP/copied product source, push or permanent configuration. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint all0. No testSource/holdout/fullprelabels read.

Parent owned original archive/retained attestation and selectedroot binding remain NOTPROVEN; parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER. Native residue/admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN. Machine synthetic checks and this independent review do not complete any product Stage.

## Ten-field handoff

1. current coordinate: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY_FOR_REVIEW"}

2. this batch: Independent CHANGES_REQUIRED F0/M1/m0;232 product cases once,guard4 once,replay22 once,targeted33 observations once

3. last passed gate: {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}

4. current blocking gate: S3_P3B_CORRECTION06_ISOLATED_REVIEW_PENDING

5. route position: Root adjudication -> bounded component correction -> isolated independent review -> parent/native/A06/Gate0 -> finite real quality and human/release gates

6. remaining work: ["NM03 earlier-read named entry custody remains Major", "Parent original archive/retained attestation and selected-root binding NOTPROVEN", "Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; synchronous callbacks not preempted", "Native residue/admission and A06 enforcement/attempt observation NOTPROVEN", "Actual registration baseline, installation and rollback NOTPROVEN", "Authentic parent ledger debit NOTPROVEN", "Real quality16/full12/productGate0/human-release NOTPROVEN"]

7. next owner: Root architecture/gate owner for disposition; implementation remains separate from review

8. authorization: Already authorized offline independent review only; no new human approval required; no actual product runtime authorization inferred

9. evidence directory: reports/v0-s3/product-gate0/independent-p3b-correction-06/

10. exact stop reason: Assigned review completed; hand off report/counts/full commit SHA; keep terminal visible

## Full V0–V3 outline from current root

Source: gitshow08caf9f only; current Stage **R1**. No progress counts or implementation/machine/independent/human states are changed by this component review. Full source evidence references and early-slice scope are retained in root-current-control.json and receipt.json.

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
