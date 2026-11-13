# N1纠偏02：完整独审11Major+1Minor集中修复

候选9352a34cfa8ea9715437b5ffa5d411369dd5548d、交付/起始HEAD8504fd6cab519ce33cea5382f7b3d8405667f479。独审msg_287dbc62810a F0/M11/m1；本包全部采纳，原11探针2OraclePASS9FAIL保留；此前54失败与32通过事实分别保持，不回填StagePASS。根已依据Microsoft原文复核内联Job PID数组、扩展STARTUPINFO大小、可继承句柄要求（见official-api-references.md）。旧N1架构/门限与安全原则不变。

只允许tools/v0_s3_native_custody.py、tools/v0_s3_native_broker.py、tools/test_v0_s3_native_custody.py及NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-02。所有旧controller/worker/QualityPhase/supervisor/runtime/driver/authority/公共合同/协议/阈值/control/MANIFEST/旧报告禁止改；原本未接线的native入口继续拒绝，真实Windows/GPU/服务仍不准运行。唯一ClaudeCode实现者，不派生Agent。三个段连续静态实现，同一批定向回归后一次集中独审，不逐缺陷反复验收。

## A：闭合计划与Windows API声明（M01/M02/M03/M04/M10/M11/m01）
M01 user_directory不能前缀match：完整字符串fullmatch且明确长度<=64、拒任何分隔符/冒号/..片段和Windows设备/绝对/ADS；只允许一个受控目录名，而不是接纳任意子路径。合法默认user保留，读取后同根封存规则不变；无副作用前拒绝，日志已修边界保持。
m01 validated plan深复制并与规范化封存bytes/hash保持一致；对外呈现副本/只读view不得改变内部roles实际命令。不能修改sealed嵌套tools/data后让role_command吃新exe。选择最小一致方式，不另造schema平台。
M02 _load_windows_api使用显式namespace/赋值，避免class体同名闭包NameError。分离纯声明/布局构造和实际WinDLL加载，以便不调用WinDLL也能检查实际声明路径；typed façade不能绕过所有声明逻辑后声称ABI已证。非Windows默认不加载实际native表，勿用伪造平台字符串解锁。
M03 完整64bit argtypes/restype（包括GetProcessTimes/CreateFile/CreatePipe/attribute/CloseHandle等），HANDLE/pointer/SIZE_T和32bit DWORD/BOOL的类型必须按Windows ABI。EXTENDED_STARTUPINFO_PRESENT时cb=sizeof(STARTUPINFOEXW)，必要继承write端/NUL句柄设可继承，read端与job/控制句柄不可继承，STARTUPINFOEX handle-list为精确白名单；无伪句柄。INVALID_HANDLE_VALUE按指针宽度识别。首个last-error在任何清理前保存；已CreateProcess成功但后续birth查询/属性清理失败时，原process/thread由本方法独立finally保留或终止/确认/关闭，不让尚未移交Core的句柄丢失。API返回失败、partial结果和CloseHandle错误具名保留，不用GC。禁止改变CreateSuspended→Assign→Resume安全顺序。
M04 Job PID结构为两个DWORD后内联ULONG_PTR数组，不是指针字段。按固定有界cap（原17）申请buffer、用返回长度和字段计数确认完整；NumberOfAssignedProcesses>returned/inconsistent/truncated/超限/查询错误均UNKNOWN，不猜零、不无限扩容。off-Windows声明/二进制布局可有纯测试，但不允许危险指针解引用或真实WinDLL调用。
M10 SAMPLER --private-pids按既有parser type=int,nargs='+'分别传每个PID，不能拼一个空格字符串；精确复核其余固定argv，失败不静默改生产sampler/parser。
M11 默认nonce采用双方一致32hex，非法nonce/角色/平台/参数应任何mkdir/write/launch前拒绝。保持固定--nonce私有启动参数，不扩任意CLI；父映射BrokerError为具名结构化UNKNOWN或启动前REFUSED，不能未收口异常留下VALIDATED/丢原句柄。nonce不授予进程托管权。

## B：资源生命周期统一收口（M05/M06/M07/M09）
M05 每个本轮创建的read/write/process/thread/job/NUL/attribute/控制handle在创建成功瞬间进入明确owner的pending资源表，移交reader或Core成功后才转移owner；Assign/Resume之前失败仍关闭其read端，部分创建/异常/取消都有准确持有关系，不能只处理process/thread而遗漏管道。未知外来句柄不碰。
M06 Core arm/launch/stop、Loop从arm开始到READY/STATUS/STOPPED写入、production main全生命周期都有不依赖诊断/写消息成功的独立finally。普通Exception→结构化UNKNOWN及primary/secondary；KeyboardInterrupt/SystemExit清理后继续传播，首个错误不被收据失败覆盖。terminate/关闭先确保执行，_collect_stream_counts/日志/fact等失败不阻断；不无限重试，不只捕BrokerError，不靠broker进程退出代替owner清理。
M07 parent Session.start收到任一阶段REFUSED/timeout/parse错误/普通异常或BaseException，均必须收口自己持有的原broker/channel；取消继续传播。若关不掉保留原broker精确引用和UNKNOWN，不能直接return/丢引用。caller无需靠“以后记得stop”清理start失败。
M09 RELEASED需要所有本轮owned process退出已确认、handle关闭已证、reader实际join完成且无未处理读错、通道/原Popen关闭与退出已确认；保留UNKNOWN资源清单，不看daemon或存在文字字段就通过。ReadFile仅明确broken-pipe/已取消/EOF分支算预期结束，其他错误未知。stop后wait超时只可终止原持有broker，再有界wait确认；句柄是否关闭由真正owner记录（按平台显式，不能靠__del__）。close失败不清空未确认引用、不沿用RELEASED。重复stop不双关/重发，保留失败而非吞掉后成功。

## C：deadline/通道边界（M08，连同M09）
绝对lease/monotonic deadline在arm/launch/首次reply之前确定，只能缩短；startup/每个受控操作/清理均受剩余时间或固定短清理上限约束。STOP等待使用独立短cleanup预算<=原5s，而不是整个剩余21600s，不产生无授权新宽限。父需有明确可用的STATUS heartbeat/poll owner，从start至stop自动有界保持；不能30s不操作就误停合法长任务，也不允许heartbeat延长绝对deadline。后台生命周期线程失败必须可见并停止/UNKNOWN，不能新增无限运行worker池。
同步writer.write/flush不能无限阻塞监督者；不得只包daemon线程超时后丢弃该线程。为parent/broker私有管道提供deadline-aware读/写与精确取消/关闭能力，Windows阻塞操作须用可取消的原生I/O或等效有界机制、POSIX受控原FD可用非阻塞/poll；不要依赖另一个线程持有BufferedReader锁时close能返回。保留原有frame32KiB/count1024/stream256KiB/evidence8MiB与Job约束，不增网络端口。通道传输若必须最小内部接口变化，允许在本三源内增加send/receive/close的deadline/原句柄证明参数；不能改旧worker协议/1或引入任意path/SQL/Shell接口。
在具体实现前可用Orca ask一次提出有界transport方案（原语、哪些thread能取消、失败保留、deadline传递），不允许运行其试探动作；root在现有授权内裁决，不求人类重复批准。不提供“Windows目前未证所以默认无界可接受”捷径；同时最终仍不声称fake验证了Windows stdin EOF/父崩溃真实语义。

## 验收与证据
NEW报告逐11M+m映射生产函数→驱动→明确Oracle→正负例→原始终态→清理。静态检查应覆盖实际API表声明/结构/签名路径，不只让Fake返回正确故事；可在不加载WinDLL的纯声明构造里注入原语表。所有typed fake构造要能逐句柄记录、故障点与真实原语码一致。不得将空liveFake表替代真实线程终态，不能依赖作者测试清理代替产品返回时收口。
因本轮三个N1源均实质变化，允许一次完整当前N1相关子树回归加必要新负例，作为同一有限批次；这不是重跑历史54/32以改历史结果，也不执行旧M08等无关大套件。实现前只静态/AST，禁止候选/pytest导入；完成后先冻结精确nodeid集合/顺序、源码工具/原223命名依赖文件pins、绝对argv/cwd/<=300s、前置guard、raw logs、FD身份/线程，再askroot ACK一次执行。旧作者54失败/纠偏32通过/独审11的2PASS9FAIL不改写；实现者只READY_FOR_REVIEW，集中独审关闭后root才裁决N1范围。
前置guard拒所有OS进程/socket/fork/exec/spawn/system/sqlite/原ledger/counter及真实native库加载；只进程内typed façade/合成文件。若纯ctypes声明构造测试涉及stdlib自加载，先提出准确有限方式，不擅自放开WinDLL/ctypes.dlopen/dlsym，不用伪造Windows平台。原counter仅guard外前后只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98 inactive28/240/12.362，不写退款清零新建/复活。无真实WindowsAPI/Job/服务/模型/GPU/native/媒体/浏览器/网络/下载；I24/产品12/A06/质量/原账本余额/人签仍未证。FIRST429停WAIT_BUDGET不retry/切路由，FIRST审批拒绝或超时停askroot不包装绕过。旧工件/报告/CRLF例外保留，不clean/reset/批量add。
