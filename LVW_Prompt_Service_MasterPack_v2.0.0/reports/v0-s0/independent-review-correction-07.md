# V0-S0 / WP-S0-21 独立离线复审（correction-07）

## 结论

本次复审绑定 packet `f15c3053dcda3407cb8af90d4a84274fc7d702be`、授权 `d264fc511756c3945118348b72735efa1fb03567`、harness `82975aefdef2df84d6ec89285f3c450a47d78d89`（目标文件 SHA-256 `706b408b822609d7a0d361f1de5c13c683eff35071110ee3d7676fdd14838ace`）、原始证据 `f196c4be0c6252cbb5a5df1c15486121f3c0486f` 和封存收据 `f4f9c01d79c50f2f14b80bac070b2e61a65269e7`。复审只使用离线只读命令，未启动服务、调用模型或网络，也未改动候选、授权和原始证据。

严重度：Fatal **0** / Major **2** / Minor **0**。

建议状态为 **BLOCKED**，不作正式 gate 裁决，也不宣布 Stage PASS。Windows-native 与 WSL 的 GPU 数值门禁一致且低于 4096 MiB，但 Win32_Process/CIM owner 枚举在解码阶段失败，完整 pre-service gate 没有通过；harness 按要求在任何服务启动前停止。图片/视频、模型与公共生产路径均未执行，不能形成新的产品或功能结论。

## Findings

### M-01 — CIM 输出被隐式 UTF-8 解码，owner gate 无法完成（Major；harness 缺陷）

- 位置：sealed harness `tools/v0_s0_live_probe.py:244-251,264-274,282-331,818-836`；`reports/v0-s0/correction-07/events.json:1-9`；live receipt `:96-102,150-170`。
- 触发：pre-service GPU 查询成功后，harness 以 `subprocess.run(..., text=True)` 执行 PowerShell `Get-CimInstance Win32_Process ... | ConvertTo-Json`；Windows 输出在 byte 44087 含 `0xbb`，Python 按 UTF-8 解码时抛出 `UnicodeDecodeError`。
- 预期：在启动任何服务前，可靠取得并脱敏 Windows process/command-line 与 8191/11434 listener owner；若原始字节无法解析，应保存受控诊断并产生稳定的 `WINDOWS_OWNER_ENUMERATION_FAILED`，完整门禁不得通过。
- 实际：Windows/WSL 两份 GPU raw 均为 `total=24564, used=1584, free=22555`，used/free delta 均为 0，数值部分通过；但异常发生在 `ps_json()` 返回和 `preflight-baseline.json` 发射之前，process owner 和 listener 分类均未完成。harness fail-closed，服务、模型、图片和视频均为 0，但没有完成授权要求的 pre-service owner gate。
- 证据：`commands.json` 只有 commit 与两条 GPU 查询；`events.json` 保存首因；不存在 `preflight-baseline.json`；receipt 明确 `gpu_owner_gate_completed=false`、`process_owner_classification_completed=false`、`listener_classification_completed_before_exception=false`。
- 复算方法：`git show 82975ae:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s0_live_probe.py | nl -ba | sed -n '235,335p;815,865p'`；`nl -ba reports/v0-s0/correction-07/{commands,events,run-summary}.json`。修复应强制 PowerShell 输出编码或按 bytes 接收后确定性解码/失败分类，并增加非 UTF-8 CIM fixture；不得用 replacement decode 后静默接受可能损坏的 PID/command line。

### M-02 — failure-finalization 假定 preflight artifact 必然存在，首因后再次崩溃（Major；harness 证据可靠性）

- 位置：sealed harness `tools/v0_s0_live_probe.py:855-927,944-1001`，特别是 `:983-984`；live receipt `:26-27,133-148,203-207`。
- 触发：M-01 在 `windows_native_preflight()` 发射 `preflight-baseline.json` 之前退出；`finally` 成功写出 commands/events/cleanup/summary/manifest 后，自动收据代码无条件读取缺失的 `preflight-baseline.json`。
- 预期：任何 pre-service 失败都应保留首因，原子生成终态 receipt；缺失阶段 artifact 应被表达为 `NOT_REACHED/BLOCKED`，不能让收据 finalization 自身再抛异常或遮蔽首因。
- 实际：sealed harness 又发生确定性的 `FileNotFoundError`，外层 invocation exit 1，自动 receipt 未完成。实现者随后依据已封存 raw 手工补建 BLOCKED receipt；该 receipt 同时记录 UnicodeDecodeError 和 FileNotFoundError，没有把二次异常伪装成原始运行结果。
- 证据：evidence tree 确实没有 `preflight-baseline.json`；代码在 receipt 组合中直接 `.read_text()`；manifest 已在该读取之前生成；receipt 的 command 3 明确记录两个异常及 no service start。
- 复算方法：`git show 82975ae:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s0_live_probe.py | nl -ba | sed -n '855,1001p'`；`test ! -e reports/v0-s0/correction-07/preflight-baseline.json`；对照 receipt `runtime_exception` 和第三条 command。修复应让每个阶段先写状态或使用存在性检查，并用 fixture 覆盖“首个 preflight artifact 之前失败仍生成完整 BLOCKED receipt”。

## 完整性与绑定复算

- 提交祖先链成立：harness `82975ae` → 授权 `d264fc5` → evidence `f196c4b` → sealed receipt `f4f9c01` → packet `f15c305`。授权绑定产品候选 `138b448...`、harness `82975ae...` 与 offline receipt `2f8ac30...`。
- 从 `82975ae` 直接读取 `tools/v0_s0_live_probe.py` 重算 SHA-256 为 `706b408b...`，与 offline/live receipts 一致。
- evidence commit 实际 changed paths 为 10；live receipt 的 10 项列表经 MasterPack 根前缀归一化后完全相等。`f4f9c01` 只将 receipt 的 evidence SHA 从全零占位符封为 `f196c4b`，没有修改 raw。
- correction-07 manifest 含 8 项，恰好覆盖 evidence 目录除 manifest 自身外的 8 个文件；逐项重算 bytes/SHA-256，0 mismatch。manifest 自身在 evidence/current tree 的 SHA-256 均为 `7a324e61...`。
- Stage payload manifest 全部通过；固定分母 hash 保持 `78b158e1...`，`V0-A01/A02/A09/A10` 全部 `NOT_RUN`。

## 运行事实与边界

### Pre-service 与外部动作

- Windows-native/WSL GPU 输出均为 `24564/1584/22555 MiB`；两侧 total/used/free 完全相同，used 低于 4096 MiB。数值子门禁通过不等于整个 pre-service gate 通过。
- CIM owner 枚举未完成；listener 分类也未在首因前完成。finally 的独立 listener 查询记录最终 8191/11434 为空，只能证明终态端口空，不能追溯证明异常前完整 owner 分类。
- 代码顺序是 preflight → sample locate → target pre-snapshot → create temp → materialize/derive → start services。异常发生在 preflight 内，因此 Ollama/Comfy start、model/network call、run temp、sample materialization、target pre-snapshot、图片 attempt、视频 attempt 全部为 0/未到达。
- `resource-samples=[]`、remote samples 为空、no-cloud=false 和 pre-model gate=false 都表示窗口未开始，不能解释为“观察到无远程连接”或“no-cloud 失败”。

### Cleanup 与 target integrity

- 没有 owned PID，四项 stop 均 `attempted=false`；run temp `exists_before=false/exists_after=false`；final authorized ports 为空。这些事实支持“没有本轮服务/temp 需要清理”。
- `target_integrity_pre=null`，post snapshot 虽存在但没有可比较的前快照；因此 `target_integrity_equal=false`、`cleanup_proven=false` 是唯一忠实结论。不得把 final ports empty、post snapshot 或 0 service start 单独提升为 cleanup/target-integrity proven。
- `ollama-request-trace` 的 visual/cleanup count 均为 0；`all_started_calls_cleaned=false` 和 terminal ps false 表示未建立 cleanup proof，不是模型调用清理失败。没有任何已启动模型调用。

## 补建 receipt 与假绿审查

补建 live receipt 与 raw/代码路径一致：decision 为 `BLOCKED`，Stage claim false；GPU 数值仅标 `PASS_OBSERVED`，owner gate标 `BLOCKED_PROCESS_ENUMERATION_DECODE`；服务/model/network/media 均 0；图片/视频 `NOT_RUN`；target pair blocked；cleanup proven false；四项产品用例均 NOT_RUN。它没有把 numeric GPU pass、final ports empty 或 post-only snapshot包装成整体 preflight、cleanup、产品或 Stage PASS。

因此未发现假绿。限制是 receipt 为 harness 二次异常后的人工 finalization，而不是 sealed harness 的原生成功输出；其真实性可由 8 项 raw、缺失 artifact、代码控制流和提交链复算，但这不能消除 M-02，也不能作为 harness failure-path 已通过的证据。

## 授权、尝试预算与下一步建议

- `AUTH-V0-S0-2026-10-27-07` 的过期条件是“产生一个 WP-S0-20 终态 receipt **或** 消耗任一媒体 attempt”。终态 receipt 已产生并封存，所以旧授权已经过期，绝不可复用。
- 有效媒体 attempt 为 image 0 / video 0；本次是授权 invocation/route ordinal 2，但不是有效媒体尝试。它没有消耗冻结的最后一次有效图片或视频预算，也没有形成第二个同路线媒体失败。
- M-01/M-02 是新的、可确定复现的 harness/finalization 缺陷，不是对相同媒体路线无新证据的重复重跑。因此可以建议 root 先建立新的**纯离线 harness 编码与 receipt-finalization 纠偏 workpack**；该工作不得启动服务，也不得修改产品候选、内容 Oracle、120 秒超时、资源阈值或旧证据。
- 纠偏完成、负例测试与独立封存后，若项目负责人仍选择继续，必须另建新的 candidate-bound live authorization。新授权只能明确承接尚未消耗的最终有效媒体尝试，不能解释为恢复/延长 `d264fc5`，也不能在离线修复完成前自动获得。

综合建议：当前保持 **BLOCKED**；允许 root 规划纯 harness 纠偏，之后由人类决定是否签发新授权。任何后续运行仍必须从完整 pre-service GPU/process/port owner gate 开始；产品四项继续 NOT_RUN。
