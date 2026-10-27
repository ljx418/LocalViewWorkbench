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
