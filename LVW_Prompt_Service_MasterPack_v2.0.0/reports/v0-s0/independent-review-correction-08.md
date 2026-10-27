# V0-S0 / WP-S0-25 独立隔离复审（correction-08）

审查日期：2026-10-27（Asia/Shanghai）  
审查角色：`codex_isolated_reviewer`  
审查方式：离线、只读；未启动 ComfyUI/Ollama，未调用模型或网络，未重跑媒体，未修改候选、治理 packet 或历史证据。

## 结论

Fatal **1** / Major **2** / Minor **0**

建议 S0 状态：**NO_GO**。这只是独立复审建议，不是 root 的正式裁决，也不是 Stage PASS。实现者收据中的 `NO_GO` 不能原样采信：其视频失败首因是 harness 把合同规定的 `camera_motion: string` 错当成非空 list，属于假阴性；但是封存证据同时存在 Fatal 级隐私脱敏遗漏，且没有把实际执行的 harness 字节与授权候选作可验证绑定，因此也不能把本轮改判为 `STAGE_BASELINE_COMPLETE`。授权已经因终态收据和 1/1、1/1 媒体尝试而过期，禁止据此重跑。

本轮没有产品用例 PASS：`V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 均保持 `NOT_RUN`。correction-08 仅是 S0 feasibility 探测；即使把视频 harness 假阴性纠正为满足冻结结构 Oracle，也不等于生产质量 E2E 或产品验收通过。

## Findings

### F-01 — Fatal — 封存证据包含可逆编码的私有标识和绝对路径

- **位置**：`reports/v0-s0/correction-08/preflight-baseline.json:1318`；同一整表又内嵌于 `reports/v0-s0/implementation-receipt-correction-08-live.json:1371`。相关过采集还见 receipt `:1280`（daemon pipe/nonce/token 文件位置）及 `:2204` 起的无关 WSL 会话命令。
- **触发**：读取并审计 pre-service 进程枚举的 `CommandLine` 字段，检查占位符之外仍可逆的编码载荷。
- **预期**：按 `05-risk-and-authorization-register.md:12` 的 R-03，只保存证明 target owner/port gate 所需的最小脱敏信息；不得在证据中留下私有路径、媒体或凭据。发现泄漏应停止发布受影响证据。
- **实际**：`windows_processes` 保存 385 个系统/用户进程，其中 225 个带完整命令行，远超 Comfy/Ollama owner 判定所需范围。第 1318 行的无关 updater 命令含 `user=<Base64>` 和 `path=<Base64>`；前者可逆为九位数字用户标识，后者可逆为盘符开头的 Windows 绝对路径。用 `USER_PROFILE`/`WINDOWS_ABSOLUTE_PATH` 替换普通明文路径没有覆盖这些嵌套编码字段。报告不复述解码后的私有值。
- **证据**：上述两个封存 JSON；`preflight-baseline.json` 的结构化复算为 385/225。该原始 artifact 已由 manifest 和 evidence commit `8fa8140dc7d58bb65fe9eefbc9992f7ad08a8f70` 封存，不能在本复审中改写。
- **复现**：仅作不回显载荷的结构检查：`rg -c --pcre2 'user=[A-Za-z0-9+/]{8,}={0,2}.*path=[A-Za-z0-9+/]{8,}={0,2}' reports/v0-s0/correction-08/preflight-baseline.json reports/v0-s0/implementation-receipt-correction-08-live.json`。该命令只输出文件名与匹配计数；报告将匹配到的用户字段记为 `user=<REDACTED_BASE64_USER>`。禁止输出或解码 `user=`/`path=` 的原始值。

### M-01 — Major — 视频 semantic Oracle 使用了与冻结合同相反的类型，造成终态假阴性

- **位置**：`tools/v0_s0_live_probe.py:670-683`；`contracts/prompt-spec.schema.json:121-123`；`LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py:383`；`reports/v0-s0/correction-08/attempt-video-1.json:4,18,143`。
- **触发**：独立解析视频 history 的 `suggestion`，再逐项对照 prompt-spec、产品候选序列化代码和冻结 Oracle 文义。
- **预期**：prompt-spec 要求 `technical.camera_motion` 为 string；固定 Oracle 接受“非空 motion 或明确的逐帧变化/无变化结论”（`04-acceptance-matrix.md:21-22`）。候选测试也明确把 `no visible change can be established` 视为有效结论。
- **实际**：输出包含非空字符串 `technical.camera_motion`，并给出了明确的无变化结论；但 harness 以默认 `[]` 读取该字段，并要求 `isinstance(motion, list) and motion`，因此抛出 `ValueError: video suggestion has no camera_motion`。这直接把完成的四帧公开路径标为 FAIL，并驱动 `PUBLIC_COMFY_ROUTE_FAILED_WITHIN_ATTEMPT_BUDGET` / `NO_GO`。该判定是 harness 假阴性，而不是正确 fail-closed，也不是产品候选失败。
- **证据**：harness `:681-683`；schema `:121-123`；产品合并逻辑 `core.py:383`；候选回归 `tests/test_lvw_v0_bridge.py:181-186`；attempt 的非空字符串及 HTTP/history 成功记录。
- **复现**：`nl -ba tools/v0_s0_live_probe.py | sed -n '670,698p'`；`nl -ba contracts/prompt-spec.schema.json | sed -n '121,123p'`；`rg -n 'camera_motion|failure' reports/v0-s0/correction-08/attempt-video-1.json`。对 suggestion 运行 `json.loads(...)["technical"]["camera_motion"]` 得到非空 string，而当前 oracle 必然拒绝它。

### M-02 — Major — live 证据没有证明实际执行的 harness 字节就是授权候选

- **位置**：`reports/v0-s0/authorization-correction-08.json:14,18`；`reports/v0-s0/correction-08/commands.json:2-77`；`reports/v0-s0/implementation-receipt-correction-08-live.json:20,2821-2838`。
- **触发**：从授权的 `harness_candidate_sha` 反向查找 live receipt、commands、artifact manifest 中的候选 SHA、tool SHA、自哈希或物化命令，并与 Git object 独立哈希比较。
- **预期**：授权要求 `tools/v0_s0_live_probe.py materialized exactly from harness_candidate_sha`；终态证据应记录并可复算 harness commit、实际执行文件 SHA-256，以及在服务启动前从该 commit 物化/核对成功的命令和退出码。
- **实际**：授权绑定 `57f771823a625eabd3fd746d352f5936d37380a2`，且该 commit 与授权 commit 中的工具 blob 都独立哈希为 `5b7e3c60a37b75f0d8605f3c84fe9a6572a356ab7b3010201cfb34633c3e055e`；但是 live receipt 没有 `harness_candidate_sha`/`harness_sha256`/`tool_sha256`，commands 只验证 authorization commit 与产品 `CANDIDATE_SHA`，没有验证或物化 harness。仓库静态 blob 一致不能证明 run 当时执行文件的字节身份。
- **证据**：authorization 的明确绑定；commands 的 10 条记录；live receipt 仅记录产品 `candidate_sha=138b448...` 和 evidence commit。artifact manifest 覆盖 raw artifacts，但不包含执行工具副本或其 digest。
- **复现**：`rg -n 'harness_candidate|harness_sha|tool_sha|verify_.*candidate' reports/v0-s0/correction-08/commands.json reports/v0-s0/implementation-receipt-correction-08-live.json` 无 harness 执行绑定命中；对比 `git show 57f7718:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s0_live_probe.py | sha256sum` 只能得到被授权 blob 的 hash，不能补出 run-time identity。

## 独立复算结果

### 提交、manifest 与候选

- 审查入口 `dae89d380db6207784a195d9741ea3a2748889b4` 的直接父提交是 evidence `8fa8140...`；evidence 的直接父提交是 authorization `5e9396e...`。authorization 绑定产品 `138b448...`、harness `57f7718...` 和 fixed samples。
- evidence commit 共 27 个 changed paths：`correction-08/` 下 manifest 加 25 个 artifacts，以及 live receipt。artifact manifest 恰好覆盖除自身外的 25 个 artifacts；25/25 size 与 SHA-256 重算一致，manifest 自身 SHA-256 为 `d2939e0fe03d487eab52d8787d9f9b8287c47cf7e905224629f201cf6a2df2c9`。
- 产品 `candidate-materialization.json` 的产品提交和 `__init__.py`、`core.py`、`nodes.py` blob hash 与 `138b448...` Git objects 一致。图片/视频源 SHA-256 分别为授权的 `b4bbd08a...`、`694a50bf...`；派生图片为 306×384，四帧均为 286×384，源帧序号 9/28/46/65，四个 frame hash 不重复。
- Stage packet 的 `PAYLOAD_MANIFEST.sha256` 在审查入口 9/9 校验通过。以上证明 artifact 静态完整性；不能消除 M-02 的 run-time harness identity 缺口。

### 公开入口、模型请求与 Oracle

- 图片由 Comfy public `POST /prompt` 返回 200，随后 `/history/{prompt_id}` 返回 200，class type 为 `LVWImagePromptBridge`；history 为成功输出，raw `done=true`、`done_reason=stop`、observation 与生成 prompt 非空。图片 feasibility attempt 可独立认定为 1/1 满足冻结结构 Oracle。
- 视频同样经 public `/prompt`/`history` 到 `LVWVideoFramesPromptBridge`，workflow 明确由四个 `LoadImage`、三个 `ImageBatch` 顺序组成。history `execution_success`，保存四个按序 raw frame responses；每帧均 `done=true`、`done_reason=stop` 且 observation 非空。其最终 `camera_motion` 是合同有效的非空 string，故实现者的“缺少 camera_motion”结论不成立。输出中后续 observation 观察到 peace sign，而相应 change 多次写“no visible change”，显示语义质量仍弱；冻结 S0 Oracle 接受明确无变化结论，因此这里只作为 feasibility 限制，不能扩张成产品质量 PASS。
- `ollama-request-trace.json` 与 `ollama-live.log` 可对应 5 次 `/api/chat` 和 5 次 `keep_alive=0` `/api/generate` cleanup，cleanup HTTP 200 为 5/5，顺序相关性成立，`all_started_calls_cleaned=true`。图片后、视频后 t0/t5、最终 stop 前 `/api/ps` 均为空；最终模型驻留为空。

### 资源、网络和清理

- pre-service Windows native 与 WSL GPU 均为 total 24564 MiB、used 1668 MiB、free 22471 MiB，逐项 delta 0；used 小于 4096 MiB。target process 与 8191/11434 listener 均为 0，preflight `passed=true`。
- pre-model gate 连续约 10.01 秒、10 个样本，`OLLAMA_NO_CLOUD:true`，owned PID 非 loopback TCP 为 0。全窗口 120 个网络样本未记录非 loopback remote；这只证明观察窗口，不是对所有潜在网络路径的无限期证明。
- 资源记录 120 个样本；GPU 峰值 20186 MiB，严格小于 23552 MiB；最低 host available RAM 11589 MiB。未触发 GPU/RAM mandatory stop。
- cleanup 记录 Comfy listener PID 50208 与 Ollama listener PID 49240 stop exit 0，两个 wrapper 已先退出而 stop exit 1；stop 后 owned PID 均为空。8191/11434 最终 listener 为空，run temp 删除 exit 0 且不存在，pre/post 六个 target 文件 hash 完全相等，`target_integrity_equal=true`。没有把 wrapper “already absent”误写成 owned listener 清理失败。
- 除 F-01 外，普通明文绝对路径已大体替换为 `USER_PROFILE`、`WINDOWS_ABSOLUTE_PATH`、`WSL_ABSOLUTE_PATH`，原图片/视频未打包，只有授权 source hash 与受控派生 frame hash；没有发现明文 API key/password/cookie。F-01 说明当前扫描不足以支持“隐私脱敏通过”。

### 固定分母、角色与历史失败

- live receipt 的固定四项为 `V0-A01/V0-A02/V0-A09/V0-A10 = NOT_RUN`，PASS/FAIL/BLOCKED/SKIPPED 计数均为 0。不得用图片 attempt 或纠正后的视频结构 Oracle 改写这些产品分母。
- live evidence owner、独立 reviewer 与 root gate owner 的角色保持隔离；本 reviewer 没有继承实现者结论，也未执行产品/环境写操作。
- 历史失败仍保留且未被 correction-08 改写：早期 direct-Ollama 不能替代公开入口；rerun-02 的视频峰值 23810 MiB、no-cloud/清理缺口；correction-03 的 non-loopback remote；correction-04 的 Windows path 启动阻断；correction-05 的 prompt echo；correction-06 的 120 秒 timeout、未知 GPU owner/污染环境；correction-07 的 UnicodeDecodeError、服务与媒体 0 次及 failure-finalization 缺口，均仍是相应 run 的事实。correction-08 的干净资源和公共 trace 不能倒写这些旧记录。

## 假绿/假阴性判断与出口限制

- **假阴性存在**：M-01 使一个满足冻结 string schema/明确无变化结论的四帧输出被 harness 错判失败；因此实现者的精确 NO_GO 首因不可信。
- **产品假绿未出现**：四个固定产品用例仍是 NOT_RUN，Stage claim 未被写成 PASS；直接图片/视频 feasibility 也不得被表述为完整产品 E2E。
- **潜在治理假绿**：若只因 manifest、cleanup、资源和实现者 NO_GO 较保守就认定证据充分，会忽略 M-02 的执行身份缺口与 F-01 的隐私泄漏。Fatal/Major 未清零，按 `07-checkpoint-plan.md:14` 不允许 baseline 出口。
- **建议限制**：root 保持 `NO_GO`，隔离/限制传播受影响的 correction-08 evidence，并按隐私事件流程处理可逆编码字段；不得修改已经封存的历史事实。任何未来工作须先离线修复脱敏最小化、harness 自绑定和 `camera_motion` 类型 Oracle，再由 root/人类负责人决定是否存在新的、独立授权路径。当前过期授权绝不能恢复、延长或解释为重跑许可。
