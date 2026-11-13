# N1 native custody 批次 01：执行报告（一批，失败原样保存）

> 授权：root `msg_a468b84960db`（`ACK_ONCE_ROOT_FROZEN_EXTERNAL_RUNNER`）
> 唯一权威计划：root 冻结执行包 `validation-plan-02/plan.json`
> sha256 `f028d42a3f652a09f798e4d2269e8726c9cefc89235d11dce9738c8fd9f84cd9`（与 ACK 一致 ✓）
> **执行对象**：root 的 `guard.py` + `runner.py` + `outer_counter_read.py`。**我提交的 `runner.py` / `--run` main 没有被执行。**
> **结果：批次未通过。** pytest 退出码 `1`；`8 failed, 46 passed`，0 skip。
> 不签 Stage PASS、不签产品 Gate0、不签任何 native 能力。

---

## 1. 执行了什么（一次，三条命令，全部按 root 计划的精确 argv/cwd）

机器可读记录：`commands.json`（sha256 `22e482323ec519fb861eddfd49a55ee37ecd70433e938ee84faf0d2e3fefa972`）。

| # | 标签 | 退出码 | 秒 | 说明 |
|---|---|---|---|---|
| 1 | `counter-before` | 0 | 0.027 | root 的**外部独立**只读脚本读原 counter（候选进程**不继承**该 FD） |
| 2 | `guarded-validation` | **1** | 0.655 | root 的 `guard.py` → root 的 `runner.py` → **一次** `pytest.main`，54 节点 |
| 3 | `counter-after` | 0 | 0.027 | 同上，再读一次 |

单批墙钟 **0.709 s**（受保护批次 0.655 s），远低于 ≤300 s 上限；**批次数 1**（上限 1），
**未重跑、未补跑、未追加节点、未换路由**。

| 产物 | 路径 |
|---|---|
| stdout / stderr（逐命令） | `native-custody-01.{counter-before,guarded-validation,counter-after}.{stdout,stderr}.log` |
| root runner 的收据 | `native-custody-01.receipt.json` |
| guard 记录 | `native-custody-01.guard.json` |
| counter 前后只读快照 | `counter-before.json`、`counter-after.json` |
| 精确命令 | `commands.json` |

---

## 2. 边界与卫生（全部为**已证**事实）

| 项 | 结果 |
|---|---|
| guard 先于候选与 pytest | `guard_precedes_candidate_and_pytest: true` ✓ |
| guard 自检 | 6 个事件全部被拒（`selftest_denials: 6`），只用 `sys.audit` ✓ |
| 运行时越界 | `runtime_denials: []` —— 批次内**没有**任何 OS 进程 / socket / SQLite / 原 ledger / 原 counter 读写 |
| collection 与冻结顺序 | `collected == plan.nodeids` **逐项相等且顺序一致** ✓（不一致时 root runner 会以 4 退出） |
| 调用数 | `call_count: 54`（无 skip、无未执行） |
| FD 实际身份 | before 3 个 / after 3 个；`new_or_reused_fds: []`；`unknown: []`；EBADF 的 fd 3 被过滤并上报 |
| 线程 | before `['MainThread']` → after `['MainThread']`，**无残留线程** ✓ |
| `cleanup_proven_for_batch` | **true** ✓ |
| 原 counter | before = after = `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`；`active=false`、`starts_total=28`、`reserved=240.0`、`spent=12.362`、**charges 列表逐项相同**；`written/refunded/reset/new_counter/old_grant_revived` 全为 false ✓ |
| 真实 native 动作 | 无。未启 Windows API、未起服务、未起模型、未用 GPU、未占端口、未碰媒体、未联网、未下载 |
| 依赖范围 | root 复核的**原封存 223 个命名依赖文件**（文件级 pins），不是整环境发行版，也不是传递闭包 |

---

## 3. 通过与失败（真实计数，不折算）

| 口径 | 计数 |
|---|---|
| 选中节点 | 54 |
| 实际调用 | 54 |
| 通过 | **46** |
| 失败 | **8** |
| skip | 0 |
| **功能节点通过** | **45 / 52** |
| integrity 节点 | 2 个，其中 `test_the_old_refusal_points_are_still_declared` 通过、`test_the_old_owners_are_unchanged` **失败** |

> 按 root 的口径：**最多 52 项功能通过**，本批为 **45 项功能通过 + 1 项 integrity 通过**。
> **不得**把本批说成 54 项功能通过，也不得把批次说成通过。

---

## 4. 八个失败的逐条根因（分类：1 条产品源码缺陷 + 7 条测试侧缺陷）

失败**原样保存**，不重跑、不掩盖。每一条都给出可复核的最小修正，交 root 决定下一轮计划。

### 4.1 【产品源码缺陷】`test_an_absolute_log_reference_is_refused`

* 现象：计划里的 `log: "C:/Windows/temp/comfy.log"` 被**接受**了。
* 根因：`tools/v0_s3_native_custody.py::_require_log_reference` 只拒了以 `/` 或 `\` 开头、
  含反斜杠、以及含 `..` 的引用；**正斜杠拼写的盘符绝对路径**（`C:/...`）既不匹配这些条件，
  又能通过 `_LOG_REFERENCE` 正则，于是被当成"相对 runroot 的引用"。
* 后果：broker 会把该引用拼到 run root 上；在 Windows 上 `Path(run_root)/'C:/Windows/...'`
  会**替换**掉 run root，日志会落到 run root 之外。这是闭合计划的真实漏洞。
* 最小修正：`_require_log_reference` 拒绝引用中出现 `:`（并拒绝首段形如 `X:`），
  即相对 POSIX 引用永不含冒号；配套的负例节点**已存在**（本条即该负例）。

### 4.2 【测试侧】`test_the_child_inherits_only_its_own_streams`

* 现象：`IndexError: tuple index out of range`（`[call[1] for call in win32.calls if call[0] == 'create_job'][0]`）。
* 根因：`FakeWin32.create_job` 把调用记成 **1 元组** `('create_job',)`，取不到句柄。
* 最小修正：假 façade 记成 `('create_job', handle)`（句柄先分配再记录）。

### 4.3 【测试侧】`test_a_create_failure_creates_nothing`

* 现象：`assert 'BROKER_FAKE_FAILURE_CREATE' == 'BROKER_PROCESS_CREATE_FAILED'`。
* 根因：假 façade 抛的是通用码 `BROKER_FAKE_FAILURE_*`，而生产 façade 抛的是**稳定契约码**
  `BROKER_PROCESS_CREATE_FAILED`；broker 原样透传 façade 的码（这是**正确**行为）。
* 最小修正：假 façade 按生产码抛错（见 §5 的码表）。

### 4.4 【测试侧】`test_an_assign_failure_stops_only_the_new_suspended_process`

* 同上：假 façade 抛 `BROKER_FAKE_FAILURE_ASSIGN`，期望 `BROKER_ASSIGN_FAILED`。
* 注意：该节点要证的性质（只终止本轮刚创建且仍悬停的原句柄、不重试）在本批**未被证伪**，
  失败发生在**错误码断言**这一步。

### 4.5 【测试侧】`test_a_resume_failure_keeps_the_round_unknown`

* 同上：假 façade 抛 `BROKER_FAKE_FAILURE_RESUME`，期望 `BROKER_RESUME_FAILED`。

### 4.6 【测试侧】`test_the_job_is_closed_with_kill_on_close`

* 与 §4.2 同因：`create_job` 的调用记录缺句柄，`[0]` 取不到。

### 4.7 【测试侧】`test_a_repeated_stop_is_idempotent`

* 现象：`assert 1 == 2`（发出的帧数）。
* 根因：**期望写错了**。父侧 `start()` 是**读** broker 的主动 STATUS 帧，自己**不发** STATUS；
  整轮父侧只发 1 帧（STOP，sequence 1）。被测性质（第二次 stop 不再发帧、证据不变、
  broker 句柄只关一次）在本批**未被证伪**，失败发生在帧数期望这一步。
* 最小修正：期望改为 1 帧（或由 root 决定父侧是否也应在 start 时主动发一次 STATUS）。

### 4.8 【测试侧】`test_the_old_owners_are_unchanged`

* 现象：期望 `14e8dd28…bff8f4ca0708d958b56f12b`，实测 `…bff8f4ca0708d958b56f12c`（**末位 c**）。
* 根因：这是我**第一次抄写**旧 owner 摘要时的两处字符错误之一。第一处（`8c4a`→`f4ca`）
  被根的消息纠正；第二处（**末位 `b`→`c`**）因为根的消息引用的正是**我抄错的字面量**，
  所以**没有被纠正**。root 自己的计划重新实测得到 `…f12c` 并据此 pin，
  root 的 runner 在运行时校验了全部 pins **没有 PIN_DRIFT**，**旧 owner 文件本身未改一字**。
* 最小修正：`OLD_OWNERS['tools/v0_s3_coordinator.py']` 改为
  `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c`。
* 连带：`correction-note-01.md` 的摘要表里这一行末位也是错的。该文件被 root 计划 pin，
  按 root 的要求**原样保留**，此处以本报告与 `correction-note-02.md` 更正。

---

## 5. 交给 root 的下一轮最小修正清单（**本批未应用**）

| # | 文件 | 修正 |
|---|---|---|
| 1 | `tools/v0_s3_native_custody.py` | `_require_log_reference`：拒绝 `:` 与 `X:` 首段（闭合计划漏洞） |
| 2 | `tools/test_v0_s3_native_custody.py` | `FakeWin32.create_job` 记录 `('create_job', handle)` |
| 3 | `tools/test_v0_s3_native_custody.py` | 假 façade 按生产码抛错：`BROKER_JOB_CREATE_FAILED` / `BROKER_JOB_LIMIT_FAILED` / `BROKER_PROCESS_CREATE_FAILED` / `BROKER_ASSIGN_FAILED` / `BROKER_RESUME_FAILED` / `BROKER_TERMINATE_FAILED` / `BROKER_JOB_QUERY_UNKNOWN` / `BROKER_HANDLE_CLOSE_FAILED` |
| 4 | `tools/test_v0_s3_native_custody.py` | `test_a_repeated_stop_is_idempotent` 的帧数期望改为 1（或由 root 决定父侧是否主动发 STATUS） |
| 5 | `tools/test_v0_s3_native_custody.py` | `OLD_OWNERS['tools/v0_s3_coordinator.py']` 末位改为 `c` |

**本批未应用任何一条**：被执行的候选与 root 计划 pin 的 18 个 source/tool 项**保持逐字节不变**，
root 的 `plan.json` / `guard.py` / `runner.py` / `outer_counter_read.py` 与我提交的
`plan.json` / `guard.py` / `runner.py` / `correction-note-01.md` / 被取代版本的原始字节
**全部原样保留、未改一个字节**。应用上述修正需要 root 重新冻结计划并重新 ACK。

---

## 6. 本批**没有**主张的事（逐项）

* `native_execution_proven` — **未证**（无真实 Windows API、无真实 Job、无真实服务进程）。
* `native_cleanup_proven` — **未证**（Job 进程数为零**不等于** GPU 已释放；本批根本没有真实 Job）。
* `gpu_released_proven` / `port_released_proven` / `sampler_proven` — **未证**。
* `parent_crash_recovery_proven` / `windows_stdin_eof_proven` — **未证**（Windows stdin EOF 语义仍待实测）。
* `grant_authority` — **`NOT_VERIFIED`**；`admission_produced` — **false**；
  `plan_sha256_proves` — **仅计划完整性**。
* **不签 Stage PASS、不签产品 Gate0、不宣称批次通过。**
* 批次结果：**FAIL**（pytest 退出码 1，8 项失败）；功能通过 45/52；integrity 通过 1/2。
