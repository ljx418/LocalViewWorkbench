# 架构裁决：S3父侧native custody，N1离线实施冻结

本裁决基于b95de076/交付13e7749源码与readiness01材料，由现有架构/门禁owner签发内部实现范围，不是新产品合同、人类签署或真实运行许可。当前Stage不变。

## 采纳与纠正
采纳原生后代清理owner在worker内、父只有WSL worker句柄、sampler装配顺序和五键投影不兼容、admission无生产者、部署工厂未接线等事实；readiness材料仍是静态证据，不宣称实测。
拒绝“worker给PID/birth，父重证同路径即取得终止权”：身份相同不证明本轮创建/托管，且worker可在登记前退出留下服务。必须父在任何服务代码运行前拥有原始创建句柄并落实后代约束。worker不得授予父杀进程权限，也不按进程名/任意PID接管。
拒绝以未来native_services_stopped/gpu_released/rollback_verified作为本次启动前提的循环依赖。启动准入只核授权余额/封存工具来源/隔离与已就绪托管机制；终态再证明服务/后代/GPU释放及真实回滚。旧验证器保持failclosed，未来另冻结内部native版本和可信owner组合，不能把accepted=False改True或自写PROVEN文档解锁。
不照搬S2 cleanup代码创建第二份预算/清理权威。新owner只补“父原始创建句柄与Windows Job约束”缺口，S2 legacy owner冻结；GPU/资源采样与门限复用现有owner，Job进程数为零不等于GPU已释放。
监督协议/1本包不加事件、不改schema；broker控制走父私有通道，与worker进度协议分开。I22仍是原离线I24集的零动作义务，不改成native零动作；后续真实运行新增scope overlay，不改旧分母/证据。单行pilot不得调用被缩成1行的QualityPhase；QualityPhase固定16保持，未来单链通过单独公开媒体入口只证明接线、不替代16项。

## 后续顺序（仍在当前Stage）
N1父原始托管broker/adapter离线代码与负例→独审；N2部署/driver/sampler/五键projection与父拥有服务接线→离线组合；N3分开启动/终态准入，封存原账本/工具/模型/样本和有限子授权→最小真实生产链；N4完整固定I24及产品12/独立QS/WebP/A06/安装回滚/累计门禁与人签。这是实施顺序，不把四个包当四次完整checkpoint。合并同根因问题，不全量重跑已关闭组。原1024/24/48h历史累计不清零，134..143只是旧设计数，真实余额与工具身份须在N3前核算。本包不读账本、不探测进程/模型。
