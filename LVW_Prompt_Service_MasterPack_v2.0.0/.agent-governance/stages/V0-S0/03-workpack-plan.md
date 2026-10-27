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
