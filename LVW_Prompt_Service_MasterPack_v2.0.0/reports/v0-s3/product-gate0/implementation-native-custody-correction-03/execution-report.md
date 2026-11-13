# N1 纠偏 03：批次执行记录（**失败批次，如实保留**）

批次身份：root 冻结包
`…/native-custody-correction-03/validation-plan-01/plan.json`
（sha256 `74a2876eef546eb194cd3c273c710ed8f7c2c1232e3dbc56640b687279695f0a`），
ACK `msg_f9a155e19e77`，候选 `46af977f86e612d05306005b9e08e54b4d10477a`，
实现交付提交 `124e9c3162e38423b6ec1e39ee4e5d4b319a36b5`。

**结论：FAILED。** 133 收集 / **115 通过 / 18 失败 / 0 跳过**，pytest exit 1，
`cleanup_proven_for_batch = false`。失败全部保留：原始 stdout、逐 node 结果、receipt、
guard 收据、counter 前后只读观察。本包**没有**自动修复、**没有**复跑、**没有**覆写
失败候选的源码字节（失败候选 `46af977` 原样保留在 Git 历史中）。

## 1. 执行了什么

只执行了 root 冻结包的三条 commands，绝对 argv 与 cwd 逐字未改（见 `commands.json`）：

| label | 退出码 | 产物 |
|---|---|---|
| counter-before | 0 | `counter-before.json` + stdout/stderr |
| guarded-validation | **1** | `native-custody-correction-03.receipt.json`、`native-custody-correction-03.guard.json`、`native-custody-correction-03.stdout.log` / `.stderr.log` |
| counter-after | 0 | `counter-after.json` + stdout/stderr |

作者提交的 `runner.py` / `guard.py` **未被执行**（root ACK 明确要求不执行作者
metadata-based runner/guard）；实际执行的是 root 的 guard + runner。
外层上限 300 s，实际用时 **10.906 s**（远低于上限）。collection **133 项逐项有序
相等**（与 root 冻结 nodeids 逐字相同），无 `FROZEN_NODE_ORDER_MISMATCH`。

## 2. 环境事实

| 项 | 值 |
|---|---|
| 预装载事件 | 恰 **1** 次 `ctypes.dlopen`，`name = null`，`window_closed_before_candidate = true` |
| FD 身份（前→后） | 3 个（0/1/2）→ 3 个，dev/inode/mode 一致；`new_or_reused_fds = []`；`unknown = []`；EBADF 过滤项单列 `[3]` |
| 线程（前→后） | `['MainThread']` → `['MainThread'] + 14 × 'lvw-native-custody-channel-pump'` → **批后残留 14 个 daemon 线程，故 `cleanup_proven_for_batch = false`** |
| counter（只读） | 前后完全一致：sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、`active=false`、`starts_total=28`、`reserved_wall_seconds=240.0`、`spent_wall_seconds=12.362`、`charges` 逐条相同；未写、未退款、未清零、未新建、未复活 |
| 真实执行 | **无**：未起进程、未开 socket、未触数据库、未读原账本、未调用任何真实 Windows API / Job / GPU / 模型 / 服务 / 媒体 / 网络 / 下载 |

## 3. 十八个失败的根因归并（四个根因，全部可定位）

### 根因 A（**生产缺陷**，15 个失败）：会话的 `_remaining` 名称遮蔽

`NativeCustodySession.__init__` 里 `self._remaining = parent_child_remaining_seconds`
是一个**整数属性**（父侧剩余预算），而本轮新增的私有方法
`NativeCustodySession._remaining(self, deadline=None)`（计算 cleanup deadline 的剩余秒数）
被同名实例属性遮蔽 → `self._remaining(deadline)` 抛
`TypeError: 'int' object is not callable`。

位置：`tools/v0_s3_native_custody.py:1090`（`self._heartbeat.join(self._remaining(deadline))`）
与 `tools/v0_s3_native_custody.py:1098`（`self._pump.join_bounded(self._remaining(deadline))`）。
`_close_broker` → `_stop_background` 因此在**任何**关闭路径上抛错：broker 的引用从未被
关闭，pump 线程从未被 join，批后残留 14 个 `lvw-native-custody-channel-pump` daemon 线程。

直接失败 10 条：`test_the_session_holds_the_original_broker_handle`、
`test_the_session_does_not_extend_the_deadline`、`test_a_repeated_stop_is_idempotent`、
`test_the_evidence_keeps_every_native_claim_not_proven`、
`test_the_stop_uses_one_shared_cleanup_budget`、`test_the_heartbeat_keeps_a_long_round_alive`、
`test_the_heartbeat_does_not_extend_the_absolute_deadline`、`test_the_frame_budget_fails_closed`、
`test_n03_r06_the_start_cleans_up_everything_that_it_acquired`、
`test_n03_r14_a_close_without_facts_keeps_the_original_broker`；
同根因连带 5 条（关闭从未发生）：`test_the_session_closes_the_broker_on_a_refusal`、
`..._on_a_cancellation`、`..._on_a_parse_error`、`test_the_session_refuses_a_peer_that_is_not_deadline_aware`、
`test_n03_r11_a_failure_of_the_background_latches_the_unknown_state`。

**最小修正**：把私有方法改名为不与既有属性冲突的名字（例如 `_cleanup_remaining`），
并同步其两处调用点。**不改** `self._remaining` 这个既有属性（它是父侧剩余预算，
在 `enforce_child_budget` 与 `evidence()` 中使用）。这是一次命名遮蔽，不是设计缺陷。

### 根因 B（**生产缺陷**，1 个失败）：启动 owner 读了两次步进时钟

`test_the_absolute_lease_stops_the_round` 用 `Clock(0.0, step=0.6)`：每次读表都前进 0.6。
`_StartupOwner.await_result` 在监督侧每次轮询读一次时钟，而被监督的启动线程在动作返回后
又读一次（`_guarded_startup` 的到期复核）。两次读表把本轮的有效租约（`deadline_mono = 1.0`）
消耗掉，于是 ARM 被判为"到期后返回" → 走 `REFUSED/BROKER_STARTUP_DEADLINE_EXCEEDED`
（exit 3），而该用例的 Oracle 是租约到期停止（exit 4）。
**实测 `assert 3 == 4`。**

**最小修正**：监督侧只在**轮询超时**时读时钟（即结果没在切片内到达时才判到期），
线程侧保留一次到期复核；这样快路径上每步只读表一次，慢路径上仍按切片有界复核。

### 根因 C（**本包测试缺陷**，1 个失败）：N03-R04 的 façade 触发点写错

`test_n03_r04_...` 用 `RecordingWin32(fail_at='close')` 期望 `core.arm()` 抛错，但该 façade
的 job limit 失败点名字是 `'job_limit'`，`'close'` 只让**关闭**失败。于是 `arm()` 正常成功，
用例报 `DID NOT RAISE BrokerError`。生产行为本身正确（limit 失败 + close 失败的路径由
`arm()` 的 `_close_handle` 分支处理）。
**最小修正**：让 `RecordingWin32` 接受一组失败点，用例改为 `fail_at=('job_limit','close')`。

### 根因 D（**本包测试缺陷**，1 个失败）：N03-R05 对重复 stop 的期望错了

`test_n03_r05_...` 的第二段用 `pytest.raises(RuntimeError)` 期望**重复**的 stop 再次抛出。
第一次 stop 已经把 job 释放（`self.job = None`），第二次 stop 的 `_terminate_the_job` 因此
不再触碰 job，也就没有新的普通异常 → 重复 stop 正常返回（状态仍为 `UNKNOWN_RETAINED`）。
**最小修正**：重复 stop 断言返回值与状态（`repeated['state'] == 'UNKNOWN_RETAINED'`），
不再断言它抛错——这正是"不双关成功关闭句柄"的期望行为。

## 4. 与冻结 Oracle 的对照

16 组冻结 Oracle 的**用例本身**全部被收集且被执行（133 = 117 + 16，无跳过）。
其中 14 条新用例**通过**，2 条新用例（R04、R05）因**本包测试自身的缺陷**失败（根因 C、D），
R06、R11、R14 因根因 A 失败。R01、R02、R03、R07、R08、R09、R10、R12、R13、R15、R16 通过。
**没有任何一条失败是"断言填绿"造成的**：失败全部来自真实的 TypeError、真实的 deadline
判定和两处本包测试自身的期望错误。

## 5. 现在的状态与下一步

* 失败候选 `46af977` **原样保留**，源码字节未被覆写；本报告与全部原始工件是它的
  **后继证据提交**，只新增收据与记录，不改四份允许源。
* 需要 root 的**明确纠正包**（新候选 + 明确纠正计划 + 一次新的 ACK）才能继续：
  纠正范围已经定位到四个根因与十行以内的最小修正（本报告 §3）。
* 在此之前**不**复跑、不重试、不换路线、不改断言、不降低门槛。
* 真实 Windows / Job / GPU / 端口 / 父崩溃 / EOF / I24 / 产品 12 / A06 / 原账本余额 /
  质量与人签：**仍未证**；本包仍只报告 `READY_FOR_REVIEW`，**不签 Stage PASS**。

## 6. 勘误（root 纠正包 02 授权之后追加；本报告 §1–§5 的正文不改）

root 的纠正包 02（`…/native-custody-correction-03/correction-plan-02/contract.md` 与
`decision.json`，message_id `msg_1f5a9dd23491`）指出本报告 §4 的一处计数与机器事实矛盾。
现按 **receipt 的 `reports` 逐 node 机器复算**追加勘误：

| 事实 | §4 的原写法 | 机器复算（receipt `reports`，`when == "call"`） |
|---|---|---|
| 新增 16 组用例 | “14 条新用例通过” | **11 通过 / 5 失败** |
| 旧 117 组用例 | 未单列 | **104 通过 / 13 失败** |
| 合计 | — | **133 calls / 115 pass / 18 fail / 0 skip** |

逐 node 的复算结果与 root 的 `regression_failed_nodes` **逐项相同**：

* 失败 5 条：`test_n03_r04_a_job_that_could_not_be_closed_keeps_its_original_handle`、
  `test_n03_r05_the_stop_runs_every_cleanup_after_an_ordinary_failure`、
  `test_n03_r06_the_start_cleans_up_everything_that_it_acquired`、
  `test_n03_r11_a_failure_of_the_background_latches_the_unknown_state`、
  `test_n03_r14_a_close_without_facts_keeps_the_original_broker`。
* 通过 11 条：R01、R02、R03、R07、R08、R09、R10、R12、R13、R15、R16 对应的节点。

§3 的根因分类与实测一致，未改：A（生产，`_remaining` 遮蔽）**15** 个失败、
B（生产/时钟场景）**1** 个、C（测试 façade 触发点）**1** 个、D（测试重复 stop 期望）**1** 个，
合计 **18** ✓。批末 **14** 个 `lvw-native-custody-channel-pump` daemon 线程与
`cleanup_proven_for_batch = false` 是 A 的**产品事实**，不是环境噪声：进程退出回收了它们，
但产品没有 join 它们，因此不得写清理通过。

首批 133/115/18/0 与 cleanup=false 是**唯一事实**，不改写、不回填。
