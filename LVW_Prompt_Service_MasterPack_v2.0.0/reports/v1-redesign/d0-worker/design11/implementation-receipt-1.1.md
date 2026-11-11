# D0-B-IMPL ｜ V1 设计 1.1 校验器再冻结实现收据（READY_FOR_REVIEW）

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-IMPL`
- 设计版本：1.1 ｜ 状态：**READY_FOR_REVIEW**。本收据**不是** Stage PASS、**不是**产品 PASS、**不是**人工签署。
- 写权限：仅 `tools/verify_v1_plan.py`、`tools/test_verify_v1_plan.py`、`reports/v1-redesign/d0-worker/`（与 stage-control 的 `D0-B-IMPL.allowed_files` 一致）。
- 未执行：产品代码、GPU、媒体/FFmpeg、服务、浏览器、网络、pip/npm 安装、凭据读取、供应商切换、生产数据库、Git push、任何 canonical 合同/计划/文档/manifest/packet/产品源码的编辑。

## 1. 权威装载与围栏复验

| 项目 | 值 |
|---|---|
| 权威设计提交 | `932dcbc48bca99c463ffea8bf11d121c36aefe0c` |
| 装载方式 | `git merge --no-ff 932dcbc…` → 合并提交 `7da0612c23953a127ede25980c49a92a2a2a84bf`（**无冲突**） |
| D0 PAYLOAD_MANIFEST SHA256 | `56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a`（与任务给定值一致） |
| D0 spec-manifest.json SHA256 | `ee9ec4f4cc9277f5fe436465856e9403ffdf904aa86e7ef7eb28d10ee1eb8f51` |
| D0 stage-control.json SHA256 | `f2447d1387ac7563eff56e51af93cfc15a392308798c4826c670c50bcb0521e1` |
| 校验器 pin 再冻结到 | `56e6f07b…`（**同一 CODE 提交内**再冻结；1.0 的 `9bffdf2d…` 已失效） |
| owner hash 是否被重算以通过 | **否**。23 个 spec-manifest 文件与 10 个 D0 payload 文件全部逐一复算，0 不匹配。 |

权威输入复算（与 spec-manifest 一致）：plan `0cc505cb…`、contract `e7c86482…`、sample-design `a249380d…`、DTO schema `dbaad207…`、overlay `980d93ea…`、migration `44f19c8b…`。

D0 源清单保持不变：`00..07` + `stage-control.json` + `spec-manifest.json`（10 项），由 `PAYLOAD_MANIFEST.sha256` 自身 digest 绑定。

## 2. 命令、退出码与日志 hash

| 命令 | 退出码 | stdout SHA256 | stderr SHA256 |
|---|---:|---|---|
| `python3 -B tools/verify_v1_plan.py` | 0 | `418195639ecba4603e6bb0e6ebbf788cf5e8825bec510c31f9f4e1ba5c28e813` | `e3b0c442…b855`（空） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0（107 passed） | `d9aa6936c95d863d7b9cfe7a99bbb83d99726f27f1e5d2b4e81623512eb9c90a` | `e3b0c442…b855`（空） |
| `python3 -B reports/v1-redesign/verify-design11.py`（root 探针） | 0（`{"checks": 22, "failed": 0, "product_actions": 0}`） | `3ef3ca2c39e4f9991bb790374f1ea021459303b7756774c91818e46676c747a9` | `e3b0c442…b855`（空） |

原始日志：`reports/v1-redesign/d0-worker/design11/logs/`（每个命令 stdout/stderr/exit 三个文件；exit 文件 digest `9a271f2a…86aa`）。
root 探针重写了 `reports/v1-redesign/design11-checks.json`，但内容逐字节相同，本 worktree 中没有 root 属主文件变脏。

补充的只读复核（非 stage-control 指定命令，仅作回归旁证）：`python3 -B tools/verify_pack.py` → exit 0（`passed 7408, failed 0`，文档与合同校验，非产品验收）；`python3 -B tools/verify_governance.py` → exit 0（`errors [], failed 0`）。

## 3. 代码变更

### 3.1 再冻结

- `FROZEN_D0_PACKET_MANIFEST_SHA256` → 任务给定的 1.1 owner manifest digest，与代码变更同一提交；owner 清单与 owner hash 未被重算。
- 旧的 1.0 pin 不再能通过（有 CLI 级测试覆盖）。

### 3.2 保留的 1.0 覆盖（未削弱）

29/38/47 分母与 21/30/39 前缀、MS01–MS08 各一次、R1→V1-M1→R2 DAG 无环、R22 覆盖、Q01/MS 阈值 token、无虚假完成/无人签、`budget_reset=false`、stage 别名 V1-M1→R2、D0 四权分离与非空控制表、D0 packet manifest 围栏、spec 围栏、canonical 合同与旧 R1 packet 不可变、空表绕过（D0-CODE-M01）回归。

### 3.3 新增的 1.1 确定性守卫

| 类别 | 检查码 | 语义 |
|---|---|---|
| 父预算 | `E_BUDGET_PARENT_FORMULA` | 父时限是 `450*n+90`（n=1..12 → 540..5490），plan limits / ParentJob DTO 区间 / 合同不变式三处一致；`batch_deadline_seconds=1800` 这类固定猜测被拒 |
| 数值域 | `E_LIMIT_NOT_FINITE`、`E_LIMIT_NOT_INTEGER` | `json.loads` 接受 NaN/Infinity，而 NaN 与任何边界比较都为假——旧写法会静默放过；现在显式拒绝非有限值与非整数值 |
| 数值域 | `E_LIMIT_LOOSED`（扩展） | 新增 1.1 下限/上限：`gpu_free_mib_min>=19047`、`detection_seconds<=120`、`pts_index_bytes<=16777216`、450/90/5490 父预算项、72/21600/180 checkpoint 项 |
| 完整轮 | `E_CHECKPOINT_ACTIONS`、`E_CHECKPOINT_WALL`、`E_CHECKPOINT_CALLS` | 65+7=72 动作且 <=128；wall 21600；执行截止 = wall − 180 清理预留；video+image 调用 = 成功调用数 |
| 完整轮 | `E_CHECKPOINT_ESTIMATE_ARITHMETIC` | 用声明的阈值输入重算 20735（53×300+12×180+65×30+300+7×35+180）并要求 <= wall |
| 完整轮 | `E_CHECKPOINT_ESTIMATE_BASIS` | 估算依据必须声明“阈值”口径，并明确**不是**已测 P95、**不是**硬最坏保证 |
| 样本 | `E_SAMPLE_CLIP_COUNT`、`E_SAMPLE_SHOT_COUNT`、`E_SAMPLE_CUT_COUNT`、`E_SAMPLE_TOTALS` | 12 片 / 47 镜头 / 21 硬切标注可复算，硬切片的标注数必须等于镜头数−1 |
| 样本 | `E_SAMPLE_QUALITY_COUNT`、`E_SAMPLE_QUALITY_CATEGORY`、`E_SAMPLE_QUALITY_ID` | 显式 18 段子集，12 simple_action + 3 ambiguous + 3 static，clip/shot id 必须落在片内 |
| 样本 | `E_SAMPLE_MATERIALIZED`、`E_SAMPLE_STATUS` | source/annotation SHA、origin id、rights 等占位必须保持 null，状态保持 `NOT_MATERIALIZED_NOT_FROZEN`——不得伪造已冻结样本或 Gate0 |
| overlay | `E_OVERLAY_REPLACES_METHOD`、`E_OVERLAY_RESERVED_PATH`、`E_OVERLAY_COMPONENTS_REPLACE`、`E_OVERLAY_COMPONENT_UNKNOWN`、`E_OVERLAY_ROUTE_MISSING`、`E_OVERLAY_METADATA_REPLACES`、`E_V2_BATCH_BODY_DRIFT` | overlay 只能加：不得改写既有 method、不得碰保留 V2 路由、不得自带 components 覆盖、引用必须解析、`/jobs/shot-batches` 必须存在且返回 canonical Job、canonical `/jobs/batch` 仍是 `{items:[AnalyzeRequest]}` |
| 兼容 | `E_CANONICAL_ALIAS` | `CoreScene` 必须是 canonical `Scene` 的**逐字段相同**别名 |
| 兼容 | `E_FRAME_REF_INCOMPATIBLE`、`E_FRAME_REF_CONSTRAINT`、`E_FRAME_REF_INSTANCE` | `ShotFrameRef` 必须是 canonical `FrameRef` 的**收窄**（字段集/required/类型/枚举/边界/pattern 逐项比较），必须钉死 `decoded_pts`，不得接受 null PTS；已留存的真实 4 帧引用必须仍是合法实例 |
| 合同 | `E_CONTRACT_ENTITY_UNRESOLVED` | 声明了却没有 DTO 的合同实体是 finding，不再静默 `continue` |
| DTO | `E_PARENT_DTO_FIELD`、`E_CHILDREN_ENVELOPE`、`E_CHILD_ROW_FIELDS`、`E_EVIDENCE_DTO_FIELDS`、`E_DOMAIN_DTO_FIELDS`、`E_MODEL_RESPONSE_SCOPE` | 父 DTO 必须带 deadline/预算/全量计数；children 信封必须是 parent+children；子行必须带 ordinal/model_started/error_code 等全字段；人物/场景/动作必须带 domain=observation|inference 与帧索引；模型响应不得自带 frame_refs/user_evidence/creative_intent |
| 绑定 | `E_PUBLIC_BINDING_LEASE_TOKEN`、`E_PUBLIC_BINDING_REF`、`E_INTERNAL_BINDING_TOKEN` | 公开绑定不得暴露内部 `lease_token`，evidence 路由必须绑公开绑定，内部绑定必须保留 token |
| 状态诚实 | `E_MS_STATUS_CLAIM`、`E_STAGE_STATUS_CLAIM`、`E_R22_STATUS` | `PASS` 在通用枚举里合法，但设计评审阶段的新 MS 用例、V1-M1 阶段与 R22 必须保持 `NOT_RUN` |
| 产物 | `E_ARTIFACT_DECLARATION`、`E_ARTIFACT_NOT_HASH_BOUND`、`E_SQL_DECLARATION`、`E_SQL_FORBIDDEN` | 候选合同/DTO schema/overlay/migration/样本表必须被声明且被 spec manifest hash 绑定；SQL **只作文本解析**，不执行；不得含 ATTACH/DROP |
| 裁决 | `E_ADJUDICATION_CLAIM` | 架构裁决不得声称 product_pass 或人签 |
| 人签 | `E_HUMAN_APPROVAL_CLAIM`、`E_FORBIDDEN_CLAIM`（扩展） | `plans/execution-control.json` 的 `human_signoff`/`product_acceptance` 必须为空 |
| 围栏 | `E_SPEC_FENCE_INCOMPLETE` | owner spec manifest 必须覆盖 1.1 权威输入（docs/30–32、plans、contracts、overlay、migration、样本表、裁决、R1 manifest） |

## 4. 测试

- `tools/test_verify_v1_plan.py`：**107 个用例**（沿用 1.0 的 50 个 + 1.1 新增 57 个），全部通过。
- 夹具：全部在 pytest `tmp_path` 下的**合成包副本**上构造与变异；canonical 计划/合同/manifest/packet 从不被写入。
- 正对照：合成包 exit 0；**canonical 1.1 包 exit 0 且运行前后逐文件 hash 不变**；被取代的 1.0 pin 以 `E_D0_PACKET_MANIFEST_PINNED` 失败。
- 新负例均为“有意义的合成故障”，例如：父时限写回 1800 猜测、`limits` 注入 NaN/Infinity/4.5、checkpoint 动作数对不上、清理预留被吃掉、估算基准冒充实测 P95、样本少一片/质量子集 17 行/分类漂移/shot id 越界/把 source SHA 填成“已冻结”、overlay 覆盖既有 `PUT /scenes/{id}` 或把手伸进 `/jobs/batch`、CoreScene 改一个字段、ShotFrameRef 放开 null 或改成 `sample_target`、公开绑定塞入 `lease_token`、合同实体无 DTO、父 DTO 去掉 `deadline_at`、域枚举只剩 observation、模型响应自带 frame_refs、MS04 假 PASS、V1-M1 假 PASS、R22 假 PASS、migration 被改写/去掉 450*n+90/少一张表/加 ATTACH/DROP、spec manifest 漏掉 docs/32。

## 5. 风险与未决项

1. 本工具只是确定性计划结构检查，**不**关闭裁决里的 22 项（仍全部 `PENDING_RECHECK`），也**不是**独立复核。
2. 12 片 / 47 镜头 / 21 硬切 / 18 质量段仍是**设计分配**：媒体、授权、source SHA、PTS 索引、标注 hash 均未冻结，`E_SAMPLE_MATERIALIZED` 强制占位保持 pending。
3. 20735 秒是基于设计阈值（300/180）的**重算**，不是本次实测 P95、也不是硬最坏保证；只有代表性 pilot 才能确认预算。
4. 候选 migration SQL **未由本校验器执行**；root 的内存探针通过，但真实 R1 迁移器对产品基线仍未验证。
5. MS 用例 / V1-M1 / R22 被钉在 `NOT_RUN`：真实 checkpoint 合法产生 PASS 时必须由权威再冻结这些守卫，否则它们会 fail-closed——这是设计意图。
6. 无 jsonschema 的机器上，metaschema 与留存帧实例探针退化为结构化回退，实例结论只覆盖必填字段。
7. overlay 与 effective OpenAPI 仍是设计候选：本工具未执行构建期合并，只做合并前可见的引用/替换检查。
8. 父时限只验证“公式成立”，不保证 12 镜头永远落在 5490 秒内。
9. D0 stage-control 仍然禁止产品执行与 Stage PASS；当前 621b1bf 切片签署状态未被本次工作改动。

## 6. 交接

- 状态：**READY_FOR_REVIEW**。未宣布 Stage PASS，未合并到父 checkout，未 push。
- 下一位 owner：Codex（随后隔离的 D0-B-REVIEW 实例）。复核者须使用与本实现窗口不同的上下文/工作区。
- provider 元数据：**自报，未独立核验**。执行者为 Orca 可见 ClaudeCode 实现窗口（`term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0`）；会话环境自报的模型为 `MiniMax-M3.1-Flash-Preview`。这是开发侧助手，**不是**产品模型，产品推理调用数为 0。
