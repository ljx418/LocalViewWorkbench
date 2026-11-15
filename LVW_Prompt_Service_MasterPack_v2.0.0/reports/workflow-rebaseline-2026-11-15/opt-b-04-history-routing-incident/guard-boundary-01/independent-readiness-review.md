# 独立 output-guard 源码与有限 canary readiness

原事故三文件已精确保持 abb426d 字节；本目录独立承载此前43b14e4的guard追加评估。此处没有产品运行许可、没有动态canary通过声明，也未恢复历史证据。

## root恢复收据只读交叉核对

root restoration-receipt.json的10事件已逐份比对：实现区当前SHA等于receipt after及candidate-git-original；observed-run-output副本仍等于before；当前device/inode也与receipt一致。fsync/NOFOLLOW为root记录的执行事实，审查者没有重新执行这些操作。原事故报告中的dirty快照属于当时事实，原样保留，不据当前恢复改写过去运行或数值结果。

## 源码评估


本追加响应新派发task_c8a28469ea2b，保留以上事故、恢复建议与旧94cdd82。独立只读output-boundary-design、baseline inventory及guard-boundary-01的guard/payload/launcher/plan；三个代码pins和plan SHA256 `54926876eba6930bf29fe8688a86b45a1e1aa27ea8759b740218b04407715e1a`均一致。inventory列出的15个文件blob逐个与d645吻合；它是61 source pins中的lexical调用清单，不是所有调用都会在189执行的证明。F5的历史fallback确实仍在，下一产品plan必须显式路由N05/F5/T10；quality_phase真实dir_fd mutation存在，不得按cwd猜锚或改写O_NOFOLLOW语义。

**有限canary readiness：READY_FOR_ONE_FROZEN_OWN_CANARY_FEEDBACK_AFTER_ROOT_ACK。** 仅支持该plan的一次、20秒、自有fresh parent子进程反馈，0candidate/product import、0模型/服务、无重试；本审查不运行或发ACK。不是产品guard验收，产品runtime仍NOT_READY/RUNTIME_HOLD。此区分遵守ADR16 O1：披露的失败分支/能力缺口不必禁止完全自有对象的有限复现，但任何缺失结果或未知清理不能算自检PASS。

新guard按open write flags及canonical root检查，可在普通Path.write_text截断历史JSON前拒绝本次回归；保留原八类native/network等deny和单次preload状态控制。mkdir/remove/rename/link/chmod/utime/truncate也有根检查；两端rename/link检查、root dev/inode、hardlink nlink检查比旧deny-list实质增强。relative os.open write+dir_fd明确拒绝，其他携dir_fd的事件按procfd锚处理，不当cwd。没有改写原syscall flags/参数。

canary launcher先验证三个pins、fresh_parent mkdir(exist_ok=False)，全部外部目标也是这个新parent中的自有canary；预置symlink/hardlink只指向该自有文件。payload真实执行owned create/write/read/rename/delete，并对absolute/relative overwrite、delete、rename、symlink traversal、dirfd write/remove、hardlink alias write和新symlink作九次拒绝，逐次核外部canary字节未变。launcher仅在child exit0、9项denial、10项checks全部true、旧8项拒绝及False clean-denial-ledger一致时标passed，并复核pins。这是**预期负例拒绝**的明确特例，不能照搬为普通candidate可接受非空ledger。

需要如实保留的具体限制与最小后续修改：

- **guard ledger不是进程退出码门禁。** guard finally只写denials，payload捕获拒绝后可以exit0；本负例canary专门验证此情况，合法。下一candidate trusted outer必须硬判“任何runtime_denial→FAIL”，不得仅看pytest/guard exit0；当前draft没有证明此产品验收集成已完成。
- **launcher失败清理不完整。** parent/root/outside/symlink/hardlink setup在try之前，部分setup失败会留下自有对象且没有outer-receipt；finally中一个unlink失败又会跳过余下对象/receipt。它不授权触碰历史/私人文件，但这种实际结果必须NOT_PASS并由root containment；后续最小修正为从首次创建起覆盖try/finally、逐已创建对象guarded清理并可靠发布真实异常/剩余状态。不能把现有passed字段或CLI退出当失败清理证据。无需因此引入新框架。
- **preload正例未测。** payload不调用begin/finish或受控ctypes preload，所以该canary即使通过，preload窗口也可仍NEW/空；launcher只验旧八类拒绝，没断言CLOSED/单事件。源码保留策略不等于执行证明。若只做本次write-boundary反馈应限定证据声明；若要验收singleton正向窗口，另冻必要trusted stdlib pins/调用及CLOSED/count/order断言，不能把NEW写成CLOSED。
- **fd/链接/race仍有限。** guard无条件放行fd0/1/2和所有FIFO，procfd检查不能覆盖所有os.write/native写；relative dirfd open write明确不支持，若实际产品测试走到它，应按unsupported失败，不转成另一个路径。新symlink拒绝可能使pytest内部链接需求显式失败，需要路线审计而非放宽所有路径。realpath→open仍有TOCTOU，root inode/hardlink检查不是完整OS隔离，不能声称覆盖恶意同UID、原生扩展或所有descriptor别名。当前设计明确cooperative Python harness、不称hostile sandbox，这个限制是恰当的。

因此可由root对**精确已有canary plan**作一次独立ACK以获取有限反馈，任何setup/cleanup/receipt缺失应立即保留失败、停止且不自动重试；不能据此直接跑产品candidate。产品准入仍要可信外层denial门禁、路由审计/先前纠偏、实际canary有效证据与必要能力声明，以及新fresh root/pins/命令/预算/root ACK。原事故F0/M1/m0和恢复条件不变；这份追加未执行canary、未恢复历史文件、未改Claude候选或trusted代码。


十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批guard源码评估独立归档；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前阻断产品runtime hold；路线OPT-B→OPT-C；剩余root有限canary ACK/实际证据及后续产品边界准入；下一owner root trusted executor；授权只读、无运行ACK；证据本目录与immutable abb426d；停止有限canary可反馈、产品NOT_READY。事故原F0/M1/m0及旧五项不因归档变化关闭。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
