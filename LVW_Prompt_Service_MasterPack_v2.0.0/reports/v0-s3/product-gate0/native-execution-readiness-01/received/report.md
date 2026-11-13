# S3 真实后端准入准备 01：实现报告（只读源码/证据，一次交付）

> 实现者：Claude Code（唯一实现者，**未派生任何 Agent**）
> 状态：**READY_FOR_REVIEW / 提案未冻结**。不签 Stage PASS，不签产品 Gate0，不自签开工。
> 候选代码 `b95de076f37e64d321629c065e5531eba8a5250a`；交付 `13e77492361648dc90a414f7fd37f0bb8b8c3634`；
> impl HEAD `13e77492361648dc90a414f7fd37f0bb8b8c3634`（与合同期望一致）。
> 范围合同：`reports/v0-s3/product-gate0/native-execution-readiness-01/contract.md`
> （sha256 `fe18e17162baeba18e8794478fe851dedb9c7abc4ca0305e918682755a049834`）
> 最新离线组合接受决定：`.../production-composition-correction-review-04/root-decision.json`
> （sha256 `e8abd8c4505a03ff36eca0bfe3765d60891578b260e44da8942d557ea44de000`）

---

## 0. 本包做了什么 / 没做什么

**做了**：只读 Git、rg、源码、报告、AST 级行号核对与 sha256 计算；产出 5 份 NEW 事实材料，
供 root 冻结后续"真实后端实现合同"。

**没做（逐条）**：未改任何产品代码、合同、`plans/execution-control.json`、control 或 MANIFEST；
未导入候选、未跑 pytest、未跑任何 fixture 进程；未启动服务 / 模型 / GPU / native / 浏览器 / 媒体；
未读原账本；未探测端口与进程；未复跑任何已闭合的测试或负例；未派生 Agent；
未 clean / reset / 批量 add；既有改动工件原样保留。

**只写了一个新目录**：`reports/v0-s3/product-gate0/implementation-native-execution-readiness-01/`

| 交付物 | 内容 |
|---|---|
| `readiness.json` | 机器可读的事实登记：候选/授权/坐标、四个拒绝点、22 段 owner 链的三类分界、产品十二键现状、预算、未证明清单 |
| `owner-call-map.md` | 逐函数 owner 调用链（带 file:line 与调用边）与三桶分界总表 |
| `proposed-implementation-packet.md` | 最小下一实现包（N1–N4）、本机有限 run 准备清单、优先路线与依赖、实现者/独审者候选提示词、验收 Oracle 候选 O1–O10 |
| `I24-evidence-overlay.json` | 固定 I01–I24 的"已证范围 + 缺口 overlay"，冻结矩阵一字未改 |
| `report.md` | 本文 |

---

## 1. 合同五项的落点

| 合同条目 | 落点 |
|---|---|
| ① 读 control/docs24/S3 packet/Gate0/COMPLETE03/离线合同/最新独审决定；列 I01–I24 已证范围与缺口 overlay | `readiness.json`（治理读、冻结分母、预算）+ `I24-evidence-overlay.json`（24 行逐条：production_path / test_drive / oracle / negative / terminal / cleanup_proof / proven_scope / gap） |
| ② 在候选代码逐函数追踪整条 native 链，分"已接线 / 可复用未接线 / 缺生产 owner" | `owner-call-map.md`（含顶层调用图与 22 段分表） |
| ③ 最小下一实现包：唯一 owner/允许文件/复用接口/封存与父可信 admission 来源/父的 Windows 后代权力/最小接口与失败码/保持 10800·600·21600 与资源门限 | `proposed-implementation-packet.md` §A（A1–A5） |
| ④ 下一轮本机有限 run 准备清单（仅设计）+ 缺信息的最小无副作用核验命令计划 | `proposed-implementation-packet.md` §B（B1–B5） |
| ⑤ 优先路线 + A06/十二项/质量/安装回滚的准确依赖 + 实现者/独审者候选提示词 + 验收 Oracle 候选 | `proposed-implementation-packet.md` §C–§E |

---

## 2. 五个最重要的发现（全部为候选代码事实）

### 发现 1 —— CUSTODY-01（本轮最核心缺口）

能释放 Windows 后代与 GPU 的 owner 是 `tools/v0_s2_driver.py:260-311`（`S2SystemDriver.cleanup`
＋ `_prove_listener_owned` / `_snapshot_descendants` / `_kill_bound` / `_assert_no_new_descendants`），
**它跑在 worker 进程内**。父侧只持有 worker 的 Linux 句柄。
父监督自己就写明：`native_service_cleanup_proven=False`、`native_gpu_release_proven=False`、
`parent_crash_recovery_proven=False`（`tools/v0_s3_supervisor.py:1113-1115`）。

⇒ worker 一阻塞或一退出，父对 Windows 后代**没有任何权力**；"杀掉 WSL 的 Python"**不能**当作
Windows/GPU 已释放。这不是缺陷描述，而是候选代码自己的立场，本包不得软化。
⇒ 关闭它的最小路线是**父侧独立 custody adapter**（提案 N1），不是改已接受的 S2 owner。

### 发现 2 —— ADMISSION-OWNER-01（七份封存文档零生产者）

`verify_native_admission` 需要 `budget_binding / native_custody / gpu_release / install / rollback /
grant / tool_closure` 七份封存文档，且每份要 `status='PROVEN'` ＋严格布尔证明。
全仓唯一写出 `kind='lvw.s3-native-admission/1'` 文档的地方是**测试**
（`tools/test_v0_s3_production_composition.py:247, 925`）。
⇒ 解锁方式**不是**实现者手写 `PROVEN` JSON 或 platform 字符串：验证器恒 `accepted=False`
（`v0_s3_production_controller.py:693-705`），手写只会被挡住。必须是 root 认可**受信任生产者**。

### 发现 3 —— 两个既有 owner 的合同互不兼容（可精确修复）

* **DRIVER-PROTOCOL-01**：`QualityPhase.__init__` 要求 `callable(driver.resource_observer)`
  （`v0_s3_quality_phase.py:992-993`），但 `NativeRuntime.__init__` 里它是 `None`
  （`v0_s2_runtime.py:47`），只有 `start_sampler`（`:193`）才绑定。
  `build_native_driver`（`v0_s3_quality_worker.py:615-643`）**只构造、不启动 sampler**
  ⇒ 按现有代码，它返回的 driver 必然在 phase 构造处抛
  `QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer`。协议其余方法**全部已在**。
* **BINDING-SHAPE-01**：`WorkerContext.binding()` 要求**恰好五键**
  `{candidate_sha, authorization_sha256, ollama_pid, ollama_start_ticks, baseline_gpu_mib}`
  （`v0_s3_quality_worker.py:62-63`），而真实 native owner 写出的 profile 键集与之**都不同**
  （`v0_s2_runtime.py:131-164`），且 `baseline_gpu_mib` 只存在于 warm profile。
  ⇒ 缺一个**投影 owner**。

### 发现 4 —— 两个正确形态的 owner 没有任何生产调用点

`build_native_driver`（worker:615）与 `S3InstalledRuntimeFactory`（`v0_s3_coordinator.py:309`）
的代码**已是正确形态**（前者只从封存的六个 `driver_arguments` 构造 `NativeRuntime`；
后者继承已接受的 `InstalledPackageRuntimeFactory` 未改一份，只加一个增量键与一次根绑定）。
但它们在 S3 生产路径上**零调用点**（全仓引用只在测试里）。
⇒ N2 是**接线**，不是重写；这是本轮最低风险的收益点。

### 发现 5 —— 现状被正确地"锁死"在四处

`controller:2631`、`worker:596`、`verifier:693-705`、`supervisor:1113-1115` 四处拒绝/未证明声明，
两侧同码、且都自述。这四个点是本候选**已有**的正确事实，任何"先解锁再补证据"的做法都应被拒绝。

---

## 3. 建议的优先路线（详见提案 §C）

1. **阶段 1（先做）**：`N1 父侧 custody` → `N2 native 装配与五键 binding` → `N3 admission 生产者接线`
   → `N4 一次真实单链`（1 行 / 1 次模型动作 / 1 次真实账本 debit / 1 次真实 Windows cleanup）。
   阶段 1 完成后**仍然不能**宣布任何产品门。
2. **阶段 2**：固定全分母（10 图 + 6 视频，冻结集 `quality-execution-inputs.frozen.json`）；
   **同根因合并**：`DRIVER-PROTOCOL-01` + `BINDING-SHAPE-01` 一次做完（同根因＝native 装配从未接线
   且两 owner 合同互不兼容）；`ADMISSION-OWNER-01` + `CUSTODY-01` 一次做完（同根因＝收据无受信任生产者）。
3. **阶段 3**：A06 真实隔离 / install / rollback / WebP / 独立质量分 / 人签。
   **依赖**：A06 与 install/rollback 只依赖"部署 owner 被接线"（N2 第 2 步），**可早于**阶段 2；
   真实质量、独立分、WebP 依赖阶段 1–2。

**不得重跑已闭合负例**：I01–I24 的离线负例与 correction-04 的 20 节点定向证据已闭合；
只对实际改动的 hook/接线跑必要回归。correction-04 的 20 节点覆盖的是**离线 seam 的终态收口**，
**不覆盖**任何 native 进程、Windows 后代或 GPU ⇒ 不得用它替代 N1/N4 的证据。

---

## 4. 本轮明确**不**主张的事

* 不主张任何 native 能力已存在；四处拒绝点原样保留。
* 不主张"杀 WSL Python"＝Windows/GPU 已释放。
* 不主张 `S3InstalledRuntimeFactory` / `build_native_driver` 已接线。
* 不主张旧 13 fixture 或合成 16 行可替代 native / 质量证据。
* 不主张任何 I01–I24 或 V0-A01..A12 已通过；冻结矩阵
  `reports/v0-s3/product-gate0/s3-integration-acceptance-01.json` 一字未改，24 项仍为 `NOT_RUN`。
* 不主张 10800/600/21600 或任何生产资源门槛可以放宽。
* 不主张剩余预算：134..143 是**设计数**（`remaining-integration-budget-02.json`），本包**未读原账本**，
  实际剩余必须由 root 实测重算（COMPLETE03 全局 1024 模型动作 / 24 有效完整槽 / 172800 s，历史计入不清零）。
* 不请求对 COMPLETE03 已覆盖范围重复人批；不激活任何执行。
* **FIRST429 → 立即 WAIT_BUDGET 停**（本轮未触发）；审批拒绝或超时即停交接，不绕过。

---

## 5. 交给 root 的三个待裁决点（不是阻塞项，是必须由 root 定的选择）

1. **N1 的形态**：接受"父侧独立等价实现"（新文件，零改动已接受 owner），
   还是授权在 `tools/v0_s2_driver.py` 抽出共享 custody 原语（改动已接受 owner，风险更高）？
   提案默认前者。
2. **协议版本**：若 custody 交接需要新事件，必须冻结新的 `lvw.s3-supervision/2`；
   不得把新事件塞进现有封闭事件集合。
3. **native 轮的 I22 表述**：离线轮"I22＝零真实模型/账本动作"，native 轮必须**产生**真实动作，
   该义务在 native 轮的表述需 root 重新冻结，不能沿用。

---

## 6. 复核者可直接核验的锚点

```sh
git -C <repo> rev-parse HEAD                 # 13e77492361648dc90a414f7fd37f0bb8b8c3634
git -C <repo> diff --stat b95de076f37e64d321629c065e5531eba8a5250a -- tools/ lvw/ LVW_V0_RuntimePatch/   # 空
sha256sum tools/v0_s3_production_controller.py tools/v0_s3_quality_worker.py tools/v0_s3_quality_phase.py \
          tools/v0_s3_supervisor.py tools/v0_s3_coordinator.py tools/v0_s2_runtime.py tools/v0_s2_driver.py \
          tools/v0_s3_budget_authority.py tools/local_program_authority.py lvw/backend/app/native_runtime.py
```

源文件实测 sha256（本包读取时刻，候选一致）：

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_production_controller.py` | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38` |
| `tools/v0_s3_quality_worker.py` | `e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592` |
| `tools/v0_s3_quality_phase.py` | `90552ea113ccf53a2a1cedff3e3f399642ad932bf0f71bb1f9a57e1adb6e8789` |
| `tools/v0_s3_supervisor.py` | `7d210429e70761cea633e8f2e64d8a1f01709930068a21de5cbc3c5a519ce6d8` |
| `tools/v0_s3_coordinator.py` | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c` |
| `tools/v0_s2_runtime.py` | `a97ea20d02ed80ab4f99f133dd8162331ddba34662bfdcca637fcade40b4dbd2` |
| `tools/v0_s2_driver.py` | `72883e2fa0c252aef7655708f40ada88a755978d71f632043c8203b53b42afed` |
| `tools/v0_s3_budget_authority.py` | `80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7` |
| `tools/local_program_authority.py` | `677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787` |
| `lvw/backend/app/native_runtime.py` | `16bf3e6396f9548312f92007eebbda55a448f0bdc6bab4a10afd71179b231a85` |

---

## 7. 终态

* 本包状态：**READY_FOR_REVIEW**（事实材料齐备，提案未冻结，未执行任何事）。
* 实现者**未**宣布 Stage PASS、**未**宣布产品 Gate0、**未**代替 root 冻结任何架构或合同。
* 下一步：root 审核本包并冻结"真实后端实现合同"；冻结前**不激活执行**。
