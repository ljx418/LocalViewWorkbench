# N2生产接线准备更新02（不激活业务实现）

这是当前N1实现期间允许的一条后续文档准备线。权威顺序及当前Stage不变，沿用native-custody-implementation-01/architecture-decision.md的N1→N2→N3→N4顺序；本件补充native-execution-readiness-01的旧调用图，不另建开发路线、不冻结新合同、不消费完整checkpoint。

只读复核了8个既有owner源码，与已接受离线组合候选b95de076逐字一致；source-audit.json记录hash、AST精确符号位置。当前N1 broker/custody不在本次8源审计范围，未读取实现者尚未提交改动，不干扰同一owner写入。

## 接线前仍须完成的义务

| ID | 主题 | 当前代码位置 | 后续约束 |
|---|---|---|---|
| N2-P01 | 安装工厂 | `tools/v0_s3_coordinator.py:309` | 复用继承工厂；目前未证明正式控制器装配。首个排他profile写入即包含唯一s3_budget_binding，不先LOCAL01再覆盖。 |
| N2-P02 | 预算绑定 | `tools/v0_s3_coordinator.py:191` | 形状/来源校验不替代原账本余额或debit。执行前余额由原authority核，当前不读账本。 |
| N2-P03 | 驱动构造 | `tools/v0_s3_quality_worker.py:615` | 只构造NativeRuntime，不启动sampler。不得把函数存在当已装配。 |
| N2-P04 | 资源observer | `tools/v0_s2_runtime.py:183` | NativeRuntime构造resource_observer=None；真实采样接线须先完成且保留owner，再构造QualityPhase。父原托管下的sampler句柄只由唯一N1 owner掌握，不在worker重启一份。 |
| N2-P05 | 五键投影 | `tools/v0_s3_quality_worker.py:414` | 既有strict五键不能接收完整native/warm profile；新增只读投影绑定profile原件hash/模型digest/候选/子授权/原PID出生身份/实测baseline，不能靠人工重写PID或基线。 |
| N2-P06 | profile身份 | `tools/v0_s2_runtime.py:152` | native profile与warm profile字段不同；只有warm含baseline。最终来源由实测baseline owner产生，不能从native缺字段补0。 |
| N2-P07 | QualityPhase | `tools/v0_s3_quality_phase.py:896` | 固定16行不缩减；薄adapter复用实际submit/chat日志/observer/preload/residue。单样本真实接线pilot走独立公开媒体入口，不伪装16行通过。 |
| N2-P08 | 原件与清理 | `tools/v0_s3_coordinator.py:347` | 父读取原canonical/source/raw，不接受worker摘要代替；父原HANDLE/Job空不等于GPU释放，资源采样与系统owner事实另核。 |
| N2-P09 | native准入 | `tools/v0_s3_production_controller.py:567` | 旧拒绝点保留，不能accepted=False改True。启动前准入与运行后release/rollback拆开，不能以后验成功作为先验启动前提。 |

## N2候选执行次序（待正式packet冻结）

1. 在N1独审与root关闭后，重新绑定该最终候选及原始创建owner接口；当前任何N1自检成功都不解锁此步骤。
2. 封存工具与配置、验证安装工厂和run-root身份、原预算capability；profile首写通过S3工厂私有hook，旧S2 owner不复制、不静默改公共schema。
3. parent-owned服务与sampler先按原托管关系完成装配，实际观察器可调用后才构造QualityPhase；adapter只做兼容投影，不能自己创建服务或授予杀任意PID权限。
4. 输出strict五键只读binding与完整profile的出处关系；每个来源字段真实缺失则拒绝，unknown不补0、不伪造基线。
5. 离线组合验证真实factory→adapter→worker→QualityPhase入口，合同负例覆盖profile重写、预算来源/PID出生/模型digest漂移、sampler未就绪、残留与清理UNKNOWN。它只证明代码接线，不证明真实Ollama/Comfy/GPU/质量。
6. 真实启动仍留待N3有限子授权与工具/样本/端口/进程预算封存，N4统一执行固定I24与产品12、QS、WebP、A06、安装回滚及累计回归。不能用本清单9项替代任何旧分母。

正式N2 packet还需给出允许写入路径、精确候选、合同版本和有序测试命令；这些尚未冻结。本轮没有授权N2实施，没有import任一候选，没有模型/GPU/进程/网络/数据库/原账本动作。verification.json只核文档与源码字节/AST，不是Gate0或产品PASS。
