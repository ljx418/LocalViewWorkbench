# S3-P4 final04 exact13 fixture execution report

标签：`finite-fixture-implementation-04`；角色：`implementation`；候选：`01453ee07b4774a55711c5cf5642c12d0394a35c`。
结论：**真实执行 FAIL（13 项中 11 PASS / 2 FAIL / 0 SKIP / 0 未执行），外层真实 returncode=1**。不签 StagePASS，product_gate0=false。
本轮只执行一次 `decision.argv`；真实 FAIL 不补跑。

## 1. 执行前只读核验（全部相符才执行）

| 项 | 要求 | 实测 | 结果 |
|---|---|---|---|
| HEAD | 01453ee07b4774a55711c5cf5642c12d0394a35c | worktree `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement` HEAD=01453ee | 相符 |
| 11 个 source pins | binding 内 11 条 sha256 | 11/11 相符（运行后再核一次仍 11/11 相符） | 相符 |
| Python | /usr/bin/python3.12 = e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f | 相符（8020928 bytes） | 相符 |
| 新 binding sha256 | cd98fcaf6d4324259cccb5836b43e8d99a09a971badaeadcc20b80d5236a66f9 | 相符 | 相符 |
| 继承的 retry 变量 | 0 / 0 | `CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0` | 相符 |
| counter | active=true / starts2 / reserved120 / spent2.896 / 2×REFUSED_BEFORE_FORK / 2×SETTLED | 完全相符（budget_id s3-p4-9618f7c7bf12403b8877c90b92ed99a7） | 相符 |
| env-only 临时设置 | 只读，不删除不恢复 | `.claude/settings.local.json` sha256=7e6320a5…8010c1b0，root 建于 worker_done 前，**worker 未删除未修改**，由 root 按 hash 恢复 | 相符 |

执行目录为承载被 pin 的 runner 与 fixture 的包目录
`/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`：
`decision.argv` 的相对路径 `reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py`
只在该目录存在（`/mnt/c/...` 主 checkout 的 HEAD=7d5ccb6 不含候选代码与 runner），
且新 binding 的 `argv_prefix` 本身就指向该 worktree 的 fixture 路径。

## 2. 实际执行（一次，原样，未包装、未循环、未改 argv/审批配置）

```
/usr/bin/python3.12 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
  --mode suite --label finite-fixture-implementation-04 \
  --binding /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation-final-04.binding.json \
  --binding-sha256 cd98fcaf6d4324259cccb5836b43e8d99a09a971badaeadcc20b80d5236a66f9 \
  --role implementation --candidate-sha 01453ee07b4774a55711c5cf5642c12d0394a35c \
  --modules tools/test_v0_s3_supervisor.py::test_the_fixture_clean_terminal_is_verified_by_the_parent,\
tools/test_v0_s3_supervisor.py::test_a_blocking_callback_is_actually_stopped,\
tools/test_v0_s3_supervisor.py::test_a_blocking_persistence_is_actually_stopped,\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[history_replay-MESSAGE_HISTORY_STARTED_REPEATED],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[sequence_reversal-MESSAGE_SEQUENCE_NOT_INCREASING],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[duplicate_sequence-MESSAGE_SEQUENCE_NOT_INCREASING],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[oversize_message-MESSAGE_TOO_LARGE],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[foreign_identity-MESSAGE_RUN_ID_MISMATCH],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[unexpected_field-MESSAGE_KEY_SET_INVALID],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[nonfinite_number-MESSAGE_NONFINITE_NUMBER],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[early_exit-WORKER_EXITED_WITHOUT_TERMINAL],\
tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[message_flood-MESSAGE_COUNT_EXCEEDED],\
tools/test_v0_s3_supervisor.py::test_a_bad_terminal_reference_is_refused \
  --outdir reports/v0-s3/product-gate0/implementation-integration-01
```

外层真实 returncode = **1**（runner 自身 exit_code=1，outcome=FAIL）。
外层 stdout 字节与 runner receipt 完全一致（JSON 可解析，逐字段相同）。

## 3. 逐 13 node 结果（collected_count=13）

| # | nodeid | 结果 | charge | 子进程终态 | exit | 存活(s) |
|---|---|---|---|---|---|---|
| 1 | test_the_fixture_clean_terminal_is_verified_by_the_parent | PASSED | 2 clean_terminal | STOPPED | 0 | 0.079 |
| 2 | test_a_blocking_callback_is_actually_stopped | PASSED | 3 blocking_callback | STOPPED | -15 | 1.036 |
| 3 | test_a_blocking_persistence_is_actually_stopped | PASSED | 4 blocking_persistence | STOPPED | -15 | 1.031 |
| 4 | test_a_protocol_violation_is_refused[history_replay-…] | PASSED | 5 history_replay | STOPPED | -15 | 0.082 |
| 5 | test_a_protocol_violation_is_refused[sequence_reversal-…] | PASSED | 6 sequence_reversal | STOPPED | -15 | 0.082 |
| 6 | test_a_protocol_violation_is_refused[duplicate_sequence-…] | PASSED | 7 duplicate_sequence | STOPPED | -15 | 0.081 |
| 7 | test_a_protocol_violation_is_refused[oversize_message-…] | PASSED | 8 oversize_message | STOPPED | -15 | 0.080 |
| 8 | test_a_protocol_violation_is_refused[foreign_identity-…] | PASSED | 9 foreign_identity | STOPPED | -15 | 0.081 |
| 9 | test_a_protocol_violation_is_refused[unexpected_field-…] | PASSED | 10 unexpected_field | STOPPED | -15 | 0.081 |
| 10 | test_a_protocol_violation_is_refused[nonfinite_number-MESSAGE_NONFINITE_NUMBER] | **FAILED** | 11 nonfinite_number | STOPPED | -15 | 1.070 |
| 11 | test_a_protocol_violation_is_refused[early_exit-…] | PASSED | 12 early_exit | STOPPED | 0 | 0.089 |
| 12 | test_a_protocol_violation_is_refused[message_flood-MESSAGE_COUNT_EXCEEDED] | **FAILED** | 13 message_flood | STOPPED | -15 | 1.078 |
| 13 | test_a_bad_terminal_reference_is_refused | PASSED | 14 bad_terminal_reference | STOPPED | -15 | 0.092 |

pytest 摘要：`2 failed, 11 passed in 5.43s`；进度串 `.........F.F.` 13 位对应上表，**0 skip、0 未执行**。

两项 FAIL 的断言差异：`PHASE_DEADLINE_EXCEEDED` ≠ 期望的 `MESSAGE_NONFINITE_NUMBER` / `MESSAGE_COUNT_EXCEEDED`。

## 4. 两项 FAIL 的实际成因（代码级只读定位，非猜测）

- `nonfinite_number`：fixture 的 `scenario_nonfinite_number` 用 `Writer.write_raw()`，写出 JSON 行时**不追加 `b"\n"`**（`Writer.write()` 才追加）。父侧 `_consume_stdout` 以 `b"\n"` 切分协议行，因此该行永远不成行、永远不被 `decode_message` 解码，`json.loads(parse_constant=_reject_constant)` 从不执行，`MESSAGE_NONFINITE_NUMBER` 不产生；父等到 1.0s 缩尺 phase 截止 → `PHASE_DEADLINE_EXCEEDED`。
- `message_flood`：该场景写 1200 条 PROGRESS 行，每行 300 字节，合计 360000 字节，超过 `MAX_STREAM_BYTES=262144`；`_StreamReader` 在约第 873 条后 overflow 停止读取，**早于**协议条数上限 `MAX_MESSAGES=1024` 被触及，故 `MESSAGE_COUNT_EXCEEDED` 不产生；同样落到 1.0s phase 截止 → `PHASE_DEADLINE_EXCEEDED`。

两者均为候选侧 fixture 场景与冻结 supervisor 合同之间的确定性不匹配，**不是时序抖动，也不是预算窗口影响**（整轮 5.43s，落在 30s admission 窗口内；两个失败子进程存活 ~1.07s，恰为 fixture 的 1.0s 缩尺 phase 截止）。本执行者不改代码、不补跑。

## 5. 进程/预算/账务/清理

- admitted_attempts=13，child_handles_obtained=13，proven_child_handles=13，charges_without_handle=[]，admission_refusals=0。
- 13 条 charge 全部 settled=true 且终态已持久化（2 STOPPED/exit0，11 STOPPED/exit-15；每条带 pid+birth），settlement_failures=[]，session uncertain=false。
- session `session-6b8a5e40c8d4383821e8ddaecbf6f919`：reserve 60s = admission 30s + cleanup 60s（cleanup_deadline = admission+60），state=SETTLED，spent=5.55s，remaining_before=60s；旧两次 admit 计数保留。
- counter 累计：**3 个 session**（前 2 个 SETTLED + 本轮 SETTLED）；starts_total 2→**15**；starts_by_role.implementation 2→**15**（≤16）；reserved_wall_seconds 120→**180**（原池已满，无新池）；spent_wall_seconds 2.896→**8.446**；旧 charge 0/1（REFUSED_BEFORE_FORK）与历史 reconciliation 事件原样保留。
- 清理：cleanup_proven=true，failure_reasons=[]，runner owned root `/tmp/lvw-s3-integration-u0nm59ym` 已移除且复验不存在；源 11 pin 运行前后不变、runner 自身不变（source_unchanged_during_run=true，runner_unchanged_during_run=true）。
- guard：pytest 之前安装审计钩子，hook_install_count=1，install_attempts=1，握手确认，network=blocked，host_subprocess=bound_fixture_plan_only；无生产 quality_worker / Pillow 子进程、无模型/GPU/服务/网络/媒体、无原 ledger 访问，公共合同/固定 24/产品 12 未改。
- HEAD 未变（01453ee），本执行者未提交、未改代码；旧 report.md 的既有未提交修改与全部失败/未跟踪工件（01/02 序列、blocked-01.md 等）原样保留，未清理、未重写。

## 6. 工件

| 文件 | 说明 |
|---|---|
| `finite-fixture-implementation-04.receipt.json` | runner 自产收据（FAIL, exit 1, cleanup_proven） |
| `finite-fixture-implementation-04.stdout.log` / `.stderr.log` | runner 自身日志（pytest 输出；stderr 空） |
| `finite-fixture-implementation-04.outer-execution.json` | 独立外层工件：完整实际命令、真实外层 returncode、时间戳、各工件 hash、逐 node 结果、进程计数、结算与清理、counter 累计、失败成因 |
| `finite-fixture-implementation-04.node-results.json` | 逐 13 node 结果与 charge 终态 |
| `finite-fixture-implementation-04.outer.stdout.log` / `.outer.stderr.log` | 外层 stdout/stderr（与 runner 自身日志不同名） |
| `finite-fixture-implementation-04.outer.argv.txt` / `.outer.start.txt` / `.outer.end.txt` / `.outer.returncode.txt` | 实际 argv 与外层时间戳/returncode 原件 |

外层工件同名副本同时放在 root 主包 `reports/v0-s3/product-gate0/fixture-final-04/`（新增文件，未覆盖任何旧件），便于 root 独立复算。
