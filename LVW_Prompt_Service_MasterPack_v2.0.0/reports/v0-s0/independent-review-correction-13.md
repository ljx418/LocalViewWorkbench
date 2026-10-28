# V0-S0 / WP-S0-39 correction-13 独立离线复审

审查日期：2026-10-28（Asia/Shanghai）
审查角色：`codex_isolated_reviewer`
冻结 packet：`e37c0f797267ea3e43aba01a1960d553568237bd`
候选实现：`12527cdb01b889995089c16c8afb5956cbfdd15d`
gate-owner seal/checkpoint：`f01c8c520c9fbe141f70b53792600c1c560218a2`

审查方式：离线独立复算、静态数据流搜索及临时目录 mock fixture；未启动或探测 ComfyUI/Ollama，未访问网络或真实媒体，未修改候选、manifest、坐标或历史 evidence。

## 结论

Fatal **0** / Major **1** / Minor **0**

correction-13 已建立唯一的 cleanup proof 公式，cleanup artifact、run summary、request trace、receipt cleanup 与 cleanup check 都直接读取同一个 `self.cleanup["proven"]`。captured PID stop-after 非空时 proof/check 正确失败；干净终态和 proof=true 蕴含不变量也成立；Popen 与 NOT_REACHED 回归通过。

但是，额外的绕过路径搜索发现顶层运行决策没有消费这项权威 proof。若图片/视频路径本身成功，而 captured owned PID 在 stop 后仍存在，artifact 与 check 会正确写 cleanup FAIL，但顶层 `decision` 仍可保持 `READY_FOR_REVIEW`、进程退出码仍为 0，production status 仍写 complete。因而“单一 proof 权威”尚未成为运行出口权威，离线纠偏不能建议结束。

## Finding

### M-01 — Major — cleanup proof=false 未阻断 READY_FOR_REVIEW 与 exit 0

- **位置**：`tools/v0_s0_live_probe.py:1002-1008,1102-1121,1145-1163,1252`；`tools/test_v0_s0_live_probe.py:416-449`。
- **触发**：图片与视频 attempt 都成功，使 try 主路径先设置 `decision=READY_FOR_REVIEW`；finally 中 captured run-owned PID 的 `stop_owned().after` 非空，其余 Popen、端口、temp、integrity 和 secondary 状态干净。
- **预期**：权威 `cleanup.proven=false` 必须阻止 READY_FOR_REVIEW、complete production status 与 exit 0；顶层应 fail-closed 为 NO_GO，cleanup check 为 FAIL。
- **实际**：权威公式正确导出 absence=false、proof=false，check 也为 FAIL；但 finally 中改变顶层 decision 的条件仍自行检查 `secondary_cleanup_failures/final_ports/temp/integrity mismatch`，没有读取 `self.cleanup["proven"]` 或 `owned_resources_absent`。stop-after 非空且 secondary 为空时不会触发该条件，既有 READY_FOR_REVIEW 被保留，`return 0 if decision == READY_FOR_REVIEW` 也返回 0。
- **独立证据**：完整临时 `Probe.run()` fixture 模拟 identity/preflight/no-cloud/network/path 与图片、视频均成功，request cleanup correlation 成功；设置正常退出 Popen、captured wrapper PID=123，并令精确 `stop_owned(123)` 返回 `after=[{"Id":123}]`。实际输出：`owned_resources_absent=false`、`cleanup_proven=false`、`cleanup_check=FAIL`，同时 `decision=READY_FOR_REVIEW`、`rc=0`、`stage_pass_claim=false`。这不是 Stage PASS，但会把 cleanup 失败包装为可供复审的成功运行出口。
- **复现**：在 pack 根目录导入 `tools.v0_s0_live_probe`；用临时目录构造 Probe，mock 两个 public attempts PASS、request trace cleaned=true、listeners=[]、target integrity 前后相等、Popen 正常退出；仅让 captured wrapper PID 的 stop-after 非空。执行 `run()`，比较 receipt decision、cleanup/check 与返回码。全程不启动服务、不访问网络或媒体。
- **建议**：finally 完成权威 proof 后，以 `if not self.cleanup["proven"]` 作为成功出口的统一阻断条件；若已有 primary stop 则保留首因并记录 secondary cleanup failure，否则置 NO_GO/稳定 cleanup stop reason。新增“功能成功 + proof=false”完整 run fixture，断言 decision 非 READY、production status 非 complete、rc 非 0。

## 权威公式与消费者复算

- `derive_cleanup_proven()` 唯一公式为 `owned_resources_absent AND target_integrity_comparison == "PASS" AND secondary_cleanup_failures empty`；生产代码仅调用一次。
- `self.cleanup["proven"]` 在公式计算后与终态子状态一起写入 cleanup artifact；没有第二次生产公式计算。
- run summary、request trace、receipt cleanup 字段和 `observable_check_statuses()` 均直接读取该字段；静态搜索没有发现平行 proof 计算。
- M-01 是公式之外的出口绕过：顶层 decision/return/production status 没有把权威 proof 当作必要条件。

## 终态分支与不变量

- captured PID `after` 非空：absence=false、proof=false、cleanup check=FAIL；关闭 correction-12 的字段矛盾。
- captured PID `after=[]`、两个 Popen 退出、listeners/temp 无残留、integrity PASS、secondary=[]：absence=true、proof=true、cleanup check=PASS。
- 公式不变量五组独立输入复算一致：proof=true 只在 `(true, PASS, [])`；absence=false、integrity FAIL/NOT_REACHED 或任一 secondary failure 均为 false。
- lingering Popen、wait exception、双 Popen 任一未退出的 37 项历史回归仍通过；identity/preflight 零启动后的 NOT_REACHED 与 reached failure=FAIL 无回归。

## 测试与可复现结果

- `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：40/40 PASS，包含原 37 项、captured residual、clean terminal 与公式不变量。
- AST parse、`--help`、`--self-check`：全部 exit 0；self-check 明确 `service_started=false`。
- `python3 -B tools/verify_pack.py --schema`：1077/0；不是产品验收。
- `python3 -B tools/verify_governance.py`：38/0；`--self-test`：43/0，均明确 `product_tests_executed=false`。
- Stage payload manifest 9/9、root manifest 全项 SHA-256 通过。
- 独立成功路径绕过 fixture 稳定复现 M-01；没有任何真实外部动作。

## 候选、receipt、manifest 与 packet 绑定

- 提交链为 `e37c0f7...` → `12527cd...` → `f01c8c5...`。候选相对冻结 packet 只修改两个 harness 文件并新增 correction-13 offline receipt；changed_files 3/3 与 diff 精确一致，diff 无 whitespace error。
- candidate receipt 使用 pending 零值；gate-owner seal 才绑定 candidate/evidence=`12527cd...`，并更新 packet/control、execution-control、root manifest 和治理校验，没有实现者自签。
- 两个工具独立 SHA-256 为 `97d9b1c10cd488dba7bdb5c0ce1d171d8a90c74611657655e5c45e1a70aece37`、`c9c26357f4e8fdeb647e84df5641bc335c33a61ebf697b6de5bf44e8074509cb`，与 receipt、candidate Git blob、当前文件和 root manifest 一致。
- frozen packet、baseline harness、sealed candidate/evidence、角色、测试计数与 acceptance binding 均闭合。固定 acceptance hash 独立复算仍为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。

## 历史、外部动作与固定分母

- frozen packet、candidate、seal 三个提交中的 correction-10 tree 均为 `bb899d4ca0818c84293dab00fd1a1ed8f2c464c7`。
- correction-11 receipt/review blobs 始终为 `8174a6c874832569ed7fb3bf5f0489486514de35` / `7cbc6193339bf5bea515061513a4ada65f314078`；correction-12 receipt/review blobs始终为 `4694ee1a095e20bf8f1db63cb3817388e2f5777e` / `1b1a62b02b8986e1438b20a75e5dfb8303e58678`。历史未改写。
- correction-13 receipt 和本次复审记录 Comfy/Ollama starts、service probes、network/model calls、真实媒体读取、下载及 target writes 全为 0。
- `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 全部保持 `NOT_RUN`；分母 4、not_run 4，其余计数 0。40 个 fixture 与治理/manifest PASS 不是产品 PASS。

## 审查意见与限制

- **假绿判断**：proof 与 cleanup check 本身已 fail-closed，但 M-01 允许顶层 READY_FOR_REVIEW/exit 0 绕过 proof，仍构成运行出口假绿。
- **WP-S0-37/38 意见**：不建议通过 READY_FOR_REVIEW checkpoint；需让顶层 decision、production status 与返回码消费权威 proof，并补成功路径负例后再复审。
- **S0 状态建议**：不得 Stage PASS、不得推断 live 授权。即使离线 Major 清零，也只能返回 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并释放未知 GPU owner；真实运行仍需新授权。
