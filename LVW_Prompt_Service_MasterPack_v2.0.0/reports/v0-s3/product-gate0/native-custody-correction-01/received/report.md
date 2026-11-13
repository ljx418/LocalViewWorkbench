# N1 父侧 native custody 基础离线包 01：实现报告

> 实现者：Claude Code（唯一实现者，**未派生任何 Agent**）
> 状态：**READY_FOR_REVIEW / 批次已按 root 冻结执行包执行一次，结果 FAIL（8 failed / 46 passed）**
> impl HEAD `13e77492361648dc90a414f7fd37f0bb8b8c3634`；产品源码 `b95de076f37e64d321629c065e5531eba8a5250a`
> 范围合同：`reports/v0-s3/product-gate0/native-custody-implementation-01/contract.md`
> 架构裁决：同目录 `architecture-decision.md`
> 根的纠正与裁决：`msg_1dcd95570173`（**非执行 ACK**），逐条处理见 `correction-note-01.md`
> 执行授权：`msg_a468b84960db`（ACK 一次，仅 root 冻结执行包）；执行结果见 `native-custody-01.execution-report.md`
> 第二处勘误与本批结果：`correction-note-02.md`
> **不签 Stage PASS、不签产品 Gate0、不产生 admission 证据。**

---

## 0. 这个包是什么 / 不是什么

**是**：父侧 native custody 的**薄基础**。父将来直接启动一个 Windows broker，持有它的**原始创建句柄**
与一条私有控制通道；broker 用 `CREATE_SUSPENDED` 创建服务进程，先把它**纳管进本轮的 Job**，
再恢复它；父与 broker 都只停止**自己创建**的东西。

**不是**：不是服务平台，不是动态加载平台，不是 native 执行许可，不是 native/GPU/端口证明，
不启用现有 launcher，不改任何旧 owner。

| 新增文件（唯一） | sha256 | 行数 |
|---|---|---|
| `tools/v0_s3_native_custody.py` | `fbf4df5751ce6a819ebf2e677e39242b991186e6de040f99a8c96cfbefcf8e90` | 687 |
| `tools/v0_s3_native_broker.py` | `f2c10e6625e06aeb4da70506d5e75903ff28ecba3492017f06b4867d7d394a6f` | 1506 |
| `tools/test_v0_s3_native_custody.py` | `d0d5d4c07b7c073d3f3759e6c66fac94df6f8714d91ade3cef5a40b574f483fa` | 1050 |

| NEW 报告目录文件 | sha256 |
|---|---|
| `plan.json`（机器可读计划） | `86a7702e9e13617a9b80231e239fbb8e9041b2b3ffa8b312ea5b20f43a8eadc3` |
| `guard.py`（外部边界） | `12816fba33dd0874664f195847a599e1160099e85f5e8d3a89165b22744dfc80` |
| `runner.py`（外部 runner，只报告） | `c1ffb88686a4515aaddca3f362cd100a63db6653bc2fcf8d9939a14824fe8fd7` |
| `correction-note-01.md`（纠正记录） | `4d5f06446bbd3637694cc603b075bd3d3936810acffbb3c11a363f04a66baaeb` |
| `superseded-test-module-5cae1123.py.txt`（被取代版本的原始字节） | `5cae1123a49683389661bcb1dbe2ff8c680bcdae10c71fbded98438f595ddef4` |

执行后新增的证据（**不改动**上面任何被 root 计划 pin 的文件）：

| 文件 | sha256 | 说明 |
|---|---|---|
| `commands.json` | `22e482323ec519fb861eddfd49a55ee37ecd70433e938ee84faf0d2e3fefa972` | 精确命令、root 计划 hash、工具 hash、逐命令退出码与墙钟 |
| `native-custody-01.execution-report.md` | `b51f958c12c8b7db7f6315b2eda5839a4ce76ff7d69221e14430279a47acc31c` | 本批完整执行报告与 8 个失败的逐条根因 |
| `correction-note-02.md` | `f5dfd39841c7aa7057bd0e86e9a92866f6691f8e90a4e07db05f5af554697474` | 第二处抄写错误与本批真实结果 |
| `native-custody-01.receipt.json` | `5a8e96c027c5500e4c6834b561dc187ee437a85e431eec63145f161728cb32b2` | **root runner** 写的收据 |
| `native-custody-01.guard.json` | `336d5cdf11881596d828f743558b381d59e4f84885e2ca5e96e5bf3067ec2bbe` | **root guard** 写的记录 |
| `counter-before.json` / `counter-after.json` | `7338b51fd39a78203a59a9942984fdd182c9645936d0bc7df0bc5aa114838eb3`（**两者相同**） | 原 counter 的外层只读快照 |
| `native-custody-01.*.stdout.log` / `.stderr.log` | — | 三条命令各自的原始 stdout/stderr |

**旧文件零改动**：controller / worker / quality_phase / supervisor / coordinator / runtime /
driver / budget authority / local_program_authority / 协议 / 拒绝点 / MANIFEST / 旧证据，
全部未改；`tools/v0_s3_native_custody.py` 与 `tools/v0_s3_native_broker.py` 是**新增**文件，
没有任何旧文件被修改或被引用为写目标。

---

## 1. 权力来源与生产形态

```
父（controller）
 ├─ 原始创建句柄 + 原 Popen ──► Windows broker（本轮唯一）
 │                              ├─ Job Object（本轮唯一，KILL_ON_JOB_CLOSE，无 breakaway）
 │                              ├─ COMFY     （原 process/thread HANDLE）
 │                              ├─ OLLAMA    （原 process/thread HANDLE）
 │                              └─ SAMPLER   （原 process/thread HANDLE，可选）
 └─ 私有控制通道（stdin/stdout 的 broker 一侧，父独占）
```

* broker 与 quality_worker 是**兄弟**：worker 不创建 broker、不授予 broker 任何权力、
  不提供 PID、不提供路径。
* 父**不接管**任何 worker PID；父停止的唯一对象是它自己创建的 broker 原句柄。
* 父持有的身份来自**原句柄**（pid / 可执行文件 / 其 sha256），来自子进程的自述只记为
  `reported_by_the_broker: True / identity_source: CHILD_CLAIM`，**不作证明**。

---

## 2. 闭合计划（`lvw.s3-native-custody-plan/1`）

精确闭合键（多一个少一个都拒）：`schema`、`run_id`、`candidate_sha`、`authorization_sha256`、
`lease_expires_at`、`max_runtime_seconds`、`roles`。

| 校验 | 规则 |
|---|---|
| `run_id` | `[A-Za-z0-9][A-Za-z0-9._-]{0,79}` |
| `candidate_sha` / `authorization_sha256` | 40 / 64 位小写十六进制 |
| `lease_expires_at` | 有限数（非 bool）、正、**大于 now**；过期即拒 |
| `max_runtime_seconds` | **精确 int（非 bool、非 float）**、1…21600 |
| 预算 | `max_runtime_seconds ≤ 父有限 child 剩余`；剩余 ≤ 0 → `CUSTODY_NO_CHILD_BUDGET_REMAINING` |
| `roles` | 有限列表；仅 `COMFY`/`OLLAMA`/可选 `SAMPLER`；`COMFY`+`OLLAMA` 必在；不得重复；顺序被规范化为 COMFY→OLLAMA→SAMPLER（采样器最后建，因为它观测本轮两个服务） |
| 每 role | 精确键 `{role, tools, data, log}`；工具数固定（COMFY 2 / OLLAMA 1 / SAMPLER 2） |
| `tools[]` | 精确键 `{path, sha256}`；**绝对 Windows 路径**（盘符或 UNC）、无 `..`、sha256 64 hex、不重复 |
| `data` | 按 role 精确闭合：COMFY `{user_directory}`；OLLAMA `{}`；SAMPLER `{nvidia_exe, nvidia_sha256, max_seconds}` |
| `log` | **相对 runroot** 的 POSIX 引用；无绝对路径、无 `..`、无反斜杠、不得重复 |

**明确不接受的**：任意完整 argv、shell、script、eval、env、PID。带 `argv` 键的 role、
带 `shell` 键的 data、多一个键的 plan，全部在**任何创建之前**拒绝（`0 create`）。

命令形态**冻结在 broker 里**，不由计划携带：COMFY 的形态取自
`reports/v0-s1/wp-s1-03-phase-a/live_probe.py:156` 的 `comfy_wrapper_text` 与
`tools/v0_s2_driver.py:25` 的 `comfy_wrapper`；OLLAMA 取自同文件的 `ollama_wrapper_text:149`；
SAMPLER 取自 `tools/v0_s2_runtime.py:431` 的 `SamplerWorker.start`。

---

## 3. broker：Win32 原语与 Job 托管

### 3.1 声明与加载

* 只用已装 Windows Python 标准库 `ctypes`；无 pip / pywin32 / 下载 / 外部包。
* **延迟加载**：`WindowsApi()` 内部才 `_load_windows_api()`；非 Windows 平台在**任何创建之前**
  稳定拒绝 `BROKER_PLATFORM_UNSUPPORTED`，**绝不**降级为无约束 `Popen`。
* 指针尺寸安全：句柄一律 `wintypes.HANDLE`，指针一律显式 `ctypes` 指针，结构体字段全部声明；
  `kernel32` 以 `use_last_error=True` 载入，失败时用 `ctypes.get_last_error()` 取最后错误。
* 声明的 API：`CreateJobObjectW`、`SetInformationJobObject`、`CreateProcessW`、
  `AssignProcessToJobObject`、`ResumeThread`、`TerminateProcess`、`TerminateJobObject`、
  `WaitForSingleObject`、`GetExitCodeProcess`、`QueryInformationJobObject`、`CloseHandle`、
  `CreatePipe`、`ReadFile`、`WriteFile`、`SetHandleInformation`、`CreateFileW`、
  `InitializeProcThreadAttributeList`、`UpdateProcThreadAttribute`、`DeleteProcThreadAttributeList`。

### 3.2 每轮一个 Job

`CreateJobObjectW` → `SetInformationJobObject(JobObjectExtendedLimitInformation)`，
`LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`。
**不设** `JOB_OBJECT_LIMIT_BREAKAWAY_OK` ⇒ 子代不能脱离本轮 Job。

### 3.3 先悬停、后纳管、再恢复（不可换序）

```
create_process_suspended(CREATE_SUSPENDED)  →  assign_process_to_job  →  resume_thread
```

任一步失败：

* **Create 失败** → 本轮什么都没创建；关闭本 role 的管道；`UNKNOWN_RETAINED`；**不重试**。
* **Assign 失败**（含 Job 受限嵌套 / assign 拒绝）→ 只终止**本轮刚创建且仍悬停**的那一个原句柄，
  确认退出；关闭 thread/process/job 自有句柄；**不终止外部 PID，不允许无 Job 重试**。
* **Resume 失败** → 该进程已在 Job 内；终止本轮 Job；`UNKNOWN_RETAINED`。

失败路径**从不**退化成"先跑再纳管"，也**从不**按名字/任意 PID 接管。

### 3.4 句柄继承：服务进程不继承控制通道

子进程只拿到三样：自己的 stdout 写端、自己的 stderr 写端、`NUL` 作为 stdin。
Windows 上用 `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` **显式**给出继承集合，
因此 broker 的控制通道句柄、Job 句柄与其它任何句柄都不会进到服务里；
stdin 是 `NUL` 而不是 broker 的 stdin，控制通道因此不可能被子进程读到。

### 3.5 后代查询有界

`QueryInformationJobObject(JobObjectBasicProcessIdList)` 的缓冲按 cap **17** 分配；
`ERROR_MORE_DATA` 或数量越界 → `BROKER_DESCENDANT_LIMIT`；查询失败 → `BROKER_JOB_QUERY_UNKNOWN`。
**未知与超限都不是零**：`job_active_known=False`、`job_active=None`，本轮因此是 `UNKNOWN_RETAINED`。

### 3.6 停止与资源

停止只经**自己创建的**原句柄与本轮 Job：`TerminateJobObject` → 逐个 `WaitForSingleObject`
（有界 5 s）→ 查询 Job → 关闭 thread/process/job 句柄。
**逐句柄**记录 `exited` / `exit_code` / `process_handle_closed` / `thread_handle_closed` /
`job_handle_closed` / `job_active`。任一关闭失败、任一进程未确认退出 ⇒ `UNKNOWN_RETAINED`，
**资源泄漏不算成功**。

`BaseException` 仍执行自有资源清理并继续传播；清理不依赖日志或诊断先成功。

---

## 4. 私有有界控制通道

* 命令集合**只有** `STATUS` 与 `STOP`；不接 worker 提供的路径、PID、Shell 或外部命令。
* 帧：`schema=lvw.s3-native-custody-channel/1` + `run_id` + `candidate_sha` +
  `authorization_sha256` + **唯一 session nonce** + **严格递增 sequence** + 精确键集。
* 上界：单帧 ≤ 32 KiB；总帧 ≤ 1024；每个子进程 stdout ≤ 256 KiB、stderr ≤ 256 KiB；
  本轮新增文本 ≤ 8 MiB。越界 ⇒ 触发本轮 Job 的有界停止并保留 UNKNOWN 证据，**不延长期限**。
* 父侧读到 EOF、心跳缺失或绝对 lease 到期 ⇒ 同样触发有界停止并保留 UNKNOWN。
* 读通道**不阻塞**期限检查：broker 用**单个有界队列 + 一个后台读取线程**，主循环用
  `queue.get(timeout≤0.25s)` 轮询；期限由 broker 自己检查。
* **重复 STOP 幂等**：不重复创建、不重复终止、不重复计费。
* 通道由父独占；nonce 只绑定会话，**不是跨会话创建权的证明**。

> **Windows stdin EOF 语义未实测**：本包只提供代码与有界结构，**不承诺**父崩溃保障已证。
> `parent_crash_recovery_proven` 与 `windows_stdin_eof_proven` 恒为 `False`。

---

## 5. 绝对 lease 与只收紧的期限

```
effective_deadline = min(plan.lease_expires_at,
                         now + plan.max_runtime_seconds,
                         now + parent_child_remaining_seconds)
```

该期限**只被固定一次**（`NativeCustodySession._fix_deadline`）。STATUS、心跳、STOP
都不能延长它；evidence 里 `deadline_extended` 恒为 `False`、`absolute` 恒为 `True`。

`parent_child_remaining_seconds` **只是限额校验**，不是余额授权：
`grant_authority` 恒为 `NOT_VERIFIED`，`plan_sha256_proves` 恒为 `PLAN_INTEGRITY_ONLY`，
`admission_produced` 恒为 `False`。本包**不读账本**（根裁决 b）。

---

## 6. 状态机与证据

`NEW → VALIDATED → ARMED(job已创建) → RUNNING → STOPPING → RELEASED | UNKNOWN_RETAINED`

证据（`lvw.s3-native-custody-evidence/1`）分三层记录：**本轮 plan**、**broker 身份与通道**、
**租约与终态**；`failures` 逐条带稳定码。

恒为 `False` 的主张：`native_execution_proven`、`native_cleanup_proven`、`gpu_released_proven`、
`port_released_proven`、`sampler_proven`、`parent_crash_recovery_proven`、
`windows_stdin_eof_proven`、`admission_produced`、`stage_pass_claim`、`product_gate0`。

> Job 进程数为零**不等于** GPU 已释放。本包不签 `native_cleanup`，也不签 `GPU_RELEASED`。

---

## 7. 离线验证设计（54 节点，进程内 typed Win32 façade）

`FakeWin32` 与生产 façade **同名同形**，记录调用顺序，可在单个命名调用点失败
（`create` / `assign` / `resume` / `query_job` / `close` / …）。它**不**创建进程、不开 socket、
不碰文件——它是纯进程内对象，断言打在它的记录上。

| 合同验收项 | 节点 |
|---|---|
| 成功必须 CreateSuspended→AssignJob→Resume | `test_the_success_path_is_suspend_assign_resume` |
| 子进程只继承自己的流 | `test_the_child_inherits_only_its_own_streams` |
| bool/int/finite/未知 role/任意 argv 拒绝且 0 create | `test_a_bool_runtime_is_refused`、`test_a_float_runtime_is_refused`、`test_a_nonfinite_lease_is_refused`、`test_an_unknown_role_is_refused`、`test_an_arbitrary_argv_key_is_refused`、`test_a_create_failure_creates_nothing` |
| Create/Assign/Resume 每个失败点只处理已持有本轮句柄 | `test_a_create_failure_creates_nothing`、`test_an_assign_failure_stops_only_the_new_suspended_process`、`test_a_resume_failure_keeps_the_round_unknown` |
| 外来同 PID/记录不能 stop | `test_a_foreign_process_is_never_stopped` |
| 部分角色启动失败 | `test_a_partial_role_failure_stops_the_earlier_roles` |
| job 查询未知/超限 | `test_an_unknown_job_query_is_not_zero`、`test_an_over_limit_job_query_is_not_zero` |
| close 失败 | `test_a_close_failure_keeps_the_round_unknown` |
| 重复 STOP 幂等 | `test_a_stop_is_idempotent`、`test_a_repeated_stop_is_idempotent` |
| EOF/期限到期 | `test_a_channel_eof_stops_the_round`、`test_the_absolute_lease_stops_the_round` |
| 控制 nonce/seq/extra 键/边界 exact+one-over | `test_a_foreign_nonce_is_refused`、`test_a_repeated_sequence_is_refused`、`test_an_extra_key_in_a_command_is_refused`、`test_a_frame_at_the_limit_is_accepted_and_one_over_is_refused`、`test_an_oversize_command_is_refused`、`test_a_reply_with_a_foreign_identity_is_refused`、`test_the_frame_count_limit_is_enforced` |
| 全部句柄清理 | `test_the_job_is_closed_with_kill_on_close`、`test_a_stop_is_idempotent` |
| 预算与期限只收紧 | `test_no_remaining_child_budget_is_refused`、`test_a_runtime_above_the_child_budget_is_refused`、`test_the_session_does_not_extend_the_deadline` |
| 旧拒绝点保持 | `test_the_old_owners_are_unchanged`、`test_the_old_refusal_points_are_still_declared`（**只算 integrity，不算功能通过**） |

> 假 façade 只证明**它驱动的分支**，**不证明**真实 Windows stdin EOF 与真实 Job 行为。

---

## 8. 边界与执行（外部 guard / runner / plan）

根的 `msg_1dcd95570173` 要求把边界移出测试模块。三件套：

* **`guard.py`** —— `sys.addaudithook` 边界。**按前缀**拒 `subprocess.` 与 `socket.` 全体成员；
  按精确名拒 `os.system/os.exec/os.spawn/os.posix_spawn/os.fork/os.forkpty/sqlite3.connect`；
  拒 `open` 原 ledger 与原 counter，**无任何豁免**（没有 registry 放行）。握手自证活动；
  自检只用 `sys.audit`，不真起子进程、不真开 socket。
* **`runner.py`** —— 顺序固定：读计划 → **装 guard 之前**以 `O_RDONLY` 打开原 counter 并读一次 →
  装 guard → 自检 → **显式 `sys.path.append`** 封存依赖路径（不用 `site.main`、不用 `.pth`）→
  **guard 之后**校验 pins（17 个 source + tool + **223** 个命名依赖）→ FD/线程盘点 →
  **一次** `pytest.main`（`collection_finish` 逐项**有序**比较节点集合，不等就在任何 test call 前退出）→
  FD/线程再盘点 → counter 再读一次 → 写收据与 raw logs。
* **`plan.json`** —— 机器可读计划：绝对 argv、cwd、54 节点顺序、source·tool·223 pins、
  ≤300 s、raw logs 路径、FD 身份与线程策略、integrity-only 节点、NOT_PROVEN 清单、四项根裁决。

原 counter 只被**外层**读（装 guard 之前打开、之后用同一 fd `pread`），不写、不退款、不复活、不新建。

> **本批实际执行的不是上面这三件套。** root 的 ACK（`msg_a468b84960db`）指定**只有 root 冻结执行包**
> `…/native-custody-implementation-01/validation-plan-02` 的 `plan.json`（sha256 `f028d42a…84cd9`）、
> `guard.py`、`runner.py`、`outer_counter_read.py` 是执行对象；**我提交的这三个文件没有被执行**，
> 它们按 root 的要求**原样保留、未改一个字节**。本批的真实边界与证据以 root 的
> `native-custody-01.guard.json` / `native-custody-01.receipt.json` 为准（见 §11 与
> `native-custody-01.execution-report.md`）。

---

## 9. 根的四项裁决在本包的落地

| 裁决 | 落地 |
|---|---|
| (a) 媒体工具绑定归 N2 | plan 闭合键集未扩；broker 的 COMFY 冻结环境**不设** `LVW_FFMPEG_EXE` / `LVW_VIDEO_PROBE_BACKEND`；本包**不声称**媒体装配完整 |
| (b) 余额授权归父与原 authority | N1 入参只做限额校验；`grant_authority=NOT_VERIFIED`；不读账本 |
| (c) nonce 走固定 `--nonce` | broker 入口参数集固定为 `--plan/--plan-sha256/--run-root/--nonce`；nonce 不进 plan；nonce 只绑会话 |
| (d) 父原始 HANDLE + Job，不接管 worker PID | broker 只停自己创建的句柄与本轮 Job；本包**不生成**任何 pid 文件；S2 `wrapper.pid`/`_prove_listener_owned` 未动，N2 需显式兼容 adapter |

---

## 10. N2 必须承接的三件事（本包不做，也不越权）

1. **媒体工具绑定**：COMFY 固定环境里的 `LVW_FFMPEG_EXE` / `LVW_VIDEO_PROBE_BACKEND` 需要
   部署侧提供 ffmpeg/ffprobe 的绑定；N1 的闭合 plan 不收这两个工具。
2. **S2 兼容 adapter**：broker 直接创建服务，**没有** PowerShell wrapper，因此没有
   `comfy-wrapper.pid`；S2 的 `_prove_listener_owned` 依赖该 pid 文件。N2 需要一个**显式**
   消费原始 owner 事实（broker 的原句柄证据）的兼容 adapter，**不得**伪造 pid 文件、
   **不得**跳过 S2 的证明。
3. **父侧 authority 接线**：`grant_authority` 从 `NOT_VERIFIED` 变成真实值，需要 N3 用原
   `local_program_authority` 对原 child/ledger 的验证结果由父持有；本包不产生该结果。

---

## 11. 本批执行结果（诚实记录）

**批次结论：FAIL。** root 授权 `msg_a468b84960db`（`ACK_ONCE_ROOT_FROZEN_EXTERNAL_RUNNER`），
唯一权威计划为 root 冻结执行包 `validation-plan-02/plan.json`
（sha256 `f028d42a3f652a09f798e4d2269e8726c9cefc89235d11dce9738c8fd9f84cd9`，与 ACK 一致）。
**执行对象是 root 的 guard/runner**；我提交的 `runner.py` / `--run` main **没有**被执行。

| 项 | 结果 |
|---|---|
| 命令 | 3 条（counter-before / guarded-validation / counter-after），逐条按计划的精确 argv+cwd |
| pytest 退出码 | **1** |
| 调用 / 通过 / 失败 / skip | 54 / **46** / **8** / 0 |
| **功能节点通过** | **45 / 52**（**不是** 54 项功能通过） |
| integrity 节点 | 2 个，1 通过 1 失败 |
| collection 与冻结顺序 | 逐项相等且顺序一致 ✓ |
| guard | 先于候选与 pytest ✓；自检 6 拒 ✓；运行时越界 **0** ✓ |
| FD / 线程 | 新增或复用 FD **0**；unknown **0**；线程 `['MainThread']`→`['MainThread']`；`cleanup_proven_for_batch=true` ✓ |
| 原 counter | 前后**逐字节相同**（`acbdb8b1…`，inactive，28 / 240 / 12.362），未写/未退款/未清零/未复活 ✓ |
| 墙钟 / 批次 | 合计 0.709 s（受保护批次 0.655 s，上限 300 s）；批次数 1（上限 1） |
| 真实 native 动作 | **无** |

8 个失败的根因（详见 `native-custody-01.execution-report.md` §4）：
**1 条产品源码缺陷**（闭合计划的日志引用未拒盘符绝对路径 `C:/...`）
+ **7 条测试侧缺陷**（假 façade 的调用记录缺句柄、假 façade 抛通用错误码而非生产码、
一条帧数期望写错、一处旧 owner 摘要末位抄写错误）。

**本批未应用任何修正**：被执行的候选与 root 计划 pin 的 18 个 source/tool 项**逐字节未改**，
root 的计划/guard/runner 与我提交的计划/guard/runner/勘误/被取代版本的原始字节**全部原样保留**。
修正清单见执行报告 §5，需要 root 重新冻结计划并重新 ACK。

* FIRST 429 ⇒ 立即 `WAIT_BUDGET` 停（未触发）；审批拒绝或超时 ⇒ 停，不包装绕过（未触发）。
* **不签 Stage PASS、不签产品 Gate0、不宣称任何 native 能力已证。**
* `grant_authority` 仍 **`NOT_VERIFIED`**；`admission_produced` 仍 **false**。
