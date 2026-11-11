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


## 2026-11-11批准的V1范围与角色修订

旧canonical合同与R1切片packet不静默改；候选overlay由Codex独审后Gate0激活。 权威执行索引见[新版V1计划](30_V1_REVISED_EXECUTION_PLAN.md)、[详细架构/合同](31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md)、[验收与Orca协作](32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md)。本节覆盖此前“自动切镜全部只在V2”的范围表述，不回填任何产品PASS。
