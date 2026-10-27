# V0-S0 / WP-S0-17 独立离线复审（correction-06）

## 审查结论

审查对象为 packet commit `576748229a2423b78668175d1d63d3c933c60928`，候选 `138b4486fdaeb8d207ef6b5efb63a09865f174b9`，授权 `558bdb7d616d6fd908ff8de9a0de4ab59569afe7`，原始证据 `d337866d5f6bbb49f04d75ec0b4b1b79ba5d587e`，封存收据 `25ac028db0573b6c6d0d11ed04574db5ae1b0b86`。本次只进行了离线只读复算，未启动 ComfyUI/Ollama、未调用模型或网络，也未修改候选、原始证据或治理文件。

严重度计数：Fatal **0** / Major **2** / Minor **2**。

建议 root 将本轮 S0 出口保持为 **NO_GO**，不得给出 Stage PASS：correction-06 的真实 Comfy 公共图片路径到达了候选节点，但模型调用在 120 秒超时，未产生可用语义结果；授权要求在公共路径失败后停止，因此视频有效尝试为 0，候选所针对的视频 prompt-handoff 修复仍没有新的真实闭环证据。严格 trace 的 cleanup 判定是 harness 假阴性，但修正该假阴性只会把停止原因恢复为真实的 `MODEL_TIMEOUT`，不会把功能结果改为成功。

## Findings

### M-01 — 真实公共图片调用在 120 秒超时，无可用输出（Major；环境/模型性能边界）

- 位置：`reports/v0-s0/correction-06/attempt-image-1.json:40-106,109-158`；`reports/v0-s0/correction-06/ollama-live.log:276-282`。
- 触发：通过 Comfy `POST /prompt` 提交 `LVWImagePromptBridge`，设置 `timeout_seconds=120`，随后读取同一 `prompt_id` 的 history。
- 预期：公共入口在预算内形成可由内容 Oracle 检验的非空 raw/suggestion，或至少以准确的失败码 fail-closed。
- 实际：`/prompt` HTTP 200 且 `node_errors={}`，history HTTP 200，证明请求真实到达 `LVWImagePromptBridge`；约 120.582 秒后 history 记录 `MODEL_TIMEOUT/OLLAMA_TIMEOUT`，节点无 outputs，图片结果为 false。候选正确 fail-closed，但没有功能成功。Ollama 最终记录 `/api/chat` HTTP 499、耗时 `2m2s`。现有证据只能把失败定位到候选的 120 秒 HTTP 等待与本机 Ollama/model 未及时完成之间，不能进一步证明是候选算法缺陷、模型实现缺陷或当时环境调度中的哪一种。
- 证据：attempt 的 execution start `1793088352410`、error `1793088472992`；候选 `core.py:285-310,325-358` 将超时转换为稳定公共错误并保留 primary error；Ollama log 的 chat 499。
- 复现/复算（只读）：`nl -ba reports/v0-s0/correction-06/attempt-image-1.json | sed -n '1,180p'`；`rg -n '/api/(chat|generate|ps)' reports/v0-s0/correction-06/ollama-live.log`；`git show 138b448:LVW_Prompt_Service_MasterPack_v2.0.0/LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py`。

### M-02 — correction-06 的目标视频真实闭环未执行（Major；候选验证缺口）

- 位置：`reports/v0-s0/correction-06/run-summary.json:2-17`；`reports/v0-s0/implementation-receipt-correction-06-live.json:81-83,110-117`；`authorization-correction-06.json:18,27,41-48`。
- 触发：图片公共路径失败触发授权中的 mandatory stop；单图预算已消耗，授权随终态收据到期。
- 预期：在不触发前置停止条件时，以最多一次有效视频尝试验证四个有序单帧调用、anti-copy/grounding 修复和视频语义 Oracle。
- 实际：图片 1 次、视频 0 次；没有 correction-06 视频 `/prompt`、四次 `/api/chat`、history 输出或视频内容 Oracle。四个派生帧及其 hash 存在，只证明输入准备，不证明视频候选路径。历史 correction-05 的图片公共路径曾通过，但视频第 1 帧因 `PROMPT_ECHO` 被拒；correction-06 的新候选真实运行没有覆盖该历史失败，故不能宣称修复已在线验证。
- 证据：run summary `effective_attempts={image:1,video:0}`；receipt `live_route_counts.video={pass:0,total:0}`；correction-05 `run-summary.json` 的 `VIDEO_SEMANTIC_ORACLE_PROMPT_ECHO`；correction-06 `media-derivatives.json` 仅记录派生帧。
- 复现/复算（只读）：`sed -n '1,80p' reports/v0-s0/correction-06/run-summary.json`；`sed -n '1,190p' reports/v0-s0/implementation-receipt-correction-06-live.json`；`sed -n '1,100p' reports/v0-s0/correction-05/run-summary.json`。

### m-01 — strict trace 把并发超时日志完成顺序误判为 cleanup failure（Minor；harness 假阴性）

- 位置：`reports/v0-s0/correction-06/probe.py:577-603,817-820`；`ollama-request-trace.json:1-22`；候选 `core.py:312-316,325-361`。
- 触发：客户端在 120 秒超时后进入 `finally`，立即向 `/api/generate` 发送 `keep_alive=0`；服务端仍在结束/记账原 `/api/chat` 请求。
- 预期：按同一 run 的已启动调用与 cleanup 数量、候选控制流和终态资源证据关联 cleanup；不能把服务端“请求完成日志”的行序当成客户端“请求开始顺序”。
- 实际：cleanup `/api/generate` 在 16:07:52 完成并记为 HTTP 200，`/api/chat` 到 16:07:55 才以 499 结束并记日志。harness 强制日志种类必须为 `[chat, cleanup]`，所以在计数均为 1 时仍写出 `all_started_calls_cleaned=false`，并覆盖真实停止原因为 `OLLAMA_REQUEST_TRACE_SEQUENCE_OR_CLEANUP_FAILED`。候选代码明确在 chat/parse 的 `finally` 中调用 cleanup；该时间线是并发请求结束顺序，不是“cleanup 早于 chat 启动”。
- 证据：trace 行 7-16；Ollama log 行 276、280；attempt 的 120 秒超时；候选 finally；`/api/ps` 在 delay 0、5 秒及最终停止前均为 HTTP 200、`models=[]`。
- 复现/复算（只读）：`nl -ba reports/v0-s0/correction-06/probe.py | sed -n '570,610p;817,832p'`；`nl -ba reports/v0-s0/correction-06/ollama-request-trace.json`；对比候选 `core.py:325-361`。正确解释是 **cleanup 已证明、功能仍超时失败**；这是假阴性，不是假绿。

### m-02 — attempt 顶层 `KeyError: '2'` 会掩盖权威 history 中的真实失败码（Minor；harness 诊断质量）

- 位置：`reports/v0-s0/correction-06/attempt-image-1.json:3-4,40-106`。
- 触发：Comfy history 因节点执行错误而没有 node `2` 的 outputs，attempt 汇总仍读取该输出键。
- 预期：attempt 顶层 failure 应保留 `MODEL_TIMEOUT/OLLAMA_TIMEOUT`，并把缺少 outputs 作为其结果，而不是另报解析器 `KeyError`。
- 实际：顶层 `failure` 是 `KeyError: '2'`，但同文件的权威 history 清楚记录 BridgeError `MODEL_TIMEOUT`。receipt/run-summary 又被 m-01 的 strict-trace 覆盖，增加了诊断歧义。
- 证据：attempt 行 4、59-106；Comfy history 的 node/type、exception message 与 traceback 完整存在。
- 复现/复算（只读）：`nl -ba reports/v0-s0/correction-06/attempt-image-1.json | sed -n '1,115p'`。该问题不产生 PASS，但应在下次 harness 中避免次生异常覆盖首因。

## 独立复算记录

### 提交、授权与封存绑定

- 提交父链为：`d337866` 的直接父提交是授权 `558bdb7`；`25ac028` 的直接父提交是 `d337866`；packet `5767482` 的直接父提交是 `25ac028`。候选 `138b448` 存在，授权文件和 live receipt 均精确绑定该 SHA。
- `d337866` 实际新增/修改 26 个路径。receipt 的 26 个 `changed_files` 在补上 MasterPack 根前缀后与 `git diff-tree -r d337866` 完全相等。
- `25ac028` 只修改 live receipt，把占位 evidence SHA 替换为 `d337866`；没有改动原始 evidence 目录。
- `candidate-materialization.json` 的 `__init__.py/core.py/nodes.py` 三个 SHA-256 与从候选提交直接读取的字节分别完全一致：`e96cc472…`、`fcaec75…`、`5206e048…`。

### Manifest、样本与帧

- `artifact-manifest.json` 有 24 项，恰好覆盖 correction-06 目录除 manifest 自身外的 24 个文件；逐项重算 bytes 与 SHA-256，0 个不匹配。manifest 自身在 evidence commit 与当前封存树中的 SHA-256 都是 `15c5dd1b…`。
- 授权样本 hash 与 `sample-verification.json` 一致：图片 `b4bbd08a…`、视频 `694a50bf…`。派生图片最长边 384；四个视频帧均为 286×384 且有独立 hash。由于视频调用为 0，这些帧不得替代公共视频 trace。
- Stage packet 的 `PAYLOAD_MANIFEST.sha256` 全部通过；固定 ID 按排序、LF 及尾随 LF 重算为 `78b158e1…`。

### 公共入口与错误合同

- `POST /prompt` HTTP 200 返回 prompt ID，history HTTP 200，payload/history 都包含 `LVWImagePromptBridge`；这是实际 Comfy 公共路径，不是 direct Ollama feasibility。
- `comfy-object-info.json` 记录候选节点注册，history traceback 指向 run-temp 中物化候选的 `nodes.py/core.py`。图片结果仍为 FAIL；清理 PASS 不能提升它。
- 真实失败码是候选稳定输出的 `MODEL_TIMEOUT` / `OLLAMA_TIMEOUT`。没有模型 response body，因此没有可执行的 semantic Oracle，也没有 raw/suggestion 功能输出。

### 网络、资源与清理

- Ollama server raw 明确报告 `OLLAMA_NO_CLOUD:true`。预模型窗口 10.009 秒、9 个样本、0 个非 loopback 连接；全窗口 74 个样本独立枚举也为 0 个非 loopback remote。该结论仅是本次 owned PID/观测窗口的事实，不是对所有外联的普遍证明。
- 74 个资源样本独立复算：GPU 峰值 23521 MiB，严格小于 23552 MiB，余量仅 31 MiB；最低 host available RAM 11362 MiB。资源 stop 未触发，但单次失败 run 不能替代 V0-A09 的 10 次/P95 产品分母，31 MiB 余量也应保留为后续运行风险。
- cleanup 证据一致：模型 `/api/ps` 在图片后 0 秒、5 秒和最终停服前都为 HTTP 200 且 `models=[]`；Comfy listener PID 49404 与 Ollama listener PID 51392 均 stop exit 0 且 after 为空；两个 wrapper 在 stop 前已不存在（因此 taskkill exit 1，不表示残留）；最终授权端口为空；run-temp 删除 exit 0 且不存在；目标文件 pre/post size、mtime、SHA-256 全相等。
- `commands.json` 保存确定性准备命令及 exit 0；两个长驻启动命令的 exit code 为 null，生命周期终态由 cleanup 的 owned PID/port 证据补足。未发现 target install 写入或非 owned PID 终止证据。

### 隐私、角色、预算与历史

- 公开证据使用 `TEST_SOURCE`、`RUN_TEMP`、`COMFY_ROOT`、`USER_PROFILE`、`WINDOWS_ABSOLUTE_PATH` 等别名；未发现 cookie、Bearer、API key、原媒体或未脱敏用户绝对路径。history 只含 Comfy 截断 tensor 展示，不包含可还原的完整原媒体字节。
- 实现 receipt 标记实现会话 `/root/s0_rerun_implementer`；本报告由独立 reviewer 会话生成，且 root gate owner 未被替代。角色分离符合 WP-S0-17；本报告只给建议，不作正式 gate 裁决。
- correction-06 授权预算为图片 1、视频 1；图片 1 次后按 mandatory stop 终止，没有越权重试。授权已过期，不可复用。
- 历史证据未被后续提交改写：correction-03 在 owned Ollama 非 loopback 连接处以 0/0 停止；correction-04 通过 no-cloud/remote gate 后因 Comfy 路径启动失败而 0/0；correction-05 图片公共路径通过、视频第 1 帧被 `PROMPT_ECHO` Oracle 拒绝；correction-06 图片模型超时、视频 0 次。各次失败均保留，不能相互抵消。

## 固定分母与假绿判断

`V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 在 `plans/acceptance_cases.json`、execution control 和封存 receipt 中均保持 `NOT_RUN`；固定分母为 4，`pass=0/fail=0/blocked=0/not_run=4/skipped=0`。本轮 direct/local feasibility、公共图片请求被接受、资源阈值未越界或最终清理成功，均不构成任何产品用例 PASS。

未发现假绿：receipt 将两条公共媒体路线写为 `NOT_RUN_OR_FAIL`，Stage claim 为 false，产品四项保持 NOT_RUN。发现一处明确的 **假阴性**：strict trace 以服务端完成日志顺序推断 cleanup 顺序。即使纠正它，本轮仍因图片 `MODEL_TIMEOUT` 和视频未运行而是 NO_GO。

## 建议与限制

1. root 可采用 **NO_GO** 作为建议状态；这不是本 reviewer 的正式裁决，也不是 Stage PASS。
2. 若继续纠偏，应先修复 harness 的 request correlation/首因保留，再建立新的、独立授权预算；不得复用 correction-06 授权。
3. 后续真实运行必须重新证明图片语义成功及四帧视频完整公共 trace，并保留 `<23552 MiB`、no-cloud/remote 观察、每次调用 cleanup 和最终环境清理。不能通过放宽 120 秒、内容 Oracle、固定分母或资源阈值来换取通过；任何超时策略变更都应作为新的明确候选和授权审查。
