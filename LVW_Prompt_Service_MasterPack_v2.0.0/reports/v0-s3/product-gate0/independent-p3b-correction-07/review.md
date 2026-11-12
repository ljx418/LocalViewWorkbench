# Independent P3B correction07 aggregate review

**CHANGES_REQUIRED — Fatal0 / Major1 / Minor1.** Component recommendation only; no StagePASS or productPASS. All six previous named-custody counterexamples are now closed. NM03 resource/error closure remains incomplete: a post-open metadata failure leaks an unregistered descriptor; capacity is checked after the excess open.

Code `fd96cbc37574b382f483e757e8d7235ed5d2598c` and evidence `55e5463ae1bd1dd9f6c9c19bda347fe5900051ff` were integrated using the requested `git merge --no-edit`: evidence fast-forwarded the clean existing review worktree, and code was already an ancestor. Root intake/current outline was read only by gitshow `5f7701988f25cb2a52cc27900856d8750e29a449`. AGENTS, governance/routing, frozen contract/projection, prior review4fb52ff and root adjudicationd0cc0f9 were inspected. Implementation statements were navigation only. No rootmetadata/V2 merge was added beyond actual evidence ancestry.

|Invocation, once each|Result|Inner / outer true exit|
|---|---|---|
|Combined suite|245 passed in92.45s|0 / 0|
|Guard selftest|4 audit events blocked|0 / 0|
|Immutable correction07 replay with output-only adapter|8 observations, including6 intended counterexamples refused|0 / 0|
|Independent bounded targeted observations|20 observations, including2 cleanup defects and1 admission defect|0 / 0|

All executable product/test observations used the inspected immutable correction05 runner. Its auditguard installs before pytest/plugins/ANY product/test imports; plugin autoload, cache and bytecode are disabled. connect/bind/DNS/Popen/system/exec/spawn/fork are blocked. This is named Python audit coverage, not native direct-syscall immunity. Exact argv/cwd, raw stdout/stderr byte hashes/lengths, imported absolute paths/hashes and true inner/outer exits are retained. Exit0 for an observation means capture completed, including reproduced defects; observations are not extra product tests. No focused13 separately, old22/33 matrices,232+13 separately, capmatrix, P3A121/P2B237 or fullproject run.

## Major NM03-R1: ownership gap on a post-open metadata failure

**Locations:** tools/v0_s3_quality_phase.py:2822 `_open_child_directory`,2850 `_open_leaf`; transfer callers2948/2965.

**Trigger and expectation:** In a fresh four-byte fixture, let the actual boundary's os.open succeed, then inject one ordinary OSError(EIO) into the first fstat of that new descriptor. Every successful open must be owned immediately and released if acquisition refuses, including before custody insertion.

**Actual:** Both leaf and child-directory hooks fire exactly once. `boundary.close()` leaves the opened descriptor alive and procfs count rises8->9 in each isolated observation. The descriptor is absent from both `_fds` and `_custody`: fstat runs before guarded cleanup or ownership transfer. The probe measures the leak, then explicitly closes that known descriptor, restoring8. This is owner-level injected error evidence, not a claim to have observed an actual OS EIO or this injected error through public QS. Public QS uses these same helpers and finally calls this same boundary.close, so source inspection establishes that its cleanup cannot find the unregistered descriptor.

This is an existing open-helper gap within the explicitly assigned NM03 resource/error obligation, not a reopening of an unrelated historical closure. Scores fail closed, but repeated metadata failures can accumulate FDs outside the registry; unconditional cleanup/finite-FD claims are unsupported. Recommend keeping every successful open under cleanup ownership until safe custody transfer. No fix was made.

Evidence: targeted-observations.json `postopen_fstat_error_leaf` and `postopen_fstat_error_directory`; targeted raw stdout, inner receipt and outer receipt. findings.json records complete locations/trigger/expected/actual/evidence.

## Minor NM03-r2: cap admission happens after the excess open

**Locations:** tools/v0_s3_quality_phase.py:2649 `_NamedCustody.take`,2948 `_retain_directory`,2965 `_retain_leaf`.

**Trigger and expectation:** Fill custody with72 distinct four-byte leaves, then request a73rd. The internal cap72=4*(16+2) must refuse after a dedup miss and before any excess open.

**Actual:** Exact72 succeeds, all old entries remain, and final close returns8. The73rd request nevertheless performs one actual os.open, growing procfs count84->85 transiently; only then does take close that new FD and raise `QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:f72`. Admission is late. Normal retained use remains finite and no aggregate was incorrectly accepted; severity is Minor because this observation is one extra transient descriptor, not unbounded normal growth. Recommend capacity admission before opening a new distinct entry, with exception-safe transfer. The cap is internal, not a public threshold or a demand to alter the frozen16 shape.

Evidence: targeted-observations.json `exact72_oneover73_admission`, raw targeted output and receipts.

## Named lifetime, final completion and deduplication now hold

`_NamedCustody.take` stores `(parent_fd,name,originalidentity,kind,actualfd)` on first acquisition. All parents are either the pinned phase anchor or previously retained directories. `_retain_directory/_retain_leaf` find by pinned parent FD and name, verify the original identity/current no-follow name, and return the original descriptor. They do not reopen/adopt replacements. `_verify_custody_entry` compares fstat of the actual held FD to the original identity, then checks the current parent-relative name/type. `read` resets offsets with lseek, validates the current chain and invokes whole-boundary verify after the read. Public recompute_scores uses the same boundary for canonical, seal and raw reads and calls final verify at3638 before return, then closes in finally. No earlier entry is silently dropped. The duplicate branch in take is not used by ordinary repeated-read callers because their verified find returns first; all parent FDs remain owned until close, so ordinary dedup keys cannot acquire recycled-descriptor aliases.

The immutable replay's six intended hooks all fire exactly once with unchanged genuine originals/caller receipts: canonical symlink during seal read; canonical same-byte plain replacement during raw0; seal missing during raw0; raw0 leaf symlink during raw1; raw0 parent plain replacement during raw1; canonical redirect immediately before final completion verify. All refuse at the intended source-plan/raw/custody checks. None is a setup-only refusal and none aggregates. Clean genuine baseline remains16 submissions/34 reservations,10 usable images/6 videos/critical0.

Nine independent adjacent/final cases also refuse: canonical missing; seal plain/symlink; raw0 leaf plain/missing; raw0 parent missing/symlink; seal missing at completion; raw0 parent plain at completion. Every hook fires1, retained original SHA and caller receipt stay unchanged, and FD counts return8->8. Three same-name repeated-read replacements (plain/missing/symlink) refuse with the original registry entry and descriptor identity unchanged.

Finite normal FD proof: full16 shape consumes35 distinct entries:2 top leaves+shared rows directory+16 row directories+16 raw leaves. Four anchor descriptors add39 to the observed baseline8, giving47. Three full rereads keep47 and the exact original registry; idempotent close returns8. Replay's three-name/eight-repeat observation independently holds5 entries and17 FDs, closing to8. At the cap, normal owned FDs are4+72, and the implementation has the one transient extra open described above. This bound excludes unrelated host FDs and fails as an unconditional error bound because of NM03-R1. Constructor refusal and retained read/lseek/stat errors close back to8; the two new pre-transfer fstat errors are the explicit exceptions. No universal host concurrency, hostilekernel or nativeWindows guarantee is demanded.

## Prior closures and original obligations preserved

All232 prior nodeids remain in the245 collected suite; all180 original test definitions/decorators/bodies and old helpers are AST-identical,0 adapted/0 deleted.13 added definitions generate13 cases. test-obligation-audit.json records each new test's assertions/calls/locations. Seven new handoff/final tests invoke public recompute_scores after genuine owner runs, assert fired hooks and target errors; success/refusal cleanup and baseline also use public QS. Three repeated/growing-byte/FD tests directly exercise the actual boundary owner. These are appropriate focused owner checks, not replacements for public QS tests. They omit post-open fstat failure and pre-open cap admission, explaining the remaining findings despite245 green.

M01 remains closed: active recursive `_json_fact_equal` compares JSON types including bool/int/finitefloat, full keysets and list elements. Actual call sites in seal alignment, release/source binding and exhaustive top/row content checks were inspected; static-audit.json lists them. Typed equality/strict integer seal ordinals, closed top/row/source/release/GPU keysets and monotone verdict handling are unchanged. Supplied facts cannot replace canonical facts; unknown failures cannot become known, knownFAIL stays resolved/notusable, conservative downgrade remains allowed, and critical3 remains visible and forces failure under the preserved tests. No all-technical-success requirement was added.

M08 full seal label/order/source identity/path/bytes/hash alignment and NM04 final original-source check remain closed. The inspected `_execute_row` resolves all driver getters including cachedsubmit, then validates the sealed ORIGINAL source, takes one coherent clock/proof/ownership guard, reserves provider budget, charges attempt and calls cachedsubmit. No new getter/callback/clock appears in that interval. Original capacity0/clock10801/exact10800/oneover10801/laterproof/no-refund/no-retry tests remain AST-identical and passed in245. M02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent regression. closure-map.json preserves prior mapping and explicitly splits NM03 lifetime closure from current resource issues.

Fixed16/34 calls, images8/10, videos5/6, score>=8, critical0, raw preservation/storage/cleanup remain unchanged. Actual public production nodes, ControlledImageOwner/BridgeOwner and production oracles run with only synthetic provider/HTTP/tinydecoder substitutions. Fresh4x4PNG/tinyfakevideo remain within owned bounded roots; no real decoder/server was used. A coherent rewrite of BOTH trusted originals remains outside the signature obligation. Parent archive/retained-attestation selectedroot binding is a real integration prerequisite, not arbitrary unbound archive trust.

## Evidence identity, retained history and scope

- `tools/v0_s3_quality_phase.py`: `e670b330f239ab931ab512dcf6f13ec8b3ec35b0d3932d88e8198b94c34bac22`
- `tools/test_v0_s3_quality_phase.py`: `fdda5ed7bc5ccfa8bc2f61f8b8a81f4713905a0fd689a2cd066995ceff6e7b0d`
- `reports/v0-s3/product-gate0/p3b-quality-contract.md`: `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`
- `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`: `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`
- `reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py`: `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8`
- `reports/v0-s3/product-gate0/implementation-p3b-correction-07/probe_correction07_counterexamples.py`: `dc4cc52a4990b9668014ae0618d9e72a5ec3b88c98c23ee12068afd1b44d5392`

All four independent receipts bind source/runner/probe before+after and actual imported paths/hashes; guard imports no product module. Replay adapter verifies immutable probe bytes and changes only OUT in the in-memory program before execution; the immutable probe's filename remains its own. The runner additionally pins the adapter. Static/final reads bind the original probe before/after. Candidate argument is never attestation. Read-only Git/AST/hash auditing imports no product/test code and is separate from guarded execution.

Independently checked all25 implementation checksum entries and retained raw stream bindings (the8 final streams plus4 retained debug streams); no mismatch. All6 debug/final implementation invocation exits are0. Per-invocation source/runner/probe/import identities remain in static-audit.json; diagnostic paths moved under debug are resolved to retained bytes without relabeling. Earlier diagnostics and any historical source changes remain as recorded, not regenerated or recertified from final green. Original correction03 unguarded12 remain UNKNOWN/uncredited under the preserved erratum, with no cosmetic rerun.

All4 runner-owned roots and registered replay/targeted roots were removed. The targeted root owns its declared tiny/broken children. Explicit probe remediation closed only the two known leaked descriptors after measurement; runner removal is not proof that the product closed them. No old root was scanned/deleted. Only new text under this review subtree is authored; no candidate/tools/tests/spec/oldreports/runners/logs/checksums/coordinate/manifest were changed. No binaries/DB/ZIP/copied product source, push, permanent config or history rewrite. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint all0. No testSource/holdouts/fullprelabels were read.

Parent owned original archive/retained attestation and selected-root binding remain NOTPROVEN. Parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; native residue-admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN. This component review completes no product Stage.

## Ten-field handoff

1. current coordinate: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY_FOR_REVIEW"}

2. this batch: Independent CHANGES_REQUIRED F0/M1/m1;245 product cases once,guard4 once,replay8 observations once,targeted20 observations once

3. last passed gate: {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}

4. current blocking gate: S3_P3B_CORRECTION07_ISOLATED_REVIEW_PENDING

5. route position: Root adjudication -> bounded resource correction -> isolated review -> parent/native/A06/Gate0 -> finite real quality and human/release gates

6. remaining work: ["NM03-R1 descriptor ownership on post-open error", "NM03-r2 capacity admission before excess opens", "Parent owned original archive/retained attestation and selected-root binding NOTPROVEN", "Parent hardwatchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", "Native residue/admission and A06 NOTPROVEN", "Registration/installation/rollback NOTPROVEN", "Authentic parent ledger debit NOTPROVEN", "Real quality/full12/productGate0/human-release NOTPROVEN"]

7. next owner: Root architecture/gate owner for disposition; implementation remains separate

8. authorization: Already authorized offline review; no new human approval required and no product runtime authority inferred

9. evidence directory: reports/v0-s3/product-gate0/independent-p3b-correction-07/

10. exact stop reason: Assigned independent review completed; hand off full local commit SHA/report/counts and keep terminal visible

## Full V0–V3 outline from root gitshow5f77019

Current Stage **R1**; this component review changes none of these implementation/machine/independent/human counts. Full source and evidence paths are retained in root-current-control.json and receipt.json.

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
