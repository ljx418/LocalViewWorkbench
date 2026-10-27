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
