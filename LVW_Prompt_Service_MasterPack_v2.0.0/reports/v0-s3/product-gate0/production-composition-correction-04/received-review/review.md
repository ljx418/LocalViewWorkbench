生产组合纠偏03独立审查：CHANGES_REQUIRED，Fatal 0 / Major 1 / Minor 0。

候选6885f7a62b223f5e2c7904a9f929e760396fd88b，delivery6ea33bc4ac8a383df8db1be978b077e7ad9d8338，baseline8f375f887f0121ab5a0395f032dd74d8a6f0cf0b。M04/M06/meta01/m03关闭，M08部分修复但仍开放。35PASS不是关闭依据。本审没有产品源码修复、提交或Stage PASS签署。

已读AGENTS、governance README、execution-control、执行索引、root correction03 contract/root-decision/received-review review及原有效缺陷JSON、review03 intake/received。对照的是原独审oracle和候选代码，不采用作者自关闭结论。所有received文件逐字节匹配delivery对应文件（candidate-scope.json）。baseline到delivery只有规定四变化源和NEW implementation-production-composition-correction-03文件，没有旧证据/合同/control变更。

自身HEAD始终204e585f81837d9743869b94030ae941b2d52be4；初始91个tools顶层Python源码均等于baseline，不把自身HEAD冒充物化候选。保存initial-state.json/index原字节/sourcehash后，仅物化本次四变化源；全部91源与候选一致，index字节、HEAD不变（materialization.json/final-integrity.json）。没有checkout整树、clean/reset/add/commit，没有改CMD/CRLF。原既存修改和历史未跟踪目录保留，所有新增审查内容只写本NEW目录。

执行计划plan.json SHA256 80aa83a111cb2fa719df157898710c0254106c5ebcaccfa0f26466a909c2ed3a；root msg_260f915f8294 ACK一次后执行一次，27独立case，0 pytest.main/collection，未跑作者35/21或上轮37整套，未补跑。精确绝对argv/cwd/起止见exit.json：/usr/bin/python3 -I -B NEW/guard.py NEW/runner.py NEW/guard.json，cwd review包根；10.287秒、exit1、未超时。stdout.log/stderr.log/guard.json均原样保留，23断言PASS/4FAIL，3个有效M08失败与1个探针状态名限制，不能换算产品通过数。

前置guard在所有候选/pytest导入前安装，6个sys.audit自检硬拒事件，runtime denials=[]，拒subprocess/socket/fork/exec/spawn/system/sqlite及原counter/ledger。guard后核91source/3tool/223命名依赖pins，显式append已封存已装依赖目录；无site.main/.pth、下载或插件collection。仅本进程threads/pipe/合成文件，无业务OS子进程、模型/GPU/native/网络/服务/browser/用户媒体。原counter仅guard外前后各一次只读，hash acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，inactive/28/240/12.362未变；无写/退款/清零/新counter/13grant复活。counter不变本身不被用来证明所有历史动作。

M04 CLOSED：合法明示外部依赖锚仍经真实WorkerContext.dependency_manifest读取；父symlink即使同叶同hash被拒。独立读中parent/nested祖先替换，真实字节读完后身份复核拒绝；普通RuntimeError和KeyboardInterrupt路径前后fstat身份相同，FD无新增。代码从文件系统根逐级NOFOLLOW打开外锚与各层，以实际fd的fstat记录身份；读取后核链，finally释放。bounded-exact实际读16，over拒绝，FIFO拒绝，仍保持regular/nonblock。只按实际返回bytes合计≤limit+1作断言，没有用read请求参数合计充当实际字节。观察/读取不是原子事务，不声称外部路径永久安全。证据M04-external-*.json、M04-window-*.json、M04-bounded-*.json。

M06 CLOSED：代码在公开PRECHECK之前绑定root与两级输出链，逐级创建所得fd的fstat身份进入记录并立刻与声明路径核对，之后reservation/summary/receipt复用持有输出fd、每次写前重核。独立PRECHECK之后换root/temp/controller普通目录及root祖先symlink，替代对象零新增文件，summary/receipt均未写且路径null，未创建worker的场景安全处理，修正了上轮两个无效探针的包装器错误。创建返回接缝原始M06-create-race.json记录fd inode2901550与声明路径2901551，产品REFUSED_BEFORE_START、identity-changed、held/replacement都空、路径null；原探针错把合法拒绝状态拼成REFUSED，所以assertion FAIL。这是探针oracle限制，不是产品缺陷；M06-create-race-adjudication.json只静态裁决既存原始证据，未修改/补跑。正常正例、排他reservation重入零spawn且旧产物hash不变通过。保证止于写前观察边界，不承诺多操作原子或路径永久不变。

M08 OPEN，Major 1，以下同一终态异常收口缺口集中计数：

- 位置run终态2449–2478与_record_disk_actions 2181起。令本次新增disk observer普通RuntimeError，预期UNKNOWN+非空结构化stdout、保留真实summary、释放anchors；实际main exit5、stdout空、receipt=null，stderr S3_CONTROLLER_REFUSED EXCEPTION RuntimeError，已存在reservation和summary但无终态receipt。anchors确已释放、线程结束，不能据此忽略结构化结果丢失。M08-disk-observer.json。
- 位置run 2449–2455、_finish 2527–2588。在真实_finish已经seam.close后，让第二次_fd_snapshot抛RuntimeError，预期清理观察未知并结构化UNKNOWN；实际exit0/SUMMARY_PERSISTED/receipt_persisted=true，cleanup_failures仅FINISH:RuntimeError，PRE_RELEASE fd_cleanup缺失，未降UNKNOWN。这里无该调用新FD，后续观察正常不能补证前一次未知。M08-close-observer.json。
- 同一catch范围令_finish入口RuntimeError，预期独立生命周期清理并UNKNOWN；实际exit0/SUMMARY_PERSISTED、仅记录FINISH错误，root/output anchors释放但真实pipe FD10仍开（dev15/inode6349487/mode4480），worker线程确实结束。M08-finish.json先记录真实泄漏后仅调用captured controller自己的_release_anchors，未关闭未知FD或GC掩盖。此为受控cleanup方法边界故障，不声称自然正常运行必然抛该异常，也不要求新建清理平台。
- 静态直接相关问题：_record_disk_actions 2196–2204以os.stat当前路径是否regular来决定历史summary_written，OSError被改成false。summary_path只在成功写后设置；观察失败无法否定此前已发生写入。应保留客观写动作，另列当前可见性unknown，不能伪称未写。本点未追加动态测试，也不另计Major。

M08已修复部分：direct persist单RuntimeError现在exit4/UNKNOWN/receipt_persisted=false，secondary明确，真实summary及disk_actions.summary_written=true保留；双失败primary ValueError与secondary RuntimeError分开。终态persist KeyboardInterrupt/SystemExit继续传播，自有root/output anchors无遗留，worker线程结束；重复release未关闭探针自有外来FD。新增POST_RELEASE observer RuntimeError现在返回UNKNOWN、fd_leaked=null，磁盘PRE_RELEASE receipt仍保持SUMMARY_PERSISTED且无事后诊断字段，未重写旧磁盘receipt；返回persisted_receipt_state如实区分磁盘与返回状态。上述修复不足以关闭剩余终态窗口。

FD/线程边界：M08-finish后留下真实FD10，批次cleanup.json最终仍有同一dev/inode pipe，仅MainThread；其他后续case把该已存在FD作为自己的baseline，不能声称本批零遗留，也不能把它算成后续case新泄漏。没有关闭未知FD、没做GC/高FD忽略/空集替代。受guard批次进程最终正常以exit1退出，内核回收该进程FD；这不替代产品返回时清理证明。指定FDsnapshot修复仍保留：本轮真实自有文件fd可检出、关闭后消失；PRE_RELEASE/POST_RELEASE分离保留。原历史FD8身份仍UNKNOWN，不能拿本轮FD10证明旧FD8身份。

meta01 CLOSED：当前作者candidate与原meta01-oracle的7个frozen owner逐项一致且hash匹配：quality_phase、coordinator、runtime_binding、stage_runtime、budget_authority、local_program_authority、v0_s2_runtime；changed_sources另列本轮四源，未混淆。meta01-oracle.json保留核对。

m03 CLOSED：NEW作者报告如实统一历史3次ACK/3次尝试：attempt01 0collection/0call、pytest import失败；attempt02 19call/18PASS1FAIL；attempt03 21call/21PASS。无待ACK尾句；原FD8 UNKNOWN，枚举产生幻影只作为可能性事实，未认领具体身份。历史02/03相对argv与ACK绝对argv字符串不同，但同cwd解析目标、pins/nodeids一致，报告不再称逐字相同。本轮作者03使用root唯一修订runner，精确绝对argv/35节点与ACK相符；只静态核交付证据，没有重跑作者节点。P01保持关闭，不推导未知全局历史零动作。

必要兼容：positive通过真实16行QualityPhase/worker协议pipe/parent reader/canonical/manifest/provenance链，原件hash逐项匹配。A03 output_contract/A05 no_overwrite/A09 resource_budget正式收据仍BLOCKED，composition_facts不填正式键，summary产品PASS=0。M05原loader/封存窗口仍拒绝磁盘变化，未绕原loader。native默认拒绝确实留下空temp/s3-production-controller目录，零reservation/summary/receipt/零spawn；这是本包PRECHECK要求，不报告完全零文件系统写，也不据此重开M02或质量门槛。M01/M02/M03/M05/M07/M09/m01/m02及指定FDsnapshot/P01不全量重开；本轮_cleanup异常保留在原开放M08。

archive只读验证：旧独审zip hash7524b3c1…、3282成员逐项匹配index；作者synthetic zip hashb73e653c…匹配delivery，实际2878 ZIP成员。作者index仅提供entries=3504和aggregate hash，无逐成员清单，不能从此数字证明完整性或证明丢了626个文件；将声明数字/实际成员数并列记录在archive-index-comparison.json，作者原始合成目录范围与ZIP成员计数口径未独立证明。所有成员只读哈希/类型验证，无解压、无执行、无跟随其中symlink；不运行链接工件。

固定I24、产品12、真实native、Windows/A06、原ledger、质量、人工签署均未在本审证明，不签StagePASS。下一责任人为root据此退回M08集中修复；不得改旧summary/receipt伪造事后观察，不缩减分母或复活grant。

停止十字段：当前坐标R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION；本批完成独立27case一次及集中裁决；最后通过门禁仍唯一control既有统一切片；当前阻塞为M08终态异常与正式产品义务未证；全局路线位置S3生产组合离线纠偏；剩余M08及固定产品验证；下一责任人root→实现owner→独审；所需授权本批ACK已执行，无新增人批请求；证据本NEW目录；精确停止原因本批完成CHANGES_REQUIRED、禁止补跑。

V0–V3完整大纲（control完成子项/总子项）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
