# OPT-B-02 最小差异独审

**CHANGES_REQUIRED：新增 Fatal 0 / Major 1 / Minor 0。** OPT-R07-CLEANUP-02 的缺少显式shutdown机制在正常路径上已修复，但新增末尾清理查询存在具体异常优先级/必要证据绕过，尚不能给整体 CLOSED_STATIC。没有动态闭合或 Stage PASS。

唯一候选 `a9a63cf7f7b5ec52e271639bb6278e54b457805a`，基准 `62e0d429dd78418220235359d068ae28d7b37e6e`；T10 SHA256 独立核对为 `0aa352f2a0106e7ac700695b540b01e3a627ea5631e1d66aef80fa7122678dc1`。只检查完整195行差异（189+/6-）和必要相邻方法，权威为主控 opt-b-02/scope.json、ADR16；没有重新全面审查9k源码。精确Git/blob、scope与旧报告哈希见 source-binding.json。

正常路径实质检查：4391在fixture动作前捕获真实public stop，原public start返回/held-pump/exact0/UNKNOWN_RETAINED/原broker断言未改；4432–4456从实际zero channel的endpoint字段取得实际worker，逐一调用生产stop_accepting/request_cancel，BaseException进入原错误/中断列表。没有造worker或手工置finished。worker.request_cancel沿原context有效截止时间有界，未改产品deadline或新增产品宽限；现有fixture drain总30秒/每owner10秒未变。Api取消仅释放合成IO，真正停止来自worker方法。

4503–4505把生产channel.close加入既有drain release动作，4525–4535在drain后再调用同一可重复close。生产broker:5636–5668在channel reader仍alive时不关闭read endpoint，reader结束后才交由endpoint.close执行stop/cancel/handle释放；没有强关活read端。4546起检查真实worker alive和thread_handle_released，endpoint retained及channel retained非零加入zero_handle_proof，再于4601汇入实际zero_proof，现有最终调用者会拒绝该proof。joined_after和reader_alive等展示字段不是替代硬Oracle，未为这些重复字段命名提出工程要求。

## Major OPT-R07-CLEANUP-03-PRIORITY

**位置：T10:4546–4571，尤其4550；必要发布4668–4674，优先级4679–4683。** 新增最终核验中的 `alive = bool(worker.is_alive())` 在任何try/except之外；它是一次新的真实liveness查询，不是已经guarded的drain结果。其后handle/retained核验亦同处该无保护块。

可复现触发：zero body已有真实失败O正在展开（例如持有实际channel后某硬断言失败），或4432–4456曾捕获首个cleanup中断K1；实际stop/drain/close完成后，4550的真实查询抛普通E或不同的KeyboardInterrupt K2。实际控制流会立即离开该finally：后续owner核验、zero-salvage唯一发布和既有优先级均不可达，E/K2作为传播主异常替换O或更早的K1。外层parent cleanup可能捕获新的E/K2，但不能恢复跳过的zero shutdown/handle事实，也不能恢复先前异常优先级。代码不会在这条分支普通PASS；问题是**必要清理事实未知、发布被跳过与原错误优先级破坏**，不是纯辅助重复详情缺失。

期望：对这个新块的实际查询/事实提取作有限guard，保留每次异常类型/详情和精确中断对象，明确该owner状态unknown，继续其余已知owner核验和必要发布，然后使用原有 O > 首个精确K > 普通proof。无O时未知查询也必须失败，不能用默认False替代真实liveness。最小修复只需在新增zero finally块复用现有errors/interrupts/verdict机制，不改生产、不重写registry/drain、不建新框架。一次覆盖此同根因即可。

本分支只是精确源码控制流推演，**未执行**，不声称实际is_alive通常会失败。最小退出负例是在后续授权验证中使此实际查询产生E/K2，核对O或K1身份保留、剩余owner仍被处理、unknown/error与必要raw落盘且不PASS；正常无故障真实清理也仍需执行证据。当前候选没有真实FAIL和清理证据供Minor资格审查，不能降级。

## 证据接口、范围与后续

证据接口147–160使用root冻结环境 `LVW_N1_T10_EVIDENCE_DIR`：模块只strip并拒绝空值，然后Path.expanduser；**不验证freshness**。新鲜路径/隔离归root计划preflight验证，后续定向和完整189可用同一源候选而换冻结env；本审查未把注释或错误文案当成路径已验证的事实。缺env会在测试执行前拒绝，没有旧根fallback。

189身份顺序/签名/decorators保持117+16+24+18+14，其他四测试模块bytes不变；无assert predicate删除。除R07和env绑定外模块顶层AST不变。生产broker/custody bytes不变，hash仍为 `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` / `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581`。这些只是Git/AST数据核对，不是执行189。

旧运行审查62dbb5d与attempt01/02失败原样保留。M2/M3未变静态范围及原9项原生未知仅复用旧报告；N03-R16、N05-R06/R07/R08/R24、N07-R08、N10-R12/R13/R14仍未证实。新shutdown及查询故障分支均NOT_RUN；先前writer/secondary-publication/interrupted-query负例不因此获得验证，14/189/产品29均不得互代。

对有限复验：以上是**修复静态收口的具体源码阻断**，本报告不给整体静态清除或依赖N2实施放行；ADR16仍允许root另冻有限受控复现/负例，不因本发现增加全面静态前置。本轮不发运行ACK、不等待或轮询新结果。下一必要动作是最小新块guard修复/重冻独审，再由root封存env/freshness、源码/依赖/guard/nodeids/预算并ACK有限验证。

仅写本目录review.md/findings.json/source-binding.json并一次显式提交，无自引用pointer commit；无候选修改/import/collection/pytest/native/model/GPU/service/DB，无子agent。十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批差异独审完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；阻断新增query-priority Major；路线OPT-B→OPT-C；剩余最小guard修复/定向真实证据/正式checkpoint；下一owner实现者与root；授权静态只读；证据本目录与62dbb5d绑定；停止CHANGES_REQUIRED F0/M1/m0。实现已封存、机器新候选NOT_RUN、独审有阻断、无新增人签分列。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
