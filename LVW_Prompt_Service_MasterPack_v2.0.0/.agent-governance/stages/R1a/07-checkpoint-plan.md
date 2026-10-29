# R1a Checkpoint Plan

## Gate 1：实现内循环

- Python unit/API tests、Pydantic validation、受控媒体 exact/one-over。
- TypeScript noEmit、React build、组件状态与导出纯函数测试。
- 无外联、CDN、绝对路径、秘密、浏览器直连 Ollama扫描。

## Gate 2：Workpack 收据

每个收据绑定 packet、acceptance hash、候选、命令/退出码、生产入口和未关闭风险；公共合同变化立即停止。

## Gate 3：离线 Stage Checkpoint

统一执行后端、前端、合同负例、构建、V0 回归与治理校验。检查 dist 由真实 React 构建产生且 FastAPI 同源托管；检查模型失败、晚到模拟和重复轮询不覆盖 dirty draft。

## Gate 4：真实验收与独立审查

只有新的一次性授权可启动本地服务、Ollama、读取固定 testSource 和浏览器。真实运行必须新鲜、候选绑定、loopback/no-cloud、有限尝试并完整清理。独立审查 Fatal=0、Major=0 才进入人工签署。

## Gate 5：人工体验

人类检查可理解性、视觉层级、编辑手感、错误恢复和导出结果。允许结论：`R1A_HUMAN_EXPERIENCE_PASS` 或 `CHANGES_REQUIRED`；两者都不等于 `V1_ACCEPTED`。
