# S3-PREP-A correction-01 — 独立审查报告 / Independent review of the S3P-A-MAJOR-01 closure

**review_id**: S3-PREP-A-INDEPENDENT-CORRECTION-01
**root task**: `task_d75b429e0599`
**scope**: 仅关闭 `S3P-A-MAJOR-01`；不做新的产品验收，不做全项目重审。
**verdict**: `S3P_A_MAJOR_01_CLOSED_AND_INDEPENDENTLY_REVERIFIED`
**Fatal / Major / Minor (本任务范围内)**: `0 / 0 / 0`

> 本报告**不签 Stage PASS**，**不授予 product Gate0**，**不构成任何人工签署**，**不声称发布**，
> **不授权模型执行**。原 S2 人工签署仍为 PENDING。

---

## 1. 候选身份 / Candidate identity

| 项 | 值 |
|---|---|
| 代码候选 | `bc78869231e4dc320dfc9c7198a07aeabf9412fe` |
| 含完整纠偏原始证据的候选 tip | `491b40df908b7b9c74f110efa8a61aebe61f76ea` |
| source-loading 合并提交 | `137ce11549b4fe1b9006e5eaffaf21dbcb064c09` |
| root 权威 | `12a1594c12b57a62ce445e4cf7f11fd38423039d`（已在候选历史中） |
| 审查分支 / HEAD | `ljx418/lvw-v1-d0-review` @ `ba781a8cd8258c53ec783a527a9f7424896fcd5e` |
| 合并方式 | `git merge --no-edit 491b40df908b7b9c74f110efa8a61aebe61f76ea`，**冲突 0，退出码 0** |
| 保留的 reviewer-owned 追加材料 | `c27c157`（独立 hash 复核流程纠偏及其 append-only 记账） |
| Git 作者 | `ljx418 <1173696783@qq.com>` |

工具文件哈希（审查 worktree 实测）与候选记录 `candidate-correction-01.json` **逐项一致**：

| 文件 | sha256 | 候选记录 |
|---|---|---|
| `tools/verify_s3_handoff.py` | `d2b3fd33…c2b5fa` | modified，一致 |
| `tools/test_verify_s3_handoff.py` | `9a46fd77…de6328` | modified，一致 |
| `tools/s3_asset_inventory.py` | `333cfed9…cbb30` | unchanged，一致 |
| `tools/test_s3_asset_inventory.py` | `2af8bf3e…957e0` | unchanged，一致 |

**owner 范围核对**：`bc78869` 的 `git show --name-only` 只列出
`tools/verify_s3_handoff.py` 与 `tools/test_verify_s3_handoff.py`；`491b40d` 为纯 append-only
证据（`correction-01/`、`logs/`、`checks/`）。合同、计划、旧收据未被改动。

---

## 2. Major 是否闭合 / Was S3P-A-MAJOR-01 closed

**是，闭合。** 依据 `reports/v0-s3/preparation-03/codex-review-resolution-01.json` 要求的修复项，
逐条独立复验：

1. **实际权威被读取**：`tools/verify_s3_handoff.py` 现在 `load_json(root, "plans/execution-control.json")`
   并**解释** `development_outline`，不 hash-freeze、不以复制快照或校验和代替。
   `plans/execution-control.json` **不在** 16 个 source fence 文件之列（已在 packet
   `spec-manifest.json` 中逐项核对），因此拒绝不可能来自文件哈希。
2. **语义拒绝**：同一份 8/8 + APPROVED + 人工子项 DONE 的攻击被拒绝，退出码 1，
   失败项**全部**在 `actual.*` 前缀下，`fence./predicate./approval./request./decision./evidence./map./packet./plans.`
   **零失败**。
3. **对照实验（关键）**：把**纠偏前**的 guard（`137ce11` 版本，sha256 `5944771f…dfe9d`，
   与原盘点 preflight 记录的 `handoff_script_sha256` **完全相同**）放到同样的攻击上运行 →
   **退出码 0、HANDOFF_READINESS_VERIFIED、119 checks、0 failed（绿色）**。
   这既复现了原 Major 的现象，也证明新候选的拒绝来自 `actual.*` 语义读取，而非陈旧文件哈希。
4. **报告不谎报 7/8**：公开报告把 `historical_s2_projection`（**观测值**）与
   `historical_s2_declared_expected_state`（**声明期望**）分列；观测值与期望矛盾时，
   notes 明确写 “does NOT match the declared expectation … (no 7/8 is asserted here)”。
   17 个探针全部满足「矛盾时不声称 7/8」。
5. **历史快照按快照强制**：`historical_s2_coordinate` 被当作**保留快照**逐字段强制
   （`V0-S2 / WP-S2-06 / GATE5_HUMAN_EXPERIENCE_SIGNOFF / WAIT_HUMAN`，且键集合必须精确等于这 4 项）。
6. **当前坐标可推进**：live `coordinate` / `current_blocking_gate` / `updated_at` 未被冻结，
   `execution_coordinates_frozen` 仍为 `false`；推进后仍 VERIFIED。

**计数**：本任务范围内 Fatal `0`、Major `0`、Minor `0`。
先前独立审查的 `0 Fatal / 1 Major / 7 Minor` 中，Major 已被本候选闭合并复验；
7 项 Minor 按 root 决议**披露但不重开、不扩大重构**（见第 6 节）。

---

## 3. 实际权威状态：observed actual vs expected

直接读审查 worktree 的 `plans/execution-control.json`（`development_outline` 中 `stage_id == "V0-S2"`）：

| 字段 | **observed actual（实测）** | expected（合同声明） | 一致 |
|---|---|---|---|
| `completed_substeps` | `7`（int，非 bool） | `7` | ✅ |
| `total_substeps` | `8`（int，非 bool） | `8` | ✅ |
| `human_signoff` | `PENDING` | `PENDING` | ✅ |
| 子项数 | `8` | `8` | ✅ |
| DONE / PENDING | `7` / `1` | `7` / `1` | ✅ |
| 人工子项 | `S2 人工签署与Git同步`，`PENDING`，`evidence: null` | 同 | ✅ |
| `historical_s2_coordinate` | `V0-S2 / WP-S2-06 / GATE5_HUMAN_EXPERIENCE_SIGNOFF / WAIT_HUMAN`（四字段） | 同 | ✅ |

检查器自身公开报告中的 `historical_s2_projection` 观测值同样是 `7 / 8 / PENDING`，
与 declared expected state **逐字段相等**（`observed_equals_declared: true`）。
**本次未出现「假 8/8」被报告为「7/8」的情况**：所有矛盾场景的公开报告都给出观测原值。

---

## 4. 一次有界离线复验 / The bounded offline re-verification

只做了一次集中复验。环境：`python3 3.12.3`、Linux 5.18.40.1-microsoft-standard-WSL2、
`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`、自有 `TemporaryDirectory` 作为 basetemp 父目录。
无网络、无 GPU、无服务、无模型、无 checkpoint、无真实素材 stat/hash/probe/decode/浏览。

### 4.1 检查器

```sh
python3 -B tools/verify_s3_handoff.py
```

* 退出码 **0**，decision `HANDOFF_READINESS_VERIFIED`
* **139 checks / 139 passed / 0 failed**（预期 139 ✅）
* `authority: AUTHORITATIVE`，其中 `actual.` 前缀检查 **20** 项
* stdout sha256 `c4b67870…1a600`，stderr sha256 `e3b0c442…2b855`（空）
* 日志：`logs/guard_real_root.{stdout,stderr,exit}.log`

### 4.2 两个指定测试文件

```sh
python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py \
  -q -p no:cacheprovider --basetemp=/tmp/lvw-s3pa-indep-correction-01-pytest-0k82xjsy/pytest-basetemp
```

* 退出码 **0**，`65 passed in 0.47s`（预期 65 ✅）
* stdout sha256 `f3034ac7…32cfe`，stderr 空
* 自有 basetemp 父目录 `/tmp/lvw-s3pa-indep-correction-01-pytest-0k82xjsy`：
  **context 退出后 `exists == false`（实测已清理）**；未清理任何共享 pytest 根
* 日志：`logs/pytest_two_packet_files.{stdout,stderr,exit}.log`

> **如实披露**：该测试文件内部有 2 处 subprocess 调用 inventory CLI（`--help` 与一个
> 故意损坏的 binding），二者都跑在合成 fixture 上、**读取 0 字节媒体**，且不构成一次真实盘点。
> **审查者自身发起的 inventory CLI 调用次数 = 0**。

### 4.3 语义负例 / 正例（隔离合成副本）

每个用例都在自有 `TemporaryDirectory` 内复制**当前真实** `plans/execution-control.json`
结构 + 逐字节一致的冻结权威文件，只改 `actual.*` 语义，再用公开 CLI `--root` 运行。

**15 个负例，全部退出码 1 / `HANDOFF_READINESS_REJECTED`，且失败项全部落在 `actual.*`，
checksum/proof 类失败 0 项：**

| 用例 | 期望失败项 | 实际失败项数 | 关键失败项 |
|---|---|---|---|
| actual_full_8of8_approved_human_done | `actual.outline.completed_substeps` | 7 | completed/substeps/human_signoff/human step 全部命中 |
| actual_completed_8 | `actual.outline.completed_substeps` | 1 | — |
| actual_human_signoff_approved | `actual.outline.human_signoff` | 1 | — |
| actual_human_step_done | `actual.outline.human_substep_pending` | 4 | done_count/pending_count 同步命中 |
| actual_human_step_renamed | `actual.outline.human_substep_present` | 3 | — |
| actual_human_step_missing | `actual.outline.human_substep_present` | 3 | — |
| actual_human_step_duplicated | `actual.outline.human_substep_present` | 5 | substep_count/pending_count 同步命中 |
| actual_v0_s2_entry_missing | `actual.outline.v0_s2_occurrence` | 12 | 观测值全为 `null`（fail closed） |
| actual_v0_s2_entry_duplicated | `actual.outline.v0_s2_occurrence` | 12 | 观测值全为 `null`（fail closed） |
| actual_bad_value_types (`"7"` / `True` / `None`) | `actual.outline.completed_substeps` | 3 | total_substeps/human_signoff 同步命中 |
| actual_substeps_not_a_list | `actual.outline.substeps_container` | 8 | — |
| actual_done_substep_without_evidence | `actual.outline.done_substep_evidence` | 1 | — |
| historical_snapshot_rewritten | `actual.historical_s2_coordinate.state` | 1 | — |
| historical_snapshot_extra_key | `actual.historical_s2_coordinate.exact_keys` | 1 | — |
| historical_snapshot_field_dropped | `actual.historical_s2_coordinate.gate` | 2 | exact_keys 同步命中 |

**2 个正例，全部退出码 0 / `HANDOFF_READINESS_VERIFIED` / 0 failed：**
`synthetic_unmodified`（逐字节副本）与 `synthetic_current_coordinate_advances`
（`coordinate`/`current_blocking_gate`/`updated_at` 推进）。

### 4.4 拒绝归因的字节级证明

`probe-tree-integrity.json`（**未重跑检查器**，纯文件级测量）：17/17 用例中
**28/28 个冻结权威文件与真实仓库逐字节相同**，且 `plans/execution-control.json` 的差异
**被限制在预期路径**内（`development_outline[4].*` / `historical_s2_coordinate.*` /
`coordinate.*` / `current_blocking_gate` / `updated_at`）。

> 字段说明：`recheck-raw.json` 中的 `frozen_authority_bytes_identical_to_source` 比较的是
> **全部 29 个**权威文件，**包含**被有意改写的 `plans/execution-control.json`，
> 因此它在每个改写用例里**按构造必然为 `false`**；上面的 `probe-tree-integrity.json`
> 才是该结论的直接测量。

### 4.5 对照实验（纠偏前 guard）

```sh
python3 -B <tmp>/package/tools/verify_s3_handoff.py --root <tmp>/attack
```

`137ce11` 版本的 guard（sha256 `5944771f…dfe9d`）对**同一份** 8/8+APPROVED+DONE 攻击：
**退出码 0 / HANDOFF_READINESS_VERIFIED / 119 checks / 0 failed（绿色）**。
对照第 4.3 节同一攻击在候选上退出码 1，**归因闭合**。

---

## 5. 库存算法 / 测试 / 原 512 项收据（只读核对）

从 `311bdda937373f1055a6677f02322fb347c31cd1` 到 `491b40df908b7b9c74f110efa8a61aebe61f76ea`
**字节不变**（`git show` 逐项比对 + worktree 实测）：

| 文件 | 311bdda | 491b40d | 字节不变 |
|---|---|---|---|
| `tools/s3_asset_inventory.py` | `333cfed9…cbb30` | `333cfed9…cbb30` | ✅ |
| `tools/test_s3_asset_inventory.py` | `2af8bf3e…957e0` | `2af8bf3e…957e0` | ✅ |
| `implementation/inventory-01/receipt.json` | `05ab5d63…2ef` | `05ab5d63…2ef` | ✅ |

**旧盘点只绑定原候选**：收据的 `code_binding.candidate_sha` = `d33893303f24da57216b63b4e0b9ef7e009d7613`。
它**不是**纠偏候选 `bc78869` 的真实盘点，本报告不冒充、不改标、不声称。
其 `guard.handoff_script_sha256` = `5944771f…dfe9d`，与第 4.5 节我实际运行的纠偏前 guard
**同一哈希**，构成独立交叉印证。

**旧 preflight 绑定已陈旧且未被重新封存**：纠偏后 guard 为 `d2b3fd33…c2b5fa`，
旧盘点的 preflight 不会再匹配；**未运行 inventory CLI 去强行通过**。
审查者：`inventory CLI 调用 = 0`、`真实盘点 = 0`、**旧 hash child 未续期**。

---

## 6. 原 7 项 Minor（按 root 决议披露，不重开）

| ID | root 处置 | 本次披露 |
|---|---|---|
| S3P-A-MINOR-01 | ACCEPT_NONBLOCKING_WITH_EXPLICIT_DERIVED_PARTIAL_COVERAGE | `INVENTORY_COMPLETE` 只描述有界操作完成，**不是全量覆盖**：698 个支持扩展文件中哈希 512 个，186 个未哈希；派生目录 509 项 / 498 个不同内容；3 条私密标注路径被排除 |
| S3P-A-MINOR-02 | APPEND_CORRECTION_REQUIRED | 零清理计数是**代码契约声明而非实测**；此前「pytest 删除 TemporaryDirectory」的表述不准确；候选 errata 已 append-only 更正 |
| S3P-A-MINOR-03 | ACCEPT_NONBLOCKING_LABEL_LIMIT | `AUTHORITATIVE` 只代表本地被 pin 文件核对通过，**不是 Git 来源证明**；候选/SHA 绑定由 preflight、pre-receipt、独立审查在外部证明 |
| S3P-A-MINOR-04 | ACCEPT_NONBLOCKING_EXTERNAL_BINDING_PROOF | 真实 `d338933` 存在且脚本字节与 `77592cc` preflight 一致；仅格式字段本身不构成来源证明 |
| S3P-A-MINOR-05 | RETAIN_DISCLOSED_METADATA_DEVIATION_NO_RETRO_GRANT | `ls -la` 元数据根列举发生在有界尝试之外；**保留披露、不追溯追认、未重复**；不折算为 Gate0 PASS |
| S3P-A-MINOR-06 | ACCEPT_NONBLOCKING_FAILURE_IS_TERMINAL | 失败尝试保有自己的终态收据；未来尝试须**新的有限 child + 新路径**，不覆盖、不退款、不就同一范围重求人工授权 |
| S3P-A-MINOR-07 | EXCLUDE_FROM_FUTURE_CONTENT_ACCESS | 派生目录排除 3 条私密标注路径；原始盘点保持历史；**哈希确实打开并读取了这 3 个文件的源字节**，但**没有解码、没有视觉查看、没有原始媒体拷贝、没有 provider 调用**；此前「内容从未被打开」的措辞不准确，已 append-only 更正 |

**本次不因非阻断项扩大任何重构。**

---

## 7. 独立 hash 复核流程偏差（保留，不抹除）

`reports/v0-s3/preparation-03/independent-hash-process-deviation-01.json` 原样保留：

* 源读取 **3 遍**、文件读操作 **9 次**、唯一源文件 3 个
* `preflight_validated_before_source_access`：attempt1 **false**、attempt2 **false**、final **true**
* `one_pass_limit_met: false`、`preflight_before_each_source_access_met: false`
* 汇总字节上限达成，范围根与文件集**未扩大**

**明确声明**：最终那次正向复核**不能抹除**前两次 preflight 失败的源读取；
**本报告不声称存在一次完全合规的独立 hash 复核**，也不声称旧 hash child 完全合规。
helper 纠偏由 root 另审，本任务未实施、未真实验证它。

---

## 8. 已知限制 / Known limitations

1. 第 4.2 节所述：inventory 测试文件内部有 2 次合成 fixture 上的 CLI 子进程调用（0 字节媒体），
   已如实披露；审查者自身真实盘点 = 0。
2. 512 项收据仍绑定原候选 `d338933`，**不是** `bc78869` 的真实盘点。
3. **纠偏后的 guard 在旧 S2 被真实人签后会失败**（8/8 DONE）。这是 root 指定的 owner 规则
   （AGENTS.md 规则 24 / ADR-14：旧 S2 保持 7/8 未签）的正确行为，但**人签落地的那一刻必须重新
   裁决本门禁**，否则 S3 质量集会卡死。
4. 候选比 root 字面要求**更严**两项：每个 DONE 子项必须带非空 evidence 路径；子项状态只接受
   DONE/PENDING。两者只会让门禁更严，负例中实测均 fail closed。
5. 独立 hash 复核的 3 遍 / preflight 偏差**仍然开放**。
6. reviewer-owned helper 纠偏归 root。
7. 本报告仅覆盖 `S3P-A-MAJOR-01`，**不是新的产品验收，不是全项目重审**。

---

## 9. 下一动作 / Next actions

1. root 可依本复验在合并处置中**关闭 S3P-A-MAJOR-01**。
2. reviewer-owned helper 纠偏由 root 负责：须以合成 fixture 证明「preflight 失败 ⇒ 源读取为 0」，
   并保留 3 遍 / 9 读的真实验收账。
3. **不再授权、也不再需要**新盘点；若将来需要，必须是**新有限 child + 新路径 + 新 preflight**，
   绝不续期旧 hash child。
4. 旧 S2 人工签署落地时，必须**重新裁决本 handoff 门禁**再推进 S3 质量集。
5. `S3P-A-MINOR-01..07` 维持非阻断；不为其改代码、不改盘点标签或格式。

---

## 10. 产物清单 / Artifacts

```
reports/v0-s3/preparation-03/independent-correction-01/
├── independent-correction-01.json      # 机器可读收据（本报告的结构化版本）
├── recheck-raw.json                    # 一次集中复验的原始输出
├── probe-tree-integrity.json           # 探针树字节级完整性证明
├── review.md                           # 本可读报告
├── run_independent_recheck.py          # 复验执行器（可复现）
├── check_probe_tree_integrity.py       # 完整性测量器（未重跑检查器）
├── build_independent_correction_receipt.py  # 收据组装器（值全部取自原始件）
└── logs/                               # 每条命令的 stdout / stderr / exit
```

所有新增 JSON 均已校验为合法 JSON；原始失败记录（`independent-hash-process-deviation-01.json`、
原 `codex-review-resolution-01.json`、候选 `correction-01/` 全部收据与日志）**未被修改**。
