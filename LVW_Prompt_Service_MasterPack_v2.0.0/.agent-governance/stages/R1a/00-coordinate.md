# R1a Coordinate

```text
Project: lvw-prompt-service
Target version: V1
Stage: R1a / 单图简易前端提前切片
Packet version: 1.2.0
State: WAIT_AUTH
Active coordinate: R1a / WP-R1A-04 / GATE4_REAL_ACCEPTANCE
Last passed gate: WP_R1A_03_PACKET_1_2_OFFLINE_CHECKPOINT_PASS
Product candidate: 53b77cfff8a0d57929dd219f24f9d16e5e51a641
Evidence commit: f331622c46903e6fcbff705f2018e58b31194625
```

R1a 1.2.0 将项目负责人明确要求的本机模型服务状态/控制和自定义视觉分析提示纳入当前单图切片。固定分母仍为 `R1A-M01..M07`，不扩张到视频、V1 发布或旧 V0 完整门禁。

当前候选离线 checkpoint 11/11 通过，runtime scan 无发现。旧 `r1a-live-06` 只证明旧候选 `d1d3048...`，保留为历史证据，不能替代当前候选验收。下一步只能在项目负责人批准 `AUTH-REQUEST-V1-R1A-WP-R1A-04-LIVE-07` 后执行一次固定图片、真实 loopback Ollama、headless Chromium 和独立审查；终态后授权自动过期。

在新鲜 live 证据与独立审查完成前，不得进入人工体验签署，不得声明 R1a PASS、V1 PASS 或发布批准。
