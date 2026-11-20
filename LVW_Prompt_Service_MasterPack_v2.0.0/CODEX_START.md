# Codex开发入口｜读取当前坐标，按冻结包推进

## 下一goal

直接使用[RC-FINAL接续提示词](plans/packets/rc-review07/next-goal.md)。它依据用户已批准的[流程spec](docs/37_DELIVERY_EFFICIENCY_SPEC.md)和[最新路线](docs/38_EXECUTION_PLAN_REFRESH.md)，不重做已签R1a或统一图视频切片。

```text
读取AGENTS、.agent-governance/README.md，运行python3 -B tools/show_execution_coordinate.py查看唯一execution-control的当前视图，再读docs37/38、当前packet和机器流程spec。
Codex负责架构/接口/故障Oracle/门禁，可见ClaudeCode作为单一实现owner，隔离实例独审，受控执行器负责真实结果。先完成当前RC-FINAL三项纠偏，再验证已有R1持久化，满足相应Gate0和正式依赖后推进多镜头。不要根据历史文档中的NEXT_DELIVERY_TARGET重新启动R0/R1a。
实现前冻结候选、完整Git输入集合、命令/测试节点、工具/样本/有限预算、停止与清理协议；先复现故障后修复，按影响复验并集中独审。普通本机范围由现有母授权派生有限子收据，不重复询问GPU或候选许可。
首次ClaudeCode429立即停并交接，不自动换模型或由Codex接手。审批拒绝不绕过；历史失败和真实人签不改写；固定189/29、硬安全及正式Stage依赖不降低。到实际人工体验/发布门槛等待签署。
每次结束报告完整V0–V3已完成/总数、当前坐标、十字段与证据；源码、机器验证、独审、人签分别陈述。Stage满足必要人签后普通Git同步。未审计源码不直接宣布已完成或未实现。
```

## 路线与历史

V0-Min、R1a及统一图视频早期切片有各自签署，不等于完整V1。R1持久化→M1边界/时间轴→逐镜头观察/人工稿/导出→R2质量、恢复与打包的优先顺序见机器路线；原S3与正式退出义务保留。V2素材理解/命名和V3薄集成设计继续保留，业务尚未激活。

旧入口提示词仍可由Git历史复现，不再将其过期坐标作为执行指令。历史过程树按archives/README.md验证和恢复，不通过旧授权重跑历史PID/运行。
