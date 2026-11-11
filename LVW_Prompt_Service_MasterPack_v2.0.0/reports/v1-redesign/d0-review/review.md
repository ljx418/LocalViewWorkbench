# D0-B-REVIEW｜LVW V1 多镜头修订设计独立审查（只读设计审查）

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-REVIEW`
- 审查者身份：隔离 Orca 可见 ClaudeCode 审查窗口（`term_5671f77b-4db0-4f65-ab26-be6d9406d259`），独立 worktree `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-review`，分支 `ljx418/lvw-v1-d0-review`
- 实现会话（必须不同）：`term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0` 协调者 / `lvw-v1-d0-implement`（D0-B-IMPL）。**本次未收到、未阅读、未依赖 D0 checker 候选**；`tools/verify_v1_plan.py` 在本 checkout 中不存在，协调者消息中提到的候选 372575b 与 D0-CODE-M01 属代码审查范畴，按协调者指示不在本任务处理。
- 审查性质：`DESIGN_REVIEW`。**不构成产品 Gate0、Stage PASS、产品 PASS 或人工签署。**
- 写权限：仅 `reports/v1-redesign/d0-review/`（符合 `.agent-governance/stages/V1-D0/stage-control.json` 的 `D0-B-REVIEW.allowed_files`）
- 未执行：模型推理、GPU、媒体/FFmpeg、服务、浏览器、网络、pip/npm 安装、凭据读取、供应商切换、购买、Git push、任何 canonical 合同/计划/文档/产品源码的编辑。

---

## 0. English executive summary

The revised V1 multi-shot design is **scope-correct and internally consistent in most respects**: the approved V1 subset does not swallow full R13/V2, the fixed denominators are additive (29/38/47 with the original 21/30/39 preserved as an unchanged prefix), Q01 is retained verbatim, the stage DAG is acyclic, canonical OpenAPI/core schema/DDL are byte-identical to the pre-change record, the COMPLETE03 accounting maps the new `V1-M1` display stage onto the **authorized V1 stage `R2`** with no V2 alias and no budget reset, the 11-video human holdout stays reserved, and the claim that the current `1.8` video template is appearance-only is factually correct.

However the design is **not yet implementable without owner decisions**. One Fatal contract conflict and eleven Major gaps remain, all reproduced deterministically from the frozen files (41 recomputation checks, 31 PASS / 10 FAIL; metaschema + 22 behavioural probes). The most serious: `POST /api/v1/jobs/batch` is a single canonical path that the candidate replaces with an incompatible request body while both the V1-M1 fixed-denominator batch and the retained V2 batch semantics need it.

**Verdict: NOT GO_FOR_DESIGN_CONSOLIDATION_ONLY** (1 Fatal, 11 Major, 10 Minor). Gate owner (Codex) must resolve the Fatal and the Majors before product contract freeze. This review is not a product or human acceptance and asserts no product PASS.

---

## 1. 审查方法与证据基础

### 1.1 阅读范围（任务指定，全部已读）

`AGENTS.md`（AGENTS 22 条规则）｜`docs/00,01,14,15,29,30,31,32`｜`plans/{requirements,tasks,acceptance_cases,release_gates,execution-control,v1-revised-plan,v1-multishot-contract}.json`｜`contracts/v1-multishot.schema.json` + 未改动的 canonical `contracts/openapi.json`、`contracts/lvw.schema.json`、`contracts/storage.sql`、`contracts/semantic-invariants.json`｜`.agent-governance/stages/V1-D0/*`｜`reports/v1-redesign/product-change-approval.json`、`reports/v1-redesign/legacy-gates-before-change.json`。

补充取证（非任务清单但用于判定）：`docs/06,17,20,24`、`contracts/{job,scene,revision,media-ref,v0-result}.schema.json`、`templates/analysis_video_*.txt`、`config/runtime.defaults.json`、`reports/unified-media/live-15/video-model-run.json`、`reports/unified-media/complete03-budget-after-live15.json`、`reports/authorization-program-v1-complete-03.{request,approval}.json`、`tools/verify_pack.py`（只读阅读，未运行产品链）。

### 1.2 哈希围栏（审查前后）

`.agent-governance/stages/V1-D0/spec-manifest.json` 的 17 个受审文件在审查开始时全部匹配（`checks/hash-fence-before.txt`，`MISMATCH_COUNT 0`）；审查结束后重新计算并比对（`checks/hash-fence-after.txt`）。审查过程中未写入任何受审源文件。

### 1.3 独立复算（不依赖 D0-B-IMPL 的 checker）

`checks/recompute_design_checks.py`（本人编写，stdlib only，只读）为 41 项确定性检查；`checks/metaschema_probe.py` 用已安装 `jsonschema 4.23.0` 做 metaschema 校验 + 22 个行为负例。原始命令与退出码见 `checks/commands.log`（两个脚本 exit=0；明细见 `checks/recompute-results.json`、`checks/metaschema-check.log`）。

> 说明：`tools/verify_v1_plan.py` 由另一 worker 拥有，本次**不引用其任何结论**，也不以"存在 34 个测试"作为独立证明。

---

## 2. 结论一览

| 严重度 | 数量 | 编号 |
|---|---|---|
| Fatal | 1 | F1 |
| Major | 11 | M1–M11 |
| Minor | 10 | m1–m10 |

**推荐门禁状态**：`NOT_GO_FOR_DESIGN_CONSOLIDATION_ONLY`。F1 与 M1–M11 由门禁负责人（Codex）在产品合同冻结前裁决；本审查不自行改写合同/阈值。

---

## 3. Findings

### F1（Fatal）同一 canonical 路由 `/api/v1/jobs/batch` 被要求承载两套互不兼容的请求合同

- **位置/字段**：
  - `plans/v1-multishot-contract.json` → `reuse_paths[5] = "/api/v1/jobs/batch"`
  - `contracts/v1-multishot.schema.json` → `$defs/BatchAnalyzeRequest`（required `shot_ids, scene_revision_ids, mode, config_profile`）
  - `contracts/openapi.json` → `paths["/api/v1/jobs/batch"].post.requestBody` = `{items: [AnalyzeRequest]}`，`x-product-version: "V2"`
  - `docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md:53,61`
- **触发**：M1-B 实现"固定 `scene_revision_ids/shot_ids`、max12、202 父 job + 计划子清单"的批量提交。
- **预期**：一个路由一个请求合同；V1-M1 的固定分母逐镜头批量与仍保留在 V2 的 batch/R4（`docs/15_V2_IMPLEMENTATION.md` §R4 "batch拆child job…"）必须同时存在。
- **实际**：候选合同把该路由的请求体换成 `{shot_ids, scene_revision_ids, mode, config_profile, content_profile, custom_guidance}`，而 canonical 请求体是 `{items:[AnalyzeRequest]}`（`additionalProperties:false`）。两条合同在同一路径上互斥。同时 `product-change-approval.json.public_contract_policy` 要求 canonical OpenAPI 保持不可变，因此不能改 canonical；docs/31:53 又要求"不起平行 API"，因此也不能另起同名并行路由。三选一（改 canonical / 起平行路由 / overlay 替换 body）**设计未决**。
- **证据**：`checks/recompute-results.json` → `C20 FAIL`：`canonical=["items"] candidate=["config_profile","content_profile","custom_guidance","mode","scene_revision_ids","shot_ids"]`；`contracts/openapi.json` 中 `/api/v1/jobs/batch` 请求体与 `x-product-version: V2`；`docs/15` §R4。
- **建议的有界修正（由合同 owner 裁决）**：二选一并写死——(a) 给 V1 多镜头父批量一个独立版本化路径（如 `POST /api/v1/jobs/shot-batches`），canonical `/jobs/batch` 原样保留给 V2；或 (b) 保留同一路径但把请求体改为可辨识联合（`items` 仍合法 + 新增 `shot_ids/scene_revision_ids` 互斥分支），并在 overlay 中标明哪一分支属 V1-M1、哪一属 V2。无论哪种，`reuse_paths`、`BatchAnalyzeRequest`、`http_rules` 必须同步改写并留旧版可追溯。

---

### M1（Major）`/api/v1/scenes` 与 `/api/v1/scenes/{id}` 上 canonical `Scene` 与候选 `SceneRevision` 字段集互斥

- **位置/字段**：`contracts/openapi.json` `components.schemas.Scene`（required: `id, media_ref_id, revision, start_pts, end_pts, origin_pts, time_base_num, time_base_den, verified, editor[algorithm|human]`）对照 `contracts/v1-multishot.schema.json` `$defs/SceneRevision`（required: `id, media_ref_id, source_sha256, version, origin_pts, time_base_num, time_base_den, start_pts, end_pts, origin[detected|human], etag`）；`plans/v1-multishot-contract.json` `reuse_paths[1,2]`；`docs/31:59`（"GET/PUT /api/v1/scenes/{id} 返回SceneRevision；写入If-Match"）。
- **触发**：M1-A 实现边界读取/修订写入。
- **预期**：同一路由的有效响应 DTO 唯一，且 `If-Match` 有可比较的 etag。
- **实际**：canonical-only 字段 `{verified, editor, revision}` 与 candidate-only 字段 `{source_sha256, version, origin, etag}` 互斥，无任何字段集同时满足两者；canonical `Scene` **没有 etag 字段**，而 canonical `PUT /api/v1/scenes/{id}` 已经要求 `If-Match`——新 DTO 用 `etag` 补上了这个既存缺口，但只能靠替换该路由的响应 schema 达成。另外 canonical 只有 `PUT`，没有 `GET`，而 docs/31:59 要求 "GET/PUT"，新增 GET 属增量但必须显式声明。
- **证据**：`checks/recompute-results.json` → `C22 FAIL`（`canonical_only=["editor","revision","verified"] candidate_only=["etag","origin","source_sha256","version"]`）。
- **建议的有界修正**：在 overlay 中显式声明每个被提升路由的**有效响应 DTO**（例如新增组件 `SceneRevisionV1` 并替换这两条路由的 response schema，或另立路径），并写明词汇映射 `editor(algorithm|human) ↔ origin(detected|human)`、`revision ↔ version`、`verified ↔`（见 M2）；同时把新增的 `GET /api/v1/scenes/{id}` 列入 overlay 清单。

### M2（Major）`SceneRevision` 无法表达"未验证/估计时间"，但 `SCENE_TIME_UNVERIFIED` 已是声明错误码

- **位置/字段**：`contracts/v1-multishot.schema.json` `$defs/SceneRevision`（无 `verified` / `time_basis` / `time_unverified` 字段）；`plans/v1-multishot-contract.json` `entities.SceneRevision.invariants` 含 `"verified timestamps"`；同文件 `new_error_candidates` 含 `SCENE_TIME_UNVERIFIED`；`docs/31` §公开入口演进与 §内容分析职责；`docs/15` §R3 "缺失/不单调PTS标time_unverified并可人工校订，不能伪造精确"。
- **触发**：解码出缺失/非单调 PTS 的片段，或 VFR 片段只有估算边界时。
- **预期**：DTO 能区分"真实 PTS 边界"与"估计/未验证边界"，客户端据此提示人工校订；错误码有对应状态。
- **实际**：DTO 无任何字段承载该状态，`"verified timestamps"` 不变量在 schema 层无载体（且 canonical `Scene.verified` 布尔被新 DTO 丢弃）；实现者只能自行发明字段名或忽略该不变量——两难。
- **证据**：`checks/metaschema-check.log`（`SceneRevision_*` 无任何 verified 相关约束）；`checks/recompute-results.json` → `C22`。
- **建议的有界修正**：在候选 `SceneRevision` 增加 `time_basis`（枚举 `decoded_pts | estimated | unverified`）与 `verified`（布尔，或直接用前者），并规定：仅 `decoded_pts` 允许被 MS01 按 ±2 源帧容差评分；`estimated/unverified` 的片段必须返回 `SCENE_TIME_UNVERIFIED` 或显式标记待人工校订。

### M3（Major）候选 `FrameRef` 与 canonical `FrameRef` 同名不同形，逐镜头帧无法写入 canonical `model_run.frames`

- **位置/字段**：`contracts/v1-multishot.schema.json` `$defs/FrameRef`（required `index, source_pts, time_base_num, time_base_den, sha256`）对照 `contracts/lvw.schema.json` `$defs/FrameRef` 与 `contracts/openapi.json` `components.schemas.FrameRef`（required 额外含 `target_seconds` 与 `time_basis[sample_target|decoded_pts]`；同一 canonical 类型还被 `MediaRef.frames`、`ModelRun.frames` 引用）。
- **触发**：M1-B 记录一次逐镜头模型运行的帧引用。
- **预期**：逐镜头帧既能被 `ShotEvidence.frame_refs` 使用，也能落在 canonical `ModelRun.frames`（该表是 canonical 唯一模型运行记录，见 `plans/v1-multishot-contract.json` `storage_plan` "add shot.scene_revision_id with foreign key and required binding in model_run metadata"）。
- **实际**：(a) 同一 OpenAPI 组件命名空间出现同名不同形类型；(b) 候选 `FrameRef` 缺 `target_seconds`、`time_basis`，因此**不是** canonical `FrameRef` 的合法实例，无法写入 canonical `ModelRun.frames`；(c) 丢失 `time_basis` 即丢失 SEM02 与 docs/17 的"显示序号≠真实时间、`sample_target` 不得宣称精确"区分。
- **证据**：`checks/recompute-results.json` → `C18 FAIL`（`collisions=["FrameRef"]`）、`C19 FAIL`（`missing_in_candidate=["target_seconds","time_basis"]`）、`C41 PASS`（canonical 实际帧含 `target_seconds`+`time_basis`，见 `reports/unified-media/live-15/video-model-run.json` frames）。
- **建议的有界修正**：把候选类型改名为 `ShotFrameRef`（canonical 不动），或将其扩为 canonical `FrameRef` 的超集（必填 `target_seconds` + `time_basis`）；并在设计中写明逐镜头帧最终落在哪张表/哪个字段（与 M6 一并解决）。

### M4（Major）父任务没有任何可承载的 DTO：`ParentJob` 7 个必填字段中 5 个无载体，且 canonical `Job` 是 strict

- **位置/字段**：`plans/v1-multishot-contract.json` `entities.ParentJob.required = [id, planned_child_ids, selected_scene_revision_ids, total, terminal_count, deadline, status]`；`contracts/openapi.json` `components.schemas.Job`（`additionalProperties:false`，无上述字段）；`contracts/v1-multishot.schema.json` 无 `ParentJob` $def；`$defs/BatchChildrenResponse` 仅 `parent_job_id,total,children`（无 `deadline`、无 `terminal_count`、无计划顺序）；`docs/31` §公开入口演进要求"父进度terminal_count/total"。
- **触发**：前端显示父任务进度/剩余时间；父取消与 deadline 判定。
- **预期**：docs/31 承诺的父进度与父总时限在公开契约中可见且可核对。
- **实际**：`planned_child_ids / selected_scene_revision_ids / terminal_count / deadline / total` 无处安放；`BatchChildrenResponse` 也没有 `deadline`/`terminal_count`；客户端无法读到父 deadline。
- **证据**：`checks/recompute-results.json` → `C24 FAIL`（`not_in_canonical_job=["deadline","planned_child_ids","selected_scene_revision_ids","terminal_count","total"]`）、`C25 FAIL`（无 `ParentJob` DTO）、`C27 FAIL`（children 响应无 deadline）。
- **建议的有界修正**：在候选 schema 增补 `ParentJob`（或 `BatchParent`）DTO，并在 `GET /api/v1/jobs/{id}/children` 响应中给出 `deadline`、`terminal_count` 与计划顺序（ordinal）；若决定复用 canonical `Job.progress_done/progress_total`，必须在设计中逐字段写明映射，并说明 `deadline` 存放在何处（见 M5）。

### M5（Major）缺少"不可变子计划"与"子项↔镜头↔边界"绑定的存储定义，固定分母无法在存储层保证

- **位置/字段**：`plans/v1-multishot-contract.json` `storage_plan`（"reuse job/attempt; add parent-child relation subset without V2 recovery platform"）；`contracts/storage.sql` `CREATE TABLE batch_child(parent_job_id TEXT REFERENCES job(id), child_job_id TEXT REFERENCES job(id), PRIMARY KEY(parent_job_id,child_job_id))`；`contracts/v1-multishot.schema.json` `$defs/ChildSummary`（每项必填 `shot_id`、`scene_revision_id`）；`docs/31` §实体、时间与存储与"不能运行到一半缩分母"。
- **触发**：父批量创建 → 子项排队 → 部分失败/取消 → 导出清单。
- **预期**：计划子清单在父任务创建同一事务内物化并不可变，分母与顺序可查询；每个子项可回溯其 shot 与 scene revision。
- **实际**：`batch_child` 无 `ordinal`、`shot_id`、`scene_revision_id` 列；设计未声明"子项在父创建时一次性预建"。若子项是领取时才创建，分母可被运行时缩减（设计明令禁止）；`ChildSummary` 需要的 `shot_id`/`scene_revision_id` 没有声明的存储位置（`job.payload_json` 未被指定）。
- **证据**：`checks/recompute-results.json` → `C29 PASS`（确认基线 DDL 缺这些列）；`contracts/storage.sql` 原文。
- **建议的有界修正**：在迁移中明确：为 `batch_child` 增加 `ordinal INTEGER NOT NULL`、`shot_id`、`scene_revision_id`（外键），父任务创建时**单事务预建全部子项**（或写入不可变的 `batch_plan` 行），并写明 `deadline` 落在父 job 的哪一列。

### M6（Major）`AnalysisBinding` 两个关键量未定义：租约/fencing token 缺失、`scene_revision_hash` 无来源与存储

- **位置/字段**：`contracts/v1-multishot.schema.json` `$defs/AnalysisBinding`（required: `shot_id, scene_revision_id, scene_revision_hash, media_ref_id, media_sha256, config_hash, attempt_id, cancel_epoch`）；`plans/v1-multishot-contract.json` `storage_plan` "add shot.scene_revision_id with foreign key and required binding in model_run metadata"；`contracts/storage.sql` `model_run`（列：`id, attempt_id, model_tag, model_digest, raw_text, parsed_json, config_hash, input_hash, created_at`——**无 metadata / binding / scene_revision 列**）、`scene_revision`（**无 etag、无 source_sha256、无 hash 列**）；`docs/31` §实体、时间与存储"以attempt/token/cancel_epoch和scene_revision_hash进行终结CAS"；`docs/14` §R2"分配attempt_id/lease_token"。
- **触发**：终结 CAS（防止晚到结果写入）、边界变更后 stale 判定、显式采纳校验。
- **预期**：绑定对象能完整表达文档写明的 CAS 条件（attempt + token + cancel_epoch + scene_revision_hash），且 hash 有确定算法与存储列。
- **实际**：`AnalysisBinding` 无 `lease_token`（只有 `attempt_id`），文档要求的 token 条件无法由绑定表达；`scene_revision_hash` 既无算法定义也无存储列（`scene_revision` 表无该列）；绑定本身也没有声明的落库位置（"model_run metadata" 在基线 DDL 中不是列）。
- **证据**：`contracts/storage.sql` 原文与 `checks/recompute-results.json` → `C28`（基线 `scene_revision` 无 append-only 触发器、无 etag/source_sha256 列）。
- **建议的有界修正**：明确 `scene_revision_hash = sha256(规范化元组: media_sha256 | version | start_pts | end_pts | time_base_num | time_base_den | origin)` 并加列（含 `etag`）；把 `lease_token` 加入 `AnalysisBinding`（或写明由 `attempt_id` 联结 `attempt.token` 取得）；明确绑定落库列/表（例如 `model_run.binding_json` 或新建 `shot_analysis_binding` 表）。

### M7（Major）"未执行/截止失败"子项没有终态值，父 deadline 也不可观测

- **位置/字段**：`contracts/v1-multishot.schema.json` `$defs/ChildSummary.properties.status.enum = [queued, preparing, running, partial, succeeded, failed, cancelling, cancelled, interrupted, submission_unknown]`；同文件 `$defs/BatchChildrenResponse` x-semantic-invariants "total equals number of immutable planned children, including failed/cancelled/not-run placeholders"；`plans/v1-multishot-contract.json` `entities.ParentJob.invariants` "deadline checked before each send"；`docs/31` §资源、状态与故障"届满取消活动项并把剩余项明确终结为未执行/截止失败"。
- **触发**：父 deadline 届满，剩余子项未开始。
- **预期**：每个计划子项都有显式终态，且截止失败与普通失败可区分。
- **实际**：状态枚举中没有承载"未执行/截止失败"的值（可借用 `failed` + `error_code=BATCH_DEADLINE_EXCEEDED`，但设计未写明该映射）；`ChildSummary.status` 刻意复用了 canonical `Job.status` 枚举（`C26 PASS`），因此新增状态值本身需要一次显式裁决。
- **证据**：`checks/recompute-results.json` → `C26 PASS`（子集关系成立）、`C27 FAIL`（children 响应无 deadline/terminal_count）。
- **建议的有界修正**：写死映射（例如：截止未执行 = `status:"failed"` + `error_code:"BATCH_DEADLINE_EXCEEDED"`；被父取消未执行 = `status:"cancelled"`），并在 `BatchChildrenResponse` 增加 `deadline`、`terminal_count`、`not_executed_count`，让"未执行"在公开面可见而非被折叠。

### M8（Major）逐镜头证据无法满足四来源域合同（R06），也无法编译成逐镜头四目标

- **位置/字段**：`contracts/v1-multishot.schema.json` `$defs/ShotEvidence`（`characters[].visible_appearance`、`scene.description` **无 domain**；仅 `actions[].domain ∈ {observation, inference}`；`unknowns: string[]` 无域）；`contracts/lvw.schema.json` `$defs/Domains = {observation, inference, user_evidence, creative_intent, unknowns}`；`plans/requirements.json` R06「四域镜头结构」（introduced_in V1，stages R1/R2，acceptance A12+Q01）；`docs/14` §编译和目标映射"从四来源域和人工锁定字段生成目标文本"；`docs/31` §内容分析职责"domain只能observation/inference"（仅对动作提出）。
- **触发**：M1-B 产出逐镜头证据 → CompilerOwner 编译 natural/image/edit/motion 四目标。
- **预期**：机器建议进入编译器前必须可区分观察与推断；逐镜头草稿可映射为 canonical `Domains`。
- **实际**：人物与场景没有域字段，unknowns 是无域字符串；因此逐镜头证据无法填充 canonical `Domains.inference` / `Domains.observation`，四目标编译与 R06（四域镜头结构，V1 义务）无法闭合；MS04 的"证据一致性/未知/局限"两维也缺少字段级依据。
- **证据**：`contracts/v1-multishot.schema.json` `ShotEvidence` 定义；`contracts/lvw.schema.json` `Domains`；`plans/requirements.json` R06。
- **建议的有界修正**：给 `Character` 与 `scene` 增加 `domain`（或把整段 `ShotEvidence` 改为承载 canonical `Domains` 的子集），并在设计中写明 `ShotEvidence → PromptSpec/Domains → 四目标` 的映射与"人工锁定字段优先级"如何落到逐镜头。

### M9（Major）固定分母 47 段镜头无法由文档给出的 12 段样本构成推出

- **位置/字段**：`docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md:9`（"6个明显硬切片，各含5/5/5/4/4/4镜头（合计21个标注切点）；2个无切片覆盖摇镜/闪光；2个渐变/叠化片（疑似需可校订）；1个VFR四镜头；1个短/快切八镜头。合计47个计划镜头"）；`plans/acceptance_cases.json` MS01（"6段硬切样本至少20个预标切点"）、MS03（"全部计划镜头逐项覆盖"）、MS06（"JSON/CSV清单含每个计划项状态"）。
- **触发**：Gate0 前冻结独立标注目录与分母。
- **预期**：固定分母可由冻结样本清单**复算**（设计禁止"减少镜头数、遗漏难镜头或替换样本改变分母"）。
- **实际**：按文中枚举，硬切组 5+5+5+4+4+4=27 段，加无切片 2 段、VFR 4 段、快切 8 段共 41 段，两段渐变/叠化片文中未给镜头数，取 1 段/片得 43 段，取 2 段/片得 45 段，**只有每片恰好 3 段时才是 47**——文中未写。故 47 不可复算，标注者冻结样本时必然要自行补一个未声明假设。
- **证据**：`checks/recompute-results.json` → `C30 FAIL`（`total=43..47 stated=47`）；`C31 PASS`（文中确有"47个计划镜头"与"21个标注切点"字样）；`C32 PASS`（MS01 的"≥20 切点、±2 源帧、P/R≥0.90"与 docs/06 中 V2 A13 阈值一致，未降低 V2 门槛）。
- **建议的有界修正**：发布 12 行样本表（clip id / 类别 / 镜头数 / 切点数 / 每段动作画像 / 是否进入 18 段质量子集），据此重算 47 与 21，并在表中直接写明 18 段质量子集归属（对应 m4）。

### M10（Major）父任务 1800s 总时限覆盖不了它自己的 12 个子项，与"不得截断分母"直接冲突

- **位置/字段**：`docs/31:77`（"每个子分析仍总限420s…父视频任务总deadline1800s…届满取消活动项并把剩余项明确终结为未执行/截止失败"）；`docs/32:34`（"父任务最多12子项，单次分析420s，父总1800s"）与"不能截断分母"；`docs/24` §R09/A09 实测包线"nearest-rank P95≤180/300s"（热图 / 热四帧视频）。
- **触发**：对计划 8 镜头样本与 12 镜头样本执行父批量。
- **预期**：父任务的运行预算足以覆盖它自己被验收的固定分母；否则必须写明哪些样本不适用该父批量。
- **实际**：12 子项 × 420s = 5040s > 1800s；按实测视频 P95 300s，8 镜头样本约需 2400s、47 镜头样本集约需 14100s，均超出 1800s。设计的补救方式（把剩余项终结为未执行）恰好使这些样本**永久不可评分**，即 MS01/MS03/MS04 在分母强制的前提下无法 PASS。
- **证据**：`checks/recompute-results.json` → `C36 FAIL`（`12 children x 420 s = 5040 s vs parent deadline 1800 s; 8-shot sample at measured P95 = 2400 s`）；`docs/24` A09 行。
- **建议的有界修正**：由 Codex 修正数值而非由实现者猜测，三选一并写死：(a) 父 deadline 随计划子项数与实测每镜头 p95 缩放（n × p95 + 清理余量）；(b) 降低每镜头预算或减少单视频镜头上限；(c) 固定样本按镜头数分组为多个计划父批量，并把 8/12 镜头样本单列。同步写明"deadline 截断 = 该样本 NOT_RUN"，不得记 PASS。

### M11（Major）每完整轮预算估计低于本项目自己的实测时延包线

- **位置/字段**：`docs/32:34`（"设计估计47镜头+原18质量+UI/故障<=80次模型/10800秒一个完整轮"）；`plans/execution-control.json` → `reports/unified-media/complete03-budget-after-live15.json`（已用 29/1024 动作、8/24 有效完整轮、1506/172800 秒）；`docs/24` A09（P95≤180s 图 / ≤300s 四帧视频）；`reports/authorization-program-v1-complete-03.request.json`（每子运行上限 128 动作 / 21600 秒）。
- **触发**：Gate0 冻结一个完整 V1 checkpoint 的预算。
- **预期**：估计值与实测每调用时延相容，或明写实测依据与超出后的处置。
- **实际**：10800s/80 次隐含**每次 135s** 的均值，低于实测四帧视频 P95 300s；仅 47 次逐镜头分析按 P95 即约 14100s（`C35 FAIL`）。该估计仍低于 COMPLETE03 单子运行上限（128 动作 / 21600s，`C33 PASS`），但全局余额按 80 动作/轮只剩约 12 轮可做（余 995 动作 / 16 轮），而轮内还包含 UI/故障重试。
- **证据**：`checks/recompute-results.json` → `C35 FAIL`、`C33 PASS`、`C34 PASS`（余额明细见 detail）。
- **建议的有界修正**：以实测每镜头时延重估（65 次调用 × p95 + 清理余量），写明每完整 checkpoint 的动作数/墙钟/占全局比例与"还能做几轮"，并规定余额耗尽时走 WAIT_BUDGET 而非降低分母。

---

## 4. Minor findings

| ID | 位置 | 问题 | 建议修正 |
|---|---|---|---|
| m1 | `docs/17_DATA_AND_VERSIONING.md:5`（"V2：asset_link、scene_revision、recipe_revision、batch、FTS、backup_manifest"）、`docs/20_RELIABILITY_AND_OPERATIONS.md` §状态机（"V1持久attempt+cancel_epoch；V2lease/fencing+batch"） | 2026-11-11 的 R22 提前已把 `scene_revision` 最小子集与父子 batch/lease 子集提升到 V1-M1，但 docs/03/06/08/14/15 都加了修订脚注而这两份没有，实施者读 docs/17/docs/20 会得出"scene/batch/lease 属 V2"的相反结论 | 与其他文档一致地补一条 2026-11-11 覆盖说明（V1-M1 提升的是最小子集，完整 R13/A13/X04 仍属 V2） |
| m2 | `docs/29`（"11段保留给当前人工验收的视频不能静默转作本功能开发集"）、`docs/32`（"既有11个人工留样不得静默用来调优"） | 措辞只禁止"静默"复用；这 11 段正是 621b1bf 切片待人签的体验素材，一旦被用于多镜头开发/调优，会污染全计划正在等待的前置人签 | 改为绝对禁止："MS 样本集、独立标注集与 11 段人工留样三者互斥" |
| m3 | `docs/32` §固定验收与独立样本 | 只声明与 11 段留样分离，未声明与 Q01 现有 12 图+6 片质量集互斥；跨义务复用同一视频会同时影响两个固定分母 | 明确 12 段新视频与 Q01 的 6 段视频互斥 |
| m4 | `docs/32:9`（"18段内容质量子集在这47段内预选，不能结果出来后挑"） | 只规定"预选"，未给选择规则/归属，事后挑选风险仍在 | 在 M9 的 12 行样本表中直接写明 18 段归属（12 简单动作 / 3 含糊 / 3 静态） |
| m5 | `plans/execution-control.json` `updated_at = "2026-11-09"` | 同一记录已含 2026-11-11 的 `approved_v1_multishot_change` 与 `development_outline` 的 V1-M1 条目，坐标时间戳滞后 | 下次写坐标时同步刷新 `updated_at` |
| m6 | 候选 `origin[detected\|human]` vs canonical `editor[algorithm\|human]` | 词表不一致，overlay 未给映射 | 在 overlay 中写明双向映射（与 M1 一并修） |
| m7 | 候选 `BatchAnalyzeRequest.mode` 为 6 值闭集枚举，而 canonical `AnalyzeRequest.mode` 是自由字符串 | 新 DTO 比 canonical 更严；现有前端若允许其它 mode 值会在新路由上被拒 | 明确该路由只接受 6 个规范模式，或对齐 canonical 的自由字符串语义 |
| m8 | `docs/31` §资源、状态与故障（"候选检测需流式有界解码，不缓存全片tensor"） | 未说明逐镜头抽帧是"每镜头一次独立解码"还是"一次有界解码同时记录 frame→PTS"；两者在同一父 deadline 下的 CPU 墙钟差异显著 | 在 M1-A 设计中写明解码策略（建议单次有界解码 + PTS 索引，再按镜头取帧） |
| m9 | `plans/v1-multishot-contract.json` `new_error_candidates` 与 `http_rules` | 把请求级错误码（`SHOT_LIMIT_EXCEEDED`、`ANALYSIS_STALE`）与运行终态错误码（`BATCH_DEADLINE_EXCEEDED`）混列 | 拆成"HTTP 响应码"与"job/child 终态 error_code"两张表，Gate0 固定 HTTP 映射 |
| m10 | `plans/v1-multishot-contract.json` `storage_plan`（"add shot.scene_revision_id with foreign key and required binding"） | 存量 `shot` 行（纯图、无 media_ref_id）的迁移策略与"required binding"含义不明（可空+回填，还是分表） | 写明可空/回填策略或改用独立关联表 |

---

## 5. 已核对且一致的项目（逐项附证据，非"全部通过"泛化）

1. **批准范围 vs 完整 R13/V2 保留**：`plans/requirements.json` R13 仍 `introduced_in V2 / stages R3 / acceptance A13,X04`；R22 为 `introduced_in V1 / stages V1-M1,R2`；`docs/15` 与 `docs/14` 的 2026-11-11 覆盖段落明确"R22 子集提前，完整 R13/长片/资产/FTS/MCP 仍 V2"。✅
2. **固定分母 29/38/47 且为加法**：三道门禁分别 29/38/47；原 21/30/39 作为**未改前缀**完整保留、MS01–08 各出现一次（`C2,C3,C4`）；`plans/v1-revised-plan.json` 的 `v1_required_cases` 与 release_gates V1 顺序完全一致（`C5`）。✅
3. **原 Q01 未被改动**：preconditions "12图+6片"、assertions "图>=10/12、片>=5/6" 原样保留，且 R1/R2 的 `work_on_cases` 仍含 Q01（`C8`）。✅
4. **依赖无环**：tasks.json 依赖图无环且与 `preferred_sequence` 一致（`C9,C10`）；v1-revised-plan 的 R1→V1-M1→R2 无环且与 tasks.json 一致（`C11,C12,C13`）。✅
5. **canonical 合同字节未变**：`contracts/openapi.json`、`contracts/lvw.schema.json`、`contracts/storage.sql` 与 `legacy-gates-before-change.json` 记录哈希一致（`C14`）；旧 R1 packet manifest 哈希也在围栏内一致。✅
6. **COMPLETE03 记账**：`authority_stage=R2` 确在 COMPLETE03 已授权 stage 列表（`R0,R1a,V0-S2,V0-S3,R1,R2`）内，`design_stage=V1-M1` 为显示名映射，无任何 V2/R3/R4 别名；`budget_reset=false`；`old_slice_human_signoff_waived=false`（`C15,C16`）。✅
7. **现有人签未被冒充**：`execution-control.human_signoff=null`、`product_acceptance=null`、`active_slice.human_signoff=null`、`V1_ACCEPTED` 仍在 `forbidden_claims`；`development_outline` 中 V1-M1 为 0/3、machine_acceptance=NOT_RUN、human_signoff=NOT_SIGNED（`C37`）。D0 stage-control 亦 `product_execution_authorized=false`、`stage_pass_forbidden=true`（`C38`）。✅
8. **"1.8 仅外观"判断属实**：`reports/unified-media/live-15/video-model-run.json` 显示 `template_id=lvw-video-frame-appearance`、`template_version=1.8.0`，raw 响应键仅 `frame_appearances/prompt_zh/prompt/negative/tags/unknowns`，`subject_action="Continuous subject action unverified"`（`C40`）。docs/31/29 关于"动作需新模板与新响应 Schema、CPU 像素差不能充当动作识别"的要求与事实一致。✅
9. **新子项路由不污染 strict `Job`**：canonical 只有 `PUT /api/v1/scenes/{id}`、无 `GET /api/v1/jobs/{id}/children`；设计明确 `GET /jobs/{id}` 仍返回原 Job 且新增受控 children 路由（`C23`；M1 中 GET 增量除外）。✅
10. **11 段人工留样未被占用**：`execution-control.human_validation_holdout` = 11 段、`formal_quality_set=false`；`人工验收视频集/videos` 实为 11 个文件。✅
11. **JSON Schema 边界表述诚实**：候选 Schema 通过 draft 2020-12 metaschema；`docs/31` 明确"跨字段/跨引用语义在 x-semantic-invariants 列准…不冒充 JSON Schema 单独能验证"。实测确认：`end_pts>start_pts`、等长 id 数组、跨镜头 actor 引用、重复帧哈希、`total==len(children)`、deadline 均**不可**由 schema 校验，只能由 owner 代码校验（`checks/metaschema-check.log`）。✅（这也是 M8/M7 必须在 owner 侧写死规则的原因）
12. **基线 DDL 已有的强约束**：`scene_revision` 表有 `CHECK(end_pts>start_pts)` 与 `tb_num/tb_den>0`（`tools/verify_pack.py` 已覆盖该负例），V0 的 `prompt_revision` 有 `IMMUTABLE_REVISION` 触发器——M6 指出的是 `scene_revision` **缺**同类 append-only 触发器，而非全无约束。✅

---

## 6. 预期未来前置（属正常待办，**不是**本次发现的矛盾）

1. 12 段非私有新视频的取得、license、source/hash、PTS、切点与独立标注的冻结；目录结构与"标注先于模型运行"的执行顺序（docs/32 已声明尚未完成，未伪装已有 47 段真实输入）。✅ 属 Gate0 前置。
2. 新的动作响应 Schema/提示模板与真实模型质量验证（1.8 确无此能力）。属 M1-B 交付物。
3. V1 产品实现（R1/M1/R2）、集中 checkpoint、隔离独审与真实人签；D0 审查不替代任何一项。
4. 现有 621b1bf 切片体验签署、V0-S2/S3 原始义务、COMPLETE03 余额与本机 GPU 可用性（当前资源等待记录显示多次 `free<19047MiB`）。
5. Gate0 对具体 HTTP 映射、阈值、样本表与 overlay 的正式冻结——本审查明确不预判这些阈值，只指出它们当前互相矛盾或不可复算。

---

## 7. 结论

```text
Fatal: 1   (F1: /api/v1/jobs/batch 请求合同冲突——需合同 owner 裁决后再冻结)
Major: 11  (M1–M11)
Minor: 10  (m1–m10)
Recommended gate status: NOT_GO_FOR_DESIGN_CONSOLIDATION_ONLY
                           —— 允许继续 D0 文档/工具准备，不允许产品合同冻结与 R1/M1 产品实现启动
Limitations: 本次为 DESIGN_REVIEW。未取得样本哈希、未产生模型输出证据、未运行任何产品/媒体/服务链、
             未收到也未审查 D0 checker 候选；canonical OpenAPI overlay 的合法性与生效方式由门禁 owner 裁定，
             本审查只指出同一路由上候选 DTO 与 canonical DTO 的字段互斥事实。
             本审查不构成产品 Gate0、Stage PASS、产品 PASS 或人工签署；当前产品坐标仍为 R1/WP-R1-U3/WAIT_HUMAN。
```

若 F1 与 M1–M11 由 Codex 裁决并落盘修订（且不降低任何固定分母/阈值），本窗口可按同一只读口径复算一次；本窗口不自行修改任何合同或计划。
