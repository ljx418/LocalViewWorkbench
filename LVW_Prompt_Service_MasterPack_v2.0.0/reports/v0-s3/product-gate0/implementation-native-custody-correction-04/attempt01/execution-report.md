# N1 纠偏 04：唯一一次冻结离线复验的执行记录（**成功批次，如实保留**）

冻结计划（root 冻结、唯一）：
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-04/validation-plan-01/plan.json`
（sha256 `2aead0638c050840e4e8c3b81011b0403dc8c0b67e24e6d3f2346c13918048cb`，与 root 的
ACK `msg_7c0f444a6d76` / `ack.json` 一致），
ACK `ACK_ONE_FROZEN_133_NODE_OFFLINE_BATCH`，候选
`d751bced75cdc1d21cee072892860a7c4f8ac542`（tree `5a75eefd399c7df0fa135370db453cb4936818f4`）。

**结论：PASS（本批）。** 133 收集 / **133 通过 / 0 失败 / 0 跳过**，pytest exit **0**，
`cleanup_proven_for_batch = true`，批末线程回到 `['MainThread']`（上一批残留的
**2 个 heartbeat 线程已不再出现**）。**没有**自动重跑、**没有**复跑、**没有**覆写候选的
源码字节、**没有**改断言凑绿、**没有**派生 Agent、**没有**启动 N2 或任何真实运行。

## 0. 收据的实际文件名（不混用旧收据）

root 的 runner 沿用了第二批的收据名，本批的收据文件实际叫：

**`implementation-native-custody-correction-04/attempt01/native-custody-correction-03.receipt.json`**

这个文件名是继承来的，**本轮没有改名**（改名会改动 root 冻结的 runner 字节）。它**只**写在
本 NEW 目录里：

* 失败批次的收据在**另一个目录**
  `implementation-native-custody-correction-03/attempt02/`，本批**没有**读取、**没有**复制、
  **没有**覆写它；
* 本目录下的 `native-custody-correction-03.stdout.log` / `.stderr.log` 是**本批**的原始
  pytest 输出，与同目录的 `guarded-validation.stdout.log` / `.stderr.log` **逐字节相同**，
  只是沿用了 runner 的 basename 习惯；
* 逐 node 结果、FD 身份、前后线程、guard 与 preload 记录全部在上述收据与
  `native-custody-correction-04.guard.json` 里。

## 1. 执行了什么

只执行了 root 冻结计划的**三条 commands**，绝对 argv 与 cwd 逐字未改，顺序一次，**一批**：

| label | exit | wall | 产物 |
|---|---:|---:|---|
| counter-before | 0 | ~0.5 s | `counter-before.json` + `.stdout.log` / `.stderr.log` |
| guarded-validation | **0** | **14 s** | `native-custody-correction-03.receipt.json`、`native-custody-correction-04.guard.json`、`native-custody-correction-03.stdout.log` / `.stderr.log`（= `guarded-validation.stdout.log` / `.stderr.log`） |
| counter-after | 0 | ~0.5 s | `counter-after.json` + `.stdout.log` / `.stderr.log` |

外层上限 300 s，**实际总用时约 15 s**。逐条 argv、cwd 与退出码记录在 `commands.json`。

**外部 guard**：使用 `validation-plan-01/` 内的 root guard / runner / outer_counter_read，
sha256 分别是 `7c8dc5df…`、`4eb7f9cb…`、`3b575311…`，与第二批冻结包的**字节完全相同**
（root 复用了同一套工具字节，只有 plan.json 是新的）。

## 2. 环境事实

| 项 | 本批（纠偏 04） | 上一批（纠偏 03 第二批，失败） |
|---|---|---|
| 预装载事件 | 恰 **1 次** `ctypes.dlopen`，`name=null`，`window_closed_before_candidate=true`，窗口终态 **CLOSED** | 同 |
| guard 自检拒绝 | 8 项（`subprocess.Popen`、`socket.__new__`、`os.fork`、`os.exec`、`os.system`、`sqlite3.connect`、`ctypes.dlopen`、`ctypes.dlsym`） | 同 |
| guard 运行期拒绝 | **0**（禁止清单一项都没被尝试） | 同 |
| FD 身份（前→后） | 3 → 3，dev/inode/mode **逐项一致**，`new_or_reused_fds=[]`，`unknown=[]` | 同 |
| 线程（前→后） | `['MainThread']` → `['MainThread']` | `['MainThread']` → `['MainThread']` + **2 × heartbeat** |
| `cleanup_proven_for_batch` | **true** | **false** |
| counter（只读） | 前后**完全一致**：`acbdb8b1…23b98`；两次外层观测记录也逐字节相同 | 同 |
| 真实执行 | **无**：未起进程、未开 socket、未触数据库、未读原账本、未读媒体、未用网络、未下载、未调用真实 Windows API / Job / 服务 / GPU / 模型 | 同 |

**A 的修正生效的证据**：批末残留线程由 **['MainThread'] + 2 × heartbeat** 变为
**['MainThread']**，133 个节点由 130 通过变为 **133 通过 / 0 失败**。

## 3. 上轮三个失败节点的本轮事实

| 节点 | 上轮 | 本轮 |
|---|---|---|
| `tools/test_v0_s3_native_custody.py::test_the_session_closes_the_broker_on_a_cancellation` | `peer.close_count == 1` 实测 `0` | **passed**（0.001 s） |
| `tools/test_v0_s3_native_custody.py::test_the_session_closes_the_broker_on_a_parse_error` | `peer.close_count == 1` 实测 `0` | **passed**（0.001 s） |
| `tools/test_v0_s3_native_custody_regressions.py::test_n03_r06_the_start_cleans_up_everything_that_it_acquired` | `peer.closed == 1` 实测 `0` | **passed**（0.255 s） |

收据里 133 条记录的 `when` 全是 `call`、`outcome` 全是 `passed`，**没有** setup/teardown
失败、**没有** skip、**没有** xfail。

## 4. 本批证明了什么、没有证明什么

本批证明的是：**这 133 个检查在候选 `d751bce` 上全绿，且批末线程与 FD 都干净**。

本批**没有**证明、也**不**声称：

* cleanup deadline 在并发路径上的初始化唯一性与不可延长性；
* FINISHED 但保留资源的**同 owner 恢复**可达性；
* 后台 `Thread.start` 未返回 / 返回抛错、以及清理超期后是否仍保留实际 owner；
* `close_done` 事件发布与 closer 线程**真正退出**的区别；
* 状态 UNKNOWN 闩锁与晚到 `_apply_state` 的原子一致性；
* startup before / during / after 交错的用例覆盖是否完整。

**133 全绿不替代以上独审事实**；这五项仍须由隔离独审继续复算，本次 ACK 不视为其关闭。

## 5. 未证与不宣称

真实 Windows 执行、Job 对象行为、GPU 释放、端口释放、sampler 执行、父崩溃恢复、
Windows stdin EOF 语义、真实 Win32 ABI 运行时行为：**全部 NOT_PROVEN**。
`grant_authority = NOT_VERIFIED`，`admission_produced = false`，
`stage_pass_claim = false`，`product_gate0 = false`。
首批 133/115PASS/18FAIL 与 14 个 pump 残留、以及第二批 133/130PASS/3FAIL 与 2 个 heartbeat
残留，都是**历史事实，不改写**。

本包只报告 `READY_FOR_REVIEW`，**不签 Stage PASS**；八项 Major 是否关闭仍由隔离独审裁决。
