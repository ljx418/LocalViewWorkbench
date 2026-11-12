P3A correction04 — READY_FOR_REVIEW

Candidate `00b63d97e8a860ea1bf4759b04da0cf8045423a7`; evidence is the containing commit (full SHA supplied in worker_done). Author ljx418 <1173696783@qq.com>. Clean initial status; requested root `ae4dbc48ec4c58d09f7df460ced4bad68a91275d` merged --no-edit, fast-forward, exit0, no reset. Public contract_changes=none. This submission awaits independent review and root adjudication; no Stage/product Gate0/human/release claim.

1. Current coordinate: {'stage_id': 'R1', 'workpack_id': 'WP-R1-U3', 'gate': 'S3_P3A_CORRECTION_04_IMPLEMENTATION', 'state': 'PREPARING_NEXT_STAGE'} unchanged.
2. Batch completed: M05 post-prepare archive lifetime implementation, nine appended Oracles, final104 checks and bounded cleanup/evidence binding.
3. Last passed gate: UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, existing accepted scope only.
4. Current blocking gate: `P3A_POST_PREPARE_ARCHIVE_LIFETIME_AND_S3_GATE0_PENDING` unchanged; root owns disposition.
5. Route position: P3A component correction -> isolated review -> full S3 coordinator/profiles/quality/network obligations -> product Gate0 -> authorized execution -> independent and required human gates.
6. Remaining work: isolated review of M05 correction and residual S3 product requirements; no global counters advanced.
7. Next owner: separate reviewer, then root architecture/gate owner.
8. Authorization: existing finite synthetic offline scope only; no additional human permission needed and no real run inferred.
9. Evidence: reports/v0-s3/product-gate0/implementation-p3a-correction-04/; report, receipt, guarded runner, raw commands/stdout/stderr/exits/guards, hashes.
10. Exact stop: READY_FOR_REVIEW, preserve visible worker window, no self-signing or push.

Changed files: tools/v0_s3_stage_runtime.py and appended tools/test_s3_install_handoff.py; only new text evidence in this directory. StageRuntimeFactory, package owner, OwnedArchive and its registration seam are unchanged. No changes to old assertions/probes/raw, source fences, contracts, authority, budgets, coordinate or MANIFEST. source-check and immutable-boundaries both exit0; raw/original-tests-prefix.json proves all prior handoff test bytes remain an exact prefix.

Production call path and lifetime:

Inherited prepare still executes inside the existing protected preparation context and closes all descriptors before return. At real archive registration, the S3 adapter saves only fixed parent device/inode, root name/device/inode, label-keyed run/candidate/authorization binding; no long-lived descriptor is retained. factory.archive(context, cleanup) enters _archive_lifecycle, validates context binding and original archive lease against that saved tuple, and acquires a no-follow ancestor chain for the original parent plus a no-follow root descriptor. Both are checked against saved identities, never adopted from the current pathname. The real OwnedArchive receives the original cleanup and binding and the existing narrow native callback adapter. Its authorization, callback, inventory, copy, manifest and deletion execute within this bounded context; owner proof, budgets, consumed-root and lease checks remain intact.

During preparation failure, archive invocation reuses only a matching active parent/root context and verifies its saved lease/bindings. Recursive archive invocation is rejected. Acquisition failure closes any partial handles; callback/owner errors propagate unchanged and finally closes reacquired handles. Successful original-owner deletion is legal: teardown closes descriptors without demanding that the deleted root still exist. No new archive algorithm, pathname deletion fallback, copied source, settlement/refund or invented cleanup proof exists.

_preparation_guard now rejects an absent descriptor. The protected adapter cannot silently approve an inactive guard: it establishes or verifies context before calling the owner. Original archive authorization wrappers preserve legacy direct-owner callers when no protected context is active; existing tests call that original owner directly and keep their prior behavior. This compatibility path is not claimed to provide the new factory.archive guarantee. Protected archive calls always activate the strict guard, including around the native remove callback.

Finite lifecycle checks on final source:

| Oracle | Actual result |
| --- | --- |
| Normal default prepare -> driver cleanup -> factory.archive -> warm prepare -> cleanup -> factory.archive | Both real synthetic archives proven, roots deleted, manifests preserved, handles closed after each prepare and archive. Default has reparse proof; warm legitimately has no reparse fixture. |
| Parent already replaced / root already replaced | Reject without default-raw creation; original retained, replacement sentinel unchanged; handles closed. |
| Parent-chain open failure / root open failure | Reject acquisition before archive writes; partial descriptors closed, original root retained. |
| Cleanup callback throws | Original failure propagates, root retained, no archive destination, handles closed. |
| Cleanup callback moves parent | Reject after real cleanup callback before replacement default-raw; original root/sibling retained, foreign bytes unchanged. |
| Archive authorization drift / recursive adapter invocation | Refuse before archive destination and deletion, close handles. |
| Existing prepare-failure archive path, original5 and M04gap | All remain passing on final source. |
| Unchanged independent M05 post_prepare probe | Run once on final source: replacement_writes=[], original_root_retained=true, lifecycle_parent_fd=null. |

Actual commands are raw/<run>.command.json with cwd and environment overrides. Each invokes python3 -B reports/v0-s3/product-gate0/implementation-p3a-correction-04/guarded_checks.py MODE RUN; matching stdout/stderr/exit and guard files retain actual output. Plugin autoload/bytecode/cache are disabled; subprocess guard admits Git only inside newly registered synthetic fixture repositories and rejects shell/exec/spawn/socket connect/bind.

| Run | Denominator | Passed | Failed | Exit | Candidate scope |
| --- | ---: | ---: | ---: | ---: | --- |
| targeted-01 |74|69|5|1|First implementation; failures retained|
| targeted-02 |74|74|0|0|Final candidate; original65 + new9|
| regression |23|23|0|0|Final candidate; old S2 runtime/browser|
| probes |5|5|0|0|Final candidate; unchanged correction01 probes once|
| gap |1|1|0|0|Final candidate; unchanged M04 once|
| post |1|1|0|0|Final candidate; unchanged independent M05 once|

Final fresh total104/104, no skips or precursor results combined. First-run five failures comprise three direct legacy-owner authorization compatibility failures, one incorrect new warm-test expectation (warm has no reparse fixture), and one new parent-open injector aimed at an absolute path rather than directory_handle's relative segment. Corrected without changing any historical assertion; raw failed output remains intact. This was one evidence-driven correction, not repeated no-progress repair.

Reused, not freshly run: independent archive9 on candidate e3f9427f17c38def9216813842195b94b490698f / review9bf2cf20909437a680d4c778b77db3575701c7f8, and package17 bound to5497bd1860ae895f394ece23a1ddb5e0b22fad92 / independent e9c910e881572691449dc70da569abee0dc4b195. raw/reused-owner-evidence.json records source/test byte equality and prior stdout SHA. Their owner/default regression modules do not depend on changed S3 runtime. These26 reused checks are excluded from fresh104. No archive/package owner source changed; no P2B, broad suite, early defect observations or full checkpoint run.

Cleanup and scope: raw/cleanup-summary.json records198 registered temporary-path entries across six runs, all absent afterward, with no remaining roots reported at any run end.Each guard retains its actual Git argv/cwd list. Only newly owned temporary fixtures were inspected/removed by fixture teardown; no old /tmp roots, claims, ledgers or testSource scans. Temporary packages/databases/source repositories were not committed. No permanent configuration. Actual Windows/WSL/PowerShell/parser/host-executable hashing/media/model/GPU/services/network/download/real program ledger/full checkpoint operations are0.

Platform limitation remains Linux/POSIX synthetic no-follow/dirfd evidence; unsupported anchored operations fail closed. Handles can still address the legitimately moved original owned inode; no universal instruction-level hostile-OS guarantee is claimed. This implements finite controlled-callback lifecycle protection, not full S3 budgets/profiles/offline networking/quality or product acceptance. Prior M01/M02/m01/M03/M04 independent closures remain historical root decisions; this worker does not re-sign them.

Unchanged complete V0–V3 outline:

| Delivery | Stage | Completed/total | Existing meaning |
| --- | --- | --- | --- |
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

V1-D0 preparation remains2/2 and unified early slice3/3 remains scope-limited; neither advances full R1 or release. Original historical failures and all raw evidence remain unchanged.

Evidence staging whitespace check exits2 on preserved pytest failure traceback whitespace; raw bytes remain unchanged. Source whitespace check exits0.
