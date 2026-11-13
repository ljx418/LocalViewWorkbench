# S3-P4-OFFLINE 审计纠偏 02：守卫凭据、失败结算、安装握手与完整收据

候选基线 `74ff021934afef661f8c7e8c1c4f11b26f7c3360`；本轮零进程、零网络、零 fixture 子进程、零原账本写入。
本报告是实现者的 **READY_FOR_REVIEW**，不是 Stage PASS，不声明产品 Gate0。

## 0. 范围、授权与只读确认

- 只改了三个可执行源：`reports/v0-s3/product-gate0/implementation-integration-01/executor.py`、
  `reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py`、
  `tools/test_v0_s3_supervisor.py`；新增本报告目录
  `reports/v0-s3/product-gate0/implementation-integration-audit-correction-02/`。
  其他生产 owner、冻结合同、公共门限分母（24）、控制 MANIFEST 与 V2 未动。
- 旧 `implementation-integration-01/report.md` 的未提交改动与既有未跟踪工件原样保留，未清理、未 `git add`。
- 环境只读确认（继承 worktree 根的 env-only 设置，未改设置）：`CLAUDE_CODE_MAX_RETRIES=0`、
  `CLAUDE_CODE_RETRY_WATCHDOG=0`。本轮未遇 429，未重试、未换路由、未换供应商/模型，未调用 Harness/Codex。
- 原共享 counter 只读核对：`sha256 = 8cc8ed9ac56f92db817bfc79dacfb69145adf8ade6f7c4605551ca7dd4f5dc37`，
  与独审 counter-before/after 记录**逐字节相同**；`active=false`、2 PENDING、`starts_total=2`、
  `reserved=120`、`spent=2.896` 全部保持。两笔历史 PENDING 未退款、未清零、未消耗；
  它们的终态裁决仍属 root。证据：`audit-correction-02-counter-readonly.txt`。
- 未创建任何 fixture 子进程、未启动服务、未访问网络、未碰模型/GPU、未读原 ledger。
  所有计数器均为临时 synthetic counter（临时目录，脚本退出即删）。

## 1. 四项采纳纠偏的逐条交付

### M1 before-fork 释放必须来自本次真实 guard 审计动作

- **路径**
  - `reports/v0-s3/product-gate0/implementation-integration-01/executor.py`：
    新增 `RefusalCredential`、`refusal_credential_of()`、`FiniteCpuExecutor.mint_refusal_credential()`、
    `FiniteCpuExecutor._verify_refusal_credential()`；`spawn()` 建立**动作作用域**（每次启动一枚新 nonce），
    `admit()` 把该 nonce 绑进本次 token，`_settle_without_handle()` 只在凭据通过绑定校验时结算
    `REFUSED_BEFORE_FORK`，否则一律 `UNKNOWN`。
  - `reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py`：
    `_audit_hook()` 在**进程创建类**审计事件（`subprocess.Popen`/`os.posix_spawn`/`os.fork`/`os.forkpty`）
    被拒时向当前 executor 索取一次性凭据并挂到异常上（`REFUSAL_CREDENTIAL` 属性）。
  - `tools/test_v0_s3_supervisor.py`：两条正例改为**走真实 guard 链**（不再手工构造异常充当凭据），
    并新增负例与正例各两条。
- **凭据模型（小范围进程内关联，不建签名平台）**
  凭据由 guard 在**本次真实审计动作内**铸造，绑定四元组：`executor_id`（本 executor 实例）、
  `charge_index`（本次 charge）、`thread_id`（本次线程）、`action_nonce`（本次动作）。
  凭据**一次性消费**：首次结算即置 `consumed=True`。
  - 复制 `lvw_before_fork` 标记 + 复制 `CpuGateError`：无凭据 → `UNKNOWN`，槽位保留、根保留、finalizer 非零。
  - 重放旧真实 guard 异常：凭据已消费且 nonce/action 不匹配 → `UNKNOWN`，不释放任何槽位。
  - 真实 guard 正例：guard 自己铸造的凭据 → `REFUSED_BEFORE_FORK`，槽位释放、`created=False`、不退款。
- **Oracle**
  `tools/test_v0_s3_supervisor.py::test_the_real_guard_refusal_releases_the_slot_of_its_own_charge`（正）、
  `::test_a_copied_marker_and_a_copied_gate_error_release_nothing`（负）、
  `::test_a_replayed_real_guard_refusal_releases_nothing`（负）；
  探针 `negative_probes_correction02.py` 的 `m1_real_guard_positive`、`m1_replay_negative`。
- **真实命令与外层退出**
  `python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode focused
  --label audit-correction-02-focused --modules tools/test_v0_s3_supervisor.py
  --select "refused_start or machine_accounting or real_guard_refusal or copied_marker or replayed_real_guard or settlement_failed or proof_of_a_child or guard_installation or complete_effective_command"
  --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-02` → **外层退出 0**，
  `10 passed, 90 deselected`。
- **日志 hash**
  `audit-correction-02-focused.stdout.log` = `e63151c7348a78c844ba314bd698037cd33065e22ffc6e2675808f7f09e435f3`；
  `audit-correction-02-focused.stderr.log` = `e3b0c442…7852b855`（空）；
  `audit-correction-02-focused.receipt.json` = `0878900bc8c605a939330cf210f0bd9b81f8a6e22b17d5a280d195e189f67ddb`。
- **清理**：runner owned root 已删除（receipt `owned_root_removed=true`、`cleanup_proven=true`）；
  探针的 synthetic counter 在临时目录内，退出即删；无进程、无句柄、无后台线程残留。
- **风险**：真实 guard 正例依赖审计事件链（`subprocess.Popen` 准入 → 进程创建事件被拒），
  这正是 CPython 在 `posix_spawn` 路径上给出的序列；零进程验证下该链由 `sys.audit` 逐事件驱动，
  **没有**真的 fork。`fork_exec` 路径上 `subprocess.Popen` 之后不再有进程创建审计事件，
  正常启动路径不受影响。凭据绑定是进程内的，不抵抗任意内存篡改——与独审声明的威胁模型一致。

### M2 结算失败必须是 open/UNKNOWN，不能假写已持久化终态

- **路径**
  - `executor.py::_settle_without_handle()`：**先结算、后移出 pending**；`counter.finish` 抛错或返回未结算时，
    状态回落为 `UNKNOWN`、`uncertain=True`、charge **留在 pending**（由 reaper 再次结算），
    本地账本写 `settlement_persisted=False` + `settlement_error`，不写已持久化终态。
  - `executor.py::reap()`：**有句柄**路径同样处理——`finish` 失败时 `persisted=False`，
    proof 里显式带 `persisted`/`settlement_error`，`entry['state']='UNKNOWN'`，
    `record['settlement_persisted']=False`；**无句柄** leftover 路径不再静默 `pass`，记录失败原因。
  - `executor.py::unsettled_charges()`：`settlement_persisted is False` 的 charge 记为未结算。
  - `run_guarded_checks.py::finalize_session()`：proof 的 `persisted is False` → `CHARGE_SETTLEMENT_FAILED`，
    `cleanup_proven=False`、退出码非零、owned root 保留。
  - `tools/test_v0_s3_supervisor.py`：两条新用例覆盖**有句柄**与**无句柄**两条 finish 失败路径。
- **Oracle**
  `::test_a_charge_whose_settlement_failed_stays_open_and_keeps_the_root`（无句柄）、
  `::test_the_proof_of_a_child_is_never_written_before_its_settlement`（有句柄）；
  探针 `failed_finish`（旧 oracle 反转）。
- **真实命令与外层退出**：同 M1 的 focused 命令 → **外层退出 0**，`10 passed`。
- **日志 hash**：同 M1（同一收据与日志）。
- **清理**：合成 counter 留在临时目录；失败路径下 owned root **按设计保留**并留在断言里，
  探针收尾时由临时目录一并清理；无子进程。
- **风险**：`starts/reserved/spent` 不减、不退款、不清零的语义未变；本项只改变
  “结算未被持久化时本地不得写终态”这一条。真实 counter 的两笔历史 PENDING **未** 被本轮触碰。

### M3 安装必须被证明真正活跃，拒绝即 failclosed 并留证

- **路径**
  - `run_guarded_checks.py`：新增 `GuardInstallationError`、`GUARD_HANDSHAKE_EVENT`、
    `guard_handshake()`、`confirm_guard_active()`；`install_offline_guard()` 改为
    “注册 → **握手证明** → 才置 `hook_installed`”；`_audit_hook` 以**注册实例绑定**的方式应答握手
    （绑定 registry + 每次注册的 token），外部/旧注册的 hook 无法应答本次握手。
  - 显式异常与 CPython 静默拒绝（既有策略 hook 在 `sys.addaudithook` 事件抛错）都 failclosed：
    `hook_installed=False`、`hook_install_count=0`、`install_error` 落盘，
    **下一次调用不凭虚假 installed 成功**，且不会二次调用注册 API（避免第二个 hook/第二道闸）。
  - `main()` 把安装移到 pytest 与任何候选 import **之前**；失败时写
    `<label>.receipt.json`（`guard_installed=false`、`pytest_imported=false`、`candidate_imported=false`）
    并以非零退出，**不导入 pytest、不导入候选**。
  - 收据 `guard` 段改为真实状态（`handshake_confirmed`/`handshake_count`/`install_error`），
    不再硬编码 `True`。
- **Oracle**
  `::test_the_guard_installation_is_proved_by_an_owner_bound_handshake`（正）、
  `::test_a_refused_guard_installation_fails_closed_and_keeps_the_evidence`（负）；
  探针 `m3_handshake_positive`、`m3_registration_failure_negative`、`m3_silent_rejection_negative`。
- **真实命令与外层退出**：同 M1 的 focused 命令 → **外层退出 0**；
  guard 自检 `--mode guard` → **外层退出 0**，connect/bind/Popen/system 四事件全部拒绝。
- **日志 hash**：`audit-correction-02-guard.stdout.log` = `6e3db9bee7880783c6d86acad60653571ecf173c497793d487ec8c3758f8db7d`，
  `audit-correction-02-guard.stderr.log` = 空，`audit-correction-02-guard.receipt.json` = `86db105ec474133b0da77904a9f7b32901fbacc900b6dee48460980a801ec82c`。
- **清理**：无进程；握手是纯审计事件，无副作用。
- **风险**：握手要求本进程的 hook 真正应答；若宿主环境已有策略 hook 拒绝 `sys.addaudithook`，
  本 runner 将**拒绝运行**而不是降级运行——这是有意的 failclosed，但会让“被策略环境包裹”的
  启动方式无法执行测试，需由 root/宿主解除该策略。alias 幂等与单 owner 未放宽
  （`hook_install_count` 仍为 1，alias 只共享 registry/gate/owner）。

### m1 收据保存完整有效执行命令与参数

- **路径**：`run_guarded_checks.py` 新增 `build_effective_command()`、`invocation_evidence()`、
  `_argument_pairs()`、`_normalized_pairs()`；收据新增 `command`（完整有效命令）、
  `command_semantics`、`effective_arguments`、`invocation`、`orig_argv`，并保留原 `argv`。
  命令含 `--modules`/`--select`/`--binding`/`--binding-sha256`/`--role`/`--candidate-sha`（给了才写，不编造）。
  `invocation` 区分 **process**（`sys.orig_argv` 里确有 runner 本体）与 **programmatic**（外层无 runner argv）
  与 **UNKNOWN**（`sys.orig_argv` 不可得）；旧收据一律不改。
- **Oracle**：`::test_the_receipt_saves_the_complete_effective_command`；探针 `m1_command_positive`、`m1_invocation_negative`。
- **真实命令与外层退出**：同 M1 的 focused 命令 → **外层退出 0**。
- **日志 hash**：同 M1。
- **清理**：无副作用。
- **风险**：`command` 语义由“base command”变为“完整有效命令”，属于**内部兼容变化**：
  任何按旧语义解析 `receipt.command` 的下游会看到更长的参数列表（信息增加，不是信息减少）。
  `invocation` 是新增字段，旧解析器忽略即可。

## 2. 执行证据汇总（真实命令、外层退出、日志 hash）

| 检查 | 真实命令（在本包根执行） | 外层退出 | 结果 | 日志 sha256 |
|---|---|---|---|---|
| 定向四项正负例 | `python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode focused --label audit-correction-02-focused --modules tools/test_v0_s3_supervisor.py --select "refused_start or machine_accounting or real_guard_refusal or copied_marker or replayed_real_guard or settlement_failed or proof_of_a_child or guard_installation or complete_effective_command" --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-02` | 0 | 10 passed / 90 deselected | stdout `e63151c7…e435f3`，stderr 空 |
| 必要定向回归（被触及区域） | 同上，`--label audit-correction-02-regression --select "executor or charge or counter or settlement or session or slot or custody or termination or deadline or watchdog or finaliz or reap or admission or budget or concurrency or wall or guard or alias or production_entry or single_guard or offline_boundary or refused_start or unknown_start or machine_accounting or proof or handshake or effective_command or copy or replay"` | 0 | 57 passed / 1 skipped（机器闸门用例，无绑定即跳过）/ 42 deselected | stdout `f9e01b08…24ddc77`，stderr 空 |
| guard 四事件自检 | `python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode guard --label audit-correction-02-guard --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-02` | 0 | connect/bind/Popen/system 全部拒绝 | stdout `6e3db9be…8db7d`，stderr 空 |
| 转换后负例探针 | `python3 -B reports/v0-s3/product-gate0/implementation-integration-audit-correction-02/negative_probes_correction02.py` | 0 | `CONVERTED_ORACLES_OK` | stdout `fd005453793ee9666e4d7a60972ee9328ddf5c55346bda92d091088ec8529b3e`，stderr 空 |

没有机械重跑 92/71/257 全集；只跑了被触及区域的一次必要定向回归与一次 guard 自检。
每条命令的真实 argv 都在各自 receipt 的 `command`/`invocation` 字段里，外层 stdout/stderr/退出码另存为
`*.outer.json` / `*.outer.stderr.log`。

## 3. 独审旧 oracle 的转换

起点是独审的 `audit-correction-review-01/received/negative_probes.py`。旧脚本**以复现缺陷为成功**
（缺陷出现即退出 0）；本轮保留全部原触发条件，把每条 oracle 反转为“缺陷必须被拒绝/不得假绿”，
并补四项生产路径定向负例与正例。逐条对照见 `audit-correction-02-oracle.txt`。
旧脚本与其原始日志未被修改、未被删除。

## 4. 公共合同与内部兼容

- **公共合同：none。** 冻结的 `s3-integration-offline-contract-01.md`、24 项固定分母、
  公共 API/Schema/状态机、MANIFEST 与 V2 均未改动；无 ADR 需要新批准。
- **内部兼容变化（明确声明）**
  1. `executor.py`：可信的 before-fork 判定从“标记 + 类型”改为“一次性、绑定 executor/charge/thread/action 的凭据”；
     `is_proven_before_fork_refusal()` 被 `refusal_credential_of()` 取代（本包内唯一使用者已迁移）。
  2. `executor.py`：charge 账本新增 `settlement_persisted`、`settlement_error`；
     `session_evidence()` 新增 `settlement_failures`；proof 新增 `persisted`、`settlement_error`；
     `unsettled_charges()` 新增 `settlement_persisted`、`settlement_error` 两个键。
  3. `run_guarded_checks.py`：guard 安装新增“注册实例绑定握手”与 failclosed 出口码 5；
     `install_offline_guard()` 在证明不成立时**抛 `GuardInstallationError`** 而非静默返回 owner；
     `__main__` 不再自行安装，改由 `main()` 在任何候选 import 与 pytest 之前安装并证明。
  4. `run_guarded_checks.py`：收据 `command` 由 base command 变为完整有效命令，新增
     `command_semantics`/`effective_arguments`/`invocation`/`orig_argv`；`guard` 段字段由硬编码改为真实值。
  5. `tools/test_v0_s3_supervisor.py`：两条旧正例改为走真实 guard 链，新增 8 条定向用例。

## 5. 一个必须记录的观察

CPython 3.12 的审计 hook **按注册顺序调用**（先注册者先执行），不是文档里写的逆序。
这解释了历史事故的形状：生产 hook 先准入并 charge，随后安装的 alias hook 才在**同一个**
`subprocess.Popen` 事件上拒绝，于是留下“有 charge、无句柄”的 PENDING（历史那两笔）。
本轮因此把“拒绝凭据”的来源绑定到**本进程本注册的那一个 hook**，而不是绑定到任何异常；
外来 hook 的拒绝不再释放任何槽位（保守为 UNKNOWN）。这一观察是实现侧的读数，
供 root 与独审参考，不改任何公共合同。

## 6. 未证明 / 仍然阻塞

- **13 个 fixture：仍 NOTPROVEN。** 本轮零进程、零 fixture 子进程，未执行任何 fixture 场景；
  两个历史失败 run 的原件与原始 traceback 未改、未重跑。
- 实子进程 custody、I08/I09/I13/I14、真实停止与清理、Windows 服务/后代/GPU 释放、
  A06 实机权限与隔离、原账本 debit、最终 A/B 预算、新鲜真实 12 项/质量/人签：**全部未证明**。
- 原 24 项固定分母不变，本轮只检查守卫与失败记账，**不重新宣布这 24 项通过**。
- 原 counter 的两笔 PENDING 未退款、未清零、未消耗；其历史终态裁决由 root 另立并绑定原件哈希。
- 未做人工体验签署，未宣布 Stage PASS，未宣布产品 Gate0。

## 7. 证据目录

`reports/v0-s3/product-gate0/implementation-integration-audit-correction-02/`：
`report.md`（本文件）、`audit-correction-02-oracle.txt`（oracle 转换）、
`audit-correction-02-counter-readonly.txt`（counter 只读核对）、
`negative_probes_correction02.py`（转换后探针）、三组 receipt/stdout/stderr 与外层 stdout/stderr/退出码。

候选源 sha256（提交前）：
`executor.py` = `1cafd73ffef7230ca088b49d408f4ce4b69f5be10e238cb6710fa1e8a78d0787`、
`run_guarded_checks.py` = `da688b1502dcf625bbbf883c5e7e519d0c4c386a51fafa15539a69e2331d1005`、
`tools/test_v0_s3_supervisor.py` = `52aa2dbe2332a3f740c0fdc9d8131132aa2c765eccff4208c82ceb2e439c4815`。
