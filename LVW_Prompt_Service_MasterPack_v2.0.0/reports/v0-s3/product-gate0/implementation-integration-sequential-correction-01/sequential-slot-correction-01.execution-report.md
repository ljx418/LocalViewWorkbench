# S3-P4 顺序复用并发槽的零进程纠偏报告 — sequential-slot-correction-01

状态：**READY_FOR_REVIEW**。**不是** StagePASS，**不是** 产品 Gate0，**不是** 13 项真实 fixture 通过。
本轮**没有**执行任何带 binding 的 runner，**没有**执行任何真实 fixture 子进程，**没有**触碰原 counter。

* 基准候选：`7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0`（工作树 `ljx418/lvw-v1-d0-implement`）
* 本轮改动范围（root 允许范围）：`reports/v0-s3/product-gate0/implementation-integration-01/executor.py`、
  `tools/test_v0_s3_supervisor.py`、新增目录 `reports/v0-s3/product-gate0/implementation-integration-sequential-correction-01/`
* 未改动：`run_guarded_checks.py`、`plans/execution-control.json`、`MANIFEST.sha256`、根坐标、
  旧证据、`implementation-integration-01/report.md`（既有未提交修改原样保留）

---

## 1. 起因：root 的发现与我的独立确认

root 在派发后一分钟写下 `fixture-final-03/pre-exec-sequential-slot-finding.json`（`SUSPENDED_BEFORE_ANY_NEW_SESSION_OR_START`），
指出：`executor` 只在整轮 `reap()` 里调用 `counter.finish`，`run_fixture` 的 finally 只清 context，
已退出的前两个 child 仍为 `STARTED` 占位，第三个顺序 case 会 `CPU_CONCURRENCY_LIMIT`。

**我没有盲修。** 我用同一套假句柄、同一个真实 `executor` API，对**基准** `7ed2116` 的 executor 做了零进程复现
（`sequential-slot-baseline-7ed2116.probe.json`）：

| 序列 | 基准 7ed2116 实测 |
|---|---|
| 两个已退出假句柄 → 第三个准入 | **拒绝** `CPU_CONCURRENCY_LIMIT`（counter `occupied=2`，两条 charge 仍 `STARTED`/`settled=false`） |
| 13 个顺序假 child | 只准入 **2** 个，第 3 个（position=2）被拒；`starts_total=2` |
| 两个存活假句柄 → 第三个准入 | 拒绝 `CPU_CONCURRENCY_LIMIT`（**正确行为，必须保留**） |

→ root 的推断**成立**：顺序复用会真实撞上并发槽上限，`13` 项顺序用例过不了第 3 项。

## 2. 启动前只读核验（本轮开始时，全部满足）

| 项目 | 观察值 |
|---|---|
| HEAD | `7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0` |
| 绑定路径/hash | `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation-final-03.binding.json` / `42b41738f5a57c0cdb9e815ddfcd780cde49b5b2eb6020bdc71cc25022dd39d2` |
| 11 项 source pins | 逐项 sha256 与 `decision.json` 一致（全 OK） |
| Python hash | `/usr/bin/python3.12` = `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`（与绑定一致） |
| retry 变量 | `CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0`（自然继承；`.claude/settings.local.json` sha256 `7e6320a5…` 未改） |
| counter | `active=false`（root 在派发后暂停）、`starts_total=2`、`reserved=120.0`、`spent=2.896`、2 charge 均 `REFUSED_BEFORE_FORK`、2 session `SETTLED` |

**不符项**：counter 的 `active` 在派发时已是 `false`（root 在 03:01:29Z 暂停），
与任务书"原 counter `active=true`"不符；且 root 的发现说明原 `decision.argv` 必然撞并发槽。
→ 按任务书"任一不符停 ask root"，我**没有**执行 `decision.argv`，改为向 root 提问；
root 随后下达了新的零进程纠偏范围（`msg_b81d608598a6`），本报告即该范围的交付。

## 3. 改动（executor.py，仅 3 处 + 1 个新方法）

1. **第三条结算规则**（模块 docstring）：除"guard 自证的前 fork 拒绝"与"结算未落地"两条绝对规则外，
   新增：**原始句柄证明 child 已退出** 且 **counter 持久化了该 charge 的终态** 时，并发槽才可释放。
2. **新方法 `FiniteCpuExecutor.reconcile_exited_children()`**：在**下一次准入之前**运行的有界对账。
   只看**本 executor 自己持有的 child**；只释放"句柄已证退出 + 终态已持久化"的槽；
   存活 child / 不可证明退出 / 结算未落地 → **一律不释放**；
   **不**撤权（不 revoke admissions）、**不**停 watchdog、**不**新建 custody、**不**删除或退款任何 charge、
   **不**新建 counter、**不**提高 `max_concurrent`、**不**在每个用例后调用全局 `reap()`（`reap()` 会 revoke 并停 watchdog）。
3. **`admit()` 接入**：在 `counter.charge()` 之前先跑一次对账（顺序 run 不再被自己前一个 child 的"鬼魂"拒绝）。
4. **`reap()` 幂等**：已持久化终态的 child 不再二次 `finish`；`finish` 返回 `False` 但 counter 已持有
   `STOPPED/TIMED_OUT` 终态时视为**幂等**而非失败（不再制造假失败/假 cleanup）；
   不可证明的终态**仍然不跳过**（保持 `UNKNOWN` + 占用槽 + 保留 root）。
   另加 `SharedCounter.charge_state(index)` 只读视图，用来区分"幂等"与"结算失败"。

`tools/test_v0_s3_supervisor.py` 新增 6 个**零进程**测试（真实 `executor`/API + 合成临时 counter + 假句柄）。

## 4. 证据（本目录内，全部原始产物）

| 产物 | 内容 | 外层退出码 |
|---|---|---|
| `sequential-slot-baseline-7ed2116.probe.json` / `.stdout.log` / `.stderr.log` | 基准 executor 的零进程复现（root 推断成立） | `0`（探针本身正常；拒绝是**被观测的结果**） |
| `sequential-slot-current.probe.json` / `.stdout.log` / `.stderr.log` | 同一探针跑纠正后的 executor | `0` |
| `probe-comparison.json` | baseline/current 两次外层运行的命令、返回码、stdout/stderr sha256 | — |
| `sequential-slot-correction-01.receipt.json` / `.stdout.log` / `.stderr.log` | 有守卫 runner 的定向测试（第 1 次选择集较窄） | `0` |
| `sequential-slot-correction-02.receipt.json` / `.stdout.log` / `.stderr.log` | 有守卫 runner 的定向测试（完整选择集，15 passed / 92 deselected） | `0` |
| `sequential-slot-correction-regression-01.receipt.json` / `.stdout.log` / `.stderr.log` | 现有记账类零进程回归（49 passed / 58 deselected） | `0` |
| `sequential-slot-baseline-regression.*` + `baseline-regression-proof.outer.json` | **新测试对基准 executor 必须失败**的反证（6 failed / 9 passed / 92 deselected） | `1`（真实外层退出码，失败是**预期**） |
| `baseline-7ed2116.executor.py` | 基准 executor 的原文（`git show 7ed2116:…`，sha256 `1cafd73f…`） | — |

### 4.1 纠正后的实测行为（`sequential-slot-current.probe.json`）

| 序列 | 纠正后实测 |
|---|---|
| 两个已退出 → 第三个准入 | **准入**；两条旧 charge `STOPPED`/`settled=true` |
| 两个存活 → 第三个准入 | 拒绝 `CPU_CONCURRENCY_LIMIT`（保留） |
| 释放其中一个 → 第四个准入 | **准入**（恰好一个槽）；第五个再次拒绝 |
| 13 个顺序假 child | **13 个全部准入**，`starts_total=13`，峰值占用 `1`（≤2） |
| 退出不可证明的 child | 该 charge 保持 `STARTED`/`settled=false`，**继续占用槽**并挡住下一次准入 |
| 结算未落地（counter 拒绝） | 该 charge 保持 `STARTED`/`settled=false`，**槽不释放**，下一次准入被拒 |
| finalizer 幂等 | 已结算 child 的 `finished_wall`/`observed_lifetime_seconds` **未被重写**；`uncertain=false`；`unsettled_after_reap=[]`；`settlement_failures=[]` |

### 4.2 定向测试与回归的原命令

```text
# 定向零进程测试（无 binding、无真实 fixture、无 counter 接触）
/usr/bin/python3.12 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
  --mode focused --label sequential-slot-correction-02 \
  --outdir reports/v0-s3/product-gate0/implementation-integration-sequential-correction-01 \
  --modules tools/test_v0_s3_supervisor.py \
  --select "slot or reconciliation or sequential or finalizer"
# → 外层退出码 0；stdout: "15 passed, 92 deselected in 1.52s"；stderr 0 字节

# 记账类零进程回归
… --label sequential-slot-correction-regression-01 … \
  --select "executor or counter or session or settlement or charge or slot or reconciliation or sequential or finalizer or guard or refund or wall"
# → 外层退出码 0；stdout: "49 passed, 58 deselected in 3.16s"；stderr 0 字节

# 零进程探针对照（外层：run_probe.py）
/usr/bin/python3.12 -B reports/v0-s3/product-gate0/implementation-integration-sequential-correction-01/run_probe.py
# → 外层退出码 0；baseline 与 current 两次探针进程返回码均为 0
```

两份 runner 收据均记录：`machine_binding_present=false`、`executor_session=null`、
`fixture_process_starts=0`、`real_execution_performed=false`、`guard.single_owner_gate=true`、
`hook_install_count=1`、`handshake_confirmed=true`、`cleanup_proven=true`、`owned_root_removed=true`、
`source_unchanged_during_run=true`、`runner_unchanged_during_run=true`、
`stage_pass_claim=false`、`product_gate0=false`。

### 4.3 反证：基准上必须失败

在**仓库之外**的隔离副本（`git archive 7ed2116` → `/tmp/lvw-baseline-7ed2116`）里，用**同一份新测试文件**
跑**基准 executor**（sha256 `1cafd73f…`）：`6 failed, 9 passed, 92 deselected`，外层退出码 `1`。
失败的正是 6 个新测试；既有 9 个仍然通过。→ 新测试不是空断言，仓库本身未被改动。

## 5. 变更文件 hash（供 root 封新绑定）

| 文件 | 旧（绑定 `final-03`） | 新 |
|---|---|---|
| `reports/v0-s3/product-gate0/implementation-integration-01/executor.py` | `1cafd73ffef7230ca088b49d408f4ce4b69f5be10e238cb6710fa1e8a78d0787` | `5cf65a5ebc119bfc79c8a9ceb4dd5f28967010ca82642996273a3f63abed03f5` |
| `tools/test_v0_s3_supervisor.py` | `52aa2dbe2332a3f740c0fdc9d8131132aa2c765eccff4208c82ceb2e439c4815` | `e58585c03edb512b4b8285b48e917c5b23b0218b5986038cca47a0ac86d6dd3d` |
| 其余 9 项 pin | 未变 | 未变 |

→ **原 `final-03` 绑定已因 `PIN_DRIFT` 失效**，root 须基于新候选重新封绑定；本候选**尚未**被任何绑定授权执行。

## 6. 边界与未做的事（逐条）

* 未执行 `decision.argv`；未执行任何带 binding 的 runner；未执行任何真实 fixture 子进程；未跑 100/71/257 全套。
* 原 counter `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json` **只读未动**：
  `active=false`、`starts_total=2`、`reserved=120.0`、`spent=2.896`、2 charge `REFUSED_BEFORE_FORK`、2 session `SETTLED`。
* 未删除/退款/清零任何 charge；未新建 counter；未提高 `max_concurrent`；未改 budget_id。
* 未撤权、未停 watchdog、未在每个用例后调用全局 `reap()`；未跳过不可证明的终态。
* 未改 `plans/execution-control.json`、`MANIFEST.sha256`、根坐标、旧证据；`implementation-integration-01/report.md`
  的既有未提交修改与所有既有未跟踪工件原样保留；旧的 `finite-fixture-implementation-01/02.*` 未覆盖。
* 未改 `.claude/settings.local.json`（临时 retry env 的 hash 与 `temporary-retry-env.json` 记录一致）。

## 7. 风险与遗留（交给 root 与后续独审）

1. **本轮没有产生任何真实进程证据**：`13` 项真实 fixture 仍未跑过。顺序槽纠偏只证明"顺序准入不再被自己的
   前序 child 拒绝"，不证明真实 fixture 通过。
2. **时间预算**：原 180s 共享池只剩最后 60s；新会话的准入窗口 = 60 − 30(cleanup reserve) = 30s。
   13 个顺序 child 必须在 30s 准入窗口内跑完，且每个 child 仍受 `per_process_seconds=10` 与 `per_child_kill_seconds=1` 约束。
   纠偏本身不缩短任何单 child 生命周期。
3. **新规则的风险面**：并发槽现在多一条释放路径。它要求"原始句柄证明退出"**且**"counter 持久化终态"，
   两者缺一即不释放；结算失败会让 `uncertain=true`，finalizer 保留 root、退出码不为 0。独审应重点看
   `reconcile_exited_children()` 与 `reap()` 的幂等分支。
4. **未签 StagePASS、未签产品 Gate0**；候选 hash 绑定、独审、root 封新绑定、回收临时 env 均为 root 职责。

## 8. 给 root 的下一步（建议顺序）

1. 核对本报告与本目录原始产物（探针对照 + 反证 + 两份 runner 收据）。
2. 对新候选做隔离独审（只读复算）；独审通过后由 root 用新候选 SHA 与上表新 pin 封**新绑定**。
3. root 恢复 counter（`active=true`，同一 `budget_id`，剩余 60s 不清零、不扩容）后，
   用新绑定执行**一次**精确 13 节点（label 另起，不复用 `finite-fixture-implementation-03`）。
4. 回收窗口/恢复临时 env（`.claude/settings.local.json`）由 root 按 `temporary-retry-env.json` 处理。
