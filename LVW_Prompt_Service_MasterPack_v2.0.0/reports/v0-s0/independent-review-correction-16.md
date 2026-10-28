# V0-S0 WP-S0-47 correction-16 独立离线复审

审查角色：`codex_isolated_reviewer`

审查方式：只读 Git 对象与封存 artifact 离线复算；未启动或探测 ComfyUI、Ollama、GPU、网络或媒体，未重跑 live probe。
冻结输入：packet/seal `dc09350362204cf87bef476685ad0b84e9fbeb1b`，raw evidence `9d09f3be7bc4d206eceb7fd7f3fc9127a690e278`，authorization `d04bef7316a2a4fba000b0471d1080f6ea192725`，product `138b4486fdaeb8d207ef6b5efb63a09865f174b9`，harness `81a77cc013243f859167bd00a1971ad1543c2e46`。

## 结论

**Fatal 0 / Major 0 / Minor 0**

未发现会使 correction-16 证据失信或造成 S0 假绿的发现。实现者的 `READY_FOR_REVIEW` 可作为独立复审输入，但本报告不继承该结论：候选、授权、raw evidence、公共路径、结构/语义 Oracle、资源、网络、逐调用卸载和终态清理均已从冻结对象重新计算。

建议 root 对 V0-S0 裁决 **`STAGE_BASELINE_COMPLETE`**。这是 S0 环境/可实现性基线出口建议，不是 Stage PASS，不是产品质量 E2E，也不把 `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 改为 PASS；四项仍严格为 `NOT_RUN`。授权已因终态收据和图片/视频各一次预算消耗而过期，禁止据此继续运行。

## Findings

本轮无 Fatal、Major 或 Minor finding。为满足可复核要求，下列每一项均给出触发、预期、实际、证据与离线复现；它们是通过项，不是对实现者 PASS 字段的转述。

## 1. 授权、父子链与身份绑定 — PASS

- **位置**：authorization commit；`authorization-correction-16.json`；`candidate-materialization.json`；`harness-identity.json`；`sample-verification.json`。
- **触发**：从 raw evidence 反向追溯正式授权、请求、产品、harness 和样本身份。
- **预期**：`request -> authorization -> evidence -> seal` 为直接父子链；产品/harness commit 可达；执行脚本字节和三项产品文件与授权对象一致；样本 hash 与授权别名一致。
- **实际**：`d04bef7` 的父提交为 request commit `6a09200`，`9d09f3b` 的父提交为 `d04bef7`，`dc09350` 的父提交为 `9d09f3b`；产品和 harness 均为授权提交祖先。request SHA-256 为 `2254983e...`；harness Git blob `c7a3794...`、blob/file SHA-256 均为 `4f3b150d...`。产品 `__init__.py/core.py/nodes.py` 的 SHA-256 分别为 `e96cc472.../fcaec75c.../5206e048...`，与物化记录一致。图片/视频 source hash 分别为 `b4bbd08a.../694a50bf...`，与正式授权一致。
- **证据**：上述五个冻结 JSON；`git show -s --format='%H %P'`；`git rev-parse <commit>:<path>`。
- **复现**：对请求、候选脚本和三项产品 blob 执行 `git show <commit>:<path> | sha256sum`，再与 authorization/candidate-materialization/harness-identity/sample-verification 的字段逐项比较；不读取真实媒体。

## 2. changed_files、artifact manifest 与封存 — PASS

- **位置**：raw evidence commit；`correction-16/artifact-manifest.json`；sealed implementation receipt。
- **触发**：不信任 receipt 自报文件数和 artifact hash，直接遍历 Git tree。
- **预期**：evidence commit 仅新增允许路径；28 个 changed files 与 receipt 完全一致；manifest 每项字节数/hash 匹配；seal 只把 receipt 的 evidence commit 从 pending 改为真实 raw commit。
- **实际**：raw commit 恰有 28 个新增文件：correction-16 目录 27 个加 live receipt 1 个；receipt 列表无重复且与 Git diff 完全同集。manifest 含 26 个非自指 artifact，26/26 的 `bytes` 与 SHA-256 均匹配 Git blob；再加 manifest 自身和 receipt 正好组成 28 项。seal 对 live receipt 仅把全零 commit/`PENDING_ROOT_SEALING` 改为 `9d09f3b...`/`SEALED_BY_GATE_OWNER`。packet manifest 9/9 与 pack 根 manifest 均通过。
- **证据**：`git diff-tree -r 9d09f3b...`；artifact manifest；`git diff 9d09f3b... dc09350... -- implementation-receipt-correction-16-live.json`。
- **复现**：对 manifest 每个 `path` 从 `9d09f3b:<path>` 读取原始 bytes，独立计算 `len` 与 SHA-256；集合比较 `git diff-tree --name-only` 和 receipt `changed_files`。

## 3. 服务前门禁与 no-cloud 网络窗口 — PASS

- **位置**：`preflight-baseline.json`、`pre-model-gate.json`、`owned-ollama-remote-tcp.json`、`ollama-live.log`。
- **触发**：检查历史未知 GPU owner 是否真的在任何 owned service 前解除，以及 no-cloud 是否同时有 raw 与连接观察。
- **预期**：Windows/WSL GPU used 一致且 `<=4096 MiB`；目标进程/8191、11434 listener 均空；server raw 报告 no-cloud true；模型前至少 10 秒、至少 5 个样本且 owned PID 无非 loopback TCP。
- **实际**：Windows/WSL 均为 `3686/24564 MiB`，差值 0；`target_process_count=0`、authorized listeners 空、`service_starts=0`。server raw 含 `OLLAMA_NO_CLOUD:true`。pre-model gate 为 10.020220443 秒、7 样本、nonloopback 0；完整连接文件有 157 个样本、唯一 owned Ollama PID，所有 remote address 仅为 loopback/未连接占位，独立重算非loopback 仍为 0。
- **证据**：四个 artifact；`commands.json` 中 preflight 的逻辑命令和 exit code 0。
- **复现**：离线解析 preflight 的两个 GPU 数组、目标计数和 listener；按连接记录重新分类 remote address；检查 log 中 server config 的 no-cloud 字段。不得调用 `nvidia-smi` 或端口探测。

## 4. 图片公共 `/prompt` 与 `/history` 路径及 Oracle — PASS

- **位置**：`attempt-image-1.json`、`comfy-object-info.json`、`comfy-live.log`、产品候选三文件。
- **触发**：忽略 attempt 的顶层 `pass=true`，从 prompt payload、history 和 raw envelope 重新构造判定。
- **预期**：public `/prompt` 使用注册 `LVWImagePromptBridge`；prompt/history 关联同一 ID；history 完成且输出来自 owner；一个 loopback model envelope 完整停止、schema 严格、observation/prompt 非空且不回显请求。
- **实际**：POST 与 history 均为 200，prompt ID 在提交响应、history 和 execution messages 中一致；workflow 为 `LoadImage -> LVWImagePromptBridge`，object_info 确认公开 output node，Comfy raw log 记录一次 prompt 完成。独立解析一个 envelope 得到 `done=true`、`done_reason=stop`、精确字段集、5 条 observation 和非空 grounded prompt；suggestion 与 raw 的 observation/inference/unknown/prompt/tags 聚合逐字段一致，规范化回显为 false。
- **证据**：上述 artifact；产品 `core.py`/`nodes.py`/`__init__.py` 的注册与 owner 路径。
- **复现**：从 history `outputs["2"].text` 独立 `json.loads` 两层 raw envelope/content，再把 raw 内容重新聚合并等值比较 suggestion；核对 payload、history 和 prompt response 的 prompt ID。

## 5. 视频公共四帧路径及 Oracle — PASS（带 S0 限制）

- **位置**：`attempt-video-1.json`、`media-derivatives.json`、产品候选。
- **触发**：忽略 status 和自报 oracle，重新检查四帧顺序、每帧 envelope、suggestion 与冻结 `camera_motion` string 合同。
- **预期**：四个有序 `LoadImage` 经 `ImageBatch` 送入公开 `LVWVideoFramesPromptBridge`；恰有四个逐帧单图调用；每个 raw schema 完整、observation 非空、不回显请求；`technical.camera_motion` 为非空 string，表达逐帧变化或明确无变化结论。
- **实际**：workflow 顺序为 frame-01..04，源帧索引 `[9,28,46,65]`，四个 derivative hash 互异；history 包含恰好四个有序 raw envelope，全部完整停止且 schema/非空 observation 通过。suggestion 是四帧 observation/inference/unknown 的精确聚合，使用末帧 prompt，`camera_motion` 为四个非空 `change` string 的 `; ` 连接，符合冻结 schema 与 S0 Oracle。
- **限制**：第一帧 observation 未提及手势，后续 observation 提及手势，但各 `change` 均表示无法确认可见变化；这是模型/样本特定的语义质量偏弱，与 correction-08 历史一致。冻结 S0 Oracle 明确接受“无变化结论”，所以不形成本轮 finding；它也正是不能把该探测扩张为 V0-A02 质量 PASS 的原因。
- **证据**：attempt 的 public prompt/history、四个 frame raw responses 与最终 suggestion；`04-acceptance-matrix.md` 的 correction-03 固定 Oracle。
- **复现**：离线解析 `history.outputs["8"].text`，验证四个 envelope 字段/次序，再从四个 content 重建 suggestion 和 camera_motion；无需读取或显示真实媒体。

## 6. 尝试预算、五次调用与逐次卸载 — PASS

- **位置**：两份 attempt、`ollama-request-trace.json`、`ollama-live.log`、三份 after/final `/api/ps` artifact。
- **触发**：复算有效媒体尝试和每个 started call 的 cleanup，不使用 receipt 计数。
- **预期**：图片/视频均不超过 1 次且各 1/1 通过；总模型调用 1+4=5；每次 chat 后紧随一个 keep_alive=0 unload 200；终态 `/api/ps` 空。
- **实际**：仅存在 attempt-image-1 和 attempt-video-1，二者独立 Oracle 均通过。原始 Ollama log 恰有 10 个 POST completion：5 个 `/api/chat` 200 与 5 个 `/api/generate` 200 严格交替；trace 的 line index/status/path 与 raw log 10/10 一致。图片、视频的 t+0/t+5 `/api/ps` 均为空，stop 前终态 `/api/ps` 也为空。
- **证据**：上述 raw artifact；模型调用完成行索引 `352/689/1024/1359/1694`，清理行索引 `353/690/1025/1360/1695`。
- **复现**：只读扫描封存 log 的 `POST "/api/chat"` 与 `POST "/api/generate"`，按原始行序和 HTTP status 复算；解析所有 `/api/ps` JSON 的 `models`。

## 7. GPU/RAM 与停止条件 — PASS

- **位置**：`resource-samples.json`、run summary、receipt。
- **触发**：从 157 个 raw 样本重算峰值/最低 RAM，而非采信 summary。
- **预期**：GPU 每个样本严格 `<23552 MiB`，RAM 基线被记录，无资源 stop。
- **实际**：GPU 最小 3681 MiB，独立最大值为 `22288 MiB`，低于阈值 1264 MiB；host available RAM 独立最小值为 `12047 MiB`。没有达到阈值的样本，summary `resource_stop=false` 与 raw 一致。
- **证据**：157 条 resource sample。
- **复现**：对所有 `samples[].gpu[].used_mib` 求 max，并对 `host_ram_mib.MemAvailable` 求 min；严格比较 `max < 23552`。

## 8. 单一终态清理证明 — PASS

- **位置**：`cleanup.json`；harness `derive_cleanup_proven` 与 finally 消费者。
- **触发**：分别复算 owned Popen、captured PID、listener、temp、target integrity，再检查是否存在平行假绿出口。
- **预期**：两个 created Popen 均终态退出；四个精确 run-owned PID stop 的 after 为空；最终授权端口空；run temp 不存在；pre/post target 六项 bytes/mtime/hash 相同；无 secondary failure。proof 只能由 `owned_resources_absent && integrity==PASS && no secondary` 得出，并约束最终 decision/rc。
- **实际**：两个 Popen 均 `assigned=true/exited=true`；四个 stop after 均空；final listener 空，temp removal exit 0 且 `exists_after=false`；六项 target snapshot 完全相等；secondary list 空。独立公式得到 `owned_resources_absent=true`、integrity PASS、`proven=true`。harness 仅有一个 proof 派生函数；proof false 会降级 decision，未发现 proof false 时仍 READY/rc0 的旁路。
- **证据**：cleanup artifact；harness lines around `derive_cleanup_proven`、finally、summary/receipt 和 return。
- **复现**：从 sealed harness Git blob 静态搜索 `cleanup_proven|derive_cleanup_proven|return 0`，并用 cleanup 的原始子状态重新计算布尔公式。

## 9. 隐私最小化与历史不可改写 — PASS

- **位置**：全部 correction-16 artifact；authorization 的 minimization 条款；Git diffs。
- **触发**：扫描秘密词、认证头、长 Base64、Windows/WSL/home 私有绝对路径、CommandLine 和全量进程表；检查历史 correction 证据是否变化。
- **预期**：只持久化不可逆进程计数、目标匹配、授权 listener/PID 和脱敏诊断；不得保存全量 CommandLine、媒体 Base64、秘密或私有绝对路径；历史失败只增不改。
- **实际**：preflight 仅保存 `windows_process_count=365`、目标计数/空目标数组和空 listener；没有进程 CommandLine 或全量表。命令、temp、Comfy/Ollama 路径均使用 `TEST_SOURCE`、`RUN_TEMP`、`COMFY_ROOT`、`COMFY_PYTHON`、`USER_PROFILE`、`WINDOWS_ABSOLUTE_PATH` 等别名。结构扫描未发现认证秘密、长媒体 Base64、`/mnt/...`、home/user 私有绝对路径；模型日志中的 token 字样为 tokenizer 元数据，不是凭据。request→seal 范围内没有 correction-01..15 历史 artifact 修改，也没有合同或 acceptance case 修改。
- **证据**：全量 artifact 字节扫描；`preflight-baseline.json`、`commands.json`、两份 log、cleanup；`git diff --name-status 6a09200..dc09350`。
- **复现**：从 raw evidence commit 逐 blob 运行结构性正则扫描，只输出 artifact/模式/计数而不输出或解码候选值；再以 Git path diff 排除历史目录变更。

## 10. 固定分母与出口边界 — PASS

- **位置**：`04-acceptance-matrix.md`、`plans/acceptance_cases.json`、sealed receipt。
- **触发**：检查 feasibility attempt 是否被误写为产品 PASS。
- **预期**：固定 ID 指纹不变；四项均 NOT_RUN；本报告只能给 root S0 出口意见。
- **实际**：排序 ID 加 LF 的 SHA-256 独立复算为 `78b158e1...`；计划和 receipt 均保持四项 `NOT_RUN`，计数 denominator 4 / not_run 4 / pass 0。外部动作忠实记录为 run-owned Ollama start 1、Comfy start 1、model calls 5；下载/升级、目标安装写、浏览器、费用均 0。
- **证据**：acceptance matrix、acceptance cases、receipt、request trace。
- **复现**：对 `V0-A01\nV0-A02\nV0-A09\nV0-A10\n` 求 SHA-256；读取四个 case status 和 receipt test_counts/product_acceptance。

## S0 出口建议与限制

1. 建议 root 将 S0 裁决为 `STAGE_BASELINE_COMPLETE`；本报告本身不执行正式裁决，也不宣布 Stage PASS。
2. correction-16 只能证明冻结候选、固定样本和当前目标机上的 S0 feasibility/资源/清理基线；视频变化描述存在已记录的弱语义限制，不能外推为质量保证。
3. `V0-A01/A02/A09/A10` 继续 `NOT_RUN`；其中 A09 的 10 次/P95、A10 的取消/晚到/他人占用等完整分母均未在本次单次 probe 中运行。
4. `AUTH-V0-S0-2026-10-28-16` 已终态过期。任何后续 live 动作必须由新 packet/新授权开启，不能复用本次预算或收据。
