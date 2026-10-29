# R1a Implementation Prompt

```text
按 R1a packet 在最终 V1 架构中完成单图简易前端。先 R0 复核，再实现 FastAPI 垂直路径和 React 工作台，最后一次离线 checkpoint。

不得修改 contracts、固定分母或 release gate；不得使用临时 HTML、浏览器直连 Ollama、CDN、Gradio/NiceGUI、localStorage 数据库或云回退。raw、suggestion、draft 必须分离，只有显式采纳能把建议写入草稿。模型不可用时人工编辑和导出仍可用。

离线阶段不得启动 Ollama 或浏览器。每个 Workpack 记录变更、测试、生产路径、负例、候选 SHA 和风险。实现者只报告 READY_FOR_REVIEW，Stage PASS 与人工签署由不同角色完成。
```
