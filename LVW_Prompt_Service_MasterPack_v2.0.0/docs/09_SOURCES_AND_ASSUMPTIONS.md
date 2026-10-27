# 09｜来源、事实与待验证项

## 实际依据

本轮读取了legacy内v1.0.0/v1.1.0原ZIP及其PRD、架构、计划、合同、验收、原型；完整sha在sources/baselines.json。更早的LocalVisionWorkbench/ReuseDesign原件本轮不可读取，继承对话中已明确的决定并在覆盖表标识，未声称逐文件核对它们。

用户盘点：Windows、i7-13700KF、4090/24GB、32GB、ComfyUI、Prompt Assistant、Ollama/gemma4:26b。我们没有连接该Windows主机；tag/vision/吞吐/显存/插件API都必须V0-S0确认。模型文件有视觉层不自动等于能作为聊天模型使用，不把H3 conditioning权重当可替换VLM。

## 本次查阅的官方文档（2026-10-27）

- Ollama Chat: https://docs.ollama.com/api/chat — format、options、keep_alive、模型响应。
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs — 视觉模型同样可用Schema。
- Ollama running models: https://docs.ollama.com/api/ps — 当前加载模型与size_vram。
- ComfyUI routes: https://docs.comfy.org/development/comfyui-server/comms_routes — prompt/queue/object_info/history/interrupt；具体插件路由另查本机。
- MCP官方README: https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md — 当前文档使用MCPServer、Python3.11+、stdio等；不凭此固定未经实测的小版本。

这些事实不证明目标主机版本支持全部参数。来源与本机证据冲突时采用实际兼容适配并记录版本，不盲升整套软件。

## 设计决定而非测量

资源/延迟/质量门限、SQLite表、API、版本流程、GPU协调、项目群协议都是本包设计，须实现验证。Navia/Narralens现有接口未知，只定义LVW侧提案；对端缺失不能用Mock通过V3。

## 不在本轮执行

真实Comfy图、Gemma4、4090、Windows离线包、独立金标准和跨项目E2E。本轮仅文档/合同/例子/DDL和HTML设计演示校验，报告严格分开。
