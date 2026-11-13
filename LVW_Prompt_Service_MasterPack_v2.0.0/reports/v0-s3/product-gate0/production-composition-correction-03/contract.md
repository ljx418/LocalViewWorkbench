# 生产组合纠偏03：集中关闭 M04/M06/M08 与两项报告Minor

基准候选8f375f887f0121ab5a0395f032dd74d8a6f0cf0b。本包是现有V1/COMPLETE03内的修复，不改公共合同、固定I01–I24、产品12项、质量门限或当前Stage。独审msg_524bb3b57a25：F0/M3/m2；M05/M07/指定FD snapshot及本轮P01已关闭，不重开整套。原失败、三次作者运行及独审37例26断言通过/11失败（8有效缺陷复现、3探针限制）全部保留。

唯一实现owner ClaudeCode。允许tools/v0_s3_controller_io.py、tools/v0_s3_production_controller.py、tools/v0_s3_quality_worker.py、tools/test_v0_s3_production_composition.py；只有必要直接兼容才可改tools/test_v0_s3_supervisor.py。supervisor生产owner/QualityPhase/coordinator/runtime/authority/executor/fixture、公共合同、control/MANIFEST/旧证据不改。报告仅NEW implementation-production-composition-correction-03。源码落点以当前V1布局为准；不得清理旧工件或覆盖其他owner改动。

## M04：外部只读依赖锚点全链
open_read_only_directory绝对路径O_NOFOLLOW只保护叶目录，不够。复用现有从文件系统根逐组件NOFOLLOW打开/记录并验证身份的owner，为明确封存context声明的外部依赖锚点建立可信链；每个实际数据读取在同一有界regular/nonblock访问链上完成并验证祖先及叶身份。合法已命名外依赖仍可读；其父目录换symlink（即使同hash/同叶inode）必须拒绝。不要resolve后当原路径，也不把任意外部路径升级权限。复用现有helper，不另造通用平台。所有中间FD由明确owner在成功、普通异常、BaseException下关闭。

## M06：PRECHECK完成前绑定输出链与创建对象
_precheck在公开PRECHECK transition之前建立root及temp/s3-production-controller输出链并持有输出fd。创建helper返回的每级fd身份必须与声明path记录交叉匹配，不能先获取旧fd再lstat新path当同一对象；实现最小内部返回链或安全受控逐层机制，若要改冻结owner先ask。reservation/summary/receipt全生命周期复用同一已绑定目录fd/身份链，所有写入前重核：PRECHECK之后换root/temp/controller普通目录、换root祖先symlink，或创建返回与身份观察接缝替换，都应拒绝写入替代对象、拒绝发布虚假receipt_path/summary_path。只读检查与磁盘操作非原子，声明实际观察边界，不承诺路径永不被外部改变。保留已有partial，不在未知根补写失败收据，不删除未知目录。正常O_EXCL写与幂等无重发保留。

## M08：独立释放finally与异常终态
终态清理/persist/observer外围有独立finally，保证_persist_receipt或其他终态步骤抛KeyboardInterrupt/SystemExit时，已明确持有root/output anchors仍释放，取消继续传播；不吞BaseException。普通持久化异常即使无primary也必须结构化UNKNOWN_RETAINED/receipt_persisted=false，记录secondary错误、已有summary是否真的写成功与路径；已有磁盘summary不假称删除/未发生，不自动重写历史产物。若现有summary_persisted字段用于资格，另列客观磁盘动作事实，解释两者区别，避免虚构回滚。observer普通异常不得main泛化exit5/空stdout；以UNKNOWN及观察失败/清理未知返回，不把未知变空或假称清理成功。primary/secondary/cleanup错误分开，保留root/预约、禁止refund/resend/archive，无无限持久化重试。PRE_RELEASE磁盘收据与POST_RELEASE返回诊断分开，不改写已有收据声称含事后观察。重复_release_anchors只处理自身FD，不关闭未知FD。

## meta01 / m03 报告修正
NEW报告准确列原author-candidate.json与frozen-sources.json的7个frozen owner：quality_phase、coordinator、runtime_binding、stage_runtime、budget_authority、local_program_authority、v0_s2_runtime；另列本次changed sources，不互换。统一三次作者执行attempt01 0call import失败、attempt02 19/18PASS1FAIL、attempt03 21/21PASS；root ACK次数按事实，不继续遗留待ACK字样。原FD8身份UNKNOWN，仅已证明枚举可产生关闭FD幻影，不断言该FD8具体原因。旧报告保留，新报告勘误交叉引用。精确argv绝对/相对路径等价也如实记录，不声称字符串逐字一致。

## 执行边界与验证
先静态实现/AST，不导入候选/pytest/插件。准备一次最小定向计划（精确argv/cwd、选中nodes或独立case、source/tool/依赖hash、前置auditguard、wall<=300s、raw日志/退出码/FD线程清理）askroot。root ACK后才运行一次；不自行补compat或整套37/21/60/123等。负例驱动实际worker/controller；包括合法外依赖+父symlink、PRECHECK早窗口与创建身份接缝、直接persist单/双普通异常、终态KI/SystemExit释放且继续传播、observer普通异常及正常16行真实QualityPhase链兼容。探针不要复制原独审已说明的错误：读取请求参数总和非实际读取字节，未创建seam worker应安全处理；不能因坏探针误报产品。

auditguard必须在任何候选/pytest导入前硬拒subprocess/socket/fork/exec/spawn/system/sqlite3.connect及原ledger/counter读取；仅本进程threads/pipe/合成文件。沿用已封存已装依赖目录方案，不下载/安装/site.main/.pth，不启动模型/GPU/服务/native/browser/用户媒体。原counter仅guard外前后只读hash acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，inactive28/240/12.362；不写退款清零/另建计数器/旧grant复活。

首次429立即WAIT_BUDGET停止，不重试、不切Harness/模型、不由Codex接手。首次审批拒绝/超时停止askroot，不包装绕过或修改审批配置。完成只报READY_FOR_REVIEW；固定I24/产品12/native/Windows/A06/原ledger/质量/人签仍未证。不签StagePASS。
