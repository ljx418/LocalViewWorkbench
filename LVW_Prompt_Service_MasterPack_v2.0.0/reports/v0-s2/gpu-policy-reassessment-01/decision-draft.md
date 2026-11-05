# GPU准入纠偏 ADR 草案

日期：2026-11-05。状态：PROPOSED_NOT_ACTIVE。用户指出门限理解错误后，重新复算历史原始证据；没有新GPU/模型/媒体/服务运行。

## 错误与责任

原PRD docs/02的硬限是运行总峰值<23552MiB、可用RAM>=2048MiB、OOM=0，21GiB为优化目标。没有“启动前桌面已用显存<=4096MiB”的产品要求。实施时把历史live_probe的保守空闲环境假设搬入S2生产资源owner（首次提交2f9487f），又复制到准入、基线绑定、取消/卸载证据中，形成了错误的全链路约束。该门限不来自实际模型显存预算；num_ctx=4096的单位是tokens，与4096MiB门限无关，不据数值巧合推断历史成因。

Windows与WSL依次读取的GPU值不是同一时刻；固定要求差值<=128MiB会把合理波动当作无效遥测。应验证同一GPU/容量、每份读数合法，取最大used/最小free作保守预算，保留差值诊断。

还有一个实际CPU可复现的后续误拦截：旧video_resources要求total-used-free差额<=256MiB。本机原始读数为24564/4520/19619，差额425MiB；当前生产函数直接返回RESOURCE_BUSY/RESOURCE_TELEMETRY_INVALID。应记录保留/未归类差额，不能要求三项严格互补；每份total、used、free非负、used+free<=total等有效性检查仍需保留。

此前要求用户按4096MiB反复释放GPU，是架构/门禁判断错误。原NO_GO只描述当时错误规则下的执行器终态，不是证明物理显存不足；历史终态保留，结论解释纠正。

## 证据与建议的精确方法

receipt.json由recompute.py只读原始terminal、archive manifest与trace并校验hash后生成。历史真图：服务启动前used=3712MiB，总峰值22247MiB，观测增量18535MiB。针对同一gemma4:26b digest、num_ctx4096、单并发与受限图片1024/视频帧768的受监控尝试，建议初始模型profile采用该观测增量，另要求free余量512MiB：

- required_free_mib=18535+512=19047。
- 准入要求保守min(free)>=19047，且max(used)+18535<23552；不再要求used<=4096。
- 当前记录最小free=19619、最大used=4520，预测总used=23055，满足上述准入；应允许受监控尝试。
- 先前used9649/free14490，预测总used28184且free不足，仍拒绝；不是把所有失败放行。
- 运行时仍严格监测GPU<23552、RAM>=2048、OOM=0，原取消/晚到/清理、外来compute任务与原进程归属防护不变。
- 本profile只有真图观测基础，不声称已证明四帧/热矩阵最坏峰值；允许尝试不保证一定完成。模型digest/ctx/输入规格/并发变化不继承此预算，需新profile/校准。
- warm仅在已证明本轮模型驻留与进程归属时沿用原warm检查，不再次要求冷加载整个模型的free预算。
- 冷基线记录真实值，移除所有0..4096的伪范围；取消释放仍相对实际基线+1024、原30秒及稳定采样，运行硬限继续独立生效。

这是一份具体待批准方法，不是已经生效的新门禁。512MiB为建议的最低free余量，与仍保留的23GiB总峰值硬限共同使用；不能拿单图观测宣称全部质量/性能已经通过。

## 实施范围与一次收口

建立单一共享CPU资源策略与候选绑定的model profile，同时接入有限准入、当前NativeRuntime正式preflight、生产video_resources、warm/取消/浏览器/累计证据中的基线校验。历史reports内live_probe和失败不改写；当前NativeRuntime覆盖其旧准入，不能继续继承4096/128限制。num_ctx4096、工件4096bytes等无关边界不替换。

准确触点列入change-request-gpu-admission-01.json。先做真实记录回放、free exact/one-below、总峰值exact/one-below、设备/遥测错误、外来compute/归属、模型profile不匹配等负例，再一次最终子树/合同/治理检查，避免只改最外层准入后又卡在内部相同假设。

因当前冻结packet和获批运行请求已把这些实现假设固化为门禁，按AGENTS第10条需要明确批准纠偏ADR后再修改实际执行字节。可以一并批准新的有限执行修正：1个新准入child，恢复原未使用full-oracle-correction-01一次上限，额外完整次数0、完整复验0，所有动作预算/loopback/样本/模型/清理维持；不复活任何旧grant或重放旧child。
