# N1 纠偏02独立审查

结论：**CHANGES_REQUIRED；Fatal 0 / Major 8 / Minor 1（非阻断文档项）**。候选 `37d938b983e53fee829ef1579373a97403f41d0c`，基准 `9352a34cfa8ea9715437b5ffa5d411369dd5548d`。原 M01、M02、M10、m01 关闭；M03–M09、M11 仍开放。以下按原义务合并根因，不把20个Oracle失败计成20个Major。

## 身份、证据与唯一批次

独立完成，无派生Agent。读取本地AGENTS、governance README、control及执行索引，并读root correction02 contract/official-api-references/root-decision、transport裁决、validation01/02实际root plan/ACK/guard/runner/outercounter、原11case probes/receipt/review、最新review02 intake/received。根control快照为 R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING。

自身HEAD `204e585f81837d9743869b94030ae941b2d52be4` 不冒充候选。`before.json` 保存HEAD/index/status和当时源码SHA256；三新增源先逐Git blob确认9352a34，其余源码核候选不变，再仅物化本轮custody/broker/test为37d938b。最终265个tools/lvw/RuntimePatch跟踪文件核Git blob，唯一字节例外是已批准 `tools/open_lvw_browser.cmd` 的CRLF，sha256 `f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04` 原样保留。index/HEAD未变，其他既有源码hash无漂移。无checkout/reset/clean/add/commit，无CMD或产品修复；仅三源授权物化和NEW本报告。

先静态准备，root `msg_fad19996e808` ACK唯一计划 `0011cb5313cc3b13519e1a1317e9d51e8ae9ac5fd1b9daa65ae169727fa7e6f8`，精确三commands/cwd，外层总timeout300s。实际退出码 **0/1/0**，41项 **21 Oracle PASS / 20 Oracle FAIL**，16.392s；原始raw、异常完整traceback、receipt和guard均保留。无重跑、补例、pytest或作者测试导入；无作者117/67/54/32或旧11整套复跑。

guard先装，再核source/tool/原223命名依赖文件/解释器/ctypes __init__/_ctypes扩展pins。仅候选导入前一次 `ctypes.dlopen(None)` 本进程映像初始化，随后窗口CLOSED；其他dlopen、全部dlsym/真实Windows库/API/Job和OS业务进程/socket/sqlite/ledger均拒，运行期denials为空，自检拒8项。guard后显式append依赖目录和包根，无site.main/.pth。本次只用本进程facade、真实Python线程和NEW合成目录；Windows endpoint仅读取实际Python方法，不调用msvcrt构造、不改os.name、不执行Windows API。

批前后真实FD0/1/2的dev/inode/mode相同；枚举临时FD3的EBADF单列filtered，unknown均空；线程前后均MainThread。counter仅guard外前后各一次只读，完整观察相同：`acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive、28/240/12.362，charges相同；不写/退款/清零/新建/复活。

**批次清理与产品返回清理分开**：Core/父会话/Windows worker等在产品返回时保存live HANDLE、引用、线程、state/异常，再由明确的synthetic allocator、session或实际reader owner收尾。最终MainThread不关闭产品缺陷，不能把测试salvage当产品返回已清理。FD完整身份与线程总表仅批前后采样；不是每个case都有一份完整/proc快照，部分case仅产品owner证据或具体线程列表，这是本批记录粒度限制。

## 关闭的义务

| 原项 | 独立依据及结论 |
|---|---|
| M01 | `_require_directory_name`完整fullmatch、<=64、单段、..片段/尾点/空白/设备名拒绝。16个坏值均拒，user/64字符/受控ASCII正例均接受；无mkdir/进程调用。目录逃逸根因关闭。 |
| m01 | `LaunchPlan`深复制canonical，roles递归MappingProxyType/tuple，sealed每次深副本。修改呈现tools路径和原输入data不影响生产role_command或seal摘要；对只读view无写接口。原嵌套别名关闭；未把可信内存中主动重赋整个对象字段夸大为外部攻击面。 |
| M02 | 生产 `_windows_api_types`、`_declare_windows_primitives`、`_WindowsApiTable`实际构造成功，显式namespace消除同名class闭包NameError。真实加载分支调用同一builder/table，非Windows加载明确拒绝；关闭该NameError，不宣称真实WinDLL已运行。 |
| M10 | 生产role_command输出private-pids两个独立token4001/4002，按既有parser的int/nargs+独立解析得到[4001,4002]。静态复核既有sampler parser与旧owner固定argv未改；无sampler进程。 |

M03的DWORD/BOOL固定32位、HANDLE/SIZE_T指针宽度、GetProcessTimes等生产声明、STARTUPINFOEX大小112/cb112、明确三句柄白名单和NUL可继承已改善。真实纯builder布局与正常create路径通过；CreatePipe安全属性及清除read继承位、job默认非继承和控制handle不在白名单的源码正确性单独核实。上述局部正确不关闭下面部分创建清理缺陷，亦不证明真实Windows继承行为。

## 八项仍开放Major

### M03 — 部分创建失败仍丢原HANDLE，首错误后清理失败未具名移交

位置：broker.py:693–731、742–760 `WindowsApi.create_process_suspended/_release_created`。
触发：CreateProcess成功、GetProcessTimes失败，同时Terminate后Wait返回TIMEOUT、CloseHandle(process/thread)失败。预期原始birth错误保留，并把未退出/未关闭句柄与独立owner保留下来；正确UNKNOWN+精确保留允许，不要求不可关闭句柄凭空消失。实际 `M03_birth_close_failure`：原process502/thread503仍live，异常仅 `BROKER_PROCESS_BIRTH_QUERY_FAILED/detail=last_error=0`；cleanup失败仅留局部failures列表，未附原异常、未返回对象、WindowsApi无retained表，Core从未获得句柄。Wait返回值完全忽略。这里的缺陷是**丢引用和丢清理失败**，不是not_live严格断言本身。

`M03_attribute_cleanup_exception`另证DeleteProcThreadAttributeList抛普通异常后，紧随其后的NUL close和birth查询前的process/thread接管都跳过，501/502/503均live。清理位于finally不保证多个清理动作彼此独立。该注入证明普通异常隔离缺口，不声称Windows这个void原语必然会报此异常。正常birth失败且关闭成功的独立case通过。

### M04 — 返回长度和双计数仍未闭合，UNKNOWN可变成空Job

位置：broker.py:601–634 `WindowsApi.job_process_ids`。
预期返回长度必须足够且不超buffer、双计数一致，未知/截断不猜零。实际 `if reported and reported < needed` 允许reported=0：`(assigned,listed,returned)=(0,0,0)` 返回[]，(1,1,0)返回[111]；(0,1,16)计数反向不一致仍返回[111]；(1,1,999)超所分配长度仍接受。这些都直接调用生产查询方法和真实声明buffer，无危险地址解引用。

内联数组offset8及正常(2,2,24)正确，assigned>listed正确拒绝。18个PID由WindowsApi返回，但Core `_query_job`仍按17拒绝，因此**不把该单例宣称为端到端突破17上限**；它是探针层次限制。M04的阻断依据是零长度/不一致结果未UNKNOWN，尤以零长度空Job为关键。

### M05 — Job关闭失败后从pending与Core双重移除

位置：broker.py:1194–1207 `arm`、1552–1558 `_release_the_job`。
触发set_job_kill_on_close失败，随后的CloseHandle也失败。预期UNKNOWN并保留原job101和owner；实际 `M05_M06_M09_limits_close`：state虽UNKNOWN，live={101:job}，pending=[]、core.job=None，evidence.job.created=false。`_close_handle`失败原本保留pending，但随后无条件take及job=None抹掉了唯一可恢复的生产引用。终态文字UNKNOWN不能代替原资源保留。

**实际reader owner路径已独立确认**：正常转移仅改owner，Assign失败/取消都关本轮read端。四个真实Python reader保持阻塞时，stop不误关102/104/108/110，`core.readers`仍保留每个reader及原handle；UNKNOWN+reader_not_stopped可见。随后明确owner释放synthetic gate、join，再调用原Core._close_readers，四个HANDLE全部关闭。尽管pending在alive分支移出，这不是丢所有引用，**不以pending为空或docstring推断reader已丢失**。该子义务通过，M05由上述Job实际丢引用继续阻断。

### M06 — Core.stop没有真正独立finally，普通错误中断全部后续清理

位置：broker.py:1476–1511 `stop`、1513–1558清理流水线。
触发TerminateJob facade抛普通RuntimeError。预期记录primary/secondary后仍独立查询/关reader/关原process/thread/job，并传播原异常；实际 `M05_M06_M09_stop_ordinary` 保存九个live HANDLE，后续query/close均未调用，state UNKNOWN且 `_released=True`。方法只是try/except，没有执行这些后续清理的finally；重复stop因UNKNOWN/_released直接返回，无恢复清理。原引用多数仍在Core/pending，故这里判**没有执行合同要求的独立清理**，不是谎称全部丢引用。诊断先出错再cleanup出错时后者还覆盖primary。

Assign KeyboardInterrupt已清理并继续传播；单独诊断RuntimeError也在清理后传播。Loop READY/STATUS/STOPPED三处写失败均实际清理资源，原异常继续传播，独立通过。它们只能关闭这些子路径，不能把其他流水线错误或BaseException被_close_handle/_abort_round吞下的静态分支当成已闭合。main finally只关transport，依赖Loop.stop；Core内部缺口继续存在。

### M07 — start监督线程启动位于生命周期try之外

位置：custody.py:1029–1056（身份读取、pump构造/start、heartbeat start）；broker.py:2712–2724 launcher建Popen后接线也无独立清理。
触发broker已返回且pump活着，`_start_heartbeat`发生普通RuntimeError（模拟线程启动失败）。预期start内部有界清原broker/channel/pump，状态UNKNOWN，取消则继续传播。实际 `M07_thread_start` 返回异常时仍VALIDATED、failures=[]、peer.close_count=0，真实pump线程alive，broker仍被会话持有。事后只有明确session owner `_close_broker` 才完成清理，该salvage不算产品start成功清理。

REFUSED、parse、ordinary读错、KeyboardInterrupt读错四条实际路径均在start内关peer一次；取消继续传播。原问题已修这部分。生产launcher在Popen成功后若StreamChannel构造失败，没有把原Popen交回Session也无自己的finally，静态同属部分启动收口漏洞；未启动OS进程验证。

### M08 — 监督期限、取消/写完整性、心跳与共享清理预算仍有实际缺口

集中同原M08计一次，细分如下。

* **arm/launch监督不独立**：broker.py:2369–2383同步core.arm/launch，无deadline参数或监督者。`M06_M08_loop_arm_deadline`让实际Core的create_job facade耗尽固定期限，loop仍READY、创建并Resume两角色、写STATUS后才进_loop检测到期。mono截止确已在arm前冻结22600，但23000时仍执行launch，冻结一个数不等于启动被期限约束；真实Win32 arm/launch也仍同步在监督线程调用。
* **共享STOP预算变成多层新等待**：BrokerProcess.close(:2595–2644)先取5秒常量budget，channel.close花掉时间后两个wait继续各用原budget；`M08_shared_cleanup` fake clock从1000走到1014，deadline1005，两次wait各5秒。Session._send也用remaining/WRITE_BUDGET而非cleanup_deadline剩余，_stop_background两个固定2秒join在_close_broker计算deadline前执行，StreamChannel/Windows端固定join以及Core每process5秒/每reader2+2秒均未共享同一min(5,remaining)绝对上限。没有真实sleep14秒，使用注入时钟重算。
* **Windows精确取消竞态未闭合**：broker.py:1921–1969、2019–2095。worker.inside只set不clear且不作为启动握手；submit无界queue.put，线程handle复制失败/worker死亡后可排队卡住；CancelSynchronousIo的NO_HANDLE/NOT_FOUND只请求一次，不处理尚未进入I/O后才开始的竞争；_cancel不先stop，正常完成后worker仍回请求循环，join会报未停止。close在worker.done已set时跳过join，仍alive也照关原_file，且从未关闭duplicate_current_thread_handle取得的线程HANDLE。`M08_M09_thread_handle`实际worker停止后分配701却产品close集合为空；`M08_M09_windows_endpoint_methods`实际endpoint方法close时worker仍alive，facts.closed=true/retained_workers=1，随后测试owner才stop/join/关自己的synthetic701。不是Windows API运行证据，而是实际Python生命周期错误。
* **Windows写入截短仍成功**：_write_block(:2065)只调用一次write_stream，未循环partial WriteFile。上述endpoint case写abcdef，facade只写1字节，生产write直接返回1且只调用一次，不补余5字节；通道上层忽略返回数，残帧可被当已发送。期待必须完整写或具名失败。
* **心跳失效无人收口**：custody.py:927–980。发送错误被_heartbeat_step吞成failure字符串返回False，beat仍继续循环，state保持RUNNING、broker.close_count=0（M08_heartbeat_failure）。没有自动UNKNOWN/停止；pump异常也只缓存，不主动终止心跳。_heartbeat_step在absolute到期后仍发送STATUS（M08_heartbeat_and_budget从1→2帧），虽然effective_deadline未被延长，后台生命周期也没有按lease退出。
* **发送序列锁覆盖不完整**：custody.py:838–846的encode_command在_write_lock外取_sequence+1，heartbeat与STOP可先各构造相同sequence，再依次入锁、递增计数却发送重复seq；stop直到_close_broker才停止heartbeat。不是完整的单一序列owner；静态确定该竞争窗口，本批未动态复现并发调度。
* **双向预算接收侧未核**：Session._decode_reply仅received>1024，而_send才核sent+received+reserved；BrokerLoop收到STOP时也仅单向_frames阈值，且transport缓冲/排队不纳入总预算。此为静态缺口；本批预算子探针把received置1024，实际只验证了1025单向拒绝，**未证明双向总1024边界运行结果**。保留限制，不把它写成运行复现。
* **无换行帧无上界**：StreamChannel._drain(:2169–2184)只在发现换行后核长度，无换行时_buffer持续增长；M08_unterminated_frame实际保留98304字节，overflow=false，EOF把它静默丢弃；持续输入可无界增大。不满足32KiB界限。_drain初次read把None deadline传入endpoint，后续bind不会改变该次局部deadline；队满重试也未检查cancel/deadline，只看_eof。这些进一步阻断期限安全。

这些问题不因未接线或Windows尚未实测而忽略，也不以真实Windows NOT_PROVEN代替静态正确性要求。

### M09 — 原broker/通道未知或关闭失败仍丢引用，部分路径假RELEASED

位置：custody.py:982–1001、1147–1193；broker.py:2085–2095、2213–2250、2577–2684。
预期原broker退出、所有owned HANDLE关闭、reader实际停且无读错均须明确证实；未知/失败保持UNKNOWN和原owner引用。实际 `M09_close_false`中peer.close返回channel_closed=false/process_exited=false，会话虽UNKNOWN却仍broker=None，丢原引用；`M09_close_unknown`返回None，已收到RELEASED的会话直接保持RELEASED、无failures、broker=None。缺失字段/None不是关闭证明，不能只检查字典中显式False。

生产BrokerProcess给出的facts本身字段齐全，但返回False时一样走丢引用分支，不是只拿未知Peer的故事替代生产错误。StreamChannel的_reader._error没有进入close facts，reader_finished只看存活；Windows endpoint retained_workers计数在channel层被丢弃；_stop_background即使join失败仍把_heartbeat/_pump设None，也没把pump.error纳入RELEASED。重复close缺乏统一幂等状态，_PosixPipeEndpoint先置_closed再实际close失败，后续无法重新关闭。Windows thread HANDLE泄漏与活worker下关file也在M08描述，避免重复计数。

Core现在确实把reader.error/alive及process退出/handle关闭/Job计数纳入_is_released，正常成功与reader_error独立通过。这个局部改善不关闭父broker通道事实链的缺口。

### M11 — 默认nonce已修，但父launcher错误映射仍不满足结构化拒绝

位置：custody.py:1020–1026，broker.py:2698–2702，默认launcher调用:1267起。
默认os.urandom(16).hex是32小写hex，非法nonce在构造/生产launcher与main写前拒绝，目录副作用次序静态正确；这些原根因关闭。仍开放：默认launcher的BrokerError（例如非Windows BROKER_PLATFORM_UNSUPPORTED）被start转换为 `CUSTODY_BROKER_LAUNCH_FAILED:BrokerError` 泛型条目后原样raise，未按_failure_code保留具名码，也没有返回结构化UNKNOWN/REFUSED。接口并非只允许取消继续传播，普通错误映射仍缺。当前不会留VALIDATED（已改UNKNOWN），因此不重复旧缺陷描述。

**本项只作静态结论**：M11_nonce_mapping探针的doc租约100000配合真实wall导致在validate先触发CUSTODY_PLAN_LEASE_EXPIRED，state NEW，根本没进入default launcher。其原始Oracle FAIL是探针限制；只能用其中独立nonce构造结果确认默认32hex与5种非法nonce拒绝，不能用该失败声称已复现平台错误映射。未修probe或补跑。

## Minor与Oracle处置

保留非阻断 **m02**：broker.py:1370–1377 `_start_reader`及_pending类总述仍写“移交后leaves table”，与正常transfer仅改owner矛盾；实现者已主动披露。实际reader owner语义以上述代码和运行结果判断，不因改一个docstring强制全套重跑。原m01已关闭，m02是新文档项，不冒充原别名未修。

41行原始21/20不可改写。M11默认路径未触发、M08预算运行边界未覆盖、M04十八PID在Core被拒均明确降限；其余同根因多行不重复计Major。对刻意CloseHandle失败，不要求假成功清空资源：M03/M05给出的是原句柄引用被真正丢弃的证据；reader仍alive但实际引用保留可恢复的case通过。M03普通声明、正常创建、birth失败成功清理、Core正常/assign/cancel/诊断/读错、Loop三断写、父四收口和M10等都保留正例，不以旧97迁移给新候选。

## 作者证据复算与历史限制

`evidence-audit.json`逐项核真实root执行件、plan ACK hash、223命名依赖文件（不是dist-info元数据）、stdlib三pin、原始commands/raw/receipt/guard/counter及有序node集合。validation01 plan为90c3c5e2…，实际仍117/97PASS20FAIL，cleanup=false，pump+heartbeat残留；R1 join名称遮蔽、R2 pending/reader是原M05/M07–M09生产生命周期缺陷，不写成“全是测试错误”或“与独审无关”。原失败20条longrepr逐条保存在audit，未删除或改为PASS。

validation02 plan为474e2fe1…，三条argv/cwd逐字一致，root guard/runner/outercounter tool pins全部一致；117有序collection/calls一致、117PASS/0FAIL/0SKIP（115功能+2integrity）、FD身份与MainThread、窗口恰一次、counter不变的原始事实可复算。但这只能证明作者选中断言通过，不关闭本审查的开放义务。validation01 commands仅输出路径采用相同cwd下相对拼写，与plan绝对拼写不逐字一致；执行件和目标文件相同，NEW审计如实记argv_exact=false，未把它写成精确argv全等。

首批失败custody恢复文件sha256 `68faa274de9eb8fa786e8b32d71a501d2b24513531c3621ee98313814eae8d56` 与首批pin完全一致；broker/test仍MISSING。traceback锚点一致不证明旧源码完整封存。首批97正例不移用于37d938b。旧54失败、纠偏32与独审11的2PASS9FAIL完整保持，无重跑和回填。

## 官方依据、未证与交接

本次重新读取Microsoft官方[Job内联PID结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)、[QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)、[handle-list约束](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)、[STARTUPINFOEX cb](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-startupinfoexw)与[CancelSynchronousIo](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelsynchronousio)。它们支持布局、继承和取消请求不等于完成的静态依据；不是本机Windows运行证据。两条首次拼错/非对应header URL失败未当来源，后用正确官方URL读取。

真实native/Windows API/Job/GPU/端口/sampler/父崩溃/Windows stdin EOF全部NOT_PROVEN；grant_authority NOT_VERIFIED/admission=false。原I24/产品12/A06/原ledger余额/质量/人签仍未证，不签Stage PASS，不批准新真实运行。

十字段：当前坐标=根R1/WP-R1-U3/RUNNING离线准备；本批完成=全11Major+m01独立审查及一次41case；最后通过门禁=control既有统一切片live15人签范围；当前阻塞=8Major与后续N2/N3/N4及固定门禁；全局路线=见下；剩余工作=root集中裁决并冻结修复，不自动补跑；下一责任人=root门禁owner/实现owner；所需授权=本批一次ACK已消费，无新人类权限请求；证据目录=本NEW目录与root原received只读件；精确停止原因=独审完成CHANGES_REQUIRED，唯一批次结束，worker_done后由root回收。

完整V0–V3大纲（根control实际计数，非工时）：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3(V2)0/4、R4(V2)0/4、R5a(V3)0/4、R5b(V3)0/4、R5c(V3)0/4。实现/机器验收/独审/人签不互相代替。
