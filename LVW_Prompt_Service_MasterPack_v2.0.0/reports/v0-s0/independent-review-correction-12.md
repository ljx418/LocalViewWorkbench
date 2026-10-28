# V0-S0 / WP-S0-36 correction-12 独立离线复审

审查日期：2026-10-28（Asia/Shanghai）
审查角色：`codex_isolated_reviewer`
冻结 packet：`e9a45da095a50d2c54707d863c359c153476fe77`
候选实现：`000fa24ac62c414c8310a80bf721f4e39cfff049`
gate-owner seal/checkpoint：`73e7a2fd35de561009578517601e4d392719de42`

审查方式：离线独立复算与临时目录 mock fixture；未启动或探测 ComfyUI/Ollama，未访问网络或真实媒体，未修改候选、manifest、坐标或历史 evidence。

## 结论

Fatal **0** / Major **1** / Minor **0**

WP-S0-33 报告的 lingering-Popen M-01 已按冻结要求关闭：候选会把每个已赋值 Popen 作为一次 service start，记录 wait/poll/terminate/kill 终态；持续存活、wait timeout/异常及双 Popen 任一未退出都 fail-closed，正常退出才允许 Popen 子状态通过。terminate/kill 只调用传入的精确 run-owned Popen 对象。

但完整 run 独立 fixture 发现另一条既有 owned-resource 假绿：若按精确 captured PID 执行 `stop_owned()` 后，其 `after` 仍非空，而 Popen 已退出且端口、temp、target integrity 表面正常，候选会同时写 `owned_resources_absent=false` 与 `cleanup.proven=true`，并把 cleanup check 写成 `PASS`。这违反 correction-11 的状态分离语义，也意味着 correction-12 尚不能建议关闭离线纠偏。

## Finding

### M-01 — Major — captured owned PID 仍存活时 cleanup.proven 可与 absence 矛盾并假绿

- **位置**：`tools/v0_s0_live_probe.py:824-833,1088-1103,1142-1145,1175-1178,1224-1227`；`tools/test_v0_s0_live_probe.py` 未覆盖 `owned_process_stops[].after` 非空的完整 run 分支。
- **触发**：本 run 已捕获 wrapper/listener PID；`stop_owned()` 返回非空 `after`，说明停止后该精确 owned PID 仍可观察到；同时 Popen 已退出、final listeners 为空、temp 不存在、target integrity 前后相等且没有 secondary failure。
- **预期**：`owned_resources_absent=false` 必须使严格的 `cleanup.proven=false`，reached cleanup check 必须为 `FAIL`；不能一边承认 owned 资源仍存在，一边宣称清理已证明。
- **实际**：`owned_resources_absent` 正确包含 `all(not stop.get("after") for stop in stops)`，因此为 false；但 `summary.cleanup_proven` 只检查 listeners、temp、target integrity 与 secondary failures，没有检查 `owned_resources_absent` 或 `owned_process_stops.after`。`observable_check_statuses()` 接收该 true 后将 cleanup 写成 PASS。
- **独立证据**：纯离线完整 `Probe.run()` fixture 设置正常退出的 run-owned Popen、captured wrapper PID=123，并让精确 `stop_owned(123)` 返回 `after=[{"Id":123}]`；其他终态均干净。实际输出：`owned_resources_absent=false`、`cleanup.proven=true`、`cleanup_check=PASS`、`secondary=[]`，且 cleanup artifact 保留非空 persistent stop-after。总体 rc=2/NO_GO 只来自模拟的 no-cloud 首因，不消除清理子结论假绿。
- **复现**：在 pack 根目录导入 `tools.v0_s0_live_probe`，用临时目录构造完整 Probe；mock identity/preflight PASS、target integrity 前后 `[]`、listeners `[]`、run temp 不存在；在 `start_services` 赋值正常退出 Popen 与一个 captured wrapper PID，随后模拟 reached no-cloud failure；令 `stop_owned` 仅对该 PID 返回非空 `after`。执行 `run()` 并比较 receipt 的三个 cleanup 字段。全程不启动服务、不访问网络或媒体。
- **建议**：只计算一次严格 cleanup 结果，并至少要求 `owned_resources_absent is True`、target comparison PASS、无 secondary failure；receipt、run-summary、request trace 与 check_results 共用该值。新增完整 run fixture，断言任一 `owned_process_stops[].after` 非空时 absence/proven/PASS 均不得为真。

## 前次 Popen Major 独立复算

使用自建的状态型 Popen（没有复用实现测试 helper）运行四组完整 `Probe.run()` 临时 fixture：

- **assigned + wait timeout + poll None**：start=[1,0]；terminate/kill 各只调用该 Ollama Popen 一次；terminal `exited=false`、absence=false、proven=false、cleanup=`FAIL`；稳定记录 WAIT_TIMEOUT、TERMINATE_TIMEOUT、KILL_TIMEOUT、STILL_RUNNING。
- **wait 异常后最终退出**：start=[1,0]；只对该 Popen terminate 一次，最终 `exited=true`、absence=true，但 WAIT_FAILED 被保留，所以 proven=false、cleanup=`FAIL`。
- **正常退出**：start=[1,0]；不调用 terminate/kill；`exited=true`、absence=true、secondary=[]、proven=true、cleanup=`PASS`。
- **两个 Popen、一个仍存活**：start=[1,1]；正常退出的 Comfy Popen 未被 terminate/kill，只有 lingering Ollama Popen 接收 terminate/kill；整体 absence=false、proven=false、cleanup=`FAIL`。

这四组证明 WP-S0-33 的 Popen M-01 已关闭，也证明 terminate/kill 没有作用于未知对象或未赋值对象。候选测试中的对应四项与独立结果一致。

## correction-11 状态语义回归

- 原 33 项 fixture 全部保留并通过：identity mismatch、GPU preflight stop、owner/listener enumeration exception 在零 owned start 时保持下游 `NOT_REACHED`。
- reached no-cloud/remote/path/route failure 仍为 `FAIL`；成功映射仍只在输入的 cleanup proven 为 true 时 PASS。
- `cleanup.proven`、`owned_resources_absent`、`target_integrity_comparison` 仍是独立字段；但 M-01 表明严格 proven 没有把 captured-PID absence 纳入自身条件，因此“字段分离但不矛盾”的语义尚未完全闭合。
- Popen 计数继续由 assigned Popen 对象决定，不依赖 wrapper/listener PID 捕获。

## 测试与可复现结果

- `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：37/37 PASS，含原 33 项和四个 correction-12 fixture。
- AST parse、`--help`、`--self-check`：全部 exit 0；self-check 明确 `service_started=false`。
- `python3 -B tools/verify_pack.py --schema`：1075/0；这是文档/合同校验，不是产品验收。
- `python3 -B tools/verify_governance.py`：38/0；`--self-test`：43/0，均明确 `product_tests_executed=false`。
- Stage payload manifest 9/9、root manifest 全项 SHA-256 通过。
- 四组独立 Popen fixture 通过预期；第五组 captured-PID residual fixture 稳定复现 M-01。

## 候选、receipt、manifest 与 packet 绑定

- 提交链为 `e9a45da...` → `000fa24...` → `73e7a2f...`。候选相对冻结 packet 只修改两个 harness 文件并新增 correction-12 offline receipt；changed_files 3/3 与候选 diff 精确一致，diff 无 whitespace error。
- 候选提交中的 receipt 使用 pending 零值；gate-owner seal 才将 candidate/evidence 绑定为 `000fa24...`，并更新 packet/control、execution-control、root manifest 和治理校验，没有形成实现者自签。
- 两个工具的独立 SHA-256 为 `55443c3db896f417f083bacef75ee8c8f3967007b3a1a0b85da7beeb592ed468`、`a60e75b7f2b9b5711b3b543827a5394b3309e882a32870d8481f450a762a91e3`；与 receipt、candidate Git blob 当前字节和 root manifest 一致。
- receipt 的 frozen packet、baseline harness、sealed candidate/evidence、角色、测试计数与 acceptance binding 均闭合。固定 acceptance hash 独立复算仍为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。

## 历史不可改写、外部动作与固定分母

- 在 frozen packet、candidate、seal 三个提交中，correction-10 tree 始终为 `bb899d4ca0818c84293dab00fd1a1ed8f2c464c7`，correction-10 live receipt blob 始终为 `9c2d7d8bbad8f653189d132e686c0eac78987547`。
- correction-11 offline receipt blob 始终为 `8174a6c874832569ed7fb3bf5f0489486514de35`，其独立复审 blob 始终为 `7cbc6193339bf5bea515061513a4ada65f314078`。前次 Major 没有被改写，只由新候选前瞻性纠偏。
- correction-12 receipt 记录 Comfy/Ollama starts、service probes、network/model calls、真实媒体读取、下载、target writes 全部为 0；本次复审同样只运行 mock/静态离线命令。
- `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 全部保持 `NOT_RUN`；分母 4、not_run 4，其余计数 0。37 个 fixture、manifest 和治理 PASS 均不是产品 PASS。

## 审查意见与限制

- **假绿判断**：前次 lingering-Popen 假绿已关闭，但 M-01 的 captured-PID residual 分支仍存在清理假绿。
- **WP-S0-34/35 意见**：不建议通过 READY_FOR_REVIEW checkpoint；先闭合严格 cleanup 与 `owned_resources_absent` 的一致性，并增加完整 run 负例，再独立复审。
- **S0 状态建议**：不得 Stage PASS、不得推断 live 授权。即使离线 Major 清零，Stage 也只能回到既有 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并释放未知 GPU owner；后续真实运行必须另获新授权。
