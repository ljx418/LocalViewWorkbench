# S3-P3B aggregate correction 07 — the bounded named custody of every earlier consumed artifact

**READY_FOR_REVIEW only.**  This is an implementation batch.  It is not a Stage
pass, it is not a product Gate0 pass and it does not close the parent, native,
A06, registration, ledger, real-quality or human-release gates.  The
independent review of this candidate is the next step and it has to be
performed by a separate instance.

| Item | Value |
|---|---|
| Root disposition commit | `d0cc0f99ed33c73bd2a33d717e8eecee1c5e9abe` (merged with `--no-edit`) |
| Independent review of the previous batch | `4fb52ff3d4ef0b6bb4bcadabbd0598ce581a81af` (Fatal0 / Major1 / Minor0, `CHANGES_REQUIRED`) |
| Baseline code / evidence | `ba34b1581fc5e8e8b4de6ba469484e8eae416da1` / `b66aebaddedab3eb2bee88dda18d7657b94ff6d4` |
| Candidate code commit | `fd96cbc37574b382f483e757e8d7235ed5d2598c` |
| Product source sha256 | `e670b330f239ab931ab512dcf6f13ec8b3ec35b0d3932d88e8198b94c34bac22` (`tools/v0_s3_quality_phase.py`) |
| Test source sha256 | `fdda5ed7bc5ccfa8bc2f61f8b8a81f4713905a0fd689a2cd066995ceff6e7b0d` (`tools/test_v0_s3_quality_phase.py`) |
| Guarded runner (immutable, reused unchanged) | `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8` (`…/implementation-p3b-correction-05/run_guarded_checks.py`) |
| Counterexample probe sha256 | `dc4cc52a4990b9668014ae0618d9e72a5ec3b88c98c23ee12068afd1b44d5392` |
| Obligation audit script sha256 | see `receipt.json` → `code_sha256` |
| Frozen contract / projection | `reports/v0-s3/product-gate0/p3b-quality-contract.md`, `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json` — **unchanged** |
| Contract change | none.  No threshold, no denominator, no public schema and no quality rule changed. |
| Files changed | `tools/v0_s3_quality_phase.py`, `tools/test_v0_s3_quality_phase.py`, plus this new report subtree. |

The one remaining root of the correction-06 independent review is addressed in
this batch: **NM03** — the custody of *every* earlier consumed canonical
receipt, source seal and raw artifact had to live until the final completion
check of the whole evaluation.

---

## 1 — NM03: what was still wrong

`_ArtifactBoundary.read()` opened the child directories and the leaf of the
path it was reading, verified the *current* named entries against the pinned
handles **while those handles were still held**, and then closed every
descriptor and threw the bindings away.  `_ArtifactBoundary.verify()` only
knew the three pinned levels — the trusted parent, the run root and the phase
directory — and the `temp` level between them.

The consequence was a lifetime hole in the custody:

* an artifact that was read **early** (the canonical receipt, the source seal,
  the first raw leaves) lost its identity custody at the end of its own read;
* a later read could therefore rename it, replace it by a plain file, replace
  its parent by another plain directory, redirect it by a symlink or remove
  it, and the evaluation still consumed it as if nothing had happened;
* the final verification before the verdict had no binding left to compare
  the current name with, so the run aggregated true with a redirected
  canonical receipt.

The independent correction-06 review reproduced **six** such counterexamples
against the public QS entry point after a genuine public-owner run.  Every one
of them kept the genuine original bytes and left the caller receipt
unchanged; only the *name* stopped naming the object that had been read.

---

## 2 — NM03: what was changed

### One boundary-owned custody for the whole evaluation

`tools/v0_s3_quality_phase.py` now has a private `_NamedCustody` class.  The
custody is owned by the boundary, it lives from the first read until the
boundary is closed, and it records, for every directory and every leaf that
was opened for a read:

* the **parent** descriptor the name is relative to,
* the **name** itself,
* the pinned **identity** `(st_dev, st_ino)` of the object that was opened,
* the **kind** of the entry (`dir` or `file`),
* and the **descriptor** of that very object.

The identity custody is therefore *anchored*: a child name is always checked
against the pinned descriptor of its own parent, never against an absolute
path and never against a name that was resolved again.

### The verification points

`_verify_custody_entry()` compares

1. the **pinned handle** itself with the recorded identity — so the handle is
   never a stale or a reused descriptor — and
2. the **current, no-follow, parent relative** `stat` of the name with the
   same identity.

It is applied at four points:

| Point | What is verified |
|---|---|
| before a controlled read | the reused pinned handle against the current name |
| after a controlled read | the current path, while the handles are still held |
| on every later handoff | **every** entry that was consumed earlier |
| before a successful verdict | the final completion check of `recompute_scores` |

`_ArtifactBoundary.verify()` no longer stops at the three top directories: it
walks the whole custody, so an entry that was consumed in the first read is
still verified in the last one.

### A plain replacement and a missing entry refuse exactly like a symlink

The observation never resolves, adopts or follows anything away:

* a name that is a **symlink** is not a directory and not a plain file → refused,
* a name that is a **different plain file** or a **different plain directory**
  has a different identity → refused,
* a name that is **gone** → refused,
* a **replacement is never adopted and never reopened** as authority: the
  pinned descriptor is the only source of the bytes, and the refusal happens
  before the verdict.

The refusals carry their own vocabulary — `QS_ARTIFACT_CUSTODY_MISSING`,
`QS_ARTIFACT_CUSTODY_REPLACED`, `QS_ARTIFACT_CUSTODY_REDIRECT_FORBIDDEN` —
and the boundary translates them into the caller's own reason
(`QS_RAW_ARTIFACT_UNREADABLE`, `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN`,
`QS_SOURCE_PLAN_REDIRECT_FORBIDDEN`, …), with the precise custody reason
kept in the message.

### The bounded resource strategy

The custody is taken **once per name**.  A repeated read of the same name
reuses the pinned descriptor instead of opening a second one, and the
descriptor is read from its own beginning (`lseek` to zero), so a reused
descriptor is never read from a stale offset.  The descriptor use of an
evaluation is therefore bounded by the number of **distinct** names it
consumed and never by the number of reads it performed.

The bound is `_CUSTODY_ENTRY_LIMIT = 4 * (FIXED_TOTAL + 2) = 72`.  It is
derived from the frozen sixteen row shape: one canonical receipt, one source
seal and one raw leaf per row, plus the shared `rows` directory and one row
directory per row — 35 names for a genuine evaluation, so the bound is a
conservative multiple that a genuine evaluation can never reach.

It is an **internal, fail-closed** bound.  It is *not* a public threshold, it
is *not* a platform limit, it was not widened to let a run pass, and it never
conflicts with the frozen contract.  An evaluation that would need more
custody refuses with `QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED` instead of growing
its descriptor use without bound.

### Every owned resource is closed exactly once

`close()` releases the custody first and then the levels, and it is
idempotent.  The custody is closed on the ordinary path, on a refusal, on a
read exception and on a partially constructed boundary.  The measured
descriptor counts are in §4.

### What was *not* changed

* No threshold, no denominator, no public schema, no quality rule, no
  frozen contract, no projection, no prelabel, no owner, no package, no P3A
  file, no authority, no ledger, no workflow, no prompt, no coordinate and
  no global manifest.
* The typed actual facts and the closed key sets (M01), the seal alignment
  and the full M08 alignment, the monotone canonical and supplied failure
  constraints, the critical hallucination visibility, the actual raw hash,
  byte and `cap + 1` binding, the original source plan provenance and the
  absence of a live media re-stat in QS are all unchanged.
* The NM04 order is unchanged: the last original source check after the
  driver accessors, then the single clock and proof guard, then the
  reservation, the charge and the cached submit; the exact `10800`, the one
  over `10801` and the later proof are unchanged; there is no refund and no
  retry.
* The fixed sixteen rows, the 34 provider calls, the 8/10 images, the 5/6
  videos, the `>= 8` score, the zero critical hallucinations, the known
  failure that stays resolved and not usable and the absence of an "all
  technical success" rule are unchanged.
* The closed M02/M03/M04/M05/M06/M07/M09/m01 and the earlier NM01/NM02 are
  not reopened; the static obligation audit shows 0 adapted and 0 deleted
  original definitions.

---

## 3 — the tests

`tools/test_v0_s3_quality_phase.py` adds **13** new definitions and **13**
new cases.  Every one of them drives the **public** QS entry point
`recompute_scores` after a genuine public-owner run, or drives the real
`_ArtifactBoundary` of the product.  No test asserts the existence of a list
or a helper.

| Test | What it proves |
|---|---|
| `…_a_canonical_receipt_replaced_after_its_read_is_refused` | a plain file with the very same bytes replaces the canonical receipt during the first raw read → refused, original bytes unchanged, caller receipt unchanged |
| `…_a_canonical_receipt_redirected_after_its_read_is_refused` | a symlink replaces the canonical receipt during the source seal read → refused, original bytes unchanged |
| `…_a_source_seal_that_disappears_after_its_read_is_refused` | the source seal is removed during the first raw read → refused, retained bytes unchanged |
| `…_a_raw_leaf_redirected_after_its_read_is_refused` | a symlink replaces the first raw leaf during the second raw read → refused |
| `…_a_raw_parent_replaced_after_its_read_is_refused` | a different plain directory replaces the parent of the first raw leaf during the second raw read → refused |
| `…_an_earlier_nested_parent_that_disappears_is_refused` | the nested parent of an earlier consumed leaf is removed during a later read → refused |
| `…_a_canonical_receipt_redirected_before_the_completion_check_is_refused` | the canonical receipt is redirected immediately before the final completion check → refused |
| `…_a_repeated_read_keeps_a_bounded_custody` | eight repeated reads of three names change neither the custody nor the descriptor count |
| `…_the_custody_is_released_when_the_evaluation_refuses` | a refusing evaluation leaks no descriptor |
| `…_the_custody_is_released_after_a_successful_evaluation` | a successful evaluation leaks no descriptor |
| `…_a_repeated_tiny_read_is_exact_and_one_over` | the reused descriptor is exact at `cap` and refuses at `cap - 1` |
| `…_a_growing_leaf_is_refused_through_the_reused_descriptor` | a leaf that grows between two reads of the same name is refused |
| `…_a_clean_genuine_run_still_aggregates` | one clean honest baseline still aggregates: 10/10 images, 6/6 videos, zero critical, `aggregate_pass` true, and no stage or Gate0 claim |

The first seven are exactly the six independent counterexamples of the
correction-06 review plus the earlier nested parent that disappears.

---

## 4 — the guarded evidence

Every executable observation went through the **inspected, immutable**
correction-05 runner (`016e61a0…`), reused unchanged and pointed at the new
output paths of this subtree.  The audit guard is installed **before** pytest,
before any plugin and before any product or test import; the plugin autoload,
the cache provider and the bytecode writing are disabled; `connect`, `bind`,
the DNS resolution, `Popen`, `system`, `exec`, `spawn` and `fork` are
blocked.  This is named Python audit coverage, not direct syscall immunity.

| Invocation | Result | Inner / outer exit |
|---|---|---|
| Combined product suite (`--mode suite`) | **245 passed** (232 frozen + 13 new), 84.98 s | 0 / 0 |
| Guard selftest (`--mode guard`) | **4** audit events blocked | 0 / 0 |
| Focused new counterexamples (`--mode focused -k correction07_nm03`) | **13 passed**, 232 deselected | 0 / 0 |
| Independent bounded observations (`--mode script`) | **8** observations, 6 reproduced counterexamples | 0 / 0 |

Every receipt records the exact argv and the true exit code, the raw stdout
and stderr files with their hashes and byte lengths, the source hashes
**before and after** the run, the runner and probe hashes before and after,
the actual imported module paths with their hashes, the guard configuration
and the removal of the owned temporary root.

The static obligation audit (`audit_test_obligations.py`, a git read outside
the guard by design) compares the frozen baseline `ba34b15` with the
candidate `fd96cbc`:

* 180 baseline test definitions → 193 candidate test definitions,
* **180 identical, 0 adapted, 0 deleted**, 0 changed old helpers,
* **232** frozen collected node ids → **245** candidate node ids,
  **0** frozen node id lost, 13 added,
* the baseline and the candidate product source hashes are bound.

### The debug phase before the final evidence

`debug/` keeps the two guarded runs of the **debug** phase, before the
candidate was committed and before the final evidence was produced:

* `debug-focused` — the thirteen new cases, 13 passed, 232 deselected,
* `debug-counterexamples` — the first bounded observation of the six
  counterexamples.

Their raw streams and receipts are kept as they are; they are **not** the
final evidence and they do not certify the final candidate.  The final
evidence is the four runs of the table above, and it was produced **once**
each on the committed candidate `fd96cbc`.  No historical run was repeated,
no historical raw stream was regenerated or relabelled and no cosmetic
re-run was made.

### The six independent counterexamples, re-observed

Every observation below is a **bounded observation of the current candidate**,
not an additional product test.  A script exit of 0 means that the
observations were captured.

| Observation | Hook | Outcome |
|---|---|---|
| `after_canonical_read_symlink` | fired once | `QS_SOURCE_PLAN_REDIRECT_FORBIDDEN:QS_ARTIFACT_CUSTODY_REDIRECT_FORBIDDEN:qd-receipt.json` |
| `after_canonical_read_plain` | fired once | `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN:SYN-I00:QS_ARTIFACT_CUSTODY_REPLACED:qd-receipt.json` |
| `after_seal_read_missing` | fired once | `QS_RAW_ARTIFACT_UNREADABLE:SYN-I00:QS_ARTIFACT_CUSTODY_MISSING:qd-source-plan.json` |
| `after_raw_read_leaf_symlink` | fired once | `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN:SYN-I01:QS_ARTIFACT_CUSTODY_REDIRECT_FORBIDDEN:raw.txt` |
| `after_raw_read_parent_plain` | fired once | `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN:SYN-I01:QS_ARTIFACT_CUSTODY_REPLACED:SYN-I00` |
| `completion_canonical_leaf_redirect` | fired once | `QS_ARTIFACT_CUSTODY_REDIRECT_FORBIDDEN:qd-receipt.json` |

For all six: the hook fired exactly once, the **original bytes are
unchanged** and the **caller receipt is unchanged**.  The clean honest
baseline still aggregates with 16 submissions and 34 reserved provider calls,
10 usable images, 6 usable videos and zero critical hallucinations.

### The finite descriptor bound, measured

| Observation | Value |
|---|---|
| descriptors before the boundary | 8 |
| descriptors during the evaluation (canonical + seal + one raw leaf and their parents) | 17 |
| descriptors after **eight** further repeated reads of the same three names | 17 (unchanged) |
| custody entries of those three names | 5 (canonical, seal, `rows`, the row directory, the raw leaf) |
| internal custody bound | 72 |
| descriptors after `close()` | 8 (nothing leaked) |

The repeated read of the same names opens **no** second descriptor: the
custody is taken once per name.

### Cleanup

* the runner owned root was removed after every invocation (`owned_root_removed`
  is true in all four receipts);
* the probe registered its own root and its eight sub-roots and removed them
  in its `finally` block (`removed: true`);
* no older root was scanned or deleted;
* only new text files in this subtree are authored — no media, no binary, no
  database, no archive and no copy of the product source.

---

## 5 — what stays open

* The **parent owned original archive** or the **retained independent
  attestation** and the **selected root binding** are **NOT_PROVEN**.  A total
  coherent rewrite of **both** trusted originals stays outside the signing
  obligation of this batch.
* The **parent hard watchdog** stays **UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER**;
  synchronous callbacks are still not preempted.  This cooperative fix does
  not close it.
* The native Windows and WSL deployment, the residue admission and the A06
  enforcement and attempt observation are **NOT_PROVEN**.
* The actual registration baseline, the installation and the rollback are
  **NOT_PROVEN**.
* The authentic parent ledger debit is **NOT_PROVEN**.
* The real quality sixteen, the full twelve, the product Gate0 and the human
  and release acceptance are **NOT_PROVEN**.
* This is a cooperative, finite filesystem observation inside the existing
  audited Python and filesystem trust model.  It is **not** a claim of
  immunity against a hostile kernel, against a native Windows reparse point,
  against a filesystem that moves inodes underneath the process or against a
  universal concurrency guarantee.
* No signing platform and no native filesystem runtime were added.
* The frozen 8 MiB / 128 MiB / 256 MiB matrices were **not** repeated here;
  they remain proven by the earlier independent runs and this batch does not
  recertify them.  Every read of this batch stays at most `cap + 1`.
* The original correction-03 unguarded twelve remain UNKNOWN and uncredited.
* The 0 actual Windows / WSL / PowerShell / parser / host exe hashing, the 0
  real media, the 0 FFmpeg, the 0 models, the 0 GPU, the 0 services, the 0
  network, the 0 download, the 0 real ledger, the 0 claims and the 0 full
  checkpoint of this scope are unchanged.
* The task scoped `MAX_RETRIES=0` and `RETRY_WATCHDOG=0` remained 0; only the
  retry environment was read and no credential was dumped.

---

## 6 — Ten-field handoff

1. **current coordinate** — `{"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY"}` (from `plans/execution-control.json`).
2. **this batch** — S3-P3B aggregate correction 07 implemented: the bounded boundary-owned named custody of every earlier consumed artifact until the final QS completion; 245 product cases once (232 frozen plus 13 new), guard four once, focused thirteen once, eight bounded observations once; state `READY_FOR_REVIEW`.
3. **last passed gate** — `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate `621b1bf386db71bfe08ca2f033fa8ec396b0504b`, receipt `reports/unified-media/independent-live-15/receipt.json`, decision `10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY`.
4. **current blocking gate** — `S3_P3B_CORRECTION07_IMPLEMENTATION_AND_INDEPENDENT_REVIEW_PENDING`.
5. **route position** — root aggregate disposition → bounded correction → separate independent review → parent / native / A06 / Gate0 → finite real quality and human and release gates.
6. **remaining work** — the independent review of this candidate; the parent owned original archive or retained independent attestation and the selected root binding (NOT_PROVEN); the parent hard watchdog (`UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`); native Windows and WSL deployment, residue admission and A06 (NOT_PROVEN); the actual registration baseline, installation and rollback (NOT_PROVEN); the authentic parent ledger debit (NOT_PROVEN); the real quality sixteen, the full twelve, the product Gate0 and the human and release acceptance (NOT_PROVEN).
7. **next owner** — the root architecture and gate owner for the disposition; the independent review instance is next and it stays separated from this implementation.
8. **authorization** — the completed authorized offline implementation only; no new human approval is needed for this frozen offline scope and no real runtime authority is inferred.
9. **evidence directory** — `reports/v0-s3/product-gate0/implementation-p3b-correction-07/`.
10. **exact stop reason** — the one remaining root is implemented, the candidate `fd96cbc37574b382f483e757e8d7235ed5d2598c` is committed and the evidence is complete; the implementer reports `READY_FOR_REVIEW` only and keeps the terminal visible.

---

## 7 — Full V0–V3 outline from the current root control

Source: `plans/execution-control.json` of this worktree, read after the merge of
`d0cc0f9`.  Current Stage **R1**.  The counts and the implementation, machine
acceptance, independent review and human sign-off states are unchanged; this
batch is a correction inside V0-S3 and it does not change any of them.

|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|
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

Full declared substeps:

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

---

**Final state of this batch: `READY_FOR_REVIEW`.  No Stage pass, no product
Gate0 pass, no human acceptance.**
