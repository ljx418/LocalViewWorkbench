# V0-S1 Draft Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Prepared stage: V0-S1 / 图片与独立人工路径
Packet version: 0.2.0-draft
State: DRAFT_BLOCKED_BY_V0-S0
Active coordinate remains: V0-S0 / WP-S0-45 complete / GATE4_REAL_ACCEPTANCE / BLOCKED
Last passed gate: WP_S0_45_INDEPENDENT_REVIEW_COMPLETE
Exact stop reason: RESOURCE_BUSY_UNKNOWN_GPU_OWNER
Product cases: NOT_RUN
Prepared-against commit: b5c78ec3bd1af4be9c9517e191e2fed0a948b05a
Product bridge candidate: 138b4486fdaeb8d207ef6b5efb63a09865f174b9
Accepted S1 baseline: PENDING_V0_S0_EXIT
```

本目录是下一 Stage 文档准备线，不是已冻结或已授权的执行包。它不能改变 `plans/execution-control.json` 的唯一当前坐标，也不能绕过 V0-S0 的 live registry、真实探测、独立审查和 Stage 裁决。

V0-S0 已验证 public `/prompt` 可达 `LVWImagePromptBridge` / `LVWVideoFramesPromptBridge`，且离线修复已通过独立审查；但最近一次逐次授权在 preflight 检出非本运行所有的 GPU 占用后终止并过期，产品固定验收仍为 `NOT_RUN`。项目负责人必须先释放外部占用并重新逐次授权。冻结 V0-S1 前还必须以 V0-S0 正式出口提交替换 accepted baseline，并重新签发 packet/manifest；本草案不能自行跨 Stage。
