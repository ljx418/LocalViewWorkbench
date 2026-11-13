# S3-P4 生产组合纠偏 01：实现报告（一次集中修复 M01–M09 / m01–m02）

状态：**READY_FOR_REVIEW**。本报告**不是** Stage PASS，**不是** 产品 Gate0，**不是**
人工签署。本包所有产物都带 `stage_pass_claim = false` 与 `product_gate0 = false`；
离线合成正例**没有**让产品十二键变绿（`pass_count = 0`，十二键全部 `BLOCKED` 或
`FAIL`，无一是 `PASS`）。

冻结依据：`reports/v0-s3/product-gate0/production-composition-correction-01/contract.md`
（本次完整架构裁决、文件范围、逐 M01–M09 与 m01–m02 验收义务）与同目录
`root-decision.json`（`CHANGES_REQUIRED`；Fatal 0 / Major 9 / Minor 2；11 项发现全部采纳；
`all_in_one_correction = true`；`stage_pass_claim = false`）、`received-review/review.md`
与 `received-review/{concentrated.py,corrected_probes.py,probe_test.py}` 及其 JSON 原始证据。
旧报告、旧未跟踪文件与 `implementation-integration-01/report.md` 的既有未提交改动**全部保留**，
未 `clean`、未 `reset`、未 `git add` 全部，**未在原始 git worktree 增删任何文件**。

---

## 1. 候选身份与工作区

| 项 | 值 |
|---|---|
| 基准 commit | `7c27a11111ede5bb2eb449211f5450270d884ee3` |
| 实现分支 | `ljx418/lvw-v1-d0-implement`（Orca 隔离 worktree，HEAD = 基准） |
| 候选身份（changed sources 摘要之摘要） | `204915ced0176ffbf47dad44d1ba9d2deb9b99975f67721333b807f2ba00931c` |
| 候选绑定 | `candidate.json`（base + 6 个变更源的 sha256/字节数 + 8 个冻结源的 sha256 + git 状态） |
| 本轮是否提交 | **否**。提交与否是 root 的决定；本轮只交付工作树与可哈希绑定的源摘要 |
| 原始 git worktree | `/mnt/c/workspace/videoworkline/localviewworkbench`（`main`）**未被修改**：`git status` 无任何已跟踪文件的修改项 |

变更源摘要（`candidate.json`）：

| 路径 | 性质 |
|---|---|
| `tools/v0_s3_controller_io.py` | **新增**：私有有界安全 IO helper（limit+1 有界读、regular/no-follow/nonblock、根内 dirfd 逐层 no-follow、O_EXCL 叶写、根内目录链创建/打开） |
| `tools/v0_s3_production_controller.py` | 修改：M01–M09、m01 的全部接线（硬拒绝 native、context hash 链、消费边界重核、dirfd 排他落盘、完整义务收据、异常持久 UNKNOWN、发送前 reservation、协作取消与诚实线程保留） |
| `tools/v0_s3_quality_worker.py` | 修改：M02 默认入口硬拒绝（不构造 native driver）、M03 强制预封存 hash、M04 有界安全读、m02 text/binary 错误流保准确码 |
| `tools/v0_s3_supervisor.py` | 修改：**仅** `build_production_command` 增加 worker context hash 交接与其必要校验；其余监督/协议/caps 一字未动 |
| `tools/test_v0_s3_production_composition.py` | 修改：按合同更新的既有断言 + 21 个新定向节点（1 正例 + 11 项缺陷负例 + 必要兼容） |
| `tools/test_v0_s3_supervisor.py` | 修改：固定命令的 hash 交接测试（1 个新节点 + 1 个更新节点）+ worker `WorkerContext.load` 的 3 处必要兼容（传入预封存 hash） |

**未改动**：`tools/v0_s3_quality_phase.py`（冻结 QualityPhase）、`tools/v0_s3_coordinator.py`
（既有安全原件 owner）、`tools/v0_s3_runtime_binding.py`、`tools/v0_s3_stage_runtime.py`、
`tools/v0_s3_budget_authority.py`、`tools/local_program_authority.py`、`tools/v0_s2_runtime.py`、
executor/runner/fixture、公共合同、阈值、caps、固定分母 I01–I24 与产品 12 键、旧证据、旧 control、
`MANIFEST.sha256`、V2 目录。8 个冻结源的 sha256 见 `candidate.json.frozen_sources`，与基准一致。

---

## 2. 架构裁决的落实（逐项）

### M01 值比较：类型与值
`_bound_receipt` 不再使用身份比较。字符串按 `type(actual) is str and actual == expected`
比较，布尔按 `type(actual) is bool and actual is expected` 比较：JSON 解码的 `"PROVEN"`
与 Python 字面量一致，`1` 仍不是 `True` 的证明。
**同时**落实 M02：比较正确**不**放开 native（见下）。

### M02 可信 native 执行后端当前未有 → 默认硬拒绝
* 稳定码 `NATIVE_EXECUTION_BACKEND_NOT_READY` 同时出现在 controller 与 worker 两侧。
* `ProductionController.run()`：默认（无 seam）路径在 **precheck 之后、任何 spawn 与任何
  native driver 构造之前**抛 `CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY`；
  `spawn_attempts = 0`；根内不写任何产物。
* `quality_worker.main()`：默认（未注入 driver）路径在**加载 context 之前**返回
  `S3_WORKER_REFUSED NATIVE_EXECUTION_BACKEND_NOT_READY`（exit 2）。`build_native_driver`
  在 CLI 路径上**不可达**（独立探针以 spy 证明构造函数从未被调用）。
* `verify_native_admission` 永远 `accepted = false`，`primary_reason` 恒为
  `NATIVE_EXECUTION_BACKEND_NOT_READY`；报告新增
  `budget_binding_scope = SEALED_BINDING_SHAPE_ONLY_NOT_BALANCE_NOT_AUTHORIZATION_NOT_CUSTODY`
  与 `verified_scope = SHAPE_AND_IDENTITY_OF_SEALED_DOCUMENTS_ONLY`：
  `S3BudgetBindingProvider.sealed()` **不再被表述为**余额、有限授权或 native custody 的证明。
* 一个由本包测试自写的、字段完全正确的 PROVEN 链（native_custody / gpu_release / install /
  rollback / grant / tool_closure 全部就位）**依然不被接受**。
* 未来接口范围保留：`build_native_driver` 仍在，但只有别处已经完成 native 准入的调用者
  才能到达；CLI、序列化字段、`--force`、env 开关都无法打开它。

### M03 context hash 链与 provenance
* controller CLI **强制** `--context-sha256`：缺省 → `CONTROLLER_CONTEXT_HASH_ARGUMENT_REQUIRED`；
  非法 → `CONTROLLER_CONTEXT_HASH_INVALID`；不匹配 → `CONTROLLER_CONTEXT_SEAL_MISMATCH`。
* `build_production_command(context_path, context_sha256=…)` 现在**必须**带 hash，命令固定为
  `[python, -I, -B, tools/v0_s3_quality_worker.py, --context, <path>, --context-sha256, <hash>]`。
  新增的内部参数**只用于 hash**，没有任意 argv/module/回调。
* worker 的 `WorkerContext.load` **要求**期望 hash（`WORKER_CONTEXT_HASH_REQUIRED`），
  worker CLI **要求** `--context-sha256`；worker 的每次重载都用同一条预封存 hash 校验。
* seam 的 worker 线程从**命令里**取 hash（不从自身重算），并与 seam 预封存的 hash 交叉核对；
  在第一次 load 与正式 `worker.main` 的第二次 load 之间改动 `driver_arguments`/`source`/
  `projection` → 第二次 load 封存不符 → worker 拒绝（exit 2）→ 运行保持 UNKNOWN，无 summary。
* provenance：`controller_context` 现在记录**真正 controller context 的 bytes/hash**
  （来自被读取并校验的句柄），`worker_context` 单列；两者不再互相冒充。

### M04 有界安全读
新增 `tools/v0_s3_controller_io.py`，controller 与 worker 共用：
* 读之前先定界（`limit + 1` 是**真正向内核请求的上限**），超限文件在进入内存前被拒；
* `O_NOFOLLOW|O_NONBLOCK` 打开，类型由已打开句柄的 `fstat` 判定；
* 根内引用逐层 `dirfd + O_NOFOLLOW` 行走，祖先是链接即拒（不只末段）；
* 读后复核句柄（dev/ino/size/ctime/mtime/实读长度），读中变化即拒；
* 平台缺原语即 fail closed（`SAFE_OPEN_UNSUPPORTED`），不退回不安全读。
机器证据：精确上限文件读完；上限+1 文件在**未取字节**前被拒；从 `/proc` 读取大小说谎的文件时
循环在上限+1 处停止；FIFO 与 `/dev/null` 以 `FILE_NOT_A_REGULAR_FILE` 稳定拒绝；祖先链接以
`DIRECTORY_UNUSABLE` 拒绝。

### M05 最后消费重核
* provenance 的 canonical/source_plan digest **不再**由 controller 自己二次 `read_bytes` 得到，
  而是取自**父 owner 已重核的 manifest**；矛盾 hash 不可能出现。
* 消费边界：在写 summary 之前重新调用 owner 的 `manifest()`（内含对 root 与每个原件的
  重核）。`ORIGINALS_VERIFIED` 之后受控改动 **raw / canonical / root** → 父 owner 拒绝 →
  运行保持 `UNKNOWN_RETAINED`、根与预约保留、无 summary、无矛盾 hash。
* controller 消费的 canonical 字节（经根内安全读）与 owner 封存的 canonical digest
  **逐项交叉核对**，不一致即 `CONTROLLER_ORIGINALS_CHANGED_BEFORE_SEAL`（在 seal 之前就拒绝）。

### M06 根内 dirfd 排他落盘
* summary 与 reservation 都写在**绑定 root 的 dirfd** 之下：root 以 `O_DIRECTORY|O_NOFOLLOW`
  打开，`temp` 与 `temp/s3-production-controller` 逐层以 `dir_fd + O_NOFOLLOW` 打开/创建
  （`os.mkdir(..., dir_fd=)`），叶文件用 `O_CREAT|O_EXCL|O_NOFOLLOW` 写入。
* 任一层被换成链接或对象 → `CONTROLLER_DIRECTORY_UNUSABLE` → 拒绝，**根外零产物**
  （负例断言根外目录为空）。
* 只在本轮根内创建；未知外部内容不删除；写失败保留 partial 证据（不删、不覆盖）。

### M07 收据按完整义务
* `output_contract`：16 行全部 PASS 且每行都有 raw+suggestion 产物、产物被 manifest 覆盖、
  **且每行自报的产物 digest 与父 owner 封存的 digest 相同** → 否则 FAIL。
* `resource_budget`：16 行全部 PASS、`provider_calls_reserved` 为整数、且不超过
  `parent_budget_capacity` → 否则 FAIL（不再是“非 None 即 PASS”）。
* `no_overwrite`：16 行全部 PASS、phase 的 `exclusive_single_write` 与
  `descriptor_relative_writes` 为真、产物引用唯一且都在 `temp/s3-quality/` 内、被 manifest
  覆盖且 digest 相符 → 否则 FAIL。
* `file_safety`：manifest 存在 **且** 消费边界重核通过 → 否则 FAIL。
* `quality_16_rows`：`test_counts.PASS == 16` 且 `fixed == 16` 且行数为 16 → 否则 FAIL。
* `cleanup` 显式写 `cleanup_proven = false`；`root_retained` / `reservation_retained`
  **以产品清理证据决定**（清理未证 → 均为 `true`），不再由 worker 退出推导；
  退款/重发/归档一律 `false`。
* 顶层 12 键的 `BLOCKED` **不再**掩盖内部假 PASS：负例（release-unproven / residue /
  provider-refusal / 仅末行失败）下 `output_contract`、`resource_budget`、`no_overwrite`、
  `quality_16_rows` 全部为非 PASS。

### M08 普通异常 → 持久 UNKNOWN + 有界清理
* `run()` 捕获普通 `Exception` → `state = UNKNOWN_RETAINED`，
  `unknown_reason = CONTROLLER_UNEXPECTED_EXCEPTION:<Type>`，`exception_detail` 保留原始失败证据；
  `KeyboardInterrupt` / `SystemExit` **不吞**，在 finally 的有界清理之后重新抛出。
* `finally` 无条件执行：关闭 seam 自己的描述符、收 FD 快照、记录生命周期事实。
* 取得预约的运行会把收据**持久化**在根内 `receipt-<run_id>.json`（O_EXCL）；
  落盘失败时显式写 `receipt_persisted = false` 与 `receipt_persistence_error`，
  **绝不伪造成功**。未取到预约的拒绝（未发送任何 worker）不写根内收据。

### M09 发送前阻断重入
* 预检通过后、**任何 worker 发送之前**，在根内用 `O_EXCL` 建立
  `reservation-<run_id>.json`（含 run/candidate/authorization/root/时间戳）。
* 已存在同 run 的 summary → `CONTROLLER_SUMMARY_ALREADY_EXISTS`；
  已存在 reservation → `CONTROLLER_RESERVATION_ALREADY_EXISTS`；
  两者都在 **spawn 之前**拒绝：`spawn_attempts = 0`、seam `spawns = 0`、16 行不重跑、
  既有 summary 字节不变。
* 预约**不自动删除**：历史失败与预约保留，不换 runid 绕过，不复活旧 grant。
  并发争抢由 `O_EXCL` 保证最多一方运行。

### m01 seam 协作取消与诚实保留
* seam 线程**不再用 daemon 解决生命周期**（`daemon=False`）。
* `terminate()` = 协作取消（关 stdin + 置取消位）；`kill()` **显式抛错**
  （`LVW_S3_THREAD_CANNOT_BILLED`→`LVW_S3_THREAD_CANNOT_BE_KILLED`），父侧如实记 `kill_failed`。
* 取消在**下一次 submit 之前**检查（`_CancellableDriver` 在每次受控调用前检查取消位）：
  协作驱动 → worker 自行停止、线程被 join、`worker_thread_finished=true`、
  `late_write_after_return_is_possible=false`。
* 不协作的驱动（阻塞在自己的回调里）→ 运行保持 `UNKNOWN_RETAINED`，收据如实写
  `worker_thread_retained=true`、`worker_thread_killable=false`、
  `late_write_after_return_is_possible=true`；**不宣称**无晚到、无残留，
  测试自身释放并 join 自己的 Event（并明确这不是产品清理证明）。

### m02 worker 错误输出适配 text/binary
`quality_worker._write_refusal` 先按文本写，收到 `TypeError` 再按 UTF-8 字节写：
二进制流不再把 `WorkerError` 变成 `TypeError`，**准确拒绝码**在两种流上都保留
（`WORKER_FILE_SEAL_MISMATCH`、`NATIVE_EXECUTION_BACKEND_NOT_READY` 均逐字节核对）。

---

## 3. 集中定向范围与真实结果

范围的选择见 `selection.json`：**一次正例 + 11 项缺陷负例 + 必要兼容**。
旧的 123 / 84 / 13 / 41 / 186 / 257 分母**没有**被机械重跑，也**没有**被计入本轮。

| 计数 | 值 |
|---|---|
| 用例（distinct node） | **60** |
| 调用次数（invocation） | **60** |
| interim 批次 | **1** |
| 通过 / 失败 / 跳过 | **60 / 0 / 0** |
| 定向范围退出码 | **0**（`directed-scope.json`、`directed-scope.stdout.log`） |

用例构成：组合文件 54 个（33 个既有断言按合同更新 + 21 个新定向节点）+ supervisor 兼容 6 个。
新定向节点与发现的对应：

| 发现 | 负例节点 |
|---|---|
| M01 | `test_the_comparison_of_a_value_is_a_comparison_of_the_type_and_the_value` |
| M02 | `test_a_complete_self_written_proof_chain_is_never_an_admission`、`test_the_default_entries_refuse_the_native_execution_with_zero_spawn` |
| M03 | `test_the_command_line_entry_demands_the_exact_controller_context_hash`、`test_a_worker_context_that_changed_between_the_two_loads_is_refused` |
| M04 | `test_the_reads_are_bounded_regular_and_never_follow_a_link` |
| M05 | `test_an_original_that_changed_after_the_verification_is_refused[raw|canonical|root]` |
| M06 | `test_the_summary_is_never_written_outside_the_bound_root` |
| M07 | `test_a_failed_row_never_produces_an_internal_pass[release-unproven|residue|provider-refusal]`、`test_the_last_row_of_the_run_is_not_hidden_by_the_outer_state` |
| M08 | `test_an_ordinary_exception_keeps_a_persisted_unknown_and_cleans_up` |
| M09 | `test_a_second_run_of_the_same_run_id_is_refused_before_any_send`、`test_a_pre_existing_summary_is_refused_before_any_send` |
| m01 | `test_the_cooperative_cancel_stops_the_worker_and_the_thread_is_joined`、`test_a_worker_that_does_not_cooperate_is_retained_and_the_run_stays_unknown` |
| m02 | `test_the_refusal_of_the_worker_keeps_its_code_on_a_text_and_on_a_binary_stream` |
| 正例 | `test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary` |

正例（`run-root/` + `positive-example.receipt.json`）：正式 controller `main` → 固定生产命令
（含预封存 hash）→ 正式 worker `main` → 真实 `WorkerContext.load` → 真实 `QualityPhase` 16 行
→ 真实 `os.pipe` + `ProtocolWriter` → 父 `ParentSupervisor` 真实 reader → 真实 canonical receipt
→ 父 `ParentOriginalEvidence` 真封存/manifest 重核 → 本轮真实事实适配收据 → 根内 dirfd 排他
summary。**零 OS 子进程**：worker 跑在本进程线程上。收据写明
`pass_count = 0`、`key_count = 12`、`stage_pass_claim = false`、`product_gate0 = false`。

### 兼容回归（冻结 owner，非本定向范围）
`compat-regression.json` 与对应日志记录四个批次的真实 argv/退出码/双流：
supervisor 142 通过 / 14 跳过（fixture 进程测试的 machine gate 未绑定 → 跳过，**未启动任何宿主进程**）；
integration + quality_phase 449 通过；budget_authority 17 通过；runtime_binding 94 通过。
四个批次分开运行是因为冻结的 quality-phase 套件自带**进程级**离线 guard，与需要真实
subprocess 的 budget authority 套件同会话会互相干扰——这是冻结测试套件的既有属性，
与本次改动无关（两套单独运行均全绿）。

---

## 4. 边界与实测事实

* **零 OS 子进程**：本轮实现与证据只创建本进程线程、真实 pipe 与合成文件。
  独立 pre-import 审计钩子（`guard.py`）在候选 import **之前**装好，拒
  `subprocess`/`socket`/`os.fork`/`os.exec*`/`os.spawn*`/`os.system`/`sqlite3.connect`
  与受保护状态（shared counter、原账本）。
  * 自测：`guard-selftest` **9 项拒绝全部命中**（`guard-selftest.guard.json`）。
  * 正例与定向范围：**拒绝数 0**（`positive-example.guard.json`、`directed-scope.guard.json`）。
* **原 counter 仅外层只读**：`counter-readonly.json` 记录 `active=false`、`starts_total=28`、
  `reserved_wall_seconds=240.0`、`spent_wall_seconds=12.362`、
  `sha256 = acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`
  （与合同一致）。未退款、未清零、未新建 counter、未复活旧 grant（`EXPIRED`）。
* **未触碰真实服务 / GPU / 模型 / 媒体 / 下载 / 用户原件**：无。
* **启动参数**：retry 0、watchdog 0（未使用任何重试或看门狗）。
  本轮**未遇到 429**（因此不涉及 `WAIT_BUDGET` 路径）；**未请求任何审批**
  （因此不涉及审批拒绝/超时的 askroot 路径）。
* **临时 env**：本轮**没有**创建任何临时 env 目录或临时环境变量；
  `.claude/settings.local.json` 的临时设置由 root 按 hash 恢复，本包不自删。
* **单候选**：一个候选（base + 6 个变更源摘要），无并行候选、无中间交付。

---

## 5. C01–C12 / I01–I24 实际映射与保持未证项

逐项机器映射见 `obligation-mapping.json`（24 项逐条给出 owner、实际观察、已闭合的发现、
剩余缺口与 `complete_obligation`）。要点：

* **C 映射不是新分母**：固定 I 分母仍为 24，产品分母仍为 12，均未签。
* **24 项的 `complete_obligation` 全部为 `NOT_PROVEN`，`product_pass` 全部为 `false`**：
  本轮闭合的是**组件层**的 11 项发现，不是产品义务。
* 已闭合的组件层发现：M01/M02（I03、I04、I23）、M03（I07、I23、I24）、
  M04（I09、I23）、M05（I16、I24）、M06（I16）、M07（I07、I14、I17、I19）、
  M08（I09、I13）、M09（I13）、m01（I08）、m02（I21）。
* **明确保持未证**：native 执行后端与 native 后代 custody；Windows 平台与 reparse 语义；
  真实 A06 隔离；原账本的真实读取/扣账与旧 grant；真实独立质量评分与真实媒体/模型/GPU；
  完整工具依赖闭包；WebP、安装、回滚与产品级清理；固定 I01–I24 与产品 12 键的整体准入；
  root 迁移部署；人工体验/发布签署。
* 旧 13 项 fixture 组件证据**未被重跑、未被转记**为新候选已过；旧 grant 仍过期。

---

## 6. 风险与需要 root 裁决的点

1. **native 能力被硬拒绝是有意的空缺**：本轮把 native 路径从“看起来能用”改成
   “明确未实现”。这是合同的裁决，不是缺陷；但它意味着**任何真实 native 运行在当前代码上
   都会被拒绝**，直到另一次冻结包提供可信准入后端。真实能力冻结应作为独立的一批。
2. **worker CLI 增加了必填参数**：`--context-sha256` 现在是必填。任何外部调用方
   （含未来的人工/脚本入口）都必须同步传入预封存 hash。这是合同的直接要求，但对既有调用方
   是**破坏性变更**，需要在 root 的接口冻结记录中显式登记。
3. **收据文件落盘**：取得预约的运行会在根内写 `receipt-<run_id>.json`（O_EXCL）。若同一 run
   再次运行，收据文件已存在 → 落盘被拒并如实报告 `receipt_persisted=false`（stdout 上仍完整）。
   根内因此多出一个文件；如 root 不希望根内出现收据文件，需要另一次裁决（当前按 M08“保留收据”实现）。
4. **`no_overwrite` 的范围**：该收据的 PASS 只覆盖“本轮产物在自有阶段目录内被排他创建、
   且其真实字节与父 owner 封存一致”；**人工稿未被覆盖**这一部分在本离线合成运行中没有机器证据，
   因此人工导出的独立收据保持 `BLOCKED`。该边界写在收据的 `obligation` 字段里，不会被误读。
5. **m01 的诚实保留**：不协作的线程会被保留（而不是被假装杀掉），因此本包的离线证据里
   存在“运行返回后仍可能写文件”的**显式记录**。这是设计选择，不是遗留缺陷。
6. **`build_production_command` 的 hash 变成必填**：supervisor 的固定命令构造函数签名变了
   （keyword-only 必填）。除 controller 与测试外没有其他调用方（本轮已全包核对）。

---

## 7. 证据清单（本报告目录内）

| 文件 | 内容 |
|---|---|
| `report.md` | 本报告 |
| `candidate.json` | 候选身份：base、6 个变更源与 8 个冻结源的 sha256、git 状态 |
| `commands.json` | 三个真实命令的 argv/cwd/起止/退出码/双流日志名 |
| `guard.py` / `guard_selftest.py` | 独立 pre-import 边界与其 9 项自测 |
| `guard-selftest.guard.json` | 自测收据：9 项拒绝 |
| `positive-example.guard.json` / `directed-scope.guard.json` | 候选运行的边界收据：拒绝数 0 |
| `run_positive_example.py` / `positive-example.receipt.json` | 正例脚本与其真实收据（含 spawn 数、退出码、stderr） |
| `run-root/` | 正例的真实产物：contexts、input、temp/s3-quality（canonical + 80 件产物）、temp/s3-production-controller（reservation/summary/receipt） |
| `run_directed_scope.py` / `selection.json` / `directed-scope.json` | 定向范围脚本、范围选择与逐节点机器结果（含用例/调用/批次三种计数） |
| `directed-scope.stdout.log` / `.stderr.log` | 定向范围的真实双流日志 |
| `pytest-temp.zip` / `pytest-temp.manifest.json` | 每个用例的全部合成产物（5359 件，含逐件 sha256） |
| `collect_compat.py` / `compat-regression.json` + 4 组日志 | 冻结 owner 的兼容回归（真实退出码） |
| `counter-readonly.json` | 外层只读 counter 事实（inactive/28/240/12.362/hash） |
| `obligation-mapping.json` | C01–C12 / I01–I24 逐项映射与未证清单 |
| `collect_evidence.py` / `record_command.py` | 证据收集驱动与命令记录器 |

---

## 8. 开发大纲与角色状态（来自 `plans/execution-control.json` 的唯一快照）

当前权威坐标：**R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION**；
当前阻塞门：`S3_P4_OFFLINE_INTEGRATION_AND_MACHINE_FIXTURE_BINDING_PENDING`。

| Stage | 完成/总数 | 实现 | 机器验收 | 独审 | 人工签署 |
|---|---|---|---|---|---|
| V0-S0 | 1/2 | ARCHIVED | NO_GO_HISTORICAL | COMPLETED_WITH_BLOCKERS | NOT_SIGNED |
| V0-S1 | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| R0 | 1/2 | PARTIAL_REUSED | SINGLE_IMAGE_SUBSET_ONLY | 无独立裁决 | 无独立签署 |
| R1a | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| V0-S2 | 7/8 | IMPLEMENTED | COMPLETE_FIXED9_PASSED | COMPLETE_FATAL0_MAJOR0_MINOR0 | PENDING |
| V0-S3 | 0/6 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R1 | 0/4 | EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING | EARLY_SLICE_UM10_ONLY | EARLY_SLICE_FATAL0_MAJOR0 | EARLY_SLICE_APPROVED_FULL_R1_PENDING |
| V1-M1 | 0/3 | DESIGN_ONLY | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| V3 R3 / R4 | 0/4 / 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| V3 R5a / R5b / R5c | 0/4 / 0/4 / 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |

V2 设计已批准不等于实施激活。本轮**不**新增任何 Stage 结论：本包只交付一次集中纠偏的
实现与机器证据，状态是 **READY_FOR_REVIEW**；独立审查实例与人工签署仍由 root 组织，
本实现实例**不签** Stage PASS。

本任务未派生 Agent（唯一实现者，无 helper worker）。实现发生在 Orca 隔离 worktree；
原始 git worktree 与旧未跟踪文件、旧 report 改动均未被触碰。
