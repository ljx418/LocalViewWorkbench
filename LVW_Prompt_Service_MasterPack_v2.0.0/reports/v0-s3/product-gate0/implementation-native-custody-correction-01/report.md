# N1 纠偏 01：一次集中修复（静态完成，批次未执行）

> 实现者：Claude Code（唯一实现者，**未派生任何 Agent**）
> 根裁决来源：`reports/v0-s3/product-gate0/native-custody-correction-01/contract.md`
> 与同目录 `root-decision.json`（`msg_54665e0932ad`，decision=`CHANGES_REQUIRED`）
> 被取代的失败候选：`247519de8c1512d86921af8ed2c73f0db3982c88`
> 被取代批次的原始结果：54 call / **46 PASS / 8 FAIL / 0 SKIP**，exit 1，
> 功能 45/52、integrity 1/2。**该失败批次原样保留，本报告不声称任何通过。**
> 本报告状态：**READY_FOR_REVIEW**。本轮在 root 的执行 ACK（`msg_5f01dad38cef`）
> 之后，用 **root 冻结执行包**执行了**一次** 32 节点有限批次：**32 通过 / 0 失败 /
> 0 跳过**（功能 30、integrity 2）。ACK 之前 0 次导入、0 次 collection、0 次 pytest。

---

## 0. 一句话

上一批的 8 个失败里，**1 条是生产源码缺陷**（闭合计划的日志引用没有按 Windows
路径语义拒绝盘符绝对路径），**7 条是测试侧缺陷**（假 façade 的调用记录缺句柄、
假 façade 抛的是测试私有错误码而不是生产稳定码、父侧 stop 幂等性的帧数期望写错、
旧 owner 摘要末位抄错）。本轮一次把这 8 条全部修齐，并补上路径新边界与假 façade
映射的覆盖；**没有**改 broker、**没有**改任何旧 owner、**没有**改门限、
**没有**删断言、**没有**动旧证据；随后在 root 的 ACK 下用 root 自己的执行器跑了
**一次** 32 节点有限批次，**32 通过 / 0 失败 / 0 跳过**。

---

## 1. 授权范围与实际改动面

根合同允许改动的面只有三处，本轮**只动了前两处加本 NEW 报告目录**：

| 允许面 | 本轮是否改动 | 说明 |
|---|---|---|
| `tools/v0_s3_native_custody.py` | **是** | 只有 `_require_log_reference` 一个函数 |
| `tools/test_v0_s3_native_custody.py` | **是** | Fake façade 的句柄记录与错误码映射、STOP 幂等性期望、旧 owner 摘要字面量；另新增 12 个节点 |
| `reports/v0-s3/product-gate0/implementation-native-custody-correction-01/` | **是（NEW）** | 本报告 + `plan.json` + root 冻结 runner/guard 的**逐字节副本** |
| `tools/v0_s3_native_broker.py`（生产 broker 源码） | **否** | 一个字节未动；digest 仍为 `f2c10e6625e06aeb4da70506d5e75903ff28ecba3492017f06b4867d7d394a6f` |
| 全部旧 owner / 合同 / 质量门限 / control / MANIFEST / 旧报告 | **否** | 见 §8 |

新增源码后的 digest（工作区实测）：

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_native_custody.py` | `7fda324e74100ff6a4f0c0dd98392995b2ec916bd37c384e2fd45ba0cf3c463e` |
| `tools/test_v0_s3_native_custody.py` | `94cff3e052767d90cb8e986623c5a789aeafe6b8e7453c7b127fdbbdfbf8b098` |
| `tools/v0_s3_native_broker.py`（未改） | `f2c10e6625e06aeb4da70506d5e75903ff28ecba3492017f06b4867d7d394a6f` |
| `reports/.../implementation-native-custody-correction-01/guard.py`（**作者件副本**） | `12816fba33dd0874664f195847a599e1160099e85f5e8d3a89165b22744dfc80` |
| `reports/.../implementation-native-custody-correction-01/runner.py`（**作者件副本**） | `c1ffb88686a4515aaddca3f362cd100a63db6653bc2fcf8d9939a14824fe8fd7` |

### 1.1 勘误：作者副本**不是** root 的执行件（按 root 的裁决更正）

根在执行 ACK（`msg_5f01dad38cef`）里明确纠正了本报告早先的一处说法，现予更正：

* 本目录下的 `runner.py`（`c1ffb886…`）与 `guard.py`（`12816fba…`）是**先前被
  替换的作者件**的副本，**不是**上一批真正被 root 执行的那套执行件；
* 因此**不得**把它们称作与 root 执行件"同 hash 等价"，本报告早先那句
  "pin 相同则等价"**作废**；
* 本目录 `plan.json` 里那 223 项是 **dist-info 元数据 pins**，也**不是** root 本包的
  **223 个命名依赖文件 pins**。

本批**实际**执行的是 root 自己的冻结执行包：

| 项 | 值 |
|---|---|
| root 执行包目录 | `/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-01/validation-plan-01` |
| **权威 plan.json** | 同目录 `plan.json`，**sha256 `93284e0c6d398c468969e0e9a92c4a01ec485302bc3b08d394977138e662e689`** |
| root 的 runner | 同目录 `runner.py`，sha256 `4d82645de7cd67b3fe3915b9fa19c5df3cfb193930cbc83ad5f7840a05c95ff8` |
| root 的 guard | 同目录 `guard.py`，sha256 `5c0bd2f5ea7ad96a4f4abe3730ff42dd3322e33c02829b746bd986332f097cdd` |
| root 的外层 counter 读件 | 同目录 `outer_counter_read.py`，sha256 `3b575311b0de885b4f027dc4f135773ae34b9c95629dfddff4645c53187c0da7` |
| root 的 ACK | `msg_5f01dad38cef`，decision `ACK_ONCE_ACTUAL_ROOT_FROZEN_RUNNER` |
| root 的 ack.json | 同目录 `ack.json`（32 节点 / 功能 30 / 完整性 2 / 原 8 失败全覆盖） |

**我提交的 `plan.json`（`9e47a53f…`）只作为"选集与源码输入"**，它的 argv、runner、
guard **一律未被执行**；它与 root 的 plan 在同一目录里并存，**原提交文件全部保留**，
不为这次勘误再发一次 ask（按 root 的指示）。

---

## 2. 生产修复：`tools/v0_s3_native_custody.py`

### 2.1 缺陷

`validate_launch_plan` 里的 `_require_log_reference` 用
`re.match`（**前缀匹配**）判断日志引用，字符集 `[A-Za-z0-9._/-]` 里没有冒号，
于是：

* `C:/Windows/temp/comfy.log` —— 以 `C` 开头就能前缀匹配上 → **被接受**；
* `C:comfy.log`（盘符相对）—— 同上 → **被接受**；
* `temp/native/comfy.log:stream`（ADS）—— 前缀匹配 `temp/native/comfy.log` → **被接受**；
* `\\server\share\comfy.log`（UNC）—— 被 `'\\' in value` 拒绝（这一条原本就对）；
* `/var/log/comfy.log`（POSIX 绝对）—— 被 `startswith('/')` 拒绝（原本就对）。

根合同第 1 条的判定「**Windows drive log reference accepted**」指的正是这一条。

### 2.2 修法

改成**宿主无关的 Windows 路径语义**的闭合判定，规则逐条写进 docstring：

| 类别 | 例子 | 判定 |
|---|---|---|
| 盘符绝对 | `C:/Windows/temp/comfy.log`、`C:\Windows\temp\comfy.log` | 拒 |
| 盘符相对 | `C:comfy.log` | 拒 |
| UNC / 反斜杠 | `\\server\share\comfy.log`、`temp\native\comfy.log` | 拒 |
| POSIX 绝对 | `/var/log/comfy.log` | 拒 |
| 穿越 | `../comfy.log`、`temp/../comfy.log` | 拒 |
| ADS | `temp/native/comfy.log:stream` | 拒 |
| 空段 / 点段 | `temp//comfy.log`、`temp/./comfy.log` | 拒 |
| 非闭合字符集 | 含空格等 | 拒 |
| **合法相对正例** | `comfy.log`、`temp/native/comfy.log`、`temp/native/sub/comfy.log` | **接受** |

实现要点：

* **不依赖宿主**。没有用 `pathlib.Path.is_absolute()`（它在 Linux 上对 `C:/...`
  返回 `False`），没有用 `os.path`，没有用 `ntpath`。规则是纯字符串判定，
  在 Linux 上和 Windows 上给出同一个答案。
* **冒号一律拒**。冒号同时是盘符分隔符和 ADS 分隔符，一刀切掉这两类，
  日志引用因此只能是"根下的普通相对名"。
* **闭合规则同样在 broker 消费之前生效**：`tools/v0_s3_native_broker.py:53`
  从本模块导入 `validate_launch_plan`，`main()` 在 `:1484` 用**同一个函数**
  再校验一次收据里的 plan，然后才在 `:1491` 构造 `BrokerCore`。
  新节点 `test_the_broker_validates_the_plan_before_it_consumes_it` 把这个顺序
  固定下来（静态读生产源码，断言 `validate_launch_plan` 在 `BrokerCore` 之前）。
* **拒绝发生在任何创建之前**。`validate_launch_plan` 是父侧
  `NativeCustodySession.validate()`（`:462`）和 broker `main()`（`:1484`）的入口，
  失败时不会有 job、没有进程、不会有日志。断言不是只测 helper：
  新节点 `test_an_illegal_log_reference_creates_nothing` 用 **`FakeWin32` 的调用
  记录作为 Oracle**——`win32.calls == []`、`win32.created == []`（零 job、零进程），
  `tmp_path` 下零文件，且没有在源码根旁边写出 `C:` 目录或 `comfy.log`
  （零日志、真的没有去写 Windows 路径）。

### 2.3 一处**收紧**（不是放宽，如实登记）

旧判定用的是前缀匹配，所以 `'comfy.log '`（尾随空格）这类**超出闭合字符集**的
尾巴是能通过的；新判定用 `fullmatch`，尾部多一个字符即拒。这只**减少**了被接受的
集合，没有扩大它，不涉及任何门限或分母。

---

## 3. 测试侧修复：`tools/test_v0_s3_native_custody.py`

### 3.1 `FakeWin32.create_job` 记录它真正分配的假句柄

旧代码 `self.calls.append(('create_job',))` 只记了方法名，测试随后用
`[call[1] for call in win32.calls if call[0] == 'create_job'][0]` 取句柄 →
`IndexError`。现在：

```python
def create_job(self):
    handle = self._handle()
    self.calls.append(('create_job', handle))
    self._fail('create_job')
    return handle
```

句柄是 façade **真实分配**的那一个，不是占位符；失败调用仍然留在调用记录里
（失败点仍被记录），失败时**零创建**语义不变（broker 拿不到 job，
没有任何进程被创建）。

### 3.2 假 façade 按**生产稳定码**抛错

旧代码抛的是测试私有的 `BROKER_FAKE_FAILURE_CREATE` 之类，于是
`assert error.code == 'BROKER_PROCESS_CREATE_FAILED'` 必然失败——被测的分支
根本不是生产分支。现在每一处失败点都映射到生产 `WindowsApi` 在**同一位置**
抛出的稳定码：

| 假 façade 失败点 | 生产稳定码 | 生产源位置（`tools/v0_s3_native_broker.py`） |
|---|---|---|
| `create_job` | `BROKER_JOB_CREATE_FAILED` | `:341` `WindowsApi.create_job` |
| `job_limit` | `BROKER_JOB_LIMIT_FAILED` | `:357` `WindowsApi.set_job_kill_on_close` |
| `terminate_job` | `BROKER_TERMINATE_FAILED` | `:363` `WindowsApi.terminate_job` |
| `query_job` | `BROKER_JOB_QUERY_UNKNOWN` | `:387` `WindowsApi.job_process_ids`（超限分支 `:386`/`:392` 抛 `BROKER_DESCENDANT_LIMIT`） |
| `create` | `BROKER_PROCESS_CREATE_FAILED` | `:451` `WindowsApi.create_process_suspended` |
| `assign` | `BROKER_ASSIGN_FAILED` | `:477` `WindowsApi.assign_process_to_job` |
| `resume` | `BROKER_RESUME_FAILED` | `:484` `WindowsApi.resume_thread` |
| `terminate` | `BROKER_TERMINATE_FAILED` | `:490` `WindowsApi.terminate_process` |
| `close` | `BROKER_HANDLE_CLOSE_FAILED` | `:511` `WindowsApi.close_handle` |
| `pipe` | `BROKER_PIPE_FAILED` | `:524` `WindowsApi.create_pipe` |

（行号对应**未改动**的 broker 候选 `f2c10e66…`；本轮没有改 broker。）

配套的两条硬约束：

* **未知失败点不能默认为成功**：`FakeWin32(fail_at=...)` 现在只接受上表里的名字，
  写了表外的名字直接抛 `BROKER_FAKE_FAILURE_POINT_UNKNOWN`
  （新节点 `test_an_unknown_failure_point_is_refused`）。否则一个拼错的失败点
  会让整条断言**静悄悄地什么都没失败**。
* **失败真的发生过**：façade 记录 `failure_fired`，每个失败节点都断言它为真，
  不再出现"失败点根本没被走到，测试却通过"的情况。

### 3.3 STOP 幂等性：期望写错，不是生产行为错

父侧 `start()` 是**读** broker 主动发来的 STATUS 帧（`v0_s3_native_custody.py:549`），
**自己不发** STATUS；整轮父侧只发 1 帧（STOP，sequence 1）。旧期望
`len(sent) == 2` 与生产行为不符。**没有为了凑 2 帧去改生产**。新期望仍然严格：

* 初次 STOP **恰好 1 帧**，且该帧 `command == 'STOP'`、`sequence == 1`；
* 再次 stop **不新增任何帧**（`list(broker.outbound) == sent`）、**不重发 sequence**
  （`last_sequence_sent` 仍为 1、`frames_sent` 仍为 1）；
* 原 broker **只关一次**（`close_count == 1`）；
* 两次 stop 的证据 `state` 与 `frames_sent` 相同。

断言没有被删除，也没有被放宽成"至少 1 帧"。

### 3.4 旧 owner 摘要末位

`OLD_OWNERS['tools/v0_s3_coordinator.py']` 的期望值由末位 `b` 改为末位 `c`：

```
14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c
```

核对方式有二，两者在工作区一致：

1. **实文件**：`sha256sum tools/v0_s3_coordinator.py` → `…f12c`；
2. **Git blob**：`git cat-file blob 247519de8c1512d86921af8ed2c73f0db3982c88:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s3_coordinator.py | sha256sum` → `…f12c`。

**旧 owner 文件本身一个字节未改**，只改了测试里的字面期望。其余 9 项 `OLD_OWNERS`
未动，`test_the_old_refusal_points_are_still_declared` 的三处拒绝点断言未动。

### 3.5 新增节点（13 个）

路径新边界（7）：

| 节点 | 证明 |
|---|---|
| `test_a_drive_relative_log_reference_is_refused` | 盘符相对 `C:comfy.log` 被拒 |
| `test_an_alternate_data_stream_log_reference_is_refused` | ADS 被拒 |
| `test_a_unc_or_backslash_log_reference_is_refused` | UNC 与反斜杠被拒 |
| `test_a_posix_absolute_log_reference_is_refused` | POSIX 绝对被拒 |
| `test_a_legal_relative_log_reference_is_accepted` | **合法相对正例被接受** |
| `test_an_illegal_log_reference_creates_nothing` | 拒绝早于任何创建（FakeWin32 作 Oracle，零 job / 零进程 / 零日志） |
| `test_the_broker_validates_the_plan_before_it_consumes_it` | broker 消费前用同一闭合规则再校验一次 |

假 façade 映射与失败/清理分支（6）：

| 节点 | 证明 |
|---|---|
| `test_a_job_creation_failure_creates_nothing` | `BROKER_JOB_CREATE_FAILED`，零创建 |
| `test_a_job_limit_failure_closes_the_job_handle` | `BROKER_JOB_LIMIT_FAILED`，job 句柄被关闭，不泄漏 |
| `test_a_pipe_failure_creates_nothing` | `BROKER_PIPE_FAILED`，进程未被创建 |
| `test_a_failed_termination_stays_visible` | 终止失败**不会**被报成成功停止（`{'stage':'terminate','reason':'ASSIGN_FAILED','code':'BROKER_TERMINATE_FAILED'}` 在失败记录里，`terminated` 仍为 `[]`） |
| `test_a_job_termination_failure_is_not_a_release` | job 终止失败**不会**被报成 RELEASED（`job_terminated` 仍为假，轮次为 `UNKNOWN_RETAINED`） |
| `test_an_unknown_failure_point_is_refused` | 未知失败点被拒，不默认为成功 |

加上既有节点，**假 façade 的每一个失败点**（`create_job` / `job_limit` /
`terminate_job` / `query_job` / `create` / `assign` / `resume` / `terminate` /
`close` / `pipe`）在节点集合里都有**至少一个**节点驱动它的**失败**分支。

另外把两个既有节点的期望**收紧到稳定码**
（`test_an_unknown_job_query_is_not_zero` → `BROKER_JOB_QUERY_UNKNOWN`；
`test_a_close_failure_keeps_the_round_unknown` → `BROKER_HANDLE_CLOSE_FAILED`），
并给每个失败节点加上 `failure_fired` 断言。

节点总数：54 → **67**（+13）。分母、门限、既有断言**一个未减**。

---

## 4. 归因勘误（唯一一处，只改本报告，不倒写历史）

上一批的 `native-custody-01.execution-report.md` §4.8 与
`correction-note-02.md` §1 把末位 `b→c` 的错误归因为
"根的消息引用的正是**我抄错的字面量**，所以末位没有被纠正"。

**这条归因与原消息不符，现予更正。**

根的原消息在 `reports/v0-s3/product-gate0/native-custody-implementation-01/validation-plan-01/reply-body.txt`
第 2 条里写的是：

> `coordinator`正确 `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c`

**根的原回复给出的就是正确的末位 `c`。** 上一批报告说根抄错了末位，与这条原消息
直接矛盾。事实是：

1. 抄错的字面量在**实现侧**：上一批被执行的测试模块里，末位仍是 `b`；
2. 根的原回复给了正确值（`…f12c`），但**根的静态核对没有把这条正确值与测试模块里
   那一行逐位比对**——所以"测试没有按正确全文修完"这件事没有被发现。
   这是**静态核对的限制**，**不是**故意注入，也**不是**根抄错了末位；
3. 旧 owner 文件自始至终未改一个字节：根的 runner 运行时逐项校验全部 pins
   **没有 PIN_DRIFT**，根的计划 pin 的也是 `…f12c`。

旧报告、`correction-note-01.md`、`correction-note-02.md` 与被 root pin 的原始字节
**一律原样保留**，不倒写、不修改、不删除；本报告是这条归因的更正件。

---

## 5. root 旧收据的尾部换行（单列，不是产品失败）

根合同第 5 条提到的旧 runner 收据尾部字符问题，**属于 root 收据的格式问题，不是
产品失败**，登记如下：

* 原件：`reports/v0-s3/product-gate0/native-custody-correction-01/received/native-custody-01.receipt.json`
  （与 `implementation-native-custody-01/native-custody-01.receipt.json` 逐字节相同）
* **原始 bytes sha256：`5a8e96c027c5500e4c6834b561dc187ee437a85e431eec63145f161728cb32b2`**，26822 字节
* 静态读取的事实：`JSONDecoder.raw_decode` 解析到第 **26821** 字符，
  其后**尾部为 1 个换行字节** `b'\n'`；`json.loads` 对整份文件可直接解析。
* **root 已核实并澄清**（`msg_5f01dad38cef`）：原始上批收据 **`json.loads` 有效，
  末尾是正常换行**。先前"可能存在 literal 尾字符"的限制**到此澄清**。

**本轮没有改动这份收据的任何原始字节**，也没有为了它复跑旧的 54 节点批次。
下一轮 root 的 runner 只需把尾换行写对，**不得**因此修改任何历史测试结果。

---

## 6. 本次**没有**做的事

* **ACK 之前没有执行任何东西**：0 次导入候选、0 次 collection、0 次 pytest。
  **ACK 之后只执行了 1 批**，用的是 root 冻结包里的 3 条命令，没有第二批、
  没有重试、没有换路由、没有追加测试。
* **没有**真实进程、0 次 socket、0 次 sqlite、0 次读原 ledger、0 次触碰原 counter
  （counter 只被 root 的外层读件在 guard 外只读一次，前后各一次）、
  0 次 Windows API / GPU / 模型 / 服务 / 端口 / 媒体 / 下载；
  本批里只有 fake Win32 与合成文件。
* **没有**改 broker 源码、任何旧 owner、合同、质量门限、control、MANIFEST、旧报告、
  旧证据；**没有**删任何断言、**没有**改任何门限或分母。
* **没有** clean / reset / 批量 add；既有工件与失败批次原样保留。
* **没有**重跑旧的 54 全套、旧的 20/35 节点集，也没有自行补任何"compat"。
* **没有**修改 root 的冻结执行包（`validation-plan-01/` 下的 plan/runner/guard/
  outer_counter_read/ack/reply-body 全部逐字节未动）。
* **没有**主张任何 native / GPU / 端口 / 父崩溃 / Windows stdin EOF 能力：
  `grant_authority` 仍 `NOT_VERIFIED`，`admission_produced=false`，
  `stage_pass_claim=false`，`product_gate0=false`；
  native 执行、native 清理、GPU 释放、端口释放、sampler、父崩溃恢复、
  Windows stdin EOF 全部仍为 **NOT_PROVEN**。

---

## 7. 一次精确有限验证批次（已按 root 的执行 ACK 执行一次）

### 7.0 权威执行包与选集

**权威计划是 root 的冻结件**：
`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/native-custody-correction-01/validation-plan-01/plan.json`
（sha256 **`93284e0c6d398c468969e0e9a92c4a01ec485302bc3b08d394977138e662e689`**）。
root 本包采用**上一批真正被执行的那套执行器**，只换了 NEW 产物路径 / 32 节点 /
新 source pins；**3 条精确 argv 与 cwd 在 root 的 `plan.commands` 里**。
我提交的 `plan.json`（`9e47a53f…`）**只作为选集与源码输入**，其 argv / runner /
guard **未被执行**。

* **选中集合：32 个节点**（67 个里的严格子集），不是 54 全套：

  * 上一批 **8 个失败节点**：全部在集合内（`test_an_absolute_log_reference_is_refused`、
    `test_the_child_inherits_only_its_own_streams`、`test_a_create_failure_creates_nothing`、
    `test_an_assign_failure_stops_only_the_new_suspended_process`、
    `test_a_resume_failure_keeps_the_round_unknown`、`test_the_job_is_closed_with_kill_on_close`、
    `test_a_repeated_stop_is_idempotent`、`test_the_old_owners_are_unchanged`）；
  * **路径新边界**：7 个新节点 + 既有的 `test_an_escaping_log_reference_is_refused`
    + `test_a_valid_plan_is_accepted_and_closed`（合法正例）；
  * **假 façade 映射**直接关联的**成功 / 失败 / cleanup** 节点：
    `test_the_success_path_is_suspend_assign_resume`、
    `test_a_foreign_process_is_never_stopped`（终止权）、
    `test_a_partial_role_failure_stops_the_earlier_roles`（部分失败的清理）、
    `test_a_stop_is_idempotent`（core 侧幂等）、
    `test_an_over_limit_job_query_is_not_zero`（同一方法的超限分支）、
    `test_the_evidence_keeps_every_native_claim_not_proven`（反假绿）；
  * **完整性 2 个**：`test_the_old_owners_are_unchanged`、
    `test_the_old_refusal_points_are_still_declared`——**只算完整性事实，不算功能通过**。

  被改动的 Fake façade 的每一个失败点（`create_job` / `job_limit` / `terminate_job` /
  `query_job` / `create` / `assign` / `resume` / `terminate` / `close` / `pipe`）在集合里
  都有**至少一个**节点覆盖其**失败**分支，`create_job`/`job_limit`/`create`/`assign`/
  `resume`/`close` 的**成功**分支由 `test_the_success_path_is_suspend_assign_resume`、
  `test_the_child_inherits_only_its_own_streams`、`test_the_job_is_closed_with_kill_on_close`
  覆盖；**没有重复计数**（同一节点不在集合里出现两次）。
* **前置硬 guard**：root 本包自己的 `guard.py`（sha256 `5c0bd2f5…`），
  在 pytest 之前、在任何候选导入之前安装（`guard_precedes_candidate_and_pytest=true`，
  自检拒 6 项，运行时越界 0 项）；`-I -B`；root 重核了**223 个命名依赖文件 pins**
  （不是作者 plan 里的 dist-info 元数据 pins）；**精确 collection 顺序**比较
  （逐项、有序，不匹配即在任何 test call 前退出）；**真实 FD 身份**
  （dev/inode/mode，EBADF 过滤但不丢弃，未知保留）与**线程**清单。
* **原 counter**：root 的外层读件在 **guard 外**前后各读一次（不继承 FD、无访问豁免），
  期望 sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`
  （inactive 28/240/12.362），**不写、不退款、不清零、不新建、不复活**。
* **1 批，≤ 300 s**；`cwd` 为包根；3 条 argv 见 root `plan.commands`；
  tool `/usr/bin/python3.12` sha256 `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`；
  raw logs 与 receipt 落在本 NEW 目录。
* **失败原样留存**，不自动补跑、不换路由、不追加测试。

### 7.1 本批的真实结果（1 批，未重跑）

root 的执行 ACK 之后，本批**执行了一次**，用的是 root 冻结包里的 3 条命令，
命令、退出码、日志与产物的逐字节登记见本目录 `commands.json`。

| 口径 | 值 |
|---|---|
| 权威计划 | root `validation-plan-01/plan.json`，sha256 `93284e0c6d398c468969e0e9a92c4a01ec485302bc3b08d394977138e662e689` |
| 执行件 | root 的 `guard.py` + `runner.py` + `outer_counter_read.py`（作者副本**未执行**） |
| 命令 | 3 条，退出码 **0 / 0 / 0**（counter-before / guarded-validation / counter-after） |
| pytest 退出码 | **0** |
| 调用 / 通过 / 失败 / skip | 32 / **32** / **0** / **0** |
| 功能节点通过 | **30 / 30**（32 减去 2 个 integrity 节点） |
| integrity 节点 | 2 个（`test_the_old_owners_are_unchanged`、`test_the_old_refusal_points_are_still_declared`），**只算完整性事实** |
| collection 与冻结顺序 | 逐项相等且顺序一致 ✓ |
| guard | 先于候选与 pytest ✓；自检拒 6 ✓；运行时越界 **0** ✓ |
| FD | before 3 / after 3；新增或复用 **0**；unknown **0**；`cleanup_proven_for_batch=true` ✓ |
| 线程 | `['MainThread']` → `['MainThread']`，无残留 ✓ |
| 原 counter | 前后**逐字节相同**（`acbdb8b1…`，inactive，28 / 240 / 12.362，charges 相同），未写、未退款、未清零、未复活 ✓ |
| 墙钟 | 受保护批次 0.1426 s（上限 300 s），批次数 1（上限 1） |
| 真实 native 动作 | **无**（无 Windows API / 进程 / socket / SQLite / 原 ledger / 模型 / GPU / 端口 / 媒体 / 下载） |

**批次结论：PASS（32 节点内的 32 节点通过）。**
这只覆盖**被选中的 32 个节点**；失败候选那 54 节点批次**没有被重跑**，
其原始结论仍然是 **FAIL（46 PASS / 8 FAIL）**，原样保留。
本批**不关闭独审、不签 Stage PASS、不签产品 Gate0**。

---

## 8. 旧工件与旧证据的保留清单（逐字节未动）

| 工件 | sha256 | 状态 |
|---|---|---|
| `tools/v0_s3_native_broker.py` | `f2c10e6625e06aeb4da70506d5e75903ff28ecba3492017f06b4867d7d394a6f` | 未改 |
| `tools/v0_s3_coordinator.py` | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c` | 未改 |
| `tools/v0_s3_production_controller.py` | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38` | 未改 |
| `implementation-native-custody-01/runner.py` | `c1ffb88686a4515aaddca3f362cd100a63db6653bc2fcf8d9939a14824fe8fd7` | 未改 |
| `implementation-native-custody-01/guard.py` | `12816fba33dd0874664f195847a599e1160099e85f5e8d3a89165b22744dfc80` | 未改 |
| `implementation-native-custody-01/correction-note-01.md` | `4d5f06446bbd3637694cc603b075bd3d3936810acffbb3c11a363f04a66baaeb` | 未改 |
| `implementation-native-custody-01/superseded-test-module-5cae1123.py.txt` | `5cae1123a49683389661bcb1dbe2ff8c680bcdae10c71fbded98438f595ddef4` | 未改 |
| `implementation-native-custody-01/native-custody-01.receipt.json` | `5a8e96c027c5500e4c6834b561dc187ee437a85e431eec63145f161728cb32b2` | 未改 |
| 失败批次的 8 个失败与 46 个通过 | — | 原样保留，未重跑 |

其余 9 个 `OLD_OWNERS` 的 digest 见 `tools/test_v0_s3_native_custody.py` 的
`OLD_OWNERS` 表，均未改动。

---

## 9. 状态声明

* 本实现者**只报 READY_FOR_REVIEW**，**不签 Stage PASS，不签产品 Gate0**；
  本次执行 ACK **不关闭独审**。
* 上一批（失败候选 247519d）的结果仍是 **FAIL（46 PASS / 8 FAIL）**，**没有被重跑**，
  其原始证据逐字节保留。
* 本轮被 ACK 的 32 节点批次在 root 冻结执行器下 **32/32 通过、0 失败、0 跳过**
  （功能 30/30，integrity 2/2），批次结论为 PASS —— 但它**只覆盖被选中的 32 个节点**，
  不构成"全部 54 节点通过"的结论，也不构成 Stage 或 Gate0 的结论。
* 本报告不改变任何 native 结论：`grant_authority = NOT_VERIFIED`、
  `admission_produced = false`，native 执行、native 清理、GPU 释放、端口释放、
  sampler、父崩溃恢复、Windows stdin EOF 全部 **NOT_PROVEN**；
  fake Win32 只驱动了它自己那些分支，**没有**证明任何真实 Windows 行为。
