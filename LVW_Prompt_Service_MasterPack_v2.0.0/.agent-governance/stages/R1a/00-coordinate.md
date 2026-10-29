# R1a Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V1
Prepared stage: R1a / 单图简易前端提前切片
Packet version: 1.1.0
State: WAIT_AUTH
Active coordinate: R1a / WP-R1A-04 / GATE4_REAL_ACCEPTANCE
Last passed gate: WP_R1A_03_PACKET_1_1_OFFLINE_CHECKPOINT_PASS
Product candidate: febb0b3760dd733cd209d503c0ebf43f2d61e2d2
Evidence commit: f30722f88476d9407561bc4aa9d253f26f4ea87f
Prepared-against commit: f1780de806d4082dbf1d0f8a3ece81cf369aa0e1
```

本包落实 `docs/23_V1_EARLY_FRONTEND_SEQUENCE.md`。packet 1.1.0 的合同身份纠偏、wrapper、provider 账本、浏览器 oracle 和完整离线 checkpoint 已完成。项目负责人已于 2026-10-29 批准 `AUTH-PROGRAM-V1-LOCAL-01`；当前候选绑定子授权 `AUTH-V1-R1A-2026-10-29-LIVE-03` 已激活，只允许执行一次 `r1a-live-03` checkpoint，终态自动过期。R1a 不能在新鲜机器验收和独立审查完成前进入人工体验门槛，也不能声明 `V1_ACCEPTED`。

`r1a-live-03` 已且仅已执行一次并以 `NO_GO_CLEANUP_UNPROVEN` 终止：真实 React→FastAPI→Ollama 提交和 provider 调用各一次且完成，随后浏览器 Harness 在按序号定位 English `复制` 按钮时超时；Ollama 与 FastAPI 已停止、两域端口为空、Windows 临时目录已删除，但默认 `.lvw-runtime` 留下本轮预处理媒体，模型卸载也未在失败分支得到正面证明。授权已过期，历史收据保持 NO-GO；本轮自有媒体副本已单独清理。下一步仅允许离线修正稳定控件定位、隔离数据根和失败分支卸载证明，封存新候选后可使用母授权中 R1a 唯一一次 corrected-candidate 完整复验额度。

上述修正已封存为候选 `f901c49...`，候选绑定离线 checkpoint 11/11 通过并由证据提交 `55f3cf6...` 固化。母授权派生的最后一次 R1a 子授权 `AUTH-V1-R1A-2026-10-29-LIVE-04` 已绑定同一候选、四个 Harness、固定样本、端口和单次预算；当前只允许执行一次 `r1a-live-04`，终态后 R1a 自动 live 复验额度归零。
