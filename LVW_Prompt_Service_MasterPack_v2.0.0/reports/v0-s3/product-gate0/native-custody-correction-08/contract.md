# N1 correction08：五项失败的测试纠正与真实组合诊断准备

冻结失败源23e27898253683164e7cb2918661b54258a29ce0及175/170PASS5FAIL0SKIP/exit1/cleanuptrue。所有真实日志与候选保存，不覆写。六Major仍开放，本包不判它们已实现或闭合。

## root裁决
F1 N03-R01：进程退出未证时禁止Close控制句柄，故它的fail_first_close首次触发顺序已移至确认退出后的恢复。允许有界明确三阶段场景：退出未证→原handle保留且Close未调用；退出确认但首次Close失败→原handle继续保留且具名close失败；同一原deadline内下一次Close成功→forget。每阶段断言关闭次数/原identity/live/exit分别正确，不用无上限重试凑通过。
F2 N05-R11：root原产品义务一直是过期前拒绝全部创建；旧测试先arm再拒launch与本包更完整设计冲突，纠正测试为core.arm在pytest.raises内且错误码稳定，断言create_job/create_pipe/create_process/assign/Resume均未调用、原win32.live空、无输出残留。另保留期限有效arm成功、launch过期拒绝及late Create接管场景。不得删生产arm前预算核，不改变175nodeids/原质量阈值，这属于实现测试更准确覆盖已有义务，不是放松合同。
F3 N07-R02：取消子场景独立新state/closure/kernel，不能沿用第一场景exited=True；明确断言注入Terminate取消确实触发、原process控制handle仍可恢复、primary与取消对象并存。有限finally salvage保持。
F4 N07-R06：合同冻结的是取消传播及来源可核，没有冻结内部failure stage必须exit_code。可接受组stage=wait，但必须记录实际exit_code注入触发计数/原SystemExit对象与错误出处；不得只删stage断言变成任何取消都行，wait_process和exit_code两个子路径分别驱动实际方法且后续process安全清理。
F5 N07-R15：真实Session→BrokerProcess→StreamChannel→Windows endpoint→worker第二次公共stop仍不释放，现有raw只有assert失败，缺具体facts。保持UNRESOLVED，不采纳“只是测试准备错误”结论；不能把去看事实说成修复、不能预填缺失事实。先静态梳理现有链并让故障确定可控：不要全局close_failures=2让两个worker调度决定谁失败；选择明确原thread HANDLE，在测试owner显式release_fault事件前只该HANDLE Close失败，第一次公共stop后断言具体未确认项与原owner、故障确实触发。随后只清除故障条件，第二次公共stop走真实链必须有限收敛、未关项实际成功、成功项不双关、原deadline不重置。禁止改成第三次/循环多次stop来绕过两次收敛Oracle，除非新原始事实另经root裁决。
给first/second/finally salvage分别持久化 bounded JSON：session.evidence、broker close facts、channel close facts、read/write endpoint facts与retained原线程HANDLE身份、实际worker alive/stopped/handle_released、调用序列/实际targeted fault次数和原deadline。每次断言前先写，不依赖pytest失败repr；若第二次仍不完整，保留完整证据后报告实际生产缺口，不自行修到绿。真实API全是本进程facade，不能用硬编码COMPLETE_CLOSE_FACTS覆盖真实链结果；Popen fake只代表自身行为。
当前没有足够证据判F5是测试还是生产，报告须追加勘误修正原“4个测试错误”总结为3个明确测试准备问题+1个旧测试Oracle冲突+1个未定位真实组合失败。旧报告字节root已封存不改写；继承receipt文件名在NEW运行目录，不得再写“correction03收据在correction05”等错误历史位置。

## 允许范围
仅可改tools/test_v0_s3_native_custody_regressions.py、tools/test_v0_s3_native_custody_correction05.py、tools/test_v0_s3_native_custody_correction07.py和NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-08/。生产custody/broker、旧owner/main test、原16/24/18义务JSON、合同阈值/control/MANIFEST/历史报告全冻结。若静态发现F5具体生产缺口需集中askroot带位置/触发/预期实际及最小修改，当前不授权生产修改；不为收集故事盲跑。
只静态实现/AST/源码复核，精确提交新候选后askroot原175有序nodeids的单批有限计划，全部source/tool/原223依赖文件/3stdlib pins，NEW root native-custody-correction-08/validation-plan-01工具、原guard字节、三条argv/cwd、<=300s、FD真实身份/全部线程/逐node/raw/退出码和F5持久化证据。ask后结束turn等待，不能同时worker_done。未ACK不import/collect/pytest或读counter，ACK后只一次，失败原候选证据保留，不自动重跑/改断言/自行修。
可信stdlib guard后候选/pytest前一次ctypes.dlopen(None)后永久关闭，其他dlopen/dlsym/真实Win32API/Job/业务进程/GPU/模型/服务/socket/sqlite/网络/下载/媒体/原ledger拒。counter仅未来ACK外层前后各一次只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，不写清零退款复活。FIRST429停WAIT_BUDGET不retry/换路/root接手；FIRST审批拒绝/超时停不包装绕过。只READY_FOR_REVIEW，六Major独审、真实native/I24/产品12/A06/余额/质量/人签未证，N2不启动。

## Root后继裁决（本包继续执行时必读）

当前追加允许的最小broker修改与反例要求见 close-cancellation-decision-01/reply-body.txt、error-evidence-preservation-01/reply-body.txt。后者确认重复close丢失真实reader error属于M09并允许最小修正；175动态批次仍未ACK。发生Orca terminal_missing后接续同一Task时必须读取这两份已落盘决定，不能执行旧候选或旧计划。
