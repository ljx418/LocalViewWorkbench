# N1 correction03+04 独立静态审查

结论：**CHANGES_REQUIRED；Fatal 0 / Major 6 / Minor 0**。8个原开放项逐项裁决：M03/M05/M06/M07/M08/M09仍开放，M04/M11在本次冻结源码范围关闭；M01/M02/M10/m01兼容检查保持关闭。Major按原义务合并根因，不把下面子缺口另计数量。真实Windows/native仍NOT_PROVEN，静态正确性缺陷独立成立。

候选 `d751bced75cdc1d21cee072892860a7c4f8ac542`，证据commit `bc1a27d9d18faedc15797d3153cd0fe8a4cb3d8a`，四个允许源逐Git blob相等。独立读取冻结规范、源码、原JSON/zip，未继承实现者结论，无Agent。本次选择任务明确允许的“静态实锤后集中报告”路径：**候选import/pytest/collection/动态probe均0次**，没有执行原实现库脚本，没有申请或消费新动态ACK；下述复现均为可逐语句核对的生产调用路径/线程交错，不伪装运行收据。

## 身份与完整性

本工作区HEAD `204e585f81837d9743869b94030ae941b2d52be4`，原三N1文件均准确等于历史候选37d938b字节，第四回归源原不存在。已保存 workspace-before.json、tracked-before.patch、index-before.patch、原三源字节和全部tools现有源码hash。没有物化覆盖tools源码，四个候选blob仅保存在NEW报告目录供审查；没有reset/clean/checkout/add/commit。index与既有改动不改。只写本NEW目录。

sourcepins-audit.json核18个pins中17个产品包文件的候选blob全部匹配；其中10个既有产品owner在本工作区逐字相等，两个作者报告guard/runner本工作区本就不存在、未补写，四候选源与既有历史源明确区分。解释器pin另在stdlib核。批准的open_lvw_browser.cmd保留SHA256 `f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04`，规范化LF与候选相等。没有其他已核owner漂移。authority-hashes.json记录root规范/控制/原审查/本次intake身份，candidate-binding.json和static-source-audit.json记录blob与AST。

候选SHA256：custody `fee267aed425bcb5c96dcc77609766d01ca1c6ef66f173157de8249502468c39`；broker `627e829d6f4862f4dc098a0b83d6ff9d26a28813e6eb4b11e921593d86f54b36`；test `348aa4ba2775de54a102cd19237642572a1eba118a4bd6aeea0b8b84f38ba4b7`；regressions `eb4decc7c773628f6ce5995345f9f2c7998e21d7f7d9acd8fdec5623d6595947`。

下文行号均指NEW目录candidate-v0_s3_native_custody.py（C）与candidate-v0_s3_native_broker.py（B），与原候选tools行号一致。static-excerpts-*.txt逐行保留原文；它们及四个完整blob是本次静态缺陷的原始证据。未通过修候选后签通过。

## M03 — 部分创建普通失败修好process/thread表，但NUL失败仍无owner，取消会打断独立finalizer

**Major，仍开放。位置 B809–925、926–973。**

已改善：CreateProcess成功后B861–865即登记原process/thread；birth失败保留primary；普通Delete异常不会跳过NUL、birth和process清理；Wait结果区分exited/exit_not_confirmed；CloseHandle失败的process/thread留WindowsApi表，可通过release_retained到达。这些源码事实足以确认原birth+双Close失败主路径有实质修复，不以旧20FAIL否定它。

仍有确定路径：CreateFileW成功取得NUL后，从未对null调用_retain。令NUL CloseHandle普通失败，_close_quietly返回False，B887–895只是产生cleanup_error；最后释放process/thread，抛BROKER_NULL_DEVICE_CLOSE_FAILED。**返回时NUL仍打开，唯一引用只在已退栈局部null，retained_handles没有NUL，Core也没接收它**。预期每个未确认关闭原句柄有持久owner与恢复入口，错误字符串不能替代。可复现原语：CreateFileW→有效handle，CreateProcessW→成功，GetProcessTimes→成功，CloseHandle(null)→False，其余close→True；逐读B809–925即可确定结果，无真实API调用。

取消缺口：DeleteProcThreadAttributeList抛KeyboardInterrupt/SystemExit时B880仅except Exception，跳过紧随的NUL关闭，外层B896捕获后才继续birth/process释放，NUL仍失主；_release_created中TerminateProcess或Wait取消也不在except Exception内，会跳过剩余原process/thread独立关闭并可能覆盖原birth主错。预期取消完成全部安全清理后传播，主次错误并存；实际process/thread虽可能留表，独立清理没有全执行。此处明确区分“留表”与“完成清理”。

## M04 — Job长度/双计数/17边界

**关闭（静态组件范围）。位置 B694–771，C113。**

独立代入：header=8，capacity=18，64位allocated=152；reported<8或>allocated拒，assigned!=listed拒，listed>17拒，needed=8+listed*pointer_size>reported拒。因此0/0/0、1/1/0、0/1/16、超allocated、17截短、18完整都失败；0/0/8合法空、17/17/144合法完整。内联数组offset=8/pointer_size，未解引用外来指针，Core还独立核17。32位同式按pointer_size得正确offset。异常不是空列表。未执行Win32，关闭的是原检查漏洞，非Windows实测能力。

## M05 — Job保留已修，CreatePipe继承位失败仍丢两端

**Major，仍开放。位置 B1035–1060、1501–1537、1979–1994。**

Job limits失败后的job/pending/retained保留，以及成功关闭才job=None已修；原真实reader同owner引用仍在。阻断由另一冻结的pipe/API保留义务成立：CreatePipe成功后SetHandleInformation失败，两端只在局部read/write，调用两次_close_quietly后抛BROKER_PIPE_INHERIT_FAILED。若任一CloseHandle失败，该原HANDLE未加入WindowsApi._retained，Core尚未获得返回pair、pending从未登记。返回时资源仍开、原owner不可达，只有cleanup文本。预期失败两端分别保留并可真实恢复。最小原语负例为CreatePipe→两个有效handle、SetHandleInformation→False、CloseHandle(read)→False、CloseHandle(write)→True。与M03同属创建接管问题但对应原M05 pipe义务，不按两个handle重复计Major。

## M06 — 顶层step已独立，嵌套finalizer和取消仍不完整

**Major，仍开放。位置 B1707–1741、1743–1786、1821–1890、1913–1945。**

改进确认：stop顶层diagnostic/terminate/wait/readers/query/records/job/pending各自step保护，普通TerminateJob或诊断失败不会阻断后续整个stage，primary单独保存，_released只取_is_released，Loop写READY/STATUS/STOPPED异常的finally仍调用_ensure_stopped。这些不是只看测试名得出的结论。

剩余取消路径：让win32.close_handle在Core.stop的release_records内抛KeyboardInterrupt，_close_handle B1734捕获BaseException只append并return False，外层step看不到取消、primary仍None，stop返回普通evidence，**取消未在独立清理后传播**。_PendingResources.close_all同样捕获BaseException而不交回取消。预期root correction03 A中的取消清理后传播与首错保留，实际吞掉取消。

嵌套隔离还不完整：_wait_the_processes只except BrokerError，第一条record的wait/exit_code普通RuntimeError使整个wait_processes step退出，后续原process不再等待。更严重的reader负例是_start_reader已append/transfer后Thread.start在未实际启动前抛错；_close_readers对这个未启动reader先finished.wait再reader.join，join抛RuntimeError，跳过其后所有reader状态/接管检查；随后_close_pending不核owner而逐项CloseHandle，可能关闭后续仍alive reader使用的原read handle。预期每个可安全执行finalizer仍执行，不在活reader下关句柄；实际整个reader列表由一个guard包裹。保留原引用和UNKNOWN不能代替完成可执行清理。这一组合与M07启动失败有关，按原清理义务归M06，不另外计数。

## M07 — 启动保护范围扩大，但未返回/抛错的Thread.start与launcher保留仍不闭合

**Major，仍开放。位置 C1118–1150、1179–1214、1233–1289、1324–1431；B2858–2881、3666–3713。**

身份getattr、pump构造、pump.start、heartbeat构造/start现在都在start大try内；普通错结构化，原peer尝试关闭；心跳stop Event只构造一次，回调不等待closer，解决旧的直接循环等待。该改进确认。

确定的未返回start交错（不需要改变候选）：Tstart在C1141 thread.start进入后，底层线程尚未真正启动，清理者进入_stop_background；其按_background_starting等到原deadline，记录BACKGROUND_START_PENDING后继续snapshot；heartbeat.ident=None且is_alive=False时C1270直接self._heartbeat=None；pump则join未启动线程报错，外层捕获后仍继续broker.close；尝试FINISHED。随后原Thread.start真正启动并返回，finally只减计数，不重新检查_background_open，也不把被清掉引用重新登记。**清理结束后可以出现晚启heartbeat且session原引用已丢**；若是pump晚启，还可在已关闭peer上执行read。预期未知的启动中线程始终保留原owner、deadline后只能收口，不能把未启动视为已结束。

start已实际启动线程后再抛错的负例：C1145 started仅在start正常返回才True，finally在False时无条件清掉self._pump/_heartbeat，即便原线程实际alive。异常返回时原线程可能仅由threading全局表持有，不是会话原owner。合同明确要求start抛错也不能丢实际原引用；没有把一般正常Thread.start失败都推断成已经启动，而是明确区分这两类触发。

closer构造在C1197位于try外：构造抛错会留下_closer_started=True，NOT_STARTED且close_done未通知；后续_start_bounded_close拒绝重试。start抛错在except中仅当IN_PROGRESS且_close_owner is None才设FINISHED/close_done，但实际IN_PROGRESS设置总同时设_owner，常规“未成功启动closer”时还是NOT_STARTED，故这个通知条件不能覆盖它。callback外层还吞掉该异常。预期失败有明确终态通知并保留可恢复原broker；实际需另一个外部stop偶然接管，回调路径自身未完成承诺。

launcher部分失败只用_terminate_and_close_process局部善后：terminate/wait/pipe.close失败全部吞，原Popen未交Session亦无retained owner；Windows原process HANDLE未显式释放。_adopt只保护channel_factory，BrokerProcess构造在try外；StreamChannel构造后半段失败可能已有endpoint/线程。FakeProcess成功wait不能证明失败资源有持久owner。预期这些已取得资源在任何handover失败下仍有持久owner与事实。无真实Popen启动。

## M08 — 启动deadline仍只包整段；清理唯一性、取消与双向预算存在竞态

**Major，仍开放。**

1. **启动动作内部没有前/后核。B1540–1664、3251–3287。** _guarded_startup只在action()完成后看deadline，action分别是整个arm/launch。_launch_role没有任何deadline检查。令第一role的create_process_suspended阻塞到租约后才返回，生产控制流必然继续close write ends→登记process→assign→Resume→启动readers→继续其余roles，直到全部core.launch返回才检查到期。监督线程超期虽保留_startup_in_flight，**并没有取消标记被Core读取，不能阻止原后台owner晚到Resume或创建后续角色**。连“进入_run_startup前已到期”也先owner.start(action)，后await_result才查到期，启动副作用先发生。R07仅让create_job跨期，未证明role create/assign/resume跨期；不能把它关闭全义务。

2. **cleanup deadline初始化非原子。C1304–1321在_close_lock之前调用；B1432–1451也无锁。** 两线程都观察None；A算1005暂停写入，B算1006并写入且开始清理，A后写1005，或反向写导致最终从1005变1006。两个调用者可使用不同局部deadline，已开始owner的期限可能晚于第一次stop+5。不是GIL能保护的一个原子操作，分支跨多个Python调用和赋值。预期第一次入口唯一发布且后续只沿用，实际重复生成/后写延长均可达。无需新测试观察才可判定缺少互斥。

3. **即使无竞态仍多层超期。B1761–1767用同一个wait先finished.wait再join，不在两次之间重算；剩余1s时可分别耗1s。B3281在startup deadline耗尽后还固定settle(1s)，没有共用已耗尽cleanup截止；B937和release_retained B646固定Wait_MILLISECONDS，无deadline参数。Session C943–948的_send也不显式取_cleanup_deadline最小值；真实BrokerProcess会通过已绑定channel收紧，但Session的deadline-aware接口契约本身无法证明所有peer遵守不同参数中的更短值。这里主要阻断是前述生产固定等待和并发初始化，不把可由真实channel收紧的局部参数单独夸大成实测突破。

4. **Windows绑定期限不作用于已开始_await。B2713–2727只读方法局部deadline，read/write直接传入原参数。** 典型StreamChannel启动_drain时传None，后bind_deadline仅改endpoint._deadline；正在_await不会调用_effective_deadline重读。cancel之前可无界wait_done循环；取消携None进request_cancel时NOT_FOUND且done/stopped都False也无绝对终点。worker._start还在注册_reader/_writer之前固定wait_ready(CLOSE_JOIN_SECONDS)，start/wait失败无持久endpoint登记。queue.put变短有界，handle获取失败拒submit，这两项改善不足以关闭完整取消义务。

5. **worker退出与资源恢复不足。** request_cancel设_cancelled但不设_stop_event，正常cancel后worker可继续空等、join必超期；NOT_FOUND的done是上一请求可见事件而非本代证明，submit的_cancelled未拒入队，cancel与IN_IO之间没有同一锁。_write_block确实循环partial写，StreamChannel核非None写数，但partial loop无cancel/deadline核；工作线程句柄在run finally内关闭，close失败只留worker.error，endpoint只看join成功即可关file报closed，不要求thread_handle_released。retain文本不代替同owner恢复。

6. **UNKNOWN与晚到状态并非原子闩锁。C1152–1177。** Tmain在_apply_state通过if（当时RUNNING），Tcallback写UNKNOWN并开始close，然后Tmain执行self.state='RUNNING'。这是两步check-then-set，没有共用锁或独立单向latch。_stopping可能已True但_apply_state不查它。预期UNKNOWN不能被晚到READY/STATUS覆盖，实际可被覆盖；R11只顺序检查UNKNOWN，无该交错。

7. **序列发送已移入_write_lock，但双向计数不在共同锁。C939–947与C1023–1036。** pump _decode_reply在锁外check+increment，发送侧在_write_lock内check+increment，二者可在总数1015且reserved8时同时通过各自+1检查，累计变1017、加预留=1025。另终态接收始终默认reserve8，STOPPED不能消费终态预留：总数1016时发送terminal STOP允许变1017，但收到终态时1017+8+1>1024而拒绝；broker STOP接收也默认reserve8。预期双向总量原子且预留真正供终态使用。不能只看C encode序列修复就把总预算也视为原子。

已改善并独立确认：心跳常量60/缺失120保留，lease后不发心跳，STOP阻断后续STATUS；错误回调主动UNKNOWN+独立closer；32KiB无换行buffer每次append核上界并仅留one-over，partial EOF具名；队满重试核cancel/deadline；partial WriteFile循环。这些关闭相应旧子路径，仍不覆盖上述剩余安全缺口。

## M09 — FINISHED锁死保留资源恢复；Windows端先置closed且外层可在活worker下关闭原file

**Major，仍开放。位置 C1542–1571、1606–1641、1654–1686；B2775–2817、3536–3626。**

确定的同owner恢复反例：t=1000首次Session._close_broker，peer.close只因暂时关闭失败返回process_handle_released=False，其他事实True；_perform_close保留同一个peer，_finish_close标FINISHED。t=1001原deadline1005内资源已可关闭，调用同Session.stop/_close_broker：_stopped路径仅_await_close，后者FINISHED立即return；直接_close_broker也FINISHED立即return。**原peer在引用上可见，但产品没有同owner协调恢复入口**。预期只有确认成功的资源不重关，未确认资源在原期限可继续收口；实际把“尝试结束”当“永不可再尝试”。R14反而断言failed peer第二次close次数不增，把这种不可恢复当幂等成功故事。直接测试调用peer.close不是Session产品恢复入口。

Windows endpoint B2789先_closed=True，再发现live worker或_file.close失败后return False；第二次close走already_closed分支永不再尝试，_retained列表也不消退。原期限内worker后来停止仍不能关原file。Posix失败才不置_closed已修；但已成功closed再次调用会将事实closed改False，故一端成功另一端失败的真实channel重试也会破坏成功事实。

BrokerProcess更直接绕过endpoint的保护：channel.close报告reader/worker仍alive而不关read端后，B3599/B3619仍直接self._process.stdin.close与stdout.close；真实StreamChannel端点的_file正是这两个同一对象。**产品close返回前可在实际活I/O worker下关闭原file**，即便Session后来保留broker，违规关闭已经发生。channel_closed先置True仅表示方法返回；write_end_closed/read_end_closed未列入Session REQUIRED_CLOSE_FACTS，不完整endpoint事实也可能被漏检。

缺失reader事实仍被接受：REQUIRED_CLOSE_FACTS只有channel_closed/process_exited/process_handle_released三项；READER_CLOSE_FACTS仅“若key存在则必须True”，broker.reader_finished=None也不拒。仅三项True可使C1641 self.broker=None，R14正例刻意只提供这三项，**不能证明reader已停**。真实BrokerProcess字段较全不能为这个父接口宽松判断免责，且真实close的endpoint事实又未作为required检查。

close_done在_finish_close中设置时closer尚未返回，evidence同时正确暴露closer_alive，但stop/_await_close不join closer即可返回；不能把close_finished=True当真实closer退出。若_background_starting已超期、还有原线程或句柄未确认，FINISHED让它们失去产品恢复路径。预期完整facts与真实线程状态/可达恢复分别成立。没有把短暂closer尾声本身单独计成Major，它与上述实际保留资源不可恢复一起裁决。

## M11 — 默认nonce/平台拒绝

**关闭（静态范围）。C862–876、1358–1374、1435–1453；B3716起launch_broker。** 默认os.urandom(16).hex为32小写hex，非法nonce构造前拒，default launcher在非Windows用BROKER_PLATFORM_UNSUPPORTED；Session捕获普通launch错误提取原code并返回UNKNOWN结构化evidence，只有KI/SystemExit进入清理后传播路径。R15此次有wall=lambda:1000与有效100000租约，确实可到default launcher，不重复旧expired探针错误。此处未做候选运行，按源码可闭合原映射漏洞，无平台功能主张。

## 已关闭项兼容与16组冻结义务

M01目录完整fullmatch/单段/长度64/设备名拒绝保持，LaunchPlan深拷贝canonical与MappingProxyType/tuple保持（m01），M02 Windows types namespace/table与显式原语声明保持，M10 sampler private-pids独立token及原sampler parser未改。原文档m02 pending/_start_reader描述现已改为handover仅改owner，关闭该非阻断文档项。上述是本候选静态兼容检查，不迁移旧41运行成功行。

| 冻结组 | 本次裁决 |
|---|---|
| R01/R02 | process/thread birth普通错有修复；NUL保留与取消隔离仍不完整（M03） |
| R03 | 完整长度/双计数/17及截断检查闭合（M04） |
| R04 | Job保留已闭合；pipe/API原owner义务还开放（M05） |
| R05 | 顶层finalizer有修复，嵌套异常/取消传播仍开放（M06） |
| R06 | 保护范围扩大，start未返回/抛错/closer/launcher残留仍开放（M07） |
| R07 | 整段后核不能禁止late role Resume/后续create（M08） |
| R08 | 单线程BrokerProcess两wait重算已修，唯一deadline/reader/API层仍开放（M08） |
| R09/R10 | partial循环/队满/handle失败局部修复；绑定中途期限、取消、原worker HANDLE事实仍开放（M08/M09） |
| R11 | 回调主动close且无直接互等；UNKNOWN原子性/启动交错未闭合（M08） |
| R12 | 双向公式有修复；并发check/commit和终态预留未闭合（M08） |
| R13 | buffer/partialEOF/队满检查闭合；Windows已进行read的deadline另归M08 |
| R14 | None/false留peer有修复，但required reader与同owner恢复不闭合（M09） |
| R15 | 原code结构化与有效时钟default路径闭合（M11） |
| R16 | 已关闭项兼容保留，真实reader被保留属正例；测试直接_close_readers属于测试owner salvage，不能证明Session恢复 |

测试覆盖的具体限制：R06替换_start_heartbeat为立即throw，未触发真实Thread.start前/中/后交错；并发close case先等第一owner进peer.close再启动竞争者，deadline早已初始化，故不会探测并发第一次初始化。只覆盖pump失败在heartbeat构造前，不覆盖构造中/start未返回/启动后抛错、closer构造/start失败。R11用外部主线程调用_heartbeat_step，等待peer.closed_event后检查，没保存_heartbeat_step刚返回时close状态，更没证明回调运行在线程内部时close_done与真实closer退出相等。R14明文接受只有3个facts为complete并将failed close永不重试作为断言；R16 gate.set+reader.join+core._close_readers是真实测试owner salvage，且其最终线程集合只筛pump/heartbeat，漏closer/startup/endpoint worker。作者批级全线程表补充的是批末状态，不能反证这些返回时缺口。没有把作者所有facade测试笼统说成无价值：它们确实直接调用若干生产方法并证明局部行为，但没有触发上面列明Oracle负例。

## 原始证据独立复算

evidence-audit.json：最新all-run-artifacts.zip共25项、CRC正常；冻结plan hash `2aead0638c050840e4e8c3b81011b0403dc8c0b67e24e6d3f2346c13918048cb`。实际selected/collected/call顺序逐一等于133冻结nodeids，133PASS/0FAIL/0SKIP，131功能+2完整性，pytest exit0，13.628911秒。原三命令/ACK/guard读取而不执行；223命名依赖文件当前全部匹配，3tool pins和3stdlib pins全部匹配。

作者guard收据为guard先于candidate/pytest、ctypes仅一次dlopen(None)且窗口在candidate前关闭、runtime_denials空；作者批前后FD0/1/2(dev/inode/mode)逐值相同、FD3枚举EBADF filtered、unknown空；线程均MainThread。外层counter-before/after原JSON逐字相同。**这只是重读作者收据，本次没有再次读取原counter/ledger，没有调用dlopen或候选，更不声称独审新动态清理证明。** 原guard/raw与真实FD身份数据列在audit，无进程退出替代清理。

历史failed-attempt02.zip原133/130PASS3FAIL/exit1/cleanup=false、末尾2heartbeat保留；更早correction-plan-02与原独审zip身份记录，不把旧通过行混入新收据。历史原41=21PASS20FAIL保持其当时限制。本次没有运行作者133或旧41，也没有用作者133替代独立源码裁决。

## 交接与范围

root可据以上原路径一次集中冻结修复；无需先逐项返工或补跑当前已知不合格候选。本审查任务完成，但候选未通过。若另行需要动态复现，必须先冻结本报告所列负例的精确有限plan并经root ACK；本报告没有这种执行许可。所有未关闭资源描述均先列预期产品返回时事实，再区分显式测试owner salvage；本次静态未创建产品资源，因而没有待salvage线程或FD。

不主张StagePASS、真实native/Windows API/Job/父崩溃/I24/产品12/质量/A06/原ledger余额/人工签署；grant_authority仍NOT_VERIFIED/admission=false。无真实业务进程、GPU/模型/服务/socket/sqlite/网络/下载/用户媒体/原账本操作。

十字段：当前坐标=R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION/RUNNING（根control）；本批完成=冻结候选8Major与兼容项独立静态裁决及原始证据复算；最后通过门禁=既有统一切片live15范围；当前阻塞=本候选6Major及后续N2/I24/产品固定门禁；全局路线位置=以下原control大纲；剩余工作=root集中决定修复与后继新候选；下一责任人=root门禁owner/实现owner；所需授权=本次静态已授权、新动态未申请；证据目录=本NEW目录；精确停止原因=CHANGES_REQUIRED审查已完成、无动态批次待运行、worker_done后root归档释放。

完整V0–V3大纲（control真实计数，非工时）：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3(V2)0/4、R4(V2)0/4、R5a(V3)0/4、R5b(V3)0/4、R5c(V3)0/4。实现、自检机器验收、独审、人签不互相替代。

最终完整性：workspace-after.json确认HEAD、index条目、tracked/cached二进制diff全部未变；全部开工前tools源码hash无漂移。root AGENTS相对本地仅增加26条容量/归档规则，已读；本次不派生，完成后交root归档释放。root-control-snapshot.json确认RUNNING及上述完整outline。
