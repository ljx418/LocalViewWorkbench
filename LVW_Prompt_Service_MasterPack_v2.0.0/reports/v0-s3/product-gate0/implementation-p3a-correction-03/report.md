P3A correction03 — READY_FOR_REVIEW

Candidate: `e3f9427f17c38def9216813842195b94b490698f`. Evidence SHA is the commit containing this report, supplied in worker_done (no self-referential SHA). Author: ljx418 <1173696783@qq.com>. Root contract: `9aa110251c018ecaaefe4870b8047ef504bbc2de`, merged without reset from clean workspace. contract_changes=none(public). No gate, release, human acceptance or full-stage claim.

1. Current coordinate: {'stage_id': 'R1', 'workpack_id': 'WP-R1-U3', 'gate': 'S3_P3A_CORRECTION_03_IMPLEMENTATION', 'state': 'PREPARING_NEXT_STAGE'} (unchanged).
2. Batch completed: original-parent allocation, protected registration/directory/evidence seams, finite adjacent callback audit and appended fixed Oracles.
3. Last passed gate: UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, historical accepted scope only.
4. Current blocking gate: `P3A_EARLY_ALLOCATION_PARENT_BINDING_AND_S3_GATE0_PENDING` remains root-owned; this submission does not close it.
5. Route position: P3A deployment integration correction03 within S3 preparation, S3 0/6 unchanged.
6. Remaining work: isolated review/adjudication, remaining S3 product executor/Gate0 obligations and full profiles/network proofs.
7. Next owner: separate reviewer, then root coordinator.
8. Authorization: existing finite synthetic offline scope; no new human authorization needed, no real run authorized or performed.
9. Evidence: this directory; receipt.json, guarded_checks.py, raw commands/stdout/stderr/exits/guards and SHA256SUMS.
10. Exact stop: READY_FOR_REVIEW; no self-signing, push, Stage activation or checkpoint.

Changed production/test files (pack-relative): tools/v0_s2_stage_runtime.py, tools/v0_s3_stage_runtime.py, tools/v0_s2_stage_archive.py, tools/test_s3_install_handoff.py. All other new files are text evidence here. Original test assertions are unchanged: prior-handoff-tests-unchanged.json proves the historical file is an exact prefix. immutable-boundaries and package-unchanged checks both exit 0; source-check (git diff --check) exits 0. Frozen contracts, coordinates, MANIFEST, budgets, prior reports and independent probes remain unchanged.

Production call path: InstalledPackageRuntimeFactory enters its existing pinned-parent lifecycle, then inherited StageRuntimeFactory._prepare. Complete proof and authorization precede bounded descriptor-relative root allocation; real OwnedArchive registration writes its receipt through the optional internal protected persistence seam. Subdirectories are created relative to the allocated root descriptor, real package build/install and protected handoff remain the deployment owners, inherited samples/references/native preparation follow, and final preparation evidence is exclusive/no-follow relative to the original root temp directory. The inherited failure handler uses the existing protected failure writer while original descriptors remain open, then the lifecycle closes all handles. No duplicate _prepare algorithm, sourcecopy fallback, arbitrary command entry or replacement package owner was introduced.

Legacy defaults keep tempfile allocation, original mkdir behavior, pathname evidence persistence and original archive registration persistence. New base boundary hook defaults to no-op. S3 overrides guard controlled callback returns and use anchored actual writes; these guards are not presented as a universal instruction-level race guarantee.

Finite audit performed once, with its discovered gaps repaired in this aggregate candidate:

| Boundary | Production location / protection | Actual probe and finding |
| --- | --- | --- |
| complete → allocation | StageRuntimeFactory._allocate_preparation_root; S3 override at tools/v0_s3_stage_runtime.py:122 | audit complete-allocation reproduced foreign root before fix; now no replacement addition or service start. Unchanged M04 gap also passes once. Exclusive mkdir uses original parent fd, bounded 8 random single-name attempts and immediate no-follow root open. |
| authorize → registration/write | S3 factory and archive authorization wrappers; OwnedArchive.register and _persist_registration at tools/v0_s2_stage_archive.py:33,56 | audit authorize-allocation and archive-authorization reproduced effects before fix; postcallback guards reject. Registration-writer probe moves parent inside persistence; dirfd write reaches original inode only. |
| archive register/lease → subdirectories | S3 _pin_preparation_root and _prepare_directories at :136 | register-directories reproduced replacement child directories; fixed mkdir uses allocated root fd and no-follow child opens. True allocation identity is retained before registration, not falsely called registered. |
| deployment → sample/reference writes | S3 _copy at :236 and base callback boundaries | deploy-samples already rejected baseline drift with no new replacement writes; retained anchored/copy guards, added native callback-return checks. |
| native preparation callback → final evidence | base _preparation_boundary at :282; S3 _persist_preparation_evidence at :145 | native-final-evidence reproduced replacement JSON; now return-boundary checks reject and exclusive final writer is dirfd-relative. Native resource/ownership callbacks also checked. |
| error → receipt/delete | S3 _persist_preparation_failure at :195; _ArchiveCleanupBoundary.remove_owned_reparse_fixture at :42 | error-archive baseline already refused drift. Deeper cleanup callback probe reproduced replacement default-raw; narrow driver adapter now guards before/after that callback, preventing subsequent archive pathname mutation. No pathname deletion fallback. |

The allocation collision test preserves preexisting bytes after all eight collisions. Allocation no-follow open failure leaves the newly owned directory untouched and reports UNKNOWN because a reliable root descriptor was unavailable. On early parent drift before allocation there is no allocated identity: root_retained=null/UNKNOWN, archive_registered is not invented. When a root descriptor is available retention is derived from its device/inode/link observation, not stale path existence. Failure persistence is exclusive relative to the original parent: disk records PERSISTENCE_UNPROVEN as an attempt, memory acknowledges PERSISTED only after fsync. Original errors remain intact if persistence fails. Parent/root handles close on success and every tested failure; no native start or delete follows detected drift.

Actual executions (raw/<run>.command.json records exact argv; matching stdout.log, stderr.log, exit.log and -guard.json retain outcomes). Commands use python3 -B reports/v0-s3/product-gate0/implementation-p3a-correction-03/guarded_checks.py <mode> <run> from pack root.

| Run | Denominator | Passed | Failed | Errors | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| audit-before | 7 | 2 | 5 | 0 | 1 |
| targeted-01 | 64 | 64 | 0 | 1 | 1 |
| regression-01 | 23 | 23 | 0 | 0 | 0 |
| archive-01 | 9 | 9 | 0 | 0 | 0 |
| targeted-02 | 64 | 64 | 0 | 0 | 0 |
| probes-01 | 5 | 5 | 0 | 0 | 0 |
| gap-01 | 1 | 1 | 0 | 0 | 0 |
| cleanup-boundary-before | 1 | 0 | 1 | 0 | 1 |
| targeted-03 | 65 | 65 | 0 | 0 | 0 |
| regression-02 | 23 | 23 | 0 | 0 | 0 |
| archive-02 | 9 | 9 | 0 | 0 | 0 |

Final source fresh checks: 65 targeted (original54 + new11), 23 S2 and 9 archive =97, all exit0. The unchanged independent5 plus M04gap1 ran exactly once on the immediate precursor before the final cleanup-callback adapter; those six passed but are not falsely claimed as rerun on final source. Final targeted65 contains the added cleanup fixed Oracle and repeats the finite boundary assertions. Baseline five failures and cleanup failure are real reproduced gaps, preserved unchanged. targeted-01 had64 passed plus one teardown error: its new os.open injector outlived its test and blocked fixture cleanup; restoration before teardown fixed that test harness defect, without dropping an assertion or denominator.

Package owner17 is explicitly reused, not freshly executed: prior candidate `5497bd1860ae895f394ece23a1ddb5e0b22fad92`, independent evidence `e9c910e881572691449dc70da569abee0dc4b195`. raw/owner17-reuse.json binds prior stdout hash and byte/dependency check. Package owner and those parser/default installation/rollback tests do not depend on changed stage/archive modules. No P2B, full suite, earliest observation suite or checkpoint rerun.

Each temporary fixture was registered by the audit runner. raw/cleanup-summary.json covers all11 runs, preserving the one targeted-01 root left at run end; raw/targeted-01-fixture-cleanup.json records bounded cleanup of only that owned path. Every recorded path is now absent. No old fixture scan or cleanup occurred. Tests guard subprocess boundaries to allow Git only in newly owned synthetic repositories and prohibit socket connect/bind, shell/system/exec/spawn. No actual Windows/WSL/PowerShell/parser/host executable hashing, media, model/GPU, native service, network/download, real program ledger or old runtime work occurred. Synthetic fixture databases/packages are temporary and are not committed. No permanent configuration was written.

Platform/resource limits: Linux/POSIX synthetic anchored operations only; unsupported dirfd/no-follow platforms fail closed, with no guessed Windows guarantee. Original owned inode relocation remains the accepted limitation: descriptors may still address the moved owned inode. This is not a universal hostile-OS framework. The component proves deployment/lifecycle behavior under the finite contract, not full S3 resource profiles, offline networking or product quality. Historical failures stay historical. M01/M02/m01/M03 independent closures are not self-reissued here; new M04 and adjacent changes await isolated review.

Unchanged V0–V3 development outline (from execution-control; no counters advanced):

| Stage | Delivery | Completed/total | Existing meaning |
| --- | --- | --- | --- |
| V0-S0 | V0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-S1 | V0-Min | 5/5 | 已签仅V0-Min |
| R0 | V1前置 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| R1a | V1早期切片 | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0-S2 | V0.1 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0-S3 | V0.2 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R1 | V1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1-M1 | V1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| R2 | V1 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R3 | V2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R4 | V2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5a | V3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5b | V3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5c | V3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

Additional V1-D0 preparation remains2/2, accepted preparation only. Unified-media early slice remains3/3 accepted scope, separate from full R1. This report does not alter either claim.

Evidence staging check exited2 solely for pytest failure-output trailing spaces in the preserved raw baseline logs (raw/evidence-whitespace.*); raw bytes were intentionally retained. Production source whitespace check exited0.
