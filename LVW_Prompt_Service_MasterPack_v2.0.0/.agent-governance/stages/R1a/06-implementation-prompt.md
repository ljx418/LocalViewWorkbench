# R1a Implementation Prompt

```text
按 R1a packet 1.2.0 维护最终 React/FastAPI 单图路径。raw、suggestion、draft 分离，只有显式采纳能写入草稿。运行时控制只能管理本轮自有 Ollama；外部 Ollama 必须只读显示并禁用控制。内容配置必须是冻结枚举，自定义指导最多 800 字且不能覆盖系统/schema/安全边界。

不得改变固定分母、V0/V1 release gate，不得使用 CDN、云回退、临时 UI、浏览器直连 Ollama或 localStorage 数据库。实现者只报告 READY_FOR_REVIEW；Stage PASS、独立审查与人工签署权限分离。
```
