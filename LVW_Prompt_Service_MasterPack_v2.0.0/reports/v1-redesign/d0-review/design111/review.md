# D0-B-REVIEW｜LVW V1 多镜头**设计 1.1.1 + 独立代码审查** 独立复核

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-REVIEW`
- 复核对象（两份输入，合并为一次独立复核）：
  1. **代码候选** = commit `f7956941992a0c467384b5dc9c63133f95152f41`（`tools/verify_v1_plan.py` + `tools/test_verify_v1_plan.py`）
  2. **设计权威 1.1.1** = commit `743e028474909be02326facd6f14ca0ac26aa56f`（owner 关闭 N1–N6 残留并封版）
  - D0 payload manifest 摘要（owner 供给）：`04d3bfb4af3c2d7be68e494a6d59624a96051a0ebf28e81d6a0367aa32aa6710`
- 本窗口加载方式：`git merge --no-ff f795694…`（clean merge，无冲突，无手改任何权威内容），review merge commit = `471bf9509086021553c6ca360080a54767d5c3d0`
- 审查者身份：**隔离 Orca 可见 ClaudeCode 复核窗口**，worktree `…/lvw-v1-d0-review`，分支 `ljx418/lvw-v1-d0-review`
  - Orca 上下文：coordinator `term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0`；reviewer terminal `term_888c6cab-c150-4f7d-be16-55466daed9e4`；task `task_7187786f1e40`；dispatch `ctx_3000571bd72a`
- 与实现会话分离：**未实现** checker；实现收据与实现结论只作为待核对材料，不作为权威
- 复核性质：**DESIGN_RECHECK + CODE_AUDIT（离线）**。**不构成产品 Gate0、产品 PASS、Stage PASS 或人工签署。**
- 写权限：仅 `reports/v1-redesign/d0-review/design111/`（符合 `stage-control.json` 的 `D0-B-REVIEW.allowed_files`）；父工作树与实现工作树**未触碰**
- 未执行：模型推理、GPU、媒体/FFmpeg、服务、浏览器、网络、安装、provider 切换、产品数据库、push；未编辑任何 canonical 合同 / 计划 / 文档 / manifest / packet / 产品源码

---

## 0. English executive summary

**What was reviewed.** The D0-B-IMPL checker candidate (`f795694`) and the Codex design 1.1.1 authority (`743e028`), as one combined independent checkpoint: a code audit of `tools/verify_v1_plan.py` (which had deliberately **not** been done in the earlier design-1.1 audit) plus an independent recheck of the six residual findings N1–N6 against the frozen specification.

**Headline result.** The design 1.1.1 corrections are **real and correctly made**: N1, N2, N3 and N4 are **RESOLVED**; N5 and N6 are **RESOLVED_WITH_RESIDUAL**. The checker is genuinely fail-closed on the surfaces it claims to guard, the test suite is genuine and CLI-level, and the two mandatory commands pass: the checker exits 0 with a stdout **byte-identical** to the implementation's own log, and the suite is **164 passed / exit 0**.

**But the checker is not complete.** Three independent probes produced a **false green** on a semantically wrong package: a wrong scene-hash column alias (P01), a permuted `lvw_scene_hash()` argument list (P02), and a new `GET /api/v1/scenes/{id}` that returns a non-canonical DTO (P05) — exactly the M1/F1 divergence the whole design was built to prevent. Three further probes produced an **uncaught traceback with an empty stdout** instead of a deterministic finding (P22/P23/P24). Two degraded runs — missing `jsonschema`, missing retained-frame sample — produce a stdout **byte-identical** to the full run, because `Report.note()` results are collected and never printed.

**Severity.** New findings: **0 Fatal, 3 Major, 6 Minor**. N1–N6: **0 UNRESOLVED**. No code was changed by this review; every code fix belongs back to the implementer.

**Nothing product-level was granted.** The product stays at `R1 / WAIT_HUMAN`, the `621b1bf` experience signature is still absent, the samples stay `NOT_MATERIALIZED_NOT_FROZEN`, and this offline D0 packet is **not** product Gate 0.

---

## 1. 复核方法（与实现测试**不镜像**）

本窗口**没有**复用实现者的测试思路，而是自建了两套独立工具：

| 工具 | 作用 | 位置 |
|---|---|---|
| `checks/probes.py` | 43 个独立负例/正例探针，跑**真实 CLI**（`subprocess` 调 `tools/verify_v1_plan.py`） | `checks/probe-run.log`、`checks/probe-results.json` |
| `checks/recompute.py` | 用复核者自己的代码**重算** N1–N6（不调用 checker） | `checks/recompute-results.json` |

### 1.1 关键方法论：区分"哈希围栏拒绝"与"语义规则拒绝"

每个探针在**全新的 `TemporaryDirectory` 副本**上运行真实 CLI（副本之外不写任何东西；不复用通配符清理；无共享标记文件），并分两种模式：

- **fence=ON（语义）**：把改动过的文件在 `spec-manifest.json` / `PAYLOAD_MANIFEST.sha256` 中**重新冻结**（必要时连 `legacy-gates-before-change.json` 的 canonical 哈希一起重基线）。此时**只有语义规则还能拒绝它**。
- **fence=OFF（仅哈希）**：不重新冻结。此时任何拒绝**只能**证明"冻结哈希发现��编辑"，不证明任何规则。

这条区分是本次复核的核心：它让"哈希挡住"与"规则挡住"无法互相冒充，也让 false green 暴露出来。

### 1.2 源代码围栏（读只读）

`checks/hash-fence-before.txt` / `hash-fence-after.txt`：**29** 个权威/候选文件（24 个 authority spec 围栏文件 + 2 个候选代码文件 + D0 packet 的 3 个控制文件：`PAYLOAD_MANIFEST.sha256` / `spec-manifest.json` / `stage-control.json`）**审计前后逐字节一致**（逐项比对无差异）。复核者另行按存活文件重算 29 个摘要，与围栏**逐位一致**。`git status` 除本 review 目录外无任何改动。

---

## 2. 强制命令复跑（隔离临时根，一次）

| 命令 | exit | 结果 | 与候选日志比对 |
|---|---|---|---|
| `python3 -B tools/verify_v1_plan.py` | **0** | `RESULT: PASS (V1=29 V2=38 V3=47; …)` | **stdout 逐字节一致**（两者 sha256 均为 `9ae799f0…`） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | **0** | **164 passed in 19.36s** | 与候选 stdout **仅差计时行**（`19.36s` vs `23.65s`）；候选日志自身 sha256 `be7edb16…` 与其收据所列一致 |
| `python3 -B tools/verify_governance.py`（补充） | 0 | `errors [], failed 0` | **逐字节一致** |
| `python3 -B tools/verify_pack.py`（补充） | 0 | `passed 7476, failed 0` | 候选日志为 7475、候选收据正文为 7408 → 见 **NM-7** |

原始 stdout/stderr/exit 与哈希全部落在 `checks/`。**两个强制命令均 exit 0，无强制正例失败。**

---

## 3. N1–N6 独立重算结论

> 判定口径：**RESOLVED** = 权威侧纠正到位且复核者独立重算通过，并且对应机器护栏经探针验证会拒绝对应缺陷；**RESOLVED_WITH_RESIDUAL** = 纠正本身到位，但同一区域仍留有残留缺陷（列入第 4 节）；**UNRESOLVED** = 纠正缺失或错误。

| ID | 主题 | 判定 | 复核者独立重算的关键证据 |
|---|---|---|---|
| **N1** | ETag 由散文变为机器声明 + metadata 提升规则 | **RESOLVED** | 重放严格 merge：38 个 canonical operation **逐字节比对，0 处被改**、0 处 merge 问题；PUT 200 只新增 `['ETag']`，请求体与 `x-product-version: V2` 不变；`^"scene:[^":]+:[0-9a-f]{64}"$` 接受强标签、**拒绝弱标签**；新 GET 200 body = `#/components/schemas/Scene` |
| **N2** | `additive_paths` 漏掉既有 Scene 路径上的新 GET | **RESOLVED** | overlay 实际面 = **8 operation / 7 path**；contract 的 `additive_paths`/`additive_operations` 与之**完全一致**；canonical 文档**没有** `GET /api/v1/scenes/{id}`，故为新增而非替换 |
| **N3** | 7 条 reuse 路径只有 2 条被标注 | **RESOLVED** | **8 个 (path, method) 全部标注**且键集合恰为 `{x-v1-profile: local-shot-v1, x-v2-semantics-unchanged: true}`；**每个 target 都存在于 canonical OpenAPI**；**无键冲突**；canonical `x-product-version` 原值全部读回未变 |
| **N4** | `ShotFrameRef` 的不可达 null 分支 | **RESOLVED** | 属性集/required 集与 canonical `FrameRef` **完全一致**；`source_pts/time_base_num/time_base_den` 均为**纯 `type: integer`**，两个 timebase 带 `minimum: 1`，`time_basis = {const: decoded_pts}`（收窄 canonical 枚举）；**4 条保留的历史帧引用**（live-15）在 jsonschema 4.23.0 下**全部验证通过**；canonical `FrameRef` 自身 null 分支**未被改动**（canonical 冻结，正确） |
| **N5** | 双语 evidence → canonical `Domains` 映射 | **RESOLVED_WITH_RESIDUAL** | 复核者按规则**逐字节重算** owner 示例并**完全吻合**；空语言跳过、无翻译、不 trim/不去重、原文逐字节保留、human 域不生成不覆盖（仅显式采纳且 human lock 优先）、`summary.zh→text_zh / summary.en→text_en` 逐字复制、unknowns 原序 zh→en 全部落地；并由复核者用同一规则**推导出 scene/action/unknown 三种条目**证明规则可实施。残留见 **NM-5 / NM-6** |
| **N6** | 哈希字段名 ↔ DDL 列别名 | **RESOLVED_WITH_RESIDUAL** | 11 个别名**全部可解析**（`scene_revision.*` / `scene_revision_meta.source_sha256` + 旧回填 `media_ref.sha256` / `tb_num` / `tb_den` / `time_basis` / `verified`）；migration 的 `lvw_scene_hash(...)` **恰好 11 个实参且顺序与字段表一致**；复核者**自建 fixture 并独立重算哈希**：`{"editor":"algorithm",…,"verified":true}` → sha256 `91133a6cdfc93456e2bc7d53c68eec9ad1a0faf5bd0e05b84b95dbafe0d9f788` → ETag `"scene:scene-rev-001:91133a6c…"`，**符合冻结强标签格式**；`verified` 为 JSON boolean（SQLite 0/1 → false/true）。残留见 **NM-1** |

### 3.1 N1–N6 之外的保留义务复核

按指示**不重跑整个原 22 项设计审查**，只核对**变更面**上的保留义务，全部通过：

- canonical `Scene` 与候选 `CoreScene` 仍是**逐字段相等**的别名（探针 P34 反向验证：改一处即 `E_CANONICAL_ALIAS`）
- canonical `POST /api/v1/jobs/batch` 请求体仍是 `{items:[AnalyzeRequest]}`（探针 P33：**重基线 canonical 哈希后**仍被 `E_V2_BATCH_BODY_DRIFT` 拒 → 是语义规则，不是哈希）
- `contracts/openapi.json` / `lvw.schema.json` / `storage.sql` 三个 canonical 哈希与 `legacy-gates-before-change.json` **逐位一致**
- 旧 R1 packet manifest `38ca0ae5…` 与其列出的**每个文件**哈希一致
- 固定分母 29/38/47 + 21/30/39 前缀 + MS01–MS08 各一次（探针 P41 缩小 V1 分母 → `E_DENOM_V1_COUNT`）
- 样本 12 clips / 47 shots / 21 hard cuts / 18 quality(12/3/3)，全部 `NOT_MATERIALIZED_NOT_FROZEN`（探针 P42 漂移 shot 总数 → `E_SAMPLE_SHOT_COUNT`）
- 预算 `450*n+90 ≤ 5490`、checkpoint `65+7=72 actions / 21600 s / 21420+180`、阈值估算 `20735 s`（探针 P17 抬高 action cap → `E_CHECKPOINT_INPUT_DRIFT`）

---

## 4. 新发现（代码审查）

> 严重度口径：**Fatal** = 会让本包产生错误的 PASS/PASS 冒充或越过产品前置；**Major** = 存在真实的 false-green 路径或受控输入逃逸；**Minor** = 证据/披露/文本一致性问题。
> 下列任何需要改代码的项，**都必须退回实现者**，复核者不改代码。

### NM-1（Major）N6 护栏只钉住 11 个别名中的 3 个，且从不核对 SQL 调用点实参顺序

- 文件/位置：`tools/verify_v1_plan.py` → `check_scene_hash_column_mapping` (2073–2119)；`FROZEN_SCENE_HASH_COLUMN_ALIASES` (491)；`FROZEN_SCENE_HASH_REVISION_ALIAS` (495)
- 触发：把某个**未钉住**的列别名改错（如 `media_sha256 → scene_revision.media_ref_id`），或把 migration 里 `lvw_scene_hash()` 的 11 个实参**换序**
- 期望：11 个哈希字段全部绑定到自己的 DDL 列；SQL 调用点实参顺序与 `scene_hash.fields` 比对
- 实际：只有 `time_base_num→tb_num`、`time_base_den→tb_den`、`revision→scene_revision.version` 被钉住；其余 **8 个别名只检查键是否存在**；**实参顺序完全不检查**
- 复现（`checks/probe-results.json` P01 / P02，均已重冻围栏）：
  - P01 → **exit 0，`RESULT: PASS`**
  - P02 → **exit 0，`RESULT: PASS`**
  - 两者 stdout 与未改动对照 **逐字节相同**（`9ae799f0…`）
- 影响：正是 N6 点名的危害——**列映射或实参顺序不同 → 静默不兼容的场景哈希与 ETag**，而 D0 机器门禁报 PASS
- 备注：**当前 owner 产物本身是对的**（`n6.sql_call_site_field_order_ok=true`，11 个别名全部可解析）；缺陷在于机器护栏**没有保护**它

### NM-2（Major）新 `GET /api/v1/scenes/{id}` 返回的 canonical `Scene` DTO 没有机器护栏

- 文件/位置：`tools/verify_v1_plan.py` → `check_overlay_additive` (1525–1613)、`check_overlay_merge` (1863–1952)
- 触发：把 overlay 新增 GET 的 200 body 从 `#/components/schemas/Scene` 改成别的候选组件（如 `MultiShot_SceneRevisionInfo`）
- 期望：新 Scene GET 的 200 body **必须**是 canonical `Scene`——"在 `/scenes/{id}` 上保留 canonical Scene"正是 M1 补救的全部内容（design 1.1 审查证据 C02/C03）
- 实际：checker 只验证 overlay 引用的组件**存在**，**从不钉住**该 GET 上的 Scene DTO
- 复现：探针 **P05**（已重冻围栏）→ **exit 0，`RESULT: PASS`**，stdout 与对照逐字节相同
- 影响：1.0 审计判为 Fatal 的"canonical 与候选 DTO 在 `/scenes/{id}` 上互斥"可以在 checker 全绿的情况下**重新出现**
- 备注：当前 overlay 实际是正确的（`n1.new_scene_get_body_ref = #/components/schemas/Scene`）

### NM-3（Major）畸形输入逃逸为未捕获 traceback（stdout 为空），而不是确定性 finding

- 文件/位置：`tools/verify_v1_plan.py` → `check_overlay_merge` 第 1892 行 `metadata.items()`、第 1913 行 `add_headers.items()`；`check_canonical_compatibility` 第 1509 行（jsonschema 在保留帧上抛错）；`check_contract_and_schema` 第 1200 行（metaschema 检查）
- 触发：① `overlay.metadata_only` 或 `overlay.add_response_headers` 是 JSON 数组；② 候选 schema 的某个 `pattern` 是非法正则（如 `([unclosed`）
- 期望：stdout 上给出确定性 `E_*` finding 并 exit 1，或干净的 `INPUT_ERROR` 并 exit 2
- 实际：uncaught `AttributeError`（`'list' object has no attribute 'items'`）与 `re.error` traceback 打到 stderr，**stdout 为空**，exit 1
- 复现：探针 **P22 / P23 / P24**（均 exit 1、stdout 空）
- 影响：exit code 仍非零，**就退出码而言 fail-closed**；但工具自述的"exit 1 = 至少一个确定性检查失败"被破坏——**只读 stdout 的自动门禁会一个 finding 都看不到**，而 traceback 容易被误读为环境故障而非"候选被拒"
- 补充：`E_SCHEMA_META` 救不了这个场景——JSON Schema 的 `format: regex` 默认只是注解，`check_schema()` **不校验正则合法性**
- **一个干净的对照**：真正"读不到输入"的情况是**优雅**的——`--root /nonexistent` → exit **2** + `INPUT_ERROR: plan: cannot read …`，无 traceback（`checks/missing-input.stdout.log`）

### NM-4（Minor）降级校验从不披露：`Report.note()` 被收集后丢弃，且运行不记录自己验证的是哪个 pin

- 文件/位置：`tools/verify_v1_plan.py` → `Report.note` (533–534)；调用点 1040 / 1204 / 1496 / 1500；`main` (2655–2696) **只打印 `report.errors`**
- 触发：可选 `jsonschema` 不可导入；保留帧引用样本缺失；execution-control 坐标状态不是 `WAIT_HUMAN`
- 期望：运行**自述**实际执行了哪些校验（metaschema 检查、保留帧实例探针），以及它验证的是哪个 D0 payload pin
- 实际：`E_SCHEMA_META_SKIPPED` / `E_FRAME_REF_SAMPLE_SKIPPED` / `E_COORDINATE_NOTE` 被收进 `Report.notes` 后**永不打印**；降级运行的 stdout 与完整运行**逐字节相同**（三者 sha256 均为 `9ae799f0…`）
- 复现：**P25**（`--frame-sample` 指向不存在路径）、**P26**（把一个 `raise ImportError` 的影子 `jsonschema.py` 放到 `PYTHONPATH` 首位）→ 均 exit 0 且 stdout 与正例 P00 **逐字节相同**
- 影响：D0 门禁证据就是"checker exit 0 + 测试日志"，而工具**无法区分完整跑与降级跑**；换一台没有 jsonschema 的机器，会产出与本次**一样好看但更弱**的证据
- **关于可选 jsonschema 回退的诚实说明**：本环境 **jsonschema 4.23.0 可导入**（复核者自行验证：`recompute-results.json → n4.probe_engine`），因此**候选自身的证据确实跑了完整 metaschema 检查与完整保留帧实例探针，本次运行没有省略任何校验**。本条缺陷是**披露缺失**，不是"候选漏检"，更不构成任何产品 PASS

### NM-5（Minor）N5 条目序列化规则自相矛盾，且 checker 的键序常量是死代码

- 文件/位置：`plans/v1-multishot-contract.json` → `canonical_domain_mapping.entry_serialization`：`… compact UTF-8 JSON object, sorted keys, … Keys kind, ref, lang, text. …`
- 触发：实现者按枚举顺序 `kind, ref, lang, text` 而不是按同句中的 `sorted keys` 来写
- 期望：机器合同里只有**一种**无歧义键序
- 实际：同一句话既说 `sorted keys` 又枚举 `kind, ref, lang, text`；而冻结示例用的是**第三种**（排序后的）`kind, lang, ref, text`；checker 在 431 行定义了 `FROZEN_DOMAIN_ENTRY_KEYS = ("kind","ref","lang","text")` 却**从未引用**（死代码），矛盾因此**检测不到**
- 复现：探针 **P03**（把示例改写成散文键序并重冻围栏）→ exit 1 `E_DOMAIN_MAPPING` → 证明**真正生效的是示例，不是散文**
- 影响：机器合同存在两种同样合法的读法，会产出不同字节 → 不同 canonical `Domains` 条目与不同哈希；示例只在实现者自己冻结示例时消除歧义

### NM-6（Minor）N5 示例重算只覆盖 character 域，且忽略已声明的 observation/inference 路由

- 文件/位置：`tools/verify_v1_plan.py` → `check_canonical_domain_mapping` (2001–2070)，重算体在 2053–2069
- 触发：scene / action / unknown 条目序列化出错误的 `kind` 或 `ref`；或某条目被路由到错误的域（observation vs inference）
- 期望：机器合同声明的**每个**域 kind（character / scene / action / unknown）都被验证
- 实际：重算**硬编码** `kind="character"`，只解析 character 的 ref 与 source field；示例自带的 `"domain": "observation"` **从未被读取**；scene/action/unknown 的 refs 与 source fields **只做字符串比较**
- 复现：复核者用同一规则推导出 scene/action/unknown 三种条目（`recompute-results.json`）证明规则可实施，但**没有任何机器检查**能发现该处的分歧
- 影响：N5 护栏证明的是**一个示例**，不是它所属的**规则**

### NM-7（Minor）实现收据正文与其自身哈希绑定的日志自相矛盾

- 文件/位置：`reports/v1-redesign/d0-worker/design111/implementation-receipt-1.1.1.json:148`（及 `.md:71`）
- 触发：读者直接采信收据所述的 `verify_pack` 结果
- 期望：收据所述结果与其绑定（sha256）的日志一致
- 实际：收据写 **`passed 7408`**，而它自己绑定的日志 `d0-worker/design111/logs/verify_pack.stdout.log`（sha256 `c0d2ebec…`，正是收据所列的摘要）写的是 **7475**；复核者在**候选树原件**上独立复跑得 **7476 / 0**
- 影响：对 D0 门禁**无实质影响**（`verify_pack` 不是 stage-control 命令，且哈希绑定的日志本身正确且在册），但 7408 是**沿用 1.1 收据的陈旧数字**，而收据正是读者最相信的那份材料
- 补充解释：7476 个检查中 **4818 个是 MANIFEST.sha256 逐行一项**，故运行时的清单行数差 1 即可解释 7475 vs 7476

### NM-8（Minor）D0 payload pin 可被 CLI 覆盖，且运行不记录自己验证的是哪个 pin

- 文件/位置：`tools/verify_v1_plan.py` → `--d0-packet-manifest-sha256`（2485–2486，默认 `FROZEN_D0_PACKET_MANIFEST_SHA256`）；`ctx.d0_manifest_expected = args.d0_packet_manifest_sha256`（2570）
- 触发：以被覆盖的 pin 运行；或读者想确认某次 PASS 是在哪个 pin 下产生的
- 期望：运行自述所验证的 pin
- 实际：默认值**就是**硬编码的 owner 摘要 `04d3bfb4…`（复核者独立重算确认与 owner 供给一致），且 `stage-control.json` 冻结的 D0 命令**不带任何覆盖参数**，故门禁运行用的是默认值。但 checker **不打印 pin**，于是在被覆盖的 pin 下产生的 PASS 与默认 pin 下的 PASS **无法区分**；实现者自己的合成测试**必须**覆盖 pin（合成树永远无法满足默认值），因此**默认 pin 只被两条跑在真实 root 上的测试覆盖**
- 影响：对本候选**低**（pin 值、两条陈旧 pin 反例、payload 清单均已被复核者独立复现），但证据**不自述**

---

## 5. 独立探针结果总览（43 个）

| 类别 | 数量 | 说明 |
|---|---|---|
| 正确拒绝并给出**预期** finding code | **34** | 语义护栏确实生效（N1–N6、空清单家族、NaN、分母、样本、预算、伪造裁决、坐标漂移等） |
| **False green**（语义错误但 exit 0 PASS） | **3** | **P01**、**P02**、**P05** → NM-1 / NM-2 |
| 降级但仍 PASS（stdout 与完整跑逐字节相同） | **2** | **P25**、**P26** → NM-4 |
| 未捕获异常、stdout 为空 | **3** | **P22**、**P23**、**P24** → NM-3 |
| 仅哈希拒绝（已明确区分） | 2 | P20 `E_SPEC_FENCE_DRIFT`；P21 `E_CONTRACT_DRIFT` + `E_V2_BATCH_BODY_DRIFT` |
| 正例对照 | 1+ | P00 未改动副本 PASS；强制命令 stdout 与候选日志逐字节一致 |

> **有意非零 = 证据，不是失败的交付物。** 探针的非零退出表示护栏**确实开火**；两个强制正例（checker、164 测试）均为 exit 0。

---

## 6. 测试质量评估（不只看 164 这个数）

- **确实走生产路径**：`tests/test_verify_v1_plan.py` 的每个用例都用 `subprocess.run([sys.executable, "-B", CHECKER, "--root", ...])` 驱动**真实 CLI**，没有任何一个用例直接调用内部 `check_*` 函数 → CLI 入口、参数解析、退出码都被覆盖。
- **夹具纪律好**：合成包建在 pytest `tmp_path` 下；`test_canonical_package_validates_read_only` 与 `test_checker_is_read_only` 对 canonical 文件**运行前后逐文件哈希比对**并断言未变。
- **owner 真实产物覆盖**：`owner_copy` fixture 把**真实** owner 产物拷进临时目录，改一个产物，然后让**真实 checker** 对副本做判定（8 个这样的用例）。
- **D0-CODE-M01 家族是行为性的**：空 `allowed_files` / 空 `commands` / 空 `forbidden_write_paths` / 空 review `allowed_files` 都有**否定用例**，不是常量比对。
- **弱点（属覆盖问题，非风格问题）**：
  1. `test_d0_packet_pin_is_the_owner_supplied_111_digest` 只把字面量和模块常量对比，**证明力弱**；真正有分量的是"陈旧 1.1 pin 必须失败"那条行为用例；
  2. 合成套件必须覆盖 pin，**默认硬编码 pin 只被跑在真实 root 上的两条用例覆盖**；
  3. 该套件**镜像实现者自己的护栏**，因此**永远无法暴露"根本没写的护栏"**——而这正是 P01 / P02 / P05 暴露的东西。
- **结论**：测试是真实的、CLI 级、行为驱动的，**不是凑数**；但它的天花板是覆盖，不是质量。

---

## 7. 保留意见与限制

1. 本次是**离线设计 + 工具审查**：不是产品验收、不是产品 Gate0、不是 Stage PASS、不是人工签署。
2. 产品坐标仍为 `R1 / WAIT_HUMAN`；`621b1bf` 体验签署仍缺；样本仍 `NOT_MATERIALIZED_NOT_FROZEN`；MS 用例、V1-M1 stage 与 R22 仍 `NOT_RUN`。
3. checker 校验的是**计划与合同的结构**：不跑产品代码、不开产品库、不产生运行时 ETag 响应头、不物化样本。
4. 候选 migration SQL **只被当文本解析，从未执行**；定义 `lvw_scene_hash` 的 DDL **不在冻结包内**（migration 只写"register deterministic lvw_scene_hash(11args) before this transaction"），因此场景哈希**只能对着声明的散文规则**验证，**永远无法对着一个已交付的函数**验证。实现收据对此是**诚实披露**的。
5. 有效 OpenAPI 只在内存中被复核者重放，**未生成也未交付**任何 effective OpenAPI 文档。
6. `jsonschema` 4.23.0 在本环境可导入，完整 metaschema 检查与保留帧实例探针**确实执行**；无 jsonschema 的主机会**静默降级**（NM-4）。可选回退已如实说明，**未把任何省略的校验说成产品 PASS**。
7. 实现者的 provider / 模型身份**自报且未独立验证**。
8. 补充 `verify_pack` 计数与候选日志差 1、与候选收据正文差 68，原因已解释（MANIFEST 行数），但**未逐字节复现**该差异。
9. 43 个探针是**有界的独立选取**，不是对 checker 全部输入的穷举；复核者**不声称**其余未测输入必然干净。

---

## 8. 结论与下一步

- **设计 1.1.1 侧**：N1–N6 **无一 UNRESOLVED**；N1–N4 **RESOLVED**，N5/N6 **RESOLVED_WITH_RESIDUAL**。owner 的六处纠正**真实、正确**，且已被复核者独立重算。
- **代码侧**：checker **在本包声称守护的面上确实 fail-closed**，测试套件真实；但 **NM-1 / NM-2 构成真实 false-green 路径**，**NM-3 是受控输入逃逸**，**NM-4/NM-8 是证据自述缺陷**，**NM-5/NM-6 是 N5 侧的残留**，**NM-7 是收据准确性**。
- **本复核未改任何代码**：所有需要改代码的 NM 项**退回实现者**（ClaudeCode-D0-Implement），复核者不代修。
- **下一 owner**：Codex（裁决）→ 实现者（处理 NM 代码项）。本 Workpack 仅产出 `review.md` / `findings.json` / `receipt.json` 与 `checks/` 证据；**未合并到父工作树、未签署 Stage、未 push**。
- **再次明确**：以上任何结论都**不构成**产品 Gate0、产品 PASS、Stage PASS 或人工签署。

---

## 附：产物清单

```
reports/v1-redesign/d0-review/design111/
├── review.md            本报告
├── findings.json        结构化 finding（N1..N6 判定 + NM-1..NM-8）
├── receipt.json         复核收据（上下文/围栏/原始日志/探针/计数/限制/product_actions=0）
└── checks/
    ├── hash-fence-before.txt / hash-fence-after.txt   30 文件围栏（前后一致）
    ├── probes.py / probe-run.log / probe-results.json  43 个独立探针
    ├── recompute.py / recompute-results.json          N1–N6 独立重算
    ├── mandatory-checker.{stdout,stderr,exit}.log      强制 checker 复跑
    ├── mandatory-pytest.{stdout,stderr,exit}.log       强制 164 测试复跑
    ├── verify_pack.stdout.log / verify_pack.pristine.stdout.log
    ├── verify_governance.stdout.log
    ├── pin-stale-1.1.stdout.log / pin-stale-1.0.stdout.log
    └── missing-input.stdout.log
```

> 历史复核报告（含失败的探针与既往结论）**全部保留未改**；本目录是**新增**的，不覆盖 `d0-review/`、`d0-review/design11/` 与 `d0-worker/` 下的任何既有产物。
