# Independent P3A correction05 review

**Fatal0 / Major0 / Minor0. P3A-C04-M06 is closed on final candidate9ebdcc0.** Original M01/M02/m01/M03/M04/M05 remain closed. Recommendation: accept this corrected offline deployment-component change for root adjudication. This is not StagePASS, product Gate0, live execution, human acceptance or release approval.

Author: ljx418 <1173696783@qq.com>. Candidate `9ebdcc0d4060b18737001d3136671f4d2ac0506a`; evidence `282931f62cecd502bdec421339ebf30c758c25ca`; frozen root `d29be4f9f82293a48e5780a1baa4adab48613b2b`. Clean isolated worktree was fast-forwarded from c51274e by requested merge --no-edit, without reset. Only this new review subtree is authored. AGENTS, governance README, docs24, frozen correction05 contract, root correction04 decision, prior independent report/probes and actual source/tests were inspected. Coordinate was read from a62f7bc without metadata merge.

## Actual checks and M06 proof

| Final-candidate check, each once | Passed | Failed | Exit |
|---|---:|---:|---:|
| Targeted installed runtime + handoff |85|0|0|
| Two unchanged S2 files |23|0|0|
| Unchanged correction01 probes |5|0|0|
| Unchanged M04 allocation gap |1|0|0|
| Unchanged M05 post-prepare archive gap |1|0|0|
| Unchanged correction04 six probes, including original two M06 cases |6|0|0|
| Additional reachable wrong-context / nested-archive assertions |2|0|0|
| Exploratory cross-label probe: invalid precondition, stopped at factory order guard |0|2|1|

All **121 required checks pass** on final9ebdcc0, with no precursor stitching. Two additional valid assertions pass. Honest total execution count is **125 cases:123 passed,2 failed**. The two exploratory failures are preserved and excluded from candidate correctness assertions; they are neither PASS nor product findings. Prior archive9/package17 are reused evidence, not fresh counts. Exact argv/cwd/environment/stdout/stderr/exits and guarded temporary-path registries are under raw/.

M06 previously arose when the returned closures called factory.authorize after prepare had closed its descriptors. Source `tools/v0_s3_stage_runtime.py:222-239` now obtains the actual inherited DefaultContext, captures each original callback, enters `_archive_lifecycle(context)` for each invocation, checks terminal default archive state, calls the original callback, and performs a final identity guard before return. ExitStack closes handles on success or exception. The strict absent-context guard at106-108 is unchanged; authorization is not bypassed or silently ignored.

Both **original unchanged M06 tests** now execute through actual inherited prepare, original closures and original `_user_root`. They assert root identity output, ephemeral-user-root verified, and a positive original authority call count, then successfully archive through the real owner. The inherited verify closure at `tools/v0_s2_stage_runtime.py:238-246` invokes authority, compares config, checks complete_rehash/manifest/critical tool set, invokes resource_observer and checks leased user-root inode plus owned process birth and CLI/base-directory. Launch at247-251 invokes authority and `_complete`, then its locally captured original verify, returning candidate/auth/node identity. No production closure or `_user_root` is replaced in these probes. The fixture supplies synthetic tool/complete/authority/native observations, so this proves production logic and wiring, not true tool hashes or native browser execution.

The new repeat test separately verifies exact authority actions for verify, verify, launch, verify; launch's internal verify executes legally without entering a second wrapper/context. It checks candidate/output fields, no archive.used consumption, closed handles after each call, subsequent actual archive, callback refusal after deletion, and subsequent warm prepare/archive. Test count85 is original74 plus11 appended cases, not a reported constant trusted without execution.

## Finite callback inventory and lifetime audit

| Returned member / boundary | Production behavior and independent evidence |
|---|---|
| DefaultContext.verify_bindings | Original closure retained and wrapped once; per-call saved parent/root identity and run/candidate/auth/lease checks, original authority/config/tool/resource/user-root logic, final guard and close. Original M06 healthy case and repeated calls pass. |
| DefaultContext.authorize_launch | Original launch retained; original `_complete` and local original verify called inside one context. No false archive reentry for this legal nested verification. Original M06 launch and targeted repeated-call test pass. |
| WarmContext | No delayed callable fields. Actual returned default inventory contains exactly verify_bindings/authorize_launch; actual warm inventory is empty. Driver methods and data are not new wrapped factory entrypoints. |
| Prepare return / callback acquire | Preparation closes all FDs. Callback reacquires nofollow parent/root and compares saved device/inode/lease before original closure, rejects changed parent/root. No permanent handles. |
| Authority, complete, critical, resource callbacks | New10 negative cases include authority/critical errors, authority/critical/complete/resource identity drift, wrong config/binding, replaced parent/root. All reject and close captured handles; no archive destination or state consumed, roots/sentinels preserved. |
| Callback → nested archive | Independent reachable assertion invokes actual factory.archive from original authority. `_archiving` rejects reentry before owner work; root and archive.used remain intact, handles close, later real archive succeeds. |
| Error/success → archive | Wrapper has no swallowing handler and no deletion/refund. Existing real owner authorization, terminal cleanup proofs, inventory/hash/byte budget/manifest and deletion remain in the established full archive context. Default/warm success, M05 drift and prior errors pass freshly. |

Saved identities are unchanged at117-126 and reacquisition at129-177. The scope checks current factory run/candidate/auth, context binding and original lease; it never creates a new lease from a later pathname occupant. Root legitimately deleted by archive does not trigger a false final existence failure, while read-only callback success requires its final guard. Active preparation error/archive context reuse and failed-install retention fences are unchanged. The read-only wrapper itself invokes no archive owner, state consumption, source copy or cleanup. Original callbacks execute authority normally; they are not given extra budget or fabricated proof.

Mutable public fields versus captured provenance were examined explicitly. An unrelated public context.root is rejected by saved identity lookup before authority: independent reachable test confirms0 authority calls, no raw destination, unused archive state and unchanged sentinels. Altered candidate/auth/run is rejected by the unchanged six-probe suite; wrong callback config is rejected by the original closure. Captured original root/driver/config stay in the inherited closures. Deliberate mutation of private closure cells, saved identity tables or arbitrary hostile Python memory is outside this finite contract.

The exploratory `test_callback_provenance.py` tried to obtain a second warm root before replacing the default context.root. Both cases failed at unchanged `tools/v0_s2_stage_runtime.py:164`: **factory order/replay/default root not closed**, before assigning the changed field or invoking the target callback. Therefore the hypothesized cross-label adoption was not demonstrated and is not a blocker. This protective ordering requires the default root gone before warm; legitimate archive consumes default state and the new wrapper also refuses archived default callbacks. The two failed traces remain in raw/extra.*, and the probe source was not rewritten. The reachable tests were added separately, run once and logged separately; no speculative failure is converted to PASS.

## Immutable owners, evidence bindings and history

Only15 added/1 removed lines in the S3 factory and93 appended test lines differ from frozen contract. Base StageRuntimeFactory, stage sequence, package owner and OwnedArchive are byte-identical; inherited prepare is not copied, source installation/candidate/workflow/session/marker checks and earlier failure persistence remain unchanged. The old test file is an exact byte prefix. Immutable-boundary audit confirms every other preexisting path unchanged; no fixture/test/report/probe deletion.

Both changed source files exactly match final candidate Git blobs. All274 checksum entries across implementation05 and independent01–04 match. `raw/binding-recomputation.json` binds these results, command logs, historical summaries and prior evidence reuse. Prior archive9 source/test/bindings/oracles match e3f9427; prior package17 owner/test match5497bd1. Exact old commands, stdout, stderr, exits, guards, receipts and runners are hashed. Package tests use the unchanged in-process main/parser boundary; they do not execute the new wrapper. Archive9 is reused only as unchanged standalone owner evidence; new wrapper caller behavior is covered by fresh checks and static review. Neither is an external/native CLI proof.

All earlier findings/raw failures remain immutable, including correction04's original M06 failures, its initial implementation69pass/5fail, correction03 baseline/teardown issues and their owned-cleanup records, and raw whitespace. Current implementation05 raw85/23/5/1/1/6 results were inspected but not substituted for this review's runs. The review's two invalid exploratory failures and their raw whitespace also remain unchanged. Staging whitespace findings concern preserved raw tracebacks, not a changed product assertion.

Guard installs before pytest/plugins import, disables plugin autoload/bytecode/cache, allows Git only in freshly registered fixture repositories, denies shell/exec/spawn/network. All eight runs recorded1122 allowed Git children,0 S2 children,0 denials. All147 registered temporary paths are absent afterward; retained negative roots were removed only by owning synthetic fixture teardown. Fixture deletion is not rollback acceptance. No old tmp/runtime/claims or ledger, testSource or holdouts were inspected; no DB/archive/source/fixture copies committed. The final runner merely adds separate modes for reachable checks; original modes and their guards remain unchanged.

## Scope and remaining limits

Evidence is Linux/POSIX synthetic: actual package build/install, inherited prepare/closures and original archive owner with fake native/service/tool observations. Actual Windows/WSL/PowerShell/parser/host executable hashes, real media/models/GPU/services/network/download, real ledgers/claims and full checkpoint are0. No actual browser phase or native WSL/Windows proof. Controlled callback identity drift is covered; universal arbitrary OS races or hostile-memory guarantees are not claimed. Original relocated inode writes remain distinct from forbidden replacement writes.

Full S3 coordinator, profiles and budgets, A06 network blocking/attempt observation, fixed quality/resource acceptance, real rollback, product Gate0 and human/release gates remain unproved. This review closes M06's concrete inherited-callback regression and finds no new actionable blocker in the finite change; it does not reopen solved triggers for absent full product proof.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_CORRECTION_05_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE, from a62f7bc.
2. 本批完成: required121 pass, reachable extras2 pass; invalid exploratory2 failures disclosed/excluded, archive9/package17 reused; M06 closed, F0/M0/m0 scoped recommendation. Product acceptance/human signoff not performed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW,621b1bf386db71bfe08ca2f533fa8ec396b0504b, existing scoped human acceptance.
4. 当前阻塞门禁: coordinate P3A_M06_INDEPENDENT_REVIEW_AND_S3_GATE0_PENDING; M06 closure awaits root adjudication, full Gate0 remains pending.
5. 全局路线位置: P3A adjudication → complete S3 coordinator/quality/A06 → combined offline review → product Gate0 → bounded same-source execution → independent acceptance → required human signature.
6. 剩余工作: root decision and remaining complete S3 profiles/budgets/network/quality/rollback/gates.
7. 下一责任人: root architecture/gate owner; reviewer made no candidate edits.
8. 所需授权: none additional for completed offline review; no real-run permission inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a-correction-05/; report/receipt/findings/probes/guards/audit/raw/SHA256SUMS.
10. 精确停止原因: assigned independent final-candidate review complete; return once to root and retain visible window.

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

Current stage remains R1/WP-R1-U3; no completion counts advanced. Full substeps and distinct implementation/machine/independent/human states remain in raw/coordinate-extract.json.
