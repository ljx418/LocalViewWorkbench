# S3-P4-N1 纠偏 03：八个开放 Major 的集中闭合实现报告 + 16 组冻结 Oracle 回归

状态：**READY_FOR_REVIEW**（实现者自检）。**不是** Stage PASS，**不是** 产品 Gate0，
**不是** 人工签署。本包所有输出都带 `stage_pass_claim = false` 与
`product_gate0 = false`。

> 本包只回答独审 `msg_4d5efa380640`（F0 / Major 8 / Minor 1）留下的**八项 Major**：
> M03、M04、M05、M06、M07、M08、M09、M11。M01、M02、M10、m01 已关闭，**未重新设计**；
> m02 是非阻断的旧 docstring，本次三源本就要改，**已同步纠正**，不为一句文字单独复跑。
> 旧 N1 架构、门限、协议、native 拒绝点、旧 owner 全部未改；旧 54 失败、纠偏 01 的 32 通过、
> 纠偏 02 的 117/97/20、独审 41 项的 21 PASS/20 FAIL 等历史事实一律不改写、不迁移。
> 真实 Windows 仍 NOT_PROVEN。

## 1. 范围与坐标

| 项 | 值 |
|---|---|
| Stage / Workpack | R1 / WP-R1-U3（S3_P4_OFFLINE_INTEGRATION_PREPARATION） |
| 阻断门禁 | `S3_P4_N1_CORRECTION_03_CUSTODY_AND_DEADLINE_CLOSURE` |
| 实施起点 HEAD | `37d938b983e53fee829ef1579373a97403f41d0c` |
| 候选 HEAD（本包） | `46af977f86e612d05306005b9e08e54b4d10477a` |
| 冻结 root 包 | `reports/v0-s3/product-gate0/native-custody-correction-03`（contract.md / root-decision.json / regression-obligations.json / received-review/review.md） |
| 独审 | `msg_4d5efa380640`，Fatal 0 / Major 8 / Minor 1，原 41 探针 21 PASS / 20 FAIL，批次清理通过 |
| 允许改动的源 | `tools/v0_s3_native_custody.py`、`tools/v0_s3_native_broker.py`、`tools/test_v0_s3_native_custody.py`、新增 `tools/test_v0_s3_native_custody_regressions.py`、本 NEW 报告目录 |
| 未改动 | 旧 controller / worker / QualityPhase / supervisor / runtime / driver / authority / 公共合同 / 协议 / 门限 / control / MANIFEST / 旧证据 |

本轮**唯一 owner**（Claude Code），**不派生 Agent**，不清理旧工作区，不批量 `git add`。
`git status` 中 `implementation-integration-01/report.md` 的既有未提交改动与其它任务的未跟踪
文件属于本任务之外的旧状态，未 clean、未 reset、未纳入本批。

## 2. 逐项落点：生产函数 → 驱动 → Oracle → 正负例 → 终态 → 清理

### A 段：原句柄保留、partial 清理、查询与生命周期

| 独审项 | 生产函数（位置） | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M03** 部分创建失败丢原 HANDLE、首错误被清理错误覆盖 | `WindowsApi.__init__/_retain/_forget/_note/retained_handles/release_retained`、`WindowsApi.create_process_suspended`、`WindowsApi._release_created` | 生产 `WindowsApi` + 注入纯原语表 | CreateProcess 成功的瞬间原 process/thread 进入 API 持有表；DeleteProcThreadAttributeList / NUL.close / birth query / 后续释放**互为独立**；前一个清理异常不跳过后续；首错误不被后错误覆盖 | 正：正常创建→句柄移交后离开持有表；负：birth 失败 + Wait TIMEOUT + 两次 CloseHandle 失败 → 抛出 `BROKER_PROCESS_BIRTH_QUERY_FAILED` 且 detail 含 `cleanup=...WaitForSingleObject:exit_not_confirmed...CloseHandle...`，持有表保留原句柄，`release_retained()` 可事后回收；负：属性表删除抛普通异常 → NUL 仍关闭、进程仍释放、错误 `BROKER_ATTRIBUTE_LIST_CLEANUP_FAILED` | `UNKNOWN_RETAINED`，无假 RELEASED | 未关闭句柄留在 API 持有表与 core 的 `retained_resources`/`api_retained` 中，不靠 GC |
| **M04** Job 返回长度与双计数未闭合 | `WindowsApi.job_process_ids` | 生产 `WindowsApi` + 注入原语表 | 仅当 `8<=returned<=allocated`、`needed<=returned`、两计数相等且 `listed<=17` 时接受；异常/零长度/反向不一致/超限/截断 → UNKNOWN；合法空 Job 需完整 header | 正：(2,2,24)→`[111,112]`、(0,0,8)→`[]`；负：(2,1,16)、(0,1,16)、(0,0,0)、(1,1,0)、(18,18,152)、(1,1,999) 全部抛具名错 | UNKNOWN，不猜零 | 只读 buffer，不解引用任意指针 |
| **M05** Job 关闭失败后从 pending 与 Core 双重移除 | `BrokerCore.arm`、`BrokerCore._release_the_job`、`BrokerCore._release_the_records`、`BrokerCore._retain_resource/_release_resource` | 生产 `BrokerCore` + 记录型 façade | 只有确认关闭才允许忘记句柄；关闭失败不 take、不置 None，原引用留在 owner 表与 pending 表 | 正：正常关闭→pending 清空；负：limit 失败 + close 失败 → `core.job` 仍是原 job、pending 仍含该 job、`evidence['retained_resources']` 具名 | `UNKNOWN_RETAINED` | 未关闭者保留原引用与 owner |
| **M06** Core.stop 无独立 finally、普通错误中断全部清理 | `BrokerCore.stop/_close_pending/_terminate_the_job/_wait_the_processes/_close_readers/_query_job/_release_the_records/_release_the_job/_wait_timeout_ms`、`_terminate_owned` | 生产 `BrokerCore` | 清理步骤是彼此独立的 bounded finalizer；各自失败仍尝试其他项；记录原错误与次级错；**未完成不得置 `_released=True`** 阻断同 owner 恢复；重复 stop 不双关成功关闭句柄 | 正：正常 stop → RELEASED；负：terminate_job 抛普通 `RuntimeError` → 原异常 primary 抛出、后续 query/close 仍执行、`_released` 仍为 False、重复 stop 可再试；诊断先失败 → primary 是诊断错误、不被后来的清理错误覆盖 | `UNKNOWN_RETAINED` | 已确认关闭的句柄不再关闭；未确认者在共享 cleanup deadline 内可再协调 |
| **M07** start 监督线程启动位于生命周期 try 之外；launcher 丢 Popen | `NativeCustodySession.start/_launch_failure_code/_on_pump_error/_latch_background_failure/_start_bounded_close`、`_adopt_broker_process/_terminate_and_close_process`、`launch_broker` | 生产 `NativeCustodySession` + 生产 launcher 收口函数 | start 全生命周期（launcher 之前→identity→pump 构造/启动→心跳初始化）在保护范围；线程启动失败有界收原 peer；普通错返回结构化终态并保留原 `error.code`；KI/SystemExit 清理后传播 | 正：正常 start → RUNNING；负：心跳线程启动失败 → 结构化 `UNKNOWN_RETAINED` 且 peer 关闭一次；负：读侧 `KeyboardInterrupt` → 取消继续传播且 peer 关闭一次；负：Popen 成功后 channel 构造失败 → launcher 自己 terminate + wait + 关管道 | `UNKNOWN_RETAINED` | 失败返回前先收原 peer；收不掉保留原引用 |
| **M11** 默认 launcher 泛化 `BrokerError` | `NativeCustodySession.start` 的 launcher 分支、`_launch_failure_code` | 生产 `NativeCustodySession` + 生产默认 launcher | 普通 BrokerError 保留原 code（含 `BROKER_PLATFORM_UNSUPPORTED`）并返回结构化 REFUSED/UNKNOWN，不原样 raise；仅 KI/SystemExit 清理后传播；无副作用先于拒绝 | 正：默认 32 hex nonce 不变；负：有效 fake wall/租约下默认 launcher → `evidence['failures']` 含 `BROKER_PLATFORM_UNSUPPORTED`、状态 `UNKNOWN_RETAINED`、run root 未被创建 | `UNKNOWN_RETAINED` | 启动前零目录零文件 |

### B 段：一个真正的截止与序列 owner

| 独审项 | 生产函数（位置） | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M08-a** arm/launch 监督 | `BrokerLoop._fix_deadline/run/_run_startup/_guarded_startup/_ensure_stopped`、`_StartupOwner`、`BrokerCore.bind_clock/bind_absolute_deadline/cleanup_deadline` | 生产 `BrokerLoop` + 生产 `BrokerCore` | arm 前冻结时钟与绝对 deadline；每个启动操作前后核是否耗尽，超期只清理不继续启动；只允许一个有限 in-flight 启动 owner 通道；晚到结果只能清理、不得 late resume | 正：正常 arm+launch → READY/STATUS；负：arm 消耗绝对租约后返回 → **不创建任何角色**、不 resume、无成功 STATUS、只回 `REFUSED/BROKER_STARTUP_DEADLINE_EXCEEDED`、job 已释放 | `UNKNOWN_RETAINED` | 启动超时后只清理；仍在飞行则保留 owner 与线程，不声称清理完成 |
| **M08-b** 共享 cleanup 绝对截止 | `NativeCustodySession._cleanup_deadline_for/_remaining/_stop_background/_send/stop`、`BrokerProcess.close/_cleanup_deadline`、`StreamChannel.close`、`_PosixPipeEndpoint/_WindowsPipeEndpoint.close`、`BrokerCore.cleanup_deadline/remaining_cleanup_seconds/_wait_timeout_ms` | 生产会话 + 生产 `BrokerProcess` + 注入时钟 | deadline 在第一次 STOP/失败清理入口生成 = `min(original_monotonic_deadline, now+5s)`，**同一个值**贯穿 send→stop_background→close_broker→BrokerProcess.close→StreamChannel/endpoint/Windows worker→Core 每 process/reader 等待；每次调用重算 `max(0, deadline-clock())` | 正：正常 stop 只有一个 cleanup deadline；负：channel 关闭吃掉共享 5 秒中的 4 秒 → 第一次 wait 只拿 1 秒、第二次拿 0 秒，**总时钟不超过 5 秒**，没有每层新 5 秒 | `UNKNOWN_RETAINED` | 超期不再开始新等待，只保留 UNKNOWN 与原 owner |
| **M08-c** 心跳、序列与帧预算 | `NativeCustodySession._send/_check_frame_budget/_decode_reply/_heartbeat_step/_latch_background_failure`、`_ChannelPump(on_error)`、`BrokerLoop._check_frame_budget/_loop` | 生产会话 + 生产 `BrokerLoop` | encode→选 sequence→reserve budget→send→commit **同一把锁**内完成；STOP 先阻断后续心跳；心跳不得在绝对 lease 到期后发包、不得延长 lease；心跳/泵错误主动闩锁 UNKNOWN 并发起**非自 join**的有界收口；双向总预算 `sent+received+reserved<=1024`；broker STOP 分支同样核总预算并预留终态帧 | 正：六小时 fake clock 全调度 → 心跳按 60 秒节奏且到租约边界为止、帧总数仍在预算内、绝对 deadline 不变；负：心跳写失败 → `UNKNOWN_RETAINED` + `CUSTODY_HEARTBEAT_FAILED:*` + 有界收口；负：租约到期后再步进 → 不再发 STATUS；负：`sent+received` 恰好越界 → 收侧拒收且不计数、发侧拒发且不计数 | `UNKNOWN_RETAINED` | 未确认的线程保留引用，不设 None 掩盖 alive |
| **M08-d** 通道缓冲、完整写与 worker 生命周期 | `StreamChannel._drain/_check_wait/read/write/close`、`_PosixPipeEndpoint.close/bind_deadline`、`_WindowsPipeEndpoint._write_block/close/_await/_cancel/bind_deadline`、`_WindowsPipeWorker.submit/wait_done/request_cancel/stop_accepting/release_thread_handle` | 生产 `StreamChannel` + 生产 `_WindowsPipeEndpoint`/`_WindowsPipeWorker` | 无换行 buffer 每次 append 即核 32KiB 与 one-over（保留 1 字节检测）；EOF 非空 partial frame 是具名错误；队列满每轮核 cancel/deadline；所有 read 拿到实际有效 deadline（绑定后收紧对在途 read 生效）；Windows 写循环到完整帧或具名失败，上层核完整写数；每 endpoint 固定 reader/writer worker，状态 IDLE/QUEUED/IN_IO/CANCELLING/DONE/STOPPED；submit 有界、句柄创建失败/worker 已死即拒；取消先停止接收新任务，NOT_FOUND 有界复核；`done`≠线程已退出；复制的线程 HANDLE 有唯一关闭 owner | 正：写 6 字节（facade 每次只写 1 字节）→ 6 次部分写、总写数 6、worker 停止并 join、线程 HANDLE 被关闭、文件在其后关闭；负：两块无换行 → buffer ≤ 32KiB+1 且立即 overflow；负：EOF 带残帧 → `BROKER_CHANNEL_PARTIAL_FRAME`；负：取消先于 I/O 进入 → worker 不进入操作 | `UNKNOWN_RETAINED` | 活 worker 之下不关 `_file`；join 失败保留原 thread HANDLE/worker |

### C 段：终态事实与普通错误

| 独审项 | 生产函数（位置） | 驱动 | Oracle | 正/负例 | 终态 | 清理 |
|---|---|---|---|---|---|---|
| **M09** 关闭未知/失败仍丢引用、部分路径假 RELEASED | `NativeCustodySession._close_broker/stop/_stop_background`、`BrokerProcess.close`、`StreamChannel.close`、`_PosixPipeEndpoint.close` | 生产会话 + 生产 `BrokerProcess` + 生产 endpoint | 只有 `channel_closed`/`process_exited`/`process_handle_released` **及所需 reader 事实**全部为 True 才释放引用；None、缺字段、false、unknown、exception 皆 UNKNOWN 并保留同一个原 broker；`_stop_background` 失败保留 `_heartbeat`/`_pump` 引用与 error；Posix endpoint 只有 close 成功才不可逆 `_closed`；Windows retained_workers/error 向 channel→broker→Session 完整传递 | 正：全部事实为 True → 释放并沿用 RELEASED；负：close 返回 None → 保留原 broker、状态 UNKNOWN；负：`process_exited=False` → 同上；负：缺 `process_handle_released` → 同上；负：endpoint close 抛错 → `closed=False`、`error_type` 具名、可再次尝试 | `UNKNOWN_RETAINED` | 引用不丢、不假清空 |

## 3. 16 组 root 冻结 Oracle → 实际 owner 回归

`regression-obligations.json` 由 root 冻结，实现者**未修改**。16 组义务逐组落到新增模块
`tools/test_v0_s3_native_custody_regressions.py` 的 16 条用例，直接驱动**生产方法**
（生产 `WindowsApi` 注入纯原语表、生产 `BrokerCore`、生产 `BrokerLoop`、生产 `StreamChannel`、
生产 `_WindowsPipeWorker`/`_WindowsPipeEndpoint`、生产 `NativeCustodySession`、生产
`_adopt_broker_process`），不使用"只返回正确故事"的 fake 绕开失败路径。

| 义务 | 独审项 | 用例 | 触发 | Oracle 落点 |
|---|---|---|---|---|
| N03-R01 | M03 | `test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api` | birth 失败 + Wait TIMEOUT + 两次 CloseHandle 失败 | API owner 保留原句柄 + primary 与清理错；无假 RELEASED；`release_retained()` 可事后恢复 |
| N03-R02 | M03 | `test_n03_r02_a_failed_cleanup_of_the_creation_still_releases_everything` | 属性表删除抛普通异常 | NUL/process/thread 清理各自仍执行；primary 保留；无未决句柄无主 |
| N03-R03 | M04 | `test_n03_r03_the_job_query_is_unknown_whenever_a_fact_does_not_agree` | 8 组返回长度/双计数/截断/超限 | 全部 UNKNOWN；正例与零 Job 完整 header 被接受 |
| N03-R04 | M05 | `test_n03_r04_a_job_that_could_not_be_closed_keeps_its_original_handle` | limit 失败 + close 失败 | `core.job` 保留原句柄；pending/retained 具名；无无条件 take/None |
| N03-R05 | M06 | `test_n03_r05_the_stop_runs_every_cleanup_after_an_ordinary_failure` | terminate_job 普通异常（+诊断失败） | 后续清理全部尝试；primary 保留；pending 保留；UNKNOWN 且无假完成闩锁 |
| N03-R06 | M07 | `test_n03_r06_the_start_cleans_up_everything_that_it_acquired` | 心跳线程启动失败 / 取消 / Popen 后 channel 失败 | 已取得的 broker/pipe/thread 全部有主并在失败返回前清理；取消传播；清理失败保留 owner |
| N03-R07 | M08 | `test_n03_r07_the_startup_is_bounded_by_the_absolute_deadline` | arm 消耗绝对租约后返回 | 到期后不创建角色/不 resume/无成功 STATUS；独立 owner 有界返回 UNKNOWN；晚到结果只清理 |
| N03-R08 | M08 | `test_n03_r08_the_cleanup_of_the_broker_uses_one_absolute_deadline` | channel 吃 4 秒 + 两次 wait 超时 | 嵌套操作同一绝对 deadline；fake clock 不越 5 秒；无每层新 timeout/join |
| N03-R09 | M08/M09 | `test_n03_r09_a_partial_windows_write_is_never_a_success` | WriteFile 每次只写 1/6；worker done 但未退出；线程 HANDLE 已取得 | 完整 6 字节或具名失败；worker 停止并 join、复制的线程 HANDLE 被关闭；活 worker 之下不关文件 |
| N03-R10 | M08 | `test_n03_r10_the_cancellation_of_a_worker_stops_it_from_entering_io` | I/O 进入前取消；线程句柄复制失败；队列已满 | 无无界 put/join；取消状态阻止新 I/O；有界重复取消或具名 UNKNOWN 且保留原引用 |
| N03-R11 | M08 | `test_n03_r11_a_failure_of_the_background_latches_the_unknown_state` | 心跳写失败、泵失败、绝对 deadline 到期、STOP 竞态 | 闩锁 UNKNOWN + 非自 join 的有界收口；lease 之后不再 STATUS；STOP 阻断后续心跳 |
| N03-R12 | M08 | `test_n03_r12_the_frame_budget_is_the_total_of_both_directions` | 双向合计恰好 1024 与 one-over（收侧与发侧） | 边界内允许、越界在分配/发送/接受之前失败；不以单向上限替代总预算 |
| N03-R13 | M08 | `test_n03_r13_the_buffer_of_the_channel_is_bounded_and_a_partial_frame_is_named` | 两块无换行后 EOF；队列满 | buffer ≤ 32KiB(+1 检测字节) 且立即拒绝；EOF 残帧具名；等待循环观察取消/deadline |
| N03-R14 | M09 | `test_n03_r14_a_close_without_facts_keeps_the_original_broker` | close 返回 None/显式 false/缺字段；reader 与 retained worker | 缺证据不得 RELEASED；原 broker/线程/endpoint 引用保留；失败的 endpoint 不被不可逆标记 |
| N03-R15 | M11 | `test_n03_r15_the_default_launcher_refuses_with_its_own_code` | 有效 fake wall/租约下默认 launcher | 返回稳定具名结构化拒绝/UNKNOWN 并含原 code；只有取消传播；拒绝前无副作用 |
| N03-R16 | all | `test_n03_r16_the_positive_lifecycle_still_closes_everything` | 正生命周期 + 真实 retained reader 闸门与恢复 + 已闭合项 | 旧项无回归；产品返回状态与测试 salvage 分开记录；native 声明仍 NOT_PROVEN |

每条用例都**先记录产品返回时的资源/线程状态**，再由明确的测试 owner 回收（合成 allocator
释放、reader gate 释放、线程 join）；产品返回的"不干净"绝不用测试的清洁冒充。

## 4. 对既有测试文件的两处改动（如实声明）

只改 `tools/test_v0_s3_native_custody.py` 两处，**均因合同要求的行为改变**，不是放宽断言：

1. `test_the_session_closes_the_broker_on_a_parse_error`：合同 A 段要求 start 的**普通错**
   返回**结构化终态**并保留原 `error.code`，因此用例从"抛 CustodyError"改为断言
   `evidence['state'] == 'UNKNOWN_RETAINED'`、`failures` 含 `CUSTODY_FRAME_INVALID` 与
   `CUSTODY_PUMP_FAILED:CustodyError`、`peer.close_count == 1`。
   取消仍然是唯一继续传播的分支（`test_the_session_closes_the_broker_on_a_cancellation` 未改）。
2. `test_the_heartbeat_keeps_a_long_round_alive`：合同要求心跳**不得在绝对 lease 到期后发包**，
   而该用例的租约恰好等于六小时调度，因此到期那一拍（step 21600）不再发送，心跳计数由
   **360 改为 359**。用例的 Oracle（每 60 秒一次心跳、帧总数在预算内、绝对 deadline 不变）
   未变；用例仍会在心跳整体停摆时失败。

其余 115 条既有用例的断言**一律未放宽**；旧 owner 哈希与旧 native 拒绝点仍由两条 integrity
用例守住（`test_the_old_owners_are_unchanged`、`test_the_old_refusal_points_are_still_declared`）。

## 5. 静态准备与"未动态验证"的事实

* 本批**在任何动态验证之前**只做了纯静态准备：
  * `ast.parse` 四份源（custody 1481 行 / broker 3827 行 / 旧用例 2440 行 / 新回归 1291 行）全部通过；
  * 一份自写的 **纯 AST** 未定义名检查（不 import 任何候选、不执行任何候选代码）只报出模块级
    `__file__` 四个误报，无真实未定义名；
  * 逐文件 sha256 自核（见 §7）。
* **没有** import 候选模块、**没有** 运行 pytest、**没有** 触碰任何真实 Windows API / Job /
  GPU / 模型 / 服务 / 进程 / socket / sqlite / 媒体 / ledger。唯一允许的 `ctypes` 标准库预装载
  仍只在本包的**未来计划**范围内，且需要 root 的 ACK。
* 候选提交是**精确路径**提交（6 个路径：4 份源 + 本 NEW 目录的 runner/guard），没有批量 add、
  没有 reset、没有 clean、没有清理旧工作区。

## 6. 提交给 root 的精确执行计划（待 ACK，一次）

计划文件：`reports/v0-s3/product-gate0/implementation-native-custody-correction-03/plan.json`。
执行脚本：同目录 `runner.py`（离线 guard + 单次 `pytest.main` + 精确 node 绑定 + 前后 FD/线程
清单 + counter 只读观察 + receipt）。**root 的 ACK 之前不执行。**

| 项 | 值 |
|---|---|
| 候选 SHA | `46af977f86e612d05306005b9e08e54b4d10477a` |
| 基线 SHA | `37d938b983e53fee829ef1579373a97403f41d0c` |
| node 数 / 顺序 | **133**（旧 117 逐项有序不变 + 新 16 追加），顺序绑定，collection 不符即在调用任何用例前离开 |
| argv | `['/usr/bin/python3.12','-I','-B',<本目录>/runner.py,'--plan',<本目录>/plan.json]` |
| cwd | `…/LVW_Prompt_Service_MasterPack_v2.0.0` |
| 外层上限 | 300 s（一次） |
| source pins | 17（4 份允许源 + runner + guard + 11 个旧 owner/runtime 文件） |
| tool / stdlib pins | 解释器、`ctypes/__init__.py`、`_ctypes` 扩展各 1 |
| 命名依赖 pins | 223（dist-info METADATA 摘要；`pip`/`setuptools` 按计划显式排除） |
| ctypes 预装载 | 恰 1 次 `ctypes.dlopen(None)`，窗口随即 CLOSED，永不再开 |
| guard | 安装于 pytest 与任何候选 import 之前；拒 `subprocess.*`、`socket.*`、`os.system/exec/spawn/fork`、`sqlite3.connect`、一般 `ctypes.dlopen/dlsym`、`os.dlopen`；自检 8 项 |
| counter | 只读，批前批后各一次；期望 sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`；不写、不退款、不清零、不新建、不复活 |
| 失败策略 | 保留失败，不自动重跑、不加节点、不换路线；失败即失败批次，需要新候选与明确的纠正计划 |

## 7. 交付候选的字节（sha256）

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_native_custody.py` | `ef7a7c62700cc8a6bdbec19148537da559e94333af58ebcae75486ccd6c51628` |
| `tools/v0_s3_native_broker.py` | `627e829d6f4862f4dc098a0b83d6ff9d26a28813e6eb4b11e921593d86f54b36` |
| `tools/test_v0_s3_native_custody.py` | `3e0c9e5400e8ac299990517e1b63338fa0ae5c5c343dd249e871d9d2131fae4d` |
| `tools/test_v0_s3_native_custody_regressions.py` | `3fce774c43e9457c2fbbd803d78d3782c338917c0809f633ecaf44ec2fd2c181` |
| `…/implementation-native-custody-correction-03/runner.py` | `21a1b4dba51deebfb4a37cb71f6872dcb69d078d4a63fc60f4bef32223bc8cec` |
| `…/implementation-native-custody-correction-03/guard.py` | `57014eb8674b79729541d77fe65ee07b2110e39ed1fa08c1e8611743ec0b6887` |

（`plan.json` 的 `source_pins` 即以上数值，计划自身在落盘后另行复核过全部 pin，零漂移。）

## 8. 未证与不宣称

真实 Windows 执行、Job 对象行为、GPU 释放、端口释放、sampler 执行、父崩溃恢复、Windows stdin
EOF 语义、真实 Win32 ABI 运行时行为：**全部 NOT_PROVEN**。`grant_authority = NOT_VERIFIED`，
`admission_produced = false`。

本包不宣布 Stage PASS、不宣布产品 Gate0、不宣布人工签署，不回填任何历史门禁。
实现者只报告 `READY_FOR_REVIEW`；**八项 Major 是否关闭由隔离独审裁决**，本包的
静态准备与（待 ACK 后的）一次批次只证明本包的离线检查结果，不证明任何一项独审结论成立。

## 9. 已知与如实记录

1. `WindowsApi.release_retained()` 是 API owner 的**显式恢复入口**：它由 owner 主动调用，
   不是自动的。生产 Core 在 `_launch_role` 的创建失败分支把 API 保留的句柄写进
   `failures` 与 `evidence['api_retained']`，但**没有**自动调用恢复入口——自动恢复会与
   "同一 owner 决定何时再试" 的边界冲突。该事实是设计选择，不是遗漏。
2. `_StartupOwner` 的 settle 上限（`STARTUP_SETTLE_SECONDS = 1.0`）是一个独立于 cleanup
   deadline 的有界等待：它只用于"启动步骤仍在飞行时是否已经收尾"这一个判断。仍在飞行时
   loop **不**再对 core 发起清理（避免与仍在系统调用内的启动步骤竞争），并把该事实记为
   `BROKER_STARTUP_IN_FLIGHT_RETAINED`。
3. `NativeCustodySession.start()` 的普通错改为返回结构化终态后，调用方不再从 `start()` 收到
   异常。旧 owner 没有任何一处调用 `NativeCustodySession`（本包 grep 确认），因此没有旧调用方
   的行为被改变；旧 owner 与 native 拒绝点未改。
4. 本包 `runner.py` 相对纠偏 02 的同名文件只改了三处：默认 label、receipt 的 kind、以及
   `verify_pins` 现在**遵守计划里声明的 `dependency_excludes`**（纠偏 02 的实现者副本没有遵守，
   它从未被执行）。除此之外逐字未改。真正的 guard 与 runner 由 root 控制；实现者提交的
   runner/guard 只作为输入保留。
