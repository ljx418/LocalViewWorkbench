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

`r1a-live-04` 在任何目标预检或外部动作前因审批枚举值不符合冻结 Harness 而被拒绝：端口、进程、媒体、浏览器和 provider 动作均为 0，Stage checkpoint 未消耗；该子授权已过期并保留拒绝收据。替代子授权 `AUTH-V1-R1A-2026-10-29-LIVE-05` 只把审批枚举规范化为 `APPROVED`，其候选、Harness、样本、端点和预算完全不变；它继续占用且只能占用同一个 corrected-candidate full recheck 槽。

`r1a-live-05` 已执行一次并以 `NO_GO` 终止：固定图片提交、真实 provider 调用与完成事件均为 1，人工预分析导出和显式采纳已发生；浏览器随后仍无法通过 English 字段内的可访问名称 `复制` 定位按钮。失败分支已正面证明模型卸载、FastAPI/Ollama 停止、Windows/WSL 端口为空、隔离数据根删除且无 cleanup error。子授权已过期，R1a 在母授权下的 corrected-candidate 完整复验额度归零；禁止自动重跑，当前等待独立审查和项目负责人决定是否另开新授权。

隔离只读独立审查结论为 `NO_GO / Fatal 0 / Major 4 / Minor 2`：确认一次真实 provider 调用与清理证据可信，但浏览器路径、R1A-M04/M05/M06、可访问性合同和中文/负向非空 Oracle 未满足。当前不得进入 WP-R1A-05 人工体验门槛；先做离线纠偏，任何新的真实运行必须由项目负责人另行明确授权。

离线纠偏候选 `d1d3048...` 已完成：textarea 采用独立 `id/htmlFor`，四个 copy button 使用唯一 accessible name；模型 Schema 和 parser 强制中文、英文、图像提示词与负向约束非空，Harness 同步建立四输出 Oracle。候选绑定 checkpoint 11/11 通过并由 `31fb6af...` 封存。由于 R1a 母授权预算已耗尽，当前明确停在 `AUTH-REQUEST-V1-R1A-WP-R1A-04-LIVE-06`，批准前禁止任何 Ollama、媒体或浏览器运行。

项目负责人已明确批准 `AUTH-REQUEST-V1-R1A-WP-R1A-04-LIVE-06`；候选绑定子授权 `AUTH-V1-R1A-2026-10-29-LIVE-06` 已激活，只允许执行一次固定 `r1a-live-06`，终态自动过期且禁止重试。
