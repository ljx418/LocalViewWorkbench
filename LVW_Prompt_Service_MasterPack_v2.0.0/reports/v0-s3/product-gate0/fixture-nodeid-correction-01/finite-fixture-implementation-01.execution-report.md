# 有限 fixture 执行报告 01（用户批准的单次直接尝试）

状态：**真实执行已发生一次，结果 FAIL；13 项固定 node 未取得任何通过证据；不补跑。**
本轮不宣布 Stage PASS、不宣布产品 Gate0、不宣布人工签署，**不把未执行/未通过当作通过**，
不降 24 项固定义务分母。本文件只记录事实与原始收据。

## 授权与范围

* 用户明确批准：`reports/v0-s3/product-gate0/integration-fixture-explicit-retry-01.approval.json`
  （`EXPLICIT_USER_SINGLE_DIRECT_RETRY_APPROVAL`，`allowed_attempts: 1`）。
* root STEP2 ACK：`msg_574a40474c8e`；root 记录
  `reports/v0-s3/product-gate0/orca-cleanup-02/continuation.step2-grant.json`。
* 候选：`763f3d561772ec8efa7aafe597b62ac77a3b7969`（HEAD，未改动）。
* 绑定：`/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation.binding.json`
  sha256 `3594b3a30d12e1fbfe54d71118d06b996a5e21872679e4af25bc9818d41dfee1`
  （运行前后复算一致），kind `S3_INTEGRATION_MACHINE_BINDING/1`，`execution_permitted=true`。
* Python：`/usr/bin/python3.12` sha256
  `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`，8020928 bytes。
* 11 项 source pin 运行前后逐个 sha256 复算一致（`before_source_sha256` ==
  `after_source_sha256`，且等于绑定内 pin 值）；`runner_sha256_before` ==
  `runner_sha256_after` == `31ab0956e6e643771258b58f51097babe5f808e024183f39a471e95bd8c6d036`。
* 共享 counter：`/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`，
  `budget_id s3-p4-9618f7c7bf12403b8877c90b92ed99a7`；执行前 root 已恢复
  `active=true`、`starts_total=0`、`charges=[]`、`sessions=[]`、`reserved/spent=0`。

## 实际执行的命令（原样一次，无脚本包装、未改审批配置）

```text
/usr/bin/python3.12 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
  --mode suite --label finite-fixture-implementation-01 \
  --binding /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/implementation.binding.json \
  --binding-sha256 3594b3a30d12e1fbfe54d71118d06b996a5e21872679e4af25bc9818d41dfee1 \
  --role implementation --candidate-sha 763f3d561772ec8efa7aafe597b62ac77a3b7969 \
  --modules "tools/test_v0_s3_supervisor.py::test_the_fixture_clean_terminal_is_verified_by_the_parent,tools/test_v0_s3_supervisor.py::test_a_blocking_callback_is_actually_stopped,tools/test_v0_s3_supervisor.py::test_a_blocking_persistence_is_actually_stopped,tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[history_replay],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[sequence_reversal],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[duplicate_sequence],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[oversize_message],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[foreign_identity],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[unexpected_field],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[nonfinite_number],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[early_exit],tools/test_v0_s3_supervisor.py::test_a_protocol_violation_is_refused[message_flood],tools/test_v0_s3_supervisor.py::test_a_bad_terminal_reference_is_refused" \
  --outdir reports/v0-s3/product-gate0/implementation-integration-01
```

## 执行结果（原始事实）

| 项目 | 值 |
|---|---|
| 真实命令退出码 | **4**（pytest usage error） |
| 收据 `outcome` | **FAIL** |
| 收据 `duration_seconds` | 0.714 |
| stdout | `no tests ran in 0.53s`（23 bytes） |
| stderr | 2467 bytes，9 条 `ERROR: not found: ...` |
| 收集到的 node | `collected_count=0`，`collected_nodeids=[]` |
| fixture 进程启动数 | **0**（`fixture_process_starts=0`，上限 24） |
| 真实产品/模型/账本动作 | 0（`real_execution_performed=false`，network blocked，无 GPU/原账本） |
| 会话 | `session-5cc6f255f8b579ae5cb94931d71379eb`，role implementation，`state=SETTLED` |
| 清理 | `cleanup_proven=true`，`owned_root_removed=true`，`admissions_revoked=true` |
| guard | audit hook 在产品导入与 pytest 之前安装；network blocked；`subprocess.Popen/os.system/os.exec/…` 已阻断；bytecode 未写入；cacheprovider disabled |
| 失败原因字段 | `failure_reasons=[]`、`refusals=[]`、`uncertain=false` |

### 精确 13 节点逐项结果

| # | 冻结 nodeid | 结果 |
|---|---|---|
| 1 | `test_the_fixture_clean_terminal_is_verified_by_the_parent` | 未执行（pytest 因 9 条 not found 整体 usage error 中止，`collected_count=0`） |
| 2 | `test_a_blocking_callback_is_actually_stopped` | 同上，未执行 |
| 3 | `test_a_blocking_persistence_is_actually_stopped` | 同上，未执行 |
| 4 | `test_a_protocol_violation_is_refused[history_replay]` | **not found**（stderr 第 1 条） |
| 5 | `…[sequence_reversal]` | **not found**（第 2 条） |
| 6 | `…[duplicate_sequence]` | **not found**（第 3 条） |
| 7 | `…[oversize_message]` | **not found**（第 4 条） |
| 8 | `…[foreign_identity]` | **not found**（第 5 条） |
| 9 | `…[unexpected_field]` | **not found**（第 6 条） |
| 10 | `…[nonfinite_number]` | **not found**（第 7 条） |
| 11 | `…[early_exit]` | **not found**（第 8 条） |
| 12 | `…[message_flood]` | **not found**（第 9 条） |
| 13 | `test_a_bad_terminal_reference_is_refused` | 未执行（整体中止） |

即：**13 项全部没有通过证据**；9 项的 id 不匹配，另外 4 项因 pytest 整体中止未运行。
没有任何一项为 PASS，也没有一项被判为 SKIP。

### 失败的直接原因（静态核对，非推测）

`tools/test_v0_s3_supervisor.py` 的参数化装饰器为：

```python
@pytest.mark.parametrize('scenario,code', [
    ('history_replay', 'MESSAGE_HISTORY_STARTED_REPEATED'),
    ('sequence_reversal', 'MESSAGE_SEQUENCE_NOT_INCREASING'),
    ('duplicate_sequence', 'MESSAGE_SEQUENCE_NOT_INCREASING'),
    ('oversize_message', 'MESSAGE_TOO_LARGE'),
    ('foreign_identity', 'MESSAGE_RUN_ID_MISMATCH'),
    ('unexpected_field', 'MESSAGE_KEY_SET_INVALID'),
    ('nonfinite_number', 'MESSAGE_NONFINITE_NUMBER'),
    ('early_exit', 'WORKER_EXITED_WITHOUT_TERMINAL'),
    ('message_flood', 'MESSAGE_COUNT_EXCEEDED'),
])
def test_a_protocol_violation_is_refused(tmp_path, scenario, code):
```

pytest 对多参数 `parametrize` 生成的 id 为 `<param1>-<param2>`，即
`test_a_protocol_violation_is_refused[history_replay-MESSAGE_HISTORY_STARTED_REPEATED]` 等。
冻结 argv / 绑定 `allowed_scenarios` 中写的是只含第一个参数的
`…[history_replay]`，两者不一致 → pytest 报 `no match in any of
[<Module test_v0_s3_supervisor.py>]` 并以 usage error（退出码 4）整体中止。

**这不是实现代码的失败，而是机器绑定中 nodeid 书写与 pytest 实际 id 的不一致。**
按约束，本实现者**不自行改写 nodeid、不自行重新绑定、不重跑**：nodeid 列表属于
绑定内容，改动即需 root 重新签绑定（并对应用户对新 argv 的授权）。

## 共享 counter 终态与清理

* counter 终态：`active=true`、`starts_total=0`、`starts_by_role{implementation:0,
  independent_review:0}`、`charges=[]`、`sessions` 仅 1 条且 `state=SETTLED`
  （`spent_wall_seconds=0.708`，`reserved_wall_seconds=60.0`，`finished_wall` 已写）、
  `spent_wall_seconds=0.708`。
* 即：**13 次 fixture 启动额度一次未用**（本轮没有真正启动任何 fixture 子进程）。
* 进程清理：`ps -ef` 无残留 `v0_s3_supervisor_fixture` / `pytest` /
  `run_guarded_checks` 进程；自有根 `/tmp/lvw-s3-integration-_u_ift1p` 已删除，
  `/tmp/lvw-s3-integration-*` 无残留；收据 `owned_root_removed=true`、
  `cleanup_proven=true`。

## 本轮产物（未提交，HEAD 未变）

| 文件 | sha256 |
|---|---|
| `finite-fixture-implementation-01.receipt.json` | `e8eccdcb18d53ceb773b8fde1bff52baebf7fd81eae322f7e5f504d33ae13ac8` |
| `finite-fixture-implementation-01.stdout.log` | `61f92d20eefd9496022ff5ccc59e14802f2207c843f938dc59708b5c14b8ebfb` |
| `finite-fixture-implementation-01.stderr.log` | `cca5fc86f63acec20820a5e80d5524c6e646c943b8c3a1d6532d084167ac8c97` |
| 本文件 | `finite-fixture-implementation-01.execution-report.md` |

HEAD 仍为 `763f3d561772ec8efa7aafe597b62ac77a3b7969`；`report.md` 的上一轮阻断报告
修改**原样保留未改**；上一轮 `finite-fixture-execution-blocked-01.md` 原样保留；
未跟踪工件未清理；未 `git add`、未提交。

## 需要 root 决策

1. 是否以修正后的 nodeid（补全第二个参数，例如
   `test_a_protocol_violation_is_refused[history_replay-MESSAGE_HISTORY_STARTED_REPEATED]`）
   重新签发绑定并重新授权一次；重新绑定须重新核对 11 pins / 候选 / python / counter。
2. 若不重跑：本批 13 项 fixture 进程证据状态为 **FAIL / 未取得**（不是 PASS、不是 SKIP），
   产品 Gate0 仍不开放，固定 24 义务不变。

## 明确不在本轮范围内（本轮均未执行）

生产 worker / Pillow 子进程、Windows 服务、GPU、A06、真实质量 12 项、发布签署、
原账本动作、网络访问。
