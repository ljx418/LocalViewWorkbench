# 启动绑定生命周期纠偏

本轮 full-oracle-correction-01 使用候选5a439ff，终态NO_GO，原一次性授权EXPIRED_NO_GO，lease.closed=1；未重试。图片及四输出局部事实PASS，native decoder局部事实PASS；首个视频负例因绑定文件缺失返回错误失败码。固定九项未闭合。

改动仅 `tools/v0_s2_stage_runtime.py` 和对应测试：先完成服务 readiness/ownership/registry，再独占创建 native/warm profile，然后启动 sampler，最后返回 context。公共API、错误码、资源上限、固定样本/分母、Provider预算、模型与上下文均不变。生产reader未放宽缺失或篡改拒绝。

新生命周期测试在修复前真实失败为NATIVE_BINDING_UNAVAILABLE，修复后两种实际reader均能加载并拒绝后续篡改；碰撞不覆盖，不可信根不发profile。35项定向测试退出0，原始日志及执行器收据见同目录。独立审查单独归档，不替代 Stage 验收。

可运行 `PYTHONPATH=. python3 -B reports/v0-s2/profile-lifecycle-correction-01/recompute.py` 复算已有失败/归档，不启动任何外部动作。记录峰值21493MiB，最低可用RAM7603MiB，42点采样；本轮公开提交6次、Provider上界1、preload0。清理/归档验证通过，不把失败标成未来正例。

下一步：封存新候选并完成offline-checkpoint-30；若通过，提交一个新的有限完整运行授权请求。现有母授权的本Stage完整次数已用完，本次纠偏授权也已终态过期；不自动执行新的GPU/模型/浏览器动作。
