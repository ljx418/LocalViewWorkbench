# N1 correction05：六个开放Major集中纠正

接受独立静态审查F0/M6/m0，原候选d751bced75cdc1d21cee072892860a7c4f8ac542，证据bc1a27d9d18faedc15797d3153cd0fe8a4cb3d8a。M03/M05/M06/M07/M08/M09开放；M04/M11静态关闭，兼容M01/M02/M10/m01保持。133/133机器收据不改写，但不能关闭未覆盖交错。完整原审查在received-review/review.md，以生产调用路径和原blob为准，不要求对已确定缺陷先重跑失败候选。

## 根因与架构约束（Codex冻结，公共合同不变）
本次集中修复同一N1内部生命周期，不逐缺陷微型交接，不另建通用进程平台。一个有限启动/清理上下文：在不可变原授权预算与时钟上，持有单向cancel/stopping/unknown闩锁、首次清理deadline、原资源表与每个inflight操作owner。deadline初始化和状态转移由明确锁/单一owner原子发布；所有层拿同一个实际上下文，不仅抄deadline数值。启动动作前、返回后、每个create/assign/Resume/reader启动前检查；监督超期向Core发布cancel，晚到只能接管清理，不能继续业务或后续role。首次入口即过期不得先启动action再拒。

所有原资源取得瞬间登记（含NUL、pipe两端、process/thread、Popen/endpoint、I/O worker与其原thread HANDLE）；成功移交才改变owner、成功关闭才忘记。异常发生在返回pair/对象前也必须有持久owner与可达恢复入口。不接受错误字符串或只有整数copy代替原对象拥有关系。既有启动器返回类型尽量保持，必要薄内部retained registry/恢复方法可增量，不扩展公共API/旧授权。

清理是按每个resource独立执行的有限finalizer，普通错/取消不跳过后续安全步骤；primary/secondary并存，KI/SystemExit在安全清理后传播。不可在低层吞取消令上层不知道；已确认关闭项幂等，未确认项在原deadline内可继续协调。尝试FINISHED不等于资源CLOSED，不锁死恢复。期限耗尽则保留UNKNOWN与原owner供诊断/明确恢复，不无限新预算。

原始清理deadline=首次入口min(original lease, original remaining, now+5s)原子冻结，所有wait/join/cancel/settle/API release前重算剩余；无固定额外1s/5s。Windows进行中的await每次读取共享收紧期限；cancel与submit/IN_IO按实际请求代协调，不用上一代done。Cancel请求≠完成，worker stop/join确认后才允许关它使用的file，thread HANDLE关闭事实也必需。partialwrite每段核取消/截止。BrokerProcess不得绕过endpoint直接关闭同一stdin/stdout；成功Posix close幂等仍True，失败Windows close不得先置不可逆closed。

后台thread创建/启动中/实际活跃/退出/移交状态不能用Thread.start正常返回一个布尔替代。start未返回/启动后抛错也始终有会话original owner；清理超期不能把identNone当已结束。closer构造/start失败具名通知且保留可恢复入口；等待不持owner锁，不自join，不形成callback→closer→callback循环。UNKNOWN采用共享单向latch或原子状态owner，晚到reply不可覆写。

双向frame预算check/reserve/commit由共同原子owner，发送序列保持唯一；接收与STOPPED正确消费终态预留，不对终态重复加保留额。总1024、32KiB、60s/120s、16进程/17含broker、6h及5s原门限不改。Session严格要求实际reader/端点/worker完成事实，缺失/None/异常全UNKNOWN；不能以真实BrokerProcess通常提供较全字段为父接口放松借口。

## Workpack批次与允许文件
同一冻结N1内有序连续两组（每组局部静态收据，不单独完整验收）：WP-A底层资源取得/清理/endpoint/启动上下文；WP-B Session并发/恢复/预算/严格facts及贯穿回归。两组同一个Claude owner串行完成，公共内部状态机只此owner写。结束集中一次N1测试+独审，不把它们变成跨Stage。
只允许tools/v0_s3_native_custody.py、tools/v0_s3_native_broker.py、tools/test_v0_s3_native_custody.py、tools/test_v0_s3_native_custody_regressions.py，以及NEW tools/test_v0_s3_native_custody_correction05.py和NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-05/。原controller/worker/runtime/driver/supervisor/sampler/授权/公共schema/质量阈值/control/MANIFEST/全部历史报告冻结。确需跨范围先askroot，不暗改。不可将N2提前实施，不移除native拒绝点。

## 冻结验收与测试修正
regression-obligations.json冻结24组负例与Oracle，补上独审未触发路径。旧133 nodeids保留且顺序不变；独审明确R14的“失败peer永不重试”“仅三项facts算完整”是错误Oracle，root在本包批准改为原期限内只重试未关项、缺失reader/endpoint/worker事实拒绝。正例fake提供明确可核事实，不默认补True；绝不因缺事实运行困难弱化生产合同。其他case不得削弱；新增独立correction05测试节点由root冻结追加。用明确event/barrier与可控原语/假时钟触发实际生产owner，不sleep碰运气、不以无效替身解释一切。Thread.start未返回等负例先记录产品返回事实，再测试owner明确有界释放/收尾；成功条件不能靠pytest进程退出回收。新增用例逐组给义务→生产入口→触发→oracle→负例→返回时终态→salvage证明映射。

## 执行边界
当前仅静态实现/AST/源码检索，不import候选/collection/pytest。完成两组后先精确路径Git提交全允许源（不bulkadd），再askroot有限动态计划：候选SHA与source/tool pins、原223依赖文件pins和3stdlib、旧133+新增节点有序固定分母、root外部guard、三条绝对argv/cwd、单批<=300s、真实FD身份/全部线程/逐node/raw/退出码。ask后结束turn等待reply，不同时worker_done关闭问题；报告完成或受阻无待答问题才worker_done。
root ACK后一次执行；失败原候选/原收据保留不自动修到绿/复跑。一般dlopen/dlsym、真实Win32/Job/OS业务进程/GPU/模型/服务/socket/sqlite/网络/媒体/下载/原ledger严格拒；仅root前置硬guard后候选/pytest前一次ctypes.dlopen(None)可信stdlib预装，随即永久关闭。counter仅未来ACK的外层前后一次只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，不写清零退款复活，不带其FD进候选。
FIRST429立即WAIT_BUDGET不重试/切供应商/切Harness/root接手，只有用户明确恢复才继续；FIRST审批拒绝/超时停不包装绕过。禁止派生Agent、清理他人文件、批量gitadd。只READY_FOR_REVIEW，独审/真实native/I24/产品12/A06/账本余额/质量/人工签署仍未证，不StagePASS。
