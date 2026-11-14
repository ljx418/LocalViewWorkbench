# 临时计数器缺失：验证仪器纠偏，不复活旧授权

旧validation-plan-01要求外层前后各读原/tmp共享计数器。root已核精确file及parent均不存在；当前未观察到guarded终态收据。撤回旧未执行批次许可，保留旧plan/ACK/日志和历史28 starts/240 reserved/12.362 spent，不回填、不清零、不退款、不重建counter，也不把历史grant变active。本件不是宣布缺失源哈希仍相同。

本轮是严格无业务进程/无模型/无网络/无账本的N1本进程离线单测，与旧实际OS CPU fixture quota不同。旧counter是那个已过期fixture grant的历史动作账本，不是新生产授权余额。原母授权允许本轮有限离线代码验证，root可纠正本地验证仪器；不改变产品固定分母、质量阈值、公共合同或人工签署，不要求用户重复授权。

后继计划必须另冻结，当前不许执行：
1. 先获取实现者已执行命令、原始退出码、日志及NOT_RUN事实，确认未跑旧guarded batch；如果已运行/状态不明，停止本方案而审计真实状态，不能补跑或拼接。
2. 候选66600a1、175node顺序/21或22实际sourcepins/223文件依赖/3stdlib、硬guard/runner规则不变。任何新报告与工具hash逐项重新核定后root ACK一次有限<=300s批次。
3. 外层改为精确原path与parent的absence观察，lstat且拒symlink/reparse/非预期类型，不扫描其他目录。不读取/新建counter，不重建历史。前后两份观察都必须missing，若任一出现/漂移/未知错误则整批拒绝。不能把missing标成hash_equal或unchanged历史计数。
4. 不给候选任何counter FD，guard仍禁止shared-counter.json与原.lvw-runtime/ledger路径。guard在候选/pytest前安装；只一次可信stdlib ctypes.dlopen(None)后永久关闭；所有subprocess/fork/exec/socket/sqlite/一般dlopen/dlsym等硬拒。
5. 当前动作增量仅能据硬guard记录证明：业务OS进程spawn=0、模型发送=0、ledger操作=0，不声称旧counter实时连续性。自检结果必须把counter=MISSING/continuity=UNAVAILABLE与测试pass/fail、真实FD/全部线程/finally salvage分开列；任何guard runtime denial或候选原件写入均失败。不能用当前absence替代后续N3真实预算余额核算。
6. 原fixture grant仍EXPIRED_NO_REPLAY，不复用旧28启动槽位。本批必须独立run/candidate/plan/raw，失败不自动重试，FIRST429/审批拒绝/超时规则保留。F5十份诊断与六Major独审仍要求，不因环境缺失放宽。

本准备未运行测试、未创建counter/ledger、未启动模型或业务进程。待实现者确认旧批次执行终态后再决定新有限计划。
