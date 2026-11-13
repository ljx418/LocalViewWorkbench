你是唯一ClaudeCode实现负责人，继续LVW S3-P4-OFFLINE，当前仅零进程纠偏，不是真实fixture运行。旧实例已归档回收；禁止派生Agent。读工作区AGENTS和root当前执行控制/新纠偏decision。root主包：/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0。本轮基准HEAD763f3d561772ec8efa7aafe597b62ac77a3b7969；report.md存在旧阻断未提交修改，全部保留，不清理未跟踪工件。
实际失败证据root reports/v0-s3/product-gate0/fixture-audit-correction-01/decision.json和finite-fixture-implementation-02.*：13全收集/13全失败，前2个经第二份runner的离线hook拦截，原audit先记2个PENDING，余11并发拒绝，真实子进程未创建；不要把receipt fixture_process_starts=2当作成功fork。旧nodeid usage失败也保留。
根冻结纠偏范围：只可修改 reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py、同目录executor.py、tools/test_v0_s3_supervisor.py，以及NEW reports/v0-s3/product-gate0/implementation-integration-audit-correction-01/ 文本证据。禁止改coordinator/supervisor/quality_worker/fixture/S2钩子/qualityphase/其他旧证据/公共合同/门限/固定24分母/当前execution-control/globalMANIFEST/V2。
需要一次修复完整根因：
1 runner在__main__生产引导中于pytest/候选导入之前安装全局离线guard，安装幂等、受控同一owner；测试为了调用finalize_session等函数导入runner时不能自动安装第二个关闭gate的hook。不能通过移除安全hook、捕获吞掉违规或泛化白名单实现。main与模块别名都要覆盖，原零网络/零任意子进程边界保持。
2 执行器对Popen返回句柄前的异常必须有明确终态/证据，不能留下PENDING却宣称全部清理成功。仅有可信、绑定当前charge的审计拒绝位置证明before-fork时才可记录未创建；一般Popen异常可能有副作用，必须UNKNOWN保留占位与根，不能一律免费释放。累计starts和历史charge绝不减少、退款或重置。原共享counter不可修改，旧2PENDING不可由你补写。若需要新增内部执行收据字段/状态说明给root审查，但不得改产品公共合同。
3 机器收据区分admitted_attempts与实际获得/可证明创建的handles；保持旧字段兼容并明确语义，不能无孩子就让所有准入失败伪装cleanup PASS。
4 针对真实调用链增加零进程负例：多次import runner不重复注册hook；生产entry安装guard且主/别名共享同一owner；fakePopen模拟audit拒绝与未知异常各自正确记账/清理；失败后新合法准入不会因错误PENDING永久卡住（仅对有证明的before-fork拒绝），UNKNOWN仍占槽；进程/网络负例守卫仍真实触发。不要只测helper或常量存在。只跑受影响定向suite，禁止重跑旧71/257整套。
运行限制：整轮仅内存/临时根的零OS子进程验证；不得执行任何带机器binding的真实runner，不可fixture/网络/模型/GPU/服务/原账本，不创建/写原counter，不自动消耗剩余60秒池。旧counter已active=false，reserved120/spent2.896/charged2全部保留，root后续独立裁决修复候选与预算。
先只读确认自然继承两retry env均0，root启动前已建worktree根env-only临时设置；FIRST429立即WAIT_BUDGET，绝不重试/换供应商/账号/Harness或Codex接手；首次审批拒绝立即停止askroot，不包装/改权限。不要修改临时设置，结束由root按hash恢复。
交付：新候选commit（只含允许源码及新报告，不把旧report.md/失败工件/临时设置混入），变更/合同none、命令与真实退出码、原始日志、问题复现与修复oracle、仍未证明项；worker_done只报READY_FOR_REVIEW/失败，不能签StagePASS。完成即归档/释放窗口，默认不keep-open。
