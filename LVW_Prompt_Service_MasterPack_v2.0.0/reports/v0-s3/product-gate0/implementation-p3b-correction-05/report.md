# S3-P3B aggregate correction 05 — implementation report

**READY_FOR_REVIEW — component only. No Stage PASS, no product PASS, no Gate0.**

| Item | Value |
|---|---|
| Code candidate | `44ad8c7a30ee418af41834de6cc87685f80d42fa` |
| Root disposition merged | `08e6fbe8f0bcf4443b1832758327de798d78481b` (`--no-edit`, fast-forward) |
| Code baseline (corrected before) | `5de09478a4af6e3dd91410d4dde90c9020a77bfd` |
| Evidence baseline (before) | `0d28fd4d607808c1980f66ff86b289cbcc5134e8` |
| Independent review that produced the four findings | `8ea70dac74a81ae407fa149ca7f3d8c716c103ae` |
| Root adjudication | `reports/v0-s3/product-gate0/p3b-correction-05.adjudication.json` (`CHANGES_REQUIRED_F0_M4_m0`) |
| Module SHA256 (candidate) | `6229569649fde3a5542a4d5c1ced95ea0268cb885baae3a9f18b4a69cc41fbaf` |
| Test module SHA256 (candidate) | `052502d17bfb462b3831c75c8135a1384422a28b978880e68b4d1a98681e102a` |
| Guarded runner SHA256 | `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8` |
| Counterexample probe SHA256 | `202b14adc23c773896b85de503bac1ea19a047184fd1f28c2abf4580160f6ffa` |
| Evidence directory | `reports/v0-s3/product-gate0/implementation-p3b-correction-05/` |

The correction-04 independent review proved four Major gaps through public
production-owner probes although the 175 case suite was green. All four are
closed here in one frozen correction. No contract, threshold, denominator,
public schema or frozen artifact was changed, and no new infrastructure,
signing platform, ledger API or worker platform was added.

## 1. What was corrected

### M01 — the canonical document is the authority; the facts are bound exhaustively

| | |
|---|---|
| Production path | `tools/v0_s3_quality_phase.py:217` `QS_RECEIPT_OVERLAY_FIELDS`, `:222` `QS_ROW_OVERLAY_FIELDS`, `:251` `QS_RECEIPT_TYPED_CONTEXTS`, `:3051` `_verify_execution_content`, `:3101` `_effective_failure_verdict`, `:2979` `_row_evidence_complete`, `:3182` `recompute_scores` |
| Oracle | the canonical receipt that is actually published on disk under the owned artifact root, read through the strict boundary of `:2510` `_ArtifactBoundary`; the sealed original source plan; the independent scoring receipts |
| Negative | the published unknown failure stays unresolved under a supplied known error; a fabricated release sample vector, a fabricated bound baseline, a fabricated terminal count, a fabricated row attempt flag, an extra row fact and a fabricated run context are all refused or leave the row unresolved; every published field outside the closed overlay is bound |
| Terminal | `QS_EXECUTION_CONTENT_MISMATCH:<field>` for a forged fact, `EVIDENCE_UNKNOWN:RELEASE_EVIDENCE_NOT_CANONICAL` for a fabricated release observation, `UNKNOWN_EXECUTION_FAILURE` for a published unknown failure, `QUALITY_INCOMPLETE_UNRESOLVED_ROWS` for the aggregate |
| Cleanup | the supplied document is never written to; only the private owned roots of the probe are touched and they are removed in a `finally` block; the owned phase handles are closed by the phase itself |

* The permitted verdict overlay is a **closed enumeration** with an explicit monotone
  meaning (`QS_RECEIPT_OVERLAY_FIELDS`, `QS_ROW_OVERLAY_FIELDS`). The verdict fields
  and the evidence declarations are the only fields in which a supplied document may
  differ from the published one.
* Every **other** field of the published document is an actual execution fact and has
  to be reproduced **exactly**. The comparison is exhaustive over the published
  document, so the binding cannot be an incomplete ad-hoc list: a fact that is not
  named in the overlay can never be forged, and a fact that the execution starts to
  record later is bound automatically. A supplied row may not even carry an extra
  fact that the published row does not have.
* The known/unknown resolution of a failure is decided from the published **and** the
  supplied state and error together. A published unknown validation failure with
  intact raw, source and release evidence stays **unresolved** even when the caller
  supplies a known error, so critical zero plus nine of ten images and six of six
  videos can never become an aggregate pass.
* A published known failure supplied as a pass stays **resolved and not usable**; a
  fully verified known failure stays resolved and not usable; a published pass
  downgraded by a supplied known failure keeps the existing resolved and not usable
  obligation. The independent critical count stays global (`published_fail_critical3`).
* The release proof of a row must be the **published observation itself**. A well
  typed but fabricated GPU sample vector, a fabricated bound baseline and a
  fabricated terminal count are therefore no longer accepted as real observed
  evidence.
* A **mistyped** bound context (a null, a float, a boolean or a non string run root
  or baseline) stays an invalid declaration: the per row evidence validation makes
  every row unknown and the mistyped value is never compared and never accepted. A
  **well typed** context is a fact and has to reproduce the canonical one exactly.
* No all-technical-success condition was added. The thresholds are untouched: fixed
  sixteen, per sample total ≥ 8, images ≥ 8 of 10, videos ≥ 5 of 6, critical
  hallucinations 0, 34 provider calls.

### M08 — the seal must describe the very same canonical execution row

| | |
|---|---|
| Production path | `tools/v0_s3_quality_phase.py:2812` `_verify_seal_row_alignment`, `:2840` `load_source_plan`, `:1338` `_persist_source_plan` |
| Oracle | the canonical execution row of the published receipt and the fixed admitted projection order and identity (the canonical rows keep the frozen ordinals 1..16 and every asset appears exactly once) |
| Negative | one negative per field of the seal row (asset, media kind, input reference, size, hash, path, descriptor identity, ordinal) and two swaps (whole rows, descriptor), each after a genuine run, each with a consistently updated seal hash and length binding while the canonical execution row stays untouched |
| Terminal | `QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:<field>:<index>` and `QS_SOURCE_PLAN_ORDER_INVALID` |
| Cleanup | the private owned root of the case is removed by pytest; no old evidence root is written |

* Every one of the sixteen sealed rows is now cross-checked against the corresponding
  canonical execution row: the ordinal, the asset, the media kind, the input
  reference, the size, the hash, the path and the **full five component** descriptor
  identity. A seal that contradicts the execution row it claims to seal can no
  longer certify that row, even when its own artifact hash and length binding is
  consistent.
* The actual descriptor provenance, the strict typed run root and baseline, the
  shared QD and QS validators, the exclusive pre-send source plan, the bounded
  accounting and the absence of any original live media requirement after the
  archive are all preserved unchanged.

### NM03 — the strict artifact ancestry of the scoring entry point

| | |
|---|---|
| Production path | `tools/v0_s3_quality_phase.py:2510` `_ArtifactBoundary`, `:2700` `_boundary_error_code`, `:2716` `load_canonical_receipt`, `:2760` `_verify_run_root_binding`, `:2840` `load_source_plan`, `:3182` `recompute_scores` |
| Oracle | the real `<run root>/temp/s3-quality` directory of the run, opened level by level against its own pinned parent |
| Negative | a redirected temp ancestor, a redirected run root, a redirected phase directory, a redirected canonical receipt, a redirected source plan and a redirected raw artifact — every one of them with the trusted bytes unchanged |
| Terminal | `QS_ARTIFACT_ROOT_REDIRECT_FORBIDDEN:<level>`, `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN`, `QS_SOURCE_PLAN_REDIRECT_FORBIDDEN:…`, `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN:<asset>` |
| Cleanup | every descriptor of the boundary is closed in a `finally`; the owned fixture root of the case is removed |

* The run root, the `temp` directory and the phase directory are opened against
  their own pinned parent with `O_DIRECTORY|O_NOFOLLOW`, and the entry is inspected
  relative to that parent with `follow_symlinks=False`. A renamed ancestor that was
  replaced by a symlink is therefore **refused**, never resolved and adopted. The
  identity of every level is checked again after every read.
* The canonical receipt, the source seal and the raw artifacts all use that one
  boundary, so no evidence type can have a weaker ancestry rule than another. The
  bounded 8MiB + 1 read, the no-overwrite staging and the retained entry accounting
  are unchanged.
* Accepted limitation: this is an in-process inode observation inside the existing
  audited Python/filesystem trust model. It does **not** claim immunity against a
  hostile kernel, against a native Windows reparse point or against a filesystem
  that moves inodes underneath the process. No new global platform was required and
  none was added.

### NM04 — the final source handoff

| | |
|---|---|
| Production path | `tools/v0_s3_quality_phase.py:1583` `_execute_row`, `:1260` `_validate_source`, `:1076` `_resolve_driver_state`, `:1026` `_send_admission_guard`, `:1338` `_persist_source_plan` |
| Oracle | the exclusive source seal, written once before the first public submission, and the bounded five component descriptor identity that it records |
| Negative | a conforming `max_public_submissions` accessor that changes the timestamps of the first source, and one that changes a later source at the sixth accessor read |
| Terminal | `SOURCE_REPLACED` on the changed row, `HALTED_AFTER_SOURCE_REPLACED` on the later rows, all sixteen rows terminal, no row left `NOT_RUN` |
| Cleanup | the phase closes every owned handle; the private owned root of the case is removed |

* The reorder is at the **owner**, not a special case in the driver: every controlled
  driver accessor — the submission counter, the public submission limit and the
  submit callable itself — and every controlled callback is now resolved **before**
  the final bounded source verification, and that verification is made against the
  **sealed original** five component descriptor identity.
* Then the single coherent admission decides the send: the ownership check, the one
  final monotonic clock sample, the typed parent proof and the remaining capacity.
  The reservation and the attempt charge follow immediately and the cached submit
  callable is used. Between the admission and the submit there is **no** unchecked
  callback, no `getattr` and no extra clock read; the source check itself is the last
  observation before the admission.
* A source that a controlled accessor changed produces **zero sends, zero charges,
  zero reserved provider calls** and sixteen terminal refusals. A later change
  preserves the earlier real attempts and charges and stops every later send.
* The original obligations are unchanged: capacity zero refuses every send, the
  clock 10801 accessor refuses every send, the exact 10800 is accepted and one over
  is refused, the strict proof run/candidate/authorization and the cumulative
  1 or 4 ≤ capacity ≤ 34 are unchanged, and there is no refund and no retry.
* A synchronous callback can still hang. The parent hard watchdog stays
  **UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER**.

## 2. The original 175 obligation audit

| Item | Value |
|---|---|
| Baseline candidate of the corrected batch | `5de09478a4af6e3dd91410d4dde90c9020a77bfd` |
| Collected nodeids of the baseline | 175 |
| Collected nodeids of this candidate | 206 |
| Baseline nodeids missing from this candidate | **0** |
| Test definitions in the baseline module | 130 |
| Test definitions of this candidate | 155 |
| Definitions with an **identical** body and identical decorators | **130** |
| Adapted definitions (weakened or changed expectation) | **0** |
| Deleted definitions | **0** |
| Added definitions | 25 (31 collected nodeids, seven of them parametrized) |
| Evidence | `reports/v0-s3/product-gate0/implementation-p3b-correction-05/obligation-audit.json` |

No original obligation was adapted, weakened or deleted in this batch. The audit
compares the AST of every test definition of the baseline module with the AST of this
candidate module; it imports no product module and executes no product code. The
nodeid comparison against the baseline run receipt is a second, independent
statement of the same fact.

## 3. The runs (each exactly once, on the committed candidate)

| Run | Mode | Exit | Collected / result | Raw streams |
|---|---|---:|---|---|
| `full-final` | suite | 0 | 206 collected, **206 passed** in 72.04s | 271 stdout bytes, 0 stderr bytes |
| `guard-selftest` | guard | 0 | **4 of 4** deliberate attempts blocked before the action | 459 stdout bytes, 0 stderr bytes |
| `counterexamples` | script | 0 | **21 observations** of the independent correction-04 counterexamples | 22363 stdout bytes, 0 stderr bytes |

* Every runner invocation pinned the runner, the probe and both source hashes
  **before and after** the run (`source_unchanged_during_run`, `runner_unchanged_during_run`,
  `probe_unchanged_during_run` are all true in the three receipts), recorded the
  actually imported module paths and hashes, captured the raw stdout and stderr at
  the file descriptor level, wrote the true process exit code next to them and
  removed its own temporary fixture root (`owned_root_removed` is true in all three).
* The guard audit hook is installed **before** pytest, before any plugin and before
  any product or test import; plugin autoload, the cache provider and bytecode
  writing are disabled. The blocked events are `socket.connect`,
  `socket.connect_ex`, `socket.bind`, `socket.getaddrinfo`,
  `socket.gethostbyname`, `socket.gethostbyaddr`, `socket.getnameinfo`,
  `subprocess.Popen`, `os.system`, `os.exec`, `os.spawn`, `os.posix_spawn`,
  `os.fork` and `os.forkpty`.
* The new runner and the new probe live only in this new subtree. The old runner and
  the old probes were not modified and were not re-run. No direct or piped pytest,
  no ad hoc product import and no shell pipeline masking was used at any point.
* The observations of the `counterexamples` run are **observations**, not additional
  product tests. The product obligations are the 206 cases of the suite.
* The exact frozen capacity matrices, the P3A 121, the P2B 237 and the full project
  suite were **not** re-run for a count. Their previous independent proofs remain
  valid and are not restated here. The old correction-03 original twelve attempts
  remain UNKNOWN and uncredited; no historical attempt was rewritten or cosmetically
  re-run.

## 4. The trust boundary and the unresolved risks

The root accepted the independent distinction that a **total coherent rewrite of both
the original trusted canonical document and the original trusted seal** is not a new
cryptographic-signature obligation. The `consistent_seal_and_canonical_identity_rewrite`
observation still aggregates true, exactly as the correction-04 review recorded it,
and that is the accepted trust boundary rather than a code defect. This acceptance
does **not** waive:

* an internally contradictory seal label — now refused (`M08`),
* a caller-only rewriting of an actual execution fact — now refused or unresolved
  (`M01`),
* a pre-send source change by a controlled accessor — now zero sends and zero
  charges (`NM04`).

Unresolved risks and product obligations that this batch does **not** close:

* **Parent archive / attestation binding is NOT_PROVEN.** Before a real consumer
  run the parent still has to bind the selected owned archive or root to the
  retained original artifacts or an independently retained attestation. The
  integration of that binding with this component is not proven here.
* **Parent hard process supervision is UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER.** A
  synchronous callback can still hang; only the cooperative pre and post checks
  exist.
* **Native residue admission, A06 enforcement and attempt observation**,
  **registration baseline, install and rollback**, **authentic parent ledger
  debit**, **real quality against the real frozen quality set**, **the real twelve
  fixed items**, **the product Gate0**, **human experience signature** and
  **release signature** all remain NOT_PROVEN. The crash durability of the parent
  directory entry remains unproven.
* The scoring verdict still covers only the bound sixteen rows of this run, the
  four sampled frames still cannot prove motion continuity, and the reviewer
  identities are still only a schema and binding check.

## 5. The scope of the batch

* Zero actual Windows / WSL / PowerShell / parser / host executable hashing, real
  media decoding, FFmpeg, model, GPU, service, network, download, real ledger or
  full checkpoint actions. Only fresh 4x4 PNG and tiny fake video fixtures behind
  the actual production nodes, the `BridgeOwner` and the public oracles.
* No test source, holdout or full prelabel was read. No binary, media, database,
  archive or copied source was committed.
* Only `tools/v0_s3_quality_phase.py`, `tools/test_v0_s3_quality_phase.py` and the
  new text of `reports/v0-s3/product-gate0/implementation-p3b-correction-05/` were
  changed. The old reports, checksums, logs, runners, probes and test evidence are
  untouched, and no product or public contract, frozen packet, projection, quality
  set, prelabel, owner, package, P3A, ledger, authority, workflow, prompt, root
  coordinate, global MANIFEST or V2 document was touched.
* Every own temporary fixture root is registered and removed; no old root was
  touched. The retained editing diagnostics of this batch are kept in
  `editing-diagnostics/` with their raw logs and true exits.
* Git identity, read and merge operations were performed separately; there was no
  push and no permanent configuration change.

## 6. Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / READY_FOR_REVIEW; the root disposition `08e6fbe` and the current control are unchanged.
2. 本批完成: the four Major findings of the independent correction-04 review are corrected in one frozen batch; the once-only combined suite is 206 of 206, the guard selftest is 4 of 4, and the focused counterexample replay is 21 observations; the original 175 obligations are preserved with 0 adapted and 0 deleted definitions.
3. 最后通过门禁: UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on `621b1bf386db71bfe08ca2f533fa8ec396b0504b`; the existing scoped human acceptance is unchanged.
4. 当前阻塞门禁: S3_P3B_CORRECTION05_INDEPENDENT_REVIEW_PENDING; this batch is a component recommendation only, and every native, product, human and release blocker is retained.
5. 全局路线位置: Root aggregate adjudication → this bounded local correction → independent review of `44ad8c7` → parent / native residue / admission / A06 / Gate0 → the finite real sixteen and the independent semantic scoring → the required human and release gates.
6. 剩余工作: the independent review of this candidate, the parent archive and attestation binding, the parent hard watchdog, the native residue admission and A06, the registration baseline, install and rollback, the authentic parent ledger debit, the real quality against the real frozen set, the real twelve fixed items, Gate0 and the human and release signatures. No coordinate or denominator advanced.
7. 下一责任人: the separate independent reviewer for the four findings, then the root architecture and gate owner; the human for the high risk authorisations and the final experience signature.
8. 所需授权: no additional human approval was needed for this authorised offline correction; no real runtime authority is inferred from it.
9. 证据目录: `reports/v0-s3/product-gate0/implementation-p3b-correction-05/` — `report.md`, `receipt.json`, `SHA256SUMS`, `full-final.*`, `guard-selftest.*`, `counterexamples.*`, `counterexample-observations.json`, `obligation-audit.json`, `editing-diagnostics/`.
10. 精确停止原因: the frozen correction-05 batch is complete, the candidate is committed and the evidence is handed over once for the independent review; the terminal stays visible and no further work is started on this task.

## 7. Full V0–V3 outline from the current root control

The table and the declared substeps below are read from the `development_outline` of
the current `plans/execution-control.json` and are unchanged by this batch.

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
- **R3**: 真实PTS/切镜 [PENDING]; 资产/FTS5/配方 [PENDING]; 对比/QC/JSONL [PENDING]; 阶段真实验收 [PENDING].
- **R4**: MCP真客户端 [PENDING]; 批量/lease/幂等 [PENDING]; 备份恢复 [PENDING]; V2累计验收签署 [PENDING].
- **R5a**: 对端握手 [PENDING]; Navia证据 [PENDING]; Narralens建议/冲突 [PENDING]; 阶段真实验收 [PENDING].
- **R5b**: Comfy allowlist/映射 [PENDING]; 收据/outbox [PENDING]; GPU/取消协作 [PENDING]; 阶段真实验收 [PENDING].
- **R5c**: 集成UI [PENDING]; 升级回滚 [PENDING]; 三系统E2E [PENDING]; V3独审及人工签署 [PENDING].
