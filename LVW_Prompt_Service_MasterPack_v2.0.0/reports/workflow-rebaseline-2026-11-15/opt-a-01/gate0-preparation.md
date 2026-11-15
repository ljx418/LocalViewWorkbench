# OPT-A 首批准入准备

候选封存已发回原ClaudeCode实例；尚未收到提交，不作运行ACK。现有未提交源码与hold记录hash一致，其他dirty报告保留。Orca观察liveness为unverifiable，不将其解释为已退出或正在执行，不新建替代实例。

## 最小文件/owner划分

- root：政策、执行计划、候选/依赖绑定、命令、义务映射、门禁裁决。
- ClaudeCode：先原样提交现有测试源码；后续仅冻结范围内必要夹具修复。生产broker/custody保持不变。
- 隔离reviewer：只读新候选与原始结果，复核假绿/真实清理及辅助诊断资格，不能修改后自行签署。
- 自动执行器：guard先行、精确选中节点、原始退出码/报告及FD/线程终态。

## 本次发现的具体前置

1. correction23源码仍把EVIDENCE_DIR写死在旧23证据目录；封存候选只证明可恢复，不允许直接重跑。正式目标候选须将输出绑定到全新运行根，且只修改此必要接线时也要新SHA。
2. 既有trusted runner直接使用plan.nodeids，能够运行明确子集并检查实际收集顺序；不需要再开发一套runner。
3. 原189节点保持完整定义，定向子集报告单独分母，不能算189通过。14个T10组仅是选择候选，尚未冻结最终子集或预算。
4. 依赖pins和guard复用前须逐项核验；CPU组件不读取全局SQLite，不恢复已消失的历史临时counter。

## 退出顺序

源码封存收据 → 新输出接线候选 → 源码/guard/依赖/命令/节点/预算/清理全部绑定 → root ACK → 单次定向反馈 → 集中独审 → 必要修复及新候选 → 固定集合checkpoint。前两项未完成，当前Gate0为PREPARATION，不是PASS。

逐业务Workpack的设计/编码/运行/正式退出前置仍以plans/v1-workpack-development-map.json为准；下一步按实际代码及证据细化，未完成的前置不写为已满足。
