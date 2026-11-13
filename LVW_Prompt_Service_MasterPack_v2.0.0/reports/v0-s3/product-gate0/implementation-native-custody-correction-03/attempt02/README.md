# attempt02：N1 纠偏 03 第二批（纠正包 02）的执行产物目录

本目录是 **root 纠正包 02** 授权的第二批（复验）批次的**产物目录**。它的内容由 root 冻结包
`…/native-custody-correction-03/validation-plan-01/` 的 guard 与 runner 写入：

* `native-custody-correction-03.receipt.json` —— root runner 写的收据（逐 node 结果、
  FD 身份、线程清单、预装载事件、cleanup 判定）；
* `native-custody-correction-03.guard.json` —— root guard 的收据；
* `native-custody-correction-03.stdout.log` / `.stderr.log` —— 原始输出；
* `counter-before.json` / `counter-after.json` —— 原共享 counter 的**只读**前后观察；
* `pytest-temp/` —— pytest 的临时根。

第一批（attempt01）的原件**不在**本目录，也**不被**本目录覆盖：它们在
`…/implementation-native-custody-correction-03/` 的根下，由 root 的
`…/native-custody-correction-03/correction-plan-02/attempt01/` 归档索引冻结。

执行计划的草案在同级的 `attempt02-preparation/plan.json`。在 root 的唯一复验 ACK 之前，
本目录**不会**有任何内容：实现者没有运行候选导入、collection、pytest 或任何真实
Windows / GPU / 服务动作。
