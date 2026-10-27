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
