# S3-P4-N1 纠偏 02：完整独审 11 Major + 1 Minor 的集中修复实现报告

状态：**READY_FOR_REVIEW**（实现者自检）。**不是** Stage PASS，**不是** 产品 Gate0，
**不是** 人工签署。本包所有输出都带 `stage_pass_claim = false` 与
`product_gate0 = false`。

> 本包只回答独审 `msg_287dbc62810a` 的 11 项 Major 与 1 项 Minor（root 裁决
> `msg_fdd5493bfaed`：全部采纳，采用有界传输方案 A 并按其收紧）。旧 N1 架构、
> 门限与安全原则不变；旧 owner 与全部 native 拒绝点未改；旧 54 失败、纠偏 01
> 的 32 通过与独审的 11 项 2 PASS/9 FAIL 等历史事实一律不改写。真实 Windows
> 仍 NOT_PROVEN。

> 本报告的分类口径已按 root 裁决 `msg_5bd04c08d05a` 更正（见 §6.4 与 §8）：
> 批次 01 的两个根因 **R1 与 R2 正是被独审的 M05 / M07 / M08 / M09 义务本身**，
> 不是一个与独审落点无关的实现噪声；批次 01 的 97 个通过**不关闭任何一项独审
> Major**，最终由隔离独审裁决。批次 01 的报告版本保留在同目录
> `report-attempt01.md`（sha256 `2f326bdf1443fc187b3f0d127bf56b7524c1d888ec6c7d989eb2199a14b7a874`）。

## 1. 范围与坐标

| 项 | 值 |
|---|---|
| Stage / Workpack | R1 / WP-R1-U3（S3_P4_OFFLINE_INTEGRATION_PREPARATION） |
| 阻断门禁 | `S3_P4_N1_ELEVEN_MAJOR_CUSTODY_AND_DEADLINE_CORRECTION` |
| 交付 HEAD（实施起点） | `8504fd6cab519ce33cea5382f7b3d8405667f479` |
| 代码基线 | `9352a34cfa8ea9715437b5ffa5d411369dd5548d` |
| 独审 | `msg_287dbc62810a`，Fatal 0 / Major 11 / Minor 1，原 11 探针 2 PASS / 9 FAIL |
| 允许改动的源 | `tools/v0_s3_native_custody.py`、`tools/v0_s3_native_broker.py`、`tools/test_v0_s3_native_custody.py`、本 NEW 报告目录 |
| 未改动 | 旧 controller / worker / QualityPhase / supervisor / runtime / driver / authority / 公共合同 / 协议 / 阈值 / control / MANIFEST / 旧报告 |

本轮只改三规定源与 NEW 报告目录。`git status` 中 `reports/v0-s3/product-gate0/
implementation-integration-01/report.md` 的既有未提交改动属于本任务之外的旧状态，
未 clean、未 reset、未纳入本批。

## 2. 逐项落点：生产函数 → 驱动 → Oracle → 正负例 → 终态 → 清理

### A 段：计划与 Windows API 声明

| 独审项 | 生产函数（位置） | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M01** user_directory 前缀匹配可逃逸 | `tools/v0_s3_native_custody.py:_require_directory_name`（由 `_validate_role_data` 调用） | `validate_launch_plan` | 计划在 job/process/log 之前拒绝；目录名必须是单一受控段 | 正：`user`/`User`/`user_1`/`user-1`/64 字符；负：`safe/../../outside`、`a/b`、`a\b`、`a:b`、`..`、`.`、`NUL`、`con.txt`、`COM1`、65 字符、空串、首尾空格、`user.`、`a..b` | `CUSTODY_PLAN_ROLE_DATA_INVALID` | 拒绝发生在任何副作用之前；零 job、零 process、零目录 |
| **m01** sealed 嵌套别名可改 | `LaunchPlan`（`_canonical` + `_freeze` 只读视图 + `sealed_bytes`/`sealed_sha256`） | `validate_launch_plan` → `role_command` | 呈现副本不得改变内部 roles 的实际命令；封存 bytes/digest 单一来源 | 正：seal bytes 与 digest 一致、再次取 seal 不变；负：改 `sealed.roles[0].tools[0].path` 后命令仍为原 exe；改 `plan.roles[0]` 抛 TypeError | 命令不变 | — |
| **M02** 类体同名闭包 NameError | `v0_s3_native_broker.py:_windows_api_types`（纯声明）/ `_declare_windows_primitives`（原型）/ `_WindowsApiTable`（显式命名空间）/ `_load_windows_api`（唯一 WinDLL 加载点） | 离线：注入记录型原语表 | 声明与加载分离；非 Windows 不加载 native 表；无伪造平台串 | 正：声明表可离线构造、每个原语都有 argtypes/restype；负：`_load_windows_api` 在非 Windows 抛 `BROKER_PLATFORM_UNSUPPORTED` | 非 Windows 明确拒绝 | 不加载任何 native 库 |
| **M03** 结构大小/继承/64 位/last-error | `WindowsApi.create_process_suspended`、`create_pipe`、`_security_attributes`、`_process_creation_time`、`_release_created`、`_close_quietly` | 注入 `FakeKernel32` 的生产 façade | `cb=sizeof(STARTUPINFOEXW)`；handle-list 精确白名单；继承位真实成立；INVALID_HANDLE_VALUE 按指针宽；首个 last-error 在清理前保存；部分创建后原句柄由本方法 finally 终止确认关闭 | 正：cb/flags/inherit/handle-list/null 属性/关闭次序全部断言；负：CreateProcess 失败时 detail 含 `last_error=1234` 且 null 句柄在其后关闭 | `BROKER_PROCESS_CREATE_FAILED` 等具名码 | null 句柄、属性表在 finally 释放，失败逐项具名 |
| **M04** Job PID 内联数组 | `WindowsApi.job_process_ids` | 同上 | 两计数 + 内联 `ULONG_PTR` 数组；返回长度与计数互相印证 | 正：读出 `[111,222]`；负：assigned>listed → `BROKER_JOB_QUERY_TRUNCATED`；超 cap → `BROKER_DESCENDANT_LIMIT` | UNKNOWN（不猜零） | 只读 buffer，不解引用任意指针 |
| **M10** sampler `--private-pids` | `role_command`（SAMPLER 分支） | `role_command` | 既有 parser 为 `type=int,nargs='+'`：逐个 PID 独立参数 | 正：`['--private-pids','11','22','--max-seconds',...]`；负：断言 `'11 22' not in arguments`；另有一条以生产 sampler 源码 parser 为 Oracle 的对照用例 | 命令固定 | 生产 sampler/parser 未改 |
| **M11** nonce 与启动前拒绝 | `NativeCustodySession._resolve_nonce`、`BrokerProcess.bind_channel_deadline/write`、`build_broker_command`、`launch_broker`、`main` | 会话与 broker 入口 | 双方同一 32 hex；非法 nonce/平台/参数在任何 mkdir/write/launch 前拒绝；父映射为具名结构化 UNKNOWN | 正：默认 nonce 为 32 hex；负：`custody-`+32hex / 大写 / 31 / 33 / 空 全部拒绝且运行根为空 | `CUSTODY_NONCE_INVALID` / `BROKER_NONCE_INVALID` | 启动前零目录零文件 |

### B 段：资源生命周期统一收口

| 独审项 | 生产函数 | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M05** pending 资源 owner | `BrokerCore._pending`（`_PendingResources.add/transfer/take/close_all`）、`_launch_role`、`_start_reader`、`_release_pending`、`_close_readers` | `BrokerCore` | 每个本轮句柄在创建成功瞬间进入 owner 明确的 pending 表；**移交 reader 或 Core 成功后才转移 owner**，且在关闭前始终留在表内并具名；外来句柄不碰 | 正：arm 后 pending=1 项（owner=CORE）、launch 后 pending=job+2 process+2 thread+4 pipe_read（owner=CORE/READER）、stop 后为空；负：assign 失败后 pending 为空且 read 端已关；关闭集合 ⊆ 本 façade 分配集合 | `UNKNOWN_RETAINED` | 未关闭者保留在 pending 表并列名；读者仍存活时其读端不关闭、带 owner 移出并记 `reader_not_stopped` |
| **M06** 取消/诊断/写失败绕过清理 | `BrokerCore.launch/stop`、`BrokerLoop.run/_ensure_stopped`、`main` 的 finally | 注入异常/取消/断写 | arm/launch/stop/Loop/main 全生命周期独立 finally；普通 Exception→结构化 UNKNOWN 且区分 primary/secondary；取消清理后继续传播；诊断与写失败不阻断清理 | 正：正常路径 RELEASED；负：assign 抛 `KeyboardInterrupt` → 全部句柄已关且异常继续传播；诊断抛 `RuntimeError` → 清理仍完成且异常不被吞；首帧写 `BrokenPipeError` → job 已释放 | `UNKNOWN_RETAINED` | 不靠 broker 进程退出代替 owner 清理，不靠 GC |
| **M07** 父 start 失败不关 broker | `NativeCustodySession.start/_close_broker/_stop_background` | 会话 + 假 broker | 任一阶段 REFUSED/timeout/parse 错/普通异常/BaseException 都在 `start` 内收口原 broker 与通道 | 正：正常 start 返回 RUNNING；负：REFUSED / `KeyboardInterrupt` / 非帧字节 → peer 关闭次数=1、状态 UNKNOWN_RETAINED | `UNKNOWN_RETAINED` | 关不掉则保留原引用与 UNKNOWN，不直接 return 丢引用 |
| **M09** RELEASED 需真实事实 | `BrokerCore._is_released/_close_readers/_release_the_records/_release_the_job`、`WindowsApi.read_stream`、`BrokerProcess.close` | `BrokerCore` | 进程退出已确认 + 句柄关闭已证 + reader 实际 join 且无读错 + 通道/原 Popen 关闭与退出已证；ReadFile 仅 broken-pipe/已取消/EOF 算结束 | 正：正常 stop → RELEASED 且重复 stop 不再关闭；负：reader 仍 alive → `reader_not_stopped` 且非 RELEASED；读错误 → 具名 error 且非 RELEASED；close 失败 → job 未关且非 RELEASED | `UNKNOWN_RETAINED` | 句柄关闭由真正 owner 记录，不靠 `__del__` |

### C 段：deadline 与通道边界

| 独审项 | 生产函数 | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M08** 同步写/启动/心跳/STOP | `_PosixPipeEndpoint`、`_WindowsPipeEndpoint`（+`_WindowsPipeWorker`）、`StreamChannel`、`BrokerProcess.bind_channel_deadline/write/close`、`BrokerLoop._fix_deadline/_reply/_loop`、`NativeCustodySession._fix_deadline/_send/_heartbeat_step/stop` | 注入 syscall 表 / 注入 fake clock | 绝对+monotonic 在 arm/launch/首帧 reply 前冻结且只缩短；POSIX 原 FD 非阻塞+poll≤50ms 切片，每片核 cancel 与固定 deadline；Windows 原 HANDLE 可取消 I/O，读写各一常驻 worker，监督线程不执行可能阻塞的调用；取消是请求不是完成；心跳 60s/缺失窗 120s 且只有已确认帧更新 liveness；两方向帧数保守共用 1024 并预留终态帧；STOP 与 cleanup 共享一个 ≤min(5s, 剩余) 上限 | 正：非阻塞设置一次、切片≤50ms、部分写续写、EOF 可见、只关自有 FD；负：读超时 → `BROKER_PIPE_TIMEOUT`；cancel → `BROKER_PIPE_CANCELLED`；写超时同；帧预算超限 → `CUSTODY_FRAME_BUDGET_EXCEEDED`；心跳写失败 → `CUSTODY_HEARTBEAT_FAILED:*`；六小时 fake clock 全调度 → 360 次心跳、帧数仍在预算内、绝对 deadline 不变 | 失败即 `UNKNOWN_RETAINED` | 未确认句柄保留 owner 引用；不丢 daemon 线程；无无限 join |

## 3. 本轮实现引入的显式生产接口（三源内最小变更）

| 接口 | 位置 | 语义 | 为何必须显式 |
|---|---|---|---|
| `LaunchPlan.sealed` / `sealed_bytes()` / `sealed_sha256()` | custody | 呈现副本 / 规范化字节 / 其摘要 | 封存 bytes 与 digest 必须是同一份定义，父写父哈希、broker 重哈希同一份字节 |
| `LaunchPlan.roles`（只读视图） | custody | roles 的命令来源 | 呈现副本不得改变内部命令 |
| `NativeCustodySession._heartbeat_step()` | custody | 一次心跳步进（读会话时钟） | 六小时全调度必须能用 fake clock 验证，不能真实 sleep |
| `NativeCustodySession._write_to_broker(raw, deadline)` | custody | 显式 deadline 写入 | 未知 peer 不得被默认为 deadline-aware |
| `BrokerProcess.channel_deadline_aware` / `bind_channel_deadline(deadline)` / `write(raw, deadline)` | broker | deadline-aware 生产接口（类型与单位校验） | root 裁决第 3 条：显式生产接口 + 类型/单位验证 |
| `WindowsApi(table=None)` | broker | 可注入原语表 | 合同允许在纯声明构造中注入原语表，以便不加载 WinDLL 即检查真实声明路径 |
| `_windows_api_types()` / `_declare_windows_primitives(table, types)` | broker | 纯声明与原型声明 | 声明与加载分离；固定宽度显式声明，不使用宿主 `c_long`/`c_wchar` |

## 4. 静态检查与真实声明路径

* 固定宽度类型在生产声明中显式给出：`DWORD`/`BOOL` 32 bit、`WORD` 16 bit、
  `HANDLE`/`SIZE_T`/`ULONG_PTR` 为指针宽。`ctypes.wintypes` 未被用于任何固定宽度
  字段（其 `BOOL` 在宿主上是 `c_long`）。
* 原语原型逐个显式声明并被离线断言：`CreateJobObjectW`、`CreateProcessW`、
  `CreatePipe`、`CreateFileW`、`ReadFile`、`WriteFile`、`CloseHandle`、
  `SetHandleInformation`、`GetProcessTimes`、`QueryInformationJobObject`、
  `InitializeProcThreadAttributeList`、`UpdateProcThreadAttribute`、
  `DeleteProcThreadAttributeList`、`CancelSynchronousIo`、`DuplicateHandle`、
  `GetCurrentThread`、`GetCurrentProcess` 等。
* `JOBOBJECT_BASIC_PROCESS_ID_LIST` 为两个 DWORD + 内联 `ULONG_PTR[1]`；离线断言
  字段偏移 0/4/8 且数组宽度为指针宽，读数组时按字节偏移从 buffer 取，不经指针字段。
* `STARTUPINFOEXW` 的 `cb` 取整个扩展结构的大小，`lpAttributeList` 位于扩展结构
  内 `STARTUPINFOW` 之后；handle-list 为 `[stdout_write, stderr_write, NUL]` 的精确
  白名单，NUL 与两个 write 端以 `SECURITY_ATTRIBUTES(bInheritHandle=TRUE)` 创建，
  read 端 `SetHandleInformation(read, HANDLE_FLAG_INHERIT, 0)`。
* Windows 路径**没有**在离线环境执行：没有加载 `kernel32`、没有调用任何 Windows
  API、没有解引用任何指针。Windows 端点的取消、握手与 join 逻辑是**声明**与
  **代码审查**对象，不是运行证据。

## 5. 两处测试改动（如实声明，非仅改断言填绿）

1. `test_the_sampler_is_created_last_with_the_pids_of_the_services`：随 M10 的生产
   修正改为逐个 PID 断言，并新增以生产 sampler 源码 parser 为 Oracle 的对照用例。
2. `test_the_absolute_lease_stops_the_round`：原用例的 `MemoryChannel` 立即 EOF，
   使"租约到期"永不可达（Oracle 与场景自相矛盾）。改为注入推进的 fake clock 且
   通道不立即 EOF，Oracle（绝对租约到期即停止该轮）不变且确定性可复现，不真实 sleep。

全部 fake 按最终合同适配（写入带显式 deadline、标注 `channel_deadline_aware`）；
旧断言无一被放宽；旧 owner 哈希与旧 native 拒绝点仍由两条 integrity 用例守住。

## 6. 两个批次

### 6.1 批次 01（失败批次，如实保留）

执行对象是 **root 冻结包** `.../native-custody-correction-02/validation-plan-01`
（`plan.json` sha256 `90c3c5e2…`）与其三条 commands 的精确 argv/cwd；**真正的 guard
与 runner 由 root 控制**。实现者提交的 runner/guard **只作为输入保留，未被执行**。

| 项 | 值 |
|---|---|
| 收集 | 117（逐项有序一致，未触发 `FROZEN_NODE_ORDER_MISMATCH`） |
| 通过 / 失败 / 跳过 | 97 / **20** / 0 |
| pytest 退出码 | 1 |
| 用时 | 7.84 s（上限 300 s，外层 timeout） |
| guard 自检拒绝 / 运行期拒绝 | 8 项 / 0 |
| 预装载事件 | 恰 1 次 `ctypes.dlopen`（name=None），窗口最终 CLOSED |
| 线程（前→后） | `MainThread` → `MainThread` + `lvw-native-custody-channel-pump` + `lvw-native-custody-heartbeat` |
| `cleanup_proven_for_batch` | **false** |

产物（均在 `implementation-native-custody-correction-02/` 根下，未被批次 02 覆盖）：
`native-custody-correction-02.receipt.json`（root runner 写）、
`native-custody-correction-02.guard.json`（root guard 写）、`commands.json`、
`counter-before.json` / `counter-after.json`、原始 stdout/stderr。
root 的归档：`validation-plan-02/attempt01/`（含 `report.md`、`plan.json`、
`attempt01-archive-index.json`、`attempt01-synthetic-evidence.zip`）。

### 6.2 批次 01 的 20 个失败：六个根因（原始证据见 §8）

| 根因 | 性质 | 失败用例 | 修复 |
|---|---|---|---|
| **R1** `_ChannelPump._stop` 覆盖 `threading.Thread._stop` 方法 → `join()` 抛 `TypeError: 'Event' object is not callable` | **生产缺陷（M05/M07/M08/M09 的收口义务本身）** | 13 个会话用例 | 取消标志改名 `_stop_event`（`_WindowsPipeWorker` 同类隐患一并修）；会话的 stop/close 路径恢复可用，线程残留消失 |
| **R2** pending 表语义：移交后资源被移出表（应为**只转移 owner**、关闭前仍在表内）；读者仍存活时其读端会被表关闭 | **生产缺陷（M05/M09 的 pending owner 与读者存活义务本身）** | `test_every_created_handle_enters_the_pending_table` 等 | `transfer()` 只改 owner；读者仍存活时其读端带 owner 移出并记 `handle_retained` 与 `reader_not_stopped`；用例改为断言 arm/launch/stop 三个时点的表内容与 owner |
| **R3** 读错误用例在 launch 之后才注入失败的 `read_stream` | 检查 | `test_a_read_error_is_not_the_end_of_a_stream` | 失败的读在 launch 之前注入 |
| **R4** 两个手写会话用 `parent_child_remaining_seconds=60` 对 `max_runtime_seconds=600` 的计划 | 检查 | 两个父侧会话用例 | 剩余预算改为 600 |
| **R5** 旧 owner 预期摘要抄错（多一位） | 检查 | `test_the_old_owners_are_unchanged` | 按 root 的 `pending-source-edit.json` 精确替换该字面量为文件实际摘要；旧 owner **未改动** |
| **R6** `ctypes.memmove` 的源须为字节；数组字段无 `sizeof`；假 kernel32 的写入未受缓冲限制 | 检查 | 四个 Job PID 布局用例 | 源改为 `bytes(...)`；数组宽度用字段 `.size`；写入限制在缓冲区内而计数照实上报 |

**口径更正（root 裁决 `msg_5bd04c08d05a`）**：R1 与 R2 **不是**与独审落点无关的噪声，
它们正是 **M05（pending 资源 owner）、M07（父侧收口）、M08（后台线程与监督路径）、
M09（reader 存活与 RELEASED 事实）** 的义务本身在实现上的失败；批次 01 的 97 个通过
**不关闭任何一项独审 Major**。最终裁决属于隔离独审。

### 6.3 批次 02（纠正批次，root 冻结包 `validation-plan-02`）

执行对象：root 冻结包 `.../validation-plan-02`（`plan.json` sha256
`474e2fe1606d96e07a6c4d74448b10f3b1fc16c64e60bfab9c215dd18d3abc12`）与其三条
commands；root 的 guard/runner、root 的外层 counter 观察。执行前按 root 的
`pending-source-edit.json` 精确执行了**唯一一处**字面量更正（R5）：测试文件
`eb3b336b…` → `55220aeb…`（与 root 的期望一致），旧 owner 文件本身未改动。
243 个 pin（16 source + 3 tool + 223 文件级依赖 + 3 stdlib）全部校验无漂移。

| 项 | 值 |
|---|---|
| 收集 | 117（逐项有序一致） |
| 通过 / 失败 / 跳过 | **117 / 0 / 0**（其中功能 115、integrity 2） |
| pytest 退出码 | 0 |
| 用时 | 7.80 s（上限 300 s，外层 timeout） |
| guard 自检拒绝 / 运行期拒绝 | 8 项 / 0 |
| 预装载事件 | 恰 1 次 `ctypes.dlopen`（name=None），窗口最终 CLOSED，`window_closed_before_candidate=true` |
| FD 身份 | 前后各 3 个，身份一致，无新增/复用，`unknown` 为空 |
| 线程（前→后） | `MainThread` → `MainThread`（无残留） |
| `cleanup_proven_for_batch` | **true** |

产物（全部在 `implementation-native-custody-correction-02/attempt02/`，未覆盖批次 01
任何原件）：`native-custody-correction-02.receipt.json`、
`native-custody-correction-02.guard.json`、`commands.json`、
`counter-before.json` / `counter-after.json`、原始 stdout/stderr、`pytest-temp/`。

原 counter 前后两次只读观察完全一致：sha256
`acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、`active=false`、
`starts_total=28`、`reserved_wall_seconds=240.0`、`spent_wall_seconds=12.362`、charges
逐条相同；未写、未退款、未清零、未新建、未复活旧授权。

### 6.4 交付的候选源码

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_native_custody.py` | `1e1c06d263fc55778246bf9eebb2a401ba592e726501e042af9860e4dafa7e2a` |
| `tools/v0_s3_native_broker.py` | `5384ce5a7982a1620b2ed368805364170be9a7e0203af57c00f71b656dfe1b2e` |
| `tools/test_v0_s3_native_custody.py` | `55220aeb75d1ff9213901dc6e156892106e0c7e205dcbaa97ce40952d56b3759` |

三者即 root 计划 02 的 pin，即批次 02 所执行与所验证的字节。

### 6.5 批次 01 的失败候选源码（可恢复与 MISSING）

批次 01 执行时的三份源码**未交付也未 commit**。root 的归档索引对此的记录是
`NOT_DELIVERED; source pins and original execution receipts retained; do not claim
full historical source bytes archived`。本包的处理：

* `tools/v0_s3_native_custody.py`：**已按字节恢复**（把批次 02 之后的修正反向撤销后
  重算，sha256 与批次 01 执行计划的 pin `68faa274de9eb8fa786e8b32d71a501d2b24513531c3621ee98313814eae8d56`
  **完全一致**），交付于 `attempt01-failed-candidate-sources/v0_s3_native_custody.py` ✓。
* `tools/v0_s3_native_broker.py` 与 `tools/test_v0_s3_native_custody.py`：**MISSING**。
  反向重建的字节与执行计划的 pin（`0041cb0e…` / `86d3aa05…`）**不相等**，因此
  **不交付**、不冒充、不编造。重建结果已逐行对照批次 01 日志的 22 个 traceback 锚点，
  锚点一致而摘要不一致，**以摘要为准**，故两份字节记为 MISSING。

清单见 `attempt01-failed-candidate-sources/manifest.json` ✓。

## 7. 未证与不宣称

真实 Windows 执行、Job 对象行为、GPU 释放、端口释放、sampler 执行、父崩溃恢复、
Windows stdin EOF 语义、真实 Win32 ABI 运行时行为：**全部 NOT_PROVEN**。
`grant_authority = NOT_VERIFIED`，`admission_produced = false`。

本包不宣布 Stage PASS、不宣布产品 Gate0、不宣布人工签署，不回填任何历史门禁。
实现者只报告 `READY_FOR_REVIEW`；**11 项 Major + 1 项 Minor 是否关闭由隔离独审裁决**，
本包的 117/117 只证明本包的离线检查全绿，不证明任何一项独审结论成立。

## 8. 已知与如实记录

1. `BrokerCore._start_reader` 的文档字符串仍写着读端"leaves the pending table"，
   而 R2 修正后的语义是"移交只转移 owner、句柄在关闭前留在表内"。这是**文档与实现
   不一致的措辞**，不影响行为；由于批次 02 已按 root 的 pin 验证了这三个文件的
   字节，本轮不再改动候选源码（改动会使已验证的候选与交付的候选分离），如实记录
   于此，交由独审处置。
2. 批次 01 的 20 个失败与其全部原始工件保留，未删除、未改写、未回填 PASS。
3. 旧 54 失败、纠偏 01 的 32 通过、独审 11 项 2 PASS/9 FAIL 的历史结论未改。
