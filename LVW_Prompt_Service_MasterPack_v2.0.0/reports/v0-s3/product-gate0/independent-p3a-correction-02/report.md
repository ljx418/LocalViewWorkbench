# Independent P3A correction02 review — CHANGES_REQUIRED

**Open Fatal0 / Major1 / Minor0.** Original **P3A-C01-M03 is closed** for its reproduced trigger; new **P3A-C02-M04** blocks the corrected offline deployment component. M01/M02/m01 remain closed. Root adjudicates; no StagePASS or product Gate0 is claimed.

Author: ljx418 <1173696783@qq.com>. Candidate `db607d484e9627b8be8b27d581d9d174ea4a9e63`; evidence `8881098d9a0aa8f2d6434a98ea6d2b23f64d1f48`; frozen correction contract `1a553726c67c35a0c82aab54d409eb9abcb4ff45`. Initial worktree clean; requested merge fast-forwarded e9c910e to8881098, exit0, no reset. Latest coordinate read through git show abe960a, not merged. Only this new review subtree is authored; candidate/old tests/probes/reports remain unchanged.

## New Major: P3A-C02-M04 — root allocation precedes the post-verification identity guard

Location: `tools/v0_s2_stage_runtime.py:166-174`, reached through `tools/v0_s3_stage_runtime.py:103-112`. The subclass's authorize guard at lines65-68 runs before complete verification; the next effective parent identity check is inside archive registration at lines37-42, after the base has created the root.

Trigger: move the original sandbox parent and create a plain replacement at the old pathname while the complete-verification callback runs, then return the valid proof. Expected: zero writes to the replacement parent, including directory creation. Actual: `_prepare` calls `tempfile.mkdtemp(..., dir=self.directory)` at base line168 and creates an empty `lvw-s2-default-*` directory in the replacement inode. Archive registration subsequently raises `preparation parent identity drift`; it is too late to prevent that write.

Reproducer: `test_lifecycle_gap.py::test_parent_replaced_during_complete_verification_has_zero_foreign_writes`. Exact command and raw result are in `raw/gap.command.json`, stdout/stderr and exit.log. The one test genuinely **fails, exit1**, at its zero-replacement-entries assertion. Structured `INDEPENDENT_EARLY_LIFECYCLE` evidence records the new empty directory, zero archive leases, zero services, five closed descriptors and the original failure receipt in the original parent. Sentinels remain unchanged; no payload was installed, no foreign file was overwritten or deleted. Root retention is accurately unknown/null because archive registration never completed.

This is a deterministic namespace change during a potentially long complete-source verification, not an assertion of a real adversarial process or an impossible universal atomic rename guarantee. The write targets a newly substituted parent inode; it is outside the accepted limitation allowing continued writes through a descriptor to the relocated original inode. Root allocation must remain bound to that original parent through verification/registration; reviewer did not repair the candidate or broaden the implementation whitelist.

## M03 closure and full-lifecycle assessment

The unchanged five-probe suite from e9c910e ran once: **5 passed/exit0**. Its M03 case now observes zero replacement-parent writes after a late move before installation receipt persistence. The new candidate tests independently executed here also verify the failure record exists in the moved original parent, original root retention=true from its pinned descriptor, original exception preserved, no service start and lifecycle descriptors closed. Original M01/M02/m01 tests continue to pass; they were not reopened. Earliest historical four defect-observation probes were not rerun.

The base change is a thin `_persist_preparation_failure` seam. AST comparison confirms all preexisting methods except `_prepare` are unchanged, and replacing only its two original persistence statements with the hook makes the old/new `_prepare` AST identical. The default hook reproduces the old S2 root.exists/exclusive pathname write behavior. The S3 subclass does not copy the whole method: it opens the parent with `directory_handle` before inherited `_prepare`, pins root only after real archive.register/lease, closes roots in finally and parent through ExitStack. The original failure writer uses one fixed relative filename, O_EXCL/O_NOFOLLOW and original parent dir_fd, so its post-deployment exception path no longer follows the stale parent pathname.

Retention uses fstat on the registered original root (device/inode/link count), or null/UNKNOWN when no descriptor proves the state. Early and deployment failures, post-deploy-copy and post-deploy-return failures, conflict/open/write/fsync failures and successful close paths are exercised in the54 checks. Triggering errors survive persistence errors. The on-disk attempt conservatively remains PERSISTENCE_UNPROVEN; only factory memory acknowledges PERSISTED after writing and file fsync. Conflicts preserve prior bytes, errors do not retry through pathname fallback, and no durable-success claim is manufactured. This evidence does not assert crash-proof directory metadata persistence beyond the implemented file fsync.

The retained-root archive fence remains for protected-install failures. For later lifecycle failures, `_preparation_guard` stops pathname archive operations when pinned identities drift. Authorize still calls the original authorization function after its guard; `_copy` still calls the production base copy owner with guards before and after. Neither wrapper suppresses existing checks or changes the package/source seal. However these guards do not cover the early allocation window above, so they are insufficient for a blanket full-lifecycle no-foreign-write approval.

Normal production path remains inherited prepare -> real archive registration -> protected real package install -> exact bridge/workflow/landed-byte/owner/session checks -> inherited sample/reference preparation and native boundary. Tests use tracked synthetic Git packages, real install owner and archive, dirty source and throwing copy fallback; fake-native start_comfy and CLI base-directory point at the same installed root. Native preflight/model/services/registry are synthetic boundaries, not real-host proofs.

## Actual checks and evidence reuse

| Run | Result | Exit | Counted as fresh |
|---|---|---:|---:|
| Candidate targeted |54 passed|0|54|
| Two old S2 regression files |23 passed|0|23|
| Unchanged independent correction01 suite |5 passed|0|5|
| New early lifecycle assertion |1 failed|1|1|
| Prior independent owner tests |17 previously passed; reused only|previous0|0|

Fresh total83:82 passed,1 failed. Each suite ran exactly once. No broad suite/P2B237/full checkpoint or extra owner rerun. Binding audit exits0:3 declared source hashes match candidate Git blobs;37 implementation checksum entries and52 previous independent-review entries match. Immutable-boundary diff is empty, including prior reports/probes and original P3A tests; no test or fixture deletion. The correction's only code changes are the base seam, S3 lifecycle wrapper and appended targeted cases.

Package owner and its selected test module are byte-identical to5497bd1. `raw/owner17-reuse.json` independently binds their exact hashes and e9c910e owner command/stdout/stderr/exit/guard/receipt/runner hashes. The17 selected tests invoke unchanged default package parser/main/install/rollback in process and do not import or call the changed factory lifecycle, so dependency changes do not invalidate that limited evidence. This is reused in-process compatibility evidence, not fresh execution or actual external CLI proof.

`guarded_checks.py` is adapted in this new directory from the previous independent guard. It installs subprocess/network audit hooks before pytest/plugin import, disables plugin autoload/bytecode/cache output, rejects shell/exec/network actions and permits Git only in newly registered synthetic repos (effective cwd includes -C). S2 regressions use zero children. Original five-probe source remains untouched. `audit_bindings.py` records raw Git commands and derived hashes without storing code snapshots. Exact argv/cwd/environment, stdout/stderr/exits, guarded child records and temporary registrations are under raw/.

## History, cleanup and limits

Historical implementation results remain unchanged: targeted01 **52 passed/1 failed,exit1** (fsync injection exposed original-error replacement); final targeted02 **54 passed,exit0**, regression01 **23 passed,exit0**, probes01 **5 passed,exit0**. Earlier findings/failing raw and whitespace remain immutable; hashes match. The new failing M04 assertion is preserved, not labelled an observation PASS.

161 newly registered temporary paths across four runs are absent afterward;660 allowed children were Git commands confined to fresh synthetic repos, with no guard denials. Production-retained roots were removed only by the owning fixture context, including the new empty foreign fixture directory. No old /tmp, runtime or ledger was scanned or modified. Only text evidence and authored reviewer scripts are committed, no fixture/code/archive snapshots or binary DB.

Observed platform is Linux/POSIX synthetic. The unchanged protected installer requires no-follow directory-descriptor capabilities and refuses unsupported mode; actual WSL/native Windows behavior remains unverified. Descriptors pin original objects, not immutable namespace locations; permitted original-inode relocation is distinguished from the M04 replacement-inode write. Descriptor closure is demonstrated for exercised success/error/persistence cases, not generalized to arbitrary hostile OS failure.

Actual Windows/WSL/PowerShell/parser/host executable hashes, model/GPU/real media, services/network/download, testSource/holdouts, program ledger/old runtime or claims and full checkpoint: all0. Full S3 coordinator/profile/budgets, A06 blocking and attempted-egress observation, fixed quality/resource acceptance, real installation/rollback, product Gate0 and human/release gates remain unproved. No live execution or StagePASS follows from this review.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_CORRECTION_02_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE (abe960a); review scope is offline P3A correction02.
2. 本批完成: independent source/evidence/lifecycle audit;54+23+5 fresh passes and1 new failure;17 owner checks reused, not rerun; M03 closed, M04 open; F0/M1/m0. No product machine acceptance or human signoff.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b, existing scoped human acceptance only.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING plus P3A-C02-M04 component lifecycle blocker.
5. 全局路线位置: P3A lifecycle closure -> full coordinator/quality/A06 -> offline combined review -> product Gate0 -> finite same-source execution -> independent acceptance -> required human signature.
6. 剩余工作: root adjudication of early root-allocation binding and authorized correction; subsequent full S3 coordinator/profile/budgets/network/quality/rollback gates.
7. 下一责任人: root architecture/gate owner; reviewer made no implementation edits.
8. 所需授权: none extra for completed offline review; no live execution authorization inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a-correction-02/; report/findings/receipt, raw/checksums, guarded runner, single added probe and binding/reuse audit.
10. 精确停止原因: assigned independent review complete with one new reproducible Major; return to root for adjudication, keep worker visible.

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

Current coordinate is R1/WP-R1-U3 with the correction02 independent-review gate. V1-D0 preparation remains2/2; unified early slice3/3 acceptance is scoped only. Counts and implementation/machine/independent/human distinctions remain unchanged; full source extract is raw/coordinate-extract.json.

Staged whitespace check exits2 solely for trailing whitespace in the preserved failed gap-probe traceback; raw bytes are unchanged. This is separate from the probe test exit1.
