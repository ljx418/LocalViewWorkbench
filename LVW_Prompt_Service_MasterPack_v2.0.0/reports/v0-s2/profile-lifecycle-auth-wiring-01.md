# 一次性生命周期复验授权接线

用户明确批准AUTH-REQUEST-V1-S2-PROFILE-LIFECYCLE-01，原请求SHA256 d26de57732f99320615d36112fd0c54de27a990d04a2c69bfaf91e23454456da不变。批准收据单独保存，不修改原PENDING请求历史。授权窗口最多21600秒，新准入一次/完整运行一次/额外复验零；原授权均过期且保留hash。

新增tools/v0_s2_lifecycle_authorization.py复用既有有限readiness执行器和同一完整stage checkpoint，新增槽位显式接线。校验真实项目批准、母授权、暂停、请求SHA、当前模型profile、冻结合同不变、允许候选diff、五次失败终态及关闭lease、历史过期权限、当前候选新鲜三点readiness。旧槽位不可重放。源码/Stage/模型/工具/样本的执行身份封存沿用受控执行器；cleanup与终态expire沿用既有实现。

已运行16项定向CPU检查通过；新授权用例使用隔离临时Git/文件，不证明真实模型或Stage通过。新增检查覆盖真实拒绝路径、错误候选/门限、旧失败与历史授权篡改、重复claim、同候选readiness和有效路由。独立接线审查另记，最终完整离线检查必须通过后方可进行本次唯一真实准入。

独立预审发现Major：原授权校验只绑定准入摘要，缺少受控原始证据链；在任何真实动作前已修复。verify_ready新增active-child→终态child唯一变化、raw terminal→public hash、固定三组native/WSL原始输出→样本→共享oracle复算、六条命令启动/exit/stdout/stderr哈希，和零服务/模型/媒体/浏览器副作用。测试valid必须提供完整显式合成原始链；缺失、篡改、样本不足、旧候选、未关lease、同步伪造摘要与oracle均拒绝。真实验收尚未执行。
