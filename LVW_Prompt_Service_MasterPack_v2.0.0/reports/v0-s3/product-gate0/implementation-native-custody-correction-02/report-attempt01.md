# S3-P4-N1 纠偏 02：完整独审 11 Major + 1 Minor 的集中修复实现报告

状态：**CORRECTION_PENDING_ACK**。被 ACK 的批次 01 已按 root 冻结计划执行并**如实
保留为失败批次**（117 收集 / 97 通过 / 20 失败 / 0 跳过 / pytest_exit=1）；其 20 个
失败已定位为 6 个根因（1 个生产缺陷 + 5 个检查侧缺陷）并已在三规定源内修复，但
**修复后的批次尚未获得 root 的新 ACK、尚未执行**。因此本包现在**不**宣称
READY_FOR_REVIEW，更**不是** Stage PASS、**不是** 产品 Gate0、**不是** 人工签署。
本包所有输出都带 `stage_pass_claim = false` 与 `product_gate0 = false`。

> 本包只回答独审 `msg_287dbc62810a` 的 11 项 Major 与 1 项 Minor（root 裁决
> `msg_fdd5493bfaed`：全部采纳，采用有界传输方案 A 并按其收紧）。旧 N1 架构、
> 门限与安全原则不变；旧 owner 与全部 native 拒绝点未改；旧 54 失败、纠偏 01
> 的 32 通过与独审的 11 项 2 PASS/9 FAIL 等历史事实一律不改写。真实 Windows
> 仍 NOT_PROVEN。

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
| **M01** user_directory 前缀匹配可逃逸 | `tools/v0_s3_native_custody.py:_require_directory_name`（由 `_validate_role_data` 调用） | `validate_launch_plan` | 计划在 job/process/log 之前拒绝；目录名必须是单一受控段 | 正：`user`/`User`/`user_1`/`user-1`/64 字符；负：`safe/../../outside`、`a/b`、`a\b`、`a:b`、`..`、`.`、`NUL`、`con.txt`、`COM1`、65 字符、空串、首尾空格、`user.`、`a..b` | `CUSTODY_PLAN_ROLE_DATA_INVALID` | 拒绝发生在任何副作用之前；零 job、零 process、零目录（`test_the_user_directory_refusal_creates_nothing`） |
| **m01** sealed 嵌套别名可改 | `LaunchPlan`（`_canonical` + `_freeze` 只读视图 + `sealed_bytes`/`sealed_sha256`） | `validate_launch_plan` → `role_command` | 呈现副本不得改变内部 roles 的实际命令；封存 bytes/digest 单一来源 | 正：seal bytes 与 digest 一致、再次取 seal 不变；负：改 `sealed.roles[0].tools[0].path` 后命令仍为原 exe；改 `plan.roles[0]` 抛 TypeError | 命令不变 | — |
| **M02** 类体同名闭包 NameError | `v0_s3_native_broker.py:_windows_api_types`（纯声明）/ `_declare_windows_primitives`（原型）/ `_WindowsApiTable`（显式命名空间）/ `_load_windows_api`（唯一 WinDLL 加载点） | 离线：注入记录型原语表 | 声明与加载分离；非 Windows 不加载 native 表；无伪造平台串 | 正：声明表可离线构造、每个原语都有 argtypes/restype；负：`_load_windows_api` 在非 Windows 抛 `BROKER_PLATFORM_UNSUPPORTED` | 非 Windows 明确拒绝 | 不加载任何 native 库 |
| **M03** 结构大小/继承/64 位/last-error | `WindowsApi.create_process_suspended`、`create_pipe`、`_security_attributes`、`_process_creation_time`、`_release_created`、`_close_quietly` | 注入 `FakeKernel32` 的生产 façade | `cb=sizeof(STARTUPINFOEXW)`；handle-list 精确白名单；继承位真实成立；INVALID_HANDLE_VALUE 按指针宽；首个 last-error 在清理前保存；部分创建后原句柄由本方法 finally 终止确认关闭 | 正：cb/flags/inherit/handle-list/null 属性/关闭次序全部断言；负：CreateProcess 失败时 detail 含 `last_error=1234` 且 null 句柄在其后关闭 | `BROKER_PROCESS_CREATE_FAILED` 等具名码 | null 句柄、属性表在 finally 释放，失败逐项具名 |
| **M04** Job PID 内联数组 | `WindowsApi.job_process_ids` | 同上 | 两计数 + 内联 `ULONG_PTR` 数组；返回长度与计数互相印证 | 正：读出 `[111,222]`；负：assigned>listed → `BROKER_JOB_QUERY_TRUNCATED`；超 cap → `BROKER_DESCENDANT_LIMIT` | UNKNOWN（不猜零） | 只读 buffer，不解引用任意指针 |
| **M10** sampler `--private-pids` | `role_command`（SAMPLER 分支） | `role_command` | 既有 parser 为 `type=int,nargs='+'`：逐个 PID 独立参数 | 正：`['--private-pids','11','22','--max-seconds',...]`；负：断言 `'11 22' not in arguments`；另有一条以生产 sampler 源码 parser 为 Oracle 的对照用例 | 命令固定 | 生产 sampler/parser 未改 |
| **M11** nonce 与启动前拒绝 | `NativeCustodySession._resolve_nonce`、`BrokerProcess.bind_channel_deadline/write`、`build_broker_command`、`launch_broker`、`main` | 会话与 broker 入口 | 双方同一 32 hex；非法 nonce/平台/参数在任何 mkdir/write/launch 前拒绝；父映射为具名结构化 UNKNOWN | 正：默认 nonce 为 32 hex；负：`custody-`+32hex / 大写 / 31 / 33 / 空 全部拒绝且运行根为空 | `CUSTODY_NONCE_INVALID` / `BROKER_NONCE_INVALID` | 启动前零目录零文件 |

### B 段：资源生命周期统一收口

| 独审项 | 生产函数 | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M05** pending 资源 owner | `BrokerCore._pending`（`_PendingResources.add/transfer/take/close_all`）、`_launch_role`、`_start_reader`、`_release_pending` | `BrokerCore` | 每个本轮句柄在创建成功瞬间进入 owner 明确的 pending 表；移交 reader 或 Core 后才转移 owner；外来句柄不碰 | 正：arm 后 pending 仅 job、launch 后 pending 为空；负：assign 失败后 pending 为空且 read 端已关；关闭集合 ⊆ 本 façade 分配集合 | `UNKNOWN_RETAINED` | 未关闭者保留在 pending 表并列名 |
| **M06** 取消/诊断/写失败绕过清理 | `BrokerCore.launch/stop`、`BrokerLoop.run/_ensure_stopped`、`main` 的 finally | 注入异常/取消/断写 | arm/launch/stop/Loop/main 全生命周期独立 finally；普通 Exception→结构化 UNKNOWN 且区分 primary/secondary；取消清理后继续传播；诊断与写失败不阻断清理 | 正：正常路径 RELEASED；负：assign 抛 `KeyboardInterrupt` → 全部句柄已关且异常继续传播；诊断抛 `RuntimeError` → 清理仍完成且异常不被吞；首帧写 `BrokenPipeError` → job 已释放 | `UNKNOWN_RETAINED` + 具名 failures | 不靠 broker 进程退出代替 owner 清理，不靠 GC |
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

## 6. 批次 01：已执行，失败如实保留

### 6.1 执行对象与绑定

执行对象是 **root 冻结包**
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-02/validation-plan-01`
的 `plan.json`（sha256 `90c3c5e29a77663e309d480479f6e930e9cbfb2afa374701b7bcc6f9cadcf86a`）
与其三条 commands 的精确 argv/cwd；**真正的 guard 与 runner 由 root 控制**
（`validation-plan-01/guard.py`、`validation-plan-01/runner.py`）。实现者提交的
runner/guard（`implementation-native-custody-correction-02/guard.py`、`runner.py`）
**只作为输入保留，未被执行**。实现者提交的 plan（sha256 `3f88011f…`）已被 root
静态核对并被 root 计划以 `submitted_plan_sha256` 引用。

三条命令的完整 argv/cwd/退出码见
`implementation-native-custody-correction-02/commands.json`。

### 6.2 结果（原样保留）

| 项 | 值 |
|---|---|
| 收集 | 117（与 root 计划逐项有序一致，未触发 `FROZEN_NODE_ORDER_MISMATCH`） |
| 通过 | 97（其中功能 96、integrity 1 计入通过但不计功能） |
| 失败 | 20 |
| 跳过 | 0 |
| pytest 退出码 | 1 |
| 用时 | 7.84 s（上限 300 s，由调用者外层 timeout 保证） |
| guard 自检拒绝 | 8 项（subprocess/socket/fork/exec/system/sqlite/ctypes.dlopen/ctypes.dlsym） |
| guard 运行期拒绝 | 0 |
| 预装载事件 | 恰 1 次 `ctypes.dlopen`，name=None（自身映像），窗口最终态 CLOSED |
| FD 身份 | 前后清单保留；`cleanup_proven_for_batch=false`（见 6.4） |
| 线程 | 前后清单保留 |

产物：`native-custody-correction-02.receipt.json`（root runner 写）、
`native-custody-correction-02.guard.json`（root guard 写）、
`commands.json`（实现者写，记录实际执行的三条命令与退出码）、
`counter-before.json` / `counter-after.json`（root 外层只读观察）、
原始 stdout/stderr 日志。

### 6.3 原 counter 观察

前后两次只读观察完全一致：sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、
`active=false`、`starts_total=28`、`reserved_wall_seconds=240.0`、
`spent_wall_seconds=12.362`、charges 逐条相同。未写、未退款、未清零、未新建、
未复活旧授权。

### 6.4 二十个失败的六个根因（逐条对应原始证据）

| 根因 | 性质 | 失败用例 | 原始证据 | 修复 |
|---|---|---|---|---|
| **R1** `_ChannelPump._stop` 覆盖了 `threading.Thread._stop` 方法 → `join()` 抛 `TypeError: 'Event' object is not callable` | **生产缺陷** | 13 个会话用例（`test_the_session_holds_the_original_broker_handle`、`test_a_repeated_stop_is_idempotent`、`test_the_session_closes_the_broker_on_a_refusal`/`_on_a_cancellation`/`_on_a_parse_error`、`test_the_session_refuses_a_peer_that_is_not_deadline_aware`、`test_the_stop_uses_one_shared_cleanup_budget`、`test_the_heartbeat_*`、`test_the_frame_budget_fails_closed`、`test_the_evidence_keeps_every_native_claim_not_proven`、`test_the_session_does_not_extend_the_deadline`） | `tools/v0_s3_native_custody.py:691 → threading.py:1169 → TypeError` | 取消标志改名 `_stop_event`（`_ChannelPump` 与 `_WindowsPipeWorker` 两处同类隐患一并修）；会话的 stop/close 路径恢复可用 |
| **R2** pending 表语义与用例期望不一致：移交后仍留在表内的资源被期望为空 | 生产语义 + 检查 | `test_every_created_handle_enters_the_pending_table` | `Left contains one more item: {'handle': 101, 'kind': 'job', …}` | `transfer()` 改为**只改 owner、不移出表**，资源在被关闭前始终在表内并具名；用例改为断言 arm 后 1 项、launch 后 job+2 process+2 thread+4 pipe_read（owner 为 CORE/READER）、stop 后为空 |
| **R3** 读错误用例在 launch **之后**才注入失败的 `read_stream`，读者早已 EOF 结束 | 检查 | `test_a_read_error_is_not_the_end_of_a_stream` | `assert any(state['error'] == 'BROKER_STREAM_READ_FAILED' …)` 为 False | 失败的读在 launch **之前**注入，读者从第一次读就失败 |
| **R4** 两个手写会话用 `parent_child_remaining_seconds=60` 对 `max_runtime_seconds=600` 的计划 → 预算检查先失败 | 检查 | `test_the_session_closes_the_broker_on_a_parse_error`、`test_the_session_refuses_a_peer_that_is_not_deadline_aware` | `CUSTODY_CHILD_BUDGET_TOO_SMALL`（`custody.py:465`） | 剩余预算改为 600，与计划运行时一致 |
| **R5** 旧 owner 摘要抄错一位（`…bdc6cabc…` vs 实际 `…bdc6caba…`） | 检查 | `test_the_old_owners_are_unchanged` | 断言 diff 指向该位 | 更正为文件实际摘要 `16bf3e6396f9548312f92007eebbda55a448f0bdc6caba4a10afd71179b231a85`（旧 owner **未改动**） |
| **R6** `ctypes.memmove` 的源参数须为字节；数组字段无 `sizeof` | 检查 | `test_the_job_process_ids_are_read_from_the_inline_array`、`test_a_truncated_job_process_id_list_is_unknown`、`test_a_job_process_id_list_over_the_cap_is_unknown`、`test_the_process_id_list_of_a_job_is_an_inline_array` | `ctypes.ArgumentError: argument 2: TypeError: wrong type`、`TypeError: this type has no size` | 源改为 `bytes(ctypes.c_size_t(pid))`；数组宽度改用字段的 `.size`；假 kernel32 的写入被限制在缓冲区内（18 个 id）而计数照实上报 |

**结论**：20 个失败里 13 个来自一个真实的生产缺陷（R1，会话 stop/close 路径不可用），
其余 7 个来自检查侧的错误（R2 的期望、R3、R4、R5、R6 各占 1–2 项）。**没有一个失败
指向被独审的 11 项 Major + 1 项 Minor 的实现落点**：97 个通过的用例覆盖了计划边界、
封存一致性、nonce、ABI 声明与布局、Job 内联 PID 数组、pending owner、取消与诊断清理、
父侧收口、deadline-aware 传输、心跳与帧预算、旧 owner 完整性与旧拒绝点。

### 6.5 纠正批次的状态

修复后的三源摘要：
`tools/v0_s3_native_custody.py` = `1e1c06d263fc55778246bf9eebb2a401ba592e726501e042af9860e4dafa7e2a`、
`tools/v0_s3_native_broker.py` = `5384ce5a7982a1620b2ed368805364170be9a7e0203af57c00f71b656dfe1b2e`、
`tools/test_v0_s3_native_custody.py` = `eb3b336b9d80eafaab77da01f2ef9f5f349b8c240c05ef655422605e2033bcd6`。

实现者提交的纠正计划：`implementation-native-custody-correction-02/plan.json`
sha256 `b26bec9542c0fcbf4ca07f40b93b3de3e5c78433f6b293d760f95d13ffe9068e`，
nodeid 集合与顺序不变（117 项），其余绑定与批次 01 相同。由于已执行计划的 pins 绑定的是
**第一次提交**的源，纠正批次需要 root 重新冻结计划并再次 ACK；在该 ACK 之前不会执行
任何命令。

## 7. 未证与不宣称

真实 Windows 执行、Job 对象行为、GPU 释放、端口释放、sampler 执行、父崩溃恢复、
Windows stdin EOF 语义、真实 Win32 ABI 运行时行为：**全部 NOT_PROVEN**。
`grant_authority = NOT_VERIFIED`，`admission_produced = false`。

本包不宣布 Stage PASS、不宣布产品 Gate0、不宣布人工签署，不回填任何历史门禁。
实现者只报告 `READY_FOR_REVIEW`；集中独审关闭后由 root 裁决 N1 范围。
