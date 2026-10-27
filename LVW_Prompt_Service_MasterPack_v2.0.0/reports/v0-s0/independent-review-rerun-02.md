# V0-S0 / WP-S0-05 独立离线复审

审查日期：2026-10-27  
审查身份：`codex_isolated_reviewer`（会话 `/root/s0_independent_review`）  
应用候选：`95be0cd82c5500b0a71e3597f5188b147f11e75f`  
原始证据提交：`1d4d7303fb670f772825fc3aa488ecf1b1846a96`  
正式收据提交：`511020e0b26e2fe3706094297fb7b433f5bd54ff`  
checkpoint 提交：`afe6b3ac6615a04663dd91a5f091194894b38842`  
审查方式：只读离线复算；未启动 ComfyUI/Ollama，未调用模型或网络，未修改候选、原始证据、合同或治理文件。

## 结论

严重度计数：Fatal **0** / Major **5** / Minor **2**。

推荐 S0 出口：`NO_GO`，精确原因保留为 `NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL`。

证据重跑已实质修复首轮的角色隔离、raw 缺失、changed-files、坐标和候选绑定问题；但独立复算仍确认不存在 Prompt Assistant/Comfy 公开入口到本地 Ollama 的连通生产链。直接 Ollama `/api/chat` 只是分离的本地可行性探测，不是生产 E2E，也不是任何产品用例 PASS。除此以外，视频 raw 暴露了“类型 schema 通过但无可用分析”的假绿，视频 GPU 峰值越过 23 GiB 硬门限，且 no-cloud 与一次失败清理证据仍有门禁级缺口。

`V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 均保持 `NOT_RUN`。本报告不授予 `STAGE_BASELINE_COMPLETE`、V0 PASS、硬件 PASS 或进入 V0-S1 的权限；root Codex 保留最终门禁裁决。

## Findings

### R2-IR-01 — 不存在公开生产入口到本地模型的连通链

- severity: **Major**
- location: `reports/v0-s0/rerun-02/comfy-object-info-raw.json` 的 `ImageCaptionNode`/`VideoCaptionNode`; `reports/v0-s0/rerun-02/pa-models-list-llm-raw.json:1`; `reports/v0-s0/rerun-02/pa-models-list-vision-raw.json:1`; `reports/v0-s0/implementation-receipt-rerun-02.json:129-147,193-196`
- trigger: 按 Stage checkpoint 从真实 Comfy/Prompt Assistant 公开入口追踪同一图片/四帧请求到本地 Ollama owner。
- expected: 注册入口应实际暴露本地 Ollama，或存在可关联的公共请求 trace 将样本、公开入口、模型 digest、响应和终态连成同一生产链。
- actual: 两个节点的 `vlm_service` 仅暴露智谱/xFlow 远程选项；Prompt Assistant 的 Ollama model-list 对 llm/vision 均返回 HTTP 500、`ModelListService is not defined`。成功请求直接发往 Ollama `/api/chat`，与 Comfy registry 观察相互独立，没有 E2E trace。
- evidence: `command-events.json` 仅记录 `/object_info`、两次失败的 `/prompt-assistant/api/models/list` 和两次独立 `/api/chat`；收据也明确 `connected_to_local_model: false`、`end_to_end_claim: false`。
- reproduction: 解析 `comfy-object-info-raw.json` 中两节点的 `vlm_service.options`，确认不含 Ollama；读取两个 model-list raw；再检查 `command-events.json`，不存在从 Comfy/Prompt Assistant 执行入口触发 `/api/chat` 的关联 ID 或调用链。

### R2-IR-02 — 视频“PASS_FEASIBILITY”是只验类型的无可用输出假绿

- severity: **Major**
- location: `reports/v0-s0/rerun-02/ollama-video-attempt-1-response.json:1`; `reports/v0-s0/rerun-02/ollama-video-attempt-1-validation.json:1-15`; `reports/v0-s0/rerun-02/probe-summary.json:29-45`; `reports/v0-s0/implementation-receipt-rerun-02.json:122-124,188-191`; `reports/v0-s0/rerun-02/seal.py:56-62`
- trigger: 独立检查 HTTP 200 响应的实际 JSON 内容，而不是只信 schema-valid 标志。
- expected: 即使只声明 direct-Ollama feasibility，也应证明四帧产生至少一项与媒体有关的可用观察/运动/提示，或诚实分类为 `NO_USABLE_OUTPUT`；schema oracle 应拒绝所有语义字段为空且提示词仅回显请求指令的响应。
- actual: `observations=[]`、`motion=[]`、`unknowns=[]`、`tags=[]`，`video_prompt` 完整回显用户指令，没有描述任何一帧。schema 没有 `minItems`/非空约束，validation 和 self-check 仍将其判为 schema PASS，正式收据进一步标为 `PASS_FEASIBILITY_NOT_PRODUCT_ACCEPTANCE`。
- evidence: raw response 可直接复算上述空数组与回显；`seal.py` 只检查 `json_parse && schema_valid`，没有可用内容 oracle。
- reproduction: 用标准 JSON 解析 response 的 `message.content`，统计四个数组元素总数为 0，并比较 `video_prompt` 与 `command-events.json` 中请求 content；二者相同。该结果虽不能变成产品 PASS，但当前连“可用视频分析 feasibility”也没有证明。

### R2-IR-03 — 视频 GPU 峰值超过冻结的 23 GiB 门限

- severity: **Major**
- location: `reports/v0-s0/rerun-02/resources-video-1.jsonl:52`; `reports/v0-s0/rerun-02/offline-self-check.json:36-43`; `reports/v0-s0/implementation-receipt-rerun-02.json:293-305`; `plans/acceptance_cases.json` 的 `V0-A09`
- trigger: 将原始视频资源序列的最大显存值与 V0-A09 的 `GPU < 23GiB` 断言比较。
- expected: `23 GiB = 23 × 1024 = 23552 MiB`；任何观测值不小于该数都应明确记为门限超出，不能只写“接近容量”或让 offline self-check 全绿。S0 可记录不利基线，但不能将其解释为资源可行性 PASS。
- actual: 独立重算 79 个视频样本的峰值为 `23810 MiB`，比门限高 `258 MiB`，只剩 `754 MiB` 设备余量。收据风险仅称 “close to device capacity”，没有明确指出已越线；self-check 也不包含资源门限断言而报告 `all_passed: true`。
- evidence: 峰值原始行时间为 `2026-10-27T14:47:40.774+08:00`，`gpu_query_exit_code=0`、`gpu_memory_mib="23810, 24564"`；RAM 最小值约 11272.645 MiB，不是本项失败来源。
- reproduction: 对 `resources-video-1.jsonl` 每行取 `gpu_memory_mib` 逗号前整数求 max，再计算 `23810 - 23*1024 = 258`。`V0-A09` 仍是 `NOT_RUN`，所以这是不利 S0 基线，不是正式产品用例 FAIL/PASS。

### R2-IR-04 — no-cloud 控制未生效，零云调用声明缺少可验证边界

- severity: **Major**
- location: `reports/v0-s0/rerun-02/ollama-startup.log:1`; `reports/v0-s0/rerun-02/harness-failure-02-ollama-startup.log:1`; `reports/v0-s0/rerun-02/command-events.json` 的 `start-ollama`; `reports/v0-s0/implementation-receipt-rerun-02.json:271-277`
- trigger: 对照逻辑启动命令中的 `OLLAMA_NO_CLOUD=1` 与服务自身打印的生效配置。
- expected: 授权明确禁止云/付费 Provider；若以 no-cloud 环境变量作为执行边界，服务 raw 应显示该开关生效，或另有出站阻断/网络证据支持 `cloud_or_paid_provider_calls: 0`。
- actual: 最终 run 和第二次失败 run 的逻辑命令都记录 `OLLAMA_NO_CLOUD=1`，但 Ollama 自身 startup raw 明确打印 `OLLAMA_NO_CLOUD:false` 且保留 `OLLAMA_REMOTES:[ollama.com]`。证据没有网络观测或其他出站阻断，因此只能证明调用目标是 loopback，不能独立证明服务进程没有外联。
- evidence: 这是服务自报的运行配置，不是静态默认推断；正式收据仍无条件写 `cloud_or_paid_provider_calls: 0`。
- reproduction: 比较 `command-events.json` 的 `start-ollama.logical_command` 与两个 startup log 第一行。该证据不证明实际发生云调用，但足以否定“no-cloud 已受控并可据此证明零调用”的结论。

### R2-IR-05 — 第一次失败 harness 的 owned Ollama 缺少当次清理闭环

- severity: **Major**
- location: `reports/v0-s0/rerun-02/harness-failure-01-command-events.json:24-60`; `reports/v0-s0/rerun-02/harness-failure-01-cleanup.json:1-7`; `reports/v0-s0/implementation-receipt-rerun-02.json:203-206,279-283`
- trigger: 对每个保留的失败 run 逐次核对 owned PID、stop 命令、最终端口/进程/API ps 与 temp 清理。
- expected: 失败路径与成功路径同样保存 owned service 的停止事件和最终端口/进程状态；未知 owner 或清理失败是 mandatory stop，不能由最终成功 run 的 cleanup 概括替代。
- actual: 第一次失败 run 明确启动并归属 Ollama listener PID 8804，但其 cleanup 只有 `run_temp_removed: true`；没有 stop-ollama、final listeners、最终进程查询或 `/api/ps`。下一 run 能重新启动 Ollama且 GPU compute baseline 为空，是后续间接证据，但不能复算 PID 8804 在第一次失败结束时的清理终态。
- evidence: failure-02 与最终 run 都有更完整 stop/listener 记录，反衬 failure-01 的闭环缺失；正式收据的 `owned_process_and_temp_cleanup: PASS` 只引用最终 `cleanup.json`。
- reproduction: 从 failure-01 command events 取 `owned_listener_pid=8804`，搜索所有 failure-01 artifacts，找不到对应 taskkill/stop、final listener 或 process record。

### R2-IR-06 — 私有/外部动作计数低估了失败 run 的服务启动

- severity: **Minor**
- location: `reports/v0-s0/implementation-receipt-rerun-02.json:271-277`; 三份 `*command-events.json` 的 `start-ollama`/`start-comfy`
- trigger: 将正式收据的 `run_owned_services_started` 与保留的三次 harness 命令历史核对。
- expected: 动作计数覆盖整个授权纠偏 run，包括保留的两次 pre-model 失败，而不只计算最终成功 run。
- actual: 收据写 `run_owned_services_started: 2`。原始事件至少证明三次 Ollama 均成为 run-owned listener（PID 8804、3360、5568）以及最终 Comfy listener（PID 41664），即至少 4 次成功 owned listener；若按启动命令计数则 Ollama/Comfy 合计 6 次。
- evidence: 三份命令事件都被 artifact manifest 封存；两次失败未被删除。
- reproduction: 汇总 `harness-failure-01-command-events.json`、`harness-failure-02-command-events.json`、`command-events.json` 中所有 `step` 以 `start-` 开头且 `note.ready=true`、`owned_listener_pid` 非空的事件。

### R2-IR-07 — 封存后的 `seal.py --verify` 无法复现收据声称的 exit 0

- severity: **Minor**
- location: `reports/v0-s0/implementation-receipt-rerun-02.json:106-114`; `reports/v0-s0/rerun-02/seal.py:188-198`
- trigger: 在 checkpoint 提交上只读运行收据列出的验证命令。
- expected: 正式封存收据应有一个不会写入证据、且能验证最终非零 evidence commit 的可复现命令；若 exit 0 只发生在 placeholder 阶段，应明确绑定执行时点/提交。
- actual: 收据写 `python3 -B .../seal.py --verify` 为 `CONFIRMED_EXIT_0`，但脚本要求 receipt 的 `evidence_commit` 仍为 40 个零且状态以 `PENDING_ROOT_SEALING` 开头。正式收据已正确替换为 `1d4d730...`，所以同一命令现在返回 `failures=["evidence_commit_placeholder"]`、exit 1。
- evidence: 本次离线复现输出 `manifest_artifacts: 55`、唯一失败 `evidence_commit_placeholder`。新的 `tools/verify_governance.py --self-test` 能验证正式 commit binding，但不能让收据列出的旧命令在最终状态复现。
- reproduction: 在包根运行 `python3 -B reports/v0-s0/rerun-02/seal.py --verify; echo $?`，得到 1。

## 假绿判断

存在假绿，但没有被提升为产品 PASS：

1. 视频响应因 schema 只验证字段存在/类型而被标成 `PASS_FEASIBILITY`，实际所有观察类数组为空且提示字段回显请求；这是 Major 假绿。
2. `offline-self-check.json` 写 `all_passed: true`，但未检查 23 GiB 资源门限、no-cloud 生效状态或 failure-01 的清理闭环；结构检查全绿不等于这些运行义务通过。
3. `tools/verify_governance.py` 已比首轮明显改进：它读取真实收据、manifest、changed-files、角色、预算和 NO_GO disposition。报告生成前它以缺少独立报告正确返回 38/1；因此此次没有把工具退出 0 当作 Stage PASS。

## 独立复算通过项

- 提交绑定：`1d4d730^ = 95be0cd`、`511020e^ = 1d4d730`、`afe6b3a^ = 511020e`；证据、收据与 checkpoint 构成直接线性链。
- Artifact manifest：独立复算 55 项 size/sha256 全匹配；manifest 覆盖 rerun-02 下除自身外全部 55 个文件，无缺项/多项；所有 JSON 可解析。
- changed_files：正式收据声明 57 项，与原始证据提交 `1d4d730` 在包内的实际 57 项逐项相等。
- Stage packet：`PAYLOAD_MANIFEST.sha256` 九项全部匹配；`verify_pack.py --schema` 为 921/0。
- 固定分母：排序 ID 加尾随 LF 的 hash 为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`；`plans/acceptance_cases.json`、probe summary、实现收据与 execution control 均保持四项 `NOT_RUN`。
- 样本与帧：图片/视频 hash 与首轮授权样本一致；ffprobe 记录 3.342993 秒、75 视频帧；4 个分箱中心依序为 0.417874/1.253622/2.089371/2.925119 秒，frame hash 四项互异。原媒体和临时帧未进入证据包。
- HTTP/model：命令事件包含方法、loopback URL、状态与脱敏请求参数；model tag/digest 与 tags raw 一致。图片 response 可解析且有实际观察；视频限制见 R2-IR-02。
- 资源：67 个图片样本峰值 23523 MiB，79 个视频样本峰值 23810 MiB；host available RAM 最小值均远高于 2 GiB。资源仅是单次 S0 baseline，绝不构成 V0-A09 的 10 次/P95 验收。
- 最终成功 run 清理：图片/视频后 `/api/ps` 在 t0/t5 均为空；最终 run 的 owned Comfy/Ollama taskkill exit 0、8188/11434 最终监听为空、4 个临时帧已删除、配置源字节 before/after hash 相同。第一次失败 run 的限制见 R2-IR-05。
- 路径/秘密：未检出真实 Windows/WSL/home 绝对私有路径、Cookie、Bearer token、原媒体或明文 Provider key；证据使用 `COMFY_ROOT`、`TEST_SOURCE`、`RUN_TEMP`、`USER_PROFILE`、`ABSOLUTE_PATH_REDACTED`。masked config 只保留 key 是否存在。
- 角色隔离：授权将 WP-S0-04 指派给 `/root/s0_rerun_implementer`，本报告由不同会话 `/root/s0_independent_review` 完成，root 会话仍是 gate owner；未发现 rerun-02 的实现/复审身份碰撞。
- 失败保留：两次 pre-model harness failure、首轮失败账本和首轮独立审查均仍存在；本轮各 1 次有效模型调用，未超每类 2 次预算。

## S0 出口限制

- root 应裁决 `NO_GO`，不得裁决 `STAGE_BASELINE_COMPLETE`。核心技术原因是缺少连通公开生产入口；R2-IR-02 至 R2-IR-05 进一步禁止把 direct-Ollama/schema/资源/清理摘要包装成 baseline 全绿。
- 若未来修复 Prompt Assistant 或实现 `lvw_v0_bridge`，必须另建冻结 workpack/授权后重跑同一公开入口 E2E；不得把本轮直接 Ollama 结果回填成 V0-A01/A02 PASS。
- 视频输出 oracle 应加入非空/可用内容和 prompt-echo 拒绝；资源报告应明确 `23810 MiB > 23 GiB`；no-cloud 应以服务实际生效配置或独立出站阻断证明；所有失败路径应逐次闭合 owned process/port/API ps/temp/config 清理。
- 下一 Stage 仍需新 packet，四项正式产品验收保持 `NOT_RUN`。
