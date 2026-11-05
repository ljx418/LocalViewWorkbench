# 批准的GPU策略纠偏实现收据

依据：CHANGE-REQUEST-V1-S2-GPU-ADMISSION-01及项目负责人“批准继续进行”，包含proposed_resolution和execution_amendment_requested。保留原完整槽一次上限，不新增完整次数/复验，不实施P1–P5。

新增共享CPU资源owner，贯穿有限准入/当前NativeRuntime正式preflight/生产video_resources/真实基线及取消、卸载、浏览器、累计和热测join。按单GPU同源合法读数取max_used/min_free，记录reserved/异步差值；要求已知模型预算free>=19047、预测总used<23552。保留全部运行/资源/清理/归属及PRD分母，不动历史Harness或失败。

生产冷路径通过一次固定loopback /api/tags目录读取验证模型digest（最大1MiB、共享2秒绝对截止、无重试/重定向/代理），失败发生于GPU查询前。该查询不属于模型推理，仍受本轮整体loopback预算与候选源码控制。warm继续由已验证驻留与PID/birth检查，不重复冷加载预算。

事实纠正：V0 core与归档runner的实际ctx是2048、predict768，配置设计4096未用于原观测。保留既有生产参数，将profile收窄绑定实测2048/768；预加载也显式使用2048/768，避免服务默认32768。该实现说明写入批准决定，原提案和历史复算不改写。

定向阶段：首个63项通过；新共享策略/授权11项通过。扩展99项暴露measurement文件docstring中的导入插入错误（20个子场景NameError），修复实际模块导入后3项复验通过。最终100项相关定向测试实际通过，原始成功日志/哈希见policy-correction-directed-01。包括4520MiB真实基线、5544相对释放边界，以及one-over仍拒绝。

旧gpu-policy-reassessment-01属于8e7e06d时的历史策略草案/旧生产代码回放，不能在已修正源码上直接重跑其“应拒绝”断言或当新验收。新候选的生产行为由当前单测、完整离线与后续新鲜原生运行证明。

下一步最终candidate完整offline-checkpoint-28；全绿后仅一次resource-admission-policy-correction-01，成功才认领原full-oracle-correction-01。模型、固定样本、原动作上限、独审与人工签署仍必须满足。单图预算不代表完整视频/性能已通过。

完整offline-checkpoint-28保留NO_GO：482项运行中两处旧resource-resume测试fixture复制了已经过期的真实grant状态，导致其合成正例失败。仅在临时副本显式status=ACTIVE，真实旧grant不变；其余四项完整检查通过。纠正后最终完整复核使用offline-checkpoint-29。
