# R1a Scope And Non-Goals

## 目标

- 使用最终 React + TypeScript + Vite + CSS Modules 工程交付单图工作台。
- 使用同源 FastAPI/Application Service 提供健康、受控上传、分析 job、结果读取和前端静态资源。
- 浏览器只访问同源 `/api/v1`；Ollama adapter 固定 literal loopback `127.0.0.1:11434`。
- 分离 raw、观察、推断、未知、机器建议和人工稿；机器结果只可显式采纳。
- 模型不可用时，人工编辑、复制和 TXT/JSON 导出仍然工作。
- 固定 JPEG/PNG/WebP、20 MiB、40 MP、最长边 1024 与原图 hash 不变。

## 非目标

- 不交付完整 V1，不声明 V1 PASS。
- 不提前实现视频、完整 SQLite 修订、CLI、取消晚到、批量、便携包、Library、MCP 或跨项目集成。
- 不使用临时 HTML 产品、Gradio、NiceGUI、CDN、云回退或浏览器直连 Ollama。
- 不用 localStorage 冒充数据库，不把媒体全量 base64 留在 React state。
- 不修改冻结 OpenAPI、固定验收分母、V0 历史证据或 V0.1/V0.2 门禁。
