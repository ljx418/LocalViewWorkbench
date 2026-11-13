# N1 纠偏 03 第二批（纠正包 02）：执行记录（**失败批次，如实保留**）

批次身份：root 冻结包
`…/native-custody-correction-03/validation-plan-02/plan.json`
（sha256 `469681a34833c6252fd98f4e45fcb9c157c3c6d2ee3c96acd2f62667b37a7537`），
ACK `msg_fcb853286529`，候选 `895bfb9cd76c3f5ad714f52a11ed98f8a670fa86`（纠正包 02 的
静态最小纠正），失败基线 `46af977f86e612d05306005b9e08e54b4d10477a`。

**结论：FAILED。** 133 收集 / **130 通过 / 3 失败 / 0 跳过**，pytest exit 1，
`cleanup_proven_for_batch = false`。失败全部保留。**没有**自动修复、**没有**复跑、
**没有**覆写候选的源码字节、**没有**改断言凑绿。

## 1. 执行了什么

只执行了 root 冻结包 validation-plan-02 的三条 commands，绝对 argv 与 cwd 逐字未改
（见 `attempt02-preparation/plan.json` 的 `commands`）：**root 的 guard + root 的 runner +
root 的 outer_counter_read**；首批旧 runner 与作者包装**均未执行**。

| label | 退出码 | 产物 |
|---|---|---|
| counter-before | 0 | `attempt02/counter-before.json` + stdout/stderr |
| guarded-validation | **1** | `attempt02/native-custody-correction-03.receipt.json`、`attempt02/native-custody-correction-03.guard.json`、`attempt02/native-custody-correction-03.stdout.log` / `.stderr.log` |
| counter-after | 0 | `attempt02/counter-after.json` + stdout/stderr |

外层上限 300 s，实际用时 **12.21 s**。collection **133 项逐项有序相等**（与首批同一
nodeids 集合与顺序），无 `FROZEN_NODE_ORDER_MISMATCH`。

## 2. 环境事实

| 项 | 第二批（attempt02） | 首批（attempt01） |
|---|---|---|
| 预装载事件 | 恰 **1** 次 `ctypes.dlopen`，`name=null`，`window_closed_before_candidate=true` | 同 |
| FD 身份（前→后） | 3 → 3，dev/inode/mode 一致，`new_or_reused_fds=[]`，`unknown=[]` | 同 |
| 线程（前→后） | `['MainThread']` → `['MainThread'] + 2 × 'lvw-native-custody-heartbeat'` | `['MainThread'] + 14 × 'lvw-native-custody-channel-pump'` |
| `cleanup_proven_for_batch` | **false** | false |
| counter（只读） | 前后**完全一致**（整份 JSON 逐字节相同：sha256 `acbdb8b1…23b98`、`active=false`、`starts_total=28`、`reserved=240.0`、`spent=12.362`、`charges` 逐条相同） | 同 |
| 真实执行 | **无**：未起进程、未开 socket、未触数据库、未读原账本、未调用任何真实 Windows API / Job / GPU / 模型 / 服务 / 媒体 / 网络 / 下载 | 同 |

**A 的修正生效的证据**：批末残留的 pump 线程由 **14 → 0**，只剩 **2** 个
`lvw-native-custody-heartbeat`；133 个节点由 115 通过变为 **130 通过**。原 TypeError
（`self._remaining` 遮蔽）已不存在。

## 3. 三个失败：一个共同的、真实的**关闭协调**缺陷

三个失败节点：

| 节点 | 断言 | 实测 |
|---|---|---|
| `tools/test_v0_s3_native_custody.py::test_the_session_closes_the_broker_on_a_cancellation` | `peer.close_count == 1` | `0 == 1` |
| `tools/test_v0_s3_native_custody.py::test_the_session_closes_the_broker_on_a_parse_error` | `peer.close_count == 1` | `0 == 1` |
| `tools/test_v0_s3_native_custody_regressions.py::test_n03_r06_the_start_cleans_up_everything_that_it_acquired` | `peer.closed == 1` | `0 == 1` |

### 3.1 因果链（生产缺陷，位于 `tools/v0_s3_native_custody.py`）

1. `NativeCustodySession._close_broker()` 在**开始关闭之前**就把
   `self._close_attempted = True` 置位；第二个调用者看到这个标志就**立即返回**，
   它**不等待**正在进行的关闭。
2. `_start_bounded_close()`（心跳/泵失败时由 `_on_pump_error` → `_latch_background_failure`
   触发）启动一个 **closer 线程**去执行关闭。closer 线程先置位 `_close_attempted`。
3. 三个失败场景恰好都是「泵向会话报告了错误」或「心跳启动失败」的路径：
   * 取消：泵的 `read` 抛 `KeyboardInterrupt` → 泵的 `on_error` → closer 线程开始关闭；
     同时主线程在 `start()` 的 `except (KeyboardInterrupt, SystemExit)` 里调用
     `_close_broker()` → 看到 `_close_attempted` → **立即返回** → KI 继续传播 →
     调用方在**原 broker 尚未关闭**时就返回了。
   * parse error 与心跳线程启动失败：同一条路径。
4. 因此 `close_count` 在失败返回的那一刻是 **0**：原 broker 的关闭由 closer 线程稍后完成，
   而调用方没有等它。合同 A/M07 的义务是「已取得的原 broker 引用在失败返回前被拥有并
   **清理**」——此刻它仍被会话拥有（引用未丢），但**关闭尚未发生**。

### 3.2 为什么这是缺陷而不是用例过严

* **它是一个相对首批候选的行为回归**：在 `46af977` 中关闭是 `start()` 内的同步动作，
  同样的三条断言在纠偏 02 批次是 **117/117 全绿**（`close_count == 1` 当时成立）。
  本轮把它改成「closer 线程 + 标志位」时没有补上「等待进行中的关闭」这一半。
* **它违反了冻结义务 N03-R06 的 Oracle**：「All acquired original broker/pipe/thread
  references owned and **cleanup attempted before failure return**」。失败返回时关闭尚未
  发生，义务不成立。
* **它不是环境噪声**：同批次其余 130 条通过，失败全部落在同一条机制上；
  A 的 TypeError 已消失（残留 pump 线程 14→0）。

### 3.3 最小接口方案（**本轮未实施**，供 root 裁决）

在 `NativeCustodySession` 内把「关闭已在进行」与「关闭已完成」分开：

* 增加一个 `threading.Event`（如 `self._close_done`）与现有 `_close_lock`；
* `_close_broker()` 中，第二个调用者**不再立即返回**，而是在**同一个 cleanup 绝对截止内**
  等待进行中的关闭结束（owner 关闭完毕后 set 该事件），然后才返回；
* 拥有关闭的线程在关闭结束后（无论成功、失败或异常）**在 finally 中 set 该事件**，
  等待者因此不会永久等待，也不会与 pump 的错误回调形成循环等待：
  关闭者等 pump、pump 报错启动 closer、closer 等同一个事件，而事件只由关闭者 set，
  锁在等待期间不持有。

该方案不改动任何阈值、不删除任何到期检查、不改动 `self._remaining` 的语义，也不触碰
生产 broker（`tools/v0_s3_native_broker.py` 仍是 `46af977` 的字节）。
**按 ACK「不修改候选、不自行修到绿」，本轮未实施、未复跑。**

## 4. 与冻结义务的对照（机器逐 node 复算，取自 receipt 的 `reports`）

第二批：133 calls / 130 pass / 3 fail / 0 skip。**机器逐 node 复算（receipt `reports`，
`when == "call"`）**：旧 117 组 **115 通过 / 2 失败**，新增 16 组 **15 通过 / 1 失败**。

| 冻结义务 | 第二批结果 |
|---|---|
| N03-R01 / R02 / R03 | 通过 |
| N03-R04 | 通过（C 已纠正：两个失败点都真的触发） |
| N03-R05 | 通过（D 已纠正：重复 stop 不双关、保持 UNKNOWN 与第一错） |
| **N03-R06** | **失败**（§3 的关闭协调缺陷） |
| N03-R07 / R08 / R09 / R10 / R11 / R12 / R13 / R14 / R15 / R16 | 通过（B 的场景分离生效：租约用例 exit 4 与启动期到期拒绝各自成立） |

旧 117 组的两条失败是 `test_the_session_closes_the_broker_on_a_cancellation` 与
`test_the_session_closes_the_broker_on_a_parse_error`——它们与 N03-R06 是**同一条**
关闭协调缺陷（§3），不是两个独立缺陷。

## 5. 未证与不宣称

真实 Windows 执行、Job 对象行为、GPU 释放、端口释放、sampler 执行、父崩溃恢复、
Windows stdin EOF 语义、真实 Win32 ABI 运行时行为：**全部 NOT_PROVEN**。
`grant_authority = NOT_VERIFIED`，`admission_produced = false`。
`cleanup_proven_for_batch = false`（批末 2 个 `lvw-native-custody-heartbeat` daemon 线程
是产品关闭未完成的**事实**，不是环境噪声；进程退出回收了它们，但产品没有 join 它们）。

首批的 133/115PASS/18FAIL 与 14 个 pump 残留是**历史事实，不改写**。
本包只报告 `READY_FOR_REVIEW`，**不签 Stage PASS**；八项 Major 是否关闭仍由隔离独审裁决。
