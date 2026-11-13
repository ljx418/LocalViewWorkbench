# 生产组合纠偏01独立审查

结论：**CHANGES_REQUIRED**。精确候选 `7dc76ffeec685959f5906c612e58f7e1fc081425`，基准 `7c27a11111ede5bb2eb449211f5450270d884ee3`。原11项中 **6 closed / 5 open**：M01/M02/M03/M09/m01/m02关闭，M04/M05/M06/M07/M08开放。有效发现 **Fatal0 / Major6 / Minor1**，其中代码Major5、执行范围/事实陈述Major1、报告计数Minor1。审查完成不等于候选接纳。

## 1. 身份、授权与源归属

独立实例 task_a5e256548dbb / ctx_c19250e625b5，在 `lvw-v1-d0-review` 单独工作，未派生Agent。读取root AGENTS/governance/parallel/control、contract、root-decision、原F0M9m2、原集中/纠正/score探针、完整归档及新received；root新增容量26规则也读取。采用root三项已批准裁决：root可提交封存；controller/worker/command builder要求内部hash；根内排他terminal receipt允许。不请求重复人批。

先保存HEAD/status/index原bytes及暂存/未暂存binary diff。90个前轮物化源逐hash与前轮source-materialization及7c27 git blob三方一致，未知源差异0；随后只从7dc76 git blob物化6必要源，helper此前不存在。90既有源目前全部与7dc76一致，另验证6源intake哈希及7 frozen源。supervisor删除build_production_command后的AST与基准相等，监督协议/caps未改。CMD CRLF例外继承原记录，未物化、未执行。没有checkout/reset/clean、源修复、源stage或commit。

证据：initial-state.json、initial-index.bin、prior-source-ownership.json、source-materialization.json、candidate-source-comparison.json、frozen-sources.json、supervisor-unchanged-protocol.json、cmd-exception-inherited.json。

归档独立清点4588 ZIP entries，其中4547 regular、41 symlink；本地4547 regular逐hash一致、41 symlink payload一致。用户原4546历史描述保留，不据计数重写旧证据。新raw/input摘要见input-integrity.json及review-archive-integrity.json。

## 2. 运行边界和计数

每次候选import前安装本审独立audit hook，禁subprocess/socket/fork/exec/system/sqlite3.connect和counter/原ledger open；子测试猴补无法移除audit hook。guard自检8种禁止事件全部被拒；候选运行5个guard进程的denials均为空。只使用本进程threads、pipe、受控mkfifo及NEW目录内合成文件；FIFO由控制方删除，失败工件/partial保留。没有fixture业务子进程、网络、模型、GPU、服务、下载、用户媒体或原ledger动作。外层启动guard Python是测试解释器，不充作fixture证据。

**71 unique collected nodes / 71 call invocations**：68本审自写节点、3必要旧worker/command兼容节点；68 assertion PASS、3 assertion FAIL。初批51=48PASS3FAIL；补边界14PASS；最后入口4PASS；完整诊断链1PASS；parse/seal消费窗口1PASS。没有重跑作者60或旧123/84/13/41/186/257全量。用例PASS包含缺陷复现成立，不等于修复闭合。

初批2个M04失败来自Oracle过严：累计read请求18不代表实际取回18；修正探针测量actual returned=16，exact成功、读中元数据变更拒绝。第3个M06普通目录对象替换失败是有效产品缺陷，独立补例再次确认。另一次补批runner因pytest hook参数名错误在collection前失败；原stderr/runner版本保留，修正runner另名日志，不覆盖失败。初始`python`不可用exit127无写入，随后使用python3。完整测试argv/cwd/exit/stdout/stderr及各guard收据见commands.json；统计与Oracle更正见execution-accounting.json。

原counter仅外层读取摘要，前后hash仍 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`，inactive / 28 starts / 240 reserved / 12.362 spent；不改、不退款、不新建counter、不恢复旧grant、不重跑13。

## 3. 正式正例及一次汇总的11项闭环

正例由正式controller.main接受独立计算controller hash，经固定worker command携预封存worker hash，真实worker.main/QualityPhase执行16行，真实pipe/parent reader读66 messages，canonical/sourceplan/raw由原ParentOriginalEvidence封存及manifest重核，真实aggregate owner生成12键，root内O_EXCL reservation/summary/receipt落盘。独立逐hash比原件与manifest，controller/worker provenance各自等于真实context bytes；16合成PASS、12产品键0PASS；cleanup未证，root/reservation保留。证据positive.json、positive-oracle.json；这只证明无竞争正例能走通，不抹掉下面边界失败。

下表与closure.json集中列位置、触发、预期/实际Oracle、终态/清理，避免逐项回改候选。

| 项 | 裁定 | 定向触发、独立Oracle及实际 | 终态/清理及证据 |
|---|---|---|---|
| M01 | closed | controller:384；JSON PROVEN按type/value接受；1/字符串true不能当bool；形状不等于授权 | 0spawn；M01.json |
| M02 | closed | 默认controller.main及worker.main均拒NATIVE_EXECUTION_BACKEND_NOT_READY；**七项形状诊断全部verified、无其他拒因**的完整自写链仍accepted=false，正式入口0spawn/0driver | REFUSED；未建/读ledger；M02-all-seven-diagnostic-proofs.json、M02-default-controller-main.json、M02.json |
| M03 | closed | controller:1126/worker:142/supervisor:1141；缺/错controller hash拒绝；二次load前driver_arguments/source/projection漂移均拒；固定同一seal下传；两context真hash各自匹配 | UNKNOWN无summary，FD/worker清；tracked-callers.txt及M03-*.json；所有活动仓库调用方已登记，旧归档不迁改 |
| M04 | **open** | actual worker引用走_read_sealed→read_bounded_regular，只叶nofollow；把父目录换成指向owned-outside的symlink，projection/source/budget/binding/dependency五者全接受。有限limit+1、regular、FIFO/device、叶链接及真正root-relative祖先拒绝已有效，但未接入实际引用锚点 | 读取成功；FD无差、FIFO已控制回收；M04-actual-worker-*.json及read-oracle-*.json |
| M05 | **open** | controller:1287先解析、1307后读bytes；真实解析后改canonical为15PASS1FAIL，旧解析仍16PASS，后续manifest全部重核新bytes，却内部quality_16_rows PASS/provenance新hash | exit0 SUMMARY_PERSISTED；M05-parse-seal-drift.json。ORIGINALS_VERIFIED及RECEIPTS_BOUND后raw/canonical/sourceplan/root等10例已UNKNOWN拒绝；不扩大承诺到最后观察以后或多文件原子快照 |
| M06 | **open** | controller:1172每次按路径重新open root，未保持root/祖先/输出目录inode。替换普通controller目录仍summary+receipt；替换root/temp仍receipt；换root父目录链接则receipt写外部owned-external；PRECHECK换root预约写新root | partial/旧根均保留；线程FD清；M06-root-ancestor-link.json、M06-object-*.json、M06-reservation-PRECHECK.json。叶/内层symlink拒绝不能代替对象身份绑定 |
| M07 | **open** | controller:1462/1470/1486；真实首行release/residue/provider失败和末行15PASS1FAIL如今使三收据非PASS，cleanup保持未证；但成功合成例仍用窄artifact/call-count义务给正式A03/A05/A09同名收据PASS | root/reservation诚实保留；M07-*.json。正式四输出/切换0推理、人工稿异常保护、GPU/RAM/热冷/P95/0OOM未证；顶层BLOCKED/离线标签不足以补齐内部义务 |
| M08 | **open** | controller:1866 finally中的_persist_receipt只捕两类异常。受控RuntimeError存储异常先进入UNKNOWN，再在terminal持久化逃逸，exit5/stdout空/仅泛化EXCEPTION，未明确返回未持久化状态 | M08-unexpected-persistence.json；本次无FD/thread泄漏。普通bind/verify、删除canonical均持久UNKNOWN，OSError落盘失败显式未证，KeyboardInterrupt/SystemExit不吞，这些关闭分支见M08-*.json |
| M09 | closed | controller:1192；已有summary/reservation均0send保原bytes；双线程precheck barrier同步争抢只有一个supervise/send owner | 两竞争线程join；M09-*.json。同一未被替换目录下有效；root/目录替换绕过归M06，不重复关闭全局身份问题 |
| m01 | closed | 协作取消首submit后准确join，submit总1；非合作callback明确UNKNOWN/retained/不可kill/late-write-possible | 产品返回时非合作线程仍活；独审finally释放自己的Event并join，后续callback可恢复不隐瞒；该控制方回收不当产品证明，m01-*.json |
| m02 | closed | worker:337；text/binary流保准确WorkerError/默认native拒绝，不被TypeError覆盖 | exit2准确code，m02-*.json及M02.json |

## 4. 有效发现的范围

全部severity/location/trigger/expected/actual/oracle/终态与复现脚本集中在findings.json。五个代码Major均阻止本包全部关闭：M04引用锚点；M05解析与最后同源bytes；M06输出身份；M07完整义务；M08终态异常兜底。M05受控写的是本审合成canonical，不是声称产品曾真实执行FAIL后又篡改；它证明该消费窗口可产生矛盾判定。

M07不抹掉已修复的失败分支：15PASS1FAIL等真正不再被无条件PASS；但formal plans/acceptance_cases A03要求四视图/JSON/TXT和切换0额外推理，A05要求已有稿下非法JSON/超时/OOM/未答保护且可导出，A09要求目标机资源/性能完整矩阵。当前把“16行有raw+suggestion”“artifact独占写”“reserved<=capacity”分别定义成同名PASS义务，是事实子集，不是已批准降低正式义务。应另列合成事实、未证正式收据BLOCKED/NOT_RUN；无需为关闭native空缺跑模型或原ledger。

## 5. 额外兼容批次：单独的Major P01与Minor元数据

只读作者compat-regression与源码，没有重跑四批。其实际argv是直接python -m pytest，未套前置auditguard。日志142PASS14SKIP / 341PASS / 17PASS / 94PASS属额外回归，不能计本包所需证明。

supervisor的13枚举fixture有machine binding skip门，实际被skip；另一个skip为特定生产runner入口。**budget/runtime没有同样门**。budget17PASS含真实SQLite Fixture及test_real_subprocess_debit_and_exact_cap：8成功+1超额调用，program_budget._exchange实际Popen；runtime94PASS含test_correction02_factory_admission_and_owned_helper，明确调未mock _exchange并断言真实helper exit/reap/readers/pipe。因此至少10个真实业务shim/helper子进程及合成SQLite事务已有源码+通过日志证据；不是把外层pytest/guard解释器算fixture，也不伪造整个四批的精确总启动数。

COMPLETE03母授权覆盖范围内CPU验证，故不说这些CPU动作本身全缺人批；但本纠偏包contract明确最小定向/pre-importguard/零OSfixture/SQLite边界，额外四批及实际业务子进程越过本包执行范围。此为**P01 Major（流程/事实范围）**，不是声称新代码曾调真实模型、原ledger或旧13fixture。原counter未变只能证未经该counter累计，不能证无其他业务子进程。无运行时审计，不能据通过日志证明这些额外子进程所有外部行为均零。

**meta01 Minor**：作者报告8 frozen sources，实际candidate数组/root intake/逐hash均7。单列小错，不重写旧报告；本审没有429事件观察，不能由文字推定历史未发生429。

## 6. 清理、完整性和剩余边界

各批FD前后集合一致，终态仅MainThread。非合作线程测试控制方在finally释放/join；输出symlink/旧根/partial/失败原流保留。HEAD/index未改，除6授权物化源和NEW报告以外status不变；旧证据/输入hash未变。完整性清单integrity.json及最终核对final-state.json；不commit，让root按任务回收/归档。

Windows/native/GPU/A06/原ledger/真实质量未证，可信native backend缺失是已批准明确空缺，不是要求新增真实验证；固定I01–I24、产品12、StagePASS、人签均不签。当前5个代码Major及流程Major一次汇总交root裁决，没有在独审实例修源或逐项返工。

## 7. 停止十字段与完整大纲

| 字段 | 本次状态 |
|---|---|
| 当前坐标 | root control：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING；产品完整R1仍未完成 |
| 本批完成 | 独立定向复算、源/证据完整性、11项closed/open与所有有效发现一次汇总 |
| 最后通过门禁 | 仅本批无竞争合成正式链及已关闭六项定向证据；不新增Stage产品门禁 |
| 当前阻塞门禁 | S3_P4_COMPOSITION_ADMISSION_SEALS_IO_FAILURE_AND_REENTRY；本候选CHANGES_REQUIRED |
| 全局路线位置 | 既有统一媒体早期切片已签；当前S3接线准备不补完整R1/旧S2人签 |
| 剩余工作 | root集中裁决五个代码Major、P01范围事实及meta01；再冻结所需最小纠偏，不在本实例修复 |
| 下一责任人 | root协调/裁决，独立审查实例只归档报告 |
| 所需授权 | 本次既有授权足够，无待人批；未要求模型/ledger补验 |
| 证据目录 | reports/v0-s3/product-gate0/independent-production-composition-correction-01/ |
| 精确停止原因 | 已完成独审，候选仍5项原缺陷开放；一次worker_done后由root回收 |

root control完整development_outline：V0 S0 **1/2**、S1 **5/5**、S2 **7/8**、S3 **0/6**；V1前置R0 **1/2**、R1a **5/5**，D0离线准备另 **2/2**；V1 R1 **0/4**（统一早期切片另 **3/3已签**）、M1 **0/3**、R2 **0/4**；V2 R3/R4各 **0/4**，未来V2设计不激活业务；V3 R5a/R5b/R5c各 **0/4**。实现/机器/独审/人签分别读取root-control-read.json，未改变任何正式计数。

容量只读观察：本项目root工作区1、review工作区1、implementation无存活窗口；本次派生0/回收0。保留本审终端只为提交这一次worker_done，之后由root按实际退出收据回收；任务完成不是进程退出证明，未保留keep-open。
