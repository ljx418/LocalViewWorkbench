# S3-P4生产组合执行包01：冻结内部接线设计

基线07277a6，证据后继c6bce90仅报告。13真实fixture组件已独审接受，原grant过期，counter inactive；原I01–I24和产品12分母不变。此包只离线实现，不激活服务/模型/native/GPU/原账本。C01–C12为实施验收映射，不是新发布分母。

## 唯一owner与文件

新增tools/v0_s3_production_controller.py和tools/test_v0_s3_production_composition.py；允许tools/v0_s3_quality_worker.py、tools/v0_s3_coordinator.py最小内部接线适配，tools/test_v0_s3_integration.py必要兼容测试。supervisor/其测试、executor/runner/fixture、QualityPhase、runtime/authority、公共合同、阈值分母、旧证据/control/MANIFEST/V2禁止修改。接口不足先askroot，不复制phase/安装/归档/ledger/safe-read权威。NEW报告implementation-production-composition-01。

## 总体架构、详细数据流、状态机

新增正式controller CLI main，仅闭合参数/context路径及hash/有限准入引用，不接任意命令/module/Shell/callback反序列化。复用WorkerContext、build_production_command、ParentSupervisor、ParentOriginalEvidence、load_published_execution_receipt/load_source_plan/recompute_scores、aggregate_twelve_keys和既有安装工厂。默认native真实执行准入拒绝：缺原生后代custody/GPU清理、原ledger、工具依赖、有限root子授权时稳定BLOCKED/NOT_PROVEN且0spawn。调用者布尔值、platform字符串或自写能力JSON不能替代已接受准入权威，无--force绕过。当前真实能力未证，不虚造授权。

单一状态机：PRECHECK→PLAN_SEALED→WORKER_SUPERVISED→ORIGINALS_VERIFIED→RECEIPTS_BOUND→SUMMARY_PERSISTED；未开始拒绝REFUSED_BEFORE_START，开始后不明UNKNOWN_RETAINED。错误不得重发/退款/换runid或样本；清理失败保留根预约，落盘不覆盖。

PRECHECK核对context精确hash和run/candidate/authorization/root identity、16行投影/source identity/预算/依赖manifest/binding。缺失/外来在spawn前拒绝。复用原投影解析owner，发送前完整封存16行实际hash/bytes计划，不建立第二套投影协议。

生产路径必须是controller→build_production_command固定quality_worker→worker.main/WorkerContext.load/build_native_driver→run_worker→真实QualityPhase.run→ProtocolWriter真实pipe→ParentSupervisor→本轮实际canonical。不允许clean_terminal fixture或手写canonical冒充16行。原10800/600/21600与字节/消息边界保留，parent不执行worker传来的Python回调。

离线组合seam显式注入合成driver/spawner/fakeclock，全部进程内threads/os.pipe，不生成OS子进程。可在测试替换native driver构造以驱动正式worker入口，但真实phase/协议/reader/canonical仍必须使用生产owner。seam不得序列化进context或变成CLI可开启的真实执行后门；不证明native依赖闭包，所有收据标明offline/synthetic。

终态父独立读取本轮canonical/source_plan/raw，经ParentOriginalEvidence封存/manifest重核后才可消费。保留run/candidate/projection/root/canonical/sourceplan/raw至summary的source_ref/hash/owner来源链。外来/缺失/变化/未完/错根不能成功汇总。父原件安全读取owner及先前关闭发现不重新实现。

定义原收据适配表：从真实执行canonical/cleanup/quality事实生成aggregate输入，而非手写complete_receipts。没有独立QS/A06/WebP/安装回滚/cleanup等原始收据保持NOT_RUN/BLOCKED，不造PASS；QS复用recompute_scores及真实独立证明，16行执行不等于内容质量通过。离线顶层summary不把内部合成正例统计为产品12真实通过；所有模式stage_pass_claim=false/product_gate0=false。缺原件/评分/清理的失败与来源范围必须机器可读。

## 验收映射：生产路径→驱动→Oracle→负例→终态→清理

|映射|必须证明|
|---|---|
|C01/I03/I04/I23|缺/错context/hash/root/candidate/auth/投影spawn前拒绝，0spawn/0模型；不写候选业务产物|
|C02/I07|同一context真实phase16行、sourcehash/ordinal、协议事件、实际canonical落盘，经正式controller消费|
|C03/I10/I11/I21|phase真实row/history次序被parent接受，重复晚到不延长期限|
|C04/I13/I14|异常/未完/cleanup未知不成功汇总，保留根预约不重发|
|C05/I16|controller实际调用manifest并消费重核；改写/错根/缺原件拒绝|
|C06/I19/I20|实际同run收据适配→十二键；缺QS/A06/WebP/cleanup/安装回滚非PASS，旧9不能补绿|
|C07/I24|context/投影/原件→父manifest→summary provenance同源，旧外来收据拒绝|
|C08/I22|pre-import guard零fixture/network/GPU/原ledger，测试临时根清理不冒充产品服务清理|
|C09/I01/I02/I05/I06|复用工厂/default空hook，profile权威不另建ledger/debit|
|C10/I17/I18|原residue accessor，UNKNOWN不能当空、不删除未知文件|
|C11/I15|恢复只协调已有证据，不重发、不根据信息文件PID终止进程|
|C12/全24|逐I01–I24机器映射实际scope与缺口，不签全24或新28分母|

一次集中交付定向组合与负例，不机械13/41/74/186/257回归。所有失败原始日志/命令/退出/hash/guard/FD线程清理保留。13fixture仅对应072源码，不迁移为新候选PASS；变化影响范围需列明。后续真实准入另由root在母授权内封存，不要求人类重复批准。FIRST Claude429停WAIT_BUDGET，不retry/换路由/自动接手；审批拒绝或超时askroot停止。本包不证明Windows/native/GPU/A06/原ledger/实际质量/根迁移。
