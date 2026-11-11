# Independent P3A correction01 review — CHANGES_REQUIRED

**Fatal 0 / Major 1 / Minor 0 open.** The three original findings are closed for their reproduced triggers, but new **P3A-C01-M03** blocks acceptance of the corrected offline deployment component. Root retains adjudication authority; no StagePASS, product Gate0, human or release claim.

Author: ljx418 <1173696783@qq.com>. Candidate `5497bd1860ae895f394ece23a1ddb5e0b22fad92`; evidence `bf675ffb84146527f430c46467ec4e236e1fa3a4`; correction contract root `a3361b5f6e43b6a3f8b0f57fd2faa5fc7ffe4822`; previous independent review `bdbe43c084b2264ecb511f9cf6cd8d852c881efe`. Initial worktree status was clean; requested merge fast-forwarded bdbe43c to bf675ff (exit0), no reset. Latest coordinate read through git show f2ba889; metadata not merged. Only this new review directory is authored.

## Finding P3A-C01-M03 — inherited failure receipt follows a replaced parent

Location: `tools/v0_s2_stage_runtime.py:260-261`, reached from `tools/v0_s3_stage_runtime.py:177-182` after `ProtectedInstall.__exit__` closes the descriptor set (`tools/v0_incremental_package.py:1076-1080`). The correct protected receipt writer is at package lines1099-1108, but its error path returns to an unprotected inherited terminal writer.

Trigger: let real protected installation finish, then rename the sandbox parent immediately before `handoff.save_receipt`; create a plain unregistered replacement directory at the original parent pathname. This is injected only inside a newly owned synthetic fixture. The normal protected writer detects directory identity drift and refuses, preserving original installed objects in the detached parent.

Expected: no write to the replacement inode; original error and actual retention disposition recorded through the original owned parent, or a fail-closed disposition with no foreign write. Actual: inherited `_prepare` writes `default-preparation-failure.json` using `self.directory` into the replacement directory. The original parent has no terminal failure file. The new receipt records `root_retained=false` because the old pathname vanished, although the owned root still exists inside the moved parent; deployment evidence correctly says retention_required=true. The archive wrapper prevents deletion and all20 tracked descriptors close, but that does not prevent this subsequent foreign write.

Reproduction: `test_fix_and_failure_probes.py::test_failure_receipt_must_not_write_to_replacement_parent`, through the exact guarded command in `raw/probes.command.json`. `raw/probes.stdout.log` contains the full structured observation, original error `protected directory identity drift`, cleanup refusal, replacement file inventory and failed `unexpected == []` assertion. Services start0; foreign sentinel and original sibling bytes remain unchanged. The failed assertion is reported as FAIL, not converted into an observation PASS.

This is outside the accepted relocated-owned-inode limitation: it writes to the replacement directory's new inode after the descriptor context closes, not to the moved original inode through a pinned descriptor. Root should select the authorized seam that keeps final failure evidence and retention identity anchored across the inherited handler; reviewer did not repair candidate or expand its whitelist.

## Original findings closed with fresh assertions

| ID | Independent evidence | Result |
|---|---|---|
| P3A-M01 | `test_M01_late_child_redirect_refused_with_zero_foreign_writes` | PASS: late custom_nodes link refused during second sealed validation; destination contains only unchanged sentinel, zero foreign payload writes and zero services; durable original failure/retention;13 descriptors closed |
| P3A-M02 | `test_M02_late_archive_identity_refused[symlink]` and `[same_bytes_new_inode]` | PASS: linked and identical-byte replacement paths rejected for identity drift before payload install/start |
| P3A-m01 | `test_m01_receipt_session_refused_and_original_record_retained` | PASS: receipt/owner session mismatch rejected before start; original mismatching returned receipt persisted and owner identity retained |

These close the exact original defects, not the new end-to-end failure-receipt obligation. The original observation suite was not rerun here. Implementation's historical unchanged observations remain **1 passed,3 failed,exit1**, because they asserted the prior defective behavior; those failures are neither labelled PASS nor used as conclusive fix evidence.

## Checks, bindings and guards

| Run | Actual result | Exit | Runs |
|---|---|---:|---:|
| Candidate targeted (original30 + correction14) |44 passed|0|1|
| Requested two old S2 files |23 passed|0|1|
| Selected installer-owner cases |17 passed|0|1|
| Independent fix/failure assertions |4 passed,1 failed|1|1|
| Source/evidence/immutable-boundary recomputation |4 source blobs,47 implementation checksums,56 previous-review checksums match|0|1|

All84 requested fixed checks pass. Five independent probes have their actual4/1 result; they are not included in an all-green acceptance claim. No broad suite, P2B237, old observation rerun, or full checkpoint was run. Exact argv/cwd/environment overrides, raw unedited stdout/stderr/exit and guards are under raw/; `audit_bindings.py` recomputes source identities and relevant Git invariants without persisting source snapshots. Existing raw failures and trailing whitespace remain unchanged.

`guarded_checks.py` installs an audit hook before pytest/plugin imports, disables external plugin autoload and bytecode/cache output, blocks shell/exec/network actions, and permits Git only when its effective cwd (including -C) is a freshly registered synthetic repository. Owner/regression modes permit no child process. For the17 selected owner cases, only the existing `run_cli` process boundary is replaced with Python `package.main` plus captured stdout/stderr; original assertions run against actual parser/default owner/rollback functions. This is in-process compatibility proof, not actual external CLI/PowerShell parser proof. The selected owner cases use synthetic ZIPs inside new pytest temp roots, not old Git fixtures or ledgers.

All4 changed source files match candidate Git blobs and declared hashes. Original StageRuntimeFactory, selected old test files, initial P3A/correction contracts and prior reports have empty diffs against the contract root. AST comparison finds exactly two modified preexisting package functions: `_validate_archive` and `command_install`; the latter's default body after its explicit protected-mode dispatch is identical to the baseline. Other preexisting owner/parser/rollback functions are unchanged. The original test's install-failure injection only adds descriptor-relative destination recognition; assertions are preserved.

## Production path and safety assessment

Actual inherited `prepare_default/prepare_warm -> StageRuntimeFactory._prepare -> archive.register -> InstalledPackageRuntimeFactory._deploy -> ProtectedInstall -> command_install` remains the integration path. Real tracked synthetic Git packages build and install into the archive-leased run root. Candidate positive tests force base-copy deployment to fail and dirty source bytes; successful default/warm preparation therefore comes from installed bytes. Inherited actual start_comfy argument and fake-native CLI --base-directory/user-directory compare to that same installed root; registry/profile and archive behavior execute through synthetic NativeRuntime boundaries only.

Protected mode pins parent/root/preparation directories and archive ancestors with no-follow directory descriptors. Archive regular-file size/identity is checked on the opened descriptor; bounded bytes become `_SealedArchive`. Both runtime precheck and owner revalidation use the full archive validator on those bytes; owner install accepts the exact ProtectedInstall type, checks active/used/arguments and revalidates rather than taking a caller's unchecked validation dictionary. Expected package/manifest/source_commit and exact candidate bridge/workflow seals stay enforced; final landed sets/bytes and owner/hash/marker/lease/session bindings remain in the factory.

Archive read is capped at20MiB in1MiB chunks and protected decompression rejects total expanded metadata+payload over20MiB before member reads. Marker and protected reads use regular-file/no-follow/nonblocking descriptors and20MiB bounds, comparing size/mtime/ctime/inode after reads; FIFO substitutions fail rather than block. Landed traversal retains8192-entry and per-file bounds. Descriptor lifetime spans protected install and receipt verification; observed failure cases close all captured descriptors, and acquisition exceptions call the close path. This is not a proof against arbitrary memory mutation by trusted Python callers or universal adversarial filesystem races.

Writes and renames inside protected owner use original target/parent descriptors. Stage removal checks pinned inode identity and uses descriptor-relative rmdir; installation failure retains target/staging with original_failure and `RETAIN_NO_PATHNAME_ROLLBACK`, rather than invoking legacy pathname rollback. `_DeploymentArchive` fences inherited deletion for failed protected deployments. Candidate tests cover replacement before/inside commit, owner write, staging cleanup, root replacement and unsupported mode; all pass. The remaining unanchored terminal failure write is specifically isolated by M03; therefore end-to-end foreign-write prevention is not approved.

Support is Linux POSIX descriptor/no-follow behavior verified with synthetic fixtures. WSL Python is the intended deployment owner, but no actual WSL/native Windows child ran. Native Windows protected mode is unsupported and must fail closed before installer writes; the unsupported capability test confirms the refusal branch. Open descriptors pin object identity, not an immutable namespace location: a hostile rename at a syscall boundary can relocate the same owned inode. The contract accepts that disclosed limitation; no universal anti-hostile-rename guarantee is demanded or claimed. Default CLI remains its old path-based mode and does not acquire protected-mode guarantees implicitly.

## Cleanup, retained history and limits

151 temporary paths were registered across the four independent runs; all are absent afterward. Only freshly created fixture parents were inspected/cleaned. Protected failure roots were retained by production code then removed solely by their owning TemporaryDirectory; this is fixture cleanup, not rollback acceptance.539 permitted subprocesses were Git operations in fresh synthetic repositories; owner/regression modes had0 children and no guard denials occurred. No binary DB, fixture/archive/code snapshots are committed, only authored review scripts and text evidence.

Historical correction runs are retained: targeted01 42 pass, targeted02 44 pass; regression01/02 each23 pass; owner01/02 each17 pass (all exit0); original observation probes1 pass+3 fail/exit1. Initial review failures and raw-log whitespace are unchanged and their56 checksums still match. New failed M03 raw evidence is preserved without rewriting.

Actual Windows/WSL children, PowerShell/parser, host executable hashes, model/GPU/real media, services/network/download, program02.sqlite reads/writes, real/old synthetic ledgers or runtime roots and full checkpoints: all0. No testSource or human holdouts read. Full S3 coordinator/profile/budgets, A06 enforcement/attempt observation, real install/rollback, fixed quality/resource acceptance and product Gate0 remain unproved; no human/release claims.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_CORRECTION_01_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE (f2ba889); offline P3A correction is this batch's scope.
2. 本批完成: candidate/evidence binding review;84 fixed checks pass; independent4 pass/1 fail; originals M01/M02/m01 closed, new M03 open; F0/M1/m0. Implementation exists, product machine acceptance/human signoff not performed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b; existing scoped human acceptance only.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING plus P3A-C01-M03 corrected-component review blocker.
5. 全局路线位置: P3A correction -> full coordinator/quality/A06 design -> offline combination review -> product Gate0 -> finite same-source execution -> independent acceptance -> required human signature.
6. 剩余工作: root adjudication and authorized closure of final failure-evidence anchoring; subsequent full S3 coordinator/profiles/budgets/network/rollback/quality gates.
7. 下一责任人: root architecture/gate owner; reviewer made no candidate edits.
8. 所需授权: no additional authorization for this completed offline review; no real run inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a-correction-01/; report/findings/receipt, guarded runner, own probes, binding audit, raw and SHA256SUMS.
10. 精确停止原因: independent correction review complete with one reproducible new Major, pending root adjudication; preserve visible worker window.

## Unchanged complete V0–V3 outline

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

Current coordinate is R1/WP-R1-U3 with the P3A correction01 independent-review gate. V1-D0 preparation remains2/2; unified early slice3/3 is accepted only in its signed scope. Counts and implementation/machine/independent/human distinctions are unchanged; full coordinate extract is in raw/coordinate-extract.json.

Review staging check: git diff --cached --check exits2 for trailing whitespace in the preserved new failed-probe traceback only; raw bytes are retained. This is separate from probes exit1 and is not a source-code test failure.
