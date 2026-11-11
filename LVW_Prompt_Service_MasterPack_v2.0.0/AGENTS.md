# Codex/Claude Code 实施约束

0. 开工前先读`.agent-governance/README.md`、`plans/execution-control.json`与执行索引`docs/24_EXECUTION_MASTER_PLAN.md`。产品权威仍是README、docs/00、contracts、plans；治理层只约束角色、Stage/Workpack、候选、证据、预算和门禁，不得反向改写产品合同。
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
17. 项目负责人于2026-11-05要求：每次停止/最终回复都列完整V0–V3开发大纲，标记各子阶段已完成/总数及当前Stage；进度来自唯一 `plans/execution-control.json` 的 `development_outline` 和真实收据，不用主观工时百分比。保留既有十字段报告，区分实现、机器验收、独审、人工签署。执行索引见 `docs/24_EXECUTION_MASTER_PLAN.md`；`docs/25_PLAN_OPTIMIZATION_PROPOSAL.md` 的流程/门限调整须用户明确批准后才实施。

18. 项目负责人已明确授权剩余全部V0阶段的本机显卡使用与代码验证，记录见 `reports/authorization-program-v0-local-verification-01.json`。范围内诊断、定向验证、必要复验及完整checkpoint由执行器自动派生有限子授权，无需再次向人类确认；本规则覆盖旧的相关逐次授权/授权次数限制。旧过期记录不复活，每轮仍唯一候选/预算/隔离/清理/终态收据，禁止无限同路线重试；不豁免冻结合同、质量门限、独审、人工体验/发布签署，不扩大云/付费/下载/私有数据或非本轮进程权限。

19. 2026-11-09 批准 AUTH-PROGRAM-V1-LOCAL-02，完整范围与预算见 reports/authorization-program-v1-local-02.request.json 及对应 approval.json。同范围纠错候选自动封存/派生有限子授权，不再逐次确认 GPU、代码验证、候选 SHA；重叠范围采用新母授权累计预算，不叠加旧额度，不复活旧终态。Codex 临时实现角色延长至 V1；隔离独审和人工签署保留。当前 RUNTIME-01 已被覆盖，无需重复人批。

20. 2026-11-09 明确批准 AUTH-PROGRAM-V1-COMPLETE-03（request/approval见reports/）：剩余V0/V1按已批准路线自动推进，重叠范围的阶段/候选/启动/CPU检查授权次数硬配额取消，改全局累计1024模型动作/24轮有效完整验收/48小时生产运行，历史消耗计入、不清零。每轮仍有限绑定、完整清理与独审；同路线无进展须复盘，不因阶段次数再求人批。批准范围内构建期必要官方依赖下载≤2GiB/0付费/隔离安装及已装本地视觉模型比对可自动继续；无权下载模型、用云/付费/私有数据/可见浏览器/永久系统配置或V2/V3。人工体验/发布签署仍由人类实际完成，跨Stage有该前置时等待签署；机器/独审通过且无人签前置时不再另要执行许可。当前live08单次请求已覆盖，不能要求重复批准。

21. 项目负责人明确表示本机可持续使用并授权自行释放显存，记录reports/authorization-v1-gpu-reclaim-01.json。先有界定位GPU占用，优先闲置模型卸载/缓存释放，必要时仅对已确认身份的本机推理worker作PID/birth重核后关闭；不删除模型或用户文件、不重置驱动/永久配置、不误停普通GUI或未知训练任务。资源已足够时不作额外变更，直接继续已批准V1验证；这不是人工体验签署。

22. 2026-11-11用户批准多镜头能力纳入V1，记录reports/v1-redesign/product-change-approval.json。Codex负责总体/详细架构、合同、验收设计、协调和最终审查；默认通过Orca可见的ClaudeCode独立工作区承担具体实现与自检，不再默认由root批量实现。可自行启动管理这些窗口；独立审查必须与实现实例分离，自检不能签StagePASS。当前621b1bf体验签署仍待，不以产品变更冒充人签。允许先进行V1-D0文档与确定性工具准备，不跨过产品前置门槛；新功能真实运行仍受原全局预算、有限子授权、loopback/no-cloud、清理限制。

23. 2026-11-11用户明确确认“当前前端页面、基本的视频反推 我人工确认OK”，并在goal中要求绑定现有统一切片与普通推送。签署见reports/unified-media/human-signoff-live15.json，候选621b1bf，仅当前统一切片；规则22中的“体验签署仍待”是此前历史状态。不得再请求该切片重复人签，也不将此次签署扩大到旧S2/V0.2/完整R1/V1/发布。按docs30及实际依赖继续，旧范围若仍缺必要人签须明确区分。

24. 2026-11-11用户批准CHANGE-V1-S2-HANDOFF-01并要求继续goal。记录reports/v1-next-stage-readiness/change-v1-s2-handoff-01.approval.json，ADR-14生效：仅S3向V1开发衔接可使用原S2机器/独审与当前统一前端实际人签，严格校验候选和证据。旧S2保持7/8未签；不再把此衔接范围列为待人批，不扩大到其他依赖、历史版本接受或发布。当前准入与准备仍以execution-control和新S3packet为准，产品Gate0、固定质量/资源、有限运行、独审及后续人签均保留。
