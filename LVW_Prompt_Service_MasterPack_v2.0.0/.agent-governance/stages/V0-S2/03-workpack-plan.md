# V0-S2 Workpack Plan

- **WP-S2-00 合同与复用冻结**：核对 R1a 签署、V0-Min 证据、FFmpeg 身份、testSource 样本清单和现有 Bridge；不得运行目标服务。
- **WP-S2-01 视频媒体 owner**：实现本地文件边界、ffprobe/受控 PyAV 元数据解析、有界 FFmpeg 四帧采样、帧 manifest 和 run-owned 清理。
- **WP-S2-02 视频工作流**：交付 `video_reverse_prompt_v0.ui.json/.api.json`，公共 Comfy 入口接线，raw/建议/人工稿分离。
- **WP-S2-03 安全、取消和资源 owner**：路径/UNC/reparse/损坏/超限负例；单槽锁、cancel epoch、晚到丢弃、卸载与非 owned 保护。
- **WP-S2-04 离线 checkpoint**：定向、合同负例、V0-Min 回归、工作流静态校验、Harness 语法和反假绿扫描。
- **WP-S2-05 真实 Stage checkpoint**：母授权内先生成候选绑定子授权；执行固定媒体、10 次资源分母、取消和完整清理，一次完整 checkpoint。
- **WP-S2-06 独立审查与门禁**：隔离复算四项 Stage 分母和九项 V0.1 累计分母；Fatal=0、Major=0 后由 Codex 裁决。

Stage 内 WP-S2-01 至 04 可连续开发；合同变化、R1a 未签署、真实动作无子授权或 checkpoint 超预算必须停止。
