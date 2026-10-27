# V0-S0 / WP-S0-30 correction-10 独立离线复审

审查日期：2026-10-27（Asia/Shanghai）  
审查角色：`codex_isolated_reviewer`  
审查入口：`0277d5d496c3dff612957ab0543f87b0b86a1f02`  
raw evidence：`620a7246e3f99389c68f950013d257fd7bc6fb52`  
authorization：`0b870365b30decd977d92756417eda7de56175d6`  
产品候选：`138b4486fdaeb8d207ef6b5efb63a09865f174b9`  
harness 候选：`d1f268f6c9c3996ba64d49c29343cd87aa7ec1d7`

审查方式：离线、只读；未启动或探测服务，未访问网络或媒体，未修改实现、raw evidence、合同、packet 或历史记录。

## 结论

Fatal **0** / Major **0** / Minor **1**

WP-S0-29 的 run-level **NO_GO 可信**：Windows-native 与 WSL 在服务前均观测到 GPU used 6044 MiB / total 24564 MiB，超过冻结上限 4096 MiB 达 1948 MiB；harness 因此在服务、模型和媒体之前 fail-closed。identity、最小化证据、零启动和终态 listener/temp/owned PID 记录互相一致，没有发现假绿或隐私回归。

这不支持 `STAGE_BASELINE_COMPLETE`。建议 S0 运行态记为 **BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER**，同时保留本次终态收据的 `NO_GO`，两者不冲突：前者描述继续完成 baseline 所需的外部条件，后者描述本次已过期授权下的确定性结果。若项目不再寻求新的 baseline proof，root 也可维持终态 `NO_GO`；不得宣布 Stage PASS。

下一责任人是 **project_owner（人类负责人）**，不是实现者：需要识别并自行关闭或释放未知 GPU owner/负载；实现者不得终止非 owned 进程。清空后仍不能自动重跑，必须由 root 在新鲜 preflight 证据基础上决定是否签发新的单次授权。

## Finding

### N-01 — Minor — 未到达的网络、路径与清理步骤被 receipt 合并标成 FAIL

- **位置**：`reports/v0-s0/implementation-receipt-correction-10-live.json:95-122,174-186`；`reports/v0-s0/correction-10/pre-model-gate.json`；`ollama-request-trace.json`；`cleanup.json`；`run-summary.json`。
- **触发**：沿时间线从 GPU preflight stop 反推每个后续 gate 是否实际执行，再核对 receipt 的 `check_results` 与 `cleanup.proven`。
- **预期**：preflight 前置失败后，未启动 Ollama/Comfy、未建立 target pre-snapshot、未进入 no-cloud/remote gate、未调用 `/api/ps` 或路径转换的步骤应明确标为 `NOT_REACHED`；不得把空观察窗口解释为网络通过，也不应把“无需清理但无法证明 target integrity 前后相等”写成 owned cleanup failure。
- **实际**：receipt 将 no-cloud、remote TCP、Comfy path conversion 和 cleanup/target integrity 标为 `FAIL`；两条 public route 标为 `NOT_RUN_OR_FAIL`。raw 实际为：network sample 0、pre-model sample 0、服务 PID 全 null、temp 从未创建、最终 listener 为空、target_integrity_pre=null、只有 post snapshot，所以 `cleanup.proven=false`。这是保守的状态词偏差，不是残留资源证据，也不改变 GPU preflight NO_GO。
- **证据**：`commands.json` 只有 authorization/product commit、harness identity 和两次 GPU query；没有启动、HTTP、sample/media、temp 或 model 命令。`owned-ollama-remote-tcp.json` 与 `resource-samples.json` 的 samples 都为空；`ollama-request-trace.json` 为 0 chat/0 cleanup 且 terminal API ps 未执行；`cleanup.json` 的四个 owned PID 均 null、stop_attempted=false，temp attempted=false/exist=false，final listeners=[]，secondary failures=[]。
- **复现**：`rg -n '"status": "FAIL"|NOT_RUN_OR_FAIL|cleanup|sample_count|target_integrity_pre|stop_attempted' reports/v0-s0/implementation-receipt-correction-10-live.json reports/v0-s0/correction-10/{pre-model-gate,ollama-request-trace,cleanup,run-summary}.json`；只需比较字段，不启动任何服务。
- **建议**：未来 harness/receipt 将这类前置阻断后的派生检查标为 `NOT_REACHED`，并分别报告 `owned_resources_absent=true` 与 `target_integrity_comparison=NOT_REACHED`。禁止事后改写本轮 raw；本报告保留其原始字段并解释语义。

## 授权与提交绑定

- 正式授权记录绑定 product `138b448...`、harness `d1f268f...`、harness file SHA-256 `999cb17e...fc810`、固定两份样本、图片/视频各 1 次、loopback/no-cloud、GPU/owner/port 和 cleanup 门限。授权禁止代码/门限修改、非 owned kill、云、下载和远端 push。
- authorization commit `0b87036...` 是 evidence commit `620a724...` 的直接父提交；review entry `0277d5d...` 是 evidence commit 的直接后继。raw commit 产生终态 receipt，满足 `expires_when=one terminal WP-S0-29 receipt`，所以授权已经过期；媒体 0/0 不保留可自动使用的预算。
- 当前 authorization JSON 仍保存原始 `GRANTED_ONCE` 作为签发事实；其终态过期由 `expires_when`、terminal receipt、coordinate/risk register 三者共同证明。不得恢复、延长或复用。

## Harness identity

- `harness-identity.json` 记录候选 commit `d1f268f...`、Git blob object `9fb8c73b3bb4d1fbcc54544fff723ddb0e187c7b`、blob SHA-256 与 executed file SHA-256。两个 SHA-256 都为 `999cb17e42ef9f2fd4f2ba87e6cb2cf2c9009b0485d6a075b97957658e6fc810`，`matched=true`、`service_starts=0`。
- 独立执行 `git show d1f268f:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s0_live_probe.py | sha256sum`、当前 file hash 和 `git rev-parse d1f268f:...`，三者与 artifact 一致。
- `commands.json` 的时间顺序为 authorization commit → product commit → harness identity → Windows GPU → WSL GPU；identity gate 在 preflight 与任何服务启动前完成。

## Preflight、隐私和零动作

- Windows/WSL GPU 均为 total 24564、used 6044、free 18095 MiB，跨环境 delta 为 0；`windows_wsl_match=true`。6044 > 4096，`GPU_PREFLIGHT_USED_ABOVE_4096_MIB` 是授权列明的 mandatory stop，阻断行为正确。
- `windows_process_count=387` 是不可逆聚合计数；`target_process_count=0`、`target_processes=[]`；授权端口 listener 为空。证据没有证明 6044 MiB 的 owner 身份，只证明它不是 preflight 匹配到的目标 Comfy/Ollama 进程，因此应按 unknown GPU owner 处理，不可归因给产品或 harness。
- correction-10 目录和 live receipt 的结构扫描结果：`CommandLine` JSON key 0、Base64-shaped `user=`/`path=` 0、Windows 绝对路径 0、WSL/home 绝对路径 0。`logical_commands` 仅说明 CIM 曾在内存读取 command line 进行匹配，没有保存行内容。没有全量进程表、原媒体、凭据或私有路径泄漏。
- external actions 为 Comfy start 0、Ollama start 0、model calls 0；effective attempts image 0/video 0。命令链在 preflight 后停止，未出现 temp/media derivation、sample verification、HTTP 或 model 命令，故媒体读取/有效尝试也为 0。

## 网络、清理与终态

- 网络 gate **NOT_REACHED**：Ollama 未启动，remote samples=[]、pre-model sample_count=0、no-cloud 未观察、`/api/ps` 未调用。`non_loopback_seen=false` 只表示空集合中没有记录，不是“无远程连接已证明”；receipt 的 `passed=false` 与 stage_pass=false 阻止了假绿。
- final authorized listeners=[]；四类 owned PID 均 null 且 stop_attempted=false；run temp attempted=false、exists_before=false、exists_after=false；secondary cleanup failures=[]。这些字段可信地说明没有本 run owned 资源需要停止或删除。
- `cleanup.proven=false` 的精确含义是：preflight 失败发生在 `target_integrity_pre` 建立前，最终只取得 post snapshot，因此 `target_integrity_equal=false` 无法构成前后比较。它不是“发现目标被修改”，也不是“owned cleanup 失败”。不能把最终空端口/无 temp 扩张为完整 target-integrity proof。

## Manifest、receipt 与固定分母

- evidence commit 正好新增 12 个路径；live receipt 的 `changed_files` 12/12 与 commit diff 完全一致。
- correction-10 artifact manifest 含 10 个条目，恰好覆盖目录中除 manifest 自身外的 10 个 artifacts；10/10 size 与 SHA-256 独立复算一致。manifest SHA-256 为 `9a1b3f87b3fe1169012af88859f006249bf7021bb8a2b2e4ba7798e360a59016`。
- gate owner 在 review entry 中只把 receipt 的 evidence commit 从 pending 零值封存为 `620a724...`；当前 receipt SHA-256 为 `1f1b901e15d05dbe14430fa6953eca8daba74fd88e58244ac589052a73be0961`。root `MANIFEST.sha256`、Stage packet 9/9、pack 1071/0、governance 38/0 均通过；这些不是产品验收。
- 固定 acceptance hash 仍为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。receipt 的 `V0-A01/V0-A02/V0-A09/V0-A10` 全是 `NOT_RUN`，denominator 4、not_run 4、其他计数 0。不得把 GPU preflight 结论写成 V0-A09 PASS，也不得把 0/0 媒体尝试写成图片/视频阶段完成。

## 历史、假绿与出口建议

- correction-10 evidence commit 只新增本轮 artifacts/receipt；没有修改产品、harness、合同、门限或任何历史 evidence。review entry 的后续变更限于 sealing/governance 与 receipt commit 字段，不倒写 raw artifacts。
- correction-08 的隐私事故、correction-06 的 unknown-owner 污染、rerun-02 的 23810 MiB 峰值及其他历史失败继续有效。本轮最小化成功不能追溯消除旧事实。
- **假绿判断**：未发现产品或 Stage 假绿。decision=NO_GO、stage_pass=false、production path NOT_RUN、产品四项 NOT_RUN；N-01 是保守假阴性式标签偏差，不会把失败包装为成功。
- **建议状态**：本轮 `NO_GO` 可信；S0 不满足 baseline exit。若继续追求 baseline，先置为 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并关闭未知 GPU owner，再由 root 决定是否建立全新的单次授权。不得让实现者 kill 非 owned PID，不得复用已过期授权，不得自动重跑或降低 4096 MiB 门限。
