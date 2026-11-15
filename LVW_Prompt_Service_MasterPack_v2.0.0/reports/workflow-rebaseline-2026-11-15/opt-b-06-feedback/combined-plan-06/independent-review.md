# feedback06 有限 CPU 反馈独立准入复核

**本次readiness范围 Fatal 0 / Major 0 / Minor 0；READY_FOR_ROOT_ACK_ONE_COOPERATIVE_BOUNDED_CPU_FEEDBACK_ONLY。** 我未发root ACK、未执行任何guard/canary/candidate；不宣布Stage/N2准入、旧五项Major或incident关闭，也未预审全部候选语义。

计划SHA256独立核对为 **`1e370a2fdb74a3bda372100ac5323eb47d9b9ef22ce865dc85dd2738b1208271`**，候选仍`9b6d9d4b827587d132eaf20e2b838d449ed89bd3`。61 source、4 tool、223 dependency、3 stdlib、10 protected-history pins逐份重哈希无差异；61 source另逐份匹配精确候选Git blob。全部实际工具/stdlib/history hash及canary/旧05证据hash见source-binding.json，未读取counter内容。

## 实际 guard02 canary

root-canary-ack绑定b3c5da3评估及`a8c5d114…`冻结canary plan，一次20秒/0retry/0product import。已独立读取outer-receipt、guard、canary-result及日志，核对三文件/plan/codepins身份；不是只相信passed字段。

11个唯一、顺序正确的actual checks均true：exact null write；owned create/write/read/rename/remove；outside absolute overwrite、relative overwrite、delete、rename；symlink escape write；relative dir_fd write/remove；hardlink alias write；new symlink unsupported。九个denial event按相同顺序分别是open.outside_root两次、os.remove.outside_root、os.rename.outside_root、open.outside_root、open.relative_dir_fd_unsupported、os.remove.outside_root、open.hardlink_alias、os.symlink；旧八类selftest拒绝保持。

child exit0、outer passed=true，outside unchanged；原自有canary固定字节SHA与receipt一致。setup_canaries_removed=true，并用只读lstat语义确认outside-canary.txt、run/escape、run/hardlink三路径实际不存在（也不是broken symlink）。outer约0.130秒、guard约0.042秒，收据终态完整。outer-receipt SHA **`93b6e017bfd5217d323acba86fde81268e30e18e05e471a18a1627b5dd5f7350`**与feedback06所pin一致。

**证明边界**：这确证所列自有mutation/null-compatibility反馈及此次清理，不是所有filesystem/原生保护。canary guard实际preload状态仍NEW、events=[]，没有正向singleton preload证明；计划已承认此点，实际candidate runner仍须提供精确一次/CLOSED证据并由outer硬验，不能把NEW改称CLOSED。既有setup失败收尾/fd/FIFO/realpath-open race/unsupported dir_fd与新symlink限制保持，不扩展为敌对OS/native sandbox。

## frozen feedback06 接线

精确selected194=冻结原189顺序+supp5顺序，194 unique；与旧冻结清单及候选Git顶层测试名/顺序（仅AST数据）相符，未以194代替189。选定方法的修复语义将在反馈后集中独审，不在本轮提前扩大。生产/native/产品29义务不因此获证。

新R为实现区`implementation-native-custody-optimized-05/combined02`，本次只读检查lexists=false且canonical path相同。N05/F5/T10、TMPDIR均显式指向R下各自子目录；guard argv包含这个精确write-root。before/after只调用固定absence observer，输出分别为R/counter-absence-before.json与after；guard只调用固定guard02+runner并写R/guard.json，runner写R/native-custody-correction-03.receipt.json；outer validator接收本计划与这两个精确结果并写R/outer-decision.json。三阶段stdout/stderr均在R，不复用spent combined01。

**四个阶段环境一致且模式为REPLACE_CHILD_ENVIRONMENT_WITH_EXACT_DICT_NOT_INHERIT_OVERLAY**：只有PATH=/usr/bin:/bin、HOME=/home/administrator及N05/F5/T10/TMPDIR/PYTHONDONTWRITEBYTECODE五个run变量。不能从宿主继承其它变量后声称等价；尚未执行，实际executor仍必须按该dict替换并记录命令结果。路径freshness/pins在启动前还须重核。

预算明确before5秒+guard290秒+after5秒+outer5秒=**305秒，one batch，0retry**；保留原母预算不reset。counter为精确parent/counter的lstat缺失观察，绝不读内容或复活原grant。任何refusal/429/guard denial/缺结果/未知清理均按原停止规则，不包装重试。

outer工具pin `0ce99e6d475f9a3cc1a253f23f5ebef6d911cd7c3af65f65c923d3afcf7d77c0`，在咨询runner成功前拒绝任何非空、missing或invalid ledger；实际原veto自测有child0+9denials仍exit1/accepted=false的证据（plan pin也匹配）。它还检查CLOSED singleton、节点顺序/每call实际outcome及cleanup；ordinary candidate不能借用canary“9次预期拒绝可PASS”的特例。**现validator不自己重哈希protected-history**，root仍须实际完成/记录run后十份历史对比；当前pin匹配或FD干净不替代该义务。

## spent05、限制与退出

7e717ec真实final receipt及outer-decision已只读核验：同源码9b6，pytest exit3、collected0/calls0、outer REJECTED/GUARD_RUNTIME_DENIALS_NONEMPTY；对应raw仍匹配提交字节。它没有执行原189/supp5，不产生可拼接用例通过；feedback06是新guard兼容及新env/输出根的独立child，不重放05，不补造PASS。

下一步仅为root对这个**精确plan**发新的有限ACK，执行时真实替换环境并落实305秒/onebatch/0retry。随后保留before/guard/after/outer、实际singleton、分开的189/5、FD/thread/handles/历史hash与输出隔离证据，原失败原样保留，再集中独审。ADR16 O1允许在登记疑点下做这种受控反馈；本READY不推定五项修复语义已验证，不以原Major形式关闭作为新无限静态前置。产品29、9原生未知、人签及N2/Stage门禁均保持，结果不确定或发生unsupported mutation必须如实FAIL。

仅NEW本目录review.md/findings.json/source-binding.json，一次精确stage/commit；不修改旧报告（含b3c5da3）、候选或历史文件。无guard/canary/candidate import/compile/collect/tests、model/GPU/native/service/media/network/DB/counter内容或额外agent。十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批canary实证与feedback06 readiness完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前门槛root新ACK及真实反馈；路线OPT-B→OPT-C；剩余单批反馈/集中独审/正式门槛；下一owner root执行器；授权本轮只读、未发ACK；证据本目录绑定plan/canary/spent05；停止本范围F0/M0/m0、有限反馈READY、Stage未通过。canary机器实证、candidate未运行、源码疑点与人工签署分别记录。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
