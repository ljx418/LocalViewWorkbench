# R1-CORE 只读复用盘点 01

root架构/下一Stage文档准备；不启动R1产品实现、不冻结Gate0、不变更合同或阶段计数。基于当前主工作区源码，非实机/测试结果。此前统一切片3/3人工签署继续有效，不扩大为完整R1。

| 现有路径与实际行为 | R1复用与补齐 |
|---|---|
| lvw/backend/app/main.py：上传、readiness/runtime、analyze、任务查询/取消、media/model-run读取 | 保留同源API及运行服务控制，增加合同要求的业务路由；不用第二个临时前端或另一个模型入口 |
| service.py:AnalysisService：jobs/runs/idempotency均dict，串行锁、cancel_epoch、监控和显式终态已有 | 保留推理/资源/取消owner，持久化职责分离到repository；现有进程内幂等不等于重启后的持久幂等或完整CAS |
| media.py:MediaStore：媒体文件受控写入，refs/paths为dict，video_kernel受控解码 | 复用上传/媒体边界与已有文件，新增SQLite受管索引与重启恢复；不按镜头复制整片，不读取私有运行目录做本次盘点 |
| models.py：已有strict AnalyzeRequest/Job/ModelRun/PromptSpec/FrameRef | 保持canonical兼容，不用新DTO替换原形状；新增Shot/Revision存储及补充语义按冻结合同，MS绑定仍留M1 |
| frontend/src/App.tsx：useState维护人工稿/采纳来源、显式采纳确认和TXT/JSON导出 | 复用工作台及人工保护体验；接入持久化shot/head/修订，补ETag冲突和锁定，不将UI确认框当事务CAS |
| frontend/src/domain.ts：adopt/asText/asJson纯CPU映射，export标记人工/采纳来源 | 现有映射不是完整六模式四目标共享CompilerOwner；抽取/扩展共享服务并让CLI同源，格式切换不新增推理 |
| contracts/storage.sql及v1-multishot-migration.sql | 前者是合同DDL，后者是设计迁移候选；文件存在不证明实际运行SQLite或已迁移用户数据，不直接执行全部V2/V3表 |

## 与已批准R1四子项对应

A：受控media/shot/SQLite初始迁移。先冻结R1实际需要的v1核心表及repository事务范围；已有媒体边界复用。测试真实临时SQLite/重启/坏版本回滚，不用dict假持久化。
B：不可变PromptRevision、强ETag/If-Match、锁定/显式采纳。保留原始ModelRun；人工头变化与来源绑定同事务，错etag/晚到/取消/重复幂等负例验证人工头不被覆盖。
C：六模式四目标、导入/CLI共享服务。已有单图/整片分析语义保持；旧导出格式需兼容读取/明确迁移规则，不把CPU映射叫模型翻译。实际合同请求/响应字段与错误码在R1-CORE packet统一冻结。
D：一次集中相关回归、独立审查、真实体验门槛。统一切片历史签署只作为前置/回归事实，不替代新持久化与修订路径人工体验。

原R1四子项保持0/4；R1前置仍为当前S3按批准衔接完成，M1依赖R1存储/修订，R2完整恢复/CAS/便携仍后续。不得根据本盘点跨Stage实现、直接打开用户数据库或扫描运行媒体。下一R1-CORE packet还须精确允许文件、有效合同hash、测试命令/固定分母、迁移清理与有限真实预算；当前未生成这些冻结项。

## 本次读取的源码身份

- `lvw/backend/app/main.py` SHA256 `b76497f3f643a72810b98593b5efa5d60e4027f093907cd06122e6963289f430`
- `lvw/backend/app/service.py` SHA256 `920938f173f783449e87a0aa6109867ee71ce81ec2306286c55380f0b6698e99`
- `lvw/backend/app/media.py` SHA256 `7ab26a283b9faa45bfc361702e2106eb9c0e46094225f3f64212b9fbaedc4607`
- `lvw/backend/app/models.py` SHA256 `c822649d8de6cd37e0699ca16c5402d2c3221ea2e8a0f84cdece4ccc5f94c2bf`
- `lvw/frontend/src/App.tsx` SHA256 `c014512685c694e9266bd0ee86c81910a9b83603078fcd53cf89af2bbf5dba89`
- `lvw/frontend/src/domain.ts` SHA256 `927f05854ff459217d342ea0a66e043c61cb1ca07337883ee19337e5e1745b99`
- `lvw/frontend/src/api.ts` SHA256 `b06422c2715d5968982947a147848f64d6da78ad77f4213e4752ea790b202f5c`
- `lvw/pyproject.toml` SHA256 `f85167b72d21ffe7a786caef80721844be083e7f77111365aa563ea76c5114bc`
