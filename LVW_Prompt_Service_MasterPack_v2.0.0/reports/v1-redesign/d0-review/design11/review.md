# D0-B-REVIEW｜LVW V1 多镜头**设计 1.1** 独立复核（只读设计复核）

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-REVIEW`
- 复核对象：**Codex 权威设计 1.1** = commit `932dcbc48bca99c463ffea8bf11d121c36aefe0c`（"docs: resolve V1 design audit with compatible routes immutable plans and bounded budgets"）
- 本窗口加载方式：`git merge 932dcbc…`（协调者批准的唯一 source update 方式；clean merge，merge commit `4510dec`，无冲突、无手改权威内容）
- 审查者身份：隔离 Orca 可见 ClaudeCode 复核窗口，独立 worktree `…/lvw-v1-d0-review`，分支 `ljx418/lvw-v1-d0-review`
- 与实现会话分离：本窗口**未收到、未阅读、未依赖** D0-B-IMPL checker 候选（`tools/verify_v1_plan.py` 在本 checkout 中**不存在**）；按协调者指示，checker 代码复核属另一 worker / 另一任务
- 复核性质：**DESIGN_RECHECK（设计层）**。**不构成产品 Gate0、Stage PASS、产品 PASS 或人工签署。**
- 写权限：仅 `reports/v1-redesign/d0-review/design11/`（符合 `.agent-governance/stages/V1-D0/stage-control.json` 的 `D0-B-REVIEW.allowed_files = ["reports/v1-redesign/d0-review/"]`）
- 未执行：模型推理、GPU、媒体/FFmpeg、服务、浏览器、网络、安装、凭据读取、Git push、任何 canonical 合同/计划/文档/产品源码的编辑

---

## 0. English executive summary

The design 1.1 candidate **does close the 1.0 review's design contradictions**: all 22 original findings (1 Fatal / 11 Major / 10 Minor) were independently rechecked and are **RESOLVED at design level — 0 unresolved, 0 open Fatal, 0 open Major**. The compatibility model is now coherent: the canonical `POST /api/v1/jobs/batch` body is byte-untouched for V2 and the bounded V1 batch lives on a new `POST /api/v1/jobs/shot-batches`; the canonical `Scene` DTO is preserved verbatim and the new provenance lives in a `revision-info` sidecar with the ETag in the header; the per-shot frame type is renamed `ShotFrameRef` and is a valid instance of the canonical `FrameRef`; the fixed denominator, the parent budget and the checkpoint ceiling are all recomputable from machine artefacts (12 clips / 47 shots / 21 hard cuts / 18 quality segments; 450·n+90 ≤ 5490 s; 72 actions / 21600 s / 21420 s / 180 s with a 20735 s threshold estimate).

However the review also produced **6 new Minor findings** (no Fatal, no Major) that are contract-text defects the contract owner should fix before the effective contract is frozen: the ETag header is prose-only in a bespoke `metadata_only` map (N1); the machine contract's `additive_paths` omits the new `GET /api/v1/scenes/{id}` (N2); only 2 of 7 declared reuse paths carry a V1-usable annotation (N3); `ShotFrameRef` keeps a dead `anyOf` null branch next to a sibling `type: integer` (N4); the bilingual-evidence → canonical `Domains` string[] mapping has no pinned language/ordering rule (N5); the hashed field names `time_base_num/time_base_den` map onto the DDL columns `tb_num/tb_den` only inside the migration text (N6).

**Verdict: DESIGN-LEVEL CONTRADICTIONS CLOSED / 6 MINOR OPEN.** This is **not** a Stage PASS and **not** product Gate0: the 12 media clips, their hashes and annotations are still unmaterialised, no product implementation exists, the M1 inference profile is unproven, and the D0-B-IMPL checker has not been code-reviewed. The product coordinate remains `R1 / WP-R1-U3 / WAIT_HUMAN`.

---

## 1. 复核方法与证据基础

### 1.1 读取范围

`docs/30`、`docs/31`、`docs/32`、`docs/17`、`docs/20`、`docs/29`；`plans/{v1-multishot-contract,v1-multishot-sample-design,v1-revised-plan,execution-control,acceptance_cases,release_gates,requirements,tasks}.json`；`contracts/{v1-multishot.schema.json,v1-multishot.openapi-overlay.json,v1-multishot-migration.sql,openapi.json,lvw.schema.json,storage.sql,prompt-spec.schema.json}`；`reports/v1-redesign/design11-adjudication.json`（协调者裁决）、`reports/v1-redesign/design11-checks.json`（root 的 22 架构探针）、`reports/v1-redesign/d0-review/{review.md,receipt.json,checks/*}`（1.0 原始独立报告，**原文保留未改**）、`reports/v1-redesign/history/design-1.0/**`（1.0 快照）、`.agent-governance/stages/V1-D0/*`、`reports/unified-media/complete03-budget-after-live15.json`、`reports/authorization-program-v1-complete-03.{request,approval}.json`、`reports/v1-redesign/legacy-gates-before-change.json`。

### 1.2 源围栏（复核前后）

- 复核开始：`checks/hash-fence-before.txt` → `FENCED_FILES 23`（1.0 的 17 个受审文件 + 1.1 新增的 6 个：`contracts/v1-multishot-migration.sql`、`contracts/v1-multishot.openapi-overlay.json`、`plans/v1-multishot-sample-design.json`、`docs/17`、`docs/20`、`reports/v1-redesign/design11-adjudication.json`）、`MISMATCH_COUNT 0`。
- 复核结束：同一脚本重算（`checks/hash-fence-after.txt`），`MISMATCH_COUNT 0`。
- 另核对：`.agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256` 的 **文件级 SHA256 = `56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a`**，与启动指令给出的值一致；其 10 条条目逐条校验通过。
- canonical 合同三件套（`openapi.json` / `lvw.schema.json` / `storage.sql`）与 `reports/v1-redesign/legacy-gates-before-change.json` 记录的哈希一致 → **canonical 未被 1.1 改动**；旧 R1 packet manifest 哈希亦一致。

### 1.3 独立复算（本窗口自写，stdlib + jsonschema 4.23.0）

| 脚本 | 检查数 | 结果 |
|---|---|---|
| `checks/design11_contract_recheck.py` | **76** | 73 PASS / **3 FAIL**（C06、C07、C08 — 见 §4） |
| `checks/design11_sql_recheck.py` | **16** | 16 PASS / 0 FAIL |

原始命令与退出码见 `checks/commands.log`；明细见 `checks/contract-recheck-results.json`、`checks/storage-recheck-results.json`。SQL 探针**只在 `:memory:`** 上运行，hash 函数由本脚本按合同声明的算法自行实现并在报告中写明（`sha256(UTF-8 canonical JSON, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False)`，字段严格 11 项，`verified` 为 JSON boolean）。

### 1.4 与 root 的 22 架构探针的关系

root 的 `reports/v1-redesign/design11-checks.json`（22 项全过）及其生成诊断保留在权威树中：`design11.stderr.log`（overlay-builder 首次 `SyntaxError`/找不到 overlay 的路径错误）、`design11-corrected.stdout.log`、`design11-final.stdout.log`（`{"checks": 22, "failed": 0, "product_actions": 0}`）。**本复核只把它们当作支持性原始检查，不把它们当作结论**；本窗口的 92 项检查全部独立重算。已识别 root 探针未覆盖、而本窗口补上的点：合并后 effective-openapi 的**逐方法逐组件字节等价**（C03，不只是"没有同名 method"）、合并后 **`$ref` 全解析**与 **operationId 唯一**（C05/C09）、**ShotFrameRef → canonical FrameRef 的实例兼容性**（B03/B04）、**overlay 与机器合同路径集一致性**（C06/C07）、**场景 hash 的独立重算与迁移值比对**（S02）、**SQL 端父子计划封印/缺口/封后不可变/失败回滚**（S05–S13）。

---

## 2. 结论一览

| 严重度 | 1.0 原始 | 本次判定 | 新发现 |
|---|---|---|---|
| Fatal | 1（F1） | **0 未关闭**（F1 已解决） | 0 |
| Major | 11（M1–M11） | **0 未关闭**（11 全部解决，其中 4 项带 Minor 残留） | 0 |
| Minor | 10（m1–m10） | **0 未关闭**（10 全部解决） | 6（N1–N6） |

**推荐门禁状态**：`DESIGN-1.1_CONTRADICTIONS_CLOSED__MINOR_6_OPEN`（设计层）
**明确不构成**：产品 Gate0、Stage PASS、产品 PASS、人工签署。

---

## 3. 22 项原始发现的逐项复核

> 每项给出：位置/字段 · 触发 · 预期 · 1.1 实际 · 证据（探针编号 / 文件·字段）。逐项结构化版本见 `findings.json`。

### F1（Fatal）同一 canonical 路由 `/api/v1/jobs/batch` 承载两套互斥请求合同 → **已解决**

- **位置/字段**：`contracts/openapi.json` `paths["/api/v1/jobs/batch"].post.requestBody = {items:[AnalyzeRequest]}`（`x-product-version: V2`）｜`contracts/v1-multishot.openapi-overlay.json` `add_paths`｜`plans/v1-multishot-contract.json` `explicit_reserved_v2_paths`
- **触发**：M1-B 提交固定分母逐镜头批量
- **预期**：一个路由一个请求合同；V2 batch 语义与 V1 有界多镜头语义共存
- **1.1 实际**：canonical batch **字节未改**（A04）；新增有界 `POST /api/v1/jobs/shot-batches`，请求体为 `MultiShot_BatchAnalyzeRequest`（C02）；候选 DTO 自带 `x-route: "POST /api/v1/jobs/shot-batches ONLY; never replaces canonical /jobs/batch items body"`；`/api/v1/jobs/{id}/retry` 明确保留给 V2
- **证据**：C01、C02、C03；合并后的 effective-openapi 中 canonical 全部 path/method/component 与 1.0 记录**逐字节相等**

### M1（Major）canonical `Scene` 与候选 `SceneRevision` 字段集互斥 → **已解决**（残留 N1）

- **位置/字段**：`contracts/openapi.json` `components.schemas.Scene`｜`contracts/v1-multishot.schema.json` `$defs/CoreScene`、`$defs/SceneRevisionInfo`｜overlay `add_paths["/api/v1/scenes/{id}"].get`、`add_paths["/api/v1/scenes/{id}/revision-info"].get`
- **触发**：M1-A 边界读取/修订写入
- **预期**：同一路由有效响应 DTO 唯一；`If-Match` 有可比较的 etag；新增 GET 必须显式声明
- **1.1 实际**：候选 `CoreScene` **与 canonical `Scene` 完全相等**（openapi 与 lvw.schema 双源一致）；canonical `PUT` 的 request/response 未被替换，只在同路径**新增** `GET`（返回同一个 canonical `Scene`）；新 provenance 走 sidecar `GET /scenes/{id}/revision-info` → `SceneRevisionInfo`；ETag 走响应头；未引入 `detected` 词表
- **证据**：B02、B07、C03、I06
- **残留**：**N1** — overlay 中 ETag 仅以 `metadata_only` 自由文本存在，全 overlay 无 `headers` 键（C08），且 `metadata_only → effective-openapi` 的提升规则未定义

### M2（Major）`SceneRevision` 无法表达"未验证/估计时间" → **已解决**

- **位置/字段**：`$defs/SceneRevisionInfo`（`time_basis` 枚举 `decoded_pts|estimated|unverified` + 内嵌 canonical `Scene.verified`）｜`scene_revision_meta` 的配对 CHECK｜`request_errors.SCENE_TIME_UNVERIFIED=422`｜`terminal_errors.SCENE_TIME_UNVERIFIED.segment_job_status=failed`
- **触发**：解码出缺失/非单调 PTS、VFR 仅估算边界
- **预期**：DTO 能区分真实 PTS 与估计/未验证；错误码有对应状态；旧未核验 scene 不得启动新分析
- **1.1 实际**：`time_basis` 必填（G13 负例），不变式 `scene.verified iff time_basis==decoded_pts`，DDL 强制同一配对（S09），detect job 以 `SCENE_TIME_UNVERIFIED` 失败并带 `time_basis` 与缺失/倒序计数，迁移来的旧 scene 一律 `verified=0/unverified`（S02）
- **证据**：G13、S02、S09、D02、D03

### M3（Major）候选 `FrameRef` 与 canonical `FrameRef` 同名不同形 → **已解决**（残留 N4）

- **位置/字段**：`$defs/ShotFrameRef`｜canonical `contracts/lvw.schema.json` `$defs/FrameRef` 与 `openapi` `components.schemas.FrameRef`｜`model_run_artifacts.frames_json`
- **触发**：记录一次逐镜头模型运行的帧引用
- **预期**：逐镜头帧既能被 `ShotEvidence.frame_refs` 使用，又能落在 canonical `ModelRun.frames`
- **1.1 实际**：改名 `ShotFrameRef`，**无命名冲突**（C04）；形状是 canonical `FrameRef` 的合法实例（B03/B04）；live-15 的 4 个真实帧引用同时是合法 `ShotFrameRef`（B05）；落库 `model_run_artifacts.frames_json`，并按 canonical `ModelRun.frames` 返回
- **证据**：C04、B03、B04、B05、S15
- **残留**：**N4** — `source_pts/time_base_num/time_base_den` 保留 `anyOf[integer,null]` 分支同时又写 `type: integer`，null 分支永不可达（G15）；实际行为符合"逐镜头只收真实 PTS"的意图，但 schema 文本自相矛盾

### M4（Major）`ParentJob` 无 DTO、7 个必填中 5 个无载体 → **已解决**

- **位置/字段**：`$defs/ParentJob`（11 必填：`id/plan_hash/planned_child_ids/selected_scene_revision_ids/total/terminal_count/deadline_at/execution_budget_seconds/status/not_executed_count/retry_of_parent_id`）｜`$defs/BatchChildrenResponse = {parent, children}`｜`$defs/ChildSummary.ordinal`
- **触发**：前端显示父进度/剩余时间；父取消与 deadline 判定
- **预期**：父进度与总时限在公开契约可见可核对
- **1.1 实际**：机器合同 `entities.ParentJob.required` 与 schema 必填集**逐项相等**；children 响应含 parent 视图（含 `deadline_at`/`terminal_count`）与有序 children（`ordinal` 0..n-1）；canonical strict `Job` 未加字段，父进度以 `progress_done=terminal_count`、`progress_total=total` 映射
- **证据**：D_ParentJob、I09、A04、C03

### M5（Major）缺"不可变子计划"与"子项↔镜头↔边界"绑定存储 → **已解决**

- **位置/字段**：`shot_batch_parent` / `shot_batch_item` / `shot_batch_seal` / `attempt_execution`｜通用 `batch_child` 不动
- **触发**：父批量创建 → 子项排队 → 部分失败/取消 → 导出清单
- **预期**：计划在父创建同事务物化且不可变；分母与顺序可查询；子项可回溯 shot 与 scene revision
- **1.1 实际**：新表带 `ordinal/shot_id/scene_revision_id/scene_revision_hash/media_sha256/config_hash`；封印触发器校验 count/ordinal（缺子项不可封 S05、序号有缺口不可封 S06）；worker claim 必须 join seal（封前 0 个可领、封后 2 个可领 S07）；parent/item/seal 封后不可增删改（S08）；`job/attempt` 状态仍可变（S14）；通用 `batch_child` 保持原两列且为空（S16）
- **证据**：S05–S08、S14–S16
- **说明**："全部 job + 父 + items + seal 同事务"是 owner 侧代码规则（docs/31 明写），DDL 不强制——属设计候选的正常分工

### M6（Major）`AnalysisBinding` 缺租约 token、`scene_revision_hash` 无来源与存储 → **已解决**（残留 N6）

- **位置/字段**：`$defs/AnalysisBinding`（含 `lease_token`）｜`$defs/PublicAnalysisBinding`（无 token）｜`shot_analysis_binding` 表｜`scene_revision_meta.content_sha256/etag`｜`scene_hash` 声明
- **触发**：终结 CAS、边界变更 stale 判定、显式采纳校验
- **预期**：绑定能表达 attempt+token+cancel_epoch+scene hash；hash 有确定算法与存储列
- **1.1 实际**：`lease_token` 为内部必填，公开绑定**无该字段且携带时会被拒**（B06/G05）；hash 算法与 11 字段清单写死（D05）；本窗口按声明算法独立重算的 hash 与迁移落库值**逐字符相等**，etag 为带引号的强标签（S02）；绑定落 `shot_analysis_binding`（含 `lease_token`/`cancel_epoch`/`scene_revision_hash`），证据落 `shot_analysis_evidence`，原始字节仍在 `model_run`
- **证据**：B06、G05、D05、S02、S15
- **残留**：**N6** — 被 hash 的字段名 `time_base_num/time_base_den` 与 DDL 列名 `tb_num/tb_den` 的映射只体现在 SQL 调用处（D04），迁移外移植可能静默算出不同 hash

### M7（Major）"未执行/截止失败"无终态值、父 deadline 不可观测 → **已解决**

- **位置/字段**：`ChildSummary.status` / `ParentJob.status` / `terminal_errors` / `attempt_execution.model_action_at`
- **触发**：父 deadline 届满，剩余子项未开始
- **预期**：每个计划子项有显式终态；截止失败与普通失败可区分；不扩 Job 枚举
- **1.1 实际**：`ChildSummary.status`、`ParentJob.status` 均为 canonical `Job.status` 的**子集**，无 `not_run`（G06 负例）；映射写死：截止未发模型 = `failed` + `BATCH_DEADLINE_EXCEEDED` + `model_started=false`，父 `failed`；用户取消 = `cancelled` + `JOB_CANCELLED`，成功项保留；其余全终态组合父 `partial` + `CHILD_ANALYSIS_INCOMPLETE`；`terminal_count` 含所有终态且不等于成功数；`model_started` 由持久化的 `attempt_execution.model_action_at` 派生（S11）
- **证据**：D01、D02、G06、S11

### M8（Major）逐镜头证据无法满足四来源域合同（R06）→ **已解决**（残留 N5）

- **位置/字段**：`$defs/Character`、`$defs/SceneEvidence`、`$defs/Action`（均带 `domain` 与双语来源）｜canonical `$defs/Domains`
- **触发**：逐镜头证据 → CompilerOwner 编译四目标
- **预期**：机器建议进入编译器前可区分观察/推断；逐镜头草稿可映射 canonical `Domains`
- **1.1 实际**：三类证据**各带** `domain ∈ {observation, inference}` 与双语来源（I08）；缺 domain 被拒（G09）、模型声明 `user_evidence` 被拒（G10）；`unknowns` 映射 `Domains.unknowns`，`user_evidence/creative_intent` 归人工；docs/31 给出确定性适配与优先级（人工锁定 > shot > scene > 配方 > 模板 > 机器建议），R06 仍在 V1（J02）
- **证据**：I08、G09、G10、J02
- **残留**：**N5** — canonical `Domains.observation/inference/unknowns` 是 `string[]`、无语言槽位，而候选证据是双语；1.1 只说"按 domain 格式化进入 canonical Domains"，未钉死语言/顺序/条目规则，两个实现可能合法地分叉

### M9（Major）固定分母 47 段无法由 12 段构成推出 → **已解决**

- **位置/字段**：`plans/v1-multishot-sample-design.json`｜`docs/32` 12 行表
- **触发**：Gate0 前冻结样本与分母
- **预期**：固定分母可由冻结样本清单**复算**
- **1.1 实际**：机器表逐行给出 clip/类别/镜头数/硬切标注数/质量归属，复算得 **12 片 / 47 镜头 / 21 硬切**（E01）；docs/32 的 12 行表与机器表**逐行一致**（E06）；18 段归属 12/3/3 且每段编号落在该 clip 的镜头数内（E02/E03/E04）；所有媒体的 `source_sha256/annotation_hash` 为 null、状态 `NOT_MATERIALIZED_NOT_FROZEN`（E05）——**未伪装已有真实样本**
- **证据**：E01–E06

### M10（Major）父 1800 s 覆盖不了 12 个子项 → **已解决**

- **位置/字段**：`plans/v1-revised-plan.json` `limits`（`batch_per_child_budget_seconds=450`、`batch_fixed_budget_seconds=90`、`batch_deadline_seconds_max=5490`；旧 `batch_deadline_seconds=1800` 已删）
- **触发**：对 12 镜头样本执行父批量
- **预期**：父运行预算足以覆盖其固定分母
- **1.1 实际**：`450*n+90`（n=1..12，最大 5490）逐项复算通过；每子项 420 s 分析 + 30 s 释放 = 450 s；deadline 于 `created_at` 固定、公开于 `ParentJob.deadline_at`、重启不自动延长；截止项**保留为失败行**而非删除，且不得记 PASS
- **证据**：F01、D02

### M11（Major）每完整轮预算估计低于实测时延包线 → **已解决（明示为性能上限而非实测保证）**

- **位置/字段**：`plans/v1-revised-plan.json` `checkpoint_budget`｜`docs/32` 两层时间预算与全局额度
- **触发**：Gate0 冻结一个完整 V1 checkpoint 的预算
- **预期**：估计值与实测相容，或明写依据与超出处置
- **1.1 实际**：cap **72 动作 / 21600 s**，执行截止 **21420 s**，末尾 **180 s** 清理；阈值估算 `53*300 + 12*180 + 65*30 + 300 + 7*35 + 180 = 20735` ≤ 21420，且 53+12=65、65+7=72、21420+180=21600（F02）；推导式"47 逐镜头 + 原 Q01 十二图六片 = 65 成功调用"在 docs/32 与机器预算一致（F04）；`estimate_basis` 明写"design performance thresholds, not measured current per-shot P95 and not hard worst-case guarantee"，docs/32 明写"300/180 是既有性能门限，不是本次已测出的 M1 P95，也不是每次调用的硬最坏耗时"；**全局账本不清零**：live15 快照 29 动作/8 轮/1506 s → 余 995/16/171294，`min(13,16,7)=7` 轮（F03）
- **证据**：F02、F03、F04

### m1–m10（Minor）全部已解决

| ID | 判定 | 关键证据 |
|---|---|---|
| m1 | 已解决 | I01：docs/17 与 docs/20 均新增 2026-11-11 优先覆盖段，点名 V1-M1 与"完整 R13/A13/X04/通用 batch/恢复仍属 V2" |
| m2 | 已解决 | I02：docs/29 改为"禁止用于本功能开发"；docs/32 改为"绝不用于本次 MS 开发"且"即使注明用途也不允许" |
| m3 | 已解决 | I03：机器表 `mutual_exclusion` 要求开发集/新 MS 集/Q01 集/11 段人工留样在**媒体哈希与来源 ID** 上互斥；docs/32 同文；E05 证明尚未捏造哈希 |
| m4 | 已解决 | E02/E04/E06：18 段 = 12 简单动作 + 3 含糊 + 3 静态，机器表与文档表逐项给出归属 |
| m5 | 已解决 | I04：`execution-control.updated_at = 2026-11-11`；H01 同时确认人签/产品验收仍为 null、`V1_ACCEPTED` 仍在 `forbidden_claims` |
| m6 | 已解决 | B07：候选 schema 无 `detected` 词表，`editor` 枚举 == canonical |
| m7 | 已解决 | D06 + I10：六模式 == canonical `PromptSpec.mode` 枚举；canonical `AnalyzeRequest.mode` 仍是自由字符串且未改 |
| m8 | 已解决 | I05：docs/31 明写单次有界评分 + PTS 元数据索引（≤16 MiB、detect ≤120 s）+ 逐镜头 keyframe seek + 禁全片 tensor；`limits` 有对应常量 |
| m9 | 已解决 | D03：`request_errors` 的每个 HTTP 状态都在新路由的 responses 中声明；D02：`terminal_errors` 映射 canonical Job 终态 |
| m10 | 已解决 | S03：迁移后 `shot_scene_binding` **0 行**（manual/image shot 存在），旧 `prompt_revision.content_sha256` 未变；S16：通用 `batch_child` 原样保留 |

---

## 4. 本次复核的新发现（6 项 Minor，无 Fatal / 无 Major）

> 均属合同文本缺陷，需由合同 owner（Codex）在**冻结 effective 合同之前**修；不构成设计矛盾，也不阻塞"设计层矛盾已关闭"的判断。

| ID | 位置/字段 | 触发 | 预期 | 实际 | 证据 | 归属 |
|---|---|---|---|---|---|---|
| **N1** | `contracts/v1-multishot.openapi-overlay.json` `metadata_only["/api/v1/scenes/{id}"].ETag_response_header` | 实现者按"base + overlay"生成 effective-openapi，需决定 ETag 放哪 | overlay 里给出真正的 OpenAPI `responses.200.headers`（头名 ETag、string schema、强标签格式），并写明 `metadata_only` 的提升规则 | overlay **全文无 `headers` 键**；ETag 只是自定义 map 里的自由文本，其合并语义未定义（确切格式只写在 docs/31 与机器合同里） | C08 | Codex（合同） |
| **N2** | `plans/v1-multishot-contract.json` `additive_paths`（6）vs overlay `add_paths`（7） | 实现/校验按合同列出的新增路径集比对 overlay | 声明集覆盖 overlay 引入的全部 path/method，或把"新路径"与"既有路径上的新 method"分列 | overlay 在既有路径 `/api/v1/scenes/{id}` 上新增 `GET`，该路径**不在** `additive_paths` 中 → 按合同列比对者会漏掉这个新 GET | C06 | Codex（合同） |
| **N3** | overlay `metadata_only`（2 项）vs 合同 `reuse_paths`（7 项） | M1 公开面按 reuse_paths 构建（scenes 列表、shots、shots/{id}、jobs/{id}、jobs/{id}/cancel） | 要么逐 path/method 标注 V1 可用，要么明确"reuse 路径无需提升标注"的规则 | 5 条 reuse 路径**无任何标注**：canonical 中 `/api/v1/scenes` 的 GET 与 `/api/v1/scenes/{id}` 的 PUT 仍标 `x-product-version: V2`（overlay 只在 `scenes/detect` 标了 `v1_profile`）；`/api/v1/shots`、`/shots/{id}`、`/jobs/{id}`、`/jobs/{id}/cancel` 本身已是 V1，却同样没有标注 | C07 | Codex（合同） |
| **N4** | `$defs/ShotFrameRef.properties.source_pts / time_base_num / time_base_den` | 实现者读 `anyOf` 想接受 null，或 schema linter 报矛盾 | 要么纯非空 integer，要么去掉矛盾的同级 `type` | `anyOf[integer,null]` 与同级 `type: integer` 并存 → null 分支**永不可达**（G15）；实际行为符合"逐镜头只收真实 PTS"的意图，但文本两说 | G15 | Codex（合同） |
| **N5** | `$defs/Character/SceneEvidence/Action`（双语）→ canonical `$defs/Domains`（`string[]`，无语言槽） | 逐镜头适配器把证据格式化进 canonical Domains 供四目标编译 | 钉死规则（如每条进一条英文目、其余入 `text_zh`，并给顺序/去重规则） | 1.1 只说"按 domain 格式化进入 canonical Domains.observation 或 inference"，语言/顺序/条目规则未定义，两个实现可合法分叉 | I08 + canonical `lvw.schema.json` `$defs/Domains` | Codex + CompilerOwner |
| **N6** | 合同 `scene_hash.fields` vs 迁移 SQL `lvw_scene_hash(s.media_ref_id, m.sha256, s.version, …, s.tb_num, s.tb_den, …)` | 共享 hash 函数在迁移之外被实现/移植 | 合同中写明"被 hash 的字段名 ↔ DDL 列名"映射 | 该映射**只体现在 SQL 调用处**；移植时按列名 hash 会静默产出不兼容的 hash | D04 | Codex（合同） |

---

## 5. 已核对且一致的项目（逐项附证据）

1. **canonical 未被改动**：`openapi.json` / `lvw.schema.json` / `storage.sql` / 旧 R1 packet manifest 的 SHA256 与 `legacy-gates-before-change.json` 一致（A04、A05）；合并 effective-openapi 后 canonical 的每个 path/method/component 逐字节相等（C03）。
2. **V1 有界批量与 V2 批量并存且互不污染**：新路径独立组件、canonical batch 原样保留（C01、C02、C03）；`explicit_reserved_v2_paths` 明确保留 `/jobs/batch` 与 `/jobs/{id}/retry`。
3. **canonical `Scene` 形状零漂移**：候选 `CoreScene` 与 canonical `Scene` 完全相等（B02）；canonical `PUT` 未被替换，仅新增 GET（C03）；无新词表（B07）。
4. **逐镜头帧是 canonical `FrameRef` 的合法实例**（B03/B04），且真实 live-15 帧同时满足 `ShotFrameRef`（B05）；落库表 `model_run_artifacts.frames_json` 存在（S15）。
5. **内部/公开绑定分离**：公开绑定无 `lease_token`，携带即被拒（B06、G05）。
6. **场景 hash 可复现**：声明算法 + 11 字段（D05），迁移值 == 独立重算值，etag 为带引号强标签（S02）；legacy 行一律 `unverified/false`（S02、S09）。
7. **固定分母可复算**：12/47/21/18(12/3/3)，机器表与文档表一致（E01–E06）；样本**未**被伪造成已冻结（E05）。
8. **不可变计划有真实载体**：封印/缺口/封后不可变/claim 需 join seal（S05–S08）；job/attempt 仍可变（S14）；通用 `batch_child` 未动（S16）。
9. **失败闭环 fail-closed**：legacy 媒体哈希非法 → 整段迁移中止、无残留 DDL、`schema_version` 仍为 1（S12）；非法 editor 词表同样中止（S13）。
10. **父预算与轮次上限自洽**：`450*n+90 ≤ 5490`（F01）；`20735 ≤ 21420 = 21600-180`，动作 `65+7=72`（F02）；推导式在文档与机器预算一致（F04）。
11. **全局账本未清零**：`historical_consumption_reset=false`，余量与"7 轮"由 live15 快照复算（F03）；M1 仅映射到已授权的 `R2`，无 V2/R3 别名（H03）。
12. **1.0 已核对项未回退**：分母 29/38/47 仍为加法且原 21 为未改前缀（J01）；R13 仍 V2、R22/R06 仍 V1（J02）；阶段依赖图无环（J03）；Q01 的"12 图+6 片 / 图≥10/12 / 片≥5/6 / 非模型自评"原样保留（H05）；V1 用例集 = 原 21 + MS01–08 = 29（H04）。
13. **未冒充人签/产品通过**：`human_signoff=null`、`product_acceptance=null`、`active_slice.human_signoff=null`、`V1_ACCEPTED` 仍在 `forbidden_claims`、当前切片仍 `WP-R1-U3 … HUMAN_PENDING`、V1-M1 机器验收 `NOT_RUN` / 人签 `NOT_SIGNED`（H01、H02）。
14. **权威提交未触碰产品源码**：`git diff --name-only 0459f85 932dcbc` 未命中 `lvw/`、`tools/`、`frontend/`（H06）。
15. **schema 边界表述诚实**：候选 schema 通过 draft 2020-12 metaschema（B01）；跨字段/跨引用语义仍写在 `x-semantic-invariants` 中由 owner 侧校验（如等长 shot_ids/scene_revision_ids 不被 schema 拦截，G04 明确列为"仅语义"）。

---

## 6. 属正常待办、**不是**本次发现的矛盾（未来前置）

1. 12 段非私有媒体的取得、license、source/hash、PTS、切点与独立标注的冻结（E05 明确 `NOT_MATERIALIZED_NOT_FROZEN`）——属 Gate0 前置，**未伪造**。
2. M1 新 profile（think=false / ctx4096 / predict1536 / temp0.2）的真实 pilot：截断、解析、质量与 GPU 硬限——设计已声明"不能凭 profile 猜已达标"。
3. 逐镜头 300 s 阈值的实测确认；超出时必须保留失败并重排执行包，不得缩分母、不得用旧 run 正例填本轮。
4. 产品实现（R1/M1/R2）、集中 checkpoint、隔离独审与真实人签；当前 621b1bf 切片体验签署仍待，产品坐标仍为 R1/WP-R1-U3/WAIT_HUMAN。
5. **D0-B-IMPL checker 候选的代码复核**（`tools/verify_v1_plan.py` 不在本 checkout 中；本窗口按协调者指示未审）——属独立任务。
6. Gate0 对最终 HTTP 映射、effective overlay、迁移版本与阈值的正式冻结；`MANIFEST.sha256` 未包含本次新增报告文件（根文件不在本 workpack 的 `allowed_files` 内），需由 Codex 在自己的 packet 中处理。

---

## 7. 结论

```text
原始发现复核：22 项（Fatal 1 / Major 11 / Minor 10）
  已解决            22
  已解决带 Minor 残留 4（M1→N1、M3→N4、M6→N6、M8→N5）
  未解决             0
本次新发现：6 项 Minor（N1–N6），Fatal 0 / Major 0
设计层结论：DESIGN-1.1_CONTRADICTIONS_CLOSED__MINOR_6_OPEN
本窗口判定：不构成产品 Gate0、不构成 Stage PASS、不构成产品 PASS、不构成人工签署
产品坐标未变：R1 / WP-R1-U3 / WAIT_HUMAN（human_signoff=null，product_acceptance=null）
遗留前置：真实样本冻结、M1 profile pilot、实现与 checkpoint、独审、真实人签、checker 代码复核
```

若 N1–N6 由合同 owner 修订（仅合同文本，不改任何固定分母/阈值），本窗口可按同一只读口径再复算一次；本窗口不自行修改任何合同、计划或文档。
