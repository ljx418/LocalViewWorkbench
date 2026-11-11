# Independent P3A review — CHANGES_REQUIRED

Author: ljx418 <1173696783@qq.com>. Fatal **0**, Major **2**, Minor **1**. Recommendation applies only to offline installed-package runtime integration; root adjudicates. No StagePASS, product acceptance, human signature or release claim.

Candidate `7f84ac56e9d8c9bd39778a787b662634453875be`; evidence `0fc20361ace1d1ed156a5347c9280bf039b00cb5`; frozen contract `09c4384ce3250951ca7f4197bda32a464a584b7e`. Initial status was clean and requested merge fast-forwarded ac402c4 to 0fc2036, exit 0. Candidate/source tests match candidate Git blobs and declared SHA256; all 28 implementation SHA256SUMS entries independently match. Base StageRuntimeFactory, installer and both frozen contract documents have empty diffs against contract root. Latest coordinate was read from 1bf4308 without merging it. Only this new report subtree is authored.

## Findings (aggregated once; no candidate repairs)

### P3A-M01 — Major

Location: `tools/v0_s3_stage_runtime.py:97-106; tools/v0_incremental_package.py:1885-2010`. Trigger: Replace registered root/custom_nodes with a symlink to a fresh unregistered sibling during the second archive validation, before installer commit.

Expected: Refuse before writes outside the archive-leased root; retain original error and bounded cleanup evidence. Actual: Real installer wrote three bridge files to the foreign fixture directory; later plain(root/bridge) rejected with binding redirect forbidden, zero fake services started, root retained because archive rejected the redirect.

Reproduction: `test_independent_probes.py::test_child_redirect_during_install_validation` under the guarded probes command; raw evidence: `raw/probes.stdout.log: INDEPENDENT_OBSERVATION late_child_redirect`.

### P3A-M02 — Major

Location: `tools/v0_s3_stage_runtime.py:88-106,112-151`. Trigger: After initial validation, rename the package and replace package_path with a symlink to the identical archive before real command_install.

Expected: Reject changed/redirected package path before service start; initial plain/digest cannot authorize a later independently opened path. Actual: Real installer follows link; identical content passes receipt/tree checks; deployment VERIFIED and one fake Comfy start occurs.

Reproduction: `test_independent_probes.py::test_archive_link_between_validation_and_install` under the guarded probes command; raw evidence: `raw/probes.stdout.log: INDEPENDENT_OBSERVATION late_archive_link`.

### P3A-m01 — Minor

Location: `tools/v0_s3_stage_runtime.py:115-127; tools/v0_incremental_package.py:2383-2463`. Trigger: Change only returned install receipt session_id to foreign-session while preserving real owner/hash/bytes.

Expected: Installation receipt session identity agrees with in-target ownership record or is explicitly excluded from authority. Actual: Mismatched session accepted and fake Comfy starts; other owner install_hash and target/payload bindings remain valid, so no deletion escalation demonstrated.

Reproduction: `test_independent_probes.py::test_receipt_session_identity` under the guarded probes command; raw evidence: `raw/probes.stdout.log: INDEPENDENT_OBSERVATION receipt_session`.

The late mutations are deterministic injections at real filesystem check/use boundaries, not evidence that another process actually raced a Windows deployment. All foreign targets are newly owned synthetic fixtures. M01 demonstrates real unintended writes within that bounded fixture, even though the later service-start refusal and retention work. M02 demonstrates bypass of the explicit no-symlink package requirement without changing archive bytes; it does not claim changed bytes were executed. The source of both gaps is a mutable pathname crossing into a separately validating installer; acceptance needs the frozen no-redirect/no-foreign-write obligations preserved throughout that handoff, not merely another successful happy-path test.

## Actual checks and production path

| Check | Actual result | Exit |
|---|---|---:|
| Targeted initial reviewer guard attempt | 30 fixture errors, 0 pass; Git -C blocked before build | 1 |
| Targeted reviewer import correction attempt | 1 collection error, 0 collected | 2 |
| Candidate targeted final | 30 passed | 0 |
| Two requested old regression files, once together | 23 passed | 0 |
| Four independent observation probes | 4 assertions passed; 3 expose findings, 1 confirms initial ancestor-link rejection | 0 |
| Candidate/source and base/contract diffs | empty relevant diffs | 0 |
| Historical raw whitespace check | existing traceback trailing whitespace retained | 2 |

The reviewer guard/import errors are retained, not attributed to candidate defects or hidden. No broad suite, P2B rerun or full checkpoint was run. Exact command JSON, unedited stdout/stderr, exit files, subprocess audit records and temporary-root registry are in raw/. guarded_checks.py installs an audit hook before importing pytest/tests, disables plugin autoload and bytecode/cache output, denies non-Git children, allows Git only with effective cwd in a just-created registered synthetic repository, and denies shell/network actions. Regression children are all forbidden. Candidate fixture guards additionally constrain Popen. Git -C is checked as the effective repository rather than trusting shell cwd. The guard change did not relax repository ownership.

The actual inherited prepare_default/prepare_warm -> _prepare registers a new root with OwnedArchive, constructs the fake-native driver, calls subclass _deploy, calls real command_install with target=root and sandbox_parent=directory, and checks landed files/owner/receipt. Then inherited preparation calls start_comfy(root), checks actual supplied fake CLI --base-directory/user-directory against root and checks registry/profile. The positive test runs default then warm, dirties source bytes and makes the base copy deployment throw, proving no copy fallback rescued the package. Real command_build uses tracked synthetic Git bytes; real installer writes them and real archive processes them. Fake NativeRuntime preflight, commands, model, registry and cleanup are synthetic evidence only.

Static and dynamic coverage: candidate/source_commit; exact bridge AND workflow source-path/hash sets; package/manifest hashes; wrong/missing/extra/changed payload; owner and receipt target/hash checks; missing/invalid/symlink/drifting marker; wrong/unregistered/replaced root; initial child redirects; installer transaction failure; initial archive ancestor redirect. Ordinary post-install mutation is rejected before start. Failure records preserve original exceptions, deployment FAILED, cleanup and archive/retention decisions; M01 raw record preserves binding redirect forbidden plus archive unexpected redirect and root_retained=true. The archived original receipt survives post-install verification failure. No external receipt was used to authorize deletion; receipt session cross-check remains incomplete (m01).

Read bounds inspected: _digest checks plain ancestors, regular-file identity, 20MiB and bounded streaming deadline; installed traversal has 8192-entry ceiling; installer performs its existing ZIP size/ratio/member checks. These are checks on separately opened paths, not a proof of immutable handles across reads; M01/M02 prevent a blanket bounded-path/transaction-safety approval. No binary DB, source fixture copies or archives are committed.

Implementation history remains unchanged: targeted-01 28 errors/exit1; targeted-02 27 pass+1 fail/exit1; targeted-03 28 pass/exit0; targeted-04 30 pass/exit0; both historical regression runs 23 pass/exit0. Their raw-log whitespace check still exits 2. All 28 recorded implementation evidence hashes match, so neither failures nor whitespace were rewritten.

Every newly registered temporary fixture is absent after its run (raw/*guard.json); production-retained negative roots were removed only by the fixture owner's TemporaryDirectory context. Historical runtime roots were not manipulated. No testSource or human holdouts were read. No actual Windows/WSL child, PowerShell/parser, host executable hash, model/GPU/real media, service/network/download, program02.sqlite, real/old synthetic ledger or full checkpoint action occurred.

Real rollback, Windows/WSL behavior, network enforcement/attempt observation, full S3 profiles/budgets, product Gate0 and fixed quality/resource acceptance remain unproved. Temporary-root deletion is not rollback acceptance. Nothing in these checks activates real execution.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_INSTALLED_PACKAGE_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE (1bf4308); review subject is S3 P3A.
2. 本批完成: independent source/contract/evidence review; candidate 30 + old regression 23 checks passed; four focused observations; F0/M2/m1. Implementation exists; product machine acceptance and human signoff not performed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on 621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped human acceptance only.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING, plus review recommendation CHANGES_REQUIRED for P3A path-safety gaps.
5. 全局路线位置: P3A -> complete coordinator/quality/A06 -> offline combination review -> product Gate0 -> bounded same-source full execution -> independent acceptance -> required human signature.
6. 剩余工作: root adjudication of aggregated findings; implementation correction/review as directed; complete S3 coordinator/profiles/budgets/network/quality/rollback and later formal gates.
7. 下一责任人: root architecture/gate owner; reviewer has made no candidate fixes.
8. 所需授权: none additional for this offline review; no live execution authorization inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a/; report.md, findings.json, receipt.json, guarded runner/probes, raw logs, SHA256SUMS.
10. 精确停止原因: assigned independent review complete with reproducible findings; return to coordinator for adjudication, preserve visible worker window.

## Complete unchanged V0–V3 outline

| Delivery | Stage | Done/declared | Boundary |
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

Current coordinate is R1/WP-R1-U3 with the S3 P3A independent-review gate. V1-D0 preparation remains 2/2 and the unified early slice 3/3 is accepted only within its signed scope. No development counts were advanced; full state distinctions are retained in raw/coordinate-extract.json.
