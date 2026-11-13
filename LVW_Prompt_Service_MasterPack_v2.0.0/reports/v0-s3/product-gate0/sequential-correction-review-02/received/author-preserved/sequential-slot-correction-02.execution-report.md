# S3-P4 顺序槽位纠偏第二轮的零进程纠正报告 — sequential-slot-correction-02

状态：**READY_FOR_REVIEW**。**不是** StagePASS，**不是** 产品 Gate0，**不是** 13 项真实 fixture 通过。
本轮**没有**执行任何带 binding 的 runner，**没有**执行任何真实 fixture 子进程，**没有**触碰原 counter，
**没有**新建共享 counter，**没有**退款或清零，**没有**改阈值、公共合同、控制文件或 MANIFEST。

* 基准候选：`4e999043d08005829969bf5020048759557ecee9`（工作树 `ljx418/lvw-v1-d0-implement`）
* 本轮候选：`01453ee07b4774a55711c5cf5642c12d0394a35c`（同一分支，只含允许的 2 个改动源）
* 本轮改动范围（root 允许范围）：`reports/v0-s3/product-gate0/implementation-integration-01/executor.py`、
  `tools/test_v0_s3_supervisor.py`、新增目录 `reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02/`
* 未改动：`run_guarded_checks.py`（字节未变）、`plans/execution-control.json`、`MANIFEST.sha256`、根坐标、
  公共合同、旧证据、`implementation-integration-01/report.md`（既有未提交修改原样保留）、
  `implementation-integration-sequential-correction-01/`（第一轮工件原样保留）、V2 目录

---

## 0. 一句话结论

独审第一轮的三项 Major（M1 结算失败仍准入 / M2 幂等终态只按名称接受 / M3 协调跨截止仍准入）
**一次全部纠正**，同一轮内不逐项停交接；**10 个新零进程测试 + 1 个被修正的错误 Oracle 测试**
在候选上全部通过，并且**同一批新测试在基准 `4e99904` 上失败 11 项**（反证），故障矩阵
**19 个转换后的 Oracle 全部成立**。

---

## 1. 启动前只读核验（本轮开始时，全部满足）

| 项目 | 观察值 |
|---|---|
| HEAD（开工时） | `4e999043d08005829969bf5020048759557ecee9` |
| retry 变量 | `CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0`（**自然继承**；`.claude/settings.local.json` sha256 `7e6320a5…` 未改，本轮也未改） |
| 原 counter | `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json` sha256 `39f2838e…`（与第一轮交付、独审 `counter-before.json` 一致）；`active=false`、`starts_total=2`、`reserved=120.0`、`spent=2.896`、2 charge 均 `REFUSED_BEFORE_FORK`、2 session 均 `SETTLED` |
| 冻结 offline 合同 | `reports/v0-s3/product-gate0/s3-integration-offline-contract-01.md`：整包 ≤24 次启动（实现 ≤16、独审 ≤8）、并发 ≤2、每次 ≤10s、累计 ≤180s、最后 30s 只清理 |
| 本轮控制 | `plans/execution-control.json`：`R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION` |
| 独审结论 | `sequential-correction-review-01/root-decision.json`：`ROOT_SEQUENTIAL_REVIEW_CHANGES_REQUIRED`，F0 M3 m0，`stage_pass_claim=false`、`product_gate0=false` |

**未发现不符项**，因此没有中途 `ask root`；本轮全程零进程、零付费、零网络、零 GPU。

---

## 2. 三项纠偏（逐条：路径 / 负例 / Oracle / 真实外层退出 / 原始 loghash）

### 2.1 M1 — 结算失败仍准入（Spare slot allows admission despite settlement failure）

**改动路径**

| 文件 | 位置 | 改动 |
|---|---|---|
| `executor.py` | `741-752`（`FiniteCpuExecutor.admit`） | 协调结果被显式检查；`reconciliation['failures']` 非空时抛 `CpuGateError('CPU_RECONCILIATION_UNSETTLED', detail=…)`，**在 `counter.charge()` 之前**，因此不产生新 charge |
| `executor.py` | `1007-1130`（`reconcile_exited_children`） | 结算失败（`False` / `CpuGateError` / `OSError`）与终态读失败（`charge_state` 抛错）都被记为 `failures` 条目；原占位保留（不写终态、`settled=false`），`self.uncertain=True`，账本 `outcome='UNKNOWN'`、`settlement_persisted=False`、`settlement_error=<机器码>` |
| `executor.py` | `1080-1102` | `OSError` 不再向上冒泡成任意异常，而是转成 `CPU_COUNTER_IO_ERROR` 的失败条目（原始异常仍以 `__cause__` 保留在调用栈，机器码进证据） |
| `executor.py` | `732` + `757` | `_check_session()` 在协调**之后**再执行一次（见 M3）；失败的准入不会留下"下一次还能进"的窗口 |

**负例（转换后的 Oracle）**：`settlement_failure_{false,gate,oserror,read_gate,read_oserror}_capacity{1,2}`
—— 触发条件与独审一致（child 已退出、原始句柄已证、结算以指定方式失败），**1 个已退出 + 1 个空槽**与
**2 个满槽**两种容量各测一次。

**Oracle**：`actual != 'ADMITTED'` ∧ `starts_after == starts_before` ∧ 拒绝码 `== CPU_RECONCILIATION_UNSETTLED`
∧ `!= CPU_CONCURRENCY_LIMIT`（满槽时不得靠并发上限假通过）∧ `uncertain is True`
∧ finalizer `cleanup_proven=false` ∧ `root_retained=true` ∧ `exit_code != 0`。

**真实外层退出**：探针外层 `0`（19/19 Oracle 成立）；定向组外层 `0`；guard 外层 `0`。
**原始 loghash**：`sequential-correction-02-negative.stdout.log` sha256 `d9c08115bb3688ef9c7556408216bf62fbd9b0b75b8d549abccad14b72a77e86`；
矩阵结果 `sequential-correction-02-negative-results.json` sha256 `96b9b01b089a8a5eef6088d95c6abb37da1dde2c7a30b7c33ffbccf03a7288a2`。

**被修正的错误 Oracle**：`test_a_settlement_that_the_counter_refuses_keeps_its_concurrency_slot`
（`tools/test_v0_s3_supervisor.py:2763`）。原 Oracle **容许失败后继续准入**（先 `admit_one` 成功、再靠满槽拿
`CPU_CONCURRENCY_LIMIT` 收尾），这只能证明"槽没被释放"，不能证明失败关闭。改为断言：本次准入以
`CPU_RECONCILIATION_UNSETTLED` 失败关闭、**不产生新 charge**、原 charge 仍 `STARTED/settled=false`、
占用数 1 < 2（**不是**满槽）、`uncertain=True`、下一次准入以 `SESSION_UNCERTAIN_CUSTODY` 再拒、
finalizer 保根且退出码非 0。**旧标准被提高，不是降低。**

### 2.2 M2 — 幂等终态只按名称接受（Idempotent terminal lacks original identity）

**改动路径**

| 文件 | 位置 | 改动 |
|---|---|---|
| `executor.py` | `121`、`124-171` | 新增**唯一**严格匹配规则 `persisted_terminal_matches()` 与常量 `PROVEN_TERMINAL_STATES=('STOPPED','TIMED_OUT')`；`UNKNOWN` **永不**是幂等成功 |
| `executor.py` | `981-1005` | `_persisted_terminal_proof()`：从绑定的共享 counter 读记录，套用该规则；**counter 读不出来是失败，不是"没有记录"** |
| `executor.py` | `459-473` | `SharedCounter.charge_state()` 增加 `budget_id` 校验，异预算的 counter 抛 `CPU_COUNTER_IDENTITY_MISMATCH`（原实现只按 index 读） |
| `executor.py` | `1074-1102` | 协调：先取持久证明；`NO_PERSISTED_RECORD`/`NOT_SETTLED` 才尝试结算；其它（foreign index / wrong pid / wrong birth / wrong exit / UNKNOWN / 状态不符）一律判为**冲突**，不释放、不静默 |
| `executor.py` | `1276-1320` | reap：删除"本地 `settlement_persisted` 标志即可跳过持久证明"的捷径；改为**本地标志声称已结算而 counter 不证明** ⇒ 失败（保根、非零退出），且**不再补写**该记录（不"修复"分歧来伪造 cleanup） |

**要求的关联**：同 budget/counter ✔（`charge_state` 校验 `budget_id`）、同 charge index ✔、
同**原 admission** ✔（role + scenario + argv 三项同时相等）、原 handle 的 pid/birth ✔、exit_code ✔、
对应 `STOPPED`/`TIMED_OUT` ✔。仅凭**名称**（state 字符串）或仅凭**本地标志**都不再算持久证明。

**负例**：`idempotency_conflict_{wrong_exit,wrong_pid_birth,foreign_index,unknown_terminal}`
—— 触发条件沿用独审，且**排除了 pending 遮蔽**：新的 charge 一旦被准入就补齐自己的原始句柄；
本轮由于准入已在结算冲突处失败关闭，根本不产生 pending charge。

**Oracle**：`actual != 'ADMITTED'` ∧ finalizer `cleanup_proven=false` ∧ `root_retained=true` ∧ `exit_code != 0`；
矩阵中每个冲突在 **reap 侧**独立复现（`settlement_error` 分别为 `EXIT_CODE_MISMATCH` / `PID_MISMATCH` /
`FOREIGN_CHARGE_INDEX` / `STATE_MISMATCH`），`failure_reasons=['CHARGE_SETTLEMENT_FAILED','OWNED_ROOT_RETAINED','UNSETTLED_CHARGE']`，`exit_code=4`。

**真实合法重复收尾不回归**：`legitimate_repeat`（已对账的 child 再次 reap）—— `finished_wall` 与
`observed_lifetime_seconds` **未重写**、`settled` 仍为 true、`starts_total` 仍为 1、charge 数仍为 1、
`uncertain=False`、`unsettled_charges()==[]`（不双结算、不退款）。对应测试
`test_the_finalizer_never_settles_a_settled_child_twice` 与
`test_a_local_settlement_marker_keeps_the_slot_and_the_root`（后者断言磁盘原状态与本地标记冲突时
**磁盘记录不被补写**）。

**真实外层退出**：探针外层 `0`；定向组外层 `0`。
**原始 loghash**：同 2.1（矩阵 stdout sha256 `d9c08115…`、结果 json sha256 `96b9b01b…`）。

### 2.3 M3 — 协调跨截止仍准入（Reconciliation I/O crosses admission deadline）

**改动路径**

| 文件 | 位置 | 改动 |
|---|---|---|
| `executor.py` | `757` | 协调之后再次 `self._check_session()`：**用原期限**复核 `clock() >= admission_deadline` 与 `uncertain`；`admission_deadline` 从不被重设（`reserve_session()` 幂等返回，不 rebasE） |
| `executor.py` | `701-713` | `_check_session()` 未改语义：`>=` 判定（**精确边界即拒绝**），`revoked`/`uncertain` 先于窗口判定 |

**负例**：`reconciliation_crosses_deadline` —— 沿用独审触发（协调的有限 I/O 把单调钟推到
`deadline + 0.001`）；另有测试 `test_the_admission_window_boundary_after_a_reconciliation_is_exact`
覆盖 **精确边界**（`clock == deadline` 拒绝）、**越一秒**（拒绝）与**早 0.001 秒**（放行）三态。

**Oracle**：拒绝码 `== SESSION_ADMISSION_WINDOW_CLOSED` ∧ `starts_after == starts_before` ∧
`executor.admission_deadline == 原值`（未重设）。

**未绕过**：并发 2、session 60、总 180、cleanup 30、退款语义**一个数字都没动**；
`git diff` 中不含任何阈值、合同、MANIFEST 或 control 文件。

**真实外层退出**：探针外层 `0`；定向组外层 `0`。
**原始 loghash**：同 2.1。

---

## 3. 改动清单（逐文件）

### 3.1 `reports/v0-s3/product-gate0/implementation-integration-01/executor.py`

1. 模块 docstring 增补**第四、第五条规则**（失败关闭的准入；严格持久证明）。
2. 新增 `PROVEN_TERMINAL_STATES` 与模块级 `persisted_terminal_matches()`（唯一严格终态匹配规则）。
3. `SharedCounter.charge_state()`：校验 `budget_id`。
4. 新增 `FiniteCpuExecutor._persisted_terminal_proof()`。
5. `FiniteCpuExecutor.reconcile_exited_children()`：返回 `{'released': [...], 'failures': [...]}`；
   失败显式反馈、保留原占位、置 `uncertain`；`OSError` 归一为 `CPU_COUNTER_IO_ERROR`。
6. `FiniteCpuExecutor.admit()`：协调失败 ⇒ `CPU_RECONCILIATION_UNSETTLED`（不 charge）；协调之后复核窗口。
7. `FiniteCpuExecutor.reap()`：用严格证明替换本地标志捷径；本地标志与磁盘冲突 ⇒ 失败且**不补写**。
8. 删除不再使用的 `_charge_state()`（它把"counter 读不出来"吞成 None，正是 M2 的陷阱之一）。

### 3.2 `tools/test_v0_s3_supervisor.py`

* 新增 `finalize_with()`（`2642`）：用**真实**的 runner finalizer 在合成 owned root 上收尾。
* 改写 `test_a_settlement_that_the_counter_refuses_keeps_its_concurrency_slot`（`2763`，错误 Oracle → 失败关闭 Oracle）。
* 新增 10 个零进程测试：`settlement_gate_error`（`2809`）、`settlement_io_error`（`2839`）、
  `unreadable_terminal_state`（`2869`）、`foreign_exit_code`（`2895`）、`foreign_handle`（`2922`）、
  `foreign_charge_index`（`2946`）、`unknown_terminal_state`（`2975`）、
  `local_settlement_marker`（`3000`）、`reconciliation_crosses_window`（`3089`）、
  `admission_window_boundary_exact`（`3126`）。
* 更新 `test_the_reconciliation_keeps_the_window_the_source_and_the_single_owner`（`3059`）以适配新的返回形状。

### 3.3 `reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02/`（新增）

`sequential_correction_02_probes.py`、`outer_boundary.py`、`run_probes.py`、`run_baseline_proof.py`、
矩阵结果/日志、receipts、原始 log、`candidate-delivery.json`、本报告、`synthetic/`（全部合成 counter）。

### 3.4 `run_guarded_checks.py`：**未改动**（sha256 `da688b1502dcf625bbbf883c5e7e519d0c4c386a51fafa15539a69e2331d1005`，运行前后一致，见 receipt 的 `runner_unchanged_during_run`）

---

## 4. 证据清单（全部在本目录内，原始产物）

| 产物 | 内容 | 真实外层退出 |
|---|---|---|
| `sequential-correction-02-focused-final.receipt.json` + `.stdout.log` + `.stderr.log` + `.outer.stdout.log` | **有守卫 runner 的定向组**：`25 passed, 92 deselected`；guard 在 pytest 前与候选 import 前安装，`hook_install_count=1`、host subprocess=blocked、network=blocked、owned root 已移除、`real_execution_performed=false` | `0` |
| `sequential-correction-02-guard.receipt.json` + `.stdout.log` + `.outer.stdout.log` | **guard 自检 4/4**：`subprocess.Popen` / `socket.bind` / `socket.connect` / `os.system` 全部被候选拒绝，握手确认 | `0` |
| `sequential-correction-02-negative-results.json` + `.stdout.log` + `.stderr.log` + `.outer.json` | **故障矩阵 19 例，19 个转换后 Oracle 全部成立**；外层退出 `0` 的语义是"每个 Oracle 成立"，**不是**"缺陷复现成功" | `0` |
| `sequential-correction-02-baseline-proof.proof.json` + `.receipt.json` + `.stdout.log` + `.outer.stdout.log` | **反证**：同一批新测试在**基准 executor `4e99904`** 上 `11 failed, 14 passed, 92 deselected`；隔离副本已删除 | `1`（失败是**预期**） |
| `sequential-correction-02-no-regression.receipt.json` + `.stdout.log` + `.outer.stdout.log` | **原 4 项审计的无回归定向组**：14 passed / 103 deselected，恰好覆盖 credential（`test_the_real_guard_refusal_releases_the_slot_of_its_own_charge`、`test_a_replayed_real_guard_refusal_releases_nothing`）、安装（`…one_guard…`、`…owns_the_guard…`、`…single_guard…`、`…guard_installation…` ×2）、持久化终态（`…settlement_failed…`、`…proof_of_a_child…`、`…repeated_settlement…`、`…failing_settlement…` ×2）、命令（`test_the_receipt_saves_the_complete_effective_command`） | `0` |
| `sequential-correction-02-counter-snapshot.json` | 原 counter 只读快照：前后 sha256 均 `39f2838e…`，字节一致 | — |
| `candidate-delivery.json` | 候选交付：10 项 source pins、2 项 changed pins、证据文件全量 hash、保留的失败、公共合同说明、NOTPROVEN 清单 | — |
| `initial-negative.*` / `initial-baseline-proof.*` | **保留的失败**：见第 6 节 | `1` / `2` |
| `sequential-correction-02-focused.*` | 第一次定向组（结果正确但 pytest 日志被 receipt 覆盖），保留 | `0` |

### 4.1 定向组与 guard 的真实外层退出（原始）

```
$ python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
    --mode focused --label sequential-correction-02-focused-final \
    --outdir reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02 \
    --modules tools/test_v0_s3_supervisor.py \
    --select "slot or reconciliation or sequential or finalizer"
→ exit 0 ; stdout: "25 passed, 92 deselected in 2.55s"

$ python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
    --mode guard --label sequential-correction-02-guard \
    --outdir reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02
→ exit 0 ; 4/4 候选拒绝
```

### 4.2 故障矩阵（19 例，全部成立）

| 组 | 用例 | 结果 |
|---|---|---|
| M1 结算失败 | `false` / `gate` / `oserror` / `read_gate` / `read_oserror` × capacity1（1 退出+1 空槽）、capacity2（2 满槽） | 10/10 `CPU_RECONCILIATION_UNSETTLED`，`starts` 不变，占用保留，`uncertain=true`，finalizer `exit=4`、保根 |
| M2 幂等冲突 | `wrong_exit` / `wrong_pid_birth` / `foreign_index` / `unknown_terminal` | 4/4 失败关闭；reap 侧独立复现，`settlement_error` 精确到 `EXIT_CODE_MISMATCH`/`PID_MISMATCH`/`FOREIGN_CHARGE_INDEX`/`STATE_MISMATCH` |
| M3 截止 | `reconciliation_crosses_deadline` | `SESSION_ADMISSION_WINDOW_CLOSED`，不新 charge，deadline 未重设 |
| 正常 | `live_children` / `unprovable_child` / `sequential13` / `legitimate_repeat` | 4/4 成立：存活子保槽、不可证明退出保槽、13 次顺序 `starts=13`/峰值 1/一次收尾/`finished_wall` 未变、合法重复收尾幂等 |

### 4.3 原 4 项审计的无回归

独审已关闭的 4 项（credential / 安装 / 持久化终态 / 命令）在本候选上**逐项复跑且全部通过**
（14 passed / 103 deselected，外层 `0`）。这**不是**对 49/57/100/71/257 整套的机械重跑：
选择式只圈住这 4 项对应的 14 个用例。

### 4.4 反证（基准 `4e99904` 上新测试必须失败）

`11 failed, 14 passed, 92 deselected`，失败项正是本轮 10 个新测试 + 1 个改为新返回形状的对账测试：

```
test_a_settlement_that_the_counter_refuses_keeps_its_concurrency_slot
test_a_settlement_gate_error_keeps_the_slot_and_fails_the_admission_closed
test_a_settlement_io_error_keeps_the_slot_and_fails_the_admission_closed
test_an_unreadable_terminal_state_keeps_the_slot_and_fails_the_admission_closed
test_a_foreign_exit_code_keeps_the_slot_of_its_charge
test_a_foreign_handle_keeps_the_slot_of_its_charge
test_a_foreign_charge_index_keeps_the_slot_of_its_charge
test_an_unknown_terminal_state_keeps_the_slot_of_its_charge
test_a_local_settlement_marker_keeps_the_slot_and_the_root
test_the_reconciliation_keeps_the_window_the_source_and_the_single_owner
test_a_reconciliation_that_crosses_the_admission_window_refuses_the_start
```

`test_the_admission_window_boundary_after_a_reconciliation_is_exact` 在基准上**通过**（旧实现的窗口判定本身是
`>=`），它是边界锁定测试，不冒充纠正证据。

---

## 5. 公共合同 / 内部兼容 / 未证明

* **公共合同：none**。本轮没有改任何公共产品合同、Schema、阈值、分母或控制文件；
  固定 24 次启动、实现 ≤16 / 独审 ≤8、并发 2、每次 ≤10s、累计 180s、最后 30s 只清理**全部未动**。
* **内部兼容说明**：`FiniteCpuExecutor.reconcile_exited_children()` 的返回值从"已释放条目列表"改为
  `{'released': [...], 'failures': [...]}`（`released` 条目形状不变）。该方法只属于 reports 子树内的
  executor，包内无公共 API 使用它；唯一使用者是本轮的测试与探针。
  `SharedCounter.charge_state()` 现在校验 budget 身份，异预算抛 `CPU_COUNTER_IDENTITY_MISMATCH`。
* **13 项真实 fixture：NOTPROVEN**。本轮零真实进程，13 项顺序用例只有**合成**证据。
* 全 I01–I24 集成、Windows 服务/后代/GPU/A06、原生 QualityPhase 组合、产品十二项质量义务、人类签署：
  **NOTPROVEN**。

---

## 6. 保留的失败（未清理、未覆盖）

| 失败 | 事实 | 处置 |
|---|---|---|
| `initial-negative.*`（外层 `1`） | 第一次故障矩阵有 1 个 Oracle 被判 VIOLATED：`unprovable_child`。**这是我自己探针的 Oracle 写错**，不是候选缺陷——不可证明退出的 child 仍占 1 个槽，counter 还有 1 个空槽，所以第一次准入本来就应当被放行、第二次才因满槽被拒 | 改正 Oracle 后重跑，19/19 成立；**初版原件全部保留**（`initial-negative-results.json` sha256 `bbbf9700c7efb64c7c4a7ae5a12601e9bc7d553b06e2d04049388b18757f8557`，stdout sha256 `26638fc2…`） |
| `initial-baseline-proof.*`（外层 `1`，脚本自身中止） | 反证的**证据脚本**先错后崩：第一次隔离副本漏了 `run_guarded_checks.py`（我把 `executor.py` 的路径当成了目录，外层 `2`、stdout 记录了 "can't open file"，该次 stderr 随后被下一次运行覆盖）；第二次副本构造正确、测试也真的跑了（`initial-baseline-proof.stdout.log` 保留着 `............FFFFFFFFF.FF.` 与 11 个失败用例），但证据脚本把 outdir 指到包外，runner 在写 receipt 时抛 `ValueError`（`relative_to`），脚本未能把副本内的 receipt 收回本目录 | 修正副本与 outdir 后重跑，`11 failed` 的完整记录（receipt + proof.json + 原始 pytest 日志）齐全；**两次的原件都保留**，初版 stderr 被覆盖这一事实也照实写在这里 |
| `sequential-correction-02-focused.*`（外层 `0`） | 第一次定向组结果正确（25 collected、exit 0），但外层 shell 把 stdout 重定向到**与 runner 自己的 pytest 日志同名**的文件，pytest 摘要被随后打印的 receipt 覆盖 | 用不同文件名重跑，原始 pytest 日志完整保留；**两次都保留** |

---

## 7. 零进程纪律与清理

* 候选 import 之前先装边界：`run_guarded_checks.py` 的 offline guard（在 pytest 前、在任何候选 import 前安装，
  `hook_install_count=1`、握手确认）；探针另装**自带的 pre-import boundary**（`outer_boundary.py`，
  形状沿用独审第一轮的 `received/outer_boundary.py`），候选 import 前即拒绝真实 socket 与进程创建。
* 本轮**没有**运行任何带 binding 的 runner、任何 fixture、任何模型/GPU/服务、任何原 ledger；
  **没有**写 `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`；只有本目录 `synthetic/` 下的合成 counter。
* 原 counter：前后 sha256 均 `39f2838e02c33b3903e4c9b23316242abe9e75e4e3592127238a88fa627bbe15`，
  `active=false`、`starts_total=2`、`reserved=120.0`、`spent=2.896`、2×`REFUSED_BEFORE_FORK`、2×`SETTLED`；
  **最后 60 秒未消耗**，未新建共享 counter、未退款、未清零。
* 反证用的隔离副本 `/tmp/lvw-baseline-4e99904-*` 已在运行后删除（`copy_removed=true`）。
* 临时 retry env（`.claude/settings.local.json`）**全程未被修改**（sha256 始终为 `7e6320a5…`，与 root 记录一致）；
  本阶段结束后按 root 记录的策略**按 hash 恢复**（hash 未变 ⇒ 移除该临时文件；`.claude` 目录原本不存在且已空 ⇒ 一并移除），
  记录见 `sequential-correction-02-retry-env-restore.json`。本轮**未**改权限、**未**包装、**未**换模型/供应商/账号，
  **未**在 429 之后重试；两次 retry 变量均为自然继承的 0/0。
  未 `git add` 全部，未清理任何项目工件：旧的 `report.md` 修改与第一轮/失败工件全部原样保留。
* 收尾：worker_done 报告后由 root 归档回收本窗口，默认**不** keep-open。

---

## 8. 十字段交接与完整路线

完整 V0–V3 大纲（完成/列明子项，取自唯一 `plans/execution-control.json`，本轮**未**修改完成度）：
V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3 0/4、R4 0/4、
R5a 0/4、R5b 0/4、R5c 0/4。S0 历史 NO_GO 保留，S1/R1a 仅已签子集，S2 为 7/8 未签；V2/V3 未激活。

1. **当前坐标**：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / READY_FOR_REVIEW。
2. **本批完成**：顺序槽位纠偏第二轮的一次性三纠正（M1/M2/M3），10 个新零进程测试 + 1 个错误 Oracle 修正，
   定向组 25 passed、guard 4/4、故障矩阵 19/19、基准反证 11 failed。
3. **最后通过门禁**：`621b1bf` 统一切片 UM10 及范围内人签，**非**本候选的 Stage。
4. **当前阻塞**：本候选待**独立**复审（M1/M2/M3 是否真正关闭）；13 项真实 fixture、全 24 与产品门禁仍 NOTPROVEN。
5. **全局路线位置**：见上述唯一 control 的完整大纲，完成度未改。
6. **剩余工作**：root 裁决 → 若通过，另行绑定有限门禁执行真实 13 项 fixture 与完整 I01–I24；V1-M1 及其后路线未动。
7. **下一责任人**：root（架构/Stage 门禁/裁决）与人类（高风险授权与体验签署）；实现者不签 StagePASS。
8. **所需授权**：本轮只读/零进程授权已足够；真实执行须 root 另发有限绑定（候选 sha 已变，
   旧 `implementation-final-03.binding.json` 已因 PIN 漂移失效）。
9. **证据目录**：`reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02/`；
   候选 sha `01453ee07b4774a55711c5cf5642c12d0394a35c`，逐文件 hash 见 `candidate-delivery.json`。
10. **精确停止原因**：本轮实现与自检完成、交付 READY_FOR_REVIEW，等待 root 归档回收与独立复审；无 StagePASS。

---

## 9. 未派生子 Agent

本轮**未**派生任何子 Agent/辅助 worker，未跨窗口协作，未做真实盘点。
