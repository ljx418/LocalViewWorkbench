# D0-B-REVIEW｜LVW V1 多镜头**设计 1.1.2 集中纠偏（NM-1..NM-8）独立回归复核**

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-REVIEW`
- 复核对象（两份输入，作为**同一次 D0 纠偏的回归复核**）：
  1. **代码候选** = commit `eea56636b1870586fd8d6b17005334f1b4c63cd7`（`tools/verify_v1_plan.py` + `tools/test_verify_v1_plan.py` + `reports/v1-redesign/d0-worker/design112/**`）
  2. **owner 设计权威 1.1.2** = commit `3af446302f6237b41dc500ee290caf2b5075ab80`（docs/31 的 1.1.2 纠偏边界节、`plans/v1-multishot-contract.json` 的 entry_serialization 澄清、`design112-adjudication.json`）
  - D0 payload manifest 摘要（owner 供给，**由复核者独立重算一致**）：`181c08ee7290f5bef02e22b6f7fd3c874c2d404cc8b4ffff84d2148a71f47eb8`
- 本窗口加载方式：`git merge --no-ff eea56636…`（clean merge，无冲突，未手改任何 owner/候选内容），review merge commit = `2ec04c6c1d4b133008d81ec2033eda9394d3942a`；`git diff --name-only eea5663 2ec04c6` 为空 ⇒ 加载后逐字节复现候选树
- 审查者身份：**隔离 Orca 可见 ClaudeCode 复核窗口**，worktree `…/lvw-v1-d0-review`，分支 `ljx418/lvw-v1-d0-review`
  - Orca 上下文：coordinator `term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0`；reviewer terminal `term_63a988f5-9b1f-41b9-beb3-27e0217d4c17`；task `task_02d74dfb10cf`；dispatch `ctx_04634a692bef`
- 与实现会话分离：**未实现**本轮 checker；实现收据与实现结论只作为待核对材料，不作为权威
- 复核性质：**BOUNDED INDEPENDENT REGRESSION RECHECK（离线）**。**不构成产品 Gate0、产品 PASS、Stage PASS 或人工签署。**
- 写权限：仅 `reports/v1-redesign/d0-review/design112/`；父工作树与实现工作树**未触碰**
- 未执行：模型推理、GPU、媒体/FFmpeg、服务、浏览器、网络、安装、provider 切换、产品数据库、push、root merge；未编辑任何 canonical 合同 / 计划 / 文档 / manifest / packet / 产品源码

---

## 0. English executive summary

**What was reviewed.** The consolidated correction package that closes the eight independent-review findings NM-1..NM-8 raised against the design 1.1.1 checker (`f795694`), together with the Codex design 1.1.2 authority (`3af4463`) that bounds the correction. This is a *bounded independent regression recheck of the same D0 correction*, not a restart of the original 22-finding architecture audit.

**Headline result.** The correction is real, complete on the eight named findings, and machine guarded. **NM-1, NM-2, NM-3, NM-4, NM-7 and NM-8 are RESOLVED; NM-5 and NM-6 are RESOLVED_WITH_RESIDUAL** (two nonblocking Minor residuals, stated with scope below). **0 UNRESOLVED.** New findings: **0 Fatal, 0 Major, 2 Minor**.

**The three false greens of the 1.1.1 review are closed.** Every probe that was a false green before now rejects with a *semantic* code and not merely with the frozen hash notice: the unbound scene-hash alias (P01) and a permuted `lvw_scene_hash()` argument list (P02) now exit 1 with `E_SCENE_HASH_MAPPING`, and the non-canonical Scene DTO on the new `GET /api/v1/scenes/{id}` (P05) now exits 1 with `E_SCENE_GET_ENVELOPE`. This recheck additionally exercised a second, different call-site permutation (P30), a second formerly unpinned alias (P31), two success-envelope *shape* mutations (P32, P37), three nested malformed inputs (P33, P34, P35), the two degraded modes (P25, P26) and the pin modes (P27, P28, P29, P40, P41) — 23 probes in total, one positive control.

**The traceability gaps are closed.** A degraded run is no longer byte-identical to a full run, and the two degraded modes are distinguishable from each other and from the full run (`VALIDATION:` and `NOTE:` lines); every run records the expected default pin, the computed actual pin and whether the pin was overridden, and an overridden pin is marked `NON-AUTHORITY`; a malformed input yields a deterministic `E_*` on stdout with a non-zero exit instead of an uncaught traceback with an empty stdout, and a missing input yields a clean `INPUT_ERROR` on stdout with exit 2.

**The two mandatory runs pass.** `python3 -B tools/verify_v1_plan.py` exits 0 with a stdout **byte-identical** to the implementation's own hash-bound log (`4a6b877a…`), and `python3 -B -m pytest tools/test_verify_v1_plan.py -q` exits 0 with **233 passed**; the pytest stdout is identical to the candidate's apart from the wall-clock line.

**Two accuracy defects, both Minor and nonblocking.** The candidate commit message splits the 233 tests as "165 carried + 68 new"; the independently collected split is **163 carried + 70 new node ids** (NM-9). The same commit message states that `FROZEN_DOMAIN_ENTRY_KEYS` "is now used instead of being dead code"; the constant is still referenced by no check (NM-10).

**Nothing product-level was granted.** The product coordinate stays `R1 / WAIT_HUMAN`, the `621b1bf` experience signature is still absent, the samples stay `NOT_MATERIALIZED_NOT_FROZEN`, the MS cases stay `NOT_RUN`, the V1/V2/V3 denominators stay 29/38/47, and this offline D0 packet is **not** product Gate 0.

---

## 1. 复核方法（与实现测试**不镜像**）

本窗口**没有**复用实现者的测试思路；上一轮（设计 1.1.1）的探针 harness 只按“版本 / 清单 / pin 变更”做最小适配，**保留原有 oracle 期望**，并保留探针变更的来源说明。

| 工具 | 作用 | 位置 |
|---|---|---|
| `checks/probes.py` | 23 个独立负例/正例探针，跑**真实 CLI**（`subprocess` 调 `tools/verify_v1_plan.py`），每个探针用**独立 TemporaryDirectory 副本** | `checks/probe-run.log`、`checks/probe-results.json` |
| `checks/recompute.py` | 用复核者自己的代码**重算** NM-1/NM-2/NM-5/NM-6（不把 checker 当判定器；仅以只读方式 import 其 domain engine 做**双实现互证**） | `checks/recompute-results.json` |
| `checks/test_diff.py` | 用 AST 比对 1.1.1 与 1.1.2 两版测试**函数体**，核对携带用例是否被删改 | `checks/test-diff-results.json` |
| `checks/fence.py` | before/after 源码围栏（25 owner + 10 payload + 2 candidate code） | `checks/hash-fence-before.txt`、`checks/hash-fence-after.txt` |
| `checks/mandatory_runs.py` | 两条强制命令，各自在**全新临时根**中执行 | `checks/mandatory-*.log` |

**关键约束的遵守方式**

- 只读：owner 树、产品源码、合同、计划、manifest、packet 全程只读；语义负例一律在**临时副本**上做，且按上一轮的做法**只重冻副本里的围栏**（重算被改文件在 spec manifest 里的哈希、重建 D0 payload manifest、并把该副本的新 pin 显式传给 checker）。**从未改写 owner 哈希或源码**。
- 负例语义化：探针在“围栏已重冻”的模式下被拒 ⇒ 只可能是**规则**拒绝，而不是冻结哈希发现了改动。哈希层证据单独用 `fence=off` 模式取证。
- 不使用通配 `rm`、不使用共享标记文件；每个探针一个独立临时目录，结束即由 `TemporaryDirectory` 回收。
- 前一轮失败证据（`d0-review/design111/**`、`d0-worker/design11/**`、`d0-worker/design111/**`、`history/**`）**逐字节保留**：`git diff 88aab8b 2ec04c6 -- reports/v1-redesign/d0-review/design111` 为空。

---

## 2. 强制运行（隔离临时根，原始 stdout/stderr/exit/哈希全留）

| 命令 | exit | 结果 | stdout sha256 |
|---|---|---|---|
| `python3 -B tools/verify_v1_plan.py`（默认 pin，全能力） | 0 | `RESULT: PASS (V1=29 V2=38 V3=47; MS01-MS08 once and NOT_RUN; …)` | `4a6b877a46b65e05aa78d263bbf7cf844052eff94c62e7ddd72fa0aa96ecc7c9`（与候选自绑定日志**逐字节相同**） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0 | `233 passed` | `b082c174241a9a624fa66a587df8506d827f8bed8fbeeef8e4139a3ede3a3d06`（与候选 `ba0ed530…` 仅差墙钟行 `in 26.81s` / `in 26.60s`） |

补充只读校验（复核者自跑，`verify_pack` 为文档/合同校验，非产品验收）：`verify_governance` exit 0 `errors [] failed 0`（sha `e8927ccb…`）；`verify_pack` exit 0 `failed 0`（见 §5 NM-7 关于 7530/7531 一行之差）。

强制 checker 的 stdout 现在**自带可追溯信息**（这也是 NM-4/NM-8 的落点）：

```
VALIDATION: metaschema_check=jsonschema frame_instance_probe=jsonschema frame_sample=present
PIN: mode=default (frozen stage command pin) expected_default=181c08ee… actual=181c08ee…
RESULT: PASS (V1=29 V2=38 V3=47; MS01-MS08 once and NOT_RUN; …)
NOTE: design 1.1.2 (consolidated correction of NM-1..NM-8, still pending an independent recheck): … scene hash aliases 11, SQL call sites 2 x 11 arguments; spec fence 25 files; D0 payload inventory 10 files.
```

---

## 3. NM-1..NM-8 逐条独立结论

| 编号 | 1.1.1 严重度 | 本轮结论 | 决定性证据 |
|---|---|---|---|
| NM-1 | Major | **RESOLVED** | 11 个别名全量绑定；2 处 call site × 11 参数顺序由复核者自写解析器独立重算一致；P01/P31（别名）、P02/P30（调用点置换）均 exit 1 `E_SCENE_HASH_MAPPING` |
| NM-2 | Major | **RESOLVED** | 新 GET 的 envelope 与 canonical PUT 200 envelope 逐字段相等、`data.$ref` = `#/components/schemas/Scene`、38 个 canonical operation 零改写、零替换；P05/P32/P37 均 exit 1 `E_SCENE_GET_ENVELOPE` |
| NM-3 | Major | **RESOLVED** | 6 个畸形输入均得到确定性 `E_*` + 非零退出 + stdout/stderr **无 traceback**；缺输入得到 stdout 上的 `INPUT_ERROR` + exit 2 |
| NM-4 | Minor | **RESOLVED** | 降级 run 不再与完整 run 字节相同；两个降级模式**彼此也不同**并各自声明被跳过的覆盖 |
| NM-5 | Minor | **RESOLVED_WITH_RESIDUAL** | 规则文本已有唯一读法；复核者独立重算冻结示例**逐字节一致**；残余：`FROZEN_DOMAIN_ENTRY_KEYS` 仍无任何规则引用（见 NM-10） |
| NM-6 | Minor | **RESOLVED_WITH_RESIDUAL** | 声明式引擎覆盖四类证据×两个域；复核者**独立实现**同一规则，两实现对同一 bundle **三域逐字节一致**、零错误；残余见下 |
| NM-7 | Minor | **RESOLVED** | 旧收据/旧日志**逐字节保留**（旧收据仍写 7408，其绑定日志仍写 7475）；新收据追加更正并绑定其自身日志（7530），所有数字由脚本从原始日志提取 |
| NM-8 | Minor | **RESOLVED** | 每条 run 记录 expected/actual/mode；显式覆盖标 `NON-AUTHORITY`；1.1.1 / 1.1 / 1.0 旧 pin 仍被拒（P29/P40/P41） |

**NM-6 残余的范围说明（不扩 D0 范围）**：owner 的 1.1.2 纠偏边界把 NM-6 限定为“**离线声明符合性**”，并要求四类证据与两种路由都有确定性负例；本轮复核确认了声明唯一、规则可实现且**两套独立实现一致**，但也如实指出：CLI 守卫只对**冻结示例**（一个 character 源）重算引擎，四类/两域的负例位于候选**自带的单元测试**中，复核者不把实现者自己的测试当作独立保证；产品实现里的错路由不会被本 D0 工具拦下。**D0 包内没有运行时适配器、也没有产品侧 `lvw_scene_hash`，二者缺席是已知的产品实现工作，不是本轮 D0 缺陷，也不得据此要求在本轮实现。**

**NM-5 残余的范围说明**：规则本身已被“整串精确比对 + 示例重算”双重保护，功能上没有缺口；未使用的常量是外观问题，不阻塞。

---

## 4. 探针结果（23 个，非穷举）

| 探针 | 目的 | exit | 关键 finding |
|---|---|---|---|
| P00 | 正例控制：未改副本 + 默认 pin | 0 | `RESULT: PASS` |
| P01 | NM-1 重放：未冻结别名 media_sha256 被改绑 | 1 | `E_SCENE_HASH_MAPPING` |
| P02 | NM-1 重放：call site PTS 参数置换 | 1 | `E_SCENE_HASH_MAPPING` |
| P05 | NM-2 重放：新 Scene GET 返回别的候选组件 | 1 | `E_SCENE_GET_ENVELOPE` |
| P22 | NM-3 重放：`metadata_only` 为 list | 1 | `E_OVERLAY_METADATA_SHAPE` |
| P23 | NM-3 重放：`add_response_headers` 为 list | 1 | `E_OVERLAY_HEADER_SHAPE` |
| P24 | NM-3 重放：候选 schema 非法正则 | 1 | `E_SCHEMA_PATTERN` |
| P30 | **新增**：另一处 call site 置换（前两参互换） | 1 | `E_SCENE_HASH_MAPPING` |
| P31 | **新增**：另一 formerly-unpinned 别名 editor | 1 | `E_SCENE_HASH_MAPPING` |
| P32 | **新增**：成功 envelope 多一个属性 | 1 | `E_SCENE_GET_ENVELOPE` |
| P33 | **新增**：嵌套 metadata 值为 list | 1 | `E_OVERLAY_METADATA_SHAPE` |
| P34 | **新增**：嵌套 header status map 为 list | 1 | `E_OVERLAY_HEADER_SHAPE` |
| P35 | **新增**：候选 schema 嵌套容器非对象 | 1 | `E_CHECK_SHAPE` |
| P37 | **新增**：成功 envelope 少一个 required | 1 | `E_SCENE_GET_ENVELOPE` |
| P25 | NM-4 重放：无 jsonschema（降级） | 0 | `metaschema_check=structural-fallback`；stdout 哈希与 P00 **不同** |
| P26 | NM-4 重放：无保留帧样本（降级） | 0 | `frame_instance_probe=skipped-no-sample`；与 P00/P25 **三者互不相同** |
| P27 | NM-8：显式 pin 覆盖 | 0 | `mode=explicit-override (NON-AUTHORITY …)` |
| P28 | NM-8：同一副本走默认 pin | 1 | `E_D0_PACKET_MANIFEST_PINNED`；`mode=default` |
| P29 / P40 / P41 | NM-8：1.1.1 / 1.1 / 1.0 旧 pin | 1 | `E_D0_PACKET_MANIFEST_PINNED` |
| P38 | NM-6：scene 域 ref 被改绑 | 1 | `E_DOMAIN_MAPPING` |
| P39 | NM-6：示例同时携带另一域条目 | 1 | `E_DOMAIN_MAPPING` |

> 负例 exit≠0 是**守卫生效的证据**，不是复核失败；本次复核的正例（强制 checker、强制 pytest）均 exit 0。

---

## 5. 计数核对与两条新 Minor

**(a) 上一轮计数差异（按 owner 要求在新收据中核对，旧字节不动）**

- 1.1.1 的 `findings.json` 实际数组 = **3 Major + 5 Minor + 0 Fatal = 8 条（NM-1..NM-8）**；
- 1.1.1 报告 summary 写 **6 Minor**，与其自身数组矛盾；
- 1.1.2 裁决 `derived_counts {Fatal 0, Major 3, Minor 5}` + `review_summary_minor_count 6`，并要求“保留原报告”；
- 1.1.2 实施收据 `finding_counts` 同样记 **3 Major + 5 Minor**，并说明差异已核对、未凭空制造第九条；
- 本轮：`design111/findings.json` 与 `receipt.json` **逐字节未改**（`git diff 88aab8b 2ec04c6 -- reports/v1-redesign/d0-review/design111` 为空），更正后的派生计数**追加**在本轮收据中。

**(b) 233 条测试的真实拆分（不信任 prose 算术）**

| 项 | 复核者独立收集 |
|---|---|
| 1.1.1 树收集到的 node id | 164（164 个测试函数，无参数化） |
| 1.1.2 树收集到的 node id | 233（223 个测试函数，其中 1 个参数化出 11 个 id） |
| 被删除的函数 | 1：`test_d0_packet_pin_is_the_owner_supplied_111_digest` |
| 其直接替代 | `test_d0_packet_pin_is_the_owner_supplied_112_digest`（同一 oracle，只是冻结 pin 从 `04d3bfb4…` 变为 `181c08ee…`） |
| 携带函数 | 163（159 个逐字节相同，4 个有变更） |
| 变更的 4 个携带函数 | ①冻结 spec 围栏计数 24→25（oracle 保留：与冻结常量一致）；②合并用例由“仍通过”**加强**为“被 `E_SCENE_GET_ENVELOPE` 拒绝且合并守卫不报”（原 oracle“overlay 不改写 canonical operation”以 `E_OVERLAY_BASE_MUTATED` 不出现的方式保留）；③④两个旧 pin 用例改用 helper（oracle 保留） |
| 新增函数 / node id | 60 个新函数 → 70 个新 node id（59 个各 1 个 + 别名参数化 11 个） |
| **结论** | **163 携带 + 70 新 = 233**；候选 commit message 的 “165 carried + 68 new” **拆分错误**（合计对、拆分错）→ **NM-9 (Minor)** |

**没有任何负例被删除或削弱**；旧 pin、旧 alias、旧 envelope、旧 regex、旧降级区分类负例全部仍在。

**(c) NM-10 (Minor)**：候选 commit message 称 `FROZEN_DOMAIN_ENTRY_KEYS` “is now used instead of being dead code”，但 `tools/verify_v1_plan.py:494` 定义的该常量**不被任何规则引用**，全包唯一引用是 `tools/test_verify_v1_plan.py:3130-3131` 的自指断言。规则本身已由整串精确比对 + 示例重算保护，功能无缺口；该条与 NM-5 残余同源，只计一次。

---

## 6. 源码围栏、owner 未改与基线不变

- 围栏覆盖 **25 个 owner 文件 + 10 个 D0 payload 文件 + 2 个候选代码文件**（另含旧 R1 payload manifest 与 3 个 canonical 合同）：
  `checks/hash-fence-before.txt` 与 `checks/hash-fence-after.txt` **逐字节相同**（diff 为空）。
- 候选相对 owner 权威 `3af4463` 的差异**只有** `tools/verify_v1_plan.py`、`tools/test_verify_v1_plan.py` 与 `reports/v1-redesign/d0-worker/**`；owner 的合同/计划/文档/manifest **无一条被候选改写**。
- 25 个 owner 文件哈希与 owner spec manifest 声明**逐条一致**（复核者独立重算）；10 个 payload 文件与 D0 payload manifest **逐条一致**。
- canonical 基线不变：`contracts/openapi.json` `cd9df1bd…`、`contracts/lvw.schema.json` `4c0e3383…`、`contracts/storage.sql` `a2204821…` 与 `legacy-gates-before-change.json` 记录一致；旧 R1 packet manifest `38ca0ae5…` 且其 10 个文件全部按声明哈希成立。
- 分母与 MS 状态不变：`V1=29 V2=38 V3=47`；`MS01-MS08 once and NOT_RUN`；`checkpoint 65+ 7=72 actions / 21600 s`；`parent deadline 450*n+90<=5490`。
- 候选代码哈希独立重算：`tools/verify_v1_plan.py` `6dfbaaed…`、`tools/test_verify_v1_plan.py` `da75a950…`，与实施收据一致。
- 复核只写 `reports/v1-redesign/d0-review/design112/`；`git status` 除本目录外无改动。

---

## 7. 限制与未授予事项

- 这是**离线设计与工具**复核：不是产品验收、不是产品 Gate 0、不是 Stage PASS、不是人工签署。
- 产品坐标仍为 `R1 / WAIT_HUMAN`（`plans/execution-control.json` coordinate `{stage_id R1, state WAIT_HUMAN}`）；`621b1bf` 体验签署仍缺；样本状态 `DESIGN_ALLOCATION_ONLY_NOT_REAL_FIXTURES`（即 NOT_MATERIALIZED_NOT_FROZEN）；MS 用例与 V1-M1 阶段仍 `NOT_RUN`。
- checker 只校验计划与合同的**结构**：它不跑产品代码、不开产品数据库、不产生运行时 ETag、不物化任何样本；候选迁移 SQL **只作文本解析，从未执行**。
- `lvw_scene_hash` 的 DDL **不在冻结包内**，场景哈希只能对照声明的散文规则校验，无法对照已发布函数；独立夹具哈希只证明规则**确定性**（复核者自建夹具自算：`91133a6c…` → 匹配强 tag 形态）。
- N5/NM-6 只作**离线声明符合性**结论：本 D0 包内没有运行时适配器，结论不证明产品输出。
- 23 个探针是**有界独立选取**，不是对 checker 输入的穷举；未测输入未被宣称干净。
- `verify_pack` 在复核者重建的候选树上得 **7531/0**，与候选自绑定日志的 **7530/0** 差一行，属该工具“多数检查按 MANIFEST.sha256 逐行一项”的已知效应；**该收据数字以它所绑定的日志为准**，历史 7475 不受影响。
- 实现者的 provider/model 身份为**自报且未独立验证**；实现者的 provider 身份同样自报未验证。
- 上一轮全部失败证据保留未删。

---

## 8. 交付与下一步

- 本轮交付：`reports/v1-redesign/d0-review/design112/review.md`、`findings.json`、`receipt.json` 与 `checks/**`（围栏、强制运行原始日志、23 探针 harness + 结果、复核者重算、测试函数体比对）。
- **只裁决 D0 的是 Codex**；本复核不合并到父分支、不 push、不签署。
- 仍需实施者处理的两条 Minor（NM-9 commit message 的测试拆分、NM-10 commit message 的常量表述）属文案准确性；NM-5/NM-6 残余已在 `findings.json` 中带范围与理由记录，均不阻塞 D0 收口，但也不应被当作“已清零”。
