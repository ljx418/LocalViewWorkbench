# 独立实现复核

Reviewer `/root/v0_program_compute_diag_review`，独立上下文，只读。最终Fatal=0/Major=0；原4项Major（legacy未封存、启动/路径绕过账本、输出事后限额、公开异常路径泄漏）均已关闭。新PAYLOAD含精确legacy；纯路径转换与自有launch每次校验关键工具，保存argv/wrapperSHA/原handle birth/终态exit；命令复用有界runner，在失败也保留原始有限输出和真实exit；未证明释放则保留root；公开异常仅类型，详细错误仅受控state。

独立CPU执行10项新授权/诊断测试+8项生产有界runner测试，18/18 PASS，含真实CPU百万字节输出、超时、取消、拒绝越界和母授权不因子终态过期。没有执行GPU、服务、网络、媒体或浏览器操作。仅实现审查，不是Stage PASS，执行前仍须候选与子运行绑定。
