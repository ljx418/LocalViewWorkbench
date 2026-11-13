# N1 完整父侧 native custody 与纠偏01独立审查

结论：**CHANGES_REQUIRED；Fatal 0 / Major 11 / Minor 1**。这不是 Stage PASS、产品 Gate0 或真实 native 通过。纠偏01修正了原日志路径缺陷及原测试问题，但完整 N1 仍有生产实现缺陷。不可将作者32PASS或本次2PASS作为完整N1通过。

候选 `9352a34cfa8ea9715437b5ffa5d411369dd5548d`；证据交付 `8504fd6cab519ce33cea5382f7b3d8405667f479`，后者无 tools/lvw 代码变化。无N1基线 `b95de076f37e64d321629c065e5531eba8a5250a`，失败候选 `247519de8c1512d86921af8ed2c73f0db3982c88`。本审查独立完成，无派生Agent，无源码修复、Git add/commit/checkout/reset/clean。

## 归属与边界

开工读取 AGENTS、governance README、control/执行索引及根冻结 implementation architecture-decision/contract、correction contract/root-decision、review intake/received。真实根 control 为 R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING；review 本身 HEAD 为 `204e585f81837d9743869b94030ae941b2d52be4`，不把该 HEAD 冒充物化代码候选。

`initial-head.txt`、`initial-index.txt`、`initial-status.txt`、`initial-source-hashes.json` 保存初始实态；所有既有非CMD tools源逐Git blob匹配b95。发现CMD差异先问root，`msg_f507eb6ec14d`确认只保留 `open_lvw_browser.cmd` 的CRLF原bytes：sha256 `f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04`；规范化后与基线一致。仅物化三新增候选文件，其hash见materialization.json。最终265个 tools/lvw/RuntimePatch跟踪文件无缺失，仅此CMD字节例外；不能声称整树字节等于候选。index未改，旧dirty状态不归本审查制造。

根冻结证据逐文件hash见 evidence-hashes.json；原始commands/raw日志/receipt、实际root guard/runner/outer-reader pins、223命名依赖文件pins和精确collection顺序复核见 evidence-audit.json。作者submitted runner/guard与dist-info223元数据不是实际root执行件，未被本审查使用。

## 唯一独立执行与限度

先静态制作计划，`msg_c21ca49d8395` ACK唯一 plan sha256 `e1d4cf96e83608e2353ea3e8ca7370b801cb546c377c9dc2b4a3b14e7606a1a9`，然后严格执行plan.commands三条绝对argv/cwd。无pytest、无作者测试模块导入；自建Facade直接调用生产validator/Core/Session/Loop。-I -B，guard先于候选，guard后只append封存依赖目录与包根；223项是命名文件pins，无site.main/.pth。guard另拒ctypes.dlopen/dlsym；不实际加载WinDLL，不执行Windows API/Job/业务进程/socket/SQLite/模型/GPU/服务/用户媒体/网络/下载。

三条退出码 **0 / 1 / 0**。11个独立case **2个Oracle通过、9个Oracle失败**，原始结果在 receipt.json 和 guarded-validation.stdout.raw；stderr为空。guard自检拒6项，runtime_denials空，guard墙钟0.034s；真实FD0/1/2 dev/inode/mode前后相同，瞬时枚举FD3的EBADF保留记录，无unknown；线程前后均MainThread。原counter仅guard外前后各一次只读，均 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive、28/240/12.362，charges相同；不写/退款/清零/新建/复活。

每个fake资源先记录retained_owned_fake_handles/calls，再只清该Facade分配的整数句柄；不是关闭OS未知FD，也未靠GC掩盖。owner_success的线程显式join。它证明本审查批次无真实FD/线程遗留，不证明产品Win32清理。没有重跑67/54/32或旧M08/20/35/15/27/37。

限制：冻结探针捕获预期异常时保留类型、调用序列、资源和状态，未保存完整Python异常堆栈；stderr空不能当无异常。未追加traceback探针或补跑。具体失败源码位置如下。9个失败不能机械视为9个Major：sealed_plan_mutation按可信调用方边界评为Minor；同根因取消/诊断/写失败集中计数。

## 集中有效发现（位置均为候选文件行号）

下文custody.py指`tools/v0_s3_native_custody.py`，broker.py指`tools/v0_s3_native_broker.py`。

### M01 — COMFY user_directory 前缀校验允许逃逸，且无长度闭合

位置：custody.py:206–210、broker.py:601–605。触发 `data.user_directory='safe/../../outside'`（Windows反斜杠同样在合法首段后绕过）。预期计划在任何Job/process/log前拒绝；实际 `_DIRECTORY_NAME.match`只匹配safe前缀，生产validate接受，role_command生成根外user-directory。`user_directory_escape`原始case为FAIL并保存完整argv。整个字符串也不受64字符上限约束。这是原纠偏日志路径修复以外的生产边界漏洞，无需真实Windows逃逸实测才能成立。

### M02 — Windows API表类体同名赋值导致入口NameError

位置：broker.py:270–279 `_Api`类体。触发真实Windows `_load_windows_api`完成声明后构造类；`kernel32 = kernel32`（以及STARTUPINFOW/ctypes等）在类本地绑定同名标识符，右侧无法引用该函数局部的同名值，会查类/全局而失败。预期返回已声明API表；实际无法构造WindowsApi，main只捕BrokerError也不会映射NameError。静态Python作用域缺陷，未实际执行WinDLL或拿fake平台字符串冒充Windows证据。不能因当前尚未接线而关闭。

### M03 — CreateProcess原语的结构大小、继承权限、64位签名及错误保存不完整

位置：broker.py:412–419、435、443–470、516–526及API声明210–268。EXTENDED_STARTUPINFO_PRESENT时cb应为STARTUPINFOEXW大小，源码却取STARTUPINFOW。CreatePipe安全属性传None，两个管道句柄均不继承；代码仅清除read的继承位，没有给write设置继承位。NUL的CreateFile安全属性也为None、不继承；随后却把三者列为handle-list且bInheritHandles=True。预期全部白名单句柄可继承，其余句柄不可继承；实际列表值虽正确，所需继承权限未成立，真实CreateProcess参数不符合接口要求。

`GetProcessTimes`在:467调用但完全没有argtypes/restype声明，默认c_int不能确保64位原HANDLE参数完整；在新进程已创建但尚未返回原句柄给Core时查询，异常没有自有原process/thread finally。:416把c_void_p返回的INVALID_HANDLE_VALUE与Python -1直接比较，也不保证64位无效值识别。:456、458的DeleteProcThreadAttributeList/CloseHandle不记录失败，错误可被隐藏。预期64位声明完整、首个last-error在清理前保存、部分创建后清理；当前不满足。以上为静态确定的声明/参数缺陷，具体Windows错误码/发生顺序未实测；作者Facade绕过整个WindowsApi，无法证明这些正确。

### M04 — Job查询把内联PID数组声明成指针，可能解引用PID地址

位置：broker.py:208–211、375–393。Windows结构是DWORD计数后跟内联ULONG_PTR ProcessIdList[1]变长数组；源码字段却是POINTER(c_size_t)。QueryInformationJobObject会把首个PID写到内联偏移8，之后 `header.ProcessIdList[index]` 把该PID当作地址读取。非空成功查询可非法读内存/崩溃，无法作为有界同机Job查询。还未核NumberOfAssignedProcesses与返回计数一致性/完整性。预期有界内联数组读取，未知/截断不作为零；源码容量分配有界但访问布局错误。静态ABI缺陷，未做危险指针解引用，也未声称Windows崩溃实测。

### M05 — Assign/Resume失败丢失本轮两个read HANDLE

位置：broker.py:779–831、871–886。两个read句柄仅保存在 `_launch_role` 局部，直到Resume成功才注册reader。Assign或Resume失败调用_abort_round，stop只关闭已注册reader和process/thread/job，局部read句柄永远丢失。预期失败仍关闭本轮全部原句柄；`owner_assign`与`owner_resume`各保留stdout_read102/stderr_read104，无close调用。原process终止权正确：只使用刚创建106原句柄，未接管外来PID、未无Job重试；这不消除pipe泄漏。

### M06 — 取消、诊断、写通道失败绕过owner清理

位置：broker.py:730–749、779–831、913–926、1243–1264、1494–1502。Core只捕BrokerError；KeyboardInterrupt/BaseException到assign时直接离开，Job、刚建原process/thread和read句柄仍持有；`owner_cancel`证明ARMED与五个未清fake句柄。stop在真正terminate之前先 `_collect_stream_counts()`，诊断异常使其留STOPPING且无任何terminate/close；`owner_diagnostic`直接注入该诊断失败，保存九个未清fake句柄。此注入验证合同要求的诊断失败隔离，不是声称正常内存字段自发异常。

Loop没有全生命周期finally：arm后READY write抛BrokenPipeError时Job仍在ARMED，`ready_write_failure`保存Job101；生产main finally只close transport，不执行core.stop。launch后STATUS write失败同样可留下已运行服务直到broker退出，不能靠进程退出/GC替代owner清理证明。预期先确保已拥有资源有界清理，再传播原异常/写诊断；当前路径未实现。未实际取消OS进程。

### M07 — 父start REFUSED/取消路径不关闭原broker

位置：custody.py:550–600、641–660。收到READY阶段或STATUS阶段REFUSED时直接return evidence，未_close_broker；read抛BaseException也绕过仅捕CustodyError的清理。`parent_refused`返回UNKNOWN但原peer关闭次数0；`parent_cancel`抛KeyboardInterrupt，peer关闭0且state仍VALIDATED。预期所有启动失败在本方法内结束本轮原broker/channel持有，不依赖调用方后来记得stop。测试事后只手动close自己造的Peer，原始0次数保留。独立通道/原句柄权力设计正确，失败路径不闭合。

### M08 — 同步写与启动阶段使绝对期限永久失效；心跳/STOP等待也未闭合

位置：broker.py:1164–1168、1243–1278、1384–1385；custody.py:515–548、603–630。StreamChannel.write直接writer.write/flush，父_send和broker_reply均同步使用；对端持有管道不读时可永久阻塞，绝对lease只在_loop中检查，不能中断阻塞写。Loop直到arm、全部launch及两次reply后才固定mono deadline，启动代码阻塞不受lease监督；父read超时也不能保证broker尚未挂起的write退出。

父_session没有周期STATUS心跳/公开poll机制；正常start返回后30s不操作会被broker按HEARTBEAT_MISSING停止，长runtime未形成可用生命周期。stop读取STOPPED的默认timeout是整个remaining runtime（最大21600s），不是固定短清理预算。预期读写/启动/停止都不能绕过固定deadline且父能维持合法心跳；当前只有read-queue的部分等待有界。此为静态阻塞路径分析，本批未挂起真实管道，不冒称Windows EOF或父崩溃测试。

### M09 — Reader/close/退出UNKNOWN事实未参与RELEASED判定

位置：broker.py:529–535、653–671、871–886、966–977、1170–1185、1390–1416；custody.py:641–660。_close_readers等待finished事件但不join，记录alive/error后继续；released条件完全忽略reader alive/error。因此其余条件成功时可RELEASED而reader仍alive或报错；read_stream还把任何ReadFile失败当正常EOF，无法区分未知读错误。reader状态文字可见不等于正确门禁。

StreamChannel.close只关闭writer，未先解除reader阻塞，却先join，再由BrokerProcess等待/terminate/close stdout；reader_finished在stdout关闭前采样且不再join。同步BufferedReader被其他线程read持锁时close也不保证有界（与M08同阻塞根因不另计）。wait超时后terminate没有再次wait确认退出、没有关闭Popen Windows原_handle的明确所有权收口；不能靠GC证明释放。Session_close即使close异常仅追加failure、仍丢弃broker引用且不强制UNKNOWN，已收到RELEASED可继续保留RELEASED。预期结束事实、逐句柄失败与thread存活均阻断release、保留确切未确认资源；当前不满足。此项静态，无真实读线程被本审查留存。

### M10 — SAMPLER固定argv与既有parser不兼容

位置：broker.py:615–628；既有tools/v0_s2_native_sampler.py:167–170及tools/v0_s2_runtime.py:425–435。新broker将多个原owned PID拼成单个参数 `--private-pids '4001 4002'`。既有parser是type=int,nargs='+'，旧owner实际传多个独立参数。COMFY/OLLAMA至少两个PID时新命令一个带空格字符串不能int转换，sampler在参数解析即失败。预期保持既有固定role命令语义、分别传每个PID；实际固定形式错误。静态按真实parser复核，无启动sampler/模型/GPU；sampler仍NOT_PROVEN。

### M11 — 默认nonce与固定broker入口不兼容，错误映射无法保持状态

位置：custody.py:456、554–560；broker.py:1344–1347、1427。Session默认nonce为 `custody-`+32hex，build_broker_command只接受32hex，默认Windows启动必拒；且launch_broker先创建目录/写plan，再检查nonce，留下本可启动前拒绝的文件。_default_launcher抛BrokerError，Session.start只捕CustodyError，unsupported platform与nonce拒绝不会进入预期UNKNOWN稳定错误分支，可能保留VALIDATED。预期父/broker采用同一闭合nonce并在任何副作用前拒绝非法值；实际不兼容。作者FakeBroker接受任意nonce遮蔽此问题。本批显式使用合法nonce，故这里只是静态发现，不把本批通过冒充默认生产路径已测。

### m01 — “sealed”计划嵌套别名仍可修改

位置：custody.py:221–243。sealed仅对role做浅dict拷贝，tools/data与roles共享。`sealed_plan_mutation`将sealed.roles[0].tools[0].path改成foreign.exe，role_command实际使用foreign.exe，原始Oracle FAIL保留。建议深不可变/重新验证并保持digest快照。评Minor而非外部命令执行漏洞：该对象只在可信父Python内部传递，当前无接受不可信回调/JSON赋权的入口，真实broker还会重验序列化plan；本轮没有证明攻击者可取得此内存修改权。不能据此宣布grant越权已发生，亦不能自称不可变封存。

## 原54失败与纠偏32的独立处置

原54批仍 **54call / 46PASS / 8FAIL / 0SKIP，功能45/52、integrity1/2**，仅静态审计未复跑。8个失败逐原longrepr核实：日志盘符为生产validator缺陷；2个tuple越界是Fake create_job记录少handle；3个稳定码断言是Fake私有码与WindowsApi源码码不同；STOP帧数错误是测试假设主动STATUS不存在；coordinator摘要末位b为作者测试抄错。新Fake映射create_job/job_limit/create/assign/resume/terminate/query_job/close/pipe等逐生产raise位置一致，不通过删码断言放宽。重复STOP新断言核恰好一帧、sequence1、第二次不新增、broker只关一次，合理。

这只能关闭原失败根因，不能关闭M03/M04/M05等未被旧断言观察的生产漏洞：原测试只看process/thread或常量，没有穷尽实际pipe/ABI。错误分类中的“测试缺陷”与“同一生产失败分支还存在新清理缺陷”可同时成立。

纠偏实际root批仍 **32call/32PASS，30功能+2integrity**，不是54全绿。evidence-audit确认精确commands/raw hashes、collection顺序、实际root三执行件pins、223命名依赖文件、FD身份、MainThread、counter前后事实匹配。名称/常量存在/OLD_OWNERS完整性两项只算integrity，不等于生产功能通过。

root validation-plan-01/reply-body.txt原先已给正确coordinator末位c；原错归因在NEW作者报告中纠正，本审查不改旧report。原54 receipt bytes sha256 `5a8e96c027c5500e4c6834b561dc187ee437a85e431eec63145f161728cb32b2`，整份json.loads有效，尾部正常换行，无需修旧JSON。旧报告/收据/原失败均保留。

## 冻结义务覆盖与未证

| 冻结义务 | 审查结论 |
|---|---|
| 精确plan keys、int-not-bool、finite、SHA、固定角色、无argv/env/PID键 | 静态结构存在；M01边界和m01别名保留；六类坏log独立拒绝通过 |
| 预算正数、runtime<=21600/父remaining、期限只收紧 | validator与Session固定min存在；broker启动/同步write/STOP有M08，不是完整期限通过 |
| COMFY/OLLAMA/SAMPLER固定角色命令与环境 | 无任意shell/CLI façade序列化，环境复用受控变量/剔除规则；M10 sampler不兼容；授权真实性仍NOT_VERIFIED，不把path/hash自报当grant |
| 原始创建HANDLE、Suspend→Assign→Resume、无breakaway、KILL_ON_JOB_CLOSE | Core成功调用次序独立观测成立；失败仅原owned process，未见外PID收养/无Job重试；实际Windows原语受M02–M04阻断 |
| 句柄白名单/64bit/last-error/Job计数未知超限 | 设计列表存在但权限/结构不正确M03–M04；Core对Facade查询未知/超限不作零的静态分支存在，不能代替真实ABI |
| 部分创建、Assign/Resume失败、关闭失败、取消、诊断隔离 | M05–M07/M09未闭合；原关闭失败分支标UNKNOWN可见，仍不能声称所有原句柄清完 |
| 通道nonce/身份/seq/闭合键、frame/count/stdoutstderr/证据界限 | strict JSON duplicate/NaN拒绝、seq严格递增、32KiB/1024/256KiB/8MiB常量与大多数检查存在；M08/M11、M09仍阻断实际通道生命周期 |
| EOF/绝对lease/心跳/超限/STOP | Loop有停止分支，重复STOP静态幂等；同步write/启动/心跳未闭合，WindowsEOF/父崩溃不实测 |
| 父原broker及独立通道，不把worker PID/JSON/platform/hash赋权 | 结构保持，未见PID重开/全机枚举/杀名；M07/M09资源关系错误，不能用CHILD_CLAIM或自报exe补证 |
| 旧native拒绝、M08已接受owner冻结 | 原有265源比对与候选差异确认冻结，只有已批准CMD换行呈现例外；未回归旧套件，不回填旧门禁 |

所有native执行/清理、GPU释放、端口、sampler、父崩溃恢复、Windows stdin EOF仍 **NOT_PROVEN**；grant_authority **NOT_VERIFIED**，admission=false。模型动作与预算余额、质量/I24/产品12、真实native/Windows/A06、原ledger与人工签署均未证，不读取原ledger，不批准下一真实运行。

## 交接十字段与完整路线

当前坐标：根control R1/WP-R1-U3/RUNNING（S3_P4离线准备）。本批完成：完整N1源码/原证据独审和一次11case受控验证；审查工作完成、产品CHANGES_REQUIRED。最后通过门禁：既有统一切片live15/人工签署范围，仅沿用control，不新增本审查PASS。当前阻塞：上述11Major，随后仍有N2/N3/N4与固定产品门禁。全局位置：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3(V2)0/4、R4(V2)0/4、R5a(V3)0/4、R5b(V3)0/4、R5c(V3)0/4。剩余工作：由root集中裁决并冻结修复，不自动复跑；原Stage机器/独审/人签区分保留。下一责任人：root架构门禁owner，随后实现owner。所需授权：本审查既有一次ACK已消费，无新增人类授权请求；真实运行另有限绑定。证据目录：本NEW目录及根原received，只读旧件。精确停止原因：独审完成CHANGES_REQUIRED，唯一批次已用，不追加测试/源码修改，worker_done后由root回收。
