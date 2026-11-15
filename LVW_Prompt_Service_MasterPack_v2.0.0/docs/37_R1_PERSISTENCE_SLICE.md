# 37｜R1核心持久化与人工修订：离线编码执行切片

本次按已批准ADR-16实施逐Workpack准入，不改变完整Stage DAG、旧签署、产品29项或原生九项。N1 CPU组件已通过且独审F0/M0；真实Windows/模型/打包仍未验收。实时状态仍只读execution-control。

新切片保持当前R1/父WP-R1-U3，只准入内部WP-R1-U3-PERSIST-01的源码与测试源码，不授权导入/运行。既有canonical Media/Shot/Revision API＋SQLite版本1核心，形成上传受控副本→人工draft→显式保存不可变revision→重启读取→幂等/CAS/失败回滚生产路径。前端接线、job恢复、多镜头/scene版本2迁移、模型采纳overlay和V2能力均另包；不为完成本切片修改canonical合同。

[冻结执行包](../reports/r1-persistence/packet-01/00-coordinate.md)包含唯一owner、文件范围、私有表/映射、错误/事务/清理、16固定组件用例、授权和停止条件；[准入裁决](../reports/r1-persistence/packet-01/root-gate0-decision.json)只准许离线编码。旧R1统一切片packet/manifest不改，新包是当前parentWorkpack的显式内部代码范围与约束；它不扩张已签UM10或自行宣布完整R1通过。

[架构裁决D1–D5](../reports/r1-persistence/packet-01/root-decisions.json)：主控的Workpack开发映射确实存在；11字段scene hash映射已有规范、当前暂不执行scene迁移；保留inactive overlay。N2不能把另建NativeRuntime当成已经准备好的driver，不能把bridge profile误作worker五键binding；N1 broker设计上创建并持有本轮服务句柄，S3后续只认可此单一所有权路线，S2既有wrapper路径不改。N2实际运行仍需另行封存接口、准入和九项原生证明，不阻塞本包无模型的人工数据代码。

流程：完成源码/16测试源码→提交候选→root封存SQLite限定根guard与已验证监督器→定向真SQLite/公开HTTP测试→集中独审与相关旧后端回归→后续前端/产品验收。现有N1guard禁止SQLite，因此不得绕过它直接自测。不会用16组件用例替代完整产品29项，也不重跑未改N1来证明新数据路径。
