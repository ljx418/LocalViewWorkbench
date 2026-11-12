# Independent P3B correction04 review

**CHANGES_REQUIRED — component review only. Fatal 0 / Major 4 / Minor 0.** Candidate `5de09478a4af6e3dd91410d4dde90c9020a77bfd`; evidence commit `0d28fd4d607808c1980f66ff86b289cbcc5134e8` merged with `--no-edit` into existing clean review worktree. No fixes, candidate changes, root metadata merges, V2 changes, old-evidence edits, pushes or config changes. Root intake/current outline read only via `git show 67d5c87eaa1a4429c78e49602f760a807f81711f`.

The once-only combined suite passed **175/175**, guard selftest blocked **4/4** deliberate attempts, inspected counterexample replay produced **29 observations**, independent focused public-owner probes produced **38 observations**. Observations are not additional passing product tests. True inner/outer exits are0 for all four runs. Commands, actual module paths/hashes, raw streams and cleanup are in `commands.json` and each runner receipt. A prelaunch path typo exited2 before any focused validation; retained in commands.json, not hidden as a test pass.

All five required SHA256 pins match, including module `db78f5314df765aa4b27efec4e0fb1f13faf8e47fdc516c55f4f3a6fe4b6973d`, test `8469e072d92efc15110bd634f781878241a0bcc7b86925f3d840ec98d7c41751`, runner `77385fceaf403cbf60529c1161ed9c38693db803b526189ee9bfd87989c1425f`, contract `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`, projection `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`. Git candidate blobs independently match working bytes; before/after hashes and actual imported locations match in all executable runs. Candidate argument alone receives no attestation credit. All48 implementation SHA256SUMS entries match.

## Findings

### M01 — Major

Location: `tools/v0_s3_quality_phase.py:165 QS_RECEIPT_CONTENT_FIELDS;174 QS_ROW_CONTENT_FIELDS;2698 _verify_execution_content;2740 _effective_error_code;2976 known-failure resolution`.

**Trigger:** After genuine public production-owner run, inject exactly one unknown validation failure after original oracle, retaining its raw and release evidence. Change only supplied rows[0].error_code from INDEPENDENT_UNKNOWN_VALIDATION to PUBLIC_EXECUTION_NOT_SUCCESSFUL; keep canonical/seal/raw untouched.

**Expected:** Published unknown failure stays unresolved; supplied verdict overrides can only be stricter. All supplied actual execution content must be bound to canonical.

**Actual:** Canonical unknown FAIL aggregates false and unresolved. Supplied known error gives resolved=true and aggregate=true (9/10 images,6/6 videos,critical0); row stays unusable. Additionally valid fabricated GPU samples, bound baseline100->200 plus supplied releases, test_counts and row attempt flag all return aggregate=true with unchanged canonical.

**Prerequisites:** Control supplied receipt dictionary; one unknown ordinary validation error with complete raw/source/release evidence. Reproduction injects that unknown failure after real owner/oracle rather than claiming a naturally observed native failure. No artifact-root write required.

**Evidence:** `focused-observations.json:published_unknown_failure`, `focused-observations.json:published_unknown_failure_supplied_known_error`, `focused-observations.json:valid_but_fabricated_release_samples`, `focused-observations.json:fabricated_bound_baseline_and_release`, `focused-observations.json:fabricated_terminal_counts`, `focused-observations.json:fabricated_attempt_row`.

**Correction direction:** Determine known/unknown failure resolution from both authoritative and supplied verdicts; a published unknown error may never be replaced by a known one. Bind actual baseline/release/counters/attempt content, or consume authoritative values while allowing explicitly stricter constraints. Preserve fully verified known FAIL resolved/notusable and critical evidence.

### M08 — Major

Location: `tools/v0_s3_quality_phase.py:2537 load_source_plan;2634 _row_evidence_complete;2866 recompute_scores sealed_rows[index]`.

**Trigger:** After genuine run, change source-plan first-row asset_id to FOREIGN-ASSET, media_kind to video, or input_reference to foreign.png; update only canonical/supplied source_plan length/hash to describe changed bytes. Keep canonical execution row, raw, descriptor path/identity and all other source fields intact.

**Expected:** Seal asset/kind/reference/ordinal/bytes/hash/path/descriptor must align to corresponding canonical frozen-order execution row. Internally contradictory seal cannot certify that row even with correct artifact hash.

**Actual:** All three inconsistent labels yield usable=true,resolved=true,aggregate=true. Loader enforces key set and ordinal but never compares asset_id/media_kind/input_reference against execution row; source validator compares descriptor identity/bytes/hash/path only. Whole row swaps reject on ordinal; descriptor swap remains unresolved.

**Prerequisites:** Write seal and canonical/supplied source_plan binding hash/length. This is not a dictionary-only hash bypass, nor total coherent rewrite of canonical execution content: execution row still contradicts loaded seal.

**Evidence:** `focused-observations.json:seal_label_alignment.asset_id`, `focused-observations.json:seal_label_alignment.media_kind`, `focused-observations.json:seal_label_alignment.input_reference`, `focused-observations.json:seal_swap.swap_whole_rows`, `focused-observations.json:seal_swap.swap_descriptor`.

**Correction direction:** Cross-check every loaded seal row against canonical row and fixed projection order/identity before using it. Original descriptor equality and mandatory typed contexts now work and must remain. A total coherent rewrite of both trusted originals requires a separate parent archive trust/attestation decision; universal hostile-host signatures are not requested.

### NM03 — Major

Location: `tools/v0_s3_quality_phase.py:2454 load_published_execution_receipt;2408 load_canonical_receipt;2556 _safe_artifact_path`.

**Trigger:** After genuine run, rename owned run_root/temp to retained-temp and replace temp with symlink to retained-temp; pass original run_root/temp/s3-quality to public QS, original receipt/scores.

**Expected:** Strict canonical artifact-root ancestry rejects redirected temp/run-root paths, preserving actual run-root/temp/s3-quality trust boundary.

**Actual:** aggregate=true,usable=true,resolved=true while temp is a symlink. Only final s3-quality and canonical leaf symlinks are checked; root.parent.parent.resolve matches original run_root and _safe_artifact_path resolves away redirected ancestor. No canonical/seal/raw edits needed.

**Prerequisites:** Write/rename owned temp ancestor; original trusted artifacts unchanged. Reproduction is bounded same-root redirection, not evidence of arbitrary native-host access.

**Evidence:** `focused-observations.json:qs_temp_ancestor_symlink`.

**Correction direction:** Validate canonical/source-plan/raw ancestry against strict actual run root without silently following redirected ancestors; preserve bounded reads and exclusive publication.

### NM04 — Major

Location: `tools/v0_s3_quality_phase.py:1556 _execute_row final _validate_source then1559 _resolve_driver_state then1566 _send_admission_guard;949 guard checks ownership/clock/proof only`.

**Trigger:** Conforming max_public_submissions getter changes first source mtime/ctime with os.utime after final source validation; same source content/hash/path and actual production owner still execute.

**Expected:** A controlled accessor handoff cannot invalidate original full descriptor identity without another source validation; zero sends,16 terminal refusals when first source identity changes.

**Actual:** 16 sends,16 charges,34 reserved/observed,16 PASS; actual source mtime/ctime differ from sealed/recorded identity and public QS aggregates true. Final guard checks directory ownership, phase time and parent proof but does not revalidate source after driver accessors.

**Prerequisites:** A controlled driver accessor mutates prepared source descriptor before first send. No canonical/seal/dictionary rewrite or real media.

**Evidence:** `focused-observations.json:limit_source_identity_changed`.

**Correction direction:** Finish controlled driver accessors before the final bounded source check, then perform coherent final clock/proof admission and immediate charge/cached submit without unchecked callbacks. Preserve no-refund/no-retry accounting. This is a source handoff gap; the original capacity/time accessor counterexamples are fixed.

## Verified progress, regression obligations and limits

Public QS now really loads bounded canonical receipt and bounded source plan. Missing, corrupt, foreign or staged-only canonical evidence and missing/tampered/replayed seal refuse. Original descriptor identity substitutions against unchanged seal are unresolved. Missing/null/float/bool run root/baseline refuse on both PASS and known FAIL paths. A published known FAIL supplied as PASS remains unusable and resolved; genuine known failure with zero critical may satisfy9images/6videos while critical3 remains visible and blocks aggregate. Unknown storage/cleanup flags remain unknown. Fixed16, images8/10, videos5/6, per-sample>=8 and critical0 remain unchanged. No all-technical-rows-success condition was added.

The source plan is produced exclusively through bounded owned artifact writer after initial validation of all16 and before any send. It carries actual ordered descriptor identity/path/hash/bytes and run/candidate/auth/projection; canonical binds its length/hash. Actual trace: QD source48/release16, QS source32/release32, so shared validators execute at initial validation and both pre-send checks, not merely appear by name. Seal storage failure gives0sends/0charges/0reserved/16BLOCKED, storage unknown, all phase directory handles closed. Original media can be removed after archive without a QS live restat (once175 regression). Baseline physically retains139 entries/229442 bytes including6334-byte plan; inherited unchanged accounting tests independently enumerate retained entries/bytes and count both staging/canonical hardlinks. The file-cap adaptation7->8 accounts for the extra plan; original first-row/exact/one-over assertions remain. No exact real8MiB/128MiB/256 matrix was rerun: previous independent frozen-cap proofs remain valid, source writer/counter checks unchanged.

All145 previous collected nodeids occur in the new175. AST comparison covers every100 old test function and decorators/parametrization:98 test definitions are identical; two adapted tests remain, no deletion. File-cap7->8 leaves assertions identical; ancestor redirect now snapshots existing legitimate seal and verifies no new entries, no canonical and zero sends after redirect. This preserves the original post-redirect no-new-write invariant under exclusive pinned writers; file-set comparison alone is not universally stronger than an empty-set check or a content-hash comparison. _prepare only adds optional driver injection with identical default. See test-obligation-audit.json per-test/nodeid/assertion binding. New30 definitions all collect/run; destructive fixtures use private roots and reach their intended canonical/seal/context/clock/accessor guard (asserted stable reasons), rather than failing setup. Two new source-inspection tests and one direct one-clock guard unit are structural checks; actual public-run traces/boundaries independently supplement them. They are not counted as additional production integration proof.

NM01 original capacity/time driver-accessor bugs are fixed: limit/submissions/submit binding occur before admission, capacity0 and clock10801 give0sends/16BLOCKED. NM02 uses one final finite monotonic sample for phase and parent interval; public exact10800 accepted/one-over10801 refused in the once175. Later expiry/diminution keep earlier1send/1reservation/1charge and block15 with no refunds/retries. The new source handoff gap NM04 is distinct. Parent proof retains exact run/candidate/auth and strict typed1/4 cumulative<=34. Cooperative checks do not preempt hanging callbacks. Parent hard supervision remains **UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER**.

Actual production nodes/ControlledImageOwner/BridgeOwner/manual and video production oracle paths execute; only HTTP/provider and tiny decoder boundary are synthetic. Fresh4x4 PNG/tinyfakevideo fixtures only. The guard was inspected before reuse and installs audit hook before pytest/plugins/product/test imports, disabling autoload/cache/bytecode. Python audit guard blocks named connect/bind/DNS/Popen/system/exec/spawn/fork events; deliberate selftest attempts are blocked before action. No universal native-extension/direct-syscall claim.

## Trusted artifact root and integration prerequisite

The consistent_seal_and_canonical_identity_rewrite probe does aggregate true, but requires rewriting the original trusted seal, authoritative canonical execution row and hash/length binding, plus supplying the coherent changed receipt. That is control of both original trusted artifacts; it is not an unchanged-canonical/dictionary bypass and does not establish that a new signing platform was promised. This review does not count that coherent hostile-root rewrite itself as an additional code defect. Before a real consumer run, the parent must supply an owned immutable archive or independently retained original artifact attestation and bind the selected run/root to it; actual integration is NOT_PROVEN. Implementation accepted_limitations is not root approval or Stage PASS. M08 above is narrower: the allegedly bound documents contradict each other on row labels despite a valid seal hash, which is checkable without cryptography. M01 and NM04 require no trusted-artifact rewrite.

## Prior closure mapping and historical evidence

| Prior | Current scoped disposition |
|---|---|
|M02|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M03|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M04|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M05|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M06|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M07|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M09|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|m01|CLOSED_SCOPED_OFFLINE_PRESERVED — Unchanged prior obligations in test-obligation-audit.json, once-only175 suite and static source review; no broader product claim|
|M01|PARTIALLY_FIXED_REMAINS_OPEN — Canonical missing/corrupt/foreign/staged-only and field bindings improve; see M01/NM03 residuals.|
|M08|PARTIALLY_FIXED_REMAINS_OPEN — Actual exclusive original16 seal, QD48source/16release, QS32source/32release, mandatory typed contexts and original tuple comparison work; seal row alignment M08 and accessor source handoff NM04 remain.|
|NM01|CLOSED_ORIGINAL_CAPACITY_ACCESSOR_COUNTEREXAMPLE_SCOPED_OFFLINE — replay limit capacity0 and focused submissions capacity0 / submit clock10801 all zero-send16BLOCKED; separate new source handoff NM04.|
|NM02|CLOSED_SCOPED_COOPERATIVE_ONLY — One final clock sample reused for both phase/parent proof; original second read absent; actual public exact10800 accepted/10801 rejected in once175. Parent hard preemption remains unimplemented.|
|E01|CLOSED_FACTUAL_CORRECTION_ONLY_HISTORY_UNCREDITED — Root55a6bc0 append-only erratum authoritative; original12 exits UNKNOWN/zero-external-actions NOT_PROVEN remain uncredited. New current guarded evidence cannot certify history.|
|E02|CLOSED_APPEND_ONLY_COUNT_LABEL_ERRATUM — correction03 actual22 vs older21, current correction04 replay29 observations. Exact frozen cap proofs remain prior independent six realcap observations, not cap-mutating replay labels.|

Current implementation edit01..11 receipts retain actual exits **0,0,1,0,1,0,1,1,0,0,0**, each with source before/after unchanged and actual product/test module paths/hashes. Green final175, guard4 and replay29 receipts/log hashes verify separately. The48 checksum entries include retained edit failures; their earlier source states are not misrepresented as final candidate. No historical attempt was replaced or rewritten. Retained per-edit receipts report their guard/order and source hashes; the final runner is inspectable, but per-edit runner byte digests were not emitted, so final-runner inspection alone cannot retrocertify every historical runner byte or all earlier attempts. The11 retained diagnostics are distinct from the original unguarded12. Root55a6bc0 append-only erratum remains authoritative: original10piped+2direct attempts have UNKNOWN underlying exits, zero-external-actions NOT_PROVEN and no acceptance credit; correction03 replay22 vs earlier21 retained. Current guarded runs cannot certify those earlier attempts. Recovery guidance msg_a30e3ca84e71 was NOT delivered despite root send receipt; worker actually merged55a6bc0, not6bbfeb9. Review uses actual code/commands/frozen task, not undelivered instructions; no request to reopen implementer to merge metadata.

## Scope and cleanup

Only new review-subtree text is committed. Fresh owned nested roots recorded in replay/focused JSON are removed in finally; runner receipts attest all four enclosing owned roots removed (exact outer paths not emitted by immutable runner), owned phase handles closed, no older fixture roots scanned/deleted. Raw streams retain actual output and true exits; no piped pytest/debug imports or uncontrolled executable validation. Replay adapter reads immutable replay source, changes only OUT assignment through AST to avoid old evidence writes, and executes inside guard; it does not copy product/test source into Git. Static review/report scripts only parse text/AST/JSON and invoke separately authorized read-only Git.

Zero actual Windows/WSL/PowerShell/parser/host-executable hashing/real media/FFmpeg/model/GPU/service/network/download/real ledger/fullcheckpoint actions. No testSource/holdout/fullprelabel reads, DB/ZIP/binaries, permanent config, push or history rewrite. Production parent hard supervision/owned cleanup, native residue/admission, A06 enforcement/attempt observation, actual registration baseline/install rollback, authentic parent ledger debit, realquality/full12, Gate0, human/release signatures and crash durability of parent directory entry remain NOT_PROVEN. This is one aggregate review and a component recommendation; no StagePASS/productPASS.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / READY_FOR_REVIEW, root67d5c87 read-only.
2. 本批完成: Independent review175/175 once, guard4/4 once, replay29 and focused38 observations once; Fatal0/Major4/Minor0; CHANGES_REQUIRED.
3. 最后通过门禁: UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b; existing scoped human acceptance unchanged.
4. 当前阻塞门禁: S3_P3B_CORRECTION04_ISOLATED_REVIEW_PENDING in current control; this review recommends local CHANGES_REQUIRED, all native/product blockers retained.
5. 全局路线位置: Root aggregate adjudication → bounded local correction/separate review → parent/native residue/admission/A06/Gate0 → finite real16 and independent semantic scoring → required human/release gates.
6. 剩余工作: Four findings plus listed product integration/acceptance obligations; no coordinate or denominator advancement.
7. 下一责任人: Root architecture/gate owner for aggregate disposition, visible authorized implementer for any new correction, separate independent reviewer.
8. 所需授权: No additional human approval needed for completed authorized offline review; no real-runtime authority inferred.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3b-correction-04/; review.md/findings.json/receipt.json and command/source/obligation/raw/cleanup evidence.
10. 精确停止原因: Assigned independent review complete; hand off aggregate findings with full commitSHA once and keep terminal visible.

## Full V0–V3 outline from current root

Source root67d5c87 gitshow-only execution-control; current Stage **R1**. Full substeps/status/evidence unchanged in root-current-control.json and receipt.json. No V2 candidate/future activation or root metadata merged.

| Delivery | Stage | Done/total | Implementation | Machine | Independent | Human |
|---|---|---:|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|

Full declared substeps (same current root):

- **V0-S0**: 盘点与探索记录 [DONE]; 完整生产基线 [FAILED_HISTORICAL].
- **V0-S1**: 独立人工稿与导出 [DONE]; 真实图片与预处理 [DONE]; 四输出与草稿保护 [DONE]; 固定证据及独立审查 [DONE]; 人工签署 [DONE].
- **R0**: 独立单图路径在R1a验证 [DONE]; 完整复用/许可清单单独闭合 [NOT_VERIFIED].
- **R1a**: 正式合同子集与前后端 [DONE]; 真实单图链路 [DONE]; 失败/服务控制与人工稿保护 [DONE]; 独立审查七项 [DONE]; 人工体验签署 [DONE].
- **V0-S2**: WP-S2-00 冻结准备 [DONE]; WP-S2-01 媒体owner [DONE]; WP-S2-02 公开视频路径 [DONE]; WP-S2-03 安全/资源/取消 [DONE]; WP-S2-04 离线集中收口 [DONE]; WP-S2-05 完整真实验收 [DONE]; WP-S2-06 独立审查 [DONE]; S2 人工签署与Git同步 [PENDING].
- **V0-S3**: 包/清单/使用说明 [PENDING]; 安装诊断与回滚 [PENDING]; 独立质量集与标注 [PENDING]; 离线集中收口 [PENDING]; 真实十二项及质量 [PENDING]; 独审/人工签署/同步 [PENDING].
- **R1**: 受控媒体与人工镜头 [PENDING]; 六模式四目标 [PENDING]; SQLite/修订/导入 [PENDING]; 组合回归及阶段审查 [PENDING].
- **V1-M1**: M1-A detection/PTS/boundaries/timeline [PENDING]; M1-B per-shot evidence and serial child jobs [PENDING]; M1-C per-shot drafts/exports/fixed8 full validation [PENDING].
- **R2**: 异步任务/CAS/取消 [PENDING]; 真实图视频及质量 [PENDING]; CLI/导出/便携包 [PENDING]; V1累计独审及人工签署 [PENDING].
- **R3**: 真实PTS/切镜 [PENDING]; 资产/FTS5/配方 [PENDING]; 对比/QC/JSONL [PENDING]; 阶段验收 [PENDING].
- **R4**: MCP真客户端 [PENDING]; 批量/lease/幂等 [PENDING]; 备份恢复 [PENDING]; V2累计验收签署 [PENDING].
- **R5a**: 对端握手 [PENDING]; Navia证据 [PENDING]; Narralens建议/冲突 [PENDING]; 阶段真实验收 [PENDING].
- **R5b**: Comfy allowlist/映射 [PENDING]; 收据/outbox [PENDING]; GPU/取消协作 [PENDING]; 阶段真实验收 [PENDING].
- **R5c**: 集成UI [PENDING]; 升级回滚 [PENDING]; 三系统E2E [PENDING]; V3独审及人工签署 [PENDING].
