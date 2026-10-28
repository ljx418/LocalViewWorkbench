# LVW Prompt Service｜V0–V3 全阶段统一开发基线

**文档包 v2.0.0 · 2026-10-27 · 设计可指导实施，产品尚未验收。**

[打开 HTML 总览](START_HERE.html) · [交互原型](prototype/index.html) · [完整规范](FULL_SPEC.md) · [Codex 启动](CODEX_START.md) · [需求追踪](plans/requirements.json)。

## 当前执行坐标与多 Agent 治理

产品规格仍由本README、`docs/`、`contracts/`和`plans/`定义；[Agent Governance](.agent-governance/README.md)在其上增加角色隔离、Stage Packet、Workpack、候选/证据绑定、预算等待和反假绿门禁。唯一当前坐标为[execution-control.json](plans/execution-control.json)。

当前是`V0-S1 / WP-S1-03 / GATE4_REAL_ACCEPTANCE / BLOCKED`：aki-v2 live-02 已且仅已执行一次，但终态证据序列化失败，关键内存结果不可恢复，因此不推断产品结果也不重跑。`AUTH-V0-S1-2026-10-28-02` 已自动过期；终端后资源缺席检查通过，但运行内目标完整性仍未知，五项产品验收保持`NOT_RUN`。下一步是离线修复证据写入、封存新候选并申请新的逐次授权。

## 一套文档，不再多条互斥路线

| 阶段 | 用户能做什么 | 实现载体 |
|---|---|---|
| **V0 / MVP** | 本地上传图片或短视频，反推、编辑、复制/导出四类 Prompt | 现有 ComfyUI + Prompt Assistant + Ollama；无业务数据库 |
| **V1 / 独立服务** | 六类创作模式、四类目标编译、人工版本、独立运行 | React + TypeScript + Vite / FastAPI / SQLite / Ollama |
| **V2 / 创作资产服务** | 镜头切分、精确时间、风格配方、检索、批量恢复、Agent调用 | 复用现有后端，增加 PySceneDetect、FTS5、官方 MCP SDK |
| **V3 / 项目群适配** | Navia证据 → LVW提示词 → Narralens建议；受控Comfy生成交接 | 薄适配、版本合同、GPU协调、迁移回滚及真实E2E |

**完整包含V3本身，不只写“未来再做”。** 默认开工目标为V0；Codex通过`TARGET_VERSION`选择目标，按里程碑推进，不一次性混建全部功能。旧R0–R5仍保留，新增V0-S0–S3置于前面。

## 不变的原则

人工编辑/保存/内部导出不以模型成功或内容审批为条件；不新增NSFW审核器或审批状态；不承诺模型永不拒答。文件、网络、凭据、资源和供应链安全保留。**全阶段不使用Gradio/NiceGUI**。V0原生Comfy界面不会取代V1长期React方向。

LVW管理视觉观察、创作意图和提示词版本，不接管Narralens的导演/剪辑/生产审核，不替代Navia的知识采集，不重建视频生成引擎。“重资产”指结构化数据、来源、版本和关系，不是复制所有原片。

## 包内包含

PRD、目标体验及门限、全阶段架构与实现方案、分期开发计划、详细验收、HTTP/MCP/数据合同、SQLite起始DDL、六类模板、V0工作流**设计规格**、版本迁移、离线部署、风险、逐项旧包映射、可点击原型、Codex指令及校验工具。

`workflow_specs/`不是已可导入Comfy的工作流。真实节点和插件版本必须由目标机读取后生成。HTML是设计演示，不运行Gemma4、不代表产品实现。

## 完整性与证据边界

本轮实际读取v1.0.0/v1.1.0原ZIP，并在legacy原样保存；更早包原件本轮不可读，使用对话和后继包继承的决策并明确标识。详见`sources/baselines.json`和`docs/12_CHANGELOG_AND_COVERAGE.md`。旧R01–R20、A01–A22、F01–F07均有映射，新增V0独立编号。

所有产品测试初始NOT_RUN；文档/Schema/HTML校验不等于GPU、业务质量或对端集成PASS。声明完成需执行当前版本门禁和累计回归。第三方接口未就绪标BLOCKED，不用Mock冒充E2E。

## 本地阅读与校验

解压后打开START_HERE.html；无CDN/外部字体。文档结构检查：`python3 tools/verify_pack.py`。完整Schema验证：`python3 tools/verify_pack.py --schema`（构建/验收环境需预装jsonschema）。治理与反假绿负例：`python3 tools/verify_governance.py --self-test`。产品证据检查：`python3 tools/check_release.py reports/product-results.template.json --target V0`，模板未执行，预期拒绝发布。
