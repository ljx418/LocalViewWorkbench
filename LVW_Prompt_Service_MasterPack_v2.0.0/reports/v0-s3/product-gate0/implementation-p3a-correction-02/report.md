# P3A correction02 — READY_FOR_REVIEW

Candidate `db607d484e9627b8be8b27d581d9d174ea4a9e63`; root contract commit `1a553726c67c35a0c82aab54d409eb9abcb4ff45`. Author ljx418 <1173696783@qq.com>. Public contract_changes=none. Self-check only; separate independent review and root adjudication remain pending.

## Complete unchanged V0–V3 outline

| Delivery | Stage | Done/declared | Boundary |
|---|---|---:|---|
|V0|V0-S0|1/2|历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS|
|V0-Min|V0-S1|5/5|已签仅V0-Min|
|V1前置|R0|1/2|仅R1a前置单图子集可确认；不把完整视频/Q01算通过|
|V1早期切片|R1a|5/5|已签仅单图切片；完整V1未完成|
|V0.1|V0-S2|7/8|Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain.|
|V0.2|V0-S3|0/6|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V1|R1|0/4|最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。|
|V1|V1-M1|0/3|用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署|
|V1|R2|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V2|R3|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V2|R4|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5a|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5b|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|V3|R5c|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|

V1-D0 preparation 2/2; unified early slice 3/3 accepted only within its signed scope. Counts are unchanged. Current coordinate: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3A_CORRECTION_02_IMPLEMENTATION", "state": "PREPARING_NEXT_STAGE"}.

## Ten fields

1. 当前坐标: R1 / WP-R1-U3, root-directed P3A correction02; product Gate0 remains pending.
2. 本批完成: lifecycle persistence correction for M03; 54 targeted + 23 S2 + 5 unchanged independent-authored probes freshly passed, 82/82 with exit0. Implementation READY_FOR_REVIEW; no isolated review verdict, product machine acceptance or human signoff claimed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW at621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped prior human acceptance.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING; root awaits separate M03 correction review.
5. 全局路线位置: P3A correction review → complete coordinator/quality/A06 → offline combination review → product Gate0 → finite same-source execution → independent acceptance → required human signature.
6. 剩余工作: independent reviewer verifies candidate; root adjudicates M03 and remaining S3 profiles/budgets/network/rollback/quality requirements.
7. 下一责任人: separate reviewer, then root architecture/gate owner.
8. 所需授权: none additional for completed offline scope; this component authorizes no real execution.
9. 证据目录: reports/v0-s3/product-gate0/implementation-p3a-correction-02/; report, receipt, audit runner, raw commands/stdout/stderr/exits/cleanup and SHA256SUMS.
10. 精确停止原因: assigned minimal lifecycle correction and finite checks complete; READY_FOR_REVIEW only, no Stage/PASS/human/release claim.

## Minimal seam and lifecycle

Changed only tools/v0_s2_stage_runtime.py, tools/v0_s3_stage_runtime.py and appended tests in tools/test_s3_install_handoff.py. The package owner and original P3A tests are unchanged. The prior handoff tests remain unchanged before the appended correction02 cases. No independent probes, historical raw, contracts, authority, budgets, MANIFEST or coordinate were edited.

Base seam: StageRuntimeFactory._prepare now delegates its final failure record to _persist_preparation_failure(label,root,failure). The default method executes the same old root.exists() and exclusive pathname write, preserving legacy S2 semantics and exception behavior. No preparation algorithm was copied. S3 retains the actual inherited _prepare method (the original test asserting method identity still passes).

S3 call path: prepare_default/prepare_warm → thin _with_preparation context → open original evidence parent with directory_handle (no-follow ancestor descriptors) → inherited _prepare → archive.register then pin the verified original root descriptor → unchanged protected deployment owner → inherited remaining preparation → overridden persistence hook on any failure → close root descriptors and parent context in finally. Errors before the inherited handler, such as complete-binding failure, also preserve a terminal in-memory record and attempt safe persistence.

The existing archive wrapper now pins the root immediately after registration and verifies parent/root identities before invoking inherited archive deletion. Factory authorization boundaries and sample copies verify lifecycle identities before proceeding; a parent move after deployment is rejected before further staging/startup. Failed protected installs still use the prior retain/no-pathname-rollback policy. Parent/root drift therefore cannot authorize pathname deletion of a replacement directory.

Terminal failure writes use only the pinned original parent descriptor, O_CREAT|O_EXCL|O_NOFOLLOW, a fixed single relative filename, a bounded write of the existing failure record, fsync, and finally-close. They never fall back to self.directory.open. If the parent inode was renamed, the record goes into that original owned inode; replacement parent receives no files. The original error is always re-raised; conflicts, open/write/fsync failures become PERSISTENCE_UNPROVEN memory diagnostics and do not mask it. Existing failure files are not overwritten.

Conservative persistence semantics: serialized bytes retain PERSISTENCE_UNPROVEN and explicitly state that they record an attempt; only factory.preparation_failures[label] changes to PERSISTED after the write and fsync return. This avoids a complete-looking on-disk record falsely claiming durability when fsync fails. Partial/empty failed records are retained, never overwritten or deleted to manufacture success. The error/candidate/run/deployment/native cleanup/archive-retention record remains in memory even when persistence is unproven.

root_retained uses the pinned original root descriptor: matching device/inode and positive link count means the original directory still exists, including under a moved parent. Zero links can substantiate namespace removal of that original object. Missing/unusable root proof yields null with UNKNOWN observation, not false from absence at the stale pathname. Early failures before root registration correctly record null.

## Actual tests and diagnostics

| Run | Passed | Failed | Denominator | Exit |
|---|---:|---:|---:|---:|
|targeted-01|52|1|53|1|
|targeted-02|54|0|54|0|
|regression-01|23|0|23|0|
|probes-01|5|0|5|0|

Fresh final denominator82 = original44 + ten new lifecycle cases + old23 S2 + five independent-authored assertions. This is implementer execution of the unchanged independent probes, not a new independent review verdict. Original four historical observation probes were not rerun.

New cases drive actual inherited prepare: parent replacement at protected receipt save; post-deployment copy error; parent move immediately after deployment; early binding failure; ordinary deployment failure; existing failure-file conflict; open/write/fsync persistence failures; successful lifecycle release. They assert original error identity, original parent receipt or explicit unproven memory terminal, true/null retention from original objects, zero replacement writes/startup, unchanged foreign/sibling sentinels, and closed captured descriptors.

The unchanged M03 independent probe now reports replacement_writes=[], failure_at_original_parent=true, service_starts=0, all20 protected-owner descriptors closed. The ten new cases additionally track lifecycle descriptor closure and inspect the original root retention record. All five independent assertions ran once unchanged and passed.

Targeted-01 is retained as52 pass/1 fail/exit1: the new fsync fault injector unintentionally failed the earlier archive-register lease fsync, so the original error was correctly that sync error rather than the intended deployment error. The injector was narrowed by descriptor identity to only the terminal failure file; a direct write-error case was added and persistence uses os.write/finally-close so acquisition/write failures cannot leak its fd. Targeted-02 passed54, followed by23 regressions and the five unchanged probes. This is one evidence-producing correction, not repeated no-progress repairs.

Package owner source is byte-identical to5497bd1860ae895f394ece23a1ddb5e0b22fad92. Its prior17 tests are reused explicitly from independent review e9c910e881572691449dc70da569abee0dc4b195; raw/owner-evidence-reuse.json binds the prior stdout and package source hashes. They were NOT rerun and are NOT added to the fresh82 denominator.

Exact commands are in raw/*.command.json with original stdout/stderr/actual exits. The focused audit runner disables external plugins/cache/bytecode, records temporary roots, permits Git only in newly created synthetic repositories, and blocks all other subprocess/shell/exec/network actions. Regression mode permits no children. No P2B or broad/full suite was run. Initial worktree was clean; required merge --no-edit1a553726c67c35a0c82aab54d409eb9abcb4ff45 fast-forwarded, exit0. Source/staged checks and immutable-boundary/package-owner diff checks exited0.

## Cleanup and limitations

All265 registered temporary paths across four runs were absent after completion (raw/cleanup-summary.json). Production-retained original runtime roots and partial failure records were removed only by their newly owned synthetic fixture parents; no old roots/ledgers/claims were inspected or cleaned. No DB/archive/source-tree snapshots or permanent configurations were committed. Historical failures, including targeted-01 here, remain raw and unnormalized.

Actual Windows/WSL/PowerShell/parser/host-executable hashing, real media/model/GPU/services/network/download, real or old program ledger/claims and full checkpoints remain0. Tests substitute native service boundaries and use real package building/installing and inherited preparation/archival owners.

POSIX/Linux directory descriptors and no-follow semantics are the tested support boundary. No native Windows guarantee is made. As previously disclosed, descriptors pin owned object identity, not immutable namespace location; writing the original owned parent after it is moved is intentional and permitted. A concurrent hostile movement of an owned inode at a syscall boundary is not universally prevented; replacement inodes are not authorized by a stale pathname.

Complete S3 coordinator/profiles/budgets, A06 network enforcement and outbound-attempt observation, actual install/rollback acceptance, fixed quality/resource gates, product Gate0, independent correction approval and required human signatures remain outside this offline component proof.
