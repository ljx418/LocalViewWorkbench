# P3A correction 01 — READY_FOR_REVIEW

Code candidate: `5497bd1860ae895f394ece23a1ddb5e0b22fad92`. Root correction authority: `a3361b5f6e43b6a3f8b0f57fd2faa5fc7ffe4822`. Author: ljx418 <1173696783@qq.com>. Public contract_changes=none. Internal design follows the unchanged frozen correction contract. This is implementation self-check, not independent approval or Stage acceptance.

## Complete V0–V3 outline (unchanged)

| Delivery | Stage | Completed/declared | Scope/status boundary |
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

V1-D0 preparation remains 2/2; accepted unified early slice remains 3/3 only in its signed scope. No counts advanced. Current product coordinate is {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3A_CORRECTION_01_IMPLEMENTATION", "state": "PREPARING_NEXT_STAGE"}.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3, P3A correction implementation under root adjudication; product Gate0 remains pending.
2. 本批完成: aggregate M01/M02/m01 correction in one candidate; final fixed tests 44+23+17 = 84/84, exit 0; implementation READY_FOR_REVIEW, independent correction review pending, no product machine acceptance or human signoff performed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW, candidate 621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped prior human acceptance.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING; P3A root adjudication awaits separate correction review.
5. 全局路线位置: P3A installed deployment correction → independent review → complete coordinator/quality/A06 → offline combination review → product Gate0 → finite same-source execution → independent acceptance → required human signature.
6. 剩余工作: reviewer verifies this correction; root adjudicates, then remaining S3 coordinator/profiles/budgets/network/quality/rollback and formal gates.
7. 下一责任人: separate independent reviewer, then root architecture/gate owner.
8. 所需授权: none additional for the completed finite offline scope; no actual product run authorized by this implementation.
9. 证据目录: reports/v0-s3/product-gate0/implementation-p3a-correction-01/ (report, receipt, guarded runner, raw commands/stdout/stderr/exit/temporary-root registry and SHA256SUMS).
10. 精确停止原因: assigned aggregate correction and finite self-checks complete; READY_FOR_REVIEW only, independent review required; no Stage/PASS/human/release claim.

## Changes and production call path

Changed source/tests: tools/v0_s3_stage_runtime.py; tools/v0_incremental_package.py; tools/test_s3_install_handoff.py (new); LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py (only the existing failure injection also recognizes descriptor-relative rename). All original 30 cases retain their assertions; no skip/deletion. StageRuntimeFactory and its legacy default deployment/cleanup code are unchanged. No package CLI arguments or default rollback behavior changed. The package owner now has an explicitly selected internal ProtectedInstall transaction; it is not a new packaging or management tool.

Call path: inherited prepare → archive-register fresh root → InstalledPackageRuntimeFactory deployment → ProtectedInstall pins sandbox/root/preparation/parent descriptors and captures bounded no-follow archive bytes → existing complete _validate_archive over that private snapshot → exact candidate bridge AND workflow seals → existing command_install selects the internal protected owner → full archive validation again over the same snapshot → descriptor-relative staging writes/commits/owner write → original receipt and source identity evidence → all landed payload/ownership/session checks → inherited native startup, base-directory identity, registry/profile and success archive lifecycle.

M01: target and relevant parents are opened with O_DIRECTORY/O_NOFOLLOW and all actual installer writes/rename/owner writes use dir_fd with single child names. No installer target commit resolves a mutable destination pathname. Namespace identity is checked before/after operations; missing/replaced/link anchors refuse. The deterministic pre-commit redirect leaves the foreign tree unchanged with zero payload files. Injections inside rename, ownership write and staging cleanup prove the operation remains attached to the original object and does not follow a replacement tree. A plain root replacement is also retained unchanged by the inherited failure path.

Failure safety: the protected transaction does not invoke the old pathname rollback/rmtree path at all. Its error records preserve original_failure and cleanup.proven=false with RETAIN_NO_PATHNAME_ROLLBACK plus target/staging/committed identities. The runtime wraps only its archive delegate to refuse automatic pathname deletion for a failed protected deployment. Consequently a replaced ordinary directory cannot be deleted just because the original archive can enumerate it. This deliberately retains even some safely recoverable failures; the module never claims complete cleanup of those roots. The original native cleanup still runs, and success clears the archive retention fence.

M02: one no-follow descriptor supplies at most 20MiB into an immutable bytes snapshot; package/manifest/candidate validation and both source seals remain mandatory. The existing validator owns ZIP member/path/CRC/size/ratio/content checks. Protected mode additionally bounds total expanded archive bytes (including metadata) to 20MiB before decompression, without changing the old CLI size contract. The installer cannot accept an externally supplied validation dict or bypass full validation. Descriptor and original pathname identity (device/inode/size/mtime/ctime plus ancestors) are checked through the handoff and before startup; symlink, identical-file replacement and in-place rewrite refuse. Source receipt records the original path, file identity, bytes and SHA256 of the snapshot. Nonblocking opens reject late FIFOs as nonregular instead of waiting for a writer.

m01: the returned receipt session_id must equal the verified in-target owner session_id; existing hashes, target, package, manifest, marker, ownership install_hash and payload checks remain. A modified returned receipt is saved unchanged and the mismatch is durably rejected before fake service startup.

Original returned receipts are saved with exclusive/no-follow descriptor-relative writes under the pinned evidence parent. Source/marker drift cannot authorize writes through a substituted evidence path. On a directory identity change the original receipt remains in in-memory failure evidence if writing it safely is no longer possible.

## Fixed oracles, diagnostics and actual exits

| Run | Passed | Failed | Denominator | Exit |
|---|---:|---:|---:|---:|
| targeted-01 | 42 | 0 | 42 | 0 |
| regression-01 | 23 | 0 | 23 | 0 |
| owner-01 | 17 | 0 | 17 | 0 |
| probes-01 | 1 | 3 | 4 | 1 |
| targeted-02 | 44 | 0 | 44 | 0 |
| regression-02 | 23 | 0 | 23 | 0 |
| owner-02 | 17 | 0 | 17 | 0 |

Final unique fixed denominator is 84: original 30 P3A + 14 new correction cases + original 23 S2 + 17 selected existing installer-owner regressions. New cases assert no startup, unchanged unrelated bytes, persistent errors and retention; they cover validation-to-commit drift, mutation-time drift, failure cleanup, session mismatch, unsupported platform and special-file refusal, plus a successful protected source/session receipt.

Exact argv is preserved in raw/*.command.json; all unedited stdout/stderr and actual exits are adjacent. The audit runner disables bytecode/plugin/cache output, registers temporary roots, permits only Git within newly created synthetic repositories in targeted/probe runs, and denies shell/network and all other subprocesses. No subprocesses are permitted in owner or S2 regression runs. The 17 existing owner tests are unchanged on disk: their run_cli subprocess boundary is replaced in memory with the real package.main parser/owner and captured stdout/stderr, preserving the original test assertions while avoiding Python/host child launches. This is an in-process CLI/owner regression, not an external CLI process test.

The four independent observation probes were executed once without changes. Three assert historical defective behavior: accepted linked archive, foreign bridge files present, and accepted foreign session. Their new 3 failures/1 pass (exit 1) are intentionally retained, not relabelled pass and not included in the fixed acceptance denominator. The separate new fixed assertions passed. These observations ran before the final nonblocking special-file hardening; final 44/23/17 self-checks ran afterward against the committed source. No observation probe was edited or rerun to obtain a green result.

No failed fixed-test repair loop occurred: initial 42/23/17 passed. Final static review added nonblocking special-file handling and two fixed cases, then 44/23/17 passed. Historical prior candidate and independent failures remain untouched. Source/staged whitespace checks exited 0; raw diagnostic traceback whitespace remains unnormalized. Initial worktree was clean and required merge --no-edit a3361b5f6e43b6a3f8b0f57fd2faa5fc7ffe4822 fast-forwarded with exit 0. Boundary diff check exited 0 for unchanged S2, original package tests, plans/MANIFEST, frozen contract, independent probes and prior evidence.

## Cleanup, platform and remaining limitations

raw/cleanup-summary.json independently summarizes the seven audit records: 285 registered temporary paths across these runs are absent after completion. Protected failed runtime/staging roots are first retained by production policy, then removed only with the owning synthetic TemporaryDirectory context; this does not prove product rollback. Only text evidence is committed, with no DB, archive, copied source tree or permanent configuration. No old temporary roots, testSource, real ledger, model/GPU/media/service/network/download/Windows/WSL/PowerShell/parser or host executable hash operation was performed.

POSIX no-follow directory-descriptor operations are mandatory for the protected mode. Unsupported platforms refuse before installer target writes (the inherited prepare still creates its own fresh empty directories). This work exercised Linux synthetic fixtures; it does not claim native Windows or WSL production execution. Default CLI installation continues its old implementation; the new guarantees apply only to explicitly selected protected S3 handoff.

Threat boundary: descriptors pin the identity of opened directories, not their location forever. A malicious concurrent actor may move an already-open owned directory between a check and syscall; a descriptor-relative operation then affects that same owned inode at its new location. The implementation refuses detected drift, never follows its replacement, and never performs pathname rollback after failure; it does not promise to prevent arbitrary hostile relocation of the owned inode. This is disclosed rather than inferred from Linux tests as a universal Windows guarantee.

Full S3 budget/profile integration, A06 network blocking and outbound-attempt observation, real install/rollback acceptance, fixed quality/resource results, product Gate0 and full checkpoint remain unimplemented/unproved by this deployment component. Root owns architecture and gate decisions.
