# R1a Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V1
Prepared stage: R1a / 单图简易前端提前切片
Packet version: 1.0.0
State: WAIT_AUTH
Active coordinate: R1a / WP-R1A-04 / GATE4_REAL_ACCEPTANCE
Last passed gate: WP_R1A_03_OFFLINE_CHECKPOINT_PASS
Product candidate: 7735a697591e3207183a2d0714c73078565f8219
Evidence commit: 6bc83e00659af45444d31b1334665adc2bb25b92
Prepared-against commit: fc5f8afda6b78ca710f8f03605690a5b1f08355d
```

本包落实 `docs/23_V1_EARLY_FRONTEND_SEQUENCE.md`。`AUTH-V1-R1A-2026-10-29-LIVE-01` 的失败与 Fatal 0 / Major 4 独立审查已封存；双域端口、进程所有权和证据纠偏候选已通过新的离线 checkpoint。当前请求 `AUTH-REQUEST-V1-R1A-WP-R1A-04-LIVE-02` 尚未批准，不授权任何真实 Ollama、媒体或浏览器运行。R1a 不能进入人工体验门槛，也不能声明 `V1_ACCEPTED`。
