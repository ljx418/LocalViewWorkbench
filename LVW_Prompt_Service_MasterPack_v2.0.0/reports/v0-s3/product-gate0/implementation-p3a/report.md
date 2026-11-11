# P3A implementation receipt — READY_FOR_REVIEW

Candidate: `7f84ac56e9d8c9bd39778a787b662634453875be`. Frozen authority: `09c4384ce3250951ca7f4197bda32a464a584b7e`. contract_changes=none.

## Complete V0–V3 outline (unchanged coordinate)

| Delivery | Stage | Completed / declared | Boundary |
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

V1-D0 offline preparation 2/2; unified early slice 3/3 is accepted only in its own scope. Current coordinate: R1 / WP-R1-U3 / S3_P3A_INSTALLED_PACKAGE_RUNTIME_IMPLEMENTATION / PREPARING_NEXT_STAGE. No completion counts were advanced.

## Ten required fields

1. 当前坐标: R1 / WP-R1-U3; this batch implements S3 P3A under the frozen internal contract.
2. 本批完成: installed-package subclass and 30 targeted synthetic cases; final 23 legacy regressions also passed, total 53/53. Implementation self-check only; independent review pending; no machine product acceptance or human signature claimed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW, candidate 621b1bf386db71bfe08ca2f533fa8ec396b0504b, scoped existing human acceptance.
4. 当前阻塞门禁: S3_PRODUCT_EXECUTOR_AND_GATE0_PENDING.
5. 全局路线位置: P3A installed deployment → complete coordinator/quality/A06 design → offline combination review → product Gate0 → finite same-source execution → independent acceptance → required human signature.
6. 剩余工作: independent review of this candidate; remaining complete S3 coordinator, budgets/profiles, network enforcement, actual install/rollback and quality/resource acceptance.
7. 下一责任人: separate independent reviewer, then root architecture/gate owner.
8. 所需授权: none additional for completed offline scope; no real run authorized by this component or receipt.
9. 证据目录: reports/v0-s3/product-gate0/implementation-p3a/ (receipt.json, raw commands/stdout/stderr/exits, SHA256SUMS).
10. 精确停止原因: authorized deployment implementation and requested self-checks complete; READY_FOR_REVIEW, awaiting independent review, not a Stage/PASS/human/release declaration.

## Production integration and boundaries

Only tools/v0_s3_stage_runtime.py and LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py are new code. S2 requires no seam change: inherited _prepare already registers a fresh root and calls _deploy before startup. Constructor adds only keyword-only package_path/package_sha256/manifest_sha256 and forwards existing base inputs. It adds no callback or shell execution surface.

Runtime call path: inherited prepare → archive registration → installed subclass deployment → real package archive validator and command_install into exactly that root → bounded landed-byte rehash, exact bridge/workflow seals, receipt/ownership/marker/lease checks → inherited native start_comfy(root), CLI base-directory check, public registry/profile and cleanup. Deployment mode and original install receipt remain in runtime evidence; original receipt is also saved beside the runtime root. Installer errors preserve structured error/transaction cleanup details. No copy fallback or second install exists.

Before install, the root must still be the registered direct child with the four empty plain preparation directories. The caller must supply the package sandbox marker; this component never creates it. All bridge and workflow source paths/digests must exactly match candidate execution_artifact_sha256 and manifest.source_commit must equal candidate. The existing full archive validator owns extraction validation and the 20MiB package/expanded limits. After install, every payload file is size/hash checked, exact tree sets compared, and in-target ownership checked against the original receipt. Failure follows the inherited persistent failure/archive/retention path. No external receipt authorizes deletion.

Tests use real tracked synthetic Git payloads and real command_build/command_install/OwnedArchive; package module __file__ metadata and legacy ROOT are relocated to the owned synthetic pack so existing path resolution remains active. Native service boundaries are substituted using the existing synthetic driver helper; its fake command line is quoted for the Chinese/space path. Source trees are dirtied after package build and the legacy deployment method is forced to raise, proving no fallback. subprocess.Popen permits only Git in the synthetic repository; shell calls are forbidden. Legacy regression subprocesses are all forbidden. No host executable is hashed.

Positive coverage runs default then fresh warm through inherited preparation and confirms target/base-directory, installed bytes/hashes, original receipt, ownership and archival. Negative coverage includes old candidate, hashes/digests, absent/extra/different bridge seals, workflow seal gaps/drift, missing/invalid/symlink/drifting marker, linked/oversized package, installer transaction failure, changed/missing/extra/linked payload, owner/receipt mismatch, wrong/outside/unregistered/replaced root and redirected child. Every negative asserts zero service startups, unrelated sentinel bytes unchanged, and persistent failure plus archive or retention disposition.

## Actual checks and retained failures

| Run | Exit | Passed | Failed | Errors | Denominator |
|---|---:|---:|---:|---:|---:|
| targeted-01 | 1 | 0 | 0 | 28 | 28 |
| targeted-02 | 1 | 27 | 1 | 0 | 28 |
| targeted-03 | 0 | 28 | 0 | 0 | 28 |
| targeted-04 | 0 | 30 | 0 | 0 | 30 |
| regression-01 | 0 | 23 | 0 | 0 | 23 |
| regression-02 | 0 | 23 | 0 | 0 | 23 |

Exact argv is in each raw/*.command.json; full unedited stdout/stderr and actual pytest exit are adjacent. Targeted command uses python3 -m pytest -v -s -p no:cacheprovider with only the new file. Regression command uses a Python subprocess guard around pytest with only test_s2_stage_runtime.py and test_s2_browser_component.py.

Targeted-01 failed in fixture setup because the package owner locates its MasterPack using module metadata; correction relocated that metadata to a nested synthetic tracked pack. Targeted-02 produced new evidence (27 negative cases passed), with the positive fake command line failing on spaces; correction quoted the native fixture response. Targeted-03 passed 28/28. Final path review added prepopulation/child-link checking and two new cases; targeted-04 passed 30/30, followed by regression-02 23/23. This is not two same-route repairs without new evidence. Both earlier failures remain raw and are not rewritten.

Initial worktree was clean; required git merge --no-edit 09c4384ce3250951ca7f4197bda32a464a584b7e exited 0 via fast-forward. git diff --check exited 0. Code commit uses ljx418 / 1173696783@qq.com. No push or product gate operation performed.

All synthetic fixture parents are temporary and cleaned; unsafe negative runtime roots are retained by the production archive when required, then removed only by the owning test fixture cleanup. Generated untracked bytecode directories were removed (raw/cleanup.json). No temporary fixture source/package/DB archives are committed. All historical failures, authority, source fences, packet/coordinate/MANIFEST and quality inputs remain untouched.

This component proves offline deployment wiring only. Full S3 budget/profile compatibility, actual Windows/WSL services, offline network blocking/attempt observation, model/GPU/media results, production ledger, actual rollback and full checkpoint are not proven or performed. Root retains architecture and gate authority.

Evidence staging note: git diff --cached --check exited 2 solely for pytest traceback trailing whitespace in original targeted-01/02 stdout; raw bytes are deliberately preserved. The preceding source/worktree diff check exited 0. This text-log whitespace is not a runtime test failure.
