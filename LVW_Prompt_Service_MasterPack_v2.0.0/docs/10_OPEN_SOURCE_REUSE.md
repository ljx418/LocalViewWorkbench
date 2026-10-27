# 10｜复用/引用决策与部署成本

| 组件 | V0 | V1 | V2/V3 |
|---|---|---|---|
| ComfyUI / Prompt Assistant | 已装优先；规则/分析/原生UI，经核验薄补丁 | 对照/可许可规则，非运行前置 | V3 Comfy仅生成执行 |
| Ollama / Gemma4 | 唯一已有VLM | 原生API直接调用 | 延续；不默认多模型 |
| FFmpeg/ffprobe/Pillow | 宿主已有，有限抽帧 | 随运行包的已验证二进制/依赖 | 真PTS/长片分窗 |
| React/TS/Vite | 不引入 | 独立可维护SPA | Library/Integrations |
| FastAPI/Pydantic/httpx/SQLite | 不另起服务 | 单体业务服务/修订 | 同库演进FTS5 |
| PySceneDetect | 非必需 | 非必需 | V2切镜，PTS另取 |
| 官方MCP SDK | 不装 | 不必需 | V2薄代理，不手写协议 |
| Open Image Prompts | 不必装 | 可手动参考 | V2可选只读风格/CLI，不默认下载全图库 |

复用不等于复制整个仓库。Prompt Assistant的规则/文本清理/num_ctx默认/云回退需要读取已装版本；仅迁移有许可且必要的部分。优先一个模型、一套产品Python、一份运行时；Comfy既有环境不克隆到新服务。

拒绝Gradio/NiceGUI；不为本项目引入Dify/FiftyOne/MongoDB/Redis/向量库/多Agent框架。不是声称这些项目不好，而是当前没有相应必要性。Node只构建；运行不pip/npm、无现场CUDA编译、无默认权重下载。V0包≤20MiB（不含素材/权重）；V1核心运行时预算≤2GiB，实际若超出需在依赖ADR列明，不以伪造体积达标。模型外置不计入应用包。

R0复用表记录版本、接口、许可证、额外进程/包体、已验证测试和REUSE/WRAP/BUILD/DEFER/REMOVE。不得根据网上README把已装插件的行为标PASS。检索档案不是视觉推理，风格卡不是生成效果保证。
