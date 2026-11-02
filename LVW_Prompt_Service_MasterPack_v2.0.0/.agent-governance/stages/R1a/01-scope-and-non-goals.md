# R1a Scope And Non-Goals

## 目标

- 交付 React + TypeScript + Vite 单图工作台和同源 FastAPI 服务。
- 浏览器只访问同源 `/api/v1`；Ollama 只允许 literal loopback。
- 提供服务状态、模型就绪状态，以及只针对本轮自有 Ollama 的启动、重置、关闭控制。
- 提供标准、忠实、成人艺术、医学四种有界内容配置和最多 800 字自定义指导；系统安全边界优先于用户指导。
- 分离 raw、观察、推断、未知、机器建议和人工稿；机器结果只可显式采纳。
- 固定 JPEG/PNG/WebP、20 MiB、40 MP、最长边 1024 与原图 hash。

## 非目标

- 不交付完整 V1，不声明 V1 PASS 或发布批准。
- 不实现视频、完整 SQLite 修订、CLI、批量、便携包、Library、MCP 或跨项目集成。
- 不使用 CDN、云回退、可见浏览器、Gradio/NiceGUI 或浏览器直连 Ollama。
- 不终止外部启动的 Ollama，不修改永久配置，不下载模型。
- 不改变 `R1A-M01..M07` 固定分母、V0 历史证据或 V0.1/V0.2 门禁。
