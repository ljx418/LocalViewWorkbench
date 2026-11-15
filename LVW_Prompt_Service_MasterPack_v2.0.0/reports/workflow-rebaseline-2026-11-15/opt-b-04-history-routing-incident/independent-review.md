# N1 集中独审：d645bd55

**CHANGES_REQUIRED，Fatal 0 / Major 5 / Minor 0。** 新鲜原固定 **189/189 PASS** 保留；补充5项为 **3 PASS / 2 FAIL**，失败SUP01/02的指定query故障没有命中。总计192PASS/2FAIL、194个唯一call、0skip/0missing，不用194汇总替代189，更不替代未运行的产品29或Stage PASS。

唯一候选 `d645bd559af89921cd0359612cce7b78c4892fe8`，基准a9a63cf；按opt-b-03的scope/checkpoint-design/combined-plan-04及ADR16独立审查，未继承root或实现者结论。T10 SHA256 `ee72673f4a8b746ba4fe4613a1cc7f9571d4f503e867839fceb7c2dd1ce4cc32`，新增supplement `d95f4e5e798348382d4bfbd77ba8b00f2746d4662e40fd2e107707a41162e05f`。只读108行T10差异、新557行supplement及必要相邻真实方法；详尽location/trigger/expected/actual/oracle/negative/raw/退出条件见findings.json。

## 五个集中Major

1. **OPT04-M1-SHUTDOWN-WIRING：真实shutdown未接通。** T10:4469–4475查询channel的`_read/_write`，生产实际字段为`_reader/_writer`；默认None没有成为unknown，整个worker列表为空。独立的第二处错误在4495/4497：lambda返回绑定方法，4499的call()只得到方法再repr，未调用stop_accepting/request_cancel。两处都须最小修正。实际normal/SUP01/SUP02 zero-salvage均`fixture_shutdown=[]`、handle_proof=None、unknown=[]，但registry/drain中有真实read worker。这次真实资源最终清理成立，不代表遗漏的显式shutdown/handle核验被执行；原attempt02失败调度的退出义务未被可靠覆盖。

2. **OPT04-M2-FINAL-QUERY-FAULT-MISSED：SUP01/02故障定位错误。** supplement:78–83、141–146的_getframe(2)从定位函数向上看到is_alive包装器之后的R07 **lambda**，不是zero_guarded_query；该helper在depth3。M1还使最终worker查询根本没有运行，故只改stack depth不够。真实SUP01:198失败calls16/injected0，SUP02:306失败calls12/injected0，zero raw无E/K2，不能算query负例已执行。应精确命中实际held worker的目标query、只注入一次并证明命中；原189通过不补这项。

3. **OPT04-M3-NONTRANSPARENT-K1-RECORDER：SUP02丢弃真实callback。** supplement:266–282把release[2]（真实zero_close_channel）替换成k1_release，后者274却调用release[0]（gate）。原第三个channel.close被省略，first gate重复执行，违反透明forward原callback的冻结要求。每次k1_release又新建一个K1对象，drain多轮时会有多个不同K1，但安装计数k1始终1。应保存正确原callback及预创建的精确K1，forward原callback并一次注入，后续调用照常forward；不能用另一个gate或同token重造中断冒充原生命周期。

4. **OPT04-M4-UNKNOWN-ORACLE-CONTRADICTION：正确的故障语义会被外层负例拒绝。** T10:4614–4636把故障query的alive记None，并形成非空unknown handle_proof，这是正确failclosed；supplement:221–234却要求handle_proof=None且alive_after=False，323–325亦要求None。修好M1/M2、E/K2真正命中后，正确callee应FAIL/UNKNOWN而不是提供已知False。应检查保留的error/unknown/failed proof，再通过独立、真实且不覆盖原unknown的观察证明实际物理清理，区分外层negative PASS和callee FAIL。当前injected0未执行此矛盾，不能改callee把unknown置False来迁就测试。

5. **OPT04-M5-EXACT-IDENTITY-NOT-ASSERTED：必要异常与held资源identity缺口。** SUP01/02/05仅比type/token，从未断言info.value **is**实际注入的O/K1；SUP01/05的writer.injected已有对象却未比较，SUP02 inline创建K1也无从比。SUP05:528–539只要求某次settle(5)、某次interrupted-start join及非空thread，没有与独立保存的实际held owner/thread做is核对。故同type/token替换异常或错误owner/thread可被Oracle接受。最小修正是保存真实注入对象、目标owner和原thread，断言exact identity、K2不同于K1，并保持调用原settle/join及原返回；不需新增框架。

上述问题按根因集中列出，M1内的两处接线一次纠偏，不按每个字段/重复文案计数。全部涉及必要实际动作、指定故障、真实生命周期或合同identity；没有符合ADR16全部资格的辅助Minor，不改写旧Major或失败。

## 最终query guard与五例覆盖

新增zero_guarded_query:4442起确实catch BaseException、保存异常类型/详情、通过_note_interruption保存精确中断对象、记录unknown；4614起若实际query失败则handle_proof非空，4738发布在4749–4753的O > 首个精确K > 普通verdict之前。**原86ab300所指guard机制可记条件CLOSED_STATIC**，但M1使实际query路径被跳过，M2/3/4使其必要负例无法提供有效动态证明。没有新增不受保护的普通query替换O的同样分支；不把原框架重新全面展开。

| 义务 | 实际覆盖与独审状态 |
|---|---|
| N1-OPT-01 | SUP03真实PASS对应callee FAIL：CHILD_TRANSPORT内第一次writer一次E，后续写成功；持久raw保留EVIDENCE/OSError、sentinel token CHILD_TRANSPORT、failed proof、quiescent及实际all_salvage dead。此定向writer分支证据成立，非整个N1签署。 |
| N1-OPT-02 | SUP04真实PASS对应callee FAIL：第3次该phase写为final写，故障仅一次，有限retry后磁盘文档已有E及非空failed proof，后面没有同phase写掩盖它；实际清理成立。stale-proof修复得到分支证据，不需将它降成Minor。 |
| N1-OPT-03 | SUP01/02真实FAIL，目标E/K2为0次，不能闭合final-query故障下原错误/必要发布义务；M1–M4继续阻断。其他未变publication只复用旧审查。 |
| N1-OPT-04 | SUP05真实PASS、callee保留O并FAIL，raw含指定INFLIGHT E与OWNER_THREAD K、owners_attempted1、known dead；recorders调用原settle/join并forward结果。lookup只在fixture实际settle(5)完成后激活，早期生产settle上限1秒，不会仅因早期产品settle激活；未发现过早污染其他owner的已执行证据。但M5缺exact O/held owner/thread Oracle，故完整身份资格仍OPEN。 |

_phase_writer正常路径forward原writer及结果；SUP03/04的故障位置是指定前置失败，没有复制R07。五例直接调用既有R07/R09函数，沿真实public/default路径与最低合成OS seams，未换成简化生命周期。每例negative/sup-01..05独立目录并在finally恢复T10路由，normal及旧attempt raw未覆盖。本轮未用type/token或文件存在代替身份结论；持久JSON不能证明Python对象is，必须在相应负例内断言。

## 实际收据复算与保留边界

首次检查缺after/guard/runner时记PENDING，未读取部分日志作为结果；收到主控msg_8dbd99f69bc2新结果通知后，一次事件触发readiness检查发现before/after/guard/runner均齐，才完整读取、复算并哈希，没有轮询或代跑。

plan SHA256 `6eee1bafcba0d3de0c630b5d94b8dc2fa0d7e5fa7026a5b62799699af11cba37` 与root ACK/candidate匹配；61 source pins、3 tool pins、223 dependency pins全部独立重哈希一致。实际selected/collected严格等于原189顺序后接supp5；194个唯一call，0missing，报告中无隐藏setup/teardown失败或skip。原189包含两个声明的integrity-only节点（functional原子集187）；补3PASS使functional_pass_count190，不能把它读成194功能通过。

实际runner53.437秒、guard53.544秒，pytest_exit1；FD before/after三个有效FD的dev/ino/mode相同、无unknown/新增/复用，threads before/after均仅MainThread，**本批CPU资源清理成立**。guard8类selftest拒绝、runtime_denials=[]，唯一ctypes.dlopen(None)窗口在candidate前关闭。before/after精确parent/counter均MISSING/errno2，仅证明缺失，不证明历史余额/连续性或复活授权。callee的UNKNOWN_RETAINED/失败与外层negative成功分开；CPU线程收尾不等于native/GPU/端口清理。

原189名/顺序/签名/decorators逐Git blob AST数据比对不变，其他四测试模块bytes不变；生产broker/custody bytes仍为06cfc951…/7f26e927…，没有全面重审生产所有权。旧86ab300/62dbb5d/7233efd及原失败保留；9项原生未知N03-R16、N05-R06/R07/R08/R24、N07-R08、N10-R12/R13/R14继续未证实。新鲜189PASS是有效机器证据，不能覆盖必要负例和静态缺口，产品29仍NOT_RUN，N2依赖/Stage不放行。

下一必要动作：在同一最小test范围集中修正M1接线、M2定位、M3透明callback、M4unknown语义及M5精确identity后重冻候选并独审；root再封存有限受控验证，保留每个真实失败和独立raw，不自动重跑模型或扩大框架。本报告不新增运行ACK。

仅写本新目录review.md/findings.json/source-binding.json并一次显式提交，无自引用pointer；未修改/导入/编译/收集/运行候选，无native/model/GPU/service/DB、无子agent。十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批集中独审完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；阻断必要shutdown和supplement资格；路线OPT-B→OPT-C；剩余集中最小纠偏/有效负例/后续正式门槛；下一owner主控与实现者；授权本轮只读、已有单批ACK不扩展；证据本目录绑定combined01；停止CHANGES_REQUIRED F0/M5/m0。实现封存、机器189PASS/supp3PASS2FAIL、独审有阻断、无新增人签分开。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
