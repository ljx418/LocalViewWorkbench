# V0-S0 Workpack Plan

## WP-S0-00：离线治理预检

Owner：可信执行器。运行 MasterPack 与治理校验，确认 packet、合同、分母和 manifest 未漂移。无外部动作。完成只表示可以等待目标机授权。

## WP-S0-01：目标环境只读盘点

Owner：Claude Code + MiniMax。依赖 WP-S0-00 和一次明确授权。只读收集版本、digest、节点注册、许可证/来源、配置摘要和路径脱敏 hash。不得修改环境。输出 `reports/runtime-inventory.json`、`reports/node-bindings.json`、`reports/reuse-audit.md`。

## WP-S0-02：单图与四帧最小真实探测

Owner：Claude Code + MiniMax。依赖 WP-S0-01、授权样本和本地服务预算。走真实注册入口，保存 raw、配置、模型 digest、样本 hash、计时、GPU/RAM 和清理观察。最多两次有效重试；同路线两次无新证据即停止。

## WP-S0-03：独立复算与 checkpoint

Owner：独立 DeepSeek 会话执行只读复算；Codex + Sol 裁决。核对生产入口、固定四项 Stage 分母、证据绑定、失败历史和清理。实现者不得参与独立签署。

Workpack 按顺序执行。WP-S0-00 完成不能自动授权 WP-S0-01；S0 结束也不能自动进入 V0-S1。

## WP-S0-04：独立上下文纠偏重跑

Owner：`codex_isolated_implementer`。依赖首轮 WP-S0-03 独立审查和 `AUTH-V0-S0-2026-10-27-02`。使用同一获授权样本与本地服务，通过确定性 harness 保存脱敏 raw 命令、退出码、registry/HTTP/model 响应、GPU/RAM 序列及进程/端口清理。图片/视频各最多两次有效尝试；不得修改产品合同、目标配置或首轮失败证据。输出仅限 `reports/v0-s0/rerun-02/` 及新版实现收据。

## WP-S0-05：隔离复审与二次 checkpoint

Owner：`codex_isolated_reviewer`。依赖 WP-S0-04。只读复算新 run、旧失败、角色身份、候选、manifest、raw、路径脱敏和清理。不得修改候选或由实现会话复审。之后由 root Codex 根据 Fatal/Major 裁决。

## WP-S0-06：薄 bridge 离线实现

Owner：`codex_isolated_implementer`。依赖 WP-S0-05 与 root 的 NO-GO 裁决。仅在仓库内新增 `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/`：注册真实 Comfy 节点，唯一模型端点固定为 loopback Ollama；图片最多一张，视频基线最多四帧且逐帧请求；每帧缩放上限、`num_ctx`/`num_predict`、超时、`keep_alive=0` 明确。所有语义字段为空、提示回显、`done_reason=length`、非 JSON 和 schema 错误均 fail-closed，不得覆盖人工稿。禁止写目标 Comfy 安装、修改 Prompt Assistant、下载或启动服务。

## WP-S0-07：离线合同与故障测试

Owner：`codex_isolated_implementer`。依赖 WP-S0-06。用 fake loopback transport 测试公开节点 owner，而不是绕过核心：正常图片、顺序四帧、空语义、提示回显、非法 JSON、超帧、超像素、非 loopback、超时、逐请求 `keep_alive=0` 和 finally 清理。输出实现收据；只可报告 READY_FOR_REVIEW，不得报告 Stage PASS。

## WP-S0-08：新鲜公开入口真实验证

Owner：`codex_isolated_implementer`。依赖 WP-S0-07 和新的有限运行记录。把封存候选以可恢复方式挂载到独立测试位置，从 Comfy `/prompt` 真实公开入口驱动图片与四帧，保存 workflow、prompt/history trace、Ollama raw、内容 oracle、GPU/RAM、owned PID/端口/连接和每次失败/成功清理。图片/视频各最多两次有效尝试；不修改原安装的 Prompt Assistant 或永久配置。

## WP-S0-09：隔离三次复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-08。独立复算五个 Major、两个 Minor、生产 trace、资源阈值、无远程连接观察、逐次清理、候选/证据绑定和固定分母 NOT_RUN；root Codex 保留最终 S0 裁决。

## WP-S0-10：Windows 原生 no-cloud 启动纠偏与真实验证

Owner：`codex_isolated_implementer`。依赖 WP-S0-08 的网络 NO-GO 证据与 `AUTH-V0-S0-2026-10-27-04`。先用 Windows 原生命令进程内设置 `OLLAMA_NO_CLOUD=1`，必须从 server raw 观察 true，并在至少 10 秒、5 个样本内确认 owned PID 无非 loopback TCP，之后才可启动临时 Comfy 与各一次图片/视频 `/prompt`。不得修改防火墙、注册表、永久环境或候选。

## WP-S0-11：correction-04 隔离复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-10。独立复算 no-cloud 生效、完整窗口连接观察、public `/prompt` trace、semantic oracle、逐帧调用、资源、逐 run 清理和所有历史失败；root Codex 保留最终裁决。

## WP-S0-12：Windows 路径转换纠偏与真实验证

Owner：`codex_isolated_implementer`。依赖 WP-S0-10 的 no-cloud PASS / Comfy-path BLOCKED 证据与 `AUTH-V0-S0-2026-10-27-05`。仅将 Comfy `main.py` 与 cwd 经 `wslpath -w` 后传给 Windows Python；其他网络、资源、媒体、候选与清理门限完全沿用。成功后各执行一次真实图片/四帧 `/prompt`。

## WP-S0-13：correction-05 隔离复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-12。统一复算 correction-03/04/05、公开生产 trace、semantic oracle、资源、网络、逐次清理和固定分母 NOT_RUN；root Codex 保留最终 S0 裁决。

## WP-S0-14：视频 prompt 交接合同纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-12 的 `PROMPT_ECHO` 证据。只允许修改 bridge 的模型请求指令：明确 `prompt` 是基于可见事实的生成提示，不得复制系统请求或用户指令；不得放宽现有 exact-echo Oracle、响应 schema、公共错误码、媒体/资源限制或 loopback 边界。不得启动 ComfyUI/Ollama。

## WP-S0-15：纠偏离线合同测试与收据

Owner：`codex_isolated_implementer`。依赖 WP-S0-14。通过公开节点 owner 证明图片/四帧正常路径、请求明确包含 anti-copy 与 grounding 义务、用户指令回显和完整请求回显仍 fail-closed、每次已启动调用均清理。运行目标 Python 和 portable Python 测试，形成新候选与实现收据，只能 `READY_FOR_REVIEW`。

## WP-S0-16：新候选真实视频闭环

Owner：`codex_isolated_implementer`。依赖 WP-S0-15 和新的候选绑定有限运行记录。沿用 correction-05 的 Windows-native no-cloud、路径转换、网络/显存/清理门限；图片与四帧视频各最多一次有效尝试。旧授权不得复用，开始前必须由 root 冻结新授权文件。

## WP-S0-17：correction-06 隔离复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-16。独立复算候选、图片/四帧公共 trace、语义 Oracle、请求次数、资源、网络、逐次清理、历史失败不可改写和固定分母 NOT_RUN；root Codex 保留最终 S0 裁决。

## WP-S0-18：可复用 live harness 纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-17 与 `gpu-owner-clearance.md`。从 correction-06 probe 提取可复用 `tools/v0_s0_live_probe.py`，在任何 owned service 前使用 Windows-native `nvidia-smi.exe` 与进程/端口枚举；baseline used 必须 `<=4096 MiB`，且不得存在 Comfy portable Python、Ollama 或 8191/11434 listener。超出或无法归属即 fail-closed。修复超时路径：保留 history 中的 `MODEL_TIMEOUT` 首因；cleanup 是否完成按同一调用计数、cleanup 200、终态 `/api/ps` 空及最终清理组合判断，服务端完成日志顺序只作诊断。

## WP-S0-19：harness 离线负例与收据

Owner：`codex_isolated_implementer`。依赖 WP-S0-18。不得启动服务。自测至少覆盖：干净 Windows baseline、>4096 MiB、未知目标进程/端口、正常 chat→cleanup、超时 cleanup→chat499 且终态空、缺 cleanup、history error 首因保留。执行 AST、help/self-check 和治理回归，生成离线收据，只能 READY_FOR_REVIEW。

## WP-S0-20：correction-07 最终同路线真实尝试

Owner：`codex_isolated_implementer`。依赖 WP-S0-19、新候选绑定授权与通过的服务前 GPU preflight。使用候选 `138b448...`，图片/视频各最多一次；这是该路线第二次且最后一次有效尝试。同类失败且无新证据后必须停止，不得继续重跑。

## WP-S0-21：correction-07 隔离复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-20。独立复算 harness、preflight、候选、公共图片/视频 trace、语义、资源、网络、清理及全部历史失败；root 保留正式裁决。

## WP-S0-22：PowerShell 编码与原子终态纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-21。仅修改可复用 harness：PowerShell 强制 UTF-8 输出，Python 以 bytes 接收后 strict UTF-8 解码；任何进程/端口枚举异常都先写 fail-closed `preflight-baseline.json`。finally/receipt 对所有未到达 artifact 使用显式 `NOT_REACHED`，不得二次异常或覆盖首因。

## WP-S0-23：编码与 failure-finalization 离线负例

Owner：`codex_isolated_implementer`。依赖 WP-S0-22。新增非 UTF-8 raw、PowerShell UTF-8、preflight 首段异常、缺 artifact receipt、原子 BLOCKED receipt 和既有 19 项回归；不得启动服务。封存 harness 与离线收据。

## WP-S0-24：最终有效媒体尝试

Owner：`codex_isolated_implementer`。依赖 WP-S0-23 和新的明确授权。有效媒体预算仍为图片 1、视频 1；产品候选不变。这是同路线最后一次有效媒体尝试，任何媒体失败后停止。

## WP-S0-25：最终 S0 隔离复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-24。独立复算所有门禁和历史失败；root 根据 Fatal/Major 作 S0 正式裁决。

## WP-S0-26：隐私最小化、Oracle 类型与 Harness 自绑定纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-25 与 root NO-GO。仅离线修改 live harness：preflight 只持久化目标进程/端口匹配及不可逆计数，不保存全量进程或命令行；`camera_motion` 严格按冻结 schema 的非空 string 验证；服务启动前必须把实际脚本 SHA-256 与指定 harness commit blob 复算一致并写入独立 artifact/receipt。禁止修改产品候选、合同、阈值、历史原始提交或启动服务。

## WP-S0-27：三项发现离线负例与实现收据

Owner：`codex_isolated_implementer`。依赖 WP-S0-26。新增全量进程命令行不得落盘、Base64-shaped user/path 不得进入 artifact、string camera_motion 通过/list 拒绝、harness hash match/mismatch fail-closed 且零服务启动测试；保留既有 24 项。输出 correction-09 offline receipt，只能 READY_FOR_REVIEW。

## WP-S0-28：correction-09 独立离线复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-27。独立复算 F-01/M-01/M-02 是否在新候选中关闭、旧泄漏是否仍隔离、历史结论是否未改写；不得启动服务或推断新的 live 授权。root 再决定 S0 的离线出口。

## WP-S0-29：身份闭合且证据最小化的 S0 证明运行

Owner：`codex_isolated_implementer`。依赖 WP-S0-28 与新的明确授权。绑定产品候选 `138b448...`、harness 候选 `d1f268f...`、固定样本和图片/视频各一次预算；任何服务前必须通过 harness commit/blob/file 自绑定、GPU/owner/port gate。只保存目标匹配与不可逆计数；继续执行 no-cloud、非 loopback、资源、逐调用卸载和最终完整性门禁。终态即过期，禁止自动重跑。

## WP-S0-30：S0 baseline 独立出口复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-29。独立复算新鲜证据、身份、隐私、公开图片/四帧路径、Oracle、资源、网络和清理，并保留全部历史失败。仅 Fatal=0、Major=0 且 S0 固定四项都有阶段结论时，root 才可裁决 `STAGE_BASELINE_COMPLETE`；这仍不等于 V0 产品用例 PASS。

## WP-S0-31：前置阻断后的可观察状态语义纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-30 的 Minor 发现。仅离线修改可复用 harness：身份或 Windows-native service preflight 在任何 owned service 启动前阻断时，no-cloud、remote TCP、Comfy 路径转换和图片/视频公开路由必须报告 `NOT_REACHED`，不得报告 `FAIL` 或 `NOT_RUN_OR_FAIL`。`cleanup.proven=false` 保持真实，同时分别报告 `owned_resources_absent=true` 与 `target_integrity_comparison=NOT_REACHED`；若 owned service 曾启动或相应检查确实执行，则失败仍必须报告 `FAIL`。禁止修改 correction-10 原始证据、产品候选、公共合同、GPU/超时阈值或启动服务。

## WP-S0-32：状态分支离线负例与实现收据

Owner：`codex_isolated_implementer`。依赖 WP-S0-31。新增至少覆盖 harness identity mismatch、GPU preflight stop、preflight 枚举异常、服务启动后的实际检查失败和成功清理的离线测试；证明前置阻断不会产生假失败、后置失败不会被伪装为未到达。保留全部既有 harness 回归，输出 correction-11 离线实现收据，只能 `READY_FOR_REVIEW`；固定四项产品分母保持 `NOT_RUN`。

## WP-S0-33：correction-11 独立离线复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-32。只读复算新状态机、负例、候选/收据绑定和历史 correction-10 不可改写；确认 Fatal/Major/Minor 以及是否可回到等待 GPU owner 释放的真实运行门禁。独立复审不得修改候选或推断 live 授权。

## WP-S0-34：owned Popen 终态与清理 fail-closed 纠偏

Owner：`codex_isolated_implementer`。依赖 WP-S0-33 的 M-01。仅离线修改 live harness：每个已创建的 owned `Popen` 必须保持为待清理资源，直到 `poll()`/成功 `wait()` 明确证明退出；wait timeout/异常必须记录稳定的 secondary cleanup failure，并使 `owned_resources_absent=false`、`cleanup.proven=false`、cleanup check=`FAIL`。可对本 run 自己创建的精确 Popen 做有界 terminate/kill 清理，但禁止触碰未知或非 owned 进程。禁止修改历史 evidence、公共合同、阈值或启动服务。

## WP-S0-35：lingering-Popen 完整负例与实现收据

Owner：`codex_isolated_implementer`。依赖 WP-S0-34。新增完整 `Probe.run()` 离线 fixture：Popen 已创建、PID 未捕获、wait 超时且 poll 仍存活时，start=1 且 absence/proven/PASS 全部不得为真；同时覆盖 Popen 正常退出的成功清理分支、wait 异常和两个 owned Popen 的组合。保留 correction-11 全部测试，输出 correction-12 离线收据，只能 `READY_FOR_REVIEW`，产品四项保持 `NOT_RUN`。

## WP-S0-36：correction-12 独立离线复审

Owner：`codex_isolated_reviewer`。依赖 WP-S0-35。隔离复算 M-01、完整 run-level 负例、owned 边界、候选/收据绑定和历史 evidence 不可改写。Fatal/Major 必须为零才可建议关闭离线纠偏；不得修改候选、启动服务或宣布 Stage PASS。
