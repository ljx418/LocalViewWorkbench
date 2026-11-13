# N1 纠正记录 01：静态纠正，零执行

> 实现者：Claude Code（唯一实现者，**未派生任何 Agent**）
> 根裁决来源：Orca 编排消息 `msg_1dcd95570173`（明确**不是**执行 ACK）
> 本记录状态：**静态纠正已落盘，批次执行数 = 0**
> 本记录不签 Stage PASS，不签产品 Gate0，不产生任何 admission 证据。

---

## 0. 一句话

根的这条消息不是执行许可。它指出了四类必须一次修齐的问题（外部 guard 与 runner、
两处测试字面量抄写错误、FD/线程证据强度、四个开放项裁决）。本记录逐条登记**改了什么、
没改什么、以及被取代版本的原始字节如何被保存**。修正发生时本批**从未执行过任何一次**，
因此被取代的版本从来不是一个"执行过的工件"，它的消失没有销毁任何执行证据。

---

## 1. 被取代版本的原始字节（已保存）

| 项 | 值 |
|---|---|
| 被取代文件 | `tools/test_v0_s3_native_custody.py` |
| 被取代版本 sha256 | `5cae1123a49683389661bcb1dbe2ff8c680bcdae10c71fbded98438f595ddef4` |
| 被取代版本字节数 | 52172 |
| 被取代版本行数 | 1368 |
| 保存位置 | `reports/v0-s3/product-gate0/implementation-native-custody-01/superseded-test-module-5cae1123.py.txt` |
| 保存方式 | 从本次会话的编排记录中**重放该文件的写入与后续编辑**而重建；重建结果的 sha256 与上表**逐位相同**，因此该副本是**被证实的原件**，不是重建的近似 |
| 该副本的用途 | 只作历史留存。它**不是**源码、不在 `tools/` 下、文件名不以 `test_` 开头、不被 pytest 收集、不是任何入口 |

被取代版本在被取代前**从未被执行**（0 次导入、0 次 collection、0 次 pytest），
所以它的字节保留与"保留失败证据"不冲突：它不是一次执行的产物。

---

## 2. 错误清单（两处，逐位）

两处都是**我自己抄写**旧 owner 摘要时的字符错误，**旧 owner 文件本身没有被改动**，
根已静态核对实际摘要与本记录一致。

| # | 位置 | 我抄写的（错） | 正确的（实测 + 根核对） |
|---|---|---|---|
| 1 | `OLD_OWNERS['tools/v0_s3_production_controller.py']` | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f8bf9583a2b38` | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38` |
| 2 | `OLD_OWNERS['tools/v0_s3_coordinator.py']` | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8c4a0708d958b56f12b` | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12b` |

差异只在 `…c09948f8bf…`→`…c09948f9bf…` 与 `…bff8c4a0708…`→`…bff8f4ca0708…` 两处，
其余 62 个十六进制字符相同。**旧 owner 文件一字未改**：修正只落在测试里的字面期望。

其余 8 项 `OLD_OWNERS` 已逐项静态核对，与文件实测摘要相同：

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_quality_worker.py` | `e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592` |
| `tools/v0_s3_quality_phase.py` | `90552ea113ccf53a2a1cedff3e3f399642ad932bf0f71bb1f9a57e1adb6e8789` |
| `tools/v0_s3_supervisor.py` | `7d210429e70761cea633e8f2e64d8a1f01709930068a21de5cbc3c5a519ce6d8` |
| `tools/v0_s2_runtime.py` | `a97ea20d02ed80ab4f99f133dd8162331ddba34662bfdcca637fcade40b4dbd2` |
| `tools/v0_s2_driver.py` | `72883e2fa0c252aef7655708f40ada88a755978d71f632043c8203b53b42afed` |
| `tools/v0_s3_budget_authority.py` | `80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7` |
| `tools/local_program_authority.py` | `677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787` |
| `lvw/backend/app/native_runtime.py` | `16bf3e6396f9548312f92007eebbda55a448f0bdc6bab4a10afd71179b231a85` |

旧拒绝点（`NATIVE_EXECUTION_BACKEND_NOT_READY`、
`native_service_cleanup_proven/native_gpu_release_proven/parent_crash_recovery_proven` 三处 False）
也由静态断言守住，未被放宽。

---

## 3. 根的四项裁决与本包的处理

| 裁决 | 处理 |
|---|---|
| (a) ffmpeg / ffprobe / `VIDEO_PROBE_BACKEND` 绑定归 N2 部署与 driver adapter；不扩大 N1 闭合 plan；当前不声称媒体装配完整 | `plan` 的闭合键集未增加媒体工具；broker 的 COMFY 冻结环境**不设置** `LVW_FFMPEG_EXE` / `LVW_VIDEO_PROBE_BACKEND`；代码与 plan 都写明该绑定属于 N2，本包**不声称**媒体装配完整 |
| (b) N3 真实余额来自原 `local_program_authority` 对原 child/ledger 的验证并由父持有；shape-only 与调用者数字 ≠ 余额授权；N1 入参只做限额校验；`grant_authority` 仍 `NOT_VERIFIED`；不读账本 | `enforce_child_budget(plan, parent_child_remaining_seconds=…)` 只比较限额并拒绝"无剩余"；plan 的 `grant_authority` 固定为 `NOT_VERIFIED`；`plan_sha256_proves='PLAN_INTEGRITY_ONLY'`；本包不打开任何账本 |
| (c) nonce 保留父产生、经 broker 固定 `--nonce` 传入的私有启动上下文；不进 plan；无任意额外 CLI 参数；nonce 只绑会话，不授予 PID 托管权 | `build_broker_command(..., nonce=…)` 的参数集固定为 `--plan/--plan-sha256/--run-root/--nonce`；plan 的闭合键集未变；plan 文档写明 nonce 只绑定会话 |
| (d) 采用父 broker 原始创建 HANDLE + Job，不接管 worker PID；既有 S2 `wrapper.pid` / `_prove_listener_owned` 保持冻结；N2 需显式兼容 adapter 消费原始 owner 事实，不伪造 pid 文件、不跳过 S2 证明 | broker 只用**自己创建的**原句柄与本轮 Job 停止；本包**没有**任何按 PID/进程名的接管路径；plan 记录"N2 需要显式兼容 adapter"；本包不生成任何 pid 文件 |

---

## 4. 根的第一条（外部 guard / runner / plan）逐项处理

| 根的要求 | 落点 |
|---|---|
| 在 NEW `implementation-native-custody-01` 创建 `plan.json`、`guard.py`、`runner.py` | 三个文件已创建于该目录 |
| 精确 argv 绝对路径 / cwd / 54 节点顺序 / source·tool·223 命名依赖 pins / ≤300 s / raw logs / FD 身份 线程 | 全部写进 `plan.json`（argv 为绝对路径；cwd 为包根；54 个 nodeid 带顺序；source 15 项 + tool 1 项 + **223** 个命名依赖 pins；`max_seconds=300`；raw logs 与 receipt 路径；FD/线程策略段） |
| 保持 `/usr/bin/python3 -I -B` | plan 的 argv 为 `['/usr/bin/python3.12','-I','-B','<abs runner.py>','--plan','<abs plan.json>']` |
| guard 必须在所有候选/pytest 导入之前；不得依赖 test 内部 guard 作为唯一边界 | `guard.py` 由 `runner.py` 在 `import pytest` **之前**、在任何候选导入之前安装；**测试模块内部的 guard 已删除** |
| guard 后核 pins，显式 append，不用 site.main/.pth | runner 先装 guard，再 `sys.path.append(封存依赖路径)`，再校验 pins；不使用 `site.main`、不使用 `.pth` |
| pytest collection_finish 逐项比较精确节点集合与顺序，不匹配在任何 test call 前退出 | runner 的 `Collection.pytest_collection_finish` 比较**有序列表**；不等即抛错，会话在任何 test 调用前终止 |
| 不要运行 test 文件的 `--run` main；其 counter 快照豁免与硬拒绝冲突；由外部 runner 一次 pytest.main；原 counter 仅外层前后各一次只读 | 测试模块的 `--run` main 与 counter 快照**已删除**；runner 只调用一次 `pytest.main`；原 counter 由 runner 在**装 guard 之前**以 `O_RDONLY` 打开、之后用同一 fd `pread` 前后各读一次 |
| 前置 guard 硬拒所有 `subprocess.*`、`socket.*`、fork/exec/spawn/system/sqlite3.connect 与原 ledger/counter open，不只列部分 socket 事件 | guard 按**前缀**拒 `subprocess.` 与 `socket.` 全体成员，另按精确名拒 `os.system/os.exec/os.spawn/os.posix_spawn/os.fork/os.forkpty/sqlite3.connect`；`open` 命中 ledger/counter 即拒，**无任何豁免** |
| guard 自检只 `sys.audit`，不真实子进程/socket | `guard.selftest()` 只 `sys.audit` 这些事件并检查拒绝结果；不创建进程、不开 socket、不碰文件 |

---

## 5. 根的第三条（FD 身份 / 线程）逐项处理

| 根的要求 | 落点 |
|---|---|
| 外部 runner 逐 fstat 记录实际 dev/inode/mode | `runner.fd_inventory()` 对 `/proc/self/fd` 每个 fd 做 `os.fstat`，记录 `dev`/`inode`/`mode` |
| EBADF 枚举临时 FD 过滤 | `EBADF` 的 fd 进 `filtered` 列表并被报告 |
| 其他未知保留，不当空 | 非 EBADF 的失败进 `unknown` 列表；`available=False` 时整体标为不可用 |
| 比较前后身份含同 FD 编号复用 | `fd_comparison()` 逐编号比较前后身份；同一编号但身份不同 → `reused_numbers`；并报 `closed_numbers`/`new_numbers`/`same_identity_numbers` |
| 线程名称/是否 retained 与资源 cleanup 分开 | runner 单独出 `threads.before`/`threads.after`（name/daemon/alive/ident），与 FD 段、与 broker 自身的 cleanup 记录**分开** |
| BrokerLoop close 真实有界 join 事实不足就如实失败，不把 daemon 当结束 | `StreamChannel.close()` 现在做 `join(CLOSE_JOIN_SECONDS)` 并把 `reader_alive`/`reader_finished` 记入通道状态；`BrokerProcess.close()` 把 `reader_finished` 带到父侧；`BrokerCore._close_readers()` 逐 reader 记录 `finished`/`alive`；父侧 evidence 带 `broker_channel_reader_finished`。daemon 线程**不再**被当作已结束 |
| 读阻塞/close 失败先存证再只清理明确 owner 资源；不 GC、不关未知 FD | `BrokerCore` 只关闭**自己创建**的句柄（job/thread/process/自己创建的 pipe 端）；runner 从不关闭未知 fd，也从不以 GC 充当清理 |
| 五十四节点可保留；最后两个完整性/常量检查只算 integrity | plan 的 `integrity_only_nodes` 明确列出 `test_the_old_owners_are_unchanged` 与 `test_the_old_refusal_points_are_still_declared`，并写明"是完整性事实，不是本包的功能通过证明" |

---

## 6. 本次纠正**没有**做的事

* 没有改任何旧 controller / worker / quality_phase / supervisor / coordinator / runtime /
  driver / budget authority / local_program_authority / 协议 / 拒绝点 / MANIFEST。
* 没有改 N1 之外的任何产品源码；新增仍然只有三源（`tools/v0_s3_native_custody.py`、
  `tools/v0_s3_native_broker.py`、`tools/test_v0_s3_native_custody.py`）与本 NEW 报告目录。
* 没有 clean / reset / 批量 add；既有改动工件与失败原样保留。
* **没有执行**：未导入候选、未跑 pytest、未起任何进程/网络/sqlite、未读原 ledger、
  未启 Windows/服务/模型/GPU/端口/媒体、未下载。
* 没有放宽任何门限、没有签 Stage PASS、没有签产品 Gate0。

---

## 7. 本记录引用的标识

| 标识 | 值 |
|---|---|
| impl HEAD | `13e77492361648dc90a414f7fd37f0bb8b8c3634` |
| 产品源码 | `b95de076f37e64d321629c065e5531eba8a5250a` |
| 机器可读计划 | `reports/v0-s3/product-gate0/implementation-native-custody-01/plan.json` |
| 计划 sha256 | 见 `plan.json` 自身的摘要与本批 askroot 消息中的值 |
| 根的消息 | `msg_1dcd95570173` |
| 被取代版本 | `5cae1123a49683389661bcb1dbe2ff8c680bcdae10c71fbded98438f595ddef4`（52172 bytes / 1368 lines） |
