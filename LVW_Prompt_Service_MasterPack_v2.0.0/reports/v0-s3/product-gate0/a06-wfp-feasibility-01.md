# A06 WFP 可行性核实 01

2026-11-12；root 架构调查，仅读取微软官方在线文档。未调用本机 WFP、原生程序、GPU、媒体、模型或产品服务；未改变系统配置/权限/预算/固定分母。本记录不是方案已验证、运行授权或 Gate0。

## 已核实的官方机制

- [FwpmEngineOpen0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmengineopen0)：使用 FWPM_SESSION_FLAG_DYNAMIC 时，会话内新增 WFP 对象随会话结束删除。此保证只适用于这些对象，不能推广到任何全局设置。
- [WFP Access Control](https://learn.microsoft.com/en-us/windows/win32/fwp/access-control)：OPEN、READ、ADD、SUBSCRIBE、WRITE 是不同访问权限；默认 everyone 的 OPEN 不证明能添加过滤器或读取/订阅事件。当前非管理员事实不足以直接判定全部操作被拒绝，也不足以假定可执行；需实际能力核验，禁止修改 DACL 为自己提权。
- [FwpmEngineSetOption0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmenginesetoption0)：网络事件收集设置跨重启保留，不能在动态会话内调用此 setter。不能把“临时动态过滤器”扩大为可修改全局收集设置的授权。若当前事件收集不可用，不能私自开启或将无事件当零尝试。
- [FwpmNetEventSubscribe0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmneteventsubscribe0)：事件订阅有独立 SUBSCRIBE 权限要求。事件流的启用、过滤、丢失/缓冲和区间完整性仍须证明，不用订阅返回成功替代完整观测。
- [ALE](https://learn.microsoft.com/en-us/windows/win32/fwp/application-layer-enforcement--ale-) 与 [Condition Identifiers](https://learn.microsoft.com/en-us/windows/win32/fwp/filtering-condition-identifiers-)：ALE_APP_ID 使用应用程序规范路径，ALE_USER_ID 使用用户身份。两者都不能直接称为某个 PID/birth 的隔离。本机共享 Python/Ollama 路径规则可能覆盖同路径的其他进程，这是设计风险推断，尚无实际运行证据。

## 架构裁定与下一步

WFP 仅保留为候选，不进入产品执行。既有“仅本轮进程、保留 loopback、零永久设置、非 loopback 出站阻断及尝试观测”义务不变。不能采用共享 executable 路径全封、系统级 netsh、全局 audit 设置、代理环境或空连接快照冒充达标。

下一有限能力调查如果采用 WFP，须先冻结只读权限/已有事件设置的最小查询与输出上限；OPEN 成功不能触发自动写过滤器。后续还须给出真正隔离本轮身份的机制、IPv4/IPv6/UDP/DNS/子进程覆盖、观察丢失判据、完整生效区间和对象退出清理证明。不得为了证明阻断而未经许可产生真实非 loopback 请求。以上未闭合前不冻结实机执行方案、不请求笼统提权。

此调查用于排除错误接线，不新增产品子阶段，不重跑已接受 P1/P2B/P3A，不改变当前 P3B 独审范围。
