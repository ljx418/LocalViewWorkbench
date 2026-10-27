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
