# R1a Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V1
Prepared stage: R1a / 单图简易前端提前切片
Packet version: 1.0.0
State: WAIT_AUTH
Active coordinate: R1a / WP-R1A-00 / GATE0_CONTRACT_CORRECTION
Last passed gate: WP_R1A_03_OFFLINE_CHECKPOINT_PASS
Product candidate: 7735a697591e3207183a2d0714c73078565f8219
Evidence commit: 6bc83e00659af45444d31b1334665adc2bb25b92
Prepared-against commit: fc5f8afda6b78ca710f8f03605690a5b1f08355d
```

本包落实 `docs/23_V1_EARLY_FRONTEND_SEQUENCE.md`。`AUTH-V1-R1A-2026-10-29-LIVE-02` 已在 Ollama owner 记录超时后生成终态收据并自动过期；独立审查为 Fatal 0 / Major 5。门禁复核进一步发现 R1a matrix 复用了全局验收 ID 但改变了义务含义，因此当前停止所有实现与真实运行，等待 `CHANGE-REQUEST-V1-R1A-CONTRACT-01` 裁决。R1a 不能进入人工体验门槛，也不能声明 `V1_ACCEPTED`。
