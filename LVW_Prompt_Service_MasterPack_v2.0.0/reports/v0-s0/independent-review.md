# V0-S0 独立复算报告

审查日期：2026-10-27  
审查身份：V0-S0 隔离独立审查者  
应用候选：`3fb04084c50f0ef9b6bd133fe77f90bea44e6ffa`  
证据封存提交：`08d41fc7970018ee1b9bf8853e508a7f084a0415`  
审查方式：仅使用仓库内冻结 packet、提交对象和已封存证据；未启动 ComfyUI/Ollama，未调用模型或网络。

## 结论

推荐 S0 状态：`BLOCKED`。

`STAGE_BASELINE_COMPLETE` 的必要条件尚未满足。结构性校验、候选绑定、固定分母和脱敏检查通过，但存在 5 项 Major 与 2 项 Minor。冻结 checkpoint 明确要求 Fatal/Major 为零才允许 baseline 出口，因此当前证据只能支持“已有可行性观察与明确技术缺口”，不能支持已独立证明的 Stage baseline 完成。

严重度计数：Fatal **0** / Major **5** / Minor **2**。

限制：本结论不否定收据中记录的现场观察本身；它判定的是这些观察是否达到冻结 packet 要求的可独立复算、角色隔离和门禁一致性。四个产品用例 `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 均保持 `NOT_RUN`，本报告不授予任何产品 PASS。

## Findings

### IR-01 — 运行事实缺少可独立复算的原始证据

- severity: **Major**
- location: `reports/v0-s0/steps_or_command.log:5-23`; `reports/v0-s0/live-probe-receipt.json:41-105`; `reports/v0-s0/evidence-sha256.json:8-18`
- trigger: 独立审查者尝试从封存证据复算 HTTP 请求/响应、节点注册表、模型原始输出、命令退出码、GPU/RAM 采样和最终端口/进程清理。
- expected: 按 `06-implementation-prompt.md`、`07-checkpoint-plan.md` 和 WP-S0-02，保存 raw、配置、命令与退出码、资源观察和清理证明，并由 hash manifest 绑定；手写摘要不能替代原始日志。
- actual: `steps_or_command.log` 自称 navigation receipt，只列 PASS/FAIL 叙述，没有精确命令、退出码或原始输出；`live-probe-receipt.json` 仍是摘要观察。封存 artifact 列表中没有 registry/HTTP raw、完整失败响应、ffprobe/ffmpeg 命令输出、GPU/RAM 采样序列、端口/进程查询输出或清理前后清单。因此节点、模型、峰值资源、卸载和清理结论无法从仓库证据独立重算。
- evidence: 九个 artifact 的 sha256 均可复算一致，但它们绑定的是摘要文件；hash 完整性不能补足来源证据。尤其成功图片只保存了部分语义摘要，两个视频失败仅保存错误描述，没有完整 raw。
- reproduction: 运行 `find reports/v0-s0 -maxdepth 2 -type f -print`，再检查 `steps_or_command.log` 与 `live-probe-receipt.json`；没有任何被引用的 raw/command/resource/cleanup artifact。运行证据 manifest 校验只会验证现有摘要文件哈希。

### IR-02 — 实际实现者与冻结角色隔离规则冲突

- severity: **Major**
- location: `.agent-governance/stages/V0-S0/stage-control.json` 的 `roles`、WP-S0-01/WP-S0-02 owner；`reports/v0-s0/implementation-receipt.json:43-51`
- trigger: 将实现收据中的真实执行会话与 Stage packet 的实现 owner/gate owner 对照。
- expected: WP-S0-01/02 由 `claudecode_minimax` 执行，`codex_sol` 保持 gate owner，独立审查由隔离 reviewer 执行；架构、实现和独立复算三方分离。
- actual: 收据明确记录 `implementation_session = codex-gate-owner-live-probe-20261027`，并承认 gate-owner context 执行了探测。独立审查只能避免执行者自签独立报告，不能恢复 gate owner 未参与实现这一冻结职责分离。
- evidence: `implementation-receipt.json:48-51` 的风险和 decision 均承认 `ROLE_DEVIATION`；这不是推断出来的身份碰撞。
- reproduction: 读取 `stage-control.json` 中 `roles.gate_owner`、`roles.implementation_owners` 及 WP owner，再与 `implementation-receipt.json` 的 `implementation_session` 比较。

### IR-03 — “公开生产入口”链路没有形成可审计的端到端调用证据

- severity: **Major**
- location: `reports/v0-s0/implementation-receipt.json:23-36`; `reports/node-bindings.json` 的 `image_caption`、`video_caption`、`native_local_vision`；`reports/v0-s0/live-probe-receipt.json:41-95`
- trigger: 按 checkpoint 从真实公开入口追踪单图与四帧调用，并确认 owner，而不是把注册表查询和另一服务的直接调用拼接成生产链。
- expected: 证据能把输入样本、注册入口、实际 owner 调用、模型 digest、响应和终态串成同一条可追踪链；若该链不存在，应明确以缺口结论封存，不能将分离的可行性探测表述为已验证 production path。
- actual: ComfyUI/Prompt Assistant 只证明了 object registry、失败的 model discovery 和 video/info 行为；图像与四帧推理则直接调用 Ollama `/api/chat`。现有 ImageCaptionNode 没有 Ollama 选项，VideoCaptionNode 也不满足固定四帧/有界解码；计划中的 `lvw_v0_bridge` 尚不存在。因此仓库没有“注册节点/API → 实际本地模型”的同一次请求链证据。
- evidence: `node-bindings.json` 同时写明 `ollama_option_present: false`、视频 owner `DO_NOT_REUSE_AS_V0_VIDEO_OWNER`，以及 Ollama 仅可在未来 LVW adapter 后复用；`implementation-receipt.json` 把这些端点并排列出，但没有 correlation/request ID 或原始 trace 将其连接。
- reproduction: 对照 `production_paths` 与 `checks`；能找到 registry GET 和直接 Ollama POST 的摘要，却找不到 ImageCaptionNode/VideoCaptionNode 经公共执行入口处理该样本的请求或计划 bridge 的实现/调用。

### IR-04 — 执行坐标未反映预算耗尽和已进入独立审查，可能诱发重复探测

- severity: **Major**
- location: `plans/execution-control.json:7-31`; `reports/v0-s0/live-probe-receipt.json:117-121`; `reports/v0-s0/implementation-receipt.json:50-52`
- trigger: 在证据封存提交上读取权威执行坐标并依其 `next_action` 继续工作。
- expected: 两次有效尝试耗尽后停止；坐标应指向 WP-S0-03/checkpoint（或明确 WAIT/BLOCKED），记录 exact stop reason，不再要求重复执行单图/四帧探测。
- actual: 收据记录 image/video 均已用满 2 次且 ready for independent review；但 `execution-control.json` 仍停在 WP-S0-01，`current_blocking_gate` 与 `exact_stop_reason` 均为 null，`next_action` 仍要求查询并执行单图和四帧探测，`next_owner` 仍是实现者。
- evidence: 同一提交内权威 control 与 implementation/live receipt 相互矛盾。照 control 执行会重做已完成的外部动作，并可能突破同路线重试预算。
- reproduction: 比较上述三个文件的 workpack、next action、retry accounting、decision 和 exact stop reason。

### IR-05 — 治理校验器对真实收据/证据不做校验，可产生结构性假绿

- severity: **Major**
- location: `tools/verify_governance.py:126-141,184-191,225-260`
- trigger: 在当前证据提交执行 `python3 tools/verify_governance.py --self-test`。
- expected: 校验器至少应读取实际 implementation/live receipt，验证候选 SHA、固定分母计数、重试上限、实际角色、evidence manifest、执行坐标和证据存在性/哈希；发现 Major 级偏差时不得给出零失败的门禁外观。
- actual: `validate_receipt()` 只用于两个合成 self-test，从未用于实际 `implementation-receipt.json`；live receipt 仅通过“文件是否存在”设置 `target_runtime_touched`。工具不检查实际 candidate、角色偏差、重试账本、raw 缺失或 stale workpack，因此在 IR-01 至 IR-04 均存在时仍返回 `passed: 27, failed: 0, exit 0`。
- evidence: 本次离线执行的实际输出为 27/0；源代码在 251-259 行仅检查 `live-probe-receipt.json.is_file()`，没有加载该文件。
- reproduction: 执行 `python3 tools/verify_governance.py --self-test`；再阅读 `main()`，检索 `validate_receipt(` 可见实际收据没有调用点。

### IR-06 — changed_files 收据与证据提交实际变更集不一致

- severity: **Minor**
- location: `reports/v0-s0/implementation-receipt.json:17-20`; commit `08d41fc7970018ee1b9bf8853e508a7f084a0415`
- trigger: 将收据宣告的 changed files 与封存提交的 `git show --name-status` 比较。
- expected: 实现 prompt 要求交付完整 changed files，便于审计 evidence-only 提交的范围。
- actual: 收据只列 6 个文件；封存提交实际修改/新增 12 个文件，遗漏 `MANIFEST.sha256`、`reports/governance-validation.json`、`evidence-sha256.json`、`static-audit.md`、`steps_or_command.log` 和 `tools/verify_governance.py`。
- evidence: Git 提交对象提供可复算的真实变更列表。
- reproduction: 运行 `git show --name-status --format= 08d41fc7970018ee1b9bf8853e508a7f084a0415`，与 receipt 的 `changed_files` 数组求差集。

### IR-07 — 报告使用了 Stage packet 未允许的出口标签

- severity: **Minor**
- location: `reports/node-bindings.json` 的 `gate_effect.recommended_stage_conclusion`
- trigger: 将推荐出口值与 `stage-control.json.stage_exit.allowed` 比较。
- expected: S0 结论只能是 `STAGE_BASELINE_COMPLETE`、`NO_GO`、`BLOCKED`、`WAIT_BUDGET` 或 `WAIT_AUTH`，限制应另列。
- actual: 报告写入 `STAGE_BASELINE_COMPLETE_WITH_REUSE_RESTRICTIONS`，该值不在冻结枚举内。虽然当前权威 coordinate 仍为 RUNNING，这个非标准标签可能被下游误当成合法出口。
- evidence: packet 的 `04-acceptance-matrix.md`、`07-checkpoint-plan.md` 与 `stage-control.json` 三处均给出相同的五值枚举。
- reproduction: 读取 `node-bindings.json` 的推荐值，并检查其是否属于 `stage-control.json.stage_exit.allowed`。

## 独立复算通过项

- 候选/证据绑定：`08d41fc^` 精确等于 `3fb04084c50f0ef9b6bd133fe77f90bea44e6ffa`，候选是证据提交的直接父提交；所有主要收据中的 candidate SHA 一致。
- Manifest/hash：Stage `PAYLOAD_MANIFEST.sha256` 全部通过；全局 `MANIFEST.sha256` 通过；`evidence-sha256.json` 中九项 artifact 均匹配当前字节。
- 固定分母：四项 ID 为 `V0-A01,V0-A02,V0-A09,V0-A10`，按排序、LF 连接并保留尾随 LF 的 SHA-256 为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。
- 产品状态：`plans/acceptance_cases.json`、execution control、live receipt 和 implementation receipt 均保持 4/4 `NOT_RUN`；没有把 V0 产品用例标为 PASS。
- 重试/失败保留：账面上 image=2、video=2，未声明额外尝试；失败 ledger 保留了命令格式、损坏缓存、model discovery、图片首次失败、视频两次失败和绝对路径问题。限制见 IR-01：失败 raw 未封存。
- 路径/隐私：在指定公开报告中未检出 Windows/WSL/home 绝对私有路径、凭据或原媒体；样本以 alias/hash 表示。实际 Prompt Assistant 接受并返回绝对路径的问题被明确记为 `FAIL_SECURITY`，未被洗绿。
- 清理：摘要一致声称 owned 服务、监听端口、模型和临时帧已清理，没有宣称 kill 他人进程。限制见 IR-01：缺少可独立验证的原始进程、端口和资源输出。
- 离线结构校验：`python3 tools/verify_pack.py --schema` 返回 883/0；`python3 tools/verify_governance.py --self-test` 返回 27/0。后者只代表其当前覆盖范围，不能抵消 IR-05。

## 解除 BLOCKED 的最小条件

1. 由冻结实现 owner 或经正式 packet 变更授权的新 owner，重新产出职责合规的实现收据；gate owner 不再兼任运行实现者。
2. 在新的明确授权/预算下补齐可脱敏封存的 raw 命令、退出码、HTTP/registry/model 输出、资源采样和清理输出；不得删除本轮失败 ledger，也不得把本轮视频失败改写成 PASS。
3. 若 S0 仍要求生产入口链路，提供同一 request/sample 的公开入口到真实 owner 的可关联 trace；若现有链路不存在，则以明确 `BLOCKED`/`NO_GO` 缺口收口，不用直接 Ollama 可行性替代。
4. 同步 execution control 到 WP-S0-03/checkpoint 或合法等待/阻断状态，保留重试耗尽的 exact stop reason，避免重复调用。
5. 扩展治理校验器以校验真实收据、候选、角色、预算、evidence hashes 与执行坐标；修正 changed-files 清单和非法出口标签后再次独立复算。
