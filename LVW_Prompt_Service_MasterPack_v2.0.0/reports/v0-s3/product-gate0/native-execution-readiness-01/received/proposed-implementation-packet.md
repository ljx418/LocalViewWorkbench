# S3 真实后端准入准备 01：最小下一实现包建议（提案，未冻结、未执行）

> 本文是**给 root 的事实性提案**，不是开工令。架构、公共合同、状态机与验收分母由 root 最终裁决。
> 提案未冻结 → **不激活执行**。本包没有执行任何测试、服务、模型、GPU、native、浏览器、媒体，
> 没有读原账本，没有探测端口/进程，没有改动任何产品代码、合同、control 或 manifest。

---

## A. 最小下一实现包：四个串行子包，一个 owner 一个文件

现状决定了这个包的形状（依据见 `owner-call-map.md`）：

| 缺口 | 既有 owner 状态 | 结论 |
|---|---|---|
| CUSTODY-01 父对 Windows 后代/GPU 的权力 | 释放代码在 `tools/v0_s2_driver.py:260-311`，但**跑在 worker 进程内** | 需要**新的有限内部 adapter**（父侧），不动已接受 owner |
| DRIVER-PROTOCOL-01 `resource_observer` 装配 | 协议方法齐备，顺序不对 | 需要**接线**，不需新协议 |
| BINDING-SHAPE-01 五键 binding 投影 | 两个既有 owner 键集不兼容 | 需要**新的投影 owner**（薄） |
| ADMISSION-OWNER-01 七份封存文档 | 验证器齐备，**零生产者** | 需要 root 认可**受信任生产者**，并接线 |
| `build_native_driver` / `S3InstalledRuntimeFactory` 无调用点 | 代码已是正确形态 | 只需**接线**，不改形态 |

### A1 子包 N1（父侧 native custody adapter）——新 owner

* **唯一 owner**：`tools/v0_s3_native_custody.py`（**新文件**）。
* **允许改动**：`tools/v0_s3_native_custody.py`（新）；`tools/v0_s3_production_controller.py`
  仅新增"在父侧 arm/release custody"的两处调用与收据字段，**不改**其拒绝点、不改其状态机、不改其
  十二项聚合、不改 `verify_native_admission`。
* **禁止改动**：`tools/v0_s2_driver.py`、`tools/v0_s2_runtime.py`、`tools/v0_s3_quality_phase.py`、
  `tools/v0_s3_supervisor.py`、`tools/v0_s3_quality_worker.py`、`tools/v0_s3_coordinator.py`、
  `tools/v0_s3_budget_authority.py`、`tools/local_program_authority.py`、
  `LVW_V0_RuntimePatch/**`、任何 contract / control / manifest / 分母。
* **复用接口**（不改其语义，只调用）：
  * `tools/v0_s2_driver.py:147` `_kill_bound(pid, start_ticks, allow_absent=…)` 的**同一套 PowerShell 语义**：
    `Get-Process -Id` + `SafeHandle` 钉住 + `StartTime.ToUniversalTime().Ticks` 与封存 ticks 比对 +
    `Kill()` + `WaitForExit(5000)` + 结构化 stop receipt。**本包不复用该函数本身**（它是 driver 实例方法，
    且 `_prove_listener_owned` 依赖 worker 内的 wrapper 句柄），而是在新 adapter 中**按同一规则重实现**，
    并在文件头显式声明"这是 S3 父侧 custody 的独立实现，不声称是 S2 accepted owner 的替代或复用"。
    → **root 必须裁决**：接受"父侧独立等价实现"，或授权在 `tools/v0_s2_driver.py` 抽出共享的
    custody 原语（那是对已接受 owner 的改动，风险更高）。**默认取前者**。
  * `reports/v0-s1/wp-s1-03-phase-a/live_probe.py:149-160` 的 wrapper 形态（**只读参考，不改**）。
  * **最接近的既有原语**：`lvw/backend/app/native_runtime.py:9-31`（`prepare`/`proof`）+
    `lvw/backend/app/runtime.py:97-100, 135-160`（`OllamaRuntime`）——Windows 侧持有原生句柄与
    `pid + birth_ticks` 并写 owner 文档，WSL 侧只写 stop nonce 并回验终态证明，终态证明缺失即
    `RESOURCE_RELEASE_PENDING`。它**只覆盖 11434 的单个 Ollama**，没有 Comfy 8191 owner、
    没有 GPU 采样、没有 Windows 后代快照，且绑在 async FastAPI 运行时上。
    → N1 **参考**它的"Windows 侧持句柄 + nonce 停止 + 终态证明"形态，
    但**不得**把它当作 S3 的 Comfy+Ollama+GPU 链，也不得改动它（它在 V1 产品路径上）。
* **封存来源（父可信 admission 的来源）**：
  * **custody record**：worker 在**真实**启动 Comfy(8191)/Ollama(11434) 之后，把
    `{run_id, candidate_sha, authorization_sha256, nonce, listener:{pid, listener_process_start_ticks,
    wrapper_pid, wrapper_process_start_ticks, executable, port}}` 写进**封存运行根**内的固定引用
    （建议 `temp/s3-native-custody/<run_id>.custody.json`，排他写，父按 sha 读取）。
  * **父不信任 record 的数值**：父在**任何终止动作之前**自己用 CIM + `Get-Process.SafeHandle` +
    `StartTime` ticks + 归一化可执行路径**重证**（等价于 `v0_s2_driver.py:118-145` 的规则）。
    record 只提供**被验证对象**，不提供**结论**。
  * **平台字符串不是 admission**：不得以 `platform == 'win32'`、布尔标志或自算 hash 解锁任何收据。
  * **禁止自写 PROVEN**：adapter 只能从**自己的实测事实**生成收据字段；`status='PROVEN'` 的文档必须
    由**root 认可的受信任生产者**签发，验证器侧（`v0_s3_production_controller.py:567-705`）保持恒不接受。
* **最小接口 / 状态 / 失败码**（提案）：

```python
class NativeCustody:
    # 状态机（单向）：UNBOUND -> ARMED -> (RELEASED | UNKNOWN)
    def arm(self, *, record_reference: dict) -> dict: ...
    def re_prove(self) -> dict: ...
    def release(self, *, reason: str) -> dict: ...
    def fact(self) -> dict: ...
```

| 失败码（稳定） | 含义 |
|---|---|
| `CUSTODY_RECORD_ABSENT` | 封存根内没有 custody record（worker 未到那一步就死了） |
| `CUSTODY_RECORD_SEAL_MISMATCH` | record 字节与父持有的 sha256 不符 |
| `CUSTODY_RECORD_IDENTITY_MISMATCH` | record 的 run/candidate/authorization 与本轮不符 |
| `CUSTODY_LISTENER_NOT_PROVEN` | 父自证失败（无监听/端口不是授权端口/可执行路径不符） |
| `CUSTODY_PID_BIRTH_REUSED` | `StartTime` ticks 与封存值不符 → 拒绝终止 |
| `CUSTODY_STOP_RECEIPT_INVALID` | stop receipt 结构/类型/时钟不合法 |
| `CUSTODY_DESCENDANT_SNAPSHOT_INVALID` | Windows 后代快照结构不合法（深度/上限/出生链） |
| `CUSTODY_DESCENDANT_EXIT_UNPROVEN` | 后代未确认退出 |
| `CUSTODY_NEW_DESCENDANT_OWNERSHIP_UNPROVEN` | 快照与停止之间出现新后代 |
| `CUSTODY_LISTENER_STILL_PRESENT` | 8191/11434 仍有监听 |
| `CUSTODY_RELEASE_TIMEOUT` | 有界释放超时 |
| `CUSTODY_RELEASE_UNKNOWN` | worker 在 custody 封存前退出 → 状态 `UNKNOWN`，**不是 PROVEN** |

* **硬边界**：`UNKNOWN` 永不升级为 `PROVEN`；失败时运行保持 `UNKNOWN_RETAINED`、根与预约保留、
  `refund/resend/archive_allowed=False`；adapter **不启动任何服务**、**不按名字选进程**、
  **不枚举无关进程**、**不造预算**、**不造新平台**。
* **明确禁止的捷径**：父只杀掉 WSL 的 Python **不等于** Windows/GPU 已释放
  （现状证据：`v0_s3_supervisor.py:1113-1115` 自己声明 `native_service_cleanup_proven=False`）。

### A2 子包 N2（native 装配与五键 binding 投影）——接线 + 薄投影

* **唯一 owner**：`tools/v0_s3_quality_worker.py`（已存在 owner，只在其上接线）+ 一个**新**薄投影
  （建议放在同一文件的独立函数，或新文件 `tools/v0_s3_native_binding.py`，二选一由 root 定）。
* **真实 native 顺序（必须是这个顺序）**：
  1. `NativeRuntime.preflight`（`v0_s2_runtime.py:59`）→ 8191/11434 未被占、无目标进程；
  2. 部署 owner `S3InstalledRuntimeFactory.prepare_default/prepare_warm`
     （`v0_s3_coordinator.py:309-344`）→ **第一次排他**写 profile（含唯一增量键 `s3_budget_binding`），
     并在其**自己验证过的** `owned_run_root` 上 `bind_video_snapshot_root`；
  3. 启动 Comfy(8191) 与 Ollama(11434)，取得**原句柄**与**原 birth**（`v0_s2_runtime.py:167` /
     `v0_s2_driver.py:118-145`）；
  4. **启动真实 sampler**，从而绑定 `resource_observer`（`v0_s2_runtime.py:193`）——
     这一步必须在构造 `QualityPhase` **之前**，否则 `QualityPhase.__init__`
     （`v0_s3_quality_phase.py:992-993`）必然抛 `QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer`；
  5. 由**持有真实事实的 driver** 投影出**恰好五键**的 binding 文档并排他写进封存根：
     `candidate_sha, authorization_sha256, ollama_pid, ollama_start_ticks, baseline_gpu_mib`
     （键集必须严格等于 `v0_s3_quality_worker.py:62-63` 的 `BINDING_KEYS`，否则 `WORKER_BINDING_KEY_SET_INVALID`）；
     `baseline_gpu_mib` 只能来自 warm profile（`v0_s2_runtime.py:135` 有 `valid_baseline` 校验）；
  6. 写 custody record（N1 的封存来源）；
  7. 构造 `QualityPhase` 并运行。
* **投影失败码（稳定）**：`BINDING_PROFILE_KEYSET_INVALID`、`BINDING_BASELINE_ABSENT`、
  `BINDING_PID_BIRTH_INVALID`、`BINDING_PROFILE_SEAL_MISMATCH`。
* **复用接口**：`NativeRuntime.write_warm_binding` / `write_native_binding`
  （`v0_s2_runtime.py:131/152`）、`S3InstalledRuntimeFactory._profile_binding_parameters`
  （`coordinator:324`）、`WorkerContext.binding()`（`worker:414`）、`build_native_driver`（`worker:615`）。
* **不改**：phase 的协议检查、阈值、保留上限、原始证据；driver 协议方法名集合。

### A3 子包 N3（admission 受信任生产者接线）

* **唯一 owner**：`tools/v0_s3_production_controller.py`（**只接线，不改验证器**），
  生产者本身分属既有 owner：
  * `native_custody` / `gpu_release` → **N1**（父侧实测）；
  * `budget_binding` → 既有 `S3BudgetBindingProvider`（`coordinator:191`）+ `v0_s3_budget_authority.py`；
  * `install` / `rollback` → 部署 owner（`v0_s3_stage_runtime.py:75` / `v0_incremental_package.py`）的
    **真实** install/rollback 收据（当前无 → 见 §C 依赖）；
  * `grant` → 授权 owner（COMPLETE03 派生 child）；
  * `tool_closure` → 部署 owner 封存的依赖清单。
* **硬约束**：生产者必须是**root 认可的受信任 owner**，实现者不得自写 `status='PROVEN'` 的 JSON，
  不得用 platform 字符串、布尔或自算 hash 代替事实。
  `verify_native_admission` 恒 `accepted=False` 的行为**保持不变**；解锁方式是 root 冻结"接受哪些生产者",
  不是修改验证器。

### A4 子包 N4（单链最小验证的定向证据）——只跑"已接线的那一段"

* 目标：**一次**真实 native 单链（1 行、1 次模型动作、1 次真实账本 debit、1 次真实 Windows cleanup），
  用来证明 N1/N2/N3 的接线成立，**不是**全分母验收。
* 唯一 owner：执行器（root 派生），实现者只交付代码与定向用例。
* **不得**用它替代 16 行质量分母，也不得用它改写任何 I01–I24 或 V0-A01..A12 状态。

### A5 不可动的既有约束（提案明确继承）

| 约束 | 位置 | 提案中的处置 |
|---|---|---|
| phase 截止 10800 s | `v0_s3_supervisor.py:69` | 不变 |
| history 等待 600 s | `:70` | 不变 |
| child 最大 21600 s | `:71` | 不变 |
| 协议 ≤32 KiB/条、≤1024 条、流 ≤256 KiB、证据 ≤8 MiB | `:44-47` | 不变；若 custody 需要新事件，**必须由 root 冻结新协议版本**，不得悄悄塞进现有事件 |
| 生产资源门限（GPU/RAM/温度/P95/零 OOM） | `v0_s2_runtime.py` + `resource_policy.py` | 不变，不以"显存静态余量"重新制造人批 |
| 每 child ≤128 模型动作、全局 1024/24 槽/172800 s | `remaining-integration-budget-02.json`、COMPLETE03 | 不变，不叠加旧额度、不清零 |
| 拒绝点四处 | `controller:2631`、`worker:596`、`verifier:693-705`、`supervisor:1113-1115` | **全部保留**，除非 root 明确冻结新的受信任生产者 |

---

## B. 下一轮本机有限 run 准备清单（**仅设计，不执行，不签人批**）

已覆盖范围在 `AUTH-PROGRAM-V1-COMPLETE-03`（`reports/authorization-program-v1-complete-03.approval.json`，
sha256 `cd919c7fd24c24e2740366ef11998fee1b3302f16700598a3a5f75c6ef1b0821`，ACTIVE）之内，
**不请求对既有范围重复人批**。

### B1 必须先封存的原 hash

| 项 | 值/来源 | 状态 |
|---|---|---|
| 候选 code sha | `b95de076f37e64d321629c065e5531eba8a5250a` | 已知 |
| 交付 sha | `13e77492361648dc90a414f7fd37f0bb8b8c3634` | 已知 |
| impl HEAD | `13e77492361648dc90a414f7fd37f0bb8b8c3634` | 已知 |
| controller / worker / phase / supervisor / coordinator 源 sha | 见 `readiness.json` → 需 root 在冻结时重算 | **需 root 重算** |
| `tools/local_program_authority.py` sha | `677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787`（= `AUTHORITY_HASH`） | 已知 |
| `tools/v0_s3_budget_authority.py` sha | `80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7` | 已知 |
| 工具身份：powershell.exe / `C:/ComfyUI-aki-v2/python/python.exe` / `ollama.exe` / `nvidia-smi` / ffmpeg | **未知**（本包未探测、未哈希任何已装工具） | **缺，需 root 核验** |
| 依赖清单（Comfy 工作流 / Pillow 等） | 由 `dependency_manifest` 封存（`worker:359-412`） | 需在冻结时封存 |
| 16 个样本 source sha256/bytes | `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`（sha256 `47e9f14e…00c3`） | 已知 |
| 模型 digest | **未知**（本包未读任何模型） | **缺，需 root 按已装模型实测并封存** |
| F-WEBP-01 工具/配置/源/产物 hash | `NOT_MATERIALIZED_OR_HASH_FROZEN` | **缺** |

### B2 必须先确定的 root / 端口 / 原句柄

| 项 | 值 | 状态 |
|---|---|---|
| 封存运行根（run root） | 由执行器在授权根下排他创建，父与 worker 共用同一绝对路径 | 需在冻结时确定规则 |
| 控制器输出目录 | `<run root>/temp/s3-production-controller`（`production_controller.py:101`） | 已知 |
| canonical receipt 引用 | `temp/s3-quality/<CANONICAL_RECEIPT_NAME>`（`worker:66`） | 已知 |
| 端口 | 8191（Comfy）、11434（Ollama）——`preflight` 已占则拒绝 | 已知 |
| 原句柄 | worker 侧 `self.owned` / `self._wrapper_handles`；父侧 worker `Popen` 句柄 + `/proc` birth | 已知（规则） |
| Windows 原 birth | `listener_process_start_ticks` / `wrapper_process_start_ticks`（CIM + `Get-Process`） | 已知（规则），**本轮实测值缺** |

### B3 预算与母授权消耗来源

* 母授权：`AUTH-PROGRAM-V1-COMPLETE-03`（ACTIVE；request sha256 `afcde7f2…be25`）。
* 全局累计：1024 模型动作 / 24 有效完整验收 / 172800 s 生产运行，**历史消耗计入、不清零**。
* 本轮设计额度（`remaining-integration-budget-02.json`）：A 子运行 94..103 动作，B 子运行 ≥40，
  合计 134..143；每 child ≤128；两个 child 各 `full=True` ⇒ 占 **2 个有效完整槽**。
* 真实账本：`tools/local_program_authority.py:17` 的
  `ROOT.parent.parent/.lvw-runtime/lvw-prompt-service/program02.sqlite`，且必须与
  `reports/unified-media/live-15/authorization.json` 的 `budget_ledger` **同文件**
  （`v0_s3_budget_authority.py:62-64`）。
* **本包未读该账本、未查余额、未查历史消耗** ⇒ 剩余额度必须由 root **实测**后重算，
  不得沿用 134..143 这个设计数。

### B4 清理与失败保留规则（不得放宽）

* 任何未证终态 ⇒ `UNKNOWN_RETAINED`、根与预约保留、`refund/resend/archive_allowed=False`、
  不退款、不重发、不归档、不接下一 phase。
* 父只终止自己创建的句柄；Windows 后代由 N1 独立协调；两者互不代证。
* 失败与未知一律**保留证据**，不删根、不改写已落盘的收据
  （`production_controller.py:2577-2588` 的排他写与 `persisted_receipt_state` 差异命名）。

### B5 缺信息的最小无副作用核验命令计划（**交 root 执行，本包不执行**）

```sh
# 1) 候选与源码身份（只读）
git -C <repo> rev-parse HEAD
git -C <repo> status --porcelain -- tools/ lvw/ LVW_V0_RuntimePatch/
sha256sum tools/v0_s3_production_controller.py tools/v0_s3_quality_worker.py \
          tools/v0_s3_quality_phase.py tools/v0_s3_supervisor.py tools/v0_s3_coordinator.py \
          tools/v0_s2_runtime.py tools/v0_s2_driver.py tools/v0_s3_budget_authority.py \
          tools/local_program_authority.py

# 2) 已装工具身份（只读哈希，不启动、不探测端口）
#    powershell.exe / C:/ComfyUI-aki-v2/python/python.exe / ollama.exe / nvidia-smi.exe / ffmpeg.exe
#    —— 哈希方式由 root 的既有工具绑定流程决定（见 runtime-binding-correction-03.child.json 的
#       metadata_hash_files / metadata_hash_bytes 上限），不要自造新的口径。

# 3) 端口与进程占用（只读观察，先于任何启动）
powershell.exe -NoProfile -NonInteractive -Command \
  "@(Get-NetTCPConnection -State Listen -LocalPort 8191,11434 -ErrorAction SilentlyContinue).Count"

# 4) 原账本身份与该 run 的行（只读）
ls -l <authority_root>/../../.lvw-runtime/lvw-prompt-service/program02.sqlite
#    并按 reports/unified-media/live-15/authorization.json 的 budget_ledger 核对 samefile；
#    查询 run=V0-S3 的 children 行（stage/active/cpu/seconds/cap/expires）。
#    —— 只读查询，不 reserve、不 bind、不 model_action。

# 5) 模型身份（只读清单，不下载、不换模型）
#    已装模型清单 + 其 digest，与 s3 binding 的 model_digest 对齐。
```

> 说明：以上是**计划**，本包一条都没有执行；第 3、4 步属于 root 的观察动作，
> 不在本包授权内，也不需要为"已批准范围"重复请求人批。

---

## C. 优先路线与依赖（建议）

### 阶段 1：可信 native 后端接线 + 最小单链验证（先做）

* 顺序：**N1（父侧 custody） → N2（装配与五键 binding） → N3（admission 生产者接线） → N4（一次真实单链）**。
* 理由：N1 决定"父在 worker 死后还能不能释放 Windows/GPU"，是整条链唯一无法用离线合成证明的环节；
  N2/N3 是纯接线（代码已是正确形态），风险低；N4 一次单链（1 行 / 1 动作 / 1 次 debit / 1 次真实 cleanup）
  用最小代价证伪这四个接线。
* **阶段 1 完成后仍不能宣布任何产品门**：16 行质量、A06、WebP、独立分、人签全部未动。

### 阶段 2：固定全分母 + 合并同根因纠偏

* **同根因合并**：`DRIVER-PROTOCOL-01` + `BINDING-SHAPE-01` 是同一根因——**native 装配从未接线，
  且两个既有 owner 的合同互不兼容**；必须一次做完，不得拆成两轮互相掩盖。
* 同理，`ADMISSION-OWNER-01` 与 CUSTODY-01 是同一根因——**收据没有受信任生产者**；
  手写 `PROVEN` 是错解，正确解是"root 认可生产者"。
* 全分母：冻结集 10 图 / 6 视频（`quality-execution-inputs.frozen.json`），
  预算 134..143 动作 / 2 个有效 full 槽（**须由 root 按实测重算**）。

### 阶段 3：其余产品义务（依赖明确）

| 义务 | 精确依赖 | 可否早于阶段 2 |
|---|---|---|
| A06 真实隔离 + 安装前/回滚后注册表基线 + 真实回滚 | 部署 owner（`v0_s3_stage_runtime.py:75`）先被接线（N2 第 2 步）+ 真实宿主隔离目录 | **可以**，只要部署 owner 已接线；不依赖 16 行质量 |
| install / rollback 收据 | 同上 + `v0_incremental_package.py` 的真实 install/rollback 事务 | 同上 |
| 真实质量 16 行 | N1+N2+N3 全部完成 + 冻结模型 digest + 真实 ledger debit | 否 |
| 独立质量分（V0-A11/A12） | 真实 16 行 raw artifact 之后，由独立上下文评分 | 否 |
| WebP 格式（V0-A12） | F-WEBP-01 工具/配置/源/产物 hash **在任何推理前**封存 | 可与质量并行，但**不计入**质量 16 项 |
| 产品 Gate0（V0.2/V0） | 上述全部 + 清理证明 + 人签 | 否 |

### 避免重跑已闭合负例

* I01–I24 的离线负例与 correction04 的 20 节点定向证据**已闭合**，**不得为补文档重跑**。
* 只对**实际被改动的 hook / 接线**跑必要回归（离线合同出门条款：实现者 READY_FOR_REVIEW → 隔离独审复算
  → root 集中裁决；不机械重跑 P1/P2B/P3A/P3B 全套）。
* correction04 的 20 节点覆盖的是**离线 seam 的终态收口与自有资源生命周期**；
  它**不覆盖**任何 native 进程、Windows 后代或 GPU ⇒ **不得**用它替代 N1/N4 的证据。

---

## D. 可直接交实现者 / 独审者的候选提示词（**未冻结**）

> 以下提示词是**候选**，root 冻结后才可发出；发出前不得据此开工。

### D1 给实现者的候选提示词（子包 N1）

```
角色：S3-P4 实现者（唯一实现者，禁止派生 Agent）。
候选：<root 冻结的 sha>；范围：仅 tools/v0_s3_native_custody.py（新）+ tools/v0_s3_production_controller.py
的父侧 custody 调用与收据字段。禁止改动 tools/v0_s2_driver.py / tools/v0_s2_runtime.py /
tools/v0_s3_quality_phase.py / tools/v0_s3_supervisor.py / tools/v0_s3_coordinator.py /
tools/v0_s3_budget_authority.py / LVW_V0_RuntimePatch/** / 任何 contract、control、manifest、分母。
职责：在**父侧**实现一份独立、有界、带出生校验的 Windows custody 释放能力。
硬规则：
  1) 只对父**自己重证过**（CIM CreationDate + Get-Process SafeHandle + StartTime ticks + 归一化可执行路径）
     的 pid 动手；record 只提供被验证对象，不提供结论。
  2) 绝不按名字或磁盘自报 PID 选进程；绝不枚举无关进程；绝不启动服务；绝不造预算/平台。
  3) 任何不确定 → 稳定失败码 + 状态 UNKNOWN；UNKNOWN 永不升级为 PROVEN；
     运行保持 UNKNOWN_RETAINED、根与预约保留、refund/resend/archive_allowed=False。
  4) 保留 controller:2631 / worker:596 / verifier:693-705 / supervisor:1113-1115 四处拒绝点。
  5) 交付：源码 + 定向用例 + 失败保留证据；状态只报 READY_FOR_REVIEW，不签 Stage PASS。
验收 Oracle（候选）：见 E 节 O1–O4。
```

### D2 给实现者的候选提示词（子包 N2）

```
角色：S3-P4 实现者。范围：tools/v0_s3_quality_worker.py 的 native 装配接线（+ 五键 binding 投影，
位置由 root 定）。禁止改动 phase 协议检查、阈值、保留上限、原始证据。
硬规则：
  1) 装配顺序必须是 preflight → 部署 owner 第一次排他 profile 写 → Comfy/Ollama 原句柄与原 birth →
     **真实 sampler 启动并绑定 resource_observer** → 五键 binding 排他写 → custody record → QualityPhase。
  2) 五键必须严格等于 {candidate_sha, authorization_sha256, ollama_pid, ollama_start_ticks,
     baseline_gpu_mib}；baseline_gpu_mib 只能来自 warm profile 且过 valid_baseline。
  3) 装配顺序错时必须以 QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer / 
     WORKER_BINDING_KEY_SET_INVALID 这样的**既有稳定码**失败，不得新增含糊异常。
  4) 不造新的进程平台、不造新的预算、不改 10800/600/21600。
```

### D3 给隔离独审者的候选提示词

```
角色：隔离独审实例（只读复算，与实现实例分离）。禁止启动真实 native/GPU/服务，
禁止读原账本，禁止使用实现者的自报 PID/布尔作为证明。
复算对象：候选 sha 的实际字节。
必须独立回答：
  1) 父侧 custody 是否对**每一个**终止动作都先自证了 pid+birth？（列出被测函数与行）
  2) UNKNOWN 是否可能被升级为 PROVEN？（找出任何这样的路径）
  3) 是否存在任一路径把"杀掉 WSL 进程"当作 Windows/GPU 已释放？
  4) 五键 binding 是否严格等于 BINDING_KEYS，且 baseline 来自真实 warm profile？
  5) 四处拒绝点是否仍在？
  6) 是否引入了新的进程平台、新的预算口径、放宽的截止或门槛？
结论只允许 PASS/FAIL/BLOCKED/待复算；实现者的自检不算通过；不得代替 root 签 Stage PASS。
```

---

## E. 精确验收 Oracle 候选（**未冻结、未执行**）

> 每个 Oracle 都写明"输入 → 期望 → 证据落点"。
> 全部标记 `NOT_FROZEN / NOT_EXECUTED`；**本包不签任何一条**。

| # | Oracle | 输入 | 期望 | 证据落点 |
|---|---|---|---|---|
| O1 | 父侧 custody 自证 | 一个 custody record（pid + ticks），但把 record 里的 ticks 改成别的值 | 父**拒绝**终止，稳定码 `CUSTODY_PID_BIRTH_REUSED`；不产生任何 kill 动作 | adapter 收据 + 命令日志 |
| O2 | 父在 worker 死后仍能释放 | worker 在写 custody record 后被 SIGKILL | 父用 record + 自证**完成**对 11434/8191 的停止与后代确认；或诚实地落 `CUSTODY_RELEASE_UNKNOWN` | 父收据 + 端口观察 |
| O3 | 状态机不升级 | 任一路径触发不确定 | 状态恒 `UNKNOWN`；运行 `UNKNOWN_RETAINED`；根与预约保留；`refund/resend/archive_allowed=False` | 运行收据 |
| O4 | 无副作用边界 | 一次完整父侧释放 | 未触碰任何非自有 pid；未启动服务；未删除文件；未改账本 | 动作账本（`owned` 前后对比） |
| O5 | driver 协议装配 | 在**未**启动 sampler 的情况下构造 `QualityPhase` | 以既有稳定码 `QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer` 失败（不是含糊异常） | 用例收据 |
| O6 | 五键 binding 形状 | 一个多一个键的 profile | `WORKER_BINDING_KEY_SET_INVALID`（worker 侧）或 `BINDING_PROFILE_KEYSET_INVALID`（投影侧），**不得**被容忍或自动裁剪 | 用例收据 |
| O7 | 固定截止不变 | 缩尺测试 | 生产默认仍是 10800/600/21600（`v0_s3_supervisor.py:69-71`），缩尺只经显式注入 | 用例收据 |
| O8 | 准入不被自写解锁 | 一份手写 `status='PROVEN'` 的七元链 | 仍 `accepted=False`，`primary_reason=NATIVE_EXECUTION_BACKEND_NOT_READY` | 准入报告 |
| O9 | 单链最小验证 | 1 行 / 1 动作 / 1 次真实 debit / 1 次真实 Windows cleanup | 端到端一次成功，账本 debit 恰一次，清理证明为真且有原始证据 | N4 收据 + 账本行 |
| O10 | 十六行分母不被压缩 | 单链成功后 | 质量仍是 10 图 + 6 视频的固定分母；单链**不**写入任何 V0-A0x 状态 | 质量收据 + 汇总 |

---

## F. 本提案**不**做的事

* 不冻结任何新合同、状态机、协议版本、分母、门槛或截止。
* 不激活任何执行；不派生 Agent；不改任何产品代码。
* 不替 root 做架构裁决（尤其 §A1 的"父侧独立等价实现 vs 抽共享原语"必须 root 选）。
* 不宣布任何 I01–I24、V0-A01..A12、Stage 或产品 PASS。
* 不请求对 COMPLETE03 已覆盖范围重复人批。
