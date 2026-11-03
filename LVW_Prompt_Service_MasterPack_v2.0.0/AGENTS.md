# Codex/Claude Code 实施约束

0. 开工前先读`.agent-governance/README.md`与`plans/execution-control.json`。产品权威仍是README、docs/00、contracts、plans；治理层只约束角色、Stage/Workpack、候选、证据、预算和门禁，不得反向改写产品合同。
1. 当前权威：本包README、docs/00、contracts、plans。legacy是历史，不执行其冲突开工指令。计划覆盖V0–V3；目标版本、下一交付与当前 Stage 只读取 `plans/execution-control.json`，不在本文件重复保存坐标。按 docs/23 批准顺序实施，逐版满足正式出门门禁。
2. 先只读盘点、git状态和备份；用户给出的Windows/4090/Gemma4情况是待核实线索。不默认升级ComfyUI、PyTorch、CUDA或复制权重。
3. V0用已装ComfyUI/Prompt Assistant/Ollama。必要新增仅一个薄扩展；节点/API从实际注册表读取，不编造class_type或把设计JSON冒充可运行图。
4. V1独立React+TS+Vite/FastAPI/SQLite；不依赖Comfy进程，不引入Gradio/NiceGUI。V2增强资产/协议，V3仅薄集成。禁止提前建设微服务/向量库/多Agent平台。
5. 无额外NSFW自动审查/审批门禁；不移除路径、授权、网络、供应链防护。无模型或模型未答时人工操作依旧可用，不制造“无审查模型”保证。
6. raw/机器建议/人工版本分离；结果只显式采纳，禁止取消晚到、重分析、迁移覆盖人工版本。
7. 一次视觉分析复用多个编译目标；格式切换/手工编译不再调用模型。不以确定性模板谎称自动完成翻译/事实核验。
8. 真实资源记录、独立标注、断网证据、对端真调用才能满足对应门禁。模拟只证明错误分支。测试代码、日志、哈希、版本和失败均必须交付。
9. 不重写Navia/Narralens状态权威；不直接写它们的数据库；MCP无任意Shell/路径/网络fetch。外部合同不可用如实BLOCKED。
10. 偏离范围/数据合同/硬门限需ADR与批准；不能偷偷放宽验收。修复后复跑，所有产物留实际变更记录。
11. 固定四权分离：Codex+Sol负责架构和Stage门禁；Claude Code+MiniMax/DeepSeek只实现冻结Workpack；隔离审查实例只读复算；人类负责高风险授权和最终体验签署。实现者只能报告READY_FOR_REVIEW，不能宣布Stage PASS。
12. 每个并行写任务使用独立worktree/等效副本、端口、数据库、临时根和证据根。公共API/Schema/状态机/迁移默认串行。当前仓库首个commit前禁止并行写任务。
13. 候选、规格、验收分母、门禁和证据必须以SHA/hash绑定。预算不足写WAIT_BUDGET，缺高风险授权写WAIT_AUTH；不得降低门槛。连续两次同路线无新证据即停止交接。
14. 任何真实盘点、模型/媒体探测或可见浏览器动作都以`plans/execution-control.json`和当前Stage的有限授权记录为准；不得从旧聊天或历史授权推断新预算。无匹配记录时进入WAIT_AUTH。
15. 当前路线决策见`docs/23_V1_EARLY_FRONTEND_SEQUENCE.md`：`R0/R1a`先于V0-S2/S3实施；R1a不是新版本、不得使用临时HTML或浏览器直连Ollama，也不得缩小V0.1/V0.2/V1固定分母。
16. 项目负责人于2026-11-03明确要求：每个Stage完成开发并通过人工验收后，立即提交阶段代码、脱敏证据及签署记录，并推送到已配置的Git远端/跟踪分支。此授权取代旧授权中的远程推送禁令；不包含强制推送、覆盖远端历史、生产发布或放宽验收。推送失败需如实报告并保留本地提交，不得声称已上传。
