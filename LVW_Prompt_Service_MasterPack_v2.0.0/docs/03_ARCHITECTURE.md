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


## 2026-11-11批准的V1范围与角色修订

V1新增SceneRevisionOwner、FrameEvidenceOwner与有界持久化父子任务，单体/SQLite/单GPU不变。 权威执行索引见[新版V1计划](30_V1_REVISED_EXECUTION_PLAN.md)、[详细架构/合同](31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md)、[验收与Orca协作](32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md)。本节覆盖此前“自动切镜全部只在V2”的范围表述，不回填任何产品PASS。
