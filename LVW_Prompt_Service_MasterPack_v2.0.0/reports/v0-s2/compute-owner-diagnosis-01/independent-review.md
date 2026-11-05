# 隔离故障与清理审查

审查者 `/root/s2_lifecycle_terminal_review`，独立上下文，只读仓库及既有受控原始终态，无GPU、进程/服务、网络、媒体、浏览器或模型操作。不是Stage PASS。

92文件/1084286字节全部SHA与大小匹配。manifest aa5468b01d32fa8bdbd3a3104d0c166acfbe6096bbf19dd0c938b2d60ac9eef9，文件集合仅额外包含manifest自身。原owned根不存在，lease.closed=1，子授权EXPIRED_NO_GO。两服务原PID/birth复证STOPPED，wrapper/sampler退出，HTTP pending=0、listener=0，junction只删除链接保留target，清理证据闭合。

公开15项11 PASS/1 FAIL(category-static)/3 NOT_RUN；累计在线5项2局部PASS/3 NOT_RUN；完整九项0/9 PASS，不能把局部事实计为整个Stage通过。视频模型调用0，失败时未发布结果。

comfy.log直接保留内部GPU_FOREIGN_COMPUTE_PROCESS，外层RESOURCE_PREFLIGHT_UNPROVEN。默认warm=False只允许Comfy自身PID；warm才加入证明的owned PID。该集合拒绝不能独立证明实际进程归属。原始记录没有保存拒绝compute PID及birth/父链，不能确定是外部程序、本轮Ollama listener/runner或残留。

127采样峰值21516MiB，最低RAM7597MiB；准入附近GPU3347/3343MiB。这些值不能补回瞬时PID快照，不能证明显存不足，不能据此要求用户释放GPU。建议新增有限、零推理/媒体/浏览器的归属诊断，记录原GPU/compute列表、允许集合、时间、原异常，仅对观测PID保存birth/可执行文件/父链并比对本轮已证明谱系；不得直接选择PID放行。
