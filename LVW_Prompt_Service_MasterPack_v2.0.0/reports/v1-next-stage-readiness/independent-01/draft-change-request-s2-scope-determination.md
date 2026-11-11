# DRAFT 变更请求提案：原 S2 范围判定（V0-S2 人类义务绑定）

**状态：DRAFT / 未生效 / 无权限。** 本文件是独立审查员的提案，不是权威、不修改任何合同或计划、不构成批准、不激活任何 Stage、不授予任何产品运行权限。只有 Codex（门禁裁决人）与 project_owner（人类签署人）按 AGENTS 第 10/11 条作出裁决并记录后，才可能生效。

- 提出人：ClaudeCode 独立规划审查员（只读）
- 日期：2026-11-11
- 现状坐标：`plans/execution-control.json` → `state = SLICE_ACCEPTED_NEXT_STAGE_PREPARATION`，`current_blocking_gate = NEXT_STAGE_DEPENDENCY_AND_GATE0_READINESS`
- 依据缺失：`docs/30_V1_REVISED_EXECUTION_PLAN.md` 的 S2/S3 准入列明"现有统一切片实际体验签署，**原S2范围判定**"；其中"统一切片实际体验签署"已由 `reports/unified-media/human-signoff-live15.json` 完成，**"原S2范围判定"在任何源文件中均不存在**。

---

## 1. 问题陈述（非结论）

V0-S2（V0.1）的 Stage 状态为 7/8，缺失的第 8 子步是"S2 人工签署与Git同步"。该子步的人类体验对象，按 `reports/v0-s2/full-v0-auto-08/human-signoff-request.md`，是候选 `719c74559393a6489b2f630a1e0d3bc3303eb655` 上的 **ComfyUI 原生**最简短视频、显式采纳、取消与离线人工工作流。

2026-11-11，用户在统一前端上确认"当前前端页面、基本的视频反推 我人工确认OK"，该签署绑定候选 `621b1bf386db71bfe08ca2f533fa8ec396b0504b`，范围仅限当前统一切片，并**显式排除**旧 S2/V0.1。

因此出现一个尚未被任何文件回答的问题：**在统一前端已成为人类验收载体的前提下（docs/27 批准），V0-S2 的人类体验/范围义务应当绑定到哪个交付物上？** 这是范围判定问题，不是"再签一次"的问题，也不是"跳过"的问题。

---

## 2. 已批准的约束（判定时必须同时满足）

| # | 约束 | 出处 |
|---|---|---|
| C1 | 不伪造 S2 人工签署；保留 S2 7/8 及旧机器/独审事实 | `docs/27`（APPROVED 2026-11-08） |
| C2 | 旧 S2 仍 7/8 未人工签署；Comfy 界面不再是本次人类必须使用的验收入口 | `docs/23` 2026-11-08 追记 |
| C3 | 保留 V0-S2/S3 原义务**及其前置门槛**；不取消 S3；不用新多镜头结果冒充旧质量分母 | `docs/30` §范围与顺序 |
| C4 | V0.1 视频、V0.2 安装回滚与完整质量**没有取消**，只在执行顺序上后移 | `docs/23` §门禁边界 |
| C5 | 本次签署仅限当前统一切片；不得扩大到旧S2/V0.2/完整R1/V1/发布 | `AGENTS.md` 第 23 条 |
| C6 | 旧切片人签**未**被豁免 | `plans/v1-revised-plan.json.old_slice_human_signoff_waived = false` |
| C7 | 人类体验/发布签署仍由人类实际完成 | `AGENTS.md` 第 20 条 |
| C8 | 独立审查实例不实现候选、不签 Stage PASS | `AGENTS.md` 第 11 条 |

---

## 3. 三个选项（供裁决人选择；本审查员建议 A）

### Option A —— 视频能力子集上把人类体验义务重新绑定到已签署的统一前端（**建议**）

**判定内容**：V0-S2 的人类体验/范围义务，就**已被统一切片实际演示的视频能力子集**而言，绑定到已签署候选 `621b1bf…`（`reports/unified-media/human-signoff-live15.json`）；就**仅存在于 Comfy 原生交互面的部分**而言，明确记为"未获人类确认，因此不作任何主张"。

**必须同时写明（防止变绿灯）**：

1. S2 的机器 9/9 与独审 Fatal0/Major0 **仍绑定 `719c745`**，不因本次判定改变其候选绑定。
2. V0-S2 的**机器事实、历史失败、原始收据一律不改写**；本次只新增一条判定记录。
3. V0.2 累计门禁**仍是 V0-A01..A12 十二项全部通过**，且**必须在 S3 候选上重新跑**，不得用旧候选结果拼接。
4. **V0-A11（10 图 ≥8 可用、幻觉 0）与 V0-A12（6 片 ≥5 可用、幻觉 0）必须在 S3 候选上以独立预标注新跑**；本次人签输入为合成结构夹具（`tracking.mov` sha `b08ea8b0…`），**不构成任何内容质量证据**。
5. **V0-A06（断网增量迁移 / 安装 / 回滚）完全未被本次人签触及**，必须新做。
6. Comfy 原生节点图交互（导入工作流、节点参数、节点内显式采纳与取消）**记为未获人类确认**，V0-S2 不得据此宣称"Comfy 原生体验已验收"。
7. **不产生 V0.1 通过、不产生 V0.2 通过、不产生 V0 发布、不产生完整 V1 通过**；`allowed_claim` 仍为 `V0_MIN_ACCEPTED_NOT_RELEASED`。
8. 11 段人工留样仍 NOT_RUN、仍受保护。
9. `plans/tasks.json` 的 `depends_on` **完全不变**（`V0-S3.depends_on=["V0-S2"]` 等）；本判定只影响"V0-S2 是否算完成"，不放松任何依赖边。

**成本/风险**：V0-S2 的人类门关闭合，但 V0-S3 的十二项与独立质量集仍然全量欠账；对用户而言无需再学 Comfy。

### Option B —— 用户实际体验 Comfy 原生流程并签署 `719c745`（原样）

按 `reports/v0-s2/full-v0-auto-08/human-signoff-request.md` 原文执行并签署候选 `719c745`。

- 优点：不触及任何范围判定，证据链最"原味"。
- 代价：与 `docs/27` 批准动机（"不要求用户为了过门先学习Comfy"）相悖；需用户额外投入；无任何新增产品代码。

### Option C —— 直接视旧 S2 已签（**不建议，且本审查员不会据此推进**）

- 违反 C5、C6；与 `human-signoff-live15.json.explicitly_not_approved` 首项直接冲突；违反 `AGENTS.md` 第 13 条（不得降低门槛）。
- 记录在案仅为完整性，不作为可选项。

---

## 4. 最小受影响 ID / 文件 / 依赖（Option A 生效时）

### 4.1 新增（不改写任何旧文件内容）

| 路径 | 内容 |
|---|---|
| `reports/v0-s2/scope-determination-01.md` | 判定正文（人读）：范围、被绑定的候选、被排除的内容、未获人确认的部分、保留的义务 |
| `reports/v0-s2/scope-determination-01.json` | 同上机器可读：判定 ID、裁决人、签署人、签署原文、绑定的候选 SHA、被排除项、保留义务清单、关联签署记录 SHA |

### 4.2 仅"追加/更新状态字段"的既有文件（不改门槛、不改依赖、不改用例）

| 路径 | 字段 | 变更 |
|---|---|---|
| `plans/execution-control.json` | `development_outline[V0-S2].substeps[7]`（"S2 人工签署与Git同步"） | `status` → `DONE`，`evidence` → `reports/v0-s2/scope-determination-01.json` |
| `plans/execution-control.json` | `development_outline[V0-S2].human_signoff` | `PENDING` → 记录新判定引用（**不得写成 `APPROVED` 之外的任何版本号**） |
| `plans/execution-control.json` | 新增 `historical_s2_scope_determination` | 指向判定记录与被绑定候选 SHA |
| `plans/execution-control.json` | `historical_s2_last_passed_gate` | **保持不变**（仍为 `GATE5_INDEPENDENT_MACHINE_REVIEW` / `719c745`） |
| `plans/execution-control.json` | `allowed_claim` / `forbidden_claims` | **完全不变** |

### 4.3 明确**不得**修改的（防止静默放宽）

- `plans/tasks.json`（含全部 `depends_on`）
- `plans/acceptance_cases.json`（V0-A01..A12、V1 21+MS01–08 共 66 组的用例与断言）
- `plans/release_gates.json`（V0-Min / V0.1 / V0.2 / V0 / V1 / V2 / V3 全部门禁与 `all_must_pass`）
- `plans/requirements.json`、`plans/requirement_coverage.json`、`plans/v1-revised-plan.json`、`plans/v1-multishot-contract.json`、`plans/v1-multishot-sample-design.json`
- `contracts/**`（含 `openapi.json`、`errors.json`、`package-manifest.schema.json`、`v1-multishot.*`）
- `docs/13`、`docs/23`、`docs/27`、`docs/30`、`docs/31`、`docs/32`（只允许**追加**追记，不得改写既有裁决文字）
- `reports/v0-s2/**` 全部既有收据、`reports/unified-media/**` 全部既有收据、`reports/v1-redesign/**`
- `AGENTS.md`、`.agent-governance/stages/**`（V0-S3 packet 需另行冻结，不在本提案范围）
- `config/experience-gates.json`（全部阈值）
- 历史失败与旧分母，一律不改写。

---

## 5. 生效条件（全部满足才生效；否则零效果）

1. Codex（`codex_gate_owner`）作出范围裁决，选择 Option A/B，并写入判定记录。
2. project_owner 实际签署该判定文本（人类签署；审查员与实现者不得代签）。
3. 记录进入 `plans/execution-control.json`（追加字段，不改门槛）。
4. 后续 V0-S3 的 Stage Packet 由 Codex 另行冻结（含 Gate0 清单、文件白名单、样本 SHA、预算、清理）。
5. 在此之前：**零产品运行权限、零样本获取授权、零 Stage 激活、零合同改动**。

---

## 6. 与"不请求重复人签"的一致性

本提案**不**要求用户再次确认统一切片前端（该签署已由 `AGENTS.md` 第 23 条固定，不再重复索取）。本提案要求的是一次**范围判定**，其对象是"V0-S2 的人类义务绑定哪个交付物"，与统一切片人签是两个不同事项；若裁决人选择 Option B，则该事项退化为"是否需要用户再看一次 Comfy"。

---

## 7. 本提案的自我限制

- 未修改任何权威文件；本文件与同目录 `review.md`、`findings.json`、`receipt.json`、`draft-change-request-s2-scope-determination.json` 是本次审计的**全部**产物。
- 未签任何 Stage、未批准任何产品变更、未推定任何人类结论。
- 未运行服务/GPU/模型/媒体/浏览器/网络/FFmpeg，未消耗任何预算。
