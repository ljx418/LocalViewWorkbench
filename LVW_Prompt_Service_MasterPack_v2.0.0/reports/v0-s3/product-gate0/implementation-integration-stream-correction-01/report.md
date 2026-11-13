# S3-P4 流与 fixture 集中纠偏 01（实现侧交付）

标签：`stream-correction-01`；角色：implementation（唯一 ClaudeCode 实现者，无派生 Agent）；
基准：`01453ee07b4774a55711c5cf5642c12d0394a35c`；依据：`reports/v0-s3/product-gate0/fixture-stream-correction-01/{decision.json,contract.md}`。

**结论：READY_FOR_REVIEW（不是 StagePASS）。** 本轮只做零进程代码与定向测试；新候选**没有**取得真实 13/13
fixture PASS，旧 11 PASS/2 FAIL 只属于旧候选 `01453ee`。真实复验需要 root 依据 COMPLETE03 另行裁决有限机器
预算，本实现者不自行发起、不自行推断剩余额度（spent 8.446s 不得反推可退 171s），不退款、不清零、不新建
counter、不改写旧 11PASS/2FAIL 结论。

## 1. 范围（仅三源 + 新报告目录）

| 文件 | 改动 | sha256 |
|---|---|---|
| `tools/v0_s3_supervisor.py` | 生产 stream 记账、四个稳定错误码、及时拒绝与终局 drain | `5d237cb16c4ed529093f1494ca9972bb59ccfd8e06a70c9fc5287db5dd5fbf7d` |
| `tools/fixtures/v0_s3_supervisor_fixture.py` | guard 只在 `__main__` 安装、完整 NaN 帧、1025 条紧凑帧 | `1432a6503c07ebed43e9ce36100c18f9840e51af5f6c8d81472ab7439a66df4a` |
| `tools/test_v0_s3_supervisor.py` | 零进程定向检查（真实 Writer/场景/ProtocolState/ParentSupervisor 读路径） | `f8ddc380fb52d675e1117494f146b173ddf65172b18058821bf75d20bd53c43f` |
| `reports/v0-s3/product-gate0/implementation-integration-stream-correction-01/` | 本报告与全部工件（新增） | — |

未改动：executor/runner、已独审 7 项边界、其余 production owner、公共合同/门限、固定 24 项、坐标 MANIFEST、V2。
旧 `reports/v0-s3/product-gate0/implementation-integration-01/report.md` 的既有修改与全部失败/未跟踪工件
原样保留，未清理、未 git add 全量。

## 2. 两条附约的根因与修正

### 2.1 附约 1：非有限数负例（`nonfinite_number`）

- **根因**：旧场景用 `Writer.write_raw()` 写 JSON 行且**不追加换行**，父侧按 `\n` 切帧，该行永远不成帧，
  `parse_constant=_reject_constant` 从不执行 → 落到 `PHASE_DEADLINE_EXCEEDED`（final04 实测）。
- **修正**：场景改为 `writer.write(...)` 写**完整** JSONL 帧（`payload.value = float('nan')`，`json.dumps`
  输出 `NaN` 字面量），帧以 `\n` 结束。`write_raw` 的原始字节语义**未改**，`blocking_persistence` 的故意
  不完整帧**仍然不完整**（`{"schema":"...","run_id":"` 无换行）。
- **Oracle**：先证明完整（恰好一条以 `\n` 结束的帧；宽松解析得到恰好 `MESSAGE_KEYS` 七个键；`math.isnan`），
  **再**证明被拒（`decode_message` → `MESSAGE_NONFINITE_NUMBER`；父侧真实读路径同一码）。
- **负例**：非有限值不得被"截断成非法 JSON"或"变成合法 JSON"绕过；帧不完整时不得被当作协议消息。
- **持久终态**：`protocol_violation='MESSAGE_NONFINITE_NUMBER'`、`message_count=0`、`root_retained=True`、
  `cleanup.proven_stopped=True`。
- **清理**：父只终止自己持有的句柄；fixture 侧无进程残留。
- **风险**：低。`NaN` 仍是 Python 的宽松扩展，`allow_nan` 只出现在 fixture 的写侧，父侧解码仍是
  `parse_constant=_reject_constant`（严格拒绝）。

### 2.2 附约 2：消息数负例（`message_flood`）

- **根因**：旧场景写 1200 条 PROGRESS（每条约 300B，合计约 360000B），在第 1024 条**之前**先撞到
  `MAX_STREAM_BYTES=262144` → `_StreamReader` 提前 overflow → 父侧当时不察觉 overflow，只能等 10800s
  phase 兜底 → `PHASE_DEADLINE_EXCEEDED`（final04 实测）。
- **修正**：场景改为**恰好 `MAX_MESSAGES+1 = 1025` 条完整合法紧凑帧**（第 1 条 `STARTED`，其余 `PROGRESS`
  空 payload），identity 与父 context 一致；生成**前**用真实代码算 wire，任一上限不满足即
  `SystemExit('FIXTURE_WIRE_BUDGET_EXCEEDED')` 自拒，绝不写出一个会被字节上限遮蔽的流。
- **短合成 run_id**：仅该负例使用 `run_id='syn1'`（4 字符），由**父 context 与子消息同一绑定**；
  `candidate_sha` 仍 40、`authorization_sha256` 仍 64，未伪造、未放松 identity 校验。真实值（探针实测）：
  - 短身份 `syn1`：**1025 帧 / 总 252162B / 最长帧 338B** → `252162 ≤ 262144`、`338 ≤ 32768` ✔
  - 长身份 `synthetic-quality-run`（21 字符）：**总 269587B > 262144** ✘ —— 即"旧身份下即使空 payload 也
    越界"由**代码实测**确认（root 独立算得 269493，量级一致），故不能机械删 payload 充数。
- **Oracle**：真实 `ProtocolState` 先吃 1024 条（`count=1024`）→ 第 1025 条
  `MESSAGE_COUNT_EXCEEDED`；同一根因下 `stdout_overflow=False`、`stdout_bytes ≤ 262144`，**字节上限没有抢先**。
  未把 Oracle 换成 phase timeout，未提高任何上限（1024/32KiB/256KiB 逐项断言）。
- **负例**：1024 条**恰好合法**——补一条真实 `TERMINAL` 后父侧 `message_count=1024`、
  `protocol_violation=None`、`canonical_receipt_verified=True`、`root_retained=False`（证"只多一条才拒"）。
- **持久终态**：`protocol_violation='MESSAGE_COUNT_EXCEEDED'`、`message_count=1024`、
  `root_retained=True`、`cleanup.proven_stopped=True`。
- **清理**：父终止自己持有的句柄；fixture 子进程被父停止，无后代。
- **风险**：中。短 run_id 只存在于该负例的 context（临时目录内），不进入产品身份链；真实收据/候选绑定
  长度未变；但**真实 13 场景复验尚未执行**（见第 5 节），本条 Oracle 目前只有零进程证据。

### 2.3 附约 3：生产 stream 及时稳定拒绝（`ParentSupervisor`）

- **根因**：`_StreamReader` 早已记录 `overflow`/`error`，但生产父循环**从不读这两个标志**；父只能等
  10800s phase 兜底，且"同批已有 TERMINAL"会被当作成功。
- **修正**（`tools/v0_s3_supervisor.py`）：
  - 新增四个稳定内部码常量：`STDOUT_STREAM_LIMIT_EXCEEDED`、`STDERR_STREAM_LIMIT_EXCEEDED`、
    `STDOUT_STREAM_READ_FAILED`、`STDERR_STREAM_READ_FAILED`。
  - `ParentSupervisor._stream_failure()` 在**每次消费之后**检查两个 reader 的 `overflow`/`error`；命中即
    `self.violation=<稳定码>` → 跳出循环 → `_terminate_owned_worker()` 终止**自己持有**的句柄 → 保留根与
    预约。检测在轮询间隔内完成，**不等 10800s**。
  - 父循环先消费协议、后判 stream：已收到的帧**不丢**；随后判 stream 失败，**同一批的 TERMINAL 不能把
    资源/读错误变成成功**。
  - 终局 `_drain_streams()`：父停掉 worker 后**有界等待**（`DRAIN_TIMEOUT_SECONDS=0.5`）两个 reader 到 EOF，
    再消费一次剩余帧，并复查 stream 失败——否则"TERMINAL 早到、overflow 晚到"的批次会假成功。
  - `evidence()`：`unknown_outcome` 改为"`violation` 非空即未知"（原为"violation 非空**且**无 TERMINAL"），
    因此任何拒绝都保留根/预约、禁归档/退款/重发/下一 phase。
- **Oracle**：stdout/stderr 各测**恰好 262144B**（不拒：`stdout_overflow=False`、`stdout_bytes=262144`）与
  **262145B**（拒：稳定码）；两个 reader 各自读失败（`OSError` → `*_STREAM_READ_FAILED`）；TERMINAL 与
  overflow 同批 → `terminal_received=True` 但 `protocol_violation=STDOUT_STREAM_LIMIT_EXCEEDED`、
  `unknown_outcome=True`、`root_retained=True`、`archive_allowed=False`、`next_phase_allowed=False`、
  `cleanup.proven_stopped=True`。
- **负例**：不得靠关掉 guard 或放宽上限换绿；正常有界流与原 deadline 行为保持（见第 4 节回归）。
- **持久终态**：`protocol_violation=<四个稳定码之一>`、`root_retained=True`、`archive_allowed=False`、
  `refund_allowed=False`、`resend_allowed=False`、`next_phase_allowed=False`。
- **清理**：只终止父自己持有的句柄；`proven_stopped` 取真实 `poll()`。
- **风险**：中。**证据字段语义变化**：`stdout_bytes`/`stderr_bytes` 由"消费后仍持有的字节"改为"该流送达
  的总字节"，新增 `stdout_bytes_retained`/`stderr_bytes_retained`/`stdout_read_error`/`stderr_read_error`/
  `stream_violation`；`unknown_outcome` 语义见上。全仓无其它消费者读这些字段（已 grep 复核），既有 121 项
  断言全部保持。父循环新增"消费后判 stream"这一步，极端情况下（stream 失败与协议错误同批）以**先到的拒绝
  原因**为准。

### 2.4 附约 4：并发读与消费不丢帧、字节语义明确

- **根因**：旧 `_StreamReader` 溢出时**整块丢弃**（含块内仍在预算内的合法帧）；`evidence()` 把"消费后剩余
  缓冲"当成整条流（`stdout_bytes` 常年为 0，`stdout_sha256` 只哈希残余缓冲）。
- **修正**：
  - 越界时只保留**仍在预算内**的前缀（`allowed = limit - before`），越界尾巴丢弃并置 `overflow`：
    保留字节**永不超过** 256KiB，且预算内的帧不丢。
  - reader 三本账分开：`total`（该流送达总字节）、`received`（全部已收字节，供 hash）、`chunks`（父尚未
    消费的字节）；`evidence()` 报告 `stdout_bytes=total`、`stdout_bytes_retained=retained+父缓冲`、
    `stdout_sha256=hash(全部已收字节)`——**不再把消费后的空缓冲称作原流为空**。
  - 父循环临界区只做"取已收块 + 切帧 + 解码"，**不含 `os.read`、不含外部回调**，不使父循环同步等待输入；
    `os.read` 只在 reader 线程中。
- **Oracle**：`stdout_bytes_retained ≤ 262144`；1025 帧全部被解析到第 1025 条才拒（`message_count=1024`）；
  `blocking_persistence` 的不完整帧**从未成为消息**（`message_count=1`，只有前面的完整 `STARTED`）。
- **负例**：消费后的空缓冲不得报成"流为空"；越界块内仍在预算内的帧不得丢。
- **持久终态**：同上三节。
- **清理**：reader 为 daemon 线程，随父进程退出；无文件/网络副作用。
- **风险**：低—中。父在证据里保留最多 2×256KiB 内存字节（原为 0），仍在有界范围内。

## 3. 关键实现约束的满足方式（非"仅字符串/常量"证明）

| 要求 | 实现方式 | 定向检查 |
|---|---|---|
| 父 pytest collection 导入 fixture **不得**安装关闭 Popen 的 hook | guard 只在 fixture 的 `__main__` 注册；产品 import 改为惰性 `product()` | `test_the_fixture_import_installs_no_process_guard`（用 `sys.audit('subprocess.Popen',…)` 探针：fixture 的 `FixtureBoundaryViolation` 一旦出现即 `pytest.fail`）；`test_the_product_import_of_the_fixture_needs_the_guard`（`__name__='__main__'` 且无 guard → `SystemExit('FIXTURE_GUARD_MISSING')`）；`test_the_child_entry_installs_the_guard_before_the_product`（执行真实 `__main__` 块，调用序必须 `['guard','main']`） |
| 子进程入口仍须在**任何产品导入前**装自己的网络/后代禁用 guard | `if __name__ == '__main__': install_boundary_guard()` 在 `main()` 之前；`product()` 在 `__main__` 下缺 guard 即拒 | 同上三例 + runner 的 `hook_install_count=1`、握手确认、`audit_hook_installed_before_product_import=True` |
| 不得关掉 guard 换绿 | guard 未被关闭、未被绕过、未被弱化；`BLOCKED_EVENTS` 未改 | `test_the_fixture_guard_refuses_the_blocked_events`（`os.fork`/`subprocess.Popen`/`socket.connect` 真拒，非边界事件不拒）+ runner `--mode guard` 四事件全拒 |
| 外层 pre-import guard 维持 | runner 未改；`source_unchanged_during_run=True`、`runner_unchanged_during_run=True` | 第 4 节 B/C 收据 |
| 生产路径而非单元常量 | 走真实 `Writer`/`SCENARIO_FUNCTIONS`/`ProtocolState`/`ParentSupervisor._consume_stdout` | 第 4 节 A/C |

### E. 基线对照（同样的探针打旧候选 01453ee 的源，零进程）

```
git show 01453ee:.../tools/v0_s3_supervisor.py            > /tmp/lvw-s3-stream-baseline-01453ee/tools/v0_s3_supervisor.py
git show 01453ee:.../tools/fixtures/v0_s3_supervisor_fixture.py > /tmp/lvw-s3-stream-baseline-01453ee/tools/fixtures/…
python3 -I reports/.../implementation-integration-stream-correction-01/stream_baseline_probe.py /tmp/lvw-s3-stream-baseline-01453ee
```
真实外层 returncode = **0**；工件 `stream-baseline-probe-01.stdout.log`（stderr 空）。实测基线：
- `nonfinite_number`：**270 字节，`ends_with_newline=false`** → 那条 NaN 行**从来不是完整 JSONL 帧**，
  父侧不会解码 → 落到 phase deadline（与 final04 一致）。
- `message_flood`：**1201 帧 / 356940 字节 > 262144** → **字节预算先到**，消息数永远到不了 1024。
- `supervisor`：`has_stream_failure_detection=false`、四个稳定码 `[]` → 生产父**从不**察觉 reader 的
  overflow/error，只能等 10800s 兜底。
对照本候选（第 2/3 节）：1025 帧 / 252162B ≤ 262144、`ends_with_newline=true`、四个稳定码在位。

## 4. 实际执行的命令、真实外层退出与工件

外层重定向文件名与 runner 自身日志文件名**全部不同**（`*.outer.stdout.log` vs `*.stdout.log`）。

### A. 零进程 wire 探针（真实代码计算，无进程/无网络/无 ledger）

```
python3 -I reports/v0-s3/product-gate0/implementation-integration-stream-correction-01/stream_wire_probe.py
```
真实外层 returncode = **0**；工件 `stream-wire-probe-01.stdout.log`（stderr 空）。实测值见 2.2：
`{"frames":1025,"total_bytes":252162,"longest_frame_bytes":338,"inside_byte_caps":true,…}`，
长身份 `total_bytes=269587`（越界），`fixture_guard_installed_in_this_process=false`。

### B. runner guard 自检（`--mode guard`，不启动真实进程）

```
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode guard \
  --label stream-correction-guard-01 --outdir reports/v0-s3/product-gate0/implementation-integration-stream-correction-01
```
真实外层 returncode = **0**；`stream-correction-guard-01.stdout.log`：`connect`/`bind`/`Popen`/`system` 四项
全部 `offline boundary violation: …`（拒绝发生在审计事件、fork 之前，**未创建任何进程**）；
`cleanup_proven=true`、`owned_root_removed=true`、`machine_binding_present=false`（未碰 counter/ledger）。

### C. 外层 guard 之下的定向零进程检查（`--mode focused`，无 binding → 不启动进程）

```
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode focused \
  --label stream-correction-focused-02 --modules tools/test_v0_s3_supervisor.py --select <expr> \
  --outdir reports/v0-s3/product-gate0/implementation-integration-stream-correction-01
```
（`--select` 原文见 `stream-correction-focused-02.select.txt`）真实外层 returncode = **0**；
runner 日志 `stream-correction-focused-02.stdout.log`：**`30 passed, 5 skipped, 100 deselected`**。5 skipped 全部是
"the finite fixture process machine gate is not bound by the root"，即被本 select 命中的 5 个**真实进程场景**
（`[oversize_message-MESSAGE_TOO_LARGE]`、`[foreign_identity-MESSAGE_RUN_ID_MISMATCH]`、
`[unexpected_field-MESSAGE_KEY_SET_INVALID]`、`[nonfinite_number-MESSAGE_NONFINITE_NUMBER]`、
`[message_flood-MESSAGE_COUNT_EXCEEDED]`）在无 root 机器绑定时被正确跳过——这 5 个**期望码一字未改**
（`MESSAGE_NONFINITE_NUMBER` 与 `MESSAGE_COUNT_EXCEEDED` 仍是旧期望，不是改成 timeout 过关）。
收据：`exit_code=0`、`outcome=PASS`、`cleanup_proven=true`、`owned_root_removed=true`、
`admitted_attempts=0`、`child_handles_obtained=0`、`fixture_process_starts=0`、
`machine_binding_present=false`、`source_unchanged_during_run=true`、`runner_unchanged_during_run=true`、
`guard.hook_install_count=1`、`handshake_confirmed=true`、`audit_hook_installed_before_product_import=true`、
`host_subprocess=blocked`。
`stream-correction-focused-01.*` 为修正前的一轮（代码未改时），保留为证据。

### D. 受影响模块全量回归（`tools/test_v0_s3_supervisor.py`）

```
python3 -m pytest tools/test_v0_s3_supervisor.py -p no:cacheprovider -q
```
- `stream-correction-module-02.outer.*`：真实外层 returncode = **0**，`121 passed, 14 skipped in 70.95s`
  （14 skipped = 14 个需 root 机器绑定的场景测试，未获绑定前不得执行）。
- `stream-correction-module-01.outer.*`：真实外层 returncode = **1**，
  `1 failed, 120 passed, 14 skipped` —— **失败被保留**（未清理、未改写）：它抓出了本实现的一个真实竞态
  （父在 reader 读到越界字节**之前**就因 TERMINAL 跳出循环 → 假成功），已由 `_drain_streams()` 修正，
  并由 A/C/D 三轮复跑确认。

### E. 新增的零进程定向检查清单（19 项，全部通过）

| 检查 | 覆盖 |
|---|---|
| `test_the_fixture_import_installs_no_process_guard` | 父 collection 导入不装 hook（审计探针） |
| `test_the_fixture_guard_refuses_the_blocked_events` | 子 guard 真实拒绝网络/后代 |
| `test_the_product_import_of_the_fixture_needs_the_guard` | 缺 guard 即拒绝产品导入 |
| `test_the_child_entry_installs_the_guard_before_the_product` | `__main__` 顺序 guard→main |
| `test_the_nonfinite_frame_is_complete_and_is_refused` | NaN 帧**先证明完整**再被拒 |
| `test_the_parent_refuses_the_nonfinite_frame_on_a_real_pipe` | 父真实读路径拒 NaN 帧 |
| `test_the_message_count_negative_case_fits_the_frozen_byte_caps` | 1025 帧/252162B/≤32KiB，1024 合法、第 1025 条计数拒 |
| `test_the_parent_accepts_exactly_the_message_limit` | 恰好 1024 合法且 TERMINAL 仍核验通过 |
| `test_the_parent_refuses_the_one_over_message_count` | 父真实读路径计数拒，字节未抢先 |
| `test_the_stdout_stream_at_the_exact_cap_is_not_refused` | stdout 恰好 262144B 不拒 |
| `test_the_parent_refuses_an_overlong_stdout_stream` | stdout 262145B → `STDOUT_STREAM_LIMIT_EXCEEDED` |
| `test_the_stderr_stream_at_the_exact_cap_is_not_refused` | stderr 恰好 262144B 不拒 |
| `test_the_parent_refuses_an_overlong_stderr_stream` | stderr 262145B → `STDERR_STREAM_LIMIT_EXCEEDED` |
| `test_the_parent_refuses_a_failing_stdout_reader` | → `STDOUT_STREAM_READ_FAILED` |
| `test_the_parent_refuses_a_failing_stderr_reader` | → `STDERR_STREAM_READ_FAILED` |
| `test_a_terminal_with_a_stream_overflow_is_not_a_success` | 同批 TERMINAL 不掩盖失败、不假成功 |
| `test_the_blocking_partial_frame_stays_incomplete` | 故意不完整帧仍不是消息 |
| `test_the_frozen_caps_of_the_protocol_are_unchanged` | 1024/32KiB/256KiB 与四个稳定码未变 |
| （原协议 Oracle 12 项 + 期限/收据/根保留等既有项） | 由 `stream-correction-module-02` 的 121 passed 覆盖 |

方法约束：只用 `os.pipe` + 线程 + 受控 fake reader/handle 驱动**真实** `Writer`、真实场景函数、真实
`ProtocolState`、真实 `ParentSupervisor` 读路径；**未启动任何 OS 子进程/fixture、未联网、未用
模型/GPU/服务、未访问原 ledger**（runner 收据 `fixture_process_starts=0`、`machine_binding_present=false`）。
新测试连跑 5 轮（每轮 `19 passed, 1 skipped`）无抖动。

## 5. 未完成 / 明确不做

1. **新候选的真实 13 场景 fixture 复验未执行**：本轮无机器绑定、无预算授权，且旧 pool
   `reserved 180/180、starts 15、spent 8.446、3×SETTLED、active=false` 未被本实现者改动（未退款、未清零、
   未新开 counter）。真实复验须由 root 依据 COMPLETE03 另行裁决有限机器预算并重新封存 11 个 source pin
   （本轮三个源文件 hash 已变，见第 1 节）。**不得**从 `spent 8.446` 反推可退 171s。
2. **不签 StagePASS、不签 product_gate0**：本报告只报 `READY_FOR_REVIEW`；旧 11 PASS/2 FAIL 只属旧候选
   `01453ee`，新候选的真实 13 PASS 尚未取得。
3. 未改 executor/runner、未改公共合同/门限/固定 24/坐标 MANIFEST/V2、未动其余 production owner。
4. 未清理旧工件：旧 `implementation-integration-01/report.md` 的既有修改与全部失败/未跟踪工件原样保留，
   未 `git add` 全量。

## 6. 工件清单（本目录）

| 文件 | 说明 |
|---|---|
| `report.md` | 本报告 |
| `stream_wire_probe.py` | 零进程 wire 探针（真实代码计算） |
| `stream-wire-probe-01.stdout.log` / `.stderr.log` | 探针真实输出（stderr 空） |
| `stream_baseline_probe.py` | 基线对照探针（打旧候选 01453ee 的源） |
| `stream-baseline-probe-01.stdout.log` / `.stderr.log` | 基线实测输出（stderr 空） |
| `stream-correction-guard-01.*` | runner `--mode guard` 自检（外层 `*.outer.*` 与 runner `*.stdout.log` 分名） |
| `stream-correction-focused-01.*` | 修正前的外层 guard 定向轮（保留） |
| `stream-correction-focused-02.*` | 修正后的外层 guard 定向轮（30 passed / 5 skipped，外层 rc=0） |
| `stream-correction-module-01.outer.*` | **保留的失败轮**：外层 rc=1，暴露 TERMINAL/overflow 竞态 |
| `stream-correction-module-02.outer.*` | 受影响模块全量回归：外层 rc=0，121 passed / 14 skipped |
