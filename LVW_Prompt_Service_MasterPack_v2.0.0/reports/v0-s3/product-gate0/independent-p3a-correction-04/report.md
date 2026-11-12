# Independent P3A correction04 review — CHANGES_REQUIRED

**Fatal0 / Major1 / Minor0. P3A-C03-M05 is closed; new P3A-C04-M06 is open.** P3A-M01/M02/m01/C01-M03/C02-M04 remain closed. This recommendation covers the corrected offline deployment component only; root adjudicates. No StagePASS, product Gate0, live execution, human acceptance or release claim.

Author: ljx418 <1173696783@qq.com>. Final code `00b63d97e8a860ea1bf4759b04da0cf8045423a7`; merged evidence `b508f9dcb283c338c7cebabe0b3e81e5dac6654b`; frozen contract `ae4dbc48ec4c58d09f7df460ced4bad68a91275d`. Initial clean worktree was fast-forwarded with requested merge --no-edit, without reset. Only this new report directory was authored. Latest coordinate is read from e718c87 without merging metadata.

## Aggregated finding: P3A-C04-M06 — returned browser callbacks cannot authorize

Location: `tools/v0_s3_stage_runtime.py:88-93,106-108,250-253`; inherited callbacks `tools/v0_s2_stage_runtime.py:238-252`; production handoff `tools/v0_s2_stage_sequence.py:142-145`.

Trigger: successful actual inherited `factory.prepare_default()` returns its DefaultContext and closes all preparation descriptors, as required. Invoke either returned `context.verify_bindings(context.browser_config, action)` or `context.authorize_launch(context.browser_config)` with unchanged bindings and valid synthetic authority. No namespace mutation is needed.

Expected: preserve the usable inherited browser handoff: call the original authority and validate the current binding/root, without retaining preparation handles indefinitely or accepting replacement identities. Actual: both callbacks call `self.authorize`, whose first `_preparation_guard()` now raises `EvidenceError: protected lifecycle descriptor unavailable` because `_parent_fd` is None. The original authorization callback is never reached: authority_calls_after_prepare=0 for both, root_exists=true. Archive reacquisition does not cover these callbacks; the special inactive compatibility branch applies only to archive.original.authorize. Before correction04 the inactive guard returned; this is a concrete newly introduced regression in the changed lifetime guard, not a request to implement a new coordinator.

Impact: the inherited default browser phase cannot enter its authorization/verification handoff after otherwise successful installed preparation. This is a Major functional blocker, not a security bypass or proof of real browser execution. The unchanged sequence actually passes these returned functions to run_browser_phase. No code repair was made; preserving the guard while restoring the bounded handoff is root's design decision.

Reproduction: `test_archive_lifetime_gaps.py::test_returned_browser_context_remains_usable_after_prepare`, two parameter cases. Exact guarded command is `raw/extra.command.json`; original exception trace and structured RETURNED_BROWSER_CONTEXT are in `raw/extra.stdout.log`. These are **two failed assertions**, not expected-error passes: the exception is printed then reraised. Valid config, real package installer, inherited prepare and returned closures are exercised; only native/service boundaries and authority/tool observation are synthetic. No actual browser/native child is invoked.

## Final-candidate results

| Check, each run once | Passed | Failed | Exit |
|---|---:|---:|---:|
| Final targeted installed-runtime and handoff files |74|0|0|
| Old S2 runtime and browser-component regressions |23|0|0|
| Unchanged original correction01 five probes |5|0|0|
| Unchanged M04 gap |1|0|0|
| Unchanged M05 post-prepare gap |1|0|0|
| Additional context mismatch3 and replay1; returned browser callbacks2 |4|2|1|

Required104/104 pass freshly on final00b63d9. With six bounded additional checks, **108 passed / 2 failed / 110 fresh checks**. No precursor stitching. Extra checks are limited to the changed lifecycle's callers, context identity and terminal replay. No broad suite, P2B237, earliest historical observations or full checkpoint was run.

Prior **9 archive +17 package owner checks are reused, not fresh**. `raw/binding-recomputation.json` binds exact prior command/stdout/stderr/exit/guard/receipt/runner hashes and old/current source hashes. Package owner and test module are identical to5497bd1; those tests invoke main/parser in process, with the historical native boundary substitution, and do not call this S3 factory. Archive owner, its bindings/oracles dependencies and archive test file are identical to final e3f9427. Its nine cases cover unchanged owner internals only. Effective new S3 wrapper callers are separately assessed by fresh74, unchanged M05 and extra checks, including the new M06 failure; reuse does not certify the new wrapper. Neither set is proof of an external/native CLI execution.

Two changed source files match final Git blobs. All216 checked implementation/current-prior-review checksum entries match. Every preexisting path outside those two authorized source files is unchanged from frozen contract; only new implementation evidence is additional. Base StageRuntimeFactory, stage sequence, OwnedArchive and package owner are byte-identical. Old handoff tests remain an exact byte prefix, with nine tests appended; no fixture/test deletion. The inherited prepare algorithm is not copied. Binding audit records actual Git commands/stdout/stderr/exits; the metadata audit executes no candidate code.

## Affected lifecycle matrix and M05 closure

| Boundary | Review and evidence | Conclusion |
|---|---|---|
| Preparation register → saved identity | Actual allocated root is compared with original archive lease; parent/root dev+ino, fixed name/label, run/candidate/auth saved at source117-126. Fresh prior assertions and installed prepare tests. | Original identity retained; not adopted later from a pathname. |
| Prepare return → later archive acquire | Source129-177 opens parent through nofollow directory_handle and root through O_DIRECTORY/O_NOFOLLOW; fstat compared with saved identities and lease, before original owner call. Fresh parent/root replacement and open-error cases. | Refusal before destination/copy/delete; no resident FDs after prepare. |
| Archive context/binding/reentry | Source130-145 rejects reentry, missing match, changed bindings/lease; active prepare requires matching sole label/root and parent. Candidate reentry test plus independent candidate/auth/run mismatch3 and terminal replay1. | Invalid contexts do not create default-raw or consume unused owner state; valid original still archives. Replay preserves manifest bytes. |
| Actual owner authorize → cleanup callback → archive writes | Wrapper source66-72 scopes entire real owner; original authority guarded when active; adapter source41-45 guards real callback before/after. Unchanged M05 probe and fresh callback/authority-move tests. | M05 closed: adapter invoked, cleanup proven, then EvidenceError parent drift, replacement_writes=[], original_root_retained=true, lifecycle FD None after call. |
| Owner copy/manifest/delete → teardown | Real OwnedArchive remains source137-179 with inventory, byte budgets, hashes, source rechecks, lease checks and exclusive manifest; new scope surrounds whole call. Fresh default→archive→warm→archive success. | Actual synthetic archives prove both roots removed and manifests correct; all captured FDs closed; foreign/sibling bytes unchanged. No final root-existence guard falsely turns legitimate deletion into failure. |
| Active prepare error → archive/failure persistence | Existing failure retention fence and fixed descriptor-relative persistence unchanged; matching active lifecycle reused without closing caller's FDs. Five prior probes, targeted early/later errors and persistence failures rerun. | Original triggering error retained; root true/false/null based on original inode observation; disk attempt PERSISTENCE_UNPROVEN, memory PERSISTED only after fsync. |
| Prepare return → returned browser authorization | General authority wrapper still used after prepare, but strict absent-context guard now raises. Independent returned callback2. | **Open M06**, separate from repaired archive adapter lifetime. |

The unchanged M05 probe runs the original archive owner after actual inherited prepare and synthetic native cleanup. The real cleanup callback moves the parent; the postcallback guard raises before the owner creates default-raw. Replacement entries written by production are0, original root retained. Failure does not return an archive-proven result or refund anything. Tests explicitly separate valid synthetic cleanup proof from completion of the archive operation.

Acquisition failures unwind ExitStack: parent/root handles close, cleared _root_fds and _parent_fd, _archiving=false. Active preparation owns its handles until its outer finally. Callback exceptions propagate through the owner and contextmanager; there is no new catch that masks their original type or performs pathname fallback. Success deletes the root legitimately and releases handles without a final existence requirement. Original archive state changes, ownership/terminal evidence, authorization and byte limits remain executed, not mocked out. Adapter forwards actual evidence/listener_proofs/owned references, never fabricating cleanup success. Retained failed deployments are refused before archive reacquisition. Direct legacy owner access remains compatible by design; protected factory.archive always enters the identity context and cannot take that inactive-authority branch during its owner call.

Controlled-callback scope matters: the owner still uses checked pathname operations internally; the accepted finite guarantee is checks at actual controlled callback handoffs with pinned/saved identities. This is not a universal hostile-memory/instruction-level OS race guarantee. Writes through an original relocated inode remain permitted; replacement inode writes do not. Source archive snapshot, bounded validation/decompression, exact candidate/bridge/workflow seals, installed bytes/ownership/session checks and service-start gating are unchanged and exercised in fresh targeted/probe runs. This does not reopen M01/M02/m01/M03/M04.

## Evidence, history and limits

Audit hooks are installed before pytest/plugins import; plugin autoload, bytecode and pytest cache are disabled. Children are permitted only as Git commands in newly registered owned synthetic Git repos; no shell/exec/spawn/network. Six runs recorded957 allowed Git children; S2 regression child count0; no guard denials. All130 registered temporary paths are absent after owning fixture teardown. Roots made by production mkdir are within those owned fixture parents. Fixture deletion is not product rollback. No old /tmp, historical roots, program ledger/claims, testSource or human holdouts were read or manipulated; no binary DB, ZIP, source or fixture copies are committed.

Implementation initial targeted01 remains69 pass/5 fail, exit1; final targeted02 remains74 pass, exit0. Original correction03 baseline failures,64/65 results, teardown error/owned-path cleanup, prior findings and raw-log whitespace remain unchanged. They are historical evidence, not final proof. `raw/binding-recomputation.json` retains history summaries and exact hashes. This review's failed tracebacks also retain original whitespace; staging whitespace exit2 is separate from the real extra-test exit1.

Real Windows/WSL/PowerShell/parser/host executable hashes, models/GPU/media/services/network/download, real ledgers, old roots/claims and full checkpoints:0. Evidence is Linux/POSIX synthetic only; native WSL/Windows remains unverified. Full S3 coordinator/profiles/budgets, A06 offline enforcement/attempt observation, fixed quality and resource acceptance, real rollback, product Gate0 and human/release gates remain unproved. The new failure is reachable by inherited production interfaces but no real browser, service or full sequence was executed.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3A_CORRECTION_04_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE from e718c87; scoped offline component review.
2. 本批完成: final required104 pass; bounded extra4 pass/2 fail; archive9/package17 reused separately; M05 closed, M06 open, F0/M1/m0. No product machine/human acceptance.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b, existing scoped human acceptance.
4. 当前阻塞门禁: coordinate P3A_M05_INDEPENDENT_REVIEW_AND_S3_GATE0_PENDING; review closes M05 but adds M06 returned browser callback authorization regression for root adjudication.
5. 全局路线位置: P3A closure → complete S3 coordinator/quality/A06 → combined offline review → product Gate0 → bounded same-source execution → independent acceptance → required human signature.
6. 剩余工作: root adjudicate aggregated Major and authorize correction; full S3 profiles/budgets/network/quality/rollback/gates remain.
7. 下一责任人: root architecture/gate owner; reviewer made no candidate repairs.
8. 所需授权: no additional authorization for this completed offline review; no real-run permission inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3a-correction-04/; report, findings, structured receipt, scripts, raw and SHA256SUMS.
10. 精确停止原因: assigned review complete with reproducible new M06; return once to root, keep window visible.

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

Current coordinate remains R1/WP-R1-U3, correction04 independent review. No development counts advanced; V1-D0 preparation and unified early-slice completion are scope-limited. Full substeps and separate implementation/machine/independent/human states are preserved in raw/coordinate-extract.json.
