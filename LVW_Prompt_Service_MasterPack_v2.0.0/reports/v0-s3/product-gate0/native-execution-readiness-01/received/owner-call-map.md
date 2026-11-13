# S3 真实后端准入准备 01：owner 调用链精确交接（只读源码事实）

候选代码 `b95de076f37e64d321629c065e5531eba8a5250a`，交付 `13e77492361648dc90a414f7fd37f0bb8b8c3634`，
impl HEAD `13e77492361648dc90a414f7fd37f0bb8b8c3634`（`git diff b95de07 -- tools/ lvw/ LVW_V0_RuntimePatch/` 为空，
工作树源码与候选一致）。

本文只登记**实际代码**的 owner 与调用边。设计 DDL、合同文档、报告里的"应有设计"**不是实现证明**，
在下文中一律不计入"已接线"。

分类定义：

* **已接线（WIRED_IN_CANDIDATE）**：该段在候选代码里是可达的执行路径或已被真实调用的 owner。
* **可复用未接线（REUSABLE_NOT_WIRED）**：该 owner 的代码存在且是正确形态，但在 S3 生产路径上**没有任何调用点**。
* **缺生产 owner/合同（MISSING_OWNER_OR_CONTRACT）**：没有能产出该事实的生产代码，或两个既有 owner 的合同互相不兼容。

---

## 0. 顶层调用图（实际代码，非设计）

```
ProductionController.run                       tools/v0_s3_production_controller.py:2591
 ├─ _precheck                                 :1318  → WorkerContext.load + parse_projection_rows
 ├─ _admission_report                         :1531  → verify_native_admission :567  (恒 accepted=False)
 ├─ if self.seam is None: raise CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY   :2625-2631  ★拒绝点1
 ├─ _acquire_reservation                      :1569  (排他 create，失败保留)
 ├─ _seal_plan                                :1617  → ParentOriginalEvidence.seal_plan/seal_root (coordinator:385/423)
 ├─ _supervise                                :1635  → ParentSupervisor.run (supervisor:698)
 │                                                ├─ _spawn → subprocess.Popen            supervisor:566
 │                                                ├─ _birth_identity (/proc)               supervisor:591
 │                                                ├─ 协议泵 / 固定截止 10800/600/21600     supervisor:69-71, 653-696
 │                                                └─ _terminate_owned_worker                supervisor:912
 ├─ _verify_originals                         :1677  → ParentOriginalEvidence 读真实原件
 ├─ _bind_receipts                            :1778  → QS/独立分/十二项收据
 ├─ _build_summary                            :2145  → aggregate_twelve_keys (coordinator:914)
 ├─ _persist_summary                          :2171
 └─ finally: _release_owned_resources         :2511  → seam.release_resources + 有界 join(2.0s)

v0_s3_quality_worker.main                     tools/v0_s3_quality_worker.py:548
 ├─ if driver is None: raise NATIVE_EXECUTION_BACKEND_NOT_READY   :593-596  ★拒绝点2
 ├─ WorkerContext.load                        :316
 └─ run_worker                                :467
      └─ QualityPhase(...).run()              quality_phase:896 / 2445 / 2487
           ├─ driver.submit / chat_log_snapshot / owned_listener_birth
           │  / release_preload / video_snapshot_residue / resource_observer / _json_request
           │        ↑ 协议检查 quality_phase:988-995
           └─ 发布 canonical receipt → 父读真实 bytes

build_native_driver                           tools/v0_s3_quality_worker.py:615  ★无生产调用点
 └─ NativeRuntime(arguments, evidence)        tools/v0_s2_runtime.py:43
      ├─ preflight                             :59   (端口/进程占用拒绝)
      ├─ native_clock                          :112  (Windows 单调钟)
      ├─ write_warm_binding / write_native_binding  :131 / :152  (排他 profile 写)
      ├─ start_ollama                          :167  → base.ollama_wrapper_text → Popen(持有句柄)
      ├─ start_sampler                         :183  → SamplerWorker → resource_observer 绑定 :193
      ├─ owned_listener_birth                  :124  → CIM PID+birth 证明
      └─ S2SystemDriver.cleanup                v0_s2_driver.py:260  ★Windows 后代/GPU 释放在 worker 进程内
```

---

## 1. 拒绝点：native 路径今天在哪里停（已接线）

| # | 位置 | 稳定码 | 事实 |
|---|---|---|---|
| REF-01 | `tools/v0_s3_production_controller.py:2631` | `CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY` | `self.seam is None` 时在**任何 spawn 之前、任何 native driver 构造之前**拒绝。 |
| REF-02 | `tools/v0_s3_quality_worker.py:596` | `NATIVE_EXECUTION_BACKEND_NOT_READY` | 命令行入口在构造 driver 之前拒绝；命令行**永远无法**构造 native driver。 |
| REF-03 | `tools/v0_s3_production_controller.py:693-705` | `NATIVE_EXECUTION_BACKEND_NOT_READY` | `verify_native_admission` 只是诊断：即使引用链全部 `PROVEN`，`accepted` 仍恒为 `False`，primary_reason 恒为该码。 |
| REF-04 | `tools/v0_s3_supervisor.py:1113-1115` | — | 父监督证据自述 `native_service_cleanup_proven=False`、`native_gpu_release_proven=False`、`parent_crash_recovery_proven=False`。 |

两侧同一稳定码，**这是本候选已有的正确事实**，不得被绕过。

---

## 2. controller native 拒绝 → WorkerContext → build_native_driver → QualityPhase

### 2.1 已接线

* `ControllerContext`（`v0_s3_production_controller.py:417-487`）：闭合键 `CONTROLLER_CONTEXT_KEYS`（:131-133），
  `worker_context` 与 `admission` 必须是 `{path, sha256}` 且路径非空、sha 为 64 hex；`load` 要求调用方给出
  期望哈希（:474-486）。**封存 context 的来源是父方，不是 worker 自算**。
* `ControllerContext.load` 在 `_precheck`（:1318-1352）被真实调用，且 worker 的 run/candidate/authorization/root
  四项必须与 controller context 一致，否则 `CONTROLLER_WORKER_*_MISMATCH`。
* `verify_native_admission`（:567-705）：七元引用链 `budget_binding / native_custody / gpu_release / install /
  rollback / grant / tool_closure`（:492-493）；预算经 `S3BudgetBindingProvider`（coordinator:191）用**已接受**
  的 `budget.load_binding` + `budget.validate_config` 校验，而不是自写 capability 文档。
* `WorkerContext`（`v0_s3_quality_worker.py:121-435`）：闭合键集合、`reference_anchors` 声明式锚点
  （`RUN_ROOT` / `READ_ONLY_DIRECTORY`，:53-58）、逐层 `O_NOFOLLOW` 打开、读后再验链身份。
  `load` **拒绝自算哈希**：`if not expected_sha256: raise WorkerError('WORKER_CONTEXT_HASH_REQUIRED')`（:319-322）。
* `QualityPhase`（`v0_s3_quality_phase.py:896-1027`）：由 worker **真实调用**（worker:496-504），
  自带 16 行固定分母、投影哈希、source identity、binding 五键、parent budget 容量准入。
  phase 自己声明"不拥有进程、不拥有预算、不拥有账本"（:897-902）。

### 2.2 可复用未接线

* **`build_native_driver`（worker:615-643）**：形态正确——只从封存的 `driver_arguments`（六个键：powershell /
  comfy_main / comfy_python / ollama_exe / ffmpeg_exe / nvidia_exe，:60-61）构造
  `tools.v0_s2_runtime.NativeRuntime`，`warm_benchmark=False`、`native_audit=True`、
  `max_public_submissions=45`、`max_loopback_requests=8192`、`max_native_clock_reads=128`。
  **无生产调用点**：全仓唯一引用是 `tools/test_v0_s3_production_composition.py:1219`，那个测试是**拒绝**它。
* **`S3InstalledRuntimeFactory`（coordinator:309-344）**：继承已接受的
  `InstalledPackageRuntimeFactory`（`v0_s3_stage_runtime.py:75`）未改一份，只新增
  `_profile_binding_parameters`（唯一允许增量键 `s3_budget_binding`）与 `bind_video_snapshot_root`
  （只在**自己已验证的** `owned_run_root` 上绑定一次）。
  **无生产调用点**：全仓引用只在 `tools/test_v0_s3_integration.py`。
  后果：S3 路径上**没有部署、没有第一次排他 profile 写、没有 install、没有 rollback**。
* **`NativeRuntime` 生命周期**（`v0_s2_runtime.py:43-410`）：见 §4。

### 2.3 缺生产 owner / 合同（两个必须由 root 裁决的具体不兼容）

**DRIVER-PROTOCOL-01 —— phase 的 driver 协议与 `build_native_driver` 的产物不兼容。**

`QualityPhase.__init__`（`v0_s3_quality_phase.py:988-995`）要求：

```python
for name in ("submit", "chat_log_snapshot", "owned_listener_birth",
             "release_preload", "video_snapshot_residue"):
    if not callable(getattr(driver, name, None)):
        raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:" + name)
if not callable(getattr(driver, "resource_observer", None)):
    raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer")
```

`NativeRuntime.__init__`（`v0_s2_runtime.py:47`）里是 `self.resource_observer=None`；
只有 `start_sampler`（`v0_s2_runtime.py:193`）才把它换成绑定方法。
`build_native_driver`（worker:615-643）**只构造、不启动 sampler**。

⇒ 按现有代码，`build_native_driver(context)` 返回的对象在 `QualityPhase.__init__` 处必然抛
`QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer`。
其余协议方法**都在**：`submit`（`v0_s2_driver.py:389`）、`chat_log_snapshot`（`v0_s2_runtime.py:281`）、
`owned_listener_birth`（:124）、`release_preload`（:246）、`video_snapshot_residue`（:368）、
`_json_request`（`v0_s2_driver.py:347`）。
⇒ 缺口**不是**驱动协议整体缺失，而是**装配顺序**：谁在什么时刻启动真实 Windows GPU sampler 并绑定 observer。

**BINDING-SHAPE-01 —— 两个既有 owner 的 binding 文档键集不兼容。**

`WorkerContext.binding()`（`worker:414-435`）要求 `set(value) == BINDING_KEYS`，
`BINDING_KEYS = {candidate_sha, authorization_sha256, ollama_pid, ollama_start_ticks, baseline_gpu_mib}`
（`worker:62-63`），否则 `WORKER_BINDING_KEY_SET_INVALID`。

真实 native owner 写出的 profile 键集是：
`write_native_binding`（`v0_s2_runtime.py:152-164`）→ `candidate_sha, authorization_sha256, model_digest,
program_authorization_id, scope, max_runs, ollama_pid, ollama_start_ticks, issued_at, expires_at`（+可选
`s3_budget_binding`）；`write_warm_binding`（:131-149）→ 同类但带 `baseline_gpu_mib`、无 `max_runs`。

⇒ `baseline_gpu_mib` 只在 warm profile 里；键集也都不等于五键。
⇒ **缺一个投影 owner**：从真实 native profile 投影出**恰好五键**的 S3 binding 文档，并写进封存根。
   现有代码里没有这个投影。

---

## 3. S3InstalledRuntimeFactory / NativeRuntime / Windows wrapper / 服务注册 / 原 Popen 与 birth / 采样 / GPU 释放

| 环节 | 位置 | 事实 | 分类 |
|---|---|---|---|
| 安装/部署 owner | `tools/v0_s3_stage_runtime.py:75-345` | 继承 `StageRuntimeFactory`（`v0_s2_stage_runtime.py:54`），`_prepare` 在**第一次排他写**时落 profile；`_DeploymentArchive`（:49-73）保留失败安装，不按不确定路径名删除。模块 docstring 自述：**不实现 rollback 验收、不启动任何服务或包 CLI**。 | 可复用未接线 |
| S3 增量包 | `tools/v0_incremental_package.py`（`build/diagnose/install/rollback`，:848-862、:2511、:2762-3134） | install/rollback 只认目标内所有权记录所绑定的安装，逐项比对 hash；失败保留两棵树、**不做路径式回滚**。 | 可复用未接线 |
| native 预检 | `v0_s2_runtime.py:59-74` | GPU 遥测用 Windows `nvidia-smi` 与 WSL `nvidia-smi` 双读 + `admit` 比对；8191/11434 任一被占 → `PREFLIGHT_TARGET_PORT_OWNED`；ollama/Comfy python 进程存在 → `PREFLIGHT_TARGET_PROCESS_PRESENT`。 | 可复用未接线 |
| Windows 时钟 | `v0_s2_runtime.py:112-122` | 固定 `AUTHORIZED_COMFY_PYTHON = C:/ComfyUI-aki-v2/python/python.exe`（`reports/v0-s1/wp-s1-03-phase-a/live_probe.py:46`），`-I -B` 跑 `tools/v0_s2_native_clock.py`，要求 `platform=win32` 且 `clock_basis=native_python_monotonic`。 | 可复用未接线 |
| Windows wrapper（服务注册） | `reports/v0-s1/wp-s1-03-phase-a/live_probe.py:149-160`（被 `tools/v0_s2_driver.py:19-22` 以 `base` 载入） | `ollama_wrapper_text` 写 `$PID` 到 pid 文件，固定 `OLLAMA_HOST=127.0.0.1:11434` / `OLLAMA_NO_CLOUD=1` / `NO_PROXY`，前台运行 `ollama serve`；`comfy_wrapper_text` 同形监听 8191 且 `--whitelist-custom-nodes lvw_v0_bridge`。**服务注册=wrapper 进程，不是 Windows 服务。** | 可复用未接线 |
| 原 Popen 与句柄 | `v0_s2_runtime.py:167-181` | `subprocess.Popen([powershell,'-NoProfile','-NonInteractive','-File', wrapper])`，句柄存 `self._wrapper_handles[pid_file]`，`self.owned` 保留 (name, process, stream)。 | 可复用未接线 |
| Windows 侧句柄 owner（V1 产品已有形态） | `lvw/backend/app/native_runtime.py:9-31` + `lvw/backend/app/runtime.py:97-100, 135-160` | PowerShell 侧持有原生句柄（`$p.Handle`）与 `pid`＋`birth_ticks`（`$p.StartTime.ToUniversalTime().Ticks`）并写 owner 文档；WSL 侧**只写 stop nonce**，随后读 `proof()` 回验；终态证明缺失时 `runtime.py` 抛 `RESOURCE_RELEASE_PENDING`。这是仓内**最接近 N1 所需"父侧/Windows 侧独立句柄 owner"的既有原语**。但它只覆盖 11434 的单个 Ollama，没有 Comfy 8191 owner、没有 GPU 采样、没有 Windows 后代快照，且绑定在 async FastAPI 运行时上，**不是** S3 链。 | 可复用未接线 |
| 原 birth 证明 | `v0_s2_driver.py:118-145` | CIM 取 listener/wrapper 的 `CreationDate` ticks，`Get-Process` 的 `SafeHandle` 钉住对象，路径归一化后必须等于授权可执行文件；`LISTENER_BIRTH_PROOF_INVALID` / `LISTENER_OR_WRAPPER_PID_REUSED` 拒绝复用 PID。 | 可复用未接线 |
| 采样 | `v0_s2_runtime.py:183-195` + `tools/v0_s2_native_sampler.py:19-173` | `SamplerWorker` 观察自有 Windows 进程的 GPU/RAM；`observe_resources`（:89）/`guard_point`（:96）在资源策略越界时**闩锁**并触发 `_emergency_cleanup`。 | 可复用未接线 |
| GPU 释放 | `v0_s2_driver.py:260-311` | 没有独立的 `gpu_released` 收据产出者：GPU 释放是**自有进程被停掉的后果**，不是单独的动作。 | 缺生产 owner |
| 残留只读访问器 | `v0_s2_runtime.py:296` / `:368`；`coordinator:332-344` | `bind_video_snapshot_root` 只绑定一次，`video_snapshot_residue` 只枚举 `temp` 第一层 `lvw-video-*`，不跟随链接、不删除、不返回假空。**已由 S3 工厂接线**（工厂方法存在），但工厂本身没有生产调用点。 | 可复用未接线 |

---

## 4. 父独立清理 / 原账本预算 / 父对 Windows 后代的权力

### 4.1 已接线（父侧）

* `ParentSupervisor._terminate_owned_worker`（`v0_s3_supervisor.py:912-950`）：只终止**父自己创建**的句柄；
  先协作取消，再 `terminate`，5 s 宽限后 `kill`；结果里写 `proven_stopped`、
  **`native_cleanup_proven=False`**、`native_cleanup_owner='original_driver'`。
* `ParentSupervisor.evidence()`（:1022-1120）：`native_service_cleanup_proven=False`、
  `native_gpu_release_proven=False`、`parent_crash_recovery_proven=False`；未知时 `root_retained=True`、
  `reservation_retained=True`、`refund_allowed=False`、`resend_allowed=False`、`archive_allowed=False`。
* `RecoveryEntry`（:1189-1227）：无原始 custody 证据 → `BLOCKED / CUSTODY_EVIDENCE_UNAVAILABLE`，
  `replay_allowed=False`、`resend_allowed=False`；有 custody 也只 `RECOVERED_FOR_CLEANUP_ONLY`，
  `native_cleanup_proven=False`。
* `ProductionController._release_owned_resources`（:2511-2561）：**owner（seam）自己**关本轮自有 pipe、
  2.0 s 有界 join；线程不结束就**保留并如实报告 retained**，不 kill、不追加 cancel；
  close 失败 → `CONTROLLER_OWNED_RESOURCE_CLOSE_FAILED:<Type>` 并降级 `UNKNOWN_RETAINED`。
* `ProductionController._recovery_entry`（:2807-2829）：只有父**真的**持有 pid+birth 时才算 custody；
  离线 seam 没有子进程 → custody=None → 恢复保持 BLOCKED。

### 4.2 缺生产 owner / 合同（这是本轮**最关键**的缺口）

**CUSTODY-01 —— 能释放 Windows 后代与 GPU 的 owner 在 worker 进程里，父没有这个权力。**

* 释放 Windows 后代与 GPU 的真实代码是 `S2SystemDriver.cleanup`（`v0_s2_driver.py:260-311`）：
  按端口重证 listener 血缘（`_prove_listener_owned`）→ 快照 Windows 后代（`_snapshot_descendants`，
  深度 8、后代上限 17、CIM 与 `StartTime` 双重出生校验）→ 按 `pid + process_start_ticks` 逐个停
  （`_kill_bound`，`Get-Process.SafeHandle` 钉住对象，PID 复用即 `PID_REUSED`）→
  `_assert_no_new_descendants`（`NEW_DESCENDANT_OWNERSHIP_UNPROVEN`）→ 复核 8191/11434 无监听。
* 这个 owner 是 **driver 对象**，driver 活在 **worker 进程**内。
* 父侧只有 Linux 的 worker 句柄。当 worker **阻塞**（阻塞回调/阻塞持久化）或**退出**时，
  父无法执行上面的 Windows 步骤；`v0_s3_supervisor.py:912-950` 也**自己声明**它不证明 native 清理。
* ⇒ **"杀掉 WSL 的 Python" 绝不能被当作 "Windows/GPU 已释放"**。这正是现有代码自己的立场，
  本包不得软化它。
* ⇒ 下一实现包必须让**父**独立持有一份 Windows 后代权力，或在父侧重建一份等价的、有界、
  带出生校验的清理能力；否则 worker 一死，`native_custody` 收据永远只能是 `PROVEN` 的字符串而非事实。

**ADMISSION-OWNER-01 —— 七份封存文档没有生产者。**

`verify_native_admission`（`v0_s3_production_controller.py:492-497, 644-660`）需要的每份文档都必须
`status == 'PROVEN'` 且带严格布尔证明：

| 引用 | 需要的证明字段 | 生产者现状 |
|---|---|---|
| `native_custody` | `descendant_handles_closed=True`, `native_services_stopped=True` | **无**（且当前无能力证明，见 CUSTODY-01） |
| `gpu_release` | `gpu_released=True` | **无** |
| `install` | `installed=True` | **无**（S3 部署路径未接线） |
| `rollback` | `rollback_verified=True` | **无** |
| `grant` | `grant_active=True` | **无** |
| `budget_binding` | 由 `S3BudgetBindingProvider` 经已接受 `budget.load_binding`/`validate_config` 校验 | **有**（`tools/v0_s3_budget_authority.py:24-101` 侧） |
| `tool_closure` | `files[]` 每项 path+sha256 且实际重算相等 | 可由现有代码产出（工厂侧），但无 S3 调用点 |

全仓唯一写出 `kind == 'lvw.s3-native-admission/1'` 文档的地方是
`tools/test_v0_s3_production_composition.py`（:247, :925）。
⇒ **禁止**由实现者手写 `PROVEN` JSON 或 platform 字符串来"解锁"：验证器恒 `accepted=False`，
手写只会被 REF-03 挡住；要真正解锁，必须有 root 认可的**受信任生产者**。

### 4.3 原账本预算（已接线，可复用）

* `tools/v0_s3_budget_authority.py:24-101`：stdin 受限 debit（32 KiB），校验
  `protocol.validate_config`、authority 实现哈希（`AUTHORITY_HASH = 677998fa…70f787`，
  与 `tools/local_program_authority.py` 实测 sha256 一致）、child 封存、tool 三角色（authority/shim/python）
  与 `execution` 绑定、`s3_protocol` 源绑定。
* **原账本身份**：`ledger` 必须与 `reports/unified-media/live-15/authorization.json` 的 `budget_ledger`
  `samefile`（:62-64）；默认路径 `tools/local_program_authority.py:17` =
  `ROOT.parent.parent/.lvw-runtime/lvw-prompt-service/program02.sqlite`。
  生产路径下若存在 `.s3-synthetic-fixture` 标记即 `fixture forbidden in production`（:64）。
* **账本行约束**（:65-72）：`stage='V0-S3'`、`active=1`、`cpu=0`、child 路径/哈希、
  bindings 路径/哈希、`issued_at<=...<expires_at<=row.expires`、且 `0<seconds<=21600`、`0<cap<=128`。
* **debit 只在 `authority.model_action(child_path)` 返回后**才写 `DEBITED`（:91-101）；
  失败或不确定**不自动重放**。
* controller 侧**不**调用 debit：只经 `S3BudgetBindingProvider` 校验封存绑定的**形状**
  （`budget_binding_scope = SEALED_BINDING_SHAPE_ONLY_NOT_BALANCE_NOT_AUTHORIZATION_NOT_CUSTODY`，
  `v0_s3_production_controller.py:599-600`）。
* ⚠️ 本包**没有**读原账本、没有查余额、没有查历史消耗。剩余额度必须由 root 按
  `remaining-integration-budget-02.json` 的 134..143 模型动作 / 每 child ≤128 / 2 个有效 full 槽
  与 COMPLETE03 的全局 1024/24/172800s **重新核算**，不得沿用旧数字。

---

## 5. QS / A06 / WebP / 安装回滚 / 归档

| 义务 | 位置 | 事实 | 分类 |
|---|---|---|---|
| 独立质量分（QS） | `v0_s3_production_controller.py:1778+`（`_bind_receipts`）→ `v0_s3_coordinator.py:914-961` | 控制器**真的**调用已接受的 QS owner；别的 raw artifact 的分**不**变成收据（测试 `test_v0_s3_production_composition.py:790, 833`）。平台没有产出独立分的实现 → 收据恒 unproven → V0-A11/A12 恒 BLOCKED。 | 已接线（收据侧）／缺真实独立分 |
| A06 真实隔离 | `v0_incremental_package.py` + `v0_s3_stage_runtime.py:75+` | 离线包已证隔离 sandbox build/diagnose/install/rollback；**正式 A06 须在含中文空格隔离宿主目录实际启动/导入公开工作流、验证断外联保 loopback 及回滚后原工作流真实运行**（`architecture-and-acceptance-brief.md`）。控制器自列 `REAL_A06_ISOLATION_NOT_PROVEN`（:163）。 | 缺生产 owner |
| 十二项收据表 | `v0_s3_coordinator.py:67-81`（`TWELVE_REQUIREMENTS`）、`85`（`BLOCKING_RECEIPTS`） | V0-A06 需 `a06_isolation + install + rollback`；A11/A12 需 `independent_score`（+A12 需 `webp_format`）。旧 S2 九项与 45+20 发送**不是**聚合收据（:903-905）。 | 已接线 |
| WebP 格式 | `remaining-integration-budget-02.json` | 冻结质量集 **无 WebP**（JPEG 6 / PNG 4 / WebP 0）。F-WEBP-01 状态 `NOT_MATERIALIZED_OR_HASH_FROZEN`：工具/配置/源/产物 hash 必须在任何推理前封存；最多 1 次真实推理、0 重试、**不计入质量 16 项**。 | 缺生产 owner |
| install / rollback 收据 | `v0_s3_stage_runtime.py:1-4` 自述不做 rollback 验收 | 收据无生产者。 | 缺生产 owner |
| 归档 | `v0_s2_stage_archive.py:21+` + `v0_s3_stage_runtime.py:49-73` | 归档 owner 存在；但控制器在清理未证时 `archive_allowed=False`（:2657, 2697）。归档后逻辑根迁移未接通 ⇒ 明确 BLOCKED。 | 可复用未接线 |

---

## 6. 三类分界总表（精确位置）

### A. 当前已接线（7 项）

1. native 拒绝（controller `:2631` / worker `:596` / verifier `:693-705` / supervisor `:1113-1115`）
2. `ControllerContext` 封存与四重身份一致（`:417-487`, `:1318-1352`）
3. `WorkerContext` 声明式锚点与封存引用（worker `:121-435`）
4. `QualityPhase` 真实调用（phase `:896`；worker `:496-504`）
5. 父监督：原句柄 + 原 birth + 固定截止 + 只终止自有句柄（supervisor `:566-605, 653-696, 912-950`）
6. 父侧自有资源独立释放与有界 join（controller `:2511-2561`）
7. QS 收据绑定与十二项聚合（controller `:1778+`；coordinator `:914-961`）

### B. 可复用但未接线（9 项）

1. `build_native_driver`（worker `:615-643`）——无生产调用点
2. `S3InstalledRuntimeFactory`（coordinator `:309-344`）——无生产调用点
3. `NativeRuntime` 生命周期（`v0_s2_runtime.py:43-410`）
4. Windows wrapper / 服务注册形态（`live_probe.py:149-160` + `v0_s2_runtime.py:167-181`）
5. Windows 侧句柄 owner 形态（`lvw/backend/app/native_runtime.py:9-31` + `runtime.py:97-160`）——N1 的最近既有原语
6. 原 Popen + 出生证明 + 后代快照（`v0_s2_driver.py:118-234`）
7. 采样与资源闩锁（`v0_s2_runtime.py:183-195`；`v0_s2_native_sampler.py`）
8. 原账本 debit 链（`v0_s3_budget_authority.py:24-101`；`local_program_authority.py:17,198-230`）
9. 归档 owner（`v0_s2_stage_archive.py:21+`；`v0_s3_stage_runtime.py:49-73`）

### C. 缺生产 owner / 合同（7 项）

1. **CUSTODY-01** 父对 Windows 后代/GPU 的独立权力（`v0_s2_driver.py:260-311` 在 worker 内；父只有 Linux 句柄）
2. **ADMISSION-OWNER-01** 七份封存文档的生产者（`v0_s3_production_controller.py:492-497`）
3. **DRIVER-PROTOCOL-01** `resource_observer` 装配顺序（phase `:988-995` vs `v0_s2_runtime.py:47,193`）
4. **BINDING-SHAPE-01** 五键 binding 投影（worker `:62-63` vs `v0_s2_runtime.py:131-164`）
5. **A06-01** 真实隔离 + 注册表驱动的安装前/回滚后基线 + 真实回滚
6. **INSTALL-01** install/rollback 收据生产者
7. **WEBP-01** F-WEBP-01 的工具/配置/源/产物 hash 封存与执行

---

## 7. 本包明确**不**主张的事

* 不主张任何 native 能力已存在；四个拒绝点原样保留。
* 不主张"杀掉 WSL Python"等于 Windows/GPU 已释放——现有代码自己就拒绝这个推断。
* 不主张 `S3InstalledRuntimeFactory`、`build_native_driver` 已接线。
* 不主张旧 13 fixture 或合成 16 行可替代 native / 质量证据。
* 不主张 10800/600/21600 或任何生产资源门槛可以放宽。
* 不主张任何 I01–I24 或 V0-A01..A12 已通过。
