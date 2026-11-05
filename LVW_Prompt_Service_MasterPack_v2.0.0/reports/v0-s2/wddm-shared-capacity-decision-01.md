# WDDM 容量准入与控制权分离

Decision: APPROVED_FOR_IMPLEMENTATION_BY_CODEX_GATE_OWNER。依据PRD/docs02与当前A09/A10：资源门限按可用显存、实测峰值、RAM、耗时与释放；不得抢占或终止非本轮进程。用户已授权剩余V0本机GPU/代码验证。无公共API/Schema/固定分母或数值硬限变化。本决策纠正内部将桌面GPU PID列表当成独占计算租约的错误假设，冻结packet追加此authority，旧失败与旧决策保留。

原始受控诊断02：27个运行前GPU客户端，启动后仅增加本轮Comfy；原生NVIDIA XML记录WDDM且27条均C+G。不能把C+G标签或出现其他PID直接等同资源被抢占；也不能按程序名白名单或谎称它们owned。

仅在实际NVIDIA单GPUXML明确证明driver_model=WDDM时，容量准入使用现有cold profile/free>=19047MiB/预测峰值<23552、warm总峰值<23552、RAM>=2048及持续监控。完整记录observed/owned/unowned PID，unowned不重标owned。TCC与无共享证明的纯快照保持原严格PID规则；未知/无效/多GPU/缺资源数据仍fail closed。NVIDIA输出有界，设备容量匹配，先后资源读数取更保守值。

所有本轮模型调用、resident证明、卸载/取消/清理继续证明Ollama原listener PID/birth与其谱系。WDDM共享模式仅从观测GPU PID中提取能证明的owned子集；根被替换、借口不存在、错误birth仍拒绝。非本轮GPU客户端从不被卸载、终止、修改或认领。不修改numeric gates/20次warm/固定样本/重试语义。

生产owner与测量复算同时更新并加负例。实际完整矩阵及独立审查未完成前不能宣布Stage PASS；本决策不是旧失败翻绿，也不是放宽PID控制权。
