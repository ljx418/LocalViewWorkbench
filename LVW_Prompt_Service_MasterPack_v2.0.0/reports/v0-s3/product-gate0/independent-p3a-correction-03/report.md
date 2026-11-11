# Independent P3A correction03 review — CHANGES_REQUIRED

**Fatal0 / Major1 / Minor0 open. M04 is closed on final candidate e3f9427.** M01/M02/m01/M03 remain closed. New **P3A-C03-M05** affects the changed cleanup adapter after preparation returns; root adjudicates the scoped offline-component recommendation. No StagePASS/product Gate0/live/human/release claim.

Author: ljx418 <1173696783@qq.com>. Code `e3f9427f17c38def9216813842195b94b490698f`; evidence `73ce8585bc008e1ed0300c69f76b9bd8c8835dfd`; frozen contract `9aa110251c018ecaaefe4870b8047ef504bbc2de`. Initial status clean; requested merge fast-forwarded3ecd45b to73ce858, exit0, no reset. Coordinate read through git show e28b660 without merging metadata. Only this new report subtree is authored.

## Aggregated finding: P3A-C03-M05

Location: `tools/v0_s3_stage_runtime.py:42-45,66-72,100-102` and lifecycle teardown at171-193; write occurs at `tools/v0_s2_stage_archive.py:137`.

Trigger: normal `prepare_default()` completes, releasing preparation descriptors. The caller performs actual synthetic driver cleanup and invokes `factory.archive(context, cleanup)`. Inside the real delegated `remove_owned_reparse_fixture` callback, move the original parent and create a plain replacement at the old pathname, then return its legitimate cleanup result. This uses the new adapter, not a direct bypass of factory.archive.

Expected: refuse drift before archive directory creation/copy/deletion via the replacement parent. Actual: `_parent_fd` is None after preparation; `_preparation_guard` returns immediately both before and after the cleanup callback. Original OwnedArchive creates `default-raw` inside the replacement parent, then fails its next inventory with FileNotFoundError because the original root pathname vanished. The original root and foreign/sibling sentinels remain intact; no foreign deletion, overwrite or payload execution is demonstrated. The concrete violation is one empty replacement archive directory.

Reproducer: `test_callback_gaps.py::test_post_prepare_cleanup_adapter_rejects_replacement_before_archive_write`, exact guarded invocation in `raw/extra_post.command.json`. Structured `INDEPENDENT_POST_PREPARE_CLEANUP` and the failed `unexpected == []` assertion are preserved in stdout; exit1,0 passed/1 failed. This is a real failed Oracle, not an observation PASS. Scope is a controlled callback mutation at a reachable normal lifecycle call, not arbitrary malicious memory or an instruction-level OS race. Writes to a relocated original pinned inode remain permitted; this writes to the replacement inode instead.

The adapter itself preserves owner cleanup proofs and authorization; its guard lifetime is insufficient for post-prepare use. Root should decide the minimal authorized lifetime binding or explicit fail-closed behavior. Reviewer made no repair or scope expansion. This new issue does not reopen M04's allocation trigger.

## Final-candidate results and prior evidence

| Check | Actual result | Exit | Runs |
|---|---|---:|---:|
| Targeted original54 + correction11 |65 passed|0|1|
| Two old S2 files |23 passed|0|1|
| Old archive owner file |9 passed|0|1|
| Original unchanged correction01 five probes |5 passed|0|1|
| Original unchanged M04 gap probe |1 passed|0|1|
| New registration/adapter error assertions |3 passed|0|1|
| New post-prepare adapter assertion |1 failed|1|1|

All103 requested checks run freshly on final e3f9427 passed. Added gap checks3 pass/1 fail give106 fresh passes/1 failure total107. The implementer's six probe passes on a precursor were not reused as final proof. Prior17 package owner cases are explicitly **reused, not rerun or counted fresh**: package owner and test module are byte-identical to5497bd1; their direct in-process main/parser/default install/rollback tests do not depend on the changed runtime/archive. Exact old source and e9c910e command/stdout/stderr/exit/guard/receipt/runner hashes are in `raw/owner17-reuse.json`.

Four current source files match final candidate Git blobs. All78 implementation checksum entries plus101 previous-review entries match; bindings/raw in `raw/binding-recomputation.json`. Immutable-boundary Git diff is empty. Existing handoff tests remain an exact byte prefix with only appended new cases; original runtime/archive/probe test files are unchanged. No test/fixture deletion. New reviewer scripts and evidence only, no source snapshots.

## Complete finite callback/write matrix

### complete -> allocate

Locations: `tools/v0_s3_stage_runtime.py:122-134; tools/v0_s2_stage_runtime.py:167-168`. Parent pinned before inherited prepare; guard after complete; single-name exclusive mkdir relative to original parent, eight attempts, immediate nofollow pin. Evidence: targeted:complete-allocation, gap:unchanged M04 assertion, targeted:allocation-collisions, targeted:allocation-open-failure. Result: **NO_REPLACEMENT_WRITES_REPRODUCED**.

### authorize -> register/write

Locations: `tools/v0_s3_stage_runtime.py:85-98; tools/v0_s2_stage_archive.py:33-73`. Original factory/archive authorization still invoked; guards on both sides; optional descriptor-relative lease writer; no lease insertion before write/fsync success. Evidence: targeted:authorize-allocation, targeted:archive-authorization, targeted:registration-writer, extra:registration-write-zero, extra:registration-fsync. Result: **NO_REPLACEMENT_WRITES_REPRODUCED**.

### register/lease -> subdirectories

Locations: `tools/v0_s3_stage_runtime.py:56-60,112-143`. Real archive register/lease compared to allocated root identity; directory creation relative to pinned root; nofollow child opens; return guards. Evidence: targeted:register-directories, targeted:registration-writer, archive:9 original owner cases. Result: **NO_REPLACEMENT_WRITES_REPRODUCED**.

### deploy -> sample/reference writes

Locations: `tools/v0_s3_stage_runtime.py:236-240; tools/v0_s2_stage_runtime.py:179-188,117-137`. Base copy owner remains called with pre/post guards; deploy return reaches guarded first copy; reference copies use same override; checks before native preflight. Evidence: targeted:deploy-samples, targeted:default-warm-installed-root, probes:prior fix assertions. Result: **NO_REPLACEMENT_WRITES_REPRODUCED**.

### native callbacks -> final evidence

Locations: `tools/v0_s2_stage_runtime.py:178-258; tools/v0_s3_stage_runtime.py:119-120,145-163`. Guards after constructor/preflight/RAM/start/model/CLI/registry/binding/sampler/observer-summary and before final persistence; final evidence single-name exclusive/nofollow relative to allocated root/temp. Evidence: targeted:native-final-evidence, targeted:post-deploy-return, targeted:post-deploy-copy. Result: **NO_REPLACEMENT_WRITES_REPRODUCED**.

### error/cleanup -> receipt/archive/delete

Locations: `tools/v0_s3_stage_runtime.py:33-72,100-102,171-234; tools/v0_s2_stage_archive.py:129-138`. Failure writer anchors original parent; failed-install fence retained; adapter delegates actual cleanup and original owner checks; guard active only during preparation. Evidence: targeted:error-archive, targeted:cleanup-callback, extra:unproven-adapter-result, probes:unchanged M03, extra_post:post-prepare cleanup callback. Result: **OPEN_P3A_C03_M05_POST_PREPARE_GUARD_INACTIVE**.

All seven candidate callback injections were independently executed on final source; their replacement inventories compare equal before/after. The first five injections start no fake services. The native-final-evidence injection occurs after one fake Ollama/Comfy start each and triggers no further start after the move; it is not presented as zero starts for that whole test. `raw/adjacent-observations.json` retains exact events and inventories. Error-archive and the candidate's deeper cleanup test verify the adapter during preparation failure; M05 adds the previously untested post-prepare invocation of the same changed adapter.

Static review covers native constructor, preflight, RAM, Ollama/Comfy startup, cloud gate, model, CLI/user root, registry, binding writer, sampler, resource observer/ownership summary and final evidence. The new base no-op boundary hook is invoked after these controlled transitions before subsequent pathname side effects. Reference copying still goes through guarded original _copy; subsequent reference-file creation has no intervening application callback until authorization, which is guarded before and after. Guards are not substituted for descriptor writes where introduced: root creation/subdirectories, lease receipt, final evidence and failure evidence use fixed relative names and original descriptors.

## Allocation, errors, legacy behavior and adapter authority

Parent is pinned before inherited prepare. The final unchanged M04 probe confirms verification-time parent move produces replacement entries0/services0, anchored original failure and null/UNKNOWN because no root was allocated. Allocation is eight bounded random-name exclusive mkdir attempts on the original parent, immediate O_DIRECTORY/O_NOFOLLOW open and recorded inode; collisions preserve existing bytes. Open failure retains the newly allocated directory with UNKNOWN and original error, without pathname rollback. Root is allocated/pinned before register but never falsely called archive-registered; the actual archive owner publishes its lease only after its receipt write succeeds.

Independent new registration probes force zero-progress write and fsync failure. Both preserve exact triggering errors, retained allocated root=true, archive_registered=false, no services, no lease insertion, unchanged sentinels and closed descriptors. Failure receipt disk state is PERSISTENCE_UNPROVEN and memory becomes PERSISTED only after its own successful write/fsync. Candidate tests also cover open/conflict/write/fsync failures in terminal persistence, later preparation failure, successful close and moved-parent retention. Original error wins over persistence error; no fallback pathname writes or retry deletions were introduced.

AST normalization restores original root allocation, directory creation and final evidence statements and removes only new no-op boundary calls: the remaining base _prepare is identical to frozen base. All other preexisting base methods are unchanged. Only existing archive method `register` changed; original archive __call__, lease checks, ownership/terminal proof checks, inventory, copying, hash checks and state transitions remain unchanged. Default registration persistence still takes the original pathname branch; S2 allocation/directory/evidence defaults preserve prior behavior. Independent23 S2 +9 archive regressions corroborate these limited compatibility claims. No copied_prepare algorithm.

`_ArchiveCleanupBoundary` forwards original evidence/listener_proofs/owned references and invokes the real remove callback once. It supplies no forged cleanup proof or authorization and does not suppress state changes. The independent refusal test makes that real callback return unproven after running: OwnedArchive rejects, default-raw is absent, used={'default'} remains consumed, root retained and the original final-evidence exception survives. This establishes the adapter does not bypass the owner's authority; M05 separately establishes its guard is inactive after prepare.

Installed package hash/manifest/candidate/bridge AND workflow seals, no-follow archive snapshot, post-install exact bytes/sets, marker/lease/owner/session identities remain unchanged. Real synthetic package build/install and original archive execute; dirty source and forbidden copy fallback still prove installed bytes feed the same inherited start_comfy argument/CLI base-directory. All NativeRuntime service/model/registry boundaries are synthetic; these checks are not real execution or rollback acceptance.

## History, cleanup and limits

Historical baseline audit2 pass/5 fail and cleanup-boundary0 pass/1 fail remain intact. Historical targeted01 was64 pass plus1 teardown error, exit1; its os.open injector blocked cleanup, and an exact owned-path cleanup receipt records the retained fixture's later removal. Targeted02 was64 pass/exit0; final targeted03 was65 pass/exit0; both S2 runs23 and both archive runs9 passed. Precursor five probes and one gap passed, but this review reran them on final source. Original raw whitespace and all earlier findings remain unchanged. No old /tmp was inspected; historical cleanup was assessed from immutable records, not repeated.

130 registered temporary paths from these seven independent runs are absent afterward.825 children were permitted Git commands only inside newly registered synthetic repos; regression/archive child counts0, no guard denials. Root allocations made through mkdir are registered/pinned by production code where successful and remain inside owned fixture parents. Retained failure roots are removed only by owning fixture teardown; no historical root manipulation, DB/ZIP/source snapshots committed.

Guard is installed before pytest/plugins import, rejects subprocesses outside approved Git fixture cwd (including -C), shell/exec/spawn/network calls, and disables plugin autoload/bytecode/cache output. Exact argv/environment/cwd/stdout/stderr/exits are raw. Actual Windows/WSL/PowerShell/parser/host executable hashes, real media/model/GPU/services/network/download, testSource/holdouts, programledger/old roots or claims and checkpoints are0.

Platform evidence is Linux/POSIX only. Native WSL/Windows deployment remains unverified; no-follow/dirfd unsupported behavior remains fail-closed and no universal adversarial namespace/memory guarantee is claimed. Descriptors may address a legitimately relocated original inode; replacement inode side effects are not exempt. Full S3 coordinator/profiles/budgets, A06 blocking/attempt observation, quality/resource and real rollback acceptance, product Gate0 and required human/release gates remain unproved.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_CORRECTION_03_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE from e28b660; review scope offline P3A component.
2. 本批完成: full six-boundary static/dynamic audit; final requested103 passes, added3 passes/1 failure; reused owner17 separately; M04 closed, M05 open; F0/M1/m0. Product machine/human acceptance not performed.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b, existing scoped human acceptance.
4. 当前阻塞门禁: coordinate product executor/Gate0 pending plus P3A-C03-M05 post-prepare cleanup lifetime.
5. 全局路线位置: P3A closure -> complete S3 coordinator/quality/A06 -> combined offline review -> product Gate0 -> bounded same-source execution -> independent acceptance -> required human signature.
6. 剩余工作: root adjudication of one aggregated new Major and authorized correction; remaining full S3 profiles/budgets/network/quality/rollback/gates.
7. 下一责任人: root architecture/gate owner; reviewer made no candidate repairs.
8. 所需授权: none additional for this completed offline review; no real-run permission inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a-correction-03/; report/receipt/findings/audit-matrix, guards/probes/binding audit, raw/SHA256SUMS.
10. 精确停止原因: assigned final-candidate review complete with reproducible M05; return once to root for adjudication, retain visible window.

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

Current coordinate is R1/WP-R1-U3 with correction03 independent-review gate. V1-D0 preparation2/2 and unified early slice3/3 remain scope-limited; no counts advanced. Full coordinate distinctions are in raw/coordinate-extract.json.

Review staging check exits2 for trailing whitespace in the preserved failed extra_post traceback only; raw bytes remain unchanged. This is separate from the failed test exit1.
