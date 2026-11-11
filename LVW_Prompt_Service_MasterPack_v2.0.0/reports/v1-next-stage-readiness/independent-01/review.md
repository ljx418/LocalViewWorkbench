# 独立下一阶段依赖与复用审计（UNIFIED_MEDIA_EARLY 人签之后）

- 角色：ClaudeCode 独立规划审查员（Orca 可见隔离工作区 `lvw-v1-d0-review`）。
- 状态：**审计结论 + 门禁裁决建议**。本文件不是 Stage PASS、不是产品 Gate0、不是人工签署、不是任何产品批准。
- 只读产物；唯一写入目录 `reports/v1-next-stage-readiness/independent-01/`。
- 权威来源：`c448ec657c01708270c83291806a3dccc9fe6090`（已普通推送，`refs/remotes/origin/main` 指向同一 SHA），以 `git merge --no-edit` 干净并入本隔离检出（merge commit `d9a149d`）。
- 结论一句话：**剩余 V1 的关键路径上只有一个未关闭的人类义务——原 S2 范围判定；2026-11-11 的前端人签没有、也不能被当作旧 S2 的人签；在该判定作出前，任何产品 Stage/Workpack 都不能合法开工。**

---

## 0. 审计边界（已自证）

| 允许 | 实际执行 |
|---|---|
| 仓库只读检视 | 已做（git 树/文件/收据/文档） |
| 原始收据与哈希复算 | 已做（tree SHA、fixture SHA、input SHA、acceptance hash） |
| 静态检查 | 已做（`git diff --stat`、`git rev-parse`、`find`/`sha256sum` 栅栏） |
| 服务/GPU/模型/媒体/FFmpeg/网络/浏览器/productDB/推送 | **未做，0 次** |
| 写入 | 仅 `reports/v1-next-stage-readiness/independent-01/` |

源栅栏（before/after 见 `receipt.json`）：`AGENTS.md`、`docs/`、`plans/`、`contracts/`、`lvw/`、`LVW_V0_RuntimePatch/`、`.agent-governance/`、`tools/`、`launcher/`、`templates/`、`config/`、三个根 HTML 与 `人工验收视频集/` 的目录哈希在审计前后完全一致（见 `receipt.json` 的 `source_fence_before/after`，逐项相同）。

---

## 1. 这次人签到底放行了什么（要求1）

### 1.1 签署记录原文绑定

`reports/unified-media/human-signoff-live15.json`：

- `product_candidate` = `621b1bf386db71bfe08ca2f533fa8ec396b0504b`
- `scope` = "Current minimal unified image/video frontend slice only; current frontend experience and basic video reverse prompting"
- `statement` = "当前前端页面、基本的视频反推 我人工确认OK"
- `explicitly_not_approved` = `["historical V0-S2 candidate or V0.1", "V0.2", "complete R1", "complete V1", "multi-shot implementation or acceptance", "production release"]`
- `not_claimed_human_test_coverage` = 明确禁止推断用户亲自执行了每个 UM 用例、服务故障场景、全部 11 段留样、正式质量集或未来多镜头流程。

`reports/unified-media/accepted-slice-live15.json`：`old_S2_signed: false`、`full_R1_pass: false`、`full_V1_pass: false`、`release_approved: false`。

### 1.2 放行/未放行清单（逐项）

| 项 | 状态 | 依据 |
|---|---|---|
| R1 / WP-R1-U3 阶段门（UM10 机器 10/10 + 独审 Fatal0/Major0 + 人签） | **已放行（本切片范围）** | `plans/execution-control.json:14-24`、`last_passed_gate` |
| 统一切片状态 → `SLICE_ACCEPTED_NEXT_STAGE_PREPARATION` | **已放行** | `plans/execution-control.json:8-13` |
| 历史 R1a 单图切片签署 | 保持有效，未被改写 | `accepted_r1a_history`（`df4943ce…`） |
| 历史 V0-Min 签署 | 保持有效，未被改写 | `last_accepted_product`（`reports/v0-s1/v0-min-acceptance.json`） |
| 旧 S2 / V0.1 人签 | **仍未关闭** | `execution-control.development_outline[V0-S2]` 第 8 子步 `PENDING`，`human_signoff: PENDING` |
| V0.2 (S3)、完整 R1、完整 V1、多镜头、发布 | **仍未关闭** | `explicitly_not_approved`；`forbidden_claims` |
| 11 段人工留样 | **仍 NOT_RUN** | `execution-control.human_validation_holdout.lvw_status = ALL_NOT_RUN`；人签请求第 5 条为"可自选" |
| V0-A12 / Q01 质量门 | **未豁免** | `stage-control.json.future_raw_quality_gates_not_waived: ["V0-A12","Q01"]` |

### 1.3 候选产品文件 vs 当前源（无运行，复算树哈希）

```
git rev-parse 621b1bf:lvw                     -> 7e380008c9760e35d66afc51f6d823ba3c116b46
git rev-parse HEAD(merge c448ec6):lvw         -> 7e380008c9760e35d66afc51f6d823ba3c116b46   （相同）
git rev-parse 621b1bf:LVW_V0_RuntimePatch     -> 5163244ce45f63f5c7a6f1ab61666a8dd026a247
git rev-parse HEAD:LVW_V0_RuntimePatch        -> 5163244ce45f63f5c7a6f1ab61666a8dd026a247   （相同）
git diff --stat 621b1bf HEAD -- lvw/            -> 空
git diff --stat 621b1bf HEAD -- LVW_V0_RuntimePatch/ -> 空
```

- 结论：**人签候选的产品字节 == 当前 HEAD 的产品字节**。D0 之后新增的全部是 `docs/ plans/ contracts/ reports/ .agent-governance/`（+3224/-96 行，仅文档与合同候选），未动产品源码。
- 因此：(a) 已被接受的切片无需重新验证；(b) S2 的 Comfy 原生实现自 `719c745` 起**逐字节未变**，仍完整在树内，可直接复用审计，不需要重做。
- 附带：`git diff --stat 719c745 HEAD -- LVW_V0_RuntimePatch/` 为空，而 `lvw/` 增加了 U1/U2/U3 的 FastAPI 视频链路（`lvw/backend/app/video_kernel.py`、`video_appearance.py`、`video_temporal.py` 及对应测试）。

---

## 2. S2→S3→R1：三种"门"必须分开看（要求2）

### 2.1 三种门的精确定义（来自实际源，不是假设）

| 门 | 定义位置 | 现状 |
|---|---|---|
| **历史 V0 发布签名** | `plans/release_gates.json` → `V0.1.required_cases` = 9 项全部 `all_must_pass`；`V0.2` = 12 项 | V0.1 的 9 项机器已在 `719c745` 9/9 PASS；**V0.1 未发布**（`allowed_claim = V0_MIN_ACCEPTED_NOT_RELEASED`） |
| **能力/依赖门（Stage 序）** | `plans/tasks.json`：`V0-S3.depends_on=["V0-S2"]`、`R1.depends_on=["R1a","V0-S3"]`、`V1-M1.depends_on=["R1"]`、`R2.depends_on=["R1","V1-M1"]` | `V0-S2` **未完成（7/8）** |
| **已批准的统一前端人签入口** | `docs/27`（APPROVED 2026-11-08）："不要求用户为了'过门'先学习Comfy"、"保留当前S2 7/8及旧机器/独审事实"、"不伪造S2人工签署"；`docs/23` 2026-11-08 追记："旧S2仍7/8未人工签署"、"Comfy界面不再是本次人类必须使用的验收入口" | 已用于统一切片，**未用于旧 S2** |

### 2.2 关键结论：现有已批准文档**不能**合法地满足 S2→S3 依赖，且**不应**回溯签署旧 S2

不能回溯签署旧 S2 的五条独立理由（任一条即足够）：

1. **候选不同**。旧 S2 人签请求绑定 `719c74559393a6489b2f630a1e0d3bc3303eb655`；本次人签绑定 `621b1bf…`。
2. **对象不同**。`reports/v0-s2/full-v0-auto-08/human-signoff-request.md` 明确要求："先双击项目根目录'人工验收指南.html'…启动图片工作台与**临时Comfy视频流程**…当前V0视频在Comfy原生工作流中；**独立视频前端属于后续计划**"。本次人签对象是 React/FastAPI 统一前端（`launcher/README.md`："无需打开 ComfyUI 或导入节点图"）。二者是不同交付物的不同交互面。
3. **签署记录自我排除**。`human-signoff-live15.json.explicitly_not_approved` 首项即 "historical V0-S2 candidate or V0.1"。
4. **治理规则禁止**。`AGENTS.md` 第 23 条："不将此次签署扩大到旧S2/V0.2/完整R1/V1/发布…旧范围若仍缺必要人签须明确区分"。
5. **计划文件否认豁免**。`plans/v1-revised-plan.json`：`"old_slice_human_signoff_waived": false`。

同样，**也不能反过来断言"旧 S2 已因机器 9/9 + 独审 Fatal0 而实质完成"**：

- `.agent-governance/stage-gates.md`："独立出门：隔离复算，Fatal=0、Major=0、固定分母完整、**必要人类签署存在**"。
- `reports/v0-s2/full-v0-auto-08/gate-decision.md` 末句："**不进入S3业务实现**、不代签、不将机器通过称为版本完成"。
- `execution-control.development_outline[V0-S2].summary` 仍为 "human signoff and immediate Git sync remain"。

### 2.3 已经合法发生的部分（不重复请求）

`docs/27` 批准的路线**确实**把"人类必须操作的验收载体"从 Comfy 节点图移到了统一前端；这正是本次人签的合法依据，也正是 `AGENTS.md` 第 23 条禁止再向用户重复索取同一前端人签的原因。**本审计不请求再次前端人签。**

### 2.4 剩下的那个真正的缺口：原 S2 范围判定（docs/30 列明的既有前置）

`docs/30_V1_REVISED_EXECUTION_PLAN.md` 的"既有前置 S2/S3"行写明准入条件为："现有统一切片实际体验签署，**原 S2 范围判定**；S3增量包/安装回滚/独立质量/十二项"。并同时声明"保留V0-S2/S3原义务及其前置门槛"。

- "现有统一切片实际体验签署" = 已完成（本次人签）。
- "**原 S2 范围判定**" = **在任何源文件中都不存在**。`docs/23`、`docs/27`、`docs/30`、`docs/31`、`docs/32`、`.agent-governance/stages/*`、全部 `reports/v0-s2/*` 均无该项判定记录。

因此这不是"再签一次旧 S2"的问题，而是**一次尚未作出的范围/门禁绑定判定**：V0-S2 的人类体验义务应当绑定到哪个交付物上。这个判定属于门禁裁决权（`AGENTS.md` 第 11 条：Codex 负责 Stage 门禁）与人类签署权（人类负责最终体验签署），**审查员无权自行作出**。本审计给出 DRAFT 变更请求提案（第 3 节 + 附件文件），零产品权限随之生效。

### 2.5 反方论点与其处置（不留未反驳的强论据）

**反方 A（最强）**："V1 产品（FastAPI/React）**完全不依赖** Comfy（`AGENTS.md` 第 4 条、docs/23、docs/27）。要求用户先签一个 Comfy 原生 V0 交付物，才允许写一行 V1 产品代码，是把整个 V1 锁死在一个 V0 Comfy 工件上；这与 docs/27 批准统一前端的初衷矛盾。"

处置：**反方 A 成立的部分与不成立的部分必须分开。**

- 成立：把"用户必须学会 Comfy"当作 V1 的前置**确实**是已被 docs/27 批准要去掉的负担。
- 不成立：docs/27 批准的是**验收入口**的迁移，不是**义务顺序**的取消。docs/27 自己写着"保留当前S2 7/8及旧机器/独审事实""不伪造S2人工签署"；docs/30 写着"保留V0-S2/S3原义务**及其前置门槛**"；docs/23 写着"V0.1 视频、V0.2 安装回滚与完整质量**没有取消**，只在执行顺序上后移"。
- 结论：反方 A 正确地指出了**需要一次判定**，而不是授权审查员绕过判定。判定选项见第 3 节 DRAFT 提案（Option A/B/C），由 Codex 裁决 + 用户签署。

**反方 B**："`LVW_V0_RuntimePatch/` 自 `719c745` 逐字节未变，S2 的 9 项机器证据对当前产品仍然成立，重复签同一份未变代码没有增量价值。"

处置：机器证据的**可复用性**成立（`stage-gates.md`："旧证据仅在冻结复用规则证明不受影响时复用"），本审计在复用矩阵中据此把 S2 机器 9/9 记为**可复用（COMPLETE）**。但"机器证据可复用"与"人类体验义务已履行"是两件事——人类体验的对象是 Comfy 原生交互（节点图、显式采纳、取消、离线人工稿），该交互面**至今未被任何人类确认过**，且当前产品前端不提供该交互面。**不可复用的是人类结论，不是机器结论。**

**反方 C**："统一前端已经人签了'基本视频反推'，功能上覆盖了 S2 的视频体验。"

处置：**不成立**。除 2.2 的五条理由外，还有一条可复算的硬事实（见 3.2 IND-03）：本次人签所依据的视频输入是 S2 自己的**合成结构夹具**，因此"基本视频反推 OK"在**功能/链路**上成立，在**内容质量**上是零证据；而 S2 的人签义务里明确包含"范围判断"，且 S2 机器覆盖的是 Comfy 原生链路。

---

## 3. 下一步真正允许做什么（要求3）

### 3.1 裁决：当前**没有任何**可执行的产品 Stage/Workpack

| 候选 | 前置 | 可否开工 | 依据 |
|---|---|---|---|
| V0-S3 | V0-S2 完成（7/8） | **否** | `tasks.json.depends_on`；`full-v0-auto-08/gate-decision.md`"不进入S3业务实现" |
| R1（完整） | R1a ✓ + **V0-S3** | **否** | `tasks.json` |
| V1-M1 | R1 | **否** | `tasks.json` |
| R2 | R1 + V1-M1 | **否** | `tasks.json` |
| V1-D0 | — | **已关闭** | `reports/v1-redesign/d0-acceptance/decision.json`：`D0_PREPARATION_ACCEPTED_WITH_NONBLOCKING_MINORS`，且 `product_gate0:false`、`product_pass:false` |

### 3.2 唯一必要的下一动作 + 缺失的人类/产品决定

**下一动作（由 Codex/门禁责任人执行，不由本审查员执行）**：

> **作出"原 S2 范围判定"**（`docs/30` 既有前置，当前缺失），并由用户对该判定文本签署。

同时可并行（无冲突、零运行时、零产品权限）：本审计给出的 DRAFT 变更请求 + S3 Gate0 草案包（第 5 节 + 附件）。

**缺失的人类决定**（三选一，均需用户签署）：

| 选项 | 内容 | 需要谁 | 代价 / 风险 |
|---|---|---|---|
| **A（建议）** | 把 V0-S2 的**人类体验/范围义务**在"视频能力子集"上重新绑定到已签署的统一前端 `621b1bf`，同时逐条写明"未被人确认的部分"（Comfy 节点图交互）与"仍必须新做的部分"（V0-A11/A12 独立质量集、V0-A06 安装回滚、V0.2 十二项），**不产生 V0.1/V0.2 通过或发布结论** | Codex 判定 + 用户签署 | 需要一份新的范围判定记录（不得改写旧证据） |
| B | 用户按 `reports/v0-s2/full-v0-auto-08/human-signoff-request.md` 实际体验 Comfy 原生流程，签署 `719c745` | 用户 | 与 docs/27 "不要求用户先学 Comfy" 的批准意图相悖；无新增产品代码成本 |
| C（**不建议**） | 直接以统一切片人签视作旧 S2 已签 | — | **违反 AGENTS 23、`explicitly_not_approved`、`old_slice_human_signoff_waived:false`；本审计不推荐、也不会据此推进** |

**缺失的产品决定（不阻塞当前判定，但必须在 R1-CORE Gate0 前关闭）**：质量集素材来源与授权。S3 的 10 图/6 视频、V1 的 Q01 12 图/6 视频、MS 的 12 片/47 镜头**目前都不存在实体素材**（见第 4 节）。`AUTH-PROGRAM-V1-COMPLETE-03` 允许"构建期必要官方依赖下载≤2GiB/0付费"，**不包含媒体素材获取**；因此需要用户/产品责任人提供或明确授权素材来源与权利记录。

### 3.3 DRAFT 变更请求提案（不修改任何权威文件）

完整提案见同目录 `draft-change-request-s2-scope-determination.md` / `.json`。摘要：

- 提案编号（拟）：`CHANGE-V0-S2-HUMAN-BINDING-01`（**DRAFT，未生效**）
- 最小受影响 ID：`plans/tasks.json` 中 `V0-S2` 的**完成度/状态字段**（**不改 `depends_on` 关系**）；`plans/execution-control.json` 的 `development_outline[V0-S2]` 第 8 子步与其 `human_signoff` 字段；新增 `reports/v0-s2/scope-determination-01.{md,json}`（**新增文件，不改写任何旧证据**）。
- **不改**：`plans/acceptance_cases.json`（12 项 V0 分母、MS 阈值不动）、`plans/release_gates.json`（V0.1/V0.2/V1/V2/V3 全部门禁不动）、`contracts/`、`docs/`（除新增追记）、S2 已有收据与历史失败。
- 保留的义务：V0.2 累计 V0-A01..A12 全部通过；V0-A11(10 图≥8 可用、幻觉 0)、V0-A12(6 片≥5 可用、幻觉 0) 必须在 S3 候选上**新跑**；V1 29 项分母、Q01(12 图≥10/12、6 片≥5/6)、MS01–MS08 阈值全部不动；11 段留样保持 NOT_RUN；COMPLETE03 全局预算不清零；**不产生 V0.1/V0.2/V1 通过或发布结论**。
- 生效条件：Codex 裁决 + 用户签署 + 记录进 `plans/execution-control.json`；**在此之前零产品权限**。

---

## 4. 复用矩阵（要求4）

> 规则：`文件存在 ≠ 运行通过`。下表只使用原始收据、哈希与源码引用；本审计不重算模型分数、不生成样本、不跑任何运行。

### 4.1 矩阵

| # | 能力 | 原生/既有证据 | 当前 FastAPI/新方案 | 现状 | 证据位置 |
|---|---|---|---|---|---|
| R1 | **视频解码/PTS/路径限制/资源释放核** | S2 `719c745` `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/{core,video_decoder,video_input,video_process}`（FFmpeg/ffprobe CLI，CPU 有界） | **当前 FastAPI 直接复用同一份源码**：`lvw/backend/app/video_kernel.py` 用合成包 `lvw_cpu_video_kernel` 载入 `core/video_decoder/video_input/video_process`，docstring 明示不加载 `__init__/PromptServer/folder_paths/torch` | **COMPLETE（源码级）** | `lvw/backend/app/video_kernel.py:1-30`；`LVW_V0_RuntimePatch/.../video_decoder.py:1-40` |
| R2 | **视频真实链路证据（结构面）** | S2 `full-v0-auto-08`：`V0-A02 PASS`，public15/browser9/cancel2/fault4/cumulative5/warm20，九项 9/9 | 统一切片 `live15`：`UM-03 PASS`（4 个真实 `decoded_pts` 12288/36864/61440/86016 + 源哈希），`UM-08` provider3/lease3、GPU峰22146MiB、RAM最低9333MiB、`no_cloud_witness` | **COMPLETE（结构面）** | `reports/v0-s2/full-v0-auto-08/receipt.json`；`reports/unified-media/live-15/receipt.json` |
| R3 | **统一前端/显式采纳/导出/取消/模型离线人工稿** | 无（S2 走 Comfy 原生） | `UM-01/02/05/06/07/09/10` 全 PASS（7 个真实公开拒绝码、3 个真实取消阶段、采纳后导出保源、停模型后仍可人工+TXT/JSON、同一 React 页面 + Windows START_LVW 零 Comfy 启动） | **COMPLETE** | `reports/unified-media/live-15/receipt.json`；`reports/unified-media/independent-live-15/receipt.json`（10/10，Fatal0/Major0） |
| R4 | **S3 增量包：README_V0 / diagnose / install / rollback / manifests** | **不存在**：`LVW_V0_RuntimePatch/` 下无 `README_V0.md`、无 `scripts/`，`manifests/` 仅 `s1-baseline-bindings.json`（无 `versions/node-bindings/licenses/sha256`） | `contracts/package-manifest.schema.json` 存在（可复用为产出契约）；`launcher/build.ps1`、`START_LVW.cmd`、`LVW.exe` 属 **V1 便携启动**，非 V0 扩展安装/回滚（docs/30 明确二者不同） | **MISSING** | `docs/13_V0_IMPLEMENTATION.md` "目标交付目录"块；目录实检 |
| R5 | **S3 V0-A06 断网增量迁移** | 无实现、无证据 | 无 | **MISSING** | 同上 |
| R6 | **S3 质量集 10 图 / 6 视频 + 独立预标注** | 仅有**结构夹具** 4 件（`static.mp4` `7b849279…`、`tracking.mov` `b08ea8b0…`、`fast-cut.mp4` `40a33fd9…`、`vfr.mp4` `08f72af8…`），`execution-control.fixture_preparation_limitation` 明示"Neither set proves native public workflow or **quality**"；2/2 准备槽已用尽 | 无 | **MISSING** | `reports/v0-s2/frozen-structural-inputs-02.json`；`execution-control.fixture_preparation_limitation` |
| R7 | **V1 Q01 12 图 / 6 视频 + 六模式覆盖** | 无 | 无 | **MISSING** | `plans/acceptance_cases.json` Q01；`config/experience-gates.json`（`v1_image_samples_min:12`、`v1_image_usable_min:10`、`video_samples_min:6`、`video_usable_min:5`、`critical_hallucinations_max:0`） |
| R8 | **MS 12 片 / 47 镜头 / 21 硬切标注 / 18 质量段** | 无实体 | 仅**设计分配**：`plans/v1-multishot-sample-design.json` `status = DESIGN_ALLOCATION_ONLY_NOT_REAL_FIXTURES`，12 条 clip 全部 `NOT_MATERIALIZED_NOT_FROZEN`，`source_sha256/annotation_hash/rights_record/source_path` 全为 `null` | **MISSING** | 同上；阈值见 `docs/32`（MS01 P/R≥0.90 ±2 源帧；MS04 ≥10/12 简单动作、总≥15/18、五维各 0–2 且总≥8、幻觉 0；MS07 镜头 12/13 exact-one-over、GPU<23552MiB、RAM≥2048MiB、OOM 0） |
| R9 | **11 段人工留样** | 存在且冻结（`人工验收视频集/FREEZE.json`，11 条 SHA） | `lvw_status = ALL_NOT_RUN`；人签请求第 5 条为"可自选"，人签记录禁止推断用户跑过 | **PRESENT / NOT_RUN / 受保护** | `execution-control.human_validation_holdout`；`human-signoff-live15.json.not_claimed_human_test_coverage` |
| R10 | **S2 原生 Comfy 实现是否仍可复用** | `git diff 719c745 HEAD -- LVW_V0_RuntimePatch/` **为空** | 逐字节保留 | **COMPLETE** | 本审计 tree hash 复算 |

### 4.2 样本独立性——一条必须写进记录的实测事实

本次人签所依据的运行证据 **live15** 的媒体输入为：

| 输入 | 路径 | SHA256 |
|---|---|---|
| 视频 | `reports/v0-s2/fixture-preparation-02/fixtures/tracking.mov`（**S2 自己的合成结构夹具**） | `b08ea8b0b9fa3bcd4e62b2b0ad1c05b2bff09359539933f4581a5c2f2c69ff6d` |
| 图片 | `reports/unified-media/dev-image.png`（项目开发图） | `b0303b157ecb6e9f07ae83c460813a743ad4f18e9be83b92abd6ecf4c919e817` |

来源：`reports/unified-media/live-15/video-model-run.json:8`、`video-adopted.json:7`、`after-cancel.json:7`、`offline-draft.json:7`、`image-model-run.json:8`、`image-draft.json:7`；夹具侧 `reports/v0-s2/frozen-structural-inputs-02.json`（`categories.tracking.sha256`）。

由此得到的结论（必须避免被误读）：

- ✅ 人签在**链路/功能**层面有效（真实解码、真实 PTS、真实模型、真实采纳/导出/取消、真实清理）。
- ❌ 人签在**内容质量**层面是**零证据**：输入是合成结构夹具，不是内容样本；因此**不可**用于 V0-A11 / V0-A12 / Q01 / MS04。
- ⚠️ 因此 `live15` 的视频证据与 S2 机器证据**共享同一批结构夹具**，不是独立媒体证据；S3 的独立质量集、Q01 集、MS 集与 11 段留样必须**四路互斥**（`docs/32.mutual_exclusion`：按媒体 SHA 与 origin source ID 互斥，留样即使标注用途也不可用于开发/调优/自动验收）。
- ⚠️ V0-A12 与 Q01 的视频规则**数字相同**（6 片、≥5 可用、幻觉 0）但**集合不同**，不得互相改写或默认为可继承（`reports/v0-s3/preparation-01.md` 原文警告）。

### 4.3 预算与历史保留（未改写、未清零）

- `AUTH-PROGRAM-V1-COMPLETE-03` 仍然 ACTIVE：全局 1024 模型动作 / 24 有效完整轮 / 172800 生产秒，**历史消耗计入、不清零**。
- live15 结算：29 动作 / 8 有效完整轮 / 1506 生产秒（另 CPU 6 秒），active children 0。`docs/32` 记载余额 995 / 16 / 171294 —— **每次运行前必须以最新账本复算**，不得以本审计的抄录值直接预约。
- S2 自身预算终态保持：补充轮 `NO_GO`（remaining 0）、资源就绪轮 `NO_GO`、`full-checkpoint-01/…-08` 全部为历史收据；`native_checkpoint_attempts.remaining_full_rechecks = 0`；夹具准备 2/2 用尽，**无第三次准备授权**。
- 本审计**未**消耗任何模型动作、完整轮、生产秒或 CPU 配额（0）。

---

## 5. 下一阶段 Gate0 检查单（要求5）

### 5.1 面向 V0-S3（序位上第一个可开工的产品 Stage）的 Gate0 草案检查单

| 检查项 | 现状 | 指向的确切文件 / 缺口 |
|---|---|---|
| 范围 / 非目标 | 已有草案，需冻结 | `reports/v0-s3/preparation-01.md`、`preparation-02.md`；`docs/13_V0_IMPLEMENTATION.md` §V0-S3 |
| 责任人（root 架构 / 实现 / 独审） | 已有角色模板 | `.agent-governance/stages/V0-S2/stage-control.json.roles`（`codex_gate_owner` / `codex_v0_s2_implementer` / `codex_v0_s2_independent_reviewer` / `local_ci` / `project_owner`）→ 建议改为 `codex_gate_owner` / `Orca ClaudeCode implementer` / `独立只读审查实例`（依 AGENTS 22 与 docs/30） |
| 公共接口 | V0-S3 **不新增**公共产品合同（沿用 `contracts/`） | `contracts/openapi.json`、`contracts/errors.json`、`contracts/package-manifest.schema.json` |
| Schema + 错误码 | 可复用 | `contracts/package-manifest.schema.json`（**当前无产出者，需补**）；`LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/*` 现有错误码 |
| 固定 oracle | 阈值已机器可读 | `config/experience-gates.json`（`v0_image_samples_min:10 / v0_image_usable_min:8 / video_samples_min:6 / video_usable_min:5 / critical_hallucinations_max:0 / video4_warm_p95_seconds_max:300 / release_after_stop_seconds_max:30`）；`plans/acceptance_cases.json` V0-A06/A11/A12 |
| 文件白名单 | 未冻结 | 拟：`LVW_V0_RuntimePatch/{README_V0.md,scripts/,manifests/}`、`reports/v0-s3/`、`tools/v0_s3_*.py`；**禁止**：`contracts/`、`plans/acceptance_cases.json`、`plans/release_gates.json`、`legacy/`、`COMFY_ROOT/custom_nodes/prompt-assistant/`（沿用 V0-S2 packet 的 forbidden_paths） |
| 命令 | 可复用 S2 工具链 | `cd lvw && python3 -B -m pytest`（`lvw/tests`）；`LVW_V0_RuntimePatch/tests`；`tools/v0_s2_*.py` 系列（可复用为阶段驱动器）；前端 `npm run test/typecheck/build` |
| 实际输入 | **缺** | S3 质量集 10 图/6 视频实体 + 独立预标注 + SHA + 权利记录（**当前只有 4 件结构夹具**）；MS 12 片/47 镜头（`NOT_MATERIALIZED_NOT_FROZEN`）；11 段留样**受保护，不得用作 S3 质量集** |
| 预算 | 母授权可派生，未冻结 | `AUTH-PROGRAM-V1-COMPLETE-03`（全局账本）+ 每轮有限子授权；S3 质量子预算：≥16 次分析（10+6）+ 安装/冷启动/故障义务所需次数，预热/加载也扣动作（`preparation-02.md`） |
| 清理 | 已有范式 | S2 `default/warm` 归档 + `retained_root_disposition`；`live-15` `run_root_removed:true`、`api_listener_absent:true`、`ollama_listener_absent:true` |
| Stage Packet 本体 | **不存在** | `.agent-governance/stages/` 现有 `R1 R1a V0-S0 V0-S1 V0-S2 V1-D0`；**无 V0-S3** |
| 前置门 | **未关闭** | V0-S2 8/8（含原 S2 范围判定） |

### 5.2 有界的建议 Workpack 计划（DRAFT，不激活）

沿用并收敛 `preparation-02.md` 的 P1/P2/P3，收敛为 3 个包；**每个包在原 S2 范围判定关闭前不得启动**：

- **WP-S3-01｜复用审计与可逆增量包**（实现者）
  - 产出：`LVW_V0_RuntimePatch/README_V0.md`、`scripts/{diagnose,install,rollback}.ps1`、`manifests/{versions,node-bindings,licenses,sha256}.json`（产出契约用 `contracts/package-manifest.schema.json`）。
  - 复用：R1 行中"**COMPLETE**"的 S2 核（`LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/` 全部 23 个模块 + 4 个 workflow + 既有 `manifests/s1-baseline-bindings.json`），**不复制 Comfy/PyTorch/权重**。
  - Oracle：确定性 manifest + 逐文件 SHA；隔离根安装/回滚成功与失败两条终态；**不得**修改永久配置或现有用户安装。
- **WP-S3-02｜独立质量集（10 图 / 6 视频）与定向离线验证**（实现者 + 独立标注者）
  - 前置：**用户/产品责任人提供素材来源与权利记录**（COMPLETE03 不授权媒体下载）。
  - 顺序硬约束：**先冻结源字节与独立预标注，后取模型结果**；不得使用人工编辑稿评分；不得动用 11 段留样；不得与 Q01 集/MS 集/开发集重叠（按 SHA + origin source ID 互斥）。
  - Oracle：`≥8/10` 图可用、`≥5/6` 片可用、关键幻觉 `0`；缺失/拒答/未执行**不缩分母、不替换样本**。
- **WP-S3-03｜同一封存候选的累计十二项 Checkpoint + 独审 + 人工签署**（执行器 → 独立只读审查 → 人类）
  - 绑定：候选 SHA、packet manifest、样本 SHA、端口/进程/临时根、预算、清理策略、逐项命令与退出码。
  - 顺序：**先离线全绿 → 一次集中真实 checkpoint → 隔离复算（Fatal0/Major0）→ 人类体验签署 → 立即普通 Git 推送**（AGENTS 16）。

### 5.3 三权分离（docs/30 / AGENTS 11、22）

| 角色 | 归属 | 本审计的定位 |
|---|---|---|
| 总体/详细架构、合同、固定分母、验收设计、**门禁裁决** | Codex（root） | 不越权；只给建议与 DRAFT 提案 |
| 具体实现、自检、局部回归、收据 | Orca 可见 ClaudeCode 工作区（最多 1 实现槽 + 1 审查槽） | 不实现任何产品代码 |
| 隔离只读复算、复算证据 | 另一隔离只读窗口 | 本审计即此类角色的只读复算 |
| 实际体验 / 发布签署 | 人类（project_owner） | **不代签、不推定** |

---

## 6. 结论

- **就绪裁决：`NOT_READY_FOR_ANY_PRODUCT_STAGE_EXECUTION`。**
- 本次人签已完整放行"统一切片"这一件事，且**产品字节未变**（树哈希复算一致），无需重验。
- 剩余 V1 的关键路径 `S2 → S3 → R1 → M1 → R2` 上**唯一**未关闭的人类义务是**原 S2 范围判定**；它至今不存在于任何源文件中，必须由 Codex 判定 + 用户签署。
- 允许现在做的事：本审计交付物 + `draft-change-request-s2-scope-determination.{md,json}` + 面向 V0-S3 的 Gate0 草案检查单（第 5 节）。**不需要**再次请求统一前端人签。
- 授权/预算侧无缺口（COMPLETE03 ACTIVE，S2 自身预算终态保留），但**产品运行仍须等正确的 product packet 与前置**。
- 本审计未产生任何虚假绿灯：未签署任何 Stage、未批准任何产品变更、未声称任何文件存在即运行通过、未重算模型质量、未生成样本、未消耗任何预算。

## 附：证据索引

- 人签与范围：`reports/unified-media/human-signoff-live15.json`、`reports/unified-media/accepted-slice-live15.json`、`reports/unified-media/human-signoff-request-live15.json`、`reports/unified-media/gate-decision.md`
- 坐标与分母：`plans/execution-control.json`、`plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json`、`plans/requirements.json`、`plans/v1-revised-plan.json`、`plans/v1-multishot-sample-design.json`
- 权威文档：`AGENTS.md`、`.agent-governance/README.md`、`.agent-governance/stage-gates.md`、`docs/23`、`docs/27`、`docs/30`、`docs/31`、`docs/32`、`docs/13`
- S2 历史：`reports/v0-s2/full-v0-auto-08/{receipt.json,independent-review.json,gate-decision.md,human-signoff-request.md}`、`reports/v0-s2/frozen-structural-inputs-02.json`
- 统一切片：`reports/unified-media/live-15/receipt.json`、`reports/unified-media/independent-live-15/{receipt.json,review.md}`
- D0 收口：`reports/v1-redesign/d0-acceptance/{decision.md,decision.json}`、`reports/v1-redesign/d0-review/design112/receipt.json`
- S3 准备：`reports/v0-s3/preparation-01.md`、`reports/v0-s3/preparation-02.md`
- 阈值：`config/experience-gates.json`
