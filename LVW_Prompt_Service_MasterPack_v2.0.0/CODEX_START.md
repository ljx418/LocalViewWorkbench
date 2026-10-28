# 启动开发提示词｜全阶段有规格、分版本执行

## 直接粘贴

```text
请读取 LVW_Prompt_Service_MasterPack_v2.0.0，按 AGENTS.md 实施。
TARGET_VERSION=V0（可由项目负责人改为V1、V2、V3）。
本包完整定义V0–V3，但不能跳过前序验收或把后续功能偷偷加入当前版本。

先读.agent-governance/README.md、plans/execution-control.json和当前Stage Packet；校验Stage manifest、角色隔离、固定分母和授权状态。当前为V0-S1 / WP-S1-00，packet只授权离线仓库实现；S0 live授权已过期。WP-S1-03 的目标Comfy安装、Ollama、真实图片或可见浏览器必须等待新的逐次授权，不得从历史收据推断权限。

先读README、docs/00、01、03、04、05、06、对应版本实现方案和plans/*.json；
运行文档校验、只读盘点本机、备份将修改的工作流和配置。
V0从V0-S0开始：使用现有ComfyUI+Prompt Assistant+Ollama/gemma4:26b。
真实绑定节点并交付图片、短视频和独立人工编辑/导出路径。
不下载新模型、不升级整套环境、不建立V0数据库/独立SPA/MCP。

V1正式使用React+TypeScript+Vite、FastAPI、SQLite和Ollama；
V2加入镜头资产/真实PTS/FTS5/MCP/恢复；V3实现三个对端的薄集成。
各版本共用模型适配、模板、合同和测试资产，禁止重复造基础平台。
全阶段禁止Gradio/NiceGUI。

依据plans/tasks.json逐任务实现代码、测试、脚本、文档并修复失败。
按plans/acceptance_cases.json执行本版本及累计回归；PASS必须有真实证据。
资源、断网、质量、迁移和真实客户端/对端测试不能用Mock替代。
缺前置标BLOCKED，继续不受阻断的任务，不伪造验收结果。
通过当前里程碑后输出阶段审计包；达到TARGET_VERSION后停止扩展。
只有对应release_gates全PASS才声明Vn_ACCEPTED。
```

## 必须形成的实施产物

V0：真实UI/API工作流、node-bindings、必要薄扩展、模板、增量安装/回滚、用例证据。V1：后端、React源码及dist、不可变修订、便携运行包、CLI、API和真实测试。V2：迁移DDL、镜头/配方/检索、MCP工具、恢复与备份。V3：对端能力握手、合同适配、工作流白名单、真实E2E和回滚包。

## 报告格式

每阶段交付`stage-report.json`：stage、git_commit、requirements、changes、commands、results、evidence_sha256、runtime_versions、known_issues、next_gate。用例记录输入样本哈希、参数、模型digest、耗时/资源与实际状态；产品原始输出不经人工修饰再评分。

## 阶段阻断规则

V0-S0只要求环境/节点基线，不把未实现的完整打包先当门禁。模型不可用仍可实现人工路径。V1/R0重复的是新服务兼容检查，不重跑无关盘点。V3对端没准备好只阻断相关集成验收，不能要求LVW接管对端系统以消除阻断。并行工作不得共享未冻结Schema或绕过单GPU限制。
