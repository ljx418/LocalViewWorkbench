# Independent P3B correction08 aggregate review

**ACCEPT_COMPONENT_SCOPED_OFFLINE — Fatal0 / Major0 / Minor0.** Both assigned resource findings are closed within the audited cooperative offline scope. This is a component recommendation for root disposition; no StagePASS, productPASS, Gate0 or human signoff.

Candidate `6c9a0a07c66060e53b00e690ebdd98047167511d`; evidence `833c8476f03ef96983cbc84871a8ea24fb42449e`. The requested merge fast-forwarded the clean existing review worktree; code is an ancestor of evidence. Root intake/current outline were read only through gitshow1b93f17, with no extra rootmetadata/V2 merge. AGENTS, governance/routing, frozen P3B contract/projection, prior review9d2c51d and adjudication94ade2a were read; implementation claims served as navigation.

|Independent invocation, once each|Result|True inner/outer exit|Runner duration|
|---|---|---|---|
|suite|257 passed in79.39s pytest|0/0|85.147s|
|guard|4 audit events blocked|0/0|0.003s|
|replay|5 immutable resource observations,0 violations|0/0|4.527s|
|targeted|25 new bounded resource observations,0 violations|0/0|1.514s|

All product/test execution used the inspected immutable correction05 runner, which installs its auditguard before pytest/plugins/any product or test import. Plugin autoload/cache/bytecode are disabled; connect/bind/DNS/Popen/system/exec/spawn/fork are blocked. Outer invoke.py only captures the child runner and imports no product/test modules. Exact argv/cwd, actual imported paths/hashes, before/after source/runner/probe identities, raw streams/lengths and true exits are in the per-invocation receipts and aggregate receipt.json. This is named Python audit coverage, with no direct-syscall immunity claim.

NM03-R1 is closed: `_open_child_directory`2894 and `_open_leaf`2929 keep each successful open inside exception cleanup through fstat, named stat, type and identity validation. Their callers3032/3063 reserve before opening, cancel on failure and transfer into `_NamedCustody.take`2682. Registry insertion and FD-list append share rollback; previous entries remain owned. Constructor2798 catches partial acquisition and closes previously registered anchors; append-failure branches close the newly acquired descriptor before propagation. Custody closes children in reverse order before anchor descriptors; repeated close clears all references and does nothing.

Independent owner injections cover open, first-fstat EIO, named-stat EIO, wrong type, changed identity, insertion refusal and FD-list transfer refusal for both child directories and leaves, each with an existing genuine entry retained. The post-open hooks fire once; the target descriptor is closed once before boundary.close, no live target remains, prior entries verify unchanged, reservations return0 and a subsequent retry admits normally. FD counts return8 after boundary.close. Close instrumentation shows no duplicate close; a fresh reused descriptor survives another boundary.close. No probe remediation closes leaked product FDs. Constructor open failures at acquisitions1–4 and first-fstat failures at levels2–4 close every actual acquisition once and restore8; constructor append-failure branches were source audited, not independently injected.

Public `recompute_scores`3736 reaches the same precise post-open EIO for both the canonical leaf and the first raw row child directory. Both hooks fire1, no score result returns, each acquired FD closes once in the same finally3760, and8->8 is measured. This distinguishes failed scores from successful resource cleanup; it does not claim an actual operating-system EIO occurred. The immutable replay independently reproduces both owner faults and a public canonical fault.

NM03-r2 is closed: `_NamedCustody.reserve`2654 checks entries plus pending reservations after dedup misses and before os.open. Exact72 distinct four-byte leaves produce72 entries/opens; the73rd refuses with ZERO extra opens and no transient FD growth (high-water84 stays84). All72 retained entries verify and every repeated name reuses the original descriptor with zero opens. Refused open/metadata/insertion/transfer paths cancel their reservation without losing earlier custody. Final close restores8. The cap remains internal72=4*(16+2), not a public threshold. A genuine public16 evaluation retains35 entries,0 reservations, all parent references owned,47 FDs at final close and8 after; it aggregates with the existing fixed quality rules.

Evidence for each assigned finding, locations/trigger/expected/actual/limits and prior closure mapping appears in findings.json. Raw targeted output retains all25 observations; replay output retains5 observations. Observations are not additional product tests. The output-only replay adapter checks the immutable probe hash before and after and changes only its OUT assignment in memory; the immutable source filename is retained.

All245 prior nodeids remain in257. All193 prior test definitions, decorators/bodies and old helpers are AST-identical,0 adapted/0 deleted;12 added definitions generate12 cases. Each new case has inspected assertions/calls/locations in static-audit.json. The owner tests reach their post-open/type/identity/insertion/admission conditions; the public test reaches canonical fstat EIO; the constructor test reaches first level fstat; the genuine16 test consumes actual canonical/seal/raw names. They passed without procfs skips on this host. The retained old-candidate negative control shows10 failures/2 passes and inner1; four failures reflect the new reserved() API absent in old code, so10 is not10 independent leak reproductions. It supplies useful discrimination, not current-candidate failure counts; it was not rerun.

Named custody lifetime and the six earlier-read/completion substitutions remain closed: their original tests run within257 without adaptation, not through a redundant old replay. Canonical symlink during seal read, canonical same-byte plain replacement during raw0, seal missing during raw0, raw0 leaf symlink during raw1, raw0 parent plain replacement during raw1, and canonical redirect before completion still refuse. No old broad8/20 histories, focused12 separately,245+12 split, capmatrix, P3A121/P2B237 or fullproject run was performed.

M01 recursive typed facts/full keysets, M08 full seal order/label/source identity/path/bytes/hash alignment and NM04 final original-source ordering remain intact. Apart from the two resource-owner classes and the new close helper, prior top-level product definitions are unchanged. Actual QS typed-equality call sites3313/3320/3323/3514/3516/3601/3610 and public final verify3757 remain active. `_execute_row`1743 resolves driver getters/cached submit,1750 validates the sealed ORIGINAL source,1758 performs coherent clock/proof/ownership guard,1763 reserves,1767 charges,1770 invokes cached submit with no intervening driver getter/callback/extra clock. Exact10800/oneover10801/laterproof/no-refund/no-retry and capacity0 regressions remain in the original passing suite. Fixed16/34,score>=8,8/10 images,5/6 videos,critical0; knownFAIL resolved/notusable, unknownFAIL unresolved, critical3 visible, raw storage/cleanup are preserved. No all-technical-success rule or total trusted-root forgery/signature obligation was added; olderM02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent a regression.

The precommit debug-suite is an **actual execution-discipline deviation** from the focused-editing plan. It remains diagnostic, not final committed acceptance, and later green does not erase it. Retained stdout says257 passed90.67s; its runner receipt records95.06s and inner0. The distinct final implementation suite records257 passed in83.51s (0:01:23); runner88.777s,inner0. The final focused12 is a distinct redundant invocation (11.427s runner,inner0) with no added coverage credit. No mandatory fresh correction just for prose or cosmetic rerun is recommended.

All37 implementation checksum entries and20 retained debug/final raw streams match. static-audit.json retains every historical source/runner/probe before/after hash, actual imported paths/hashes, inner exit and duration. Early debug-focused used testc57127dc… rather than finaleb8327f9…; first debug probe11981b44… exited1 for the missing projection binding, while final probee664f586… exits0. Negative control used old producte670b330… and exits1. Historical outer shell exits and absolute start/end timestamps are not in those inner receipts and remain UNKNOWN, despite prose claiming0/0; durations and content bindings are proven. No earlier logs were relabelled, regenerated or deleted. The prior429/taskresume/stop_unknown history remains; the task/root records explicitly restored the same Claude task and observed its resume. No settled implementer was reopened. Original correction03 unguarded12 remain UNKNOWN/uncredited under the immutable erratum.

All four runner-owned roots and registered replay/targeted roots were removed. FD cleanup was measured before filesystem teardown. Fresh4x4 PNG/tiny fake video fixtures use actual ControlledImageOwner/BridgeOwner/oracles through existing synthetic transport helpers; no real decoder/server or original quality sources/prelabels/holdouts were used. Only new text in this subtree was authored; candidate/tools/tests/spec/oldreports/runners/checksums/logs/coordinate/manifest remain unchanged. No copied product source/binaries/DB/ZIP, push, permanent config or history rewrite. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint are all0.

Limitations remain explicit: cooperative Python/filesystem observations, not universal concurrency/hostile-kernel/native-Windows/direct-syscall immunity or exhaustive allocation-failure certification. Parent archive/attestation and selected-root binding remain NOTPROVEN; parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; native residue-admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN.

Ten-field handoff (root gitshow1b93f17):

1 current_coordinate: {"gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "stage_id": "R1", "state": "READY_FOR_REVIEW", "workpack_id": "WP-R1-U3"}

2 this_batch: Independent component recommendation F0/M0/m0;257 cases once,guard4 once,replay5 once,targeted25 once

3 last_passed_gate: {"candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "cpu_checks": 212, "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "fixed_cases": 10, "gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "human_signoff": "reports/unified-media/human-signoff-live15.json", "passed_cases": 10, "receipt": "reports/unified-media/independent-live-15/receipt.json"}

4 current_blocking_gate: S3_P3B_CORRECTION08_ISOLATED_REVIEW_PENDING

5 route_position: Root disposition of independent review -> parent/native/A06/Gate0 -> finite real quality -> human/release

6 remaining_work: ["Parent owned original archive/retained independent attestation and selected-root binding NOTPROVEN", "Parent hardwatchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", "Native residue-admission/A06 NOTPROVEN", "Registration-installrollback NOTPROVEN", "Authentic parent ledger debit NOTPROVEN", "Realquality/full12/Gate0/human-release NOTPROVEN"]

7 next_owner: Root architecture/gate owner; implementation remains separate

8 authorization: Already authorized offline isolated review; configured default Codex, no override/new human permission, no product runtime authority inferred

9 evidence_directory: reports/v0-s3/product-gate0/independent-p3b-correction-08/

10 exact_stop_reason: Assigned independent aggregate review complete; hand off full local commit/report/counts; keep terminal visible

Full V0–V3 outline from root gitshow1b93f17, current Stage **R1**. This review changes no formal completion or human-signoff counts. Full evidence paths and substep statuses are in root-current-control.json and receipt.json.

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
