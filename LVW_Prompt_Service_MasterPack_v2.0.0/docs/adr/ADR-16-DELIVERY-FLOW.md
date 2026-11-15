# ADR-16｜有界验证反馈与开发准入分层

2026-11-15，用户已批准 CHANGE-V1-DELIVERY-FLOW-01。批准依据：[审计](../../reports/optimization-audit-2026-11-15.md)，原话与边界：[批准记录](../../reports/workflow-rebaseline-2026-11-15/approval.json)。

立即生效：O1受控定向验证前置、O2辅助诊断义务分层、O6固定问题台账与证据差异复用。O3职责拆分只做最小内部提取并重新冻结允许文件；O4先做逐Workpack依赖审计；O5只在关键安全和有限运行计划具备后执行代表性pilot。本次不新授运行次数或产品PASS。

定向检查、固定189组件checkpoint、产品29项、人工签署是四个不同层次。运行候选前仍由root封存源码/guard/依赖/命令/预算并ACK；取消“辅助静态细节全部关闭才能启动任何受控定向检查”的循环前置。旧packet原样保留，新候选使用[优化组件合同](../../reports/workflow-rebaseline-2026-11-15/optimized-n1-01/contract.json)，其运行计划尚未冻结。

产品数据/原件/权限/隐私、实际资源清理、假绿、固定集合或质量阈值、候选和证据身份、必要签署继续阻断。仅当运行已真实FAIL、必要原始结果/原始错误/候选绑定/授权和清理事实均可验证、缺失仅为辅助附加诊断且无产品/假绿风险时，可由隔离审查列Minor技术债，登记owner及退出条件。任何未知均不满足例外，不能由实现者自降级。

旧M2/M3审查不改写，新版本按[义务复核表](../../reports/workflow-rebaseline-2026-11-15/optimized-n1-01/obligation-review.json)重新取证；当前没有任何Major因本ADR自动关闭。关键事实写入失败或未知清理仍不得PASS。

正式Stage DAG与历史完成数不变；[Workpack开发准入映射](../../plans/v1-workpack-development-map.json)区分设计、离线编码、本机运行、正式出门。未经Gate0和实际前置验证的路线仍为待激活；单写入Stage、独立审查、人工门槛、429停止及原累计预算不变。不得用开发准入冒充正式验收或签署。
