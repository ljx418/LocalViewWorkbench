# ADR-15｜V2 视觉素材理解与可审核命名整理

日期2026-11-12；CHANGE-V2-LIBRARY-01。状态：PRODUCT_INTENT_ADOPTED / DESIGN_CANDIDATE_NOT_ACTIVE。用户明确授权目标与文档调整，未授权真实源目录、V2运行预算、质量阈值冻结或产品PASS。

Problem：现有Prompt反推不能安全承载本地大量DJ素材命名、原位整理和撤销；上传副本不是原件授权，内存任务不具跨重启保证。

Evidence：基线56832a4源码与执行坐标核验，见reports/v2-library-design-2026-11-12/change-record.json。外部考察文件已读取并哈希，仅为设计输入。

Options：截取Prompt为文件名（丢来源/恢复/权限，拒绝）；独立桌面/资源平台（重复栈/权限，拒绝）；同一单体共享视觉证据、独立描述修订+CPU命名+唯一写owner（采用）。

Chosen：V2以R3/R4承载R23–R30、RN01–RN18候选增量；SourceRegistry/AssetDescriptor/NamingCompiler/RenamePlanner/FileOperationService与原持久任务/资产owner组合；不复用shot_batch12代表千文件。原R13/R14/R15/R16/R21义务保留，L5单独后续。部署及GPU模型不变。

Authority resolution：ADR-07“引用优先/不复制原片”和旧“默认不改源文件”继续成立；仅V2新增登记、显式rename_archive scope、精确计划确认后的唯一owner例外，当前V1仍无原件写权限。原30/39计数是旧设计，已生效多镜头基线38/47；新候选为56/65，未激活前不能据旧门禁签扩展产品。MasterPack v2.0.0非产品V2。

Compatibility：canonical API/core schema/Job/batch/DDL及当前Stage packet/manifest不改，增量候选独立存放；未来overlay仅增不相交路径及Library_组件。V1仍29项。已签621b1bf统一切片不扩大，S2历史7/8及S3失败/阻断保留。

Migration：实施前审计最终V1实际schema和迁移号，一致性snapshot/校验、事务增量，外部文件journal和DB分离，restore后先协调不盲重放；不在真实库执行候选DDL。

Consequences：新增原生Windows身份/no-replace/句柄防替换、日志和可恢复撤销工程量；不能以exists+os.replace或SQLite事务冒充安全原件操作。稀疏长片采样不证明整场理解；BPM/调性/曲名/身份查询等范围外。

Tests：RN01–RN18明确生产入口/Oracle/负例/终态/清理，真实原生故障与授权30样本/独立留样、V1和原V2累计回归；当前仅确定性设计验证，未来native/model/UX尚未证明。

Approval：用户产品意图与本次设计落盘指令为依据；设计候选需隔离审查、pilot及正式Gate0；新预算/路径/指标批准记录均null。当前V1 WAIT_BUDGET不受此新任务解除。
