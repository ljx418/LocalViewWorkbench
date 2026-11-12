# S3-P3B aggregate correction 08 — the ownership of every opened descriptor and the admission bound of the custody

**READY_FOR_REVIEW only.**  This is an implementation batch.  It is not a Stage
pass, it is not a product Gate0 pass and it does not close the parent, native,
A06, registration, ledger, real-quality or human-release gates.  The
independent review of this candidate is the next step and it has to be
performed by a separate instance.

| Item | Value |
|---|---|
| Root disposition commit | `94ade2aa32740830c17849b04dc2d3c365857c3e` (merged with `--no-edit`) |
| Root resumption approval | `4de8379eaf658d10f53fe3a1c954ff29773c95ae` (read with `git show`, not merged into this worktree) |
| Independent review of the previous batch | `9d2c51de4e8df6e5f882405cbff1332356dc8269` (Fatal0 / Major1 / Minor1, `CHANGES_REQUIRED`) |
| Baseline code / evidence | `fd96cbc37574b382f483e757e8d7235ed5d2598c` / `55e5463ae1bd1dd9f6c9c19bda347fe5900051ff` |
| Candidate code commit | `6c9a0a07c66060e53b00e690ebdd98047167511d` |
| Product source sha256 | `395f1a24bb9d9846b7dc23cae43d0c3f76699bdfd6b8de7f6941f3fccf2c1e1b` (`tools/v0_s3_quality_phase.py`) |
| Test source sha256 | `eb8327f936a3cc5281e1ba2064b6baba43779a15eee4539b93adcfc504999e2f` (`tools/test_v0_s3_quality_phase.py`) |
| Guarded runner (immutable, reused unchanged) | `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8` (`…/implementation-p3b-correction-05/run_guarded_checks.py`) |
| Bounded observation probe sha256 | `e664f586d1d6db6b049c7de05475b77dbf9fe5848985b8fd160a9aa5b7e235d9` |
| Obligation audit script sha256 | `2a338c20a902b34cd46fb3109be472391821fcc838fe1b2ff2b5bde6004096e7` |
| Frozen contract / projection | `reports/v0-s3/product-gate0/p3b-quality-contract.md`, `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json` — **unchanged** |
| Contract change | none.  No threshold, no denominator, no public schema and no quality rule changed. |
| Files changed | `tools/v0_s3_quality_phase.py`, `tools/test_v0_s3_quality_phase.py`, plus this new report subtree. |

The two remaining roots of the correction-07 independent review are addressed
in this batch, in the same owner and in the same batch:

* **NM03-R1** (Major) — a post-open metadata failure lost the descriptor
  ownership before the custody insertion.
* **NM03-r2** (Minor) — the custody cap refused only *after* the excess entry
  had been opened.

---

## 1 — NM03-R1: what was still wrong

`_ArtifactBoundary._open_child_directory()` and `_ArtifactBoundary._open_leaf()`
opened the descriptor of the entry and then read its metadata **before** any
owner knew about it:

```python
descriptor = os.open(name, flags, dir_fd=parent_fd)   # ownership: nobody
info = os.fstat(descriptor)                           # <-- OSError(EIO) here
identity = (info.st_dev, info.st_ino)
```

The descriptor was registered in `self._fds` or in the custody only much
later, so an ordinary `OSError(EIO)` at the first `os.fstat` of a just-opened
child directory or leaf left the descriptor owned by **nobody**: neither the
custody nor the boundary knew it, `boundary.close()` closed nothing, and the
descriptor stayed live outside the finite custody.  Repeated metadata failures
could therefore grow the descriptor use of an evaluation without bound, while
the score refusal stayed fail-closed.

The independent correction-07 review reproduced exactly that against the real
boundary: both hooks fired exactly once, the procfs count went from 8 to 9
after `boundary.close()`, and only an explicit probe remediation closed the
leaked descriptor.

The same owner family was audited **once** for the same gap:

| Opener | Ownership of a successful open | Verdict |
|---|---|---|
| `_open_trusted_parent` | the descriptor is appended to `self._fds` immediately after the open, before any metadata | no gap |
| `_open_directory` (the three pinned levels) | the descriptor is appended to `self._fds` immediately after the open, before any metadata; a failed construction closes the boundary | no gap |
| `_open_child_directory` | the descriptor was owned by nobody until the custody took it | **the gap** |
| `_open_leaf` | the descriptor was owned by nobody until the custody took it | **the gap** |

No unrelated refactor and no platform specific code was added.

## 2 — NM03-r2: what was still wrong

`_NamedCustody.take()` checked the internal bound **after** the descriptor of
the excess entry had already been opened:

```python
descriptor = os.open(...)                     # already opened
entry = self._custody.take(...)              # only here the bound is checked
```

So the exact 72 entries succeeded, but the 73rd name was opened first, the
transient descriptor use rose from 84 to 85, and only then did `take()` close
the excess descriptor and raise `QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED`.  The
normal finiteness held, but the *before-excess-open* bound did not.

---

## 3 — NM03-R1: what was changed

### Exactly one owner at every point

Every successful `os.open` now has exactly one owner from the very first
`os.open` until the descriptor is closed, and the owner is transferred
explicitly:

```
os.open succeeds
   -> the opener owns the descriptor
      -> the opener validates the metadata, the type and the identity
         -> the custody takes it over: it closes it on every refusal and
            transfers it only when the entry was really inserted
            -> the custody closes it exactly once in close()
```

* `_open_child_directory()` and `_open_leaf()` now own the descriptor from the
  first successful open.  Every failure below it — a metadata error, a missing
  name, a wrong type, a replaced identity — closes it **exactly once** and
  hands the failure on unchanged.  The failure is *not* swallowed and the
  refusal stays truthful: the original `OSError` of the metadata read is the
  error that the caller sees, and the original `SCORE_ARTIFACT_MISSING` /
  `SCORE_ARTIFACT_REDIRECT_FORBIDDEN` of the validation are unchanged.
* `_open_trusted_parent()` and `_open_directory()` transfer the descriptor
  into the boundary **before** they read any metadata, and a transfer that
  fails closes the descriptor again.  A failed construction therefore releases
  everything it had opened.
* `_NamedCustody.take()` owns the descriptor from the moment the caller hands
  it over: it closes it when the name is already in the custody (the pinned
  descriptor of the first acquisition stays the only descriptor of that name),
  it closes it when the custody refuses the name, and it closes it when the
  insertion into the registry fails.  A descriptor is therefore never closed
  twice and never left behind.
* One helper, `_close_owned_descriptor()`, is the only place that closes a
  descriptor, so there is no stale descriptor, no double close and no reused
  descriptor number anywhere in the boundary.

The descriptor of a name that is **already** in the custody is reused, never
duplicated: the pinned descriptor of the first acquisition stays the only
descriptor of that name, and the entry that was pinned first is preserved.

## 4 — NM03-r2: what was changed

### The capacity is reserved before the entry is opened

`_NamedCustody.reserve()` reserves one custody **slot** before the descriptor
of a new name is opened.  A reservation holds no descriptor and it is not an
entry; it is released again as soon as the open, the metadata validation or
the insertion fails.

* A name that does not fit into the internal bound is refused **before**
  anything is opened, so the 73rd name costs **zero** `os.open` calls and the
  transient descriptor use never rises above the bound.
* A refused admission gives its slot back: no slot is consumed, no entry that
  was taken earlier is disabled and the registry is undamaged.
* The bound is the **existing internal** bound `_CUSTODY_ENTRY_LIMIT = 4 *
  (FIXED_TOTAL + 2) = 72`.  It was not raised, it is not a public threshold,
  it is not a new Stage and a genuine evaluation of the sixteen rows still
  consumes 35 names — far inside the bound.

---

## 5 — the tests

`tools/test_v0_s3_quality_phase.py` adds **12** new definitions and **12**
new cases.  Every one of them drives the **real** `_ArtifactBoundary` of the
product or the **public** QS entry point `recompute_scores` after a genuine
public-owner run.  Every fault is injected into the owner itself — into the
product's own `os` module — and **nothing is repaired afterwards**, so a
leaked descriptor stays visible in the descriptor count and a "fake cleanup"
cannot pass.  No test asserts the existence of a list, and no probe name or
probe type is hardcoded.

| Test | What it proves |
|---|---|
| `…_a_child_directory_whose_metadata_fails_after_the_open_is_closed` | a child directory whose first `os.fstat` fails with `OSError(EIO)` → the hook fires once, the descriptor use is back to the use of the pinned levels, the custody has no entry and no reserved slot, `close()` releases everything |
| `…_a_leaf_whose_metadata_fails_after_the_open_is_closed` | the same for a leaf |
| `…_a_child_directory_whose_named_stat_fails_is_closed` | the no-follow, parent relative `stat` of the opened child directory fails → `SCORE_ARTIFACT_MISSING`, the descriptor is closed |
| `…_a_leaf_whose_named_identity_differs_is_closed` | the named entry names another, genuinely different regular file → `SCORE_ARTIFACT_REDIRECT_FORBIDDEN`, the descriptor is closed; the test proves the identity really differed |
| `…_a_leaf_whose_named_type_differs_is_closed` | the named entry is the parent directory → `SCORE_ARTIFACT_REDIRECT_FORBIDDEN`, the descriptor is closed |
| `…_an_insertion_failure_closes_the_descriptor_and_leaves_the_custody_intact` | the custody refuses the insertion of the entry → the descriptor is closed, no entry, no reserved slot, no descriptor in the registry |
| `…_a_public_evaluation_whose_metadata_fails_releases_every_descriptor` | the **public** `recompute_scores` fails with the same metadata fault → the refusal releases every descriptor it had pinned |
| `…_the_custody_bound_is_checked_before_the_excess_open` | exactly 72 leaves are admitted, the 73rd is refused with **zero** extra `os.open` calls, the descriptor use does not rise, the earlier custody is still verifiable and still usable, and a repeated name is opened again **not at all** |
| `…_a_repeated_name_at_the_custody_bound_opens_nothing` | a repeated name at the full bound reuses its pinned descriptor: no new open, no descriptor growth |
| `…_a_refused_admission_does_not_consume_a_custody_slot` | a refused admission gives its slot back and the next name is admitted normally |
| `…_a_boundary_that_fails_its_construction_releases_every_descriptor` | the audit of the constructor: a metadata failure during the construction releases every descriptor it had opened |
| `…_the_genuine_sixteen_rows_stay_inside_the_custody_bound` | the genuine evaluation of the sixteen rows stays strictly inside the internal bound and stays verifiable |

The **existing 245** obligations are unchanged: the six earlier-read and
completion mutations of the correction-07 review are still refused, the
current read/root/temp/phase/leaf checks are still in place, the raw and
source-plan bounded `cap + 1` and the descriptor relative, no-follow reads are
unchanged, the M01 recursive typed JSON and the closed key sets, the full M08
seal alignment, the NM04 order (the last original source check after the
getters, then the one clock and proof, then the immediate charge and the
cached submit) and the fixed sixteen rows / 34 provider calls / `>= 8` score /
8 of 10 images / 5 of 6 videos / zero critical hallucinations are unchanged.

---

## 6 — the guarded evidence

Every executable observation went through the **inspected, immutable**
correction-05 runner (`016e61a0…`), reused unchanged and pointed at the new
output paths of this subtree.  The audit guard is installed **before** pytest,
before any plugin and before any product or test import; the plugin autoload,
the cache provider and the bytecode writing are disabled; `connect`, `bind`,
the DNS resolution, `Popen`, `system`, `exec`, `spawn` and `fork` are
blocked.  This is named Python audit coverage, not direct syscall immunity.

### The final evidence of the committed candidate — four invocations, each once

| Invocation | Result | Inner / outer exit |
|---|---|---|
| Combined product suite (`--mode suite`) | **257 passed** (245 frozen + 12 new), 88.78 s | 0 / 0 |
| Guard selftest (`--mode guard`) | **4** audit events blocked | 0 / 0 |
| Focused new resource counterexamples (`--mode focused -k correction08_nm03`) | **12 passed**, 245 deselected | 0 / 0 |
| Independent bounded resource observations (`--mode script`) | **5** observations, 0 violated invariants | 0 / 0 |

Every receipt records the exact argv and the true exit code, the raw stdout
and stderr files with their hashes and byte lengths, the source hashes
**before and after** the run, the runner and probe hashes before and after,
the actual imported module paths with their hashes, the guard configuration
and the removal of the owned temporary root.

### The debug phase before the final evidence

The `debug/` directory keeps the guarded runs of the **debug** phase.  They
were produced **before** the candidate was committed and they are **diagnostic
runs, not the final evidence**: their raw streams and receipts are kept as they
are, they are not relabelled and they do not certify the candidate.  The final
evidence is the four invocations of the table above, produced **once** each on
the committed candidate `6c9a0a0`.

| Diagnostic run | Role | Result |
|---|---|---|
| `debug-focused` | the new cases, first run | 12 passed, 245 deselected |
| `debug-focused-2` | the new cases after the assertions were reordered | 12 passed, 245 deselected |
| `debug-counterexamples` | the bounded observation probe, first run | 5 observations, **1 violated invariant** — the probe lacked the projection binding of the public observation; the probe was corrected |
| `debug-counterexamples-2` | the bounded observation probe after the correction | 5 observations, 0 violated invariants |
| `debug-suite` | the combined suite **before** the commit | 257 passed, 90.67 s |
| `debug-negative-control` | the new cases against the **unfixed baseline** product code `fd96cbc` | **10 failed, 2 passed** |

The failed diagnostic runs are retained exactly as they are; they are not
deleted, not relabelled and not rerun.

### The negative control — the new cases against the unfixed baseline

The twelve new cases were executed once against the baseline product code
`fd96cbc` (`e670b330…` during that run).  **Ten of the twelve failed** there
and all twelve pass against the candidate:

| New case | Baseline result |
|---|---|
| child directory whose metadata fails after the open | `the refused child directory leaked a descriptor` (21 against 20) |
| leaf whose metadata fails after the open | `the refused leaf leaked a descriptor` (22 against 21) |
| child directory whose named stat fails | the new `reserved()` registry API does not exist on the baseline |
| leaf whose named identity differs | the new `reserved()` registry API does not exist on the baseline |
| leaf whose named type differs | the new `reserved()` registry API does not exist on the baseline |
| the custody refuses the insertion | `the failed insertion leaked a descriptor` |
| the public evaluation fails | `the refusing evaluation leaked a descriptor` |
| the custody bound is checked before the excess open | `the excess entry was opened` |
| a repeated name at the bound opens nothing | passed on the baseline as well: the reuse of a pinned descriptor was already correct |
| a refused admission consumes no slot | `the refused admission leaked a descriptor` |
| the construction of the boundary fails | passed on the baseline as well: the level openers already transferred the ownership |
| the genuine sixteen rows stay inside the bound | the new `reserved()` registry API does not exist on the baseline |

The negative control is a **debug diagnostic**, not a final evidence run.

### The static obligation audit

The static obligation audit (`audit_test_obligations.py`, a git read outside
the guard by design) compares the frozen baseline `fd96cbc` with the
candidate `6c9a0a0`:

* 193 baseline test definitions → **205** candidate test definitions,
* **193 identical, 0 adapted, 0 deleted**, 0 changed old helpers,
  6 added helper definitions,
* **245** frozen collected node ids → **257** candidate node ids,
  **0** frozen node id lost, 12 added,
* the baseline and the candidate product source hashes are bound.

### The bounded resource observations, measured

| Observation | Descriptors before | during | after the refusal | after `close()` |
|---|---:|---:|---:|---:|
| child directory whose metadata fails after the open | 8 | 12 | **12** | 8 |
| leaf whose metadata fails after the open | 8 | 12 | **12** | 8 |
| the public evaluation fails | 8 | — | — | **8** |
| a refused admission | — | 12 | **12** | — |

The hook fired exactly once in every observation, the custody was undamaged
(0 entries, 0 reserved slots) and nothing was repaired by the probe.

### The admission bound, measured

| Measurement | Value |
|---|---|
| internal custody bound | 72 |
| entries at the bound | **72** (exact) |
| real `os.open` calls for the exact bound | **72** |
| real `os.open` calls for the 73rd name | **0** |
| descriptors at the bound | 84 (8 baseline + 4 pinned levels + 72 custody entries) |
| descriptors after the refused 73rd name | **84** (no rise) |
| descriptors after a repeated name at the bound | **84** (no rise) |
| real `os.open` calls after the repeated name | **72** (no new open) |
| the earlier custody after the refusal | still verifiable |
| descriptors after `close()` | **8** (nothing leaked) |

The refusal stays truthful: `QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:bound-excess.bin`.

### Cleanup

* the runner owned root was removed after every invocation (`owned_root_removed`
  is true in all four final receipts);
* the probe registered its own root and its five sub-roots and removed them
  in its `finally` block (`removed: true`);
* no older root was scanned or deleted;
* only new text files in this subtree are authored — no media, no binary, no
  database, no archive and no copy of the product source.

---

## 7 — what stays open

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
* The original correction-03 unguarded twelve, the old eight and twenty broad
  histories, the split 245, the cap matrix, the P3A 121, the P2B 237 and the
  full project were **not** rerun.  No historical run was repeated, no
  historical raw stream was regenerated or relabelled and no cosmetic rerun
  was made.

---

## 8 — Ten-field handoff

1. **current coordinate** — `{"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY"}` (from `plans/execution-control.json`).
2. **this batch** — S3-P3B aggregate correction 08 implemented: the immediate exception-safe ownership of every opened descriptor until the custody transfer completes (NM03-R1) and the internal custody bound checked before the excess open (NM03-r2); 257 product cases once (245 frozen plus 12 new), guard four once, focused twelve once, five bounded observations once; state `READY_FOR_REVIEW`.
3. **last passed gate** — `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, receipt `reports/unified-media/independent-live-15/receipt.json`, decision `10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY`.
4. **current blocking gate** — `S3_P3B_CORRECTION08_IMPLEMENTATION_AND_INDEPENDENT_REVIEW_PENDING`.
5. **route position** — root aggregate disposition → bounded correction → separate independent review → parent / native / A06 / Gate0 → finite real quality and human and release gates.
6. **remaining work** — the independent review of this candidate; the parent owned original archive or retained independent attestation and the selected root binding (NOT_PROVEN); the parent hard watchdog (`UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`); native Windows and WSL deployment, residue admission and A06 (NOT_PROVEN); the actual registration baseline, installation and rollback (NOT_PROVEN); the authentic parent ledger debit (NOT_PROVEN); the real quality sixteen, the full twelve, the product Gate0 and the human and release acceptance (NOT_PROVEN).
7. **next owner** — the root architecture and gate owner for the disposition; the independent review instance is next and it stays separated from this implementation.
8. **authorization** — the completed authorized offline implementation only; no new human approval is needed for this frozen offline scope and no real runtime authority is inferred.
9. **evidence directory** — `reports/v0-s3/product-gate0/implementation-p3b-correction-08/`.
10. **exact stop reason** — the two remaining roots are implemented, the candidate `6c9a0a07c66060e53b00e690ebdd98047167511d` is committed and the evidence is complete; the implementer reports `READY_FOR_REVIEW` only and keeps the terminal visible.

---

## 9 — Full V0–V3 outline from the current root control

Source: `plans/execution-control.json` of this worktree, read after the merge of
`94ade2a`.  Current Stage **R1**.  The counts and the implementation, machine
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
