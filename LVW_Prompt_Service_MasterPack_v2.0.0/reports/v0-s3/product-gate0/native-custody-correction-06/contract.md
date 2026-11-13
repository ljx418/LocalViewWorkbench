# N1 correction06：157项失败的集中最小纠正

原候选0e83077321186b52c7e3826efbbf92c143737b0f。157调用151PASS6FAIL0SKIP（149功能+2完整性）、exit1、cleanup=false，批末late/closer两个线程。原收据/候选/失败不覆写。父包correction05及24组义务继续冻结，6Major未关闭。

## 裁决与实现范围
本次静态最小改动两生产源tools/v0_s3_native_custody.py、tools/v0_s3_native_broker.py及tools/test_v0_s3_native_custody_correction05.py，如确需修同一缺陷测试夹具可改tools/test_v0_s3_native_custody_regressions.py；主测试test_v0_s3_native_custody.py保持。只新增NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-06/。旧owner/合同/原24义务/control/MANIFEST/全部历史报告不改，不提前N2或真实运行。

F1 production：内部_close_broker FINISHED分支不得自动再协调未关peer，避免同一次startup失败/回调重复close。恢复由明确公共stop意图驱动：首次stop若遇到此前后台尝试已完成且仍保留，也必须能在原期限内接管；反复stop不发第二STOP，不重开预算，只协调未确认项。不是只挪一行使R06过关：设计每次公共stop最多一次恢复，竞争者等待同一owner，成功关闭项绝不双关，过期只UNKNOWN保留。不能把恢复锁死。

F2 test：ctypes原handle可不hashable，字典membership用getattr(handle,'value',handle)数值，仍证明retained原对象/身份一致和同owner恢复，不改生产把原HANDLE对象换成可hash副本来配合测试。

F3 production+test：取消首次job CloseHandle后pending pass成功真实关闭，Core.job/record flags/retained_resources必须与实际关闭事实一致。成功结果通过唯一资源表/明确通知同步，失败仍有原owner；不能清空所有retained来“绿”。保留取消传播与primary/secondary，确认成功关闭后不再关闭同一handle。用例分别覆盖暂时关闭失败→pending重试成功、持续失败→具名保留，在返回时核实实际closed/live/pending/record同一身份；不得只把assert core.job in live删掉。原报告F3已明言生产bookkeeping，故“只有3个生产缺陷”不准确，应新报告勘误：F1/F3/F5/F6四个生产相关路径、F2/F4两纯测试路径，F3另有测试预期错。原报告不覆盖。

F4 test：StartedThenFailed替身完整实现实际reader接口(error/alive/必要的stop/join/finished)，驱动实际_start_background_thread和evidence并记录真实started/alive/owner；不修改生产evidence来掩盖有效reader事实。

F5 production：create_process_suspended成功返回后立刻将原process/thread登记pending与record并正确转移owner，必须早于后置预算检查、pipe close、日志或其他可抛动作。deadline耗尽不能跳过接管；后续不得Assign/Resume/创建下一role，仅清理late原process/thread。父API移交失败原owner和Core成功接管去重保证均保留。以原用例真实live记录验证无失主，不伪造win32.live空。

F6 production：_await_close即使入口已FINISHED也需区分尝试结束与实际closer线程退出。等待/原Thread.join必须用同一原deadline、剩余逐次重算、不自join、不在回调形成循环；真正join确认而非在线程finally提前set事件冒充已退出。超期UNKNOWN保留原closer与原owner，原deadline不延长。明确closer/调用线程两种执行模式，只有没有closer且无清理进行中才可立即确认；等待者在finish事件前/后到达均测试。

## 测试清理与原始事实
本轮late为故障替身实际线程，closer为生产创建的清理线程，不能笼统说“不是产品线程”。原报告batch process退出不等于产品清理，false保持。所有新/受影响用例在任何断言失败时仍由测试owner在finally有限release gate/通知/join保存清理收据；产品返回时的事实先记录再salvage，salvage不能改为产品成功。F4/F6等测试断言失败也不能跳过自身salvage污染批末。不可把线程名过滤/daemon退出/GC当清理证明。
157nodeids与顺序保持；可以在既有节点内增加上述正负场景，未授权删断言/恒True/阈值变化。若需新node先列给root冻结追加。尤其close recovery通过公共stop、late返回即原owner、pending成功记账及真实closer退出四条同根因路径一次审完整，不逐条反复交接。

## 执行边界
现在只静态实现/AST，不import候选/collection/pytest。精确路径提交新候选后askroot有限执行plan，含候选SHA/5源+旧owner pins、原223文件级依赖和3stdlib pins、root外部guard/runner/outercounter、原157节点顺序、三条绝对argv/cwd、<=300s单批、真实FD与全部线程/raw/pernode/退出码。ask后结束turn等待，不同时worker_done。root ACK前任何动态都禁止，之后唯一一次，失败不自动修/重跑/覆盖候选。
沿用root guard后一次ctypes.dlopen(None)可信预装且候选/pytest前关闭；其余dlopen/dlsym/真实Win32API/Job/业务进程/GPU/模型/服务/socket/sqlite/网络/媒体/下载/原ledger拒绝。counter仅未来ACK外层前后各一次只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，不写/清零/退款/复活。FIRST429立即WAIT_BUDGET不retry/切路由/root接手；FIRST审批拒绝/超时停不包装绕过。只READY_FOR_REVIEW非StagePASS，6Major独审/native/I24/产品12/A06/原预算余额/质量/人工签署仍未证。
