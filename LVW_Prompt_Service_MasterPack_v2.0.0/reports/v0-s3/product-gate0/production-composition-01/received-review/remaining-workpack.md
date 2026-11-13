集中 remaining-workpack 建议：S3-P4 生产组合与真实平台一次规划包

这是只读规划，未授权新运行、未改合同/门限，不把固定24改为28，也不签任何固定24或产品12 PASS。当前072候选可保留为组件基线；13 fixture已经补证，不应继续逐项返工或再次消耗已EXPIRED的grant。先由root一次冻结下列缺口矩阵、候选兼容映射和有限下一包，再按依赖执行；遇首次审批拒绝/超时/429停止并ask root，不包装绕过。

| 范围/生产owner | 兼容性与现有证据 | 缺失Oracle/运行路径 | 最小下一命令或实施范围（均未执行） |
|---|---|---|---|
| I07/I10/I11/I13/I21，quality_worker + supervisor owner | 072的run_worker真实构造QualityPhase；旧fake-driver16行/66帧及本轮parent13均兼容，但两段没有通过真正生产worker入口连成一次运行 | 冻结16行projection→WorkerContext.load→main/build_native_driver→QualityPhase.run→ProtocolWriter真实管道→ParentSupervisor→原canonical，必须逐行状态/独立质量/终态哈希一致；异常、父失联、partial I/O及history多行边界也有准确Oracle | 先补一组组合测试与受控生产driver入口（建议新增tools/test_v0_s3_production_composition.py，尚不存在）；离线可用显式合成driver但须实际QualityPhase和parent真实reader，不许fixture脚本替代worker。提议收集命令：python3 -B -m pytest --collect-only -q tools/test_v0_s3_production_composition.py；实际进程运行须新封存有限包，不能直接使用此命令开跑 |
| I16/I19/I20/I24，coordinator + originals + aggregator owner | O1/O2/C等已独审关闭，072保持其代码；本轮clean_terminal的手写一行receipt不是完整QualityPhase原件 | 当前tools生产代码中ParentOriginalEvidence、aggregate_twelve_keys、build_production_command只有定义，没有相互调用；缺实际parent控制入口将原件manifest验证结果、selected root、cleanup、QS/A06收据交给12键汇总 | 实施一个正式生产控制入口，复用原owner；同一次run保存投影/父原件manifest/原canonical/cleanup/agg来源链，负例对原件变更/缺cleanup/缺独立score拒绝；先扩上述集中composition测试，采用真实生成的收据，不造complete_receipts冒充生产证据 |
| I01–I06/I15/I17/I18/I23，runtime/profile/binding/install/recovery owner | 已有静态hook和合成测试兼容072；本轮没有安装或native路径 | 安装前/后/回滚后真实基线，首次default/warm绑定，原authority/ledger身份/有效期/debit，父崩溃不重发/不信自报PID，residue缺根/读取失败/512/256/reparse平台语义 | 一次窄范围集成修订：先保留tools/test_v0_s3_integration.py现有节点并按上述缺口补组合Oracle；静态选点命令 python3 -B -m pytest --collect-only -q tools/test_v0_s3_integration.py；后续真实安装/原ledger必须root另冻结同源有限包，当前审查不碰原ledger |
| 产品12/Gate0，native/Windows/GPU/A06/质量/安装owner + 独立评分人 | 原P1/P2B/P3A/P3B组件证据仅其自身限定范围；新13不带来真实平台产品通过 | Windows/native进程后代与GPU有界释放；A06真实隔离；原ledger消费；实际质量16行集合和独立评分/质量阈值；A/B预算、注册表驱动安装及回滚；每phase与最终12键同候选原始收据 | 不能给出当前可安全执行的真实命令：需root先填生产入口、现有依赖闭包、固定输入、工具hash、原ledger路径及有限预算，生成新的execution-argv.json。最小实施范围是补齐上一行生产组合后再做一次有界真实准入，不重跑41/31/186/134/257替代真实门禁 |
| root集成/归档owner | 独审工作区072源物化，HEAD仍204e585；root此前缺supervisor属于未合并预期；证据commit c6bce90仅证据 | root migration/全生产调用入口及最终candidate一致性缺证，不能把独审材料等同root部署 | root先只读git diff --stat 07277a6f2f6f730dc7b9383bfeaf8c412126fe16和选择性候选迁移方案；明确生产owner后一次归档本报告与兼容映射，实施后重新封存唯一候选，保留全部历史失败和counter，无checkout/reset/clean整树 |

集中包的出门Oracle应继续逐项列固定I01–I24的生产入口、驱动、准确拒绝/正例、真实终态与清理来源，并与产品12分别报告。离线合成driver组合只能关离线接线缺口，不能给实际质量/A06/native产品计PASS；所有后续进程命令均须新root有限授权，不得复活本轮binding。
