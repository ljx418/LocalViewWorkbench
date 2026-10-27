# LVW Prompt Service · V0–V3完整规范

文档包2.0.0；产品未验收。本文件汇编全部当前有效设计，原型、机器合同与历史ZIP另见同包。


---

# 00｜定位、状态权威与架构决策

LVW = Visual Prompt & Creative Asset Service。核心是“观察什么、想创造什么、怎样表达给生成器、哪些人工版本可复用”。不做第二个导演工作台。设计覆盖V0–V3，本次文档交付不代表任一产品版本已经开发。

| 系统 | 权威数据 | 允许交接 | 不允许 |
|---|---|---|---|
| Navia | 显式保存的知识/引用/来源 | 用户授权的摘要、引文、证据引用 | 浏览器凭据、默认原媒体/路径读取 |
| Narralens | 项目、脚本、生产镜头顺序、复检/审批、最终交付 | brief和参考进入，Prompt建议返回 | LVW写生产审批/剪辑/交付状态 |
| LVW | 视觉观察、推断、用户证据、创意、Prompt/配方修订 | 版本化建议/编译结果/引用 | 复制所有素材，冒充知识/史实权威 |
| Ollama/ComfyUI | 推理与生成执行 | 请求、任务、受控工件 | 接管生产项目状态 |
| Codex/Claude Code | 开发和受控工具使用 | 合同内API/MCP调用 | 成为必须在线的生产运行时 |

## 冻结决策

- ADR-01：V0为Comfy工作流MVP；V1独立服务；V2资产；V3集成，边界按版本生效。
- ADR-02：V1起模块化单体FastAPI+SQLite+受管小工件+单GPU执行槽；不引入消息集群。
- ADR-03：V0原生Comfy UI；V1–V3 React+TS+Vite/CSS Modules；Node仅构建。禁止Gradio/NiceGUI。
- ADR-04：默认已有Ollama/gemma4:26b；实际能力以目标机digest与探测为准。Prompt Assistant V0复用、V1对照，不重复下载模型。
- ADR-05：raw/机器建议/人工修订隔离；四来源域和未知值一直保留；模板编译为纯CPU。
- ADR-06：无人审通过状态作为内部编辑/保存/导出的前置；不追加NSFW过滤。模型未答不等于系统判断违规。
- ADR-07：引用优先，不复制原片；结构化资产版本、权限、索引、迁移做实，不构建海量媒体平台。
- ADR-08：V2 MCP官方SDK，按开工版本与客户端实测锁定；V3外部合同是提案，必须映射真实接口。
- ADR-09：升级软件与数据分开，模型外置复用；V0增量包，V1独立运行包，V3完整恢复测试。
- ADR-10：引用旧测试编号但不继承PASS。V0不替代V1，模拟不替代GPU/离线/真实对端。

## 优先级

最新用户授权 > 本文件ADR > 当前plans/contracts/config > 当前docs > 只读legacy。发现同级矛盾先记录ADR，不自行扩大范围。V0的无数据库不削减V1修订/V2资产；V0依赖Comfy不改变V1独立运行。


---

# 01｜PRD：从反推MVP到创作资产服务

## 目标用户与任务

Windows 4090/32GB单人创作者：将参考图片/短片或纯文字意图，转为可编辑、可追溯的视觉描述和下游Prompt。主题包括纪录片、写实、科幻、科普、电影质感、风格化。前两项强调来源；后几项允许创作扩展但不伪装为观测事实。

成功标准是少重复推理、少重复描述、人工稿不丢失、资料可复用，非“更自主的Agent”或“恢复原始seed”。静图不能证明连续动作；采样视频不能证明未被观察的片段；图像风格不能证明历史身份/科学结论。

## 版本化范围

| 版本 | 核心用户故事 | 数据与体验 |
|---|---|---|
| V0 | 上传图片/短视频→反推→人工编辑→复制/TXT/JSON | 会话工作稿，无业务数据库；允许平台上传/临时帧/显式导出落盘 |
| V1 | 选模式→分析/手写→锁定字段→编译→保存修订 | 轻React、独立服务、SQLite最小修订，CLI |
| V2 | 镜头切分→检索资产/配方→批量复用→Agent调用 | 时间/来源/关系/FTS5、批处理恢复、MCP |
| V3 | Navia授权证据→Narralens brief→Prompt建议→受控生成交接 | 引用、版本协商、跨进程资源和集成状态 |

## 完整需求清单

R01本地媒体受控导入；R02真实视觉分析及raw；R03无模型人工路径；R04六模式；R05四目标编译；R06四来源域/镜头结构；R07不可变修订/锁定/ETag；R08 SQLite和引用工件；R09 HTTP/CLI/React；R10资源/取消/卸载；R11离线/文件安全；R12导出/迁移；R13 V2切镜与PTS；R14资产/FTS5/配方；R15 MCP；R16批量恢复幂等备份；R17 Navia；R18 Narralens；R19 Comfy；R20 V3迁移及E2E。

另补R21：参考属性对比、非破坏性QC候选与分镜/JSONL导出（V2），承接更早讨论的业务场景。

这些旧ID不删除；具体验收、版本和任务在`plans/requirements.json`。另有V0-R01–R12，描述V0同类最小能力而非提前宣称R01–R20实现。

## 输入输出

V0/V1默认图片JPEG/PNG/WebP≤20MiB、40MP；短视频MP4/MOV≤256MiB、60s、单帧≤8294400像素。格式与解码器实测；默认4帧、图长边1024、视频帧长边768。超限提示截短，不静默只分析前段。V2长片通过引用和分段流式处理，默认≤2h、20GiB，不全量上传到浏览器内存；V3沿用而非重复存媒体。

V0四输出：自然中英、图像Prompt、视频Prompt、标签。V1四目标：natural、image（自然描述/SD标签两种rendering）、edit（generic/Qwen适配）、motion（generic/H3适配）。**FLUX优先自然描述，不等同SD标签**。专用后端模板是配置，不新增第五套推理管线。负向词可空，目标不支持时只作用户备注。

## 纯人工闭环

没有参考/没有模型/模型未答都能创建草稿。编译不调用LLM；英文缺失不假装已翻译。已保存人工修订只读；重分析仅出新建议，显式采纳才能产生新版本。内容备注不产生任何审批权限。

## 不做

自动版权判定、人物识别、史实自动认证、浏览器爬取/下载平台、全功能剪辑、模型训练、生成器权重管理、多用户SaaS、无限长片全理解、自动NSFW审核、通用Shell Agent、向量数据库、多前端框架。推荐候选项不能悄悄变为必装组件。

## 业务质量

V0独立标注10图+6片；V1起12图+6片覆盖六模式，所有模式至少2张图，全部原始结果参与评分。单样本5维0–2分，≥8且无关键幻觉才可用；V0图≥8/10、片≥5/6，V1图≥10/12、片≥5/6。24模式×目标是确定性编译组合测试，不等于24项视觉质量已合格。V2/V3继承并增时间/集成场景。


---

# 02｜目标体验、状态和门限

## V0：工作流而非平台

两个工作流“图片反推”“视频反推”，输入/规则/建议/工作稿四分组；已有面板优先，缺口才加原生JS。独立人工编辑/导出不得接在可能失败的模型节点之后。典型≤5个主要操作；4帧预览附采样时间与“未分析音频”。会话未导出关闭会丢失，要提示；不暗中建立localStorage资产库。

## V1：单页工作台

左参考预览，中间观察/推断/证据/创作字段，右机器建议和人工稿，底部版本/导出。上传→模式/目标→分析→采纳/修改→保存复制。无模型时同页保留所有人工能力。非空草稿采纳需要确认；冲突时显示差异和另存，不最后写覆盖。输入规则和高级资源参数折叠。

## V2：资产库 + 配方 + 任务

工作台之外增加Library，按文字、标签、类型、来源、配方过滤。结果卡显示可复用Prompt版本、源可用性、镜头范围。选中资产→引用已有修订或创建分支；删除是可恢复的归档/引用解除，不删原片。Recipe编辑产生新版本；批量任务按项失败、恢复、不阻断手工编辑。没有向量索引时明确叫“文字/标签检索”。

## V3：项目群交接

Integration页显示Navia授权范围、Narralens源镜头版本、Comfy工作流版本、建议/执行/接收状态。对端离线则排队或保留待交接稿；不伪报已交付。授权只约束数据与机器操作，不是内容审批。Prompt建议和Narralens最终采纳分开；只有后者掌握生产状态。

## 全局状态体验

queued/preparing/running/partial/succeeded/failed/cancelling/cancelled/interrupted分清。resource_state独立，取消反馈不意味着GPU已停。明确错误、重试范围、保留了什么。模型结果到达只进建议区；手动工作稿依靠draft_epoch/etag保护。日志不要给假百分比。

## 可测门限（设计值，不是实测）

| 指标 | V0 | V1–V3 |
|---|---|---|
| 点击/取消反馈 | ≤1s | ≤1s |
| 等待提示 | ≤2s | ≤2s |
| ≤20000字编辑/复制反馈 | ≤1s，导出≤2s | 同左；保存API P95≤500ms（不含大文件hash） |
| 默认热模型单图/4帧 | 各10次P95≤180/300s；另报冷加载 | 同左，超过需正式ADR而非隐性缩输出 |
| 超时 | 分析420s硬上限；释放另测 | 单窗口420s；批量按窗口，不能把2h片视为单窗口 |
| GPU | 总峰值<23GiB；21GiB为优化目标 | 同左；不把网络锁当驱动级隔离 |
| 内存 | 系统可用RAM≥2GiB | 同左；LVW+子进程/Ollama汇总Private Bytes≤26GiB作为补充预算 |
| 资源释放 | 已停止计算后30s内/api/ps消失且GPU回到空闲基线+1GiB，3次采样 | 同左；取消≤60s仍未停则RESOURCE_BUSY，人工仍可用 |
| 前端 | 1280/1920桌面、原生200%可达 | 360/768/1280/1920，200%不隐藏核心操作 |
| 资产查询 | 不适用 | V2起1000引用，P95≤500ms，结果首屏≤1s，虚拟/分页不冻结 |
| 包迁移 | 同宿主中文/空格目录 | V1新目录/用户；V3干净Windows宿主与数据恢复 |

测试模型默认卸载；热基准临时保持加载并结束后恢复配置。P95采用nearest-rank，10次即第10个，样本数必须披露。无伪造吞吐/计时。更大数据量/8帧/8192 ctx是另测配置，不是默认承诺。

## 原型解释

`prototype/index.html`可切四版本、六模式、四目标、选择本地预览、模拟成功/取消/模型不可用、修改并导出设计示例。醒目标记“演示”，不运行真实模型；原型不是节点图或React实现。本包浏览器检查只证明原型本身。


---

# 03｜架构设计：连续演进，不重复建系统

## V0拓扑

```text
ComfyUI原生界面/已装Prompt Assistant
  ├ 图片→受控缩放 ─┐
  ├ 视频→有限抽帧 ─┼→Ollama→raw/建议→显式采纳
  └ 人工稿→CPU四输出→复制/导出（独立路径）
                        推理调用finally→释放检查
```

最多一个LVW薄扩展。Comfy为宿主，Ollama为执行。无业务持久队列/数据库。平台上传、现有历史和临时帧落盘必须披露。不得把整个视频先载入GPU张量再挑4帧。

## V1–V3目标拓扑

```text
React静态dist ── 同源HTTP ─┐
CLI / V2 MCP stdio ────────┼→ FastAPI / Application Service
V3对端适配 ────────────────┘      ├ Compiler（CPU纯函数）
                                 ├ Revision / Asset / Evidence
                                 ├ Job Coordinator（单GPU槽）
                                 └ SQLite Repository / 文件工件
                                    │
                       CPU预处理→Ollama VisionProvider
                       V2分镜 / V3 Comfy执行适配
```

浏览器不直连Ollama，不拿绝对路径/凭据；MCP薄代理到同一服务，不因多客户端启动多份GPU Worker。V1关闭Comfy仍可运行；V3只有生成任务才依赖Comfy。

## 代码边界

`domain/{PromptSpec,compiler,revision_policy}`不依赖HTTP/Comfy；`services/{media,analysis,assets,jobs}`持有业务；`adapters/{ollama,comfy,navia,narralens}`隔离协议；`repositories/sqlite`唯一写权限；`api/cli/mcp`入口共享服务。前端只管理展示和草稿状态，不复制后端事务规则。

V0提取的模板/预处理/结果合同可迁移；Comfy节点ID、插件路由、session graph不是正式业务对象。输入output schema版本需转换，不把V0 run_id当revision_id。

## 控制面与执行面

CPU编译/保存与GPU队列独立。V1 SQLite记录job/attempt，进程崩溃标interrupted、显式重试；V2才提供批量续跑策略/lease/恢复。写入时CAS检查attempt_id和cancel_epoch；结果原子发布，人工修订append-only。

V3 GPU协调只约束所有接入协作租约的生产者；不控制未接入的外部Comfy/Ollama。发现未知占用返回RESOURCE_BUSY，不能kill其他进程。对端队列和本地job要有分别的id，不制造分布式“恰好一次”承诺。

## 数据权威与缓存

媒体本体引用默认归来源系统；hash标识内容，asset_id标识业务引用。模板版本、模型digest、采样、输入hash形成analysis_key；结果缓存只供显式复用、不得覆盖人工稿。更新模板产生新key，不能命中旧结果伪称已用新模板。

## 部署单元

V0增量工作流/薄扩展；V1一个Python服务（含静态前端）+已有Ollama；V2增加同应用模块而非新数据库服务；V3按需启用外部适配。无Redis/MongoDB/独立向量库/大Agent运行时。Node仅构建，所有浏览器资源本地。


---

# 04｜V0–V3迭代目标与门禁

| 版本 | 阶段 | 出门能力 | 出门证据 |
|---|---|---|---|
| V0 | V0-S0~S3 | 图/短视频反推、独立人工四输出、增量包 | V0-A01~A12全PASS |
| V1 | R0复核、R1、R2 | React/FastAPI/Ollama、六模式四目标、修订、离线独立包 | A01~A12、F01~F05、Q01、X01~X03；V0合同回归 |
| V2 | R3、R4 | 真实PTS、资产/FTS5/配方、MCP、批处理恢复 | A13~A17、F06、X04~X06；V1累计回归 |
| V3 | R5a、R5b、R5c（旧R5细拆） | 三对端交接、资源协调、升级回滚、E2E | A18~A22、F07、X07~X09；V1/V2累计回归 |

Q01为独立质量；X为对旧包未细化风险的补强，并非取消旧A/F。精确门禁见plans/release_gates.json。文档版本2.0≠产品V2。

## 进入与退出

V0-S0是探测不是产品验收，禁止用完整发布项卡住开工。V1前复核V0转换和独立API；旧Prompt Assistant只作对照，不再是依赖。V2迁移保留所有已保存revision_id和hash。V3仅在真实授权/对端合同可调用时完成相关E2E，模拟能解阻开发不能通过发布。

可在前序受阻时实现无依赖功能，但不能提前宣称整个版本通过。达到TARGET_VERSION后停止；跨里程碑自动推进仅在用户明确选择更高目标时授权。

## 不继承什么

不继承旧报告PASS、不把4帧近似升格为精确PTS、不把工作流JSON改名为API服务、不把本地检索当语义模型、不把返回Prompt当视频已生成、不把外部任务提交成功当Narralens已采纳。

## 范围升级

候选新模型、大型图库、Linux二进制、多用户、语义向量检索、ASR、自动剪辑不属于V0–V3必选。出现真实需求再ADR；不得为“完整”把它们加到默认依赖。工期由目标机基线与实际burn-down修订，不写虚构保证日期。


---

# 05｜完整开发计划与实现交付

权威清单`plans/tasks.json`给每项依赖、产物、关联需求/用例、实现步骤与阶段出门。以下是可执行工作包，而不只是愿景。

| 阶段 | 实现工作 | 交付 |
|---|---|---|
| V0-S0 | 只读盘点/备份、模型单图+4帧、节点注册/参数/许可与取消卸载探测 | inventory、node-bindings、baseline、依赖锁候选 |
| V0-S1 | 独立人工编辑导出优先，图片预处理/真分析/建议分离/四输出 | 图片UI/API图、人工流程、模板及导出 |
| V0-S2 | 视频上传/限量解码、采样预览/时间性质、请求级资源锁/清理 | 视频UI/API图、资源与异常测试 |
| V0-S3 | 冻结质量集、断网/迁移/回滚/性能，最小增量包 | 真实验收、使用说明、可逆补丁 |
| R0 | 新独立服务接口探测，复用V0模型模板，确认正式依赖/许可 | 复用审计、架构差距与数据映射 |
| R1 | React SPA、FastAPI合同、人工镜头、CPU编译、SQLite和受控导入 | 实际前后端、单元/API测试、模板矩阵 |
| R2 | Ollama真推理、异步job/CAS、修订/导出、Windows便携包 | V1运行包、CLI、API和累计验收 |
| R3 | PySceneDetect/真实PTS、长片分窗、资产链接/FTS5/配方、Library | V2资产/时间功能、迁移DDL、检索实测 |
| R4 | MCP薄工具、批量/lease/幂等恢复、备份/restore | 真客户端、故障注入、V2运行包 |
| R5a | 外部能力握手、Navia显式证据导入、Narralens建议与冲突 | 双端合同与真实安全测试 |
| R5b | Comfy工作流allowlist/参数映射/收据/单GPU协作 | 真生成交接、超时不重复提交与取消隔离 |
| R5c | 集成UI、迁移/回滚/离线三系统E2E、最终交付 | V3运行包、兼容表、可复核审计包 |

## 每阶段统一步骤

先更新环境/变更清单；实现合同与测试；产物校验；单位/集成/真实场景分层执行；失败修复复跑；报告实际PASS/FAIL/BLOCKED/NOT_RUN。合同先冻结再让前后端并行；同卡硬件测试串行。功能开发、环境准备和外部依赖阻断分别计量。

## 实施目录

```text
lvw/
  v0_patch/{custom_nodes,workflows,templates,scripts}/
  backend/app/{api,domain,services,repositories,adapters,cli}/
  frontend/src/{features/workbench,features/library,features/integrations,api,components}/
  mcp_bridge/              # 业务服务薄代理，无第二GPU worker
  contracts/ templates/ migrations/
  tests/{unit,contract,integration,e2e,hardware,offline,security,quality}/
  scripts/{build,diagnose,backup,restore,rollback}/
  reports/ manifests/
```

V0交付真实workflow；本设计包不伪造具体节点。正式代码生成Pydantic/OpenAPI/TS类型，合同变更做双向一致性测试。编译/导出不受GPU队列影响。入站文件安全和人工版本保护优先于美化UI。

## 交付与停止

每版本都给可运行产物、锁定依赖、用法、升级/卸载、测试和证据；不能只有截图。V3支持对端不可用时人工工作，不用扩大本项目边界消除外部阻断。所有缺口进入risk register；不修改旧成功证据来覆盖当前失败。


---

# 06｜全阶段验收计划

## 判定与证据

PASS实际执行达标；FAIL执行未达标；BLOCKED缺可验证前置；NOT_RUN未执行。每个用例有前置、步骤、断言、测试类型、证据和资源指标，机器真源在plans/acceptance_cases.json。所有产品状态初始NOT_RUN。

必须记录git/环境/插件/模型digest、配置、样本哈希、命令/截图/输出及哈希、计时和资源。模拟测试只证明逻辑分支，不能证明真实推理质量、断网无外联、GPU停止、外部项目可用。发布检查器可检查证据结构，不能证明人为证据真实。

## 验收分层

1. 单元：确定性编译、6×4组合、Schema、时间换算、CAS冲突、权限判定。
2. 集成：真实SQLite、文件/媒体处理、API错误、崩溃与恢复；故障注入显式标识。
3. UI：对应真实V0宿主或React产品，键盘/缩放/响应式、工作稿保护。
4. 硬件/离线：Windows4090、已有Gemma4、图+4帧，loopback保留的外联阻断和观测。
5. 业务质量：独立标注的原始模型结果；不以修改后结果自证模型正确。
6. 跨项目：V3真Navia/Narralens/Comfy版本和权限，不能用HTTP mock通过。

## 版本门槛

V0 12组；V1原A01–A12/F01–F05+Q01+X01–X03；V2 A13–A17/F06+X04–X06；V3 A18–A22/F07+X07–X09。所有版本继承前序正式合同回归，V0包仍按发布目录进行兼容复查。详细集合见release_gates。

## 业务评分

每样本主体/环境、光线/构图/风格、动作/时间或静图不虚构、事实/创作分离、Prompt可用性五维各0–2。≥8/10且零关键幻觉才可用。V0图8/10、视频5/6；V1起图10/12、视频5/6。禁止把未提供的真人身份、年代/地点、科学结论写成确定事实。原始响应与人工稿分别评分；样本/评分表测试前冻结，由用户或独立人员签注。

V2切镜算法独立评估：至少20个人工标注切点+连续镜头，±2源帧容差，precision/recall各≥0.90；困难淡入/闪白失败必须展示并可人工校订。PTS“精确”指实际帧时间基映射，不表示算法切点永不错误。

## 性能与离线方法

各10次热模型图/视频；P95 nearest-rank，第10值；冷加载各另报。1s或更细采样总GPU与系统可用RAM，Private Bytes标明进程集合。默认自动卸载，热测试后恢复配置。仅图像响应HTTP结束不证明模型卸载；用/api/ps+显存稳定3次采样。

断网冷启动：预置权重/依赖保留，浏览器缓存清理；阻断非loopback出站、观测连接尝试，首屏/分析/编辑/导出全测。只被防火墙拦住但不断尝试外联不算该配置通过，需隔离无关联网插件后重测。

## 迁移与负例

跨目录/用户名、中文路径、WAL活跃快照、包篡改/zip-slip/符号链接、缺素材重绑定、schema升级失败回滚。原始媒体hash不变；所有revision_id/content_hash相同；不要只复制.db遗漏WAL。

## 发布结论

Vn_ACCEPTED要求该版本全部必选及累计回归PASS。缺独立质量最多ENGINEERING_READY/QUALITY_PENDING；缺对端V3_INTEGRATION_BLOCKED。NOT_RUN/FAIL/BLOCKED不能当skip成功；诊断性optional用例须在执行前声明而非失败后改为可选。


---

# 07｜攻击者视角与安全边界

| 攻击/失败路径 | 影响 | 必须防线与用例 |
|---|---|---|
| 图片字幕/网页/模板提示注入 | 诱导执行命令/泄漏资料 | 将内容视为数据、无tools给VLM；MCP白名单；V0-A07/A08/X01/A15 |
| 任意路径、UNC、重解析、zip-slip | 越界读写/破坏工作区 | resolve+允许根、拒绝链接、无shell拼接；A08/X03/X09 |
| 巨幅/长片/压缩炸弹 | OOM/磁盘满 | 像素/时长/字节/帧/临时配额/子进程超时；V0-A07/A10 |
| 本地网页跨源请求或DNS rebinding | 未授权调用loopback | 校验Host/Origin、随机本地会话token、非GET写操作鉴权；X01 |
| 供应链自动更新/插件联网 | 隐私外泄/环境损坏 | 固定版本hash、离线资产、增量patch和回滚；A09/X02 |
| 取消/重复提交/重启晚到 | 错写人工稿/重复生成 | attempt fencing、CAS、幂等键payload hash、unknown状态；A07/A16/X08 |
| 多系统写同一镜头/审批 | 状态冲突、不可追溯 | 明确权威、只返回建议、ETag/源版本；A19/X07 |
| 史实/科学幻觉 | 误导内容 | 四来源域+unknown+人工证据；Q01/A12/A22 |
| 人审备注变成执行门禁 | 卡住创作 | 不建approval_required内容字段，手工路径永在；V0-A08/A01/A05 |
| GPU租约与实际资源脱节 | 外部任务被误停或OOM | 协作者锁+实际检测，不控制未接入客户端；A20/X08 |

应用默认只绑定127.0.0.1，拒绝非预期Host/Origin；不要为了插件CORS方便开`*`。本地token存操作系统当前用户可读配置，不在日志/导出出现。上传生成受管ID，不让浏览器提交任意绝对路径；登记来源根须本机操作和授权。

没有内容审核器≠没有授权。Navia“显式保存/授权”是资料访问边界，不是审查题材。Narralens自身生产复检仍由它负责，LVW不篡改也不复制。文件/网络保护不能被“人工负责NSFW”当作移除理由。

无通用Shell、任意URL抓取、任意Comfy工作流执行、直接SQL MCP。日志默认不含原图base64、完整私人Prompt、cookie、绝对路径；诊断包脱敏且显式导出。第三方源码/模型/素材许可证各自核验，不作自动法律结论。


---

# 08｜HTTP / MCP / 数据合同

`contracts/openapi.json`列出V1–V3端点及版本；`contracts/lvw.schema.json`是核心数据初始合同；`contracts/mcp-tools.json`列V2工具；`contracts/integration-contracts.json`定义V3提案与能力握手。实施后Pydantic为运行时真源，CI验证生成OpenAPI/TS和设计合同兼容，禁止三份手写Schema互相漂移。

## 通用语义

HTTP成功`{data,request_id,schema_version}`；错误`{error:{code,message,retryable,details},request_id}`。请求ID由服务生成/校验并贯穿日志，不能作为业务幂等键。202表示已受理，不表示完成。列表cursor+limit≤100，结果按稳定id排序。健康端点不泄漏路径。

写操作校验本地token与Origin；GET可按部署策略保护。POST jobs/revisions/import/handoff需Idempotency-Key；同键同规范化payload返回已有结果，同键不同payload 409 IDEMPOTENCY_CONFLICT。V1 job键在记录生命周期内永久唯一，V2/V3交接键至少保留项目记录生命周期，不以短缓存代替。

镜头GET带ETag；PUT必须If-Match，缺失428、不匹配412；旧包409冲突统一迁移为标准条件失败412，并保留error.code=REVISION_CONFLICT给旧客户端解释。逻辑版本/幂等冲突仍409。删媒体只归档自己的引用，不删外部源文件。

## V1

health/capabilities；受控multipart media；创建/读取/更新shots；analyze job、poll/cancel；CPU compile；append-only revisions、TXT/JSON export；CLI与HTTP共业务。保存revision须绑定shot当前etag，事务内快照+hash，旧revision无PUT/DELETE。

## V2

asset list/query/links、scenes及人工时间边界、recipe revisions、batch/retry、backup/export/import。MCP工具8个：capabilities、search_assets、get_asset、analyze、get_job、cancel_job、compile_prompt、save_revision。参数只接受ID/受控规则，不收任意路径；客户端启动薄代理到已有LVW服务，无第二worker。

## V3

capability handshake、Navia evidence import、Narralens brief/suggestion receipts、Comfy allowed workflow jobs、integration status、project package import/export。接收拒绝附带额外凭据/不允许字段，授权scope必须与具体来源匹配。版本不兼容返回CONTRACT_UNSUPPORTED；不能猜测对端接受字段。

## 不当承诺

MCP SDK的存在不代表生产工具实现；OpenAPI是设计合同不是运行中的API；工作流设计别名不是Comfy class_type。Ollama structured output只约束语法，不证明事实正确。不得把浏览器SDK可读路径行为当原始HTTP可接受路径；HTTP图像发送编码内容，路径只留本机服务。


---

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


---

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


---

# 11｜前端工程与界面原型

## V0

原生Comfy工作流/同源JS面板，输入、规则、raw/建议、人工稿四组。复制/导出脱离GPU链；必要独立纯CPU人工图或JS Blob导出。只读ShowText不算可编辑。raw不能经自动清理器覆盖用户稿。默认不localStorage持久化，平台现有缓存/历史另披露。

## V1–V3

React+TypeScript+Vite+CSS Modules，同源FastAPI托管dist；构建产物本地，不使用CDN图标/字体/分析脚本。开发Vite代理仅开发用，生产无Node服务，无通配CORS。初期React hooks/fetch即可；路由/状态库仅有实际需求时ADR，不重复前端框架。

```text
src/
  api/{client,types}.ts
  features/workbench/{MediaInput,AnalysisPanel,ShotEditor,PromptOutputs,RevisionHistory}.tsx
  features/library/{Search,AssetList,RecipeEditor}.tsx
  features/integrations/{ConnectionStatus,SourceReferences,HandoffReceipts}.tsx
  components/{Button,Field,Alert,Dialog,EmptyState}.tsx
  styles/{tokens,base}.css
```

工作稿带dirty flag和etag；建议到来不改变草稿；明确采纳/另存。切换模式/目标只重新编译，不能隐式调用模型。文件预览URL及时revoke；媒体不全量base64放React state。耗时操作poll带退避、AbortController与卸载清理，取消poll不伪装取消服务器任务。

F01–F07对应真实产品测试，见plans。键盘能操作所有关键控件，焦点清楚；360px核心动作无横向隐藏，200%可滚动操作；长中文字、错误、空状态必须覆盖。

## 原型说明

HTML预览示意设计和交互，不是生产React代码，不连接模型。四版本页面展示范围差异、六模式、四输出、人工输入与异常兜底、资产和集成样例。所有演示数据显式标记；上传仅在浏览器本地预览，模拟分析不分析图片内容。


---

# 12｜全部已知基线的归并与变更

## 读取与继承

| 来源 | 本轮状态 | 处理 |
|---|---|---|
| Prompt Service DesignPack v1.0.0 | 原ZIP可读，已归档 | 逐文件映射；S0–S11保留来源 |
| Prompt Service DesignPack v1.1.0 | 原ZIP可读，已归档 | R01–R20/A01–A22/F01–F07保持ID；R0–R5继续 |
| 最早LocalVisionWorkbench/ReuseDesign包 | 原ZIP本轮不可读 | 对话需求继承，不能声称逐文件完整审阅 |
| 已同意的V0方案 | 对话及当前草案 | 新V0-S0–S3/V0-R/V0-A独立前缀，全量纳入 |

机器表`plans/legacy_file_map.json`覆盖两个原包的每一个文件；`plans/legacy_id_map.json`覆盖旧ID。`plans/requirement_coverage.json`覆盖需求→任务→用例→文档→合同。旧验收证据只归档，不转换为当前PASS。

## 消除的冲突

- 不再把V0无数据库写成整个项目永不持久化；V1修订、V2重资产保留。
- 不再把Comfy宿主写成V1运行前置；V0快落地，V1独立服务。
- 不再把未来V1–V3仅放到“后续目录”；本包有完整实现、API、DDL、验收和UI。
- SD标签与FLUX自然描述分开；V0四视图与V1四目标存在明确转换，不反复运行视觉模型。
- 卸载节点不能只位于失败节点之后；取消状态与GPU资源独立。
- 旧409版本冲突按If-Match改为412，幂等/逻辑冲突仍409；客户端迁移有说明。
- 旧MCP具体小版本不强制继承；按官方SDK和真实客户端锁定。
- 视频V0近似采样、V2真实PTS，严格保留time_basis。
- 旧V1 12图+3片升级为12图+6片；增加Q01质量门禁而非把性能等同质量。
- V3外部接口未核实，候选合同不是实现事实；提交不确定时不盲目重复生成。

## 历史探索功能如何处置

历史来源卡/摄影研究→R06/R17；Prompt版本→R07；本地检索/配方→R14；参考片vs生成片对比→V2属性对比（X06）；技术质检/数据导出→V2诊断候选/JSONL与分镜导出（X06）；图/视频真正生成→R19调用外部，不自建模型。人脸身份、自动史实认证、ASR、跟踪/分割、上色修复、向量检索、独立剪辑→明确非目标/可选后续，非悄悄删除。

本包完整性是针对可见需求与可读基线的可追踪覆盖，不是声称能预知尚未提供的仓库与隐含需求。新发现差异需追加ADR、测试和映射。


---

# 13｜V0实现方案：最简图片／视频反推

本章只定义V0；不削减后续V1–V3。真实工作流由目标机生成。


这里的名称是**职责别名**，不是保证存在的ComfyUI class_type。节点真实名称/版本/输入输出由S0绑定。

## W-I 图片

```text
本地图片输入 → 旋转/色彩/像素限额 → 已装PA视觉调用 → raw + suggestion
                       ↓                  ↓finally
              预览/源hash/参数          Ollama释放核验
                                          │
建议区 ──用户采纳──→ 人工稿 ──CPU四视图──→ 复制/TXT/JSON
```

输入最多1张图。EXIF方向显式处理；RGBA透明以配置背景合成或明确保留策略；不静默丢失原始颜色解释。来源hash对原文件计算，预处理尺寸单独记录。

## W-V 视频

```text
本地视频上传 → ffprobe限额/可解码检查 → 按时间顺序有限抽帧
                                        ↓
                   4个缩小帧 + 时间性质 + 源hash
                                        ↓
                        PA多帧规则 / 同源薄适配
                                        ↓
                          raw/建议 → 人工稿/导出
```

默认4帧均匀分箱中心；短片不足4个可区分帧允许少帧但警告，不能复制同帧冒充多个观察。较长/快切只保证采样可追踪，不给“完整分镜”的标题。超60s要求用户先截取，不背地只看前60s。

现有视频节点若先把全部帧加载为tensor，即使最后选4帧也不合格。采用受控FFmpeg按需解码，最大待推理帧8、默认4。V0不装PySceneDetect作为必需。

## W-M 人工（独立于W-I/W-V成功）

```text
人工文本/上次导出 → 编辑 → 本地格式整理 → 复制/导出
```

无Ollama、推理失败、取消待清理都可运行。只有Comfy本身完全不可用时V0界面不可用，此时依赖已导出的文本；不承诺系统崩溃仍能提供UI。人工支路不能连接到必须执行的VLM节点。导出按钮应原生JS或独立纯CPU路径，不入GPU执行队列。

## 真实工作流交付要求

UI JSON与API JSON必须由同一个真实图生成；图中只有已安装/已随补丁提供的节点。载入无missing node，测试输入到输出可复跑。附`node-bindings.json`及上游版本；不能把本包`workflow_specs/*.json`改名为UI工作流来交付。

资源释放必须在调用者清理路径，非只在“正常输出之后的节点”。视频时间/错误/模型digest由代码填写，不让模型编造。



```text
ComfyUI 原生页面 / Prompt Assistant 面板
 ├─ 图片上传 → 受控缩放/规范化 ───────┐
 ├─ 视频上传 → ffprobe→有限抽帧/顺序 ├─ 现有PA视觉节点/经核验薄适配
 └─ 独立人工稿 → 格式整理→复制/导出  │              ↓
                   ↑                │  本地Ollama /api/chat
                   └── 显式采纳 ← 原文/建议         ↓
                                 finally清理→/api/ps与显存核验
```

## 1. 模块与新增边界

ComfyUI 负责上传、工作流可视化、已有任务执行；Prompt Assistant 尽量承担模型调用与规则。Ollama 独占模型执行。LVW 只补输入限额、统一结果、人工稿保护、受控导出与任务资源边界。

若现有节点完整满足合同，零额外扩展；否则增加 `custom_nodes/lvw_v0_bridge/` 一份包，使用宿主已有依赖/标准库。必要的原生JS面板从同源加载，无Node运行服务。不把整份PA代码复制成新项目，先核许可证。

## 2. 运行与结果状态（仅会话内，不建持久队列）

分析状态：`idle → preparing → running → succeeded | partial | failed`；取消经 `cancelling`，释放经独立 `resource_state`。会话临时 `run_id` 每次不同，当前run token不匹配的结果只可被丢弃或显式查看，不能改稿。

`resource_state = unknown | busy | releasing | released`。`cancelled`表示产品不再接收该结果，**不代表已停止GPU**；下一任务只有在资源确认释放后进入。宿主/后端崩溃不自动恢复任务，重开需显式重试，这属于V0边界。

会话工作稿维护 `draft_epoch`；每次用户改写递增。结果只进suggestion区，“采纳”显式创建新的草稿内容。导出记录是机器建议还是人工稿及来源run_id，允许纯手工 `run_id=null`。

## 3. 单 GPU 与取消清理

只允许1个LVW视觉请求，ComfyUI自动队列模式对本工作流关闭。锁只约束本扩展；不能宣称它控制其他独立生成工作流或Ollama客户端。使用者先暂停外部GPU任务；发现竞争提示并阻止本次分析，不强制杀进程。

推理调用自身使用 `try/finally` 请求清理。成功请求用 `keep_alive=0`；错误/取消时对本次模型做经本机验证的显式卸载，并轮询`/api/ps`。若存在别的用户请求，不能主动卸载或终止对方任务；报告资源占用及人工处理办法。

不能仅把“Unload Model”节点放在推理节点后：上游异常时它可能永不执行。关闭HTTP连接也不能直接判定停止计算。控制返回不等于驱动显存回收，二者分别验收。

## 4. 多帧处理

默认按视频时长取4个均匀分箱中心（例10s：1.25、3.75、6.25、8.75），不是承诺精确PTS。导出target_time和actual_pts（若可可靠取得），`time_basis`固定写明来源。V0允许目标时间近似；不可用平均fps反算结果冒充真实时间。

每次按顺序解码/缩小一帧，最多4帧进入模型；最多8帧是需另外实测的高级配置。不能一次载入整片HD帧tensor。变帧率、快切、画面内文字和音频均有局限，notes显式说明。重复帧不可伪造新时间内容。

## 5. 四输出与事实/创作分离

一个视觉调用返回观察、推断、未知和可用提示词/关键词。轻量CPU整理可同时生成四个视图；换格式无需再次推理。不能从纯中文通过确定性模板声称自动高质量翻译，英文应来自原始模型字段或用户输入，缺失需显示缺失。

单张静图的运动提示词属于 `creative_additions`，模型猜测的焦距/年代属于 `inferences`。负向词与生成器能力无关时可留空，不自动承诺某个下游工作流支持。

## 6. 后续架构

V1改为独立React/FastAPI/Ollama，不依赖Comfy进程；迁移templates/schema/测试集和纯函数，不迁移Comfy节点状态成为HTTP业务模型。V2才持久任务/资产，V3才跨项目执行。详见本包 docs/14_V1_IMPLEMENTATION.md。



权威任务源为 本包 `plans/tasks.json`。阶段冒烟与完整发布验收分开；S0不得要求尚未实现的导出/完整离线包先PASS。

## V0-S0｜本机基线与节点绑定

只读核对：Windows实际内存、显卡/驱动、ComfyUI版本与Python、PA安装目录/commit/配置/许可、Ollama端点和模型digest、FFmpeg。备份涉及文件并保存哈希，记录已有工作流加载状态。

读取真实节点注册信息，核实图像/视频输入、文本展示/编辑、取消/卸载、输出类型。分别运行真图和4帧最小分析；对比插件与必要的原生Ollama调用，仅用来选最小路径。检查PA实际发出的num_ctx/输入尺寸，不能只信UI值。

产物：`reports/runtime-inventory.json`、`reports/node-bindings.json`、`reports/reuse-audit.md`、baseline日志。只有read-only inventory通过才允许修改。模型阻断时仍能做S1人工部分，不得据此宣布V0完成。

## V0-S1｜图片与独立人工路径

先提供无模型可用的草稿编辑、复制、TXT/JSON导出；再接图片预处理和真模型。若原生面板没有可编辑输出，仅一个薄扩展补齐；不能要求用户另装通用UI平台。

固化默认规则和4输出，raw/建议/人工稿分离。捕获正常、格式无效、模型未回答、超时；错误不扔掉已有结果。输出的机器字段可空，导出仍是合法JSON且带状态，不伪造成功。

真实交付：`workflows/image_reverse_prompt_v0.ui.json`、对应 `.api.json`、`manual_prompt_v0.ui.json`或等价已验原生面板。测试图片输入、4输出、无模型导出、原图不变、注入和超限。

## V0-S2｜视频有限抽帧与资源控制

优先复用已安装视频加载节点，但需先证明解码与内存有界；否则调用已有FFmpeg实现CPU受控采样。上传/探测/抽帧都必须在本机完成；远程URL不作为输入。

显示4帧与时间性质，生成视频描述及运动推断；保存采样顺序与哈希。完成请求级锁、取消晚到、finally卸载/释放监测，验证下一任务不能抢入。真实交付视频UI/API工作流。真视频至少包括静态、跟拍、快切、VFR；高级8帧不通过就不开放，不能默默降级且仍标8帧。

## V0-S3｜完整验收、封装、回滚

冻结10图+6视频质量集，完成12组验收。限制外联、保留loopback，重启宿主/浏览器/Ollama再测试；只清浏览器应用缓存，不删除预置模型权重。记录外联尝试，不仅记录“被防火墙挡住所以没成功”。

资源测试将冷启动与热模型分开；检查默认卸载后恢复空闲。复用环境增量包换到含中文/空格的新路径安装，工作流导入、模型复用与导出正常；卸载本扩展并回滚配置后，原有Comfy工作流仍能打开运行。

最终产物：版本锁/节点依赖表、模型引用而非权重副本、实际工作流、必要扩展与静态JS、templates、diagnose/install/rollback、README_V0、tests及实际验收证据。工具和依赖只在构建准备时安装，正式运行不联网拉包。

## 交付目录（实施后生成，不是本设计包中已实现）

```text
LVW_V0_RuntimePatch/
  README_V0.md
  workflows/{image_reverse_prompt_v0,video_reverse_prompt_v0}.{ui,api}.json
  workflows/manual_prompt_v0.ui.json    # 或已验独立人工面板
  custom_nodes/lvw_v0_bridge/           # 仅确有缺口才提供
  templates/   contracts/   config/
  scripts/{diagnose,install,rollback}.ps1
  manifests/{versions,node-bindings,licenses,sha256}.json
  tests/   reports/                    # 无私密素材默认打包
```

## 修改与依赖纪律

保留用户未提交修改；不强行git reset/全局pip升级。标准库/宿主已装依赖优先；新依赖必须给出缺口证据并锁版本，不能隐含装FFmpeg大包或复制模型。改动在独立扩展实现，确须修PA才提供可逆小patch与文件原哈希校验。


---

# 14｜V1实现方案：独立服务与版本

## R0：从MVP转独立运行

复用V0模板、样本、模型配置、预处理纯函数与已知失败；直调Ollama的图/4帧再测。确认Structured Outputs支持；不支持则保留raw和PARSE_PARTIAL，不自动换云。关闭Comfy后测试，证明独立性。模板搬运记录原许可。

## R1：人工优先骨架

FastAPI同源SPA、受控媒体multipart streaming、ShotSpec、六模式/四目标、纯CPU编译先落地。SQLite foreign_keys/WAL；shot可更新、revision append-only、job记录。初始DDL见contracts/storage.sql，生成迁移而非运行时随意改表。已存在介质hash相同可复用内容引用但业务asset不同。

React和CLI共用Application Service。人工新建无媒体shot；保存传If-Match；同事务读取当前etag、验证、插入revision、更新head。冲突412显示当前版本，不覆盖。revision hash只针对规范化内容，服务器时间/随机ID不参与内容相同判定。

## R2：模型与任务

submit分析获得202；单worker领取queued，分配attempt_id/lease_token，输入预处理和Ollama请求。请求一律本地固定base_url；不传工具或外部URL。format校验后保存raw/parsed，partial可带建议。模型返回不写人工revision；用户采纳再保存。

cancel：queued直接终止；running设置cancel_epoch并关闭/停止当前调用，资源仍busy直至实际释放。终结CAS必须匹配attempt_id+epoch；晚到丢弃。异常try/finally卸载并轮询，不能仅依赖下游节点。默认并发1，竞争外部GPU返回RESOURCE_BUSY。

V1进程重启把running标interrupted，不自动重放，用户显式retry新attempt。幂等submit同键同载荷返回原job；同键异载荷409。取消/保存幂等各有作用域，不能重用一个键覆盖不同动作。

## 编译和目标映射

从四来源域和人工锁定字段生成目标文本，按用户锁定>镜头>场景>项目配方>模板>机器建议合并；冲突列表可见。natural输出中英已有内容；image选自然或tags；edit输出源保持/变更/约束；motion输出主体动作/相机/节拍/时长。缺事实留unknown，缺英文留待补，不额外偷偷调用LLM。

## 导出与便携

TXT/JSON/轻项目包显式导出；V0 JSON导入创建新的来源和revision，不能假称V0已保存不可变版本。发布包包含便携Python、FFmpeg、dist、依赖锁/许可；模型仍外置。no npm/pip运行安装。中文路径、无开发工具宿主、恢复和断网验收。

## 测试与产物

24组合编译、API/Schema/类型、ETag/幂等/取消、原图不变、无模型编辑、真实推理/资源、12图+6片、便携包。R1/R2所有产物必须是代码和真实测试，不以HTML设计稿代替React。


---

# 15｜V2实现方案：结构化创作资产与Agent

## R3：镜头与时间

视频导入引用+hash，ffprobe/解码器读time_base、start_pts、best_effort_timestamp，帧索引保存实际PTS和time_base分子分母。规范时间t=(pts-origin_pts)*num/den，存整数ticks与有理数，展示ms四舍五入；片段[start,end)。VFR禁止frame_index/平均fps充当真时间。

PySceneDetect给候选切点，再映射实际解码帧；缺失/不单调PTS标time_unverified并可人工校订，不能伪造精确。人工改边界新版本保留旧，Prompt证据引用具体scene_revision。每镜头有限窗口，最多8帧需配置实测；长片只保留活动窗口，释放解码buffer，不线性增长内存。

## R3：资产、检索、配方与对比

asset是引用+类型+来源权限；content hash去重不是删除源文件依据。media、scene、prompt_revision、style_recipe组成关系；library搜索文件名/人工标签/描述/来源，FTS5明确不是视觉语义检索。中文采用经目标SQLite验证的trigram/确定性分词方案；不支持时降级有界LIKE并说明，1000引用性能仍需达标。

style_recipe append-only、版本化字段/锁定/来源；模板改动不修改旧Prompt。属性对比使用同一schema和双方版本，显示observed/inferred/unknown，**不是身份或真实性鉴定**。QC只输出黑帧/冻结/模糊候选、算法参数和采样证据，不自动删除或拒绝素材。导出分镜CSV/Markdown/JSONL+manifest+来源域；机器标签不冒充人工标注。

## R4：任务恢复

batch拆child job，独立状态、父进度是已终结项/总数；失败项不回滚成功项。claim用原子事务，lease过期转interrupted，重试新attempt；写入fencing令牌。临时工件在attempt目录，成功同卷原子rename后事务注册；重启扫描未注册临时文件按保留期清理，绝不删引用工件/原片。

明确at-least-once调度+幂等提交，不承诺任意副作用exactly-once。SQLite一次writer串行，busy_timeout/有限重试；磁盘满回滚并保留人工工作稿提示。备份通过SQLite backup API一致性snapshot，manifest哈希，先校验再restore。

## R4：MCP

8白名单工具见合同，stdio桥接已有服务，schema复用Pydantic；只传资产/镜头ID，不允许任意路径/SQL/Shell/URL。授权scope对应读/分析/修订，不包含内容审查。长任务立即返回job_id，后续poll/cancel，不占用会话直到视频完成。实际Codex或Claude Code客户端发现、调用、错误/取消测试必做。

## V1升级

迁移前backup，事务DDL加表/索引，原revision ID/hash不变，重建可重建的FTS索引。中途故障回旧代码+旧库。资产缺失显示offline_missing，用户选择根目录重绑定后hash校验，不偷偷联网补文件。

## 产物

时间与镜头模块、资产/配方UI、迁移SQL、数据导出、batch/recovery、MCP桥接、测试/兼容报告。关键验收A13–A17/F06/X04–X06，累计V1回归。


---

# 16｜V3实现方案：项目群薄适配

## R5a：合同发现与能力握手

记录每个对端实际版本、连接方式、接口、权限、字段、支持功能和兼容测试hash。请求带contract_version、caller_id、correlation_id、source_revision、idempotency_key。缺字段/不支持版本显式错误，不通过“随便JSON”容忍猜错。合同提案见contracts/integration-contracts.json，不假设对端已实现。

### Navia → LVW

只接收用户显式保存且授权范围内的evidence包：稳定knowledge_ref、citation_id、source_url、quote/summary、source_hash、consent_scope、rights_note。source_url只作引用，不自动fetch。cookie/token/本地绝对路径/原始媒体不允许字段；需要图像时独立授权导入受控asset，不从引用反解浏览器存储。保存来源与撤销/失效状态；撤销不篡改历史已发布revision，但新使用警示并遵循访问范围。

### Narralens ↔ LVW

入站project/shot外部ID、源版本、brief、reference_ids、目标/约束；LVW建立映射，不复制全项目。返回建议ID、prompt_revision_id、compiled内容、证据/未知、基于哪个shot版本。Narralens独立决定采纳；旧shot版本建议不能自动写入新shot。重放同幂等键返回同建议，收到采纳回执只记录receipt，不改变生产审批。

## R5b：Comfy生成交接

只允许冻结workflow_id+workflow_hash+节点版本，参数映射仅允许提示词/受控媒体ID/已批准种子与尺度等白名单，不接受任意节点JSON、脚本节点参数或路径。LVW解析到受管中转目录；模型权重缺失明确BLOCKED，不自动下载。

提交记录先落outbox；成功存external_prompt_id再查询history/queue。响应丢失而不知是否提交时状态SUBMISSION_UNKNOWN，按受支持的关联标识/历史人工或程序核对后再决定，**不能自动重试产生重复视频**。Comfy不提供原生幂等保证时不宣称exactly-once。

取消只删自己的待执行队列项；若/interrupt是全局当前任务，只在确认当前prompt归本请求并独占该执行槽时调用，否则报告CANCEL_UNSAFE而不是误杀其他任务。/free不代表Ollama卸载，两者分测。

GPU协调由协作生产者共用租约+心跳+fencing，外部非协作客户端只能检测和提示。停止推理、确认释放，再授予生成；租约过期但GPU仍忙不能盲目启动。LVW只映射执行任务，不重建导演工作流或剪辑器。

## R5c：UI、恢复与E2E

集成页显示授权、可用/不兼容/待交接/已接收/执行中/未知，按钮可见而非“全绿成功”。外部离线不锁人工稿。完整E2E：授权Navia引用→Narralens brief→LVW分析/人工修订→建议回执→受控Comfy工件→Narralens引用，验收只检查LVW责任范围与端到端交接，最终视频剪辑质量仍Narralens负责。

升级/回滚包括代码+匹配DB+模板+工作流映射，外部版本不兼容拒绝自动继续。干净Windows宿主离线部署、旧数据迁移、磁盘/进程故障重放、隐私字段不外泄全部记录。

## 发布

A18–A22/F07/X07–X09全PASS及V1/V2回归。对端不可用或缺真实工作流仅可INTEGRATION_BLOCKED；模拟合同通过不是V3_ACCEPTED。生成质量不靠一次成功执行自证，保留Narralens的复检责任。


---

# 17｜数据、来源和版本设计

## 实体及权威

V0仅一次run/会话draft/显式导出。V1：media_ref、shot、model_run、prompt_revision、job/attempt。V2：asset_link、scene_revision、recipe_revision、batch、FTS、backup_manifest。V3：external_link、evidence_ref、outbox、handoff_receipt、workflow_allowlist。SQL是建表起点，版本化迁移和字段校验由实际实现补齐，不把设计DDL称为完整数据库实现。

shot_id是可编辑工作对象；revision_id不可变；prompt_id/模型任务ID不混用。analysis结果带model_digest、template_hash、input_hash、config_hash、采样记录；raw不可自动覆写。null表示未知，不用空字符串伪装已确认。人工锁定字段优先，模板升级不传播到既有revision。

## 四来源域

observation来自可见内容及对应帧；inference有不确定解释；user_evidence有来源引用与权限；creative_intent是用户扩展。引用来源不证明真实；史实/科学确认由用户依据外部资料承担，不自动“已验证”。静图运动只能在creative_intent。

## 时间与关联

frame_index是显示顺序，source_pts/time_base才是真时间；time_basis=sample_target或decoded_pts。scene [start,end)并带版本。下游Prompt引用scene_revision和evidence而非可变“当前镜头”。迁移不得将V0近似time改成精确。

## 修订与删除

append-only revision事务保存规范内容hash（UTF-8、排序key、数字格式固定）。shot head通过ETag CAS更新；已有revision没有更新删除API。用户删除资产默认tombstone/解除引用，原始媒体不删除；独立隐私清理工具在用户授权下按引用图删除LVW自有工件与相应记录，并生成不含内容的审计清单，不伪称append-only永久不可依法清理。

## 项目包

manifest列schema_version、app_version、IDs、内容hash、模板hash、媒体相对引用/可选复制、许可/来源备注；禁止绝对路径、凭据和任意代码。轻包不含模型/原片；完整包只含显式选择的媒体。校验所有路径、压缩比/解压上限、哈希、Schema、外键和来源授权后事务导入。

ID碰撞同hash复用，不同hash拒绝或生成映射并保留原ID，不能最后写覆盖。升级迁移先snapshot；回滚旧代码和对应snapshot，不能旧代码打开新schema硬撑。


---

# 18｜模型、规则和Prompt实现

默认复用用户已有Ollama gemma4:26b；本机报告不是实际验证。tag可能移动，验收锁digest。Heretic/H3编码器文件不直接当聊天VLM；新模型只在明确质量/兼容缺口并批准后引入。无自动fallback到云或下载权重。

## 单次分析

安全读图/EXIF/色彩/透明合成→限制长边/像素→视频附时间性质→系统规则+六模式+用户意图→Ollama /api/chat→raw→Schema解析→机器建议。外层run_id/hash/模型/时间由代码填，不让模型生成。format仅校验形状，不确认事实。

默认num_ctx4096、num_predict1536、temperature0.2、单并发、4帧；8帧/8192必须单独实测。thinking参数仅在/api/show证明支持时配置，不臆造参数；默认不保存内部思考字段。超时/解析异常不无限重试、不重复抄问绕过模型行为。

## 模式与模板

六模式文件只设视觉观察重点与创作边界。统一四来源域后，CPU compiler根据目标做结构排列和字段取舍。每次编译存模板版本/hash和warning。用户锁定优先；合并冲突返回提示。图像自然语言与SD标签分开；edit/motion专用模型适配确认后才启用，不用名字冒称已对接。

模型输出中英缺一项就标缺失，不能靠拼接宣称翻译准确；允许用户手填或显式新建润色任务（非V0必需）。negative仅来自用户/模板兼容配置，不反推“原图真实负向词”。

## 模型未回答

明显声明不提供内容可记MODEL_REFUSAL/DECLINED，不能因某词或空字段自动判违规；不确定记NO_USABLE_OUTPUT。UI保留raw、建议、人工稿。没有NSFW分类/审批；文件/访问安全继续生效。

## 工具复用

PA已有规则通过许可证与本机版本核查后使用；输出cleaner不得修改raw/人工版本。OIP风格卡可选，只读参考不作为事实来源或模型能力。生成器不支持的参数留notes，不能造成错误参数请求。


---

# 19｜打包、本地部署与迁移

## 三种交付强度

V0：依赖已验证宿主的增量包，workflow+必要扩展+规则+绑定/安装/回滚。不复制Comfy/PyTorch/模型；同机重定位测试，不宣称任意机器即用。

V1：Windows便携Python/FFmpeg/前端dist/锁定依赖+启动诊断，外部已有Ollama与模型作为明确前置。无Node/npm/pip运行安装、无现场编译、无模型下载。venv不能未经验证直接当可移机运行时。

V2/V3：软件、数据、模型分开，项目轻包/完整包、SQLite一致性备份、升级/回滚、新用户/干净宿主验证。Linux发行不是V1必选；需要时单独按ABI构建，不能复制Windows二进制。

```text
LVW/
  releases/<version>/{python,app,frontend/dist,bin}
  launcher/ config/ manifests/
  data/{catalog.sqlite,artifacts,temp}
  projects/ exports/ backups/ reports/
# Ollama模型外置，项目包只记digest，不重复存权重
```

## 安装与诊断

检查OS/驱动、端口、写权限、剩余磁盘、FFmpeg、依赖hash、模型存在和能力、SDK版本。仅修改当前应用允许目录，保留用户未提交变更。供应链目录列license/SBOM、原始来源和可逆patch。运行禁止自动更新/拉包；依赖缓存只属于构建阶段。

## 离线

禁外联并观察尝试，保留127.0.0.1；预置权重不清除。浏览器无CDN字体/图片/分析脚本；Ollama云功能按实际版本关闭，插件云provider/回退禁用。所有配置需实测，不把开关当安全沙箱。

## 数据迁移和回滚

SQLite backup API取一致性快照，不只复制正在写的.db。备份manifest、hash、schema、模板和工件引用；先在新目录restore+integrity_check+foreign_key_check+计数/修订hash核对再切current。业务数据不放release内。升级失败恢复旧代码+匹配旧库；保留用户升级后新导出文件，不删除外部原媒体。

新机器媒体通过用户选根重绑定相对路径与hash，缺失可人工编辑但不能假称可回看。模型可复用按digest检验，不以同tag当相同权重。隐私导出不含凭据、绝对路径或默认全片。

## 预算

V0≤20MiB增量目标；V1核心≤2GiB目标，模型/用户媒体不计；超预算需依赖清单与批准而非默默增包。运行用户手动clone=0、pip/npm=0、CUDA编译=0。V3验证完整恢复时间并报告实测，不预先写无法支持的RTO。


---

# 20｜可靠性、故障恢复与运维

## 状态机

job: queued→preparing→running→succeeded/partial/failed；取消经cancelling→cancelled；重启残留→interrupted；显式retry新attempt。resource: unknown/busy/releasing/released。job终止不等于resource released；新的GPU任务需二者条件满足。UI显示当前attempt和可重试原因，不无限轮询。

V0会话内run_id/draft_epoch；V1持久attempt+cancel_epoch；V2lease/fencing+batch；V3外部receipt/outbox。对相同Idempotency-Key不同payload拒绝；晚到attempt不允许写shot head/revision。

## 提交和副作用

纯分析可重试但保留旧run；不可变修订用唯一业务键防重复。工件先临时目录、完成哈希、原子rename、事务登记；失败清理只针对本attempt。外部Comfy响应未知不自动重试，先reconcile。不存在任意跨系统恰好一次保证。

## 取消

UI≤1s反馈；停止/卸载单独观测。V0 Comfy全局interrupt不能误伤其他工作流；V3确认所有权后才能用。HTTP断连不是GPU已停，查询/api/ps及显存。取消60s未停止标资源仍占用，人工操作不锁；记录诊断，不kill用户进程。

## 资源与重试

单GPU任务；超限输入在预处理前拒绝，CPU预处理流式。可恢复网络断连最多一次**显式或受控**重试，仅在确认无外部副作用时；OOM不自动提高ctx/无限换模型，推荐降低配置由用户确认。驱动异常/磁盘满错误可读，数据事务回滚。

## 观测

每请求request_id，业务job/attempt/asset/revision/external_id；日志默认元数据不含私密正文。指标load/preprocess/infer/compile/queue/release时长、GPU/AvailableRAM、错误码、取消终态；诊断包显式导出脱敏。记录stage_report与证据hash，不用日志“success”自证结果正确。

## 运维命令目标

`diagnose`只读；`backup`一致性snapshot；`restore --dry-run`先校验；`migrate --plan`展示版本；`rollback`切软件+匹配数据；`clean-temp`仅LVW临时根且不碰活动lease；`export-project`显式范围。这些是实施命令合同，不是本包已提供生产命令。


---

# 21｜风险、决策与变更控制

| 风险 | 触发证据 | 处理，不扩大范围 |
|---|---|---|
| 当前PA/模型能力不匹配 | 真图/4帧失败 | 最小薄适配；仍失败BLOCKED，不马上装一堆模型 |
| 4090峰值超预算 | 实测OOM/ctx自动膨胀 | 硬限制输入/ctx，单任务；配置修改留ADR |
| 质量不满足 | 独立评分未过 | 改模板/样本错误定位，保留原测试；不删失败样本 |
| V0手工依赖模型节点 | 断Ollama不能导出 | 独立CPU面板/流程，不能用文档教用户绕过作为通过 |
| V2资产库变成复制媒体平台 | 文件/DB急增 | hash引用/分页/缓存配额；不默认上外部DB |
| 对端合同不存在 | V3握手失败 | 薄适配本地完成，真实E2E BLOCKED，不接管对端开发 |
| 插件或模型许可不清 | 缺许可/来源 | 不复制相关资产；保留用户已有调用，交付标许可待核 |
| 本地Agent用云模型 | 数据流越界 | 区分开发助手与运行时；离线目标必须本地执行方 |
| 多份旧计划冲突 | 同ID指向不同门槛 | 当前master为准，legacy只读，crosswalk更新 |

任何范围/技术栈/硬门限改变需ADR：problem、evidence、options、chosen、compatibility、migration、tests、approval。不得因为失败将P0改optional；不得悄悄新增自动内容审核。开发者可以修不改变合同的bug，但需重跑受影响用例。

终态：V0/V1/V2/V3_ACCEPTED、ENGINEERING_READY/QUALITY_PENDING、INTEGRATION_BLOCKED、NOT_ACCEPTED。文档检查通过只叫DOCS_VALIDATED。每阶段留下未完成项和原因，避免“设计完成”变成“产品可用”。
