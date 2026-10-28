# V0-S1 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Prepared stage: V0-S1 / 图片与独立人工路径
Packet version: 1.0.0
State: RUNNING / OFFLINE_REPOSITORY_ONLY
Active coordinate: V0-S1 / WP-S1-00 / GATE0_DOCUMENT_READY
Last passed gate: V0_S1_GATE0_PACKET_FROZEN
Exact stop reason: none
Product cases: NOT_RUN
Prepared-against commit: dfb00ad462d94628f1aa22045061f66a7629ec01
Product bridge candidate: 138b4486fdaeb8d207ef6b5efb63a09865f174b9
Accepted S1 baseline: dfb00ad462d94628f1aa22045061f66a7629ec01
```

本目录是已冻结的 V0-S1 Stage packet。冻结提交完成前，它不改变 `plans/execution-control.json` 的唯一当前坐标；激活后只授权 packet 允许路径内的离线仓库工作，不能继承 S0 的 live 授权。

V0-S0 已以 `dfb00ad...` 正式闭合：public `/prompt`/`history` 可达 `LVWImagePromptBridge` / `LVWVideoFramesPromptBridge`，correction-16 独立复审 Fatal/Major/Minor 均为 0。S1 可执行 WP-S1-00/01/02 的离线实现；WP-S1-03 的目标 Comfy 安装、Ollama 调用和真实图片运行仍须新的逐次授权。产品固定验收仍为 `NOT_RUN`。
