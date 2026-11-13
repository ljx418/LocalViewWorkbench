# N1 correction05+06 独立静态审查

**CHANGES_REQUIRED；Fatal 0 / Major 6 / Minor 0。** M03/M05/M06/M07/M08/M09均仍开放，以下按原六项义务合并计数，不按子缺口重复计Major。M04/M11及M01/M02/M10/m01保持静态关闭。此结论由原生产owner的确定控制流与可达交错形成，不继承作者报告的开放/关闭结论，不要求先重跑已知不合格候选。

候选 `4287090b464d16f398b92797d8f5595359fcb442`；证据commit `e03648631ed855bcb89245b07f698386859a62a4`。候选五源只读Git blob保存在本目录 `candidate/`，没有物化或修改tools。下文 C=候选v0_s3_native_custody.py，B=候选v0_s3_native_broker.py，T=候选test_v0_s3_native_custody_correction05.py；行号与候选原tools完全一致。两个完整numbered.txt保留逐行证据；candidate-pins.json保存原blob ID和SHA256。

本轮候选import、collection、pytest、动态probe均 **0次**；没有执行作者runner/guard，没有读取当前counter/原ledger，没有调用ctypes或真实Win32/进程/Job/GPU/模型/服务/socket/sqlite/网络/下载/媒体。不派生Agent。静态审查所用Python只做Git blob读取、SHA256、JSON和AST解析，绝不exec/import候选。已有足够静态实锤，未申请新的动态ACK，也未把作者ACK当成本独审许可。

## 基线、权威与证据核对

开工保存head.txt、status.txt（完整tracked/untracked）、index.txt、tracked-diff.txt、index-diff.txt及source-hashes.json；原三源逐字等于历史37d938b，两个新增测试源在本review tools原不存在。HEAD为204e585f81837d9743869b94030ae941b2d52be4。未reset/clean/checkout/add/commit，历史tracked/index/untracked及既有源码保持。

读取根AGENTS（含26条容量/归档规则）、governance README、control、docs24、correction05合同及24组JSON、received-review六Major原报告、correction06合同/decision、validation-plan-01完整JSON及ACK/回复与工具文本。根当前坐标仍R1/WP-R1-U3/RUNNING，阻塞S3_P4_N1_CORRECTION06_INDEPENDENT_REVIEW。authority-hashes.json绑定这些权威输入。冻结plan SHA256=65e9df9904e297d0f5c76f756b5d6070f2437375f3b6a65eb2f9d0a0b85a2251，与ACK一致；仅重读，未执行其中三条命令。

pin-evidence-audit.json：19 source pins均匹配候选blob/解释器，223命名依赖文件、3stdlib、3root工具当前字节全部匹配；10个旧产品owner与review本地相等，两个旧作者guard/runner本review原不存在且未补写。批准的tools/open_lvw_browser.cmd保留CRLF SHA256=f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04，规范化LF等于候选。没有发现其他非历史owner漂移。

作者原始JSON/raw日志从证据commit只读保存于evidence/。selected、collected、157个call顺序与根冻结nodeids逐一相同；157PASS/0FAIL/0SKIP、155功能+2完整性、exit0、21.50613284111023秒。继承文件名native-custody-correction-03.receipt.json位于本次correction06/attempt01，不能误称旧运行。作者guard记录先于candidate/pytest、一次dlopen(None)预装后永久关闭、runtime_denials空；FD0/1/2真实dev/inode/mode前后相等，FD3过滤、unknown空，线程前后均MainThread，批级cleanup=true。以上只复算作者收据，**不证明下面未覆盖交错的产品返回清洁**。保存的counter-before/after证据逐字相同；本轮没有重新读取live counter。

旧0e830773/4693c12d的157调用151PASS6FAIL（149功能+2完整性）、exit1、cleanup=false和late/closer两个线程不改写。分类保留F1/F3/F5/F6四个生产相关路径、F2/F4两个纯测试路径，F3兼有错误测试预期；late是故障替身真实线程，closer是生产创建线程，不能统称“不是产品线程”。

## M03 — 取得时保留改善，但未确认退出即可丢最后process控制句柄

**Major，开放。原blob B981–1158、1181–1231、806–869。**

已修：NUL在CreateFileW成功后立即_retain，process/thread在成功创建后登记；Delete异常与NUL close分离，原引用失败留表，birth主错和cleanup文本保留。N05-R01和R02的部分路径成立。

确定负例：CreateProcess成功，birth查询失败；TerminateProcess返回False，WaitForSingleObject返回WAIT_TIMEOUT，随后两个CloseHandle都成功。这是允许发生的原语组合，不能把CloseHandle成功当作进程退出。B1181的_release_created虽记录terminate失败/exit_not_confirmed，仍无条件CloseHandle(thread/process)，成功就_forget；B1158抛birth原错时，**仍可能存活的本轮suspended process已没有任何原process控制句柄，retained_handles为空，Core从未收到CreatedProcess**。预期退出未证实的原process仍有可恢复控制owner；实际只剩错误文本与PID，release_retained再无原handle可协调。同样问题在API release_retained对process terminate/wait失败后仍关闭并forget的路径。这里不把“句柄已关闭”说成“句柄泄漏”，缺陷是活process控制权被提前释放。

取消方面，_release_created收集KI/SystemExit只附release_cancelled而不向调用层传取消对象；create_pipe的取消另见M05。主错误应保留，不意味着取消只可变成普通字符串。R02仅覆盖Delete取消及birth普通主错+terminate取消，不覆盖退出未确认但Close成功的活process负例；SyntheticKernel32.live按handle close删除项也不能证明OS process实际退出。

## M05 — pipe成功移交仍有两个owner，partial/cancel清理仍不闭合

**Major，开放。B1298–1335、806–869、1900–1940、2140–2146。**

已修：CreatePipe成功瞬间保留原ctypes两端，继承位返回False且Close失败的端仍可通过API恢复；job关闭失败保留以及pending成功通知job已改善。

确定的所有权反例：WindowsApi.create_pipe在B1319–1335登记两端后，**成功return从未_forget/transfer API表中的原端点**。Core随后把相同原对象登记pending并transfer到READER，API的retained_handles仍把它们标作WINDOWS_API。原process成功移交有_forget，两端没有。于是合法的API恢复入口release_retained会对这些已移交、可能由实际活reader读取的原read HANDLE执行CloseHandle；Core pending/reader仍持有它且不知已关闭。预期成功移交唯一owner，失败API保留与Core接管去重；实际两个可独立关闭的owner。不是单纯表名问题，也不是默认stop一定调用该API恢复的断言，而是实际恢复入口本身无法区分未移交与已移交资源。

取消反例：SetHandleInformation返回False，read CloseHandle抛KI/SystemExit，write close可成功；_close_quietly把取消放入局部cancellations，B1332仍只抛普通BROKER_PIPE_INHERIT_FAILED，从不传播取消。若SetHandleInformation本身抛取消，则整个失败清理块都不进入，两端虽仍在API表内，独立安全close没有执行。预期安全清理后取消传播；实际一个分支吞取消、另一个跳过清理。N05-R03仅测试返回False+普通close失败，不能覆盖这些分支。

## M06 — pending通知局部正确，reader取消和record恢复仍有事实/所有权缺口

**Major，开放。B2148–2239、2274–2392、2435–2467、2476–2514、1592–1642。**

已修：pending pass成功关闭后_note_closed_handle同步job/records/retained，取消仍由顶层step在末尾抛出；多个process普通wait失败不再跳过下一record；未启动reader不非法join；普通alive reader会从pending拿走read端避免末尾关闭。

确定取消反例：某真实reader仍alive，其finished.wait或join遭KeyboardInterrupt。_close_readers捕获取消后继续其他reader，最后抛取消；但本reader未走到B2224的_pending.take，read HANDLE仍是owner=READER的pending项。stop的step保存取消并继续_close_pending，close_all对所有item无条件CloseHandle，**在该reader仍alive时关闭原read端**。预期每个资源独立清理且任何取消分支都不能在活reader下关read端；实际“顶层继续清理”绕过read端保护。普通wait/join异常同路径。R06只构造两个从未启动的reader，没有它在docstring承诺的后续活reader，更没有取消交错。

另一个确定取消吞噬：B2435的_wait_one_process把wait_process和exit_code的所有BaseException变成error_type后return，外层_wait_the_processes的KI/SystemExit分支永远收不到它们；故stop可能返回普通UNKNOWN evidence而不传播取消。R05只注入RuntimeError，R04只注入CloseHandle取消，两者都未覆盖。

恢复事实反例：首次stop的record handle持续关闭失败，_retained_resources登记原handle；原期限内条件恢复，第二次stop的_release_the_records关闭成功，更新record并_pending.take，却不_release_resource。末尾pending已没有该handle，_note_closed_handle不会再收到通知，**retained_resources仍声称保留已实际关闭的原handle**。job路径已调用_release_resource，但record/reader成功恢复路径未等价修复；不能将F3的首次pending成功证明推广为所有恢复路径一致。

## M07 — Session pump登记有修复，真实endpoint/launcher/closer启动仍失主或误确认

**Major，开放。C1300–1360、1417–1459、2095–2140；B3282–3340、3474–3496、4504–4585。**

已修：Session background_threads在Thread.start前登记STARTING；start已实际启动后抛错保留原thread；晚到pump的stop_event已置位，不再业务read；closer构造异常具名且closer_started可恢复。这些静态成立，R07/R08局部owner有实质改进。

真实Windows endpoint仍是旧模式：B3282创建worker后先worker.start，再固定wait_ready(5)，函数正常返回后read/write才赋self._reader/_writer。若Thread.start实际启动后抛错，或wait_ready被取消，原worker及其已取得thread HANDLE从未进入endpoint/持久表；Session/Core并不拥有它。start未返回期间endpoint.close看不到这个worker，能关闭它稍后要用的原file。预期原线程从创建/启动中即登记、晚到只能收口；实际登记只在_start正常return后。这是直接生产read/write入口，不依赖测试直接调用fake。

launcher仍不闭合：Popen成功后到_adopt之间的executable.read_bytes/hash只捕获OSError，KI/SystemExit直接离开launch_broker，原Popen尚未登记任何persistent owner。进入_adopt后，_terminate_and_close_process没有显式关闭Windows Popen._handle；terminate/wait/pipe.close均成功时不retain process，原HANDLE释放仅可能依赖GC。该helper若遇KI也在建retained表前中断。若BrokerProcess构造失败而channel已成功创建，先关闭Popen的stdin/stdout、后channel.close，可能在活IO上先关原file；channel.close返回不完整facts而不抛异常时也未retain channel。StreamChannel构造本身start已启动后抛错时赋值channel尚未成功，外层根本看不到已活动channel/endpoint。

closer的另一个启动中分支：_start_bounded_close先公布_closer再Thread.start；在start尚未实际启动而未返回时，_await_closer_exit的join抛RuntimeError，被C2137直接当“从未启动、无需等待”返回True。没有closer STARTING/返回状态证明，这个原thread随后仍可启动。已保留引用不等于证明线程已结束。R09仅构造失败，R23仅已启动closer，均未覆盖此分支。

## M08 — 锁/终态接线改善，但预算跨层、取消进入IO及partialwrite仍开放

**Major，开放。B1839–1875、1920–1930、3001–3051、3112–3156、3282–3379、3941–3968、4472–4501；C1746–1824。**

确认关闭的子路径：_apply_state与_latch_unknown_state共用RLock，UNKNOWN单向锁实际存在；双向_reserve_frame在同一_budget_lock下check+commit，序列仍在write锁内；C_decode_reply对STOPPED/REFUSED终态消费预留，B_loop decode出STOP后用reserved=0，_stop公开发terminal STOPPED，已沿实际公开链路静态核对。R18仅helper测试不能证明接线，本结论来自C_send/stop/decode与B_loop/_stop/_reply逐条调用，不迁移helper的PASS。60s/120s、32KiB、partialEOF、队满检查、1024、16进程/17含broker与6h数值保持。

确定取消交错：worker.run持_condition只读取_cancelled=False，释放锁后才置IN_IO/inside并进入action。取消线程随后取得_condition置cancelled/stop_event，CancelSynchronousIo返回NOT_FOUND（IO尚未进入）；request_cancel的_stop_event.wait立即True，因为它刚刚自己set该event，于是取消循环必在一次NOT_FOUND后退出。原worker随后进入blocking read。预期取消与IN_IO按代协调并禁止取消后新IO；实际锁只包check未包state过渡，所谓重复取消循环不能重复。旧代done.is_set仍被用于取消完成判断，也不是本代真实完成。R15/原R10让first IO已进入、second排队，没有强制此check/enter交错。

partialwrite动态期限仍失效：write开始时复制self._write_deadline；_write_block每段只读这个旧值，不读_effective_deadline。bind_deadline在进行中的await上已动态生效，但worker partial loop仍可在更短cleanup截止后继续下一段WriteFile。若cancel=None或channel cancel尚未传播，旧write deadline不能替代共享截止；即使有channel cancel，worker也可能在前述取消竞态后进入操作。预期每段核实际共享期限；实际await新值与worker旧值分裂。

预算跨层未全部修好：endpoint._start的wait_ready(CLOSE_JOIN_SECONDS)不取任何原deadline，也在read的截止核对之前创建worker；_await先submit才检查过期/cancel，已过期请求仍可被worker执行。launcher失败恢复的process.wait每次固定5秒，release_retained_launches不接原context或deadline，每次恢复可以重新得到5秒。父/子各自只有Session、Core/Loop共享context；BrokerProcess、StreamChannel、endpoint、WindowsApi/launcher仅保存数值或无绑定，不能满足“各进程内所有层同实际context”的合同。Core.arm自身不核创建前/后预算，_launch_role连续创建stdout/stderr pipe中间也没有后核；虽guarded startup和late process接管已修好，第一pipe跨期仍继续创建第二pipe。N05-R11甚至在绝对期限999、当前1000时先core.arm成功，再只检查launch拒绝，未证明每个create前拒绝。

另有StartupOwner._run在_finished.set后尚需_put和退出，settle只要_finished为True就可返回True且release_inflight，不能由这个event证明真实线程已退出；正常成功await_result也未做真实join/release_inflight，保留与已退出事实没有完整收敛。这与closer问题同属“工作尝试完成”与“真实线程退出”两个事实。

## M09 — 公开恢复已增加，但真实BrokerProcess和等待事件仍锁死恢复

**Major，开放。B3381–3430、4229–4339；C1746–1824、1931–1959、2036–2140。**

已修：Session公开stop可恢复未确认peer，内部FINISHED不再重复close；首次public stop遇此前后台FINISHED可接管；原期限不变。Posix成功close再次仍True。REQUIRED_CLOSE_FACTS严格包含reader、两端和worker HANDLE，缺失/None/false的这些布尔事实会拒绝；reader_finished属性也必需True。BrokerProcess不再直接关闭stdin/stdout，已关闭原违例。

**阻断的实际公开恢复路径：** 首次Session.stop→BrokerProcess.close→StreamChannel.close，read端/worker尚未关闭，channel.close正常返回不完整facts。B4299将channel_closed=True，仅代表方法return；第二次公共Session.stop确实调用同BrokerProcess.close，但它从上次facts复制True，然后`if not facts['channel_closed']`整个跳过channel.close。即使worker已退出、file可关，read/write endpoint和worker HANDLE永远不会再协调，Session仍保留同peer。预期只跳过确认成功项，未确认端点可达；实际高层“调用已结束”锁死下层资源恢复。N05-R19仅把RecordingPeer.close_facts从False改True，完全绕开这个实际owner；R21只验证第一次不直关file，没有第二次真实恢复。

即便直接endpoint.close，失败后_retained只append从不清除/去重；worker后来真实退出，retained_workers仍旧非零，worker_alive旧True也未清。thread HANDLE Close失败后原worker确实还持有handle，但endpoint.close不调用release_thread_handle恢复；它甚至可将file关闭并_closed=True，之后early return永不再试HANDLE。预期保留表反映实际live/closed且失败恢复可达；实际仅保留引用而产品路径无法收敛。R20创建reader/writer均None，不能证明worker/HANDLE恢复。

**等待者第二次尝试被旧close_done骗过：** 首次不完整关闭结束，_finish_close设_close_done；公开stop恢复在_recover_close将状态改IN_PROGRESS但不clear/reset按代event。另一个public stop竞争者进_await_close，旧event立即True；若清理由调用线程执行、_closer=None，_await_closer_exit直接True，即使当前owner仍阻塞于真实broker.close。预期等待同一个当前owner或到原deadline；实际把上一尝试完成当当前完成。这里不是要求无限等待或新预算，只要求当前代终态正确。

**真正public stop仍漏join：** 后台closer已_finish_close，broker=None，但closer尚未真实退出（R23的slow_finish就是合法强制尾声）。首次公共stop的_close_broker在FINISHED直接返回ALREADY_FINISHED，_public_stop_recovery因broker=None直接返回，随后C1824返回evidence，从不调用已修复的_await_close；可见closer_alive=True。R23直接调用_await_close能证明该helper改善，不能证明public stop在finish前/后到达均有限join。反复stop分支有_await_close，首次分支没有。成功资源无须双关，但真实closer退出仍需单独协调。

## 24组冻结义务逐项裁决（均核实际owner）

| 组 | 生产入口与独立结论 |
|---|---|
| N05-R01 | WindowsApi.create_process_suspended NUL取得即retain、close失败恢复成立；M03整体另有未确认process退出失主。 |
| N05-R02 | Delete取消后独立NUL/process清理改善；_release_created退出未确认即丢控制handle/取消对象不上传，未闭合M03。 |
| N05-R03 | create_pipe partial普通失败原对象保留改善；成功移交API去重、KI独立清理/传播未闭合M05。 |
| N05-R04 | stop→pending on_closed首次通知job/record成立；第二次record直接close成功遗留retained，未闭合M06全事实。 |
| N05-R05 | 多record普通异常隔离成立；wait/exit_code取消在_wait_one_process吞掉，未闭合M06。 |
| N05-R06 | 未启动reader不join成立；该测试没有后续alive reader，取消/异常时pending仍可关活read端，未闭合M06。 |
| N05-R07 | Session pump STARTING原owner及晚到stop_event成立；实际endpoint worker另有启动中失主，M07未全闭。 |
| N05-R08 | Session start已启动后抛错保留原thread成立；T finally是测试owner salvage，不证明产品返回清洁。 |
| N05-R09 | closer构造失败具名且公开stop能接管成立；closer.start未返回被join RuntimeError当结束，未闭合M07。 |
| N05-R10 | _adopt保留terminate/wait/pipe普通失败成立；Popen到adopt空窗、原HANDLE与部分channel失败、取消未闭合M07。 |
| N05-R11 | late CreateProcess返回先pending/record再核截止成立，Assign跨期后的Resume前核成立；arm/pipe/endpoint create及后核不全，M08开放。 |
| N05-R12 | Session context发布值有锁、Core生成+发布在锁内；发布后同值不延长成立，不用四线程barrier通过冒充完整跨层预算证明。 |
| N05-R13 | Core reader wait/join与多个process逐次重算成立；endpoint startup/launcher恢复仍独立5秒，M08开放。 |
| N05-R14 | endpoint._await每次重读_effective_deadline成立；_start在该检查前固定wait，partialwrite旧值仍开放M08。 |
| N05-R15 | submit取消共享锁/完成按代部分成立；run取消check到IO窗口、NOT_FOUND只一次、旧done及HANDLE恢复仍开放M08/M09。 |
| N05-R16 | 由C_state_lock覆盖检查+赋值与unknown整个临界区静态关闭原check/set竞态；50轮barrier并不强制交错，但无需动态probe才能证明源码锁覆盖。 |
| N05-R17 | C_budget_lock覆盖双向check+commit成立；exact-one-over公式保持。 |
| N05-R18 | 测试是helper；独立已沿Session.stop→_send/_decode_reply及BrokerLoop._loop→_stop/_reply核真实STOP/STOPPED终态消费预留成立。 |
| N05-R19 | Session public stop意图恢复改善；实际BrokerProcess channel_closed复制True跳过未完成channel，开放M09。 |
| N05-R20 | Posix成功幂等与Windows无worker时file失败重试成立；retained worker/原HANDLE重试不收敛，开放M09。 |
| N05-R21 | BrokerProcess不再绕过endpoint直关file成立；launcher adoption失败仍先直关Popen pipes，归M07。 |
| N05-R22 | required布尔facts缺/None/false拒绝成立；COMPLETE_CLOSE_FACTS是硬编码测试声明，不能证明真实资源完成，恢复等待仍归M09。 |
| N05-R23 | _await_close FINISHED分支实际join、两模式/到达前后helper改善；首次public stop没调用该等待，旧event恢复代不分，closer启动中误确认仍开放M09/M07。 |
| N05-R24 | 原133+24顺序和兼容保留；每组未覆盖负例不能由函数数量/名称通过，salvage与产品返回事实分开。 |

## 原16组、已关闭项及测试诚实性

| 原组 | 本候选独立结果 |
|---|---|
| N03-R01 | birth+双close失败原owner改善；terminate失败/wait超期+close成功丢活process控制权，M03开放。 |
| N03-R02 | ordinary attribute cleanup失败后的独立收尾改善；不外推未确认退出。 |
| N03-R03 | M04长度/双计数/17边界静态保持关闭。 |
| N03-R04 | job失败原HANDLE/pending/retained保留成立；pipe成功移交问题仍属M05。 |
| N03-R05 | 顶层独立step和ordinary多process等待改善；nested取消/pending活reader保护仍M06。 |
| N03-R06 | startup保护与内部close不重试改善；endpoint/launcher/closer启动中仍M07。 |
| N03-R07 | guarded startup前后核、late process接管改善；每个create/endpoint仍M08。 |
| N03-R08 | BrokerProcess单次两个wait递减成立；固定endpoint ready/launcher wait未归一。 |
| N03-R09 | partial write完整循环成立；绑定中途收紧未进入worker每段检查。 |
| N03-R10 | queued请求取消部分成立；check→IN_IO和NOT_FOUND重试未闭合。 |
| N03-R11 | UNKNOWN真正同锁、callbacks不等待closer成立；真实closer退出/public首次stop仍开放。 |
| N03-R12 | 双向预算同锁，实际终态预留消费静态成立。 |
| N03-R13 | 32KiB/one-over/partialEOF/队满检查保持；不能由它证明Windows取消竞态。 |
| N03-R14 | strict facts与Session恢复入口改善；真实BrokerProcess跳过channel锁死恢复。 |
| N03-R15 | M11 default nonce/unsupported code映射静态保持关闭。 |
| N03-R16 | 正常Core记录清理成立；活reader后gate.set/join/_close_readers只是测试owner salvage，pump/heartbeat名字过滤不覆盖closer/startup/endpoint全部线程。 |

M04独立代入B_job_process_ids：header=8、capacity=18、64位buffer=152；reported<8或>allocated、assigned!=listed、listed>17、needed>reported均拒。0/0/0、1/1/0、0/1/16、18完整、17截短拒；0/0/8和17/17/144合法；32位按pointer_size计算内联数组，不读取外来指针。Core再次核17。此为静态检查，不是Win32实测。

M11：默认os.urandom(16).hex、非法nonce构造前拒；launch_broker非Windows在创建目录前抛BROKER_PLATFORM_UNSUPPORTED；Session._launch_failure_code保留code，KI/SystemExit进入清理后传播。原R15有效wall/lease到default launcher，不重用expired假负例。M01 fullmatch单段/设备名/64边界、m01深拷贝canonical/MappingProxyType/tuple、M02固定Windows宽度/显式prototype、M10 sampler独立private-pids参数及旧parser字节保持；未执行旧41。

COMPLETE_CLOSE_FACTS（T82）字面常量的注释声称“每项来自stand-in事实”，实际并无读取实际端点、worker或HANDLE状态；RecordingPeer.close只置reader_finished=True并原样返回close_facts。因此这些正例可证明父接口接受完整声明，不能证明真实BrokerProcess清洁、更不能掩盖它的恢复接线缺失。R18和R23的helper覆盖限制已逐项说明；没有把一切fake都判无价值。

R16五十轮barrier未强制check/set穿插，但本候选源码临界区确实完整，不据缺少强制调度虚增缺陷；其他已存在静态缺陷无需为追求动态记录而新增probe。T的R04/R08/R23 finally补救保留产品返回前断言且有价值，但不是生产成功证明；R07/R14等仍有断言前可能未进finally、sleep轮询和测试主动gate/join，作者批末MainThread只能证明该一次成功自检的批末状态。没有以pytest进程退出/GC当清理证据。

十字段：当前坐标=R1/WP-R1-U3/RUNNING；本批完成=固定候选五源、全部六Major/24新组/16原组静态独立裁决与原收据复算；最后通过门禁=621b1bf统一切片live15范围；当前阻塞=本六Major及后续N2/I24/产品门禁；全局路线位置=下列原control大纲；剩余工作=root集中冻结修复/后继候选；下一责任人=root门禁owner与实现owner；所需授权=本次静态已授权，未请求新动态；证据目录=本NEW目录；精确停止原因=CHANGES_REQUIRED静态审查已完成，无待ACK/待运行批次，worker_done后交root归档释放。

V0–V3完整大纲：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3(V2)0/4、R4(V2)0/4、R5a(V3)0/4、R5b(V3)0/4、R5c(V3)0/4。实现、自检、独审、人签分别保留，不改变正式计数。

本审查不修改候选后签通过，不主张StagePASS、真实native/Windows/Job/I24/产品12/A06/原余额/质量/人工签署；grant_authority仍NOT_VERIFIED、admission=false。本轮没有创建产品线程/FD，无待salvage产品资源；最终workspace-after.json核本轮既有HEAD/index/tracked diff及所有保存源码hash不变，只新增本报告目录。
