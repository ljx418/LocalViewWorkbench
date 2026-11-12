# 33｜V2 产品目标调整：视觉素材理解与整理

2026-11-12，CHANGE-V2-LIBRARY-01 / ADR-15。**用户已提出并授权本次产品目标和设计调整；详细合同为候选，未激活 V2 业务 Stage、原件写权限或真实素材运行。** 文档包 v2.0.0 不是产品 V2。当前产品坐标仍读取 execution-control，不改 V1 目标、在途任务、已签范围或429停止规则。

## 产品与核心用户路径

LVW 调整为本地优先的视觉素材理解与整理工作台。带来源的视觉观察共享用于提示词反推、素材描述/标签、可审核命名与归档。优先服务大量本地 DJ 视频及通用视觉素材，同一个 React/FastAPI/SQLite/Ollama 单体；不新建桌面程序、媒体平台或生成引擎。

可信本地入口登记目录及 scope → 分页扫描/受控引用 → 可选本地分析或手工描述 → 中文/英文模板 → 原名/新名/缩略图/依据/unknowns/冲突预览 → 编辑生成新修订 → 确认精确选中项 → 不覆盖改名/同卷归档 → 逐项结果、映射导出、审阅撤销。模型不可用时仍可完成人工描述、计划、应用与撤销；CPU渲染/编辑/预览/执行/撤销不调用模型。

## 本期必须包含与范围外

| 核心义务 | 需求候选 | 生产职责 |
|---|---|---|
| 本地根登记/撤销、分页/取消扫描、原片引用、缺失与重绑定 | R23 | SourceRegistry |
| 图/视频真实描述、来源、人工修订与锁定、unknowns | R24 | AssetDescriptor |
| 中英模板、受控词表、长度/序号/缺值策略、DJ/通用预设 | R25 | NamingCompiler |
| 原新名/证据/缩略图/冲突预览、选中确认、CSV/JSON计划 | R26 | RenamePlanner |
| 不覆盖批量改名、登记范围内同卷归档、幂等/部分成功/取消重试 | R27 | FileOperationService |
| 持久日志、重启协调、可审阅且有冲突检测的撤销 | R28 | FileOperationJournal |
| 资产检索/旧名可查、稳定asset/media/Prompt/Scene身份 | R29 | AssetRepository/FTS |
| 有界大视频profile、严格分析复用、离线模型与无模型人工路径 | R30 | LibrarySampling/既有任务及Provider |

原 R13真实PTS、R14资产/配方、R15 MCP、R16通用批次/恢复/备份、R21对比/QC/JSONL及V1累计回归全部保留。L1–L4是R3/R4内新增工作包，不取代原有子项。

L5独立扩展：watch folders（默认只建议）、显式auto apply、PDF/Office、更多容器/音频、跨卷移动。BPM、调性、曲名识别、ASR、联网识人/演出查询不在核心；不承诺全功能等价RenamerX。现有短视频60秒/256MiB/4帧入口不放宽，MKV/AVI未验证不开放。V3对端数据权威和原V0/V1硬门限不改。

## 真实性与命名语义

每个事实字段保存 value、来源类型、引用及版本、确认状态和unknown原因。视觉事实需要实际帧/时间覆盖；可信技术元数据来自受控探测；人工确认记录用户及来源。inference可展示但不得静默提升为确定事实。creative_intent、风格化Prompt和模型推测不能写入事实字段。

姓名、DJ真实身份、演出/地点/日期/曲名必须有可追溯且经确认的来源；原文件名、OCR、容器标签先是候选，文件创建/修改时间不是演出日期。不能从画面猜BPM/调性/具体歌曲，也不能从像素位移直接断言运镜。

预设固定为：已确认元信息 `{DJ}_{Event}_{Date}_{VisualSummary}_{Seq}`；未确认元信息 `DJ现场_{VisualSummary}_{Seq}`。不预填实际人物/日期。缺值策略按字段配置 omit / pending / block；身份事实默认 block 或 omit，不能要求AI补齐。英文缺失保持unknown，纯CPU模板不伪造翻译。

## 现状核验和复用分层

核验基线56832a43a2beb05f03ea7a00a66e198acfdd19f7，与外部方案b1a9386快照不同。[源码事实与冲突记录](../reports/v2-library-design-2026-11-12/change-record.json)绑定文件哈希。外部方案仅作为设计输入。

| 层次 | 可复用内容 | 不能推导的结论 |
|---|---|---|
| 当前源码可复用 | React同源UI、FastAPI、Ollama/资源单槽、Prompt四来源域、受控短片CPU解码、原始模型结果 | media.py refs/paths为字典；图片转PNG、视频复制；source_root_id/relative_path=null。service.py jobs/runs/idempotency内存、Lock串行、128任务。均不证明源库/千文件持久任务 |
| 最终V1通过后才可复用 | R1修订/CAS/SQLite、M1帧证据/Scene修订、R2持久任务/attempt/取消 | docs31和候选DDL是设计输入，未交付部分不得当实现。V2准入重新核对真实schema/owner/迁移版本 |
| V2新增 | 源目录授权、描述修订、纯CPU命名、计划修订、唯一文件写owner、日志/恢复/撤销、大视频profile | 无原件绑定的上传副本只能生成建议，不能写原文件；最多12镜头的shot_batch不承载千文件命名 |

## 合同与验收状态

[架构](34_V2_LIBRARY_ARCHITECTURE.md)、[执行与验收](35_V2_LIBRARY_EXECUTION_AND_ACCEPTANCE.md)、[ADR](adr/ADR-15-V2-LIBRARY-NAMING.md)。机器候选位于 plans/candidates/v2-library 与 contracts/candidates/v2-library；设计快照可哈希审阅，尚不是生产合同激活。

新增 RN01–RN18 与 R23–R30；V2候选累计38+18=56，V3候选累计47+18=65，V1保持29。当前 canonical gates 仍38/47，**只证明旧范围**，不得据其对新增功能签V2/V3。完成独审、pilot依据和正式Gate0激活后才合并候选；不得保持旧30项声称覆盖新增能力。旧收据和失败不改写。

建议可应用率>=90%、事实编造0、覆盖/丢失/内容修改0，1000引用分页检索P95<=1s、CPU预览P95<=2s，均为待pilot校准的新目标；目前无实测、无预算批准、无生产PASS。安全不覆盖/不丢失/不改内容是协议义务，不能通过pilot放宽；旧硬门限不降低。
