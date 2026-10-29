# R1a Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V1
Prepared stage: R1a / 单图简易前端提前切片
Packet version: 1.1.0
State: FROZEN_READY_OFFLINE
Active coordinate: R1a / WP-R1A-03 / GATE1_OFFLINE_CORRECTION
Last passed gate: R1A_CONTRACT_CORRECTION_APPROVED
Product candidate: 7735a697591e3207183a2d0714c73078565f8219
Evidence commit: 6bc83e00659af45444d31b1334665adc2bb25b92
Prepared-against commit: f1780de806d4082dbf1d0f8a3ece81cf369aa0e1
```

本包落实 `docs/23_V1_EARLY_FRONTEND_SEQUENCE.md`。项目负责人已批准 `CHANGE-REQUEST-V1-R1A-CONTRACT-01`；packet 1.1.0 使用独立的 `R1A-M01…M07`，不再复用或重解释全局 V1 案例。当前仅授权 wrapper、provider 账本、浏览器 oracle 与依赖收据的离线纠偏和 checkpoint，不授权 Ollama、媒体或浏览器真实运行。R1a 不能在新鲜机器验收和独立审查完成前进入人工体验门槛，也不能声明 `V1_ACCEPTED`。
