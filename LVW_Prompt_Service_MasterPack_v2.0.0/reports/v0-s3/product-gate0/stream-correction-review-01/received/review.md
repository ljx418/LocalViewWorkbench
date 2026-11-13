# 独立流与 fixture 纠偏审查 01

结论：**CHANGES_REQUIRED，Fatal 0 / Major 2 / Minor 1**。候选 `626d37cf59bfc69324c1a9f886a65cd3f8c56964`，基准 `01453ee07b4774a55711c5cf5642c12d0394a35c`。这是限定零进程审查完成，不是候选通过；`stage_pass_claim=false`、`product_gate0=false`。

审查者未参与实现、未派生 Agent。先阅读 root AGENTS、治理/parallel-execution、当前 control、冻结 offline 合同和本轮 decision/contract，以及 final04 原始 receipt/内外 stdout/stderr/outer returncode；先读源码并独立取证，最后才阅读作者 report 与首轮模块失败日志。作者的 19/35/121 等计数没有作为通过证据。

## 发现（一次汇总）

### M1：最后 drain 未证明完成，未决流仍能发布可归档成功

位置：`tools/v0_s3_supervisor.py:561–580`（尤其 572），调用链 `run:553–558` → receipt 核验 → `evidence:728–780`。

触发：父读到合法 TERMINAL，canonical receipt 实际存在且 hash/长度一致；fake 原句柄 poll=0，但真实 os.pipe 的 stdout/stderr 写端仍打开，两个实际 `_StreamReader` 阻塞在 read。先确认 TERMINAL 的 381 bytes 已入 reader，再调用生产 `run()`，消除入口轮询的调度歧义。这个 fake 句柄只模拟产品 owner 对停止的观察，不启动任何 OS child，也不推断真实 descendants 已清理。

预期：`finished.wait()` 返回 false 时保留未决 I/O，禁止 archive/next phase，保留根/预约，不能以 daemon 属性证明清理。等待预算应受既有 child/session 边界约束，不能为 drain 增加固定额外生产期限。

实际：两个 wait 各超时 0.5s，**返回值被忽略**；约 **1.0005s** 后 `canonical_receipt_verified=true`、`protocol_violation=null`、`unknown_outcome=false`、`root_retained=false`、`archive_allowed=true`、`next_phase_allowed=true`，两个 reader.finished 均为 false。注入 child deadline=0.04s，返回已越过此固定截止，未登记 deadline 拒绝。`cleanup.proven_stopped=true` 仅来自原假句柄 poll=0，不能证明 reader EOF；native cleanup 仍为 false。

更直接的晚到证据：在上述成功结果已返回后，继续向原 stderr pipe 写 262145 bytes，原 reader 随后真实置 overflow，`_stream_failure()` 为 `STDERR_STREAM_LIMIT_EXCEEDED`，而已经返回的 evidence 仍声称可归档且 stream_violation=null。探针随后关闭自己的写端并等两个 reader 完成，不把 daemon 留到退出当清理。

同类完整性缺口：真实管道已 EOF 时，TERMINAL 后跟 14 bytes 未闭合 JSON fragment，`stdout_buffer` 仍有 14 bytes，`_drain_streams` 也未拒绝，archive/next phase 仍为 true。这属于本轮“终局未决数据未 fail closed”的同一发现，不额外计数。

复现：`final_drain_probe.py` 经本目录 `hardguard.py`；精确命令/真实 rc=0 见 `independent-final-drain.outer.command.json`、`.outer.returncode.txt`，原始输出和 JSON 见 `independent-final-drain.outer.stdout.log`、`final-drain-observation.json`。探针 rc=0 意味其断言成功复现缺陷，不意味着产品通过。末尾 partial 证据另见 `independent-observations.json: terminal_trailing_partial` 与第二轮原始日志。

初次较宽探针观察到约 5 秒：已有 process-exited 分支会先各等 2s（未改 source），再进入新增两次 0.5s drain。专门复现已预先等到 TERMINAL 入队，隔离出**新增 drain 自身的 1s**；不把原 4s 等待归咎本次新增代码。

### M2：有界完整帧可在 retain/take 并发交接中失去解析机会

位置：`tools/v0_s3_supervisor.py:315–322`（新增 `_retain` 与既有 `take` 的交接）。这是本轮“不丢预算内帧”义务仍未达成；不声称仅凭没有 lock 或旧 take 已存在便判 Major，也不声称自然调度高概率复现。

受控调度：Python 3.12 `sys.monitoring` 只对生产 `_retain.__code__` 开启 INSTRUCTION 事件，在 offset 46 的首个 CALL 前暂停 reader，此时旧 `chunks` 列表的 bound append 已在执行栈上。父 `take()` 把空旧列表换走并 join 返回空；释放 reader 后，真实 list.append 把块放进那个已经被消费的旧列表，`received.append` 仍记录全块。随后父再 take/`_consume_stdout()` 也无消息可读。

使用真实 os.pipe、真实 `_StreamReader.run/_retain/take`，没有替换 chunks 为自定义列表，也没有修改产品函数。wire 是生产 canonical JSON 编码的合法完整 STARTED（**243 bytes**，4/40/64 身份、7 keys、sequence=1）；期望父解析1帧，实际 `parent_message_count=0`、两次 take 都0、reader.total=243、raw received=243、error=null、overflow=false、finished=true。hash/total 的存在不能替代帧已经进入 ProtocolState。

复现：`handoff_probe.py`；`independent-handoff-final.outer.command.json`、原始 stdout、`handoff-observation.json`，真实 rc=0。监控只提供可重现合法交错，不证明未插桩解释器的发生频率；这是一条受控调度证据，不是“无锁所以必有 Major”的猜测。原始 sys.settrace 方案未产生 opcode 事件、未建立调度；两个 rc=1 和一次 paused=false 的诊断全部保留，不作为竞态证明。最终用实际 opcode monitoring 建立调度后才列此 Major。

建议限本轮解决：对 `_retain` 和 `take` 做短的共享同步/原子队列交接；不要把 os.read、等待或外部回调放进临界区。

### m1：超限时摘要实际是预算内 prefix，报告却称 all-received

位置：`tools/v0_s3_supervisor.py:301–307,324–326,744–750`；作者 report 2.4 节明确称 `stdout_sha256=hash(全部已收字节)`。

真实 reader 从 os.pipe 观察 262145 个相同字节时，total=262145、raw retained=262144、overflow=true。报告的 hash 是前262144 bytes，**不是 all-observed 262145 bytes**；两端 stdout/stderr 均已实测。`stdout_bytes_retained` 另指父尚未消费的 bytes（消费后可为0），也不表示用于 hash 的 prefix 长度。

证据：`independent-observations.json` 的 stdout_over_reader/stderr_over_reader，包含两个不同摘要；`boundary-parent-observations.json` 的 stdout_over 在15帧解析完成后也显示 wire_sha256 与 reported_stdout_sha256 不同。超限本身仍拒绝，因此列 Minor；修正只需如实标明 digest scope/hashed bytes，或采用有界增量 all-observed digest，不要求保留无界原始流或继续无界读取。reader 在首次超限块后停止，total 也只是该 reader **实际观察**的 bytes，不是子方完整发出量。

## 通过的限定复验与保留项

| 检查 | 本次证据及边界 |
|---|---|
| 精确新增集合 | AST 从基准独立求差，18个新增函数，集合与 root 名单一致；生产无 binding runner 用 `--mode suite --modules <18个精确nodeids逗号连接> --label independent-stream-focused --outdir 本目录`，**18 PASS / 0 skip / 0 deselected**，外层 rc=0；没有机械重跑全模块或旧大量集合。 |
| 一次 guard4 | `independent-guard`，4/4拒绝，rc=0；外层独立 pre-import hook 先于 runpy/任何候选 import，进程和网络事件直接拒绝。runner 仍有自己的单 owner hook；外层是零进程防线，不用于有 binding 的真实启动。 |
| NaN | 真实 Writer/scenario 生成单个闭合 JSONL、NaN 保留，生产 decode 与真实 pipe ParentSupervisor 均得到 `MESSAGE_NONFINITE_NUMBER`，message_count=0；没有 timeout 换绿。 |
| raw/partial | write_raw 原样写入；blocking_persistence 仍只有前面的 STARTED 完整，尾部故意不完整。选择集验证原 phase timeout 拒绝。 |
| flood | 独立生成**1025合法完整帧**，首 STARTED，其余空 PROGRESS，逐条 decode/闭合7keys/sequence/identity；空root下完整1024 wire=**251863** bytes，1025 wire=**252110** bytes，最长含换行286 bytes，均在32KiB/256KiB内；root 字符串只增加首帧长度，所以不强行复用作者252162数字。实际父读路径第1025条得到 `MESSAGE_COUNT_EXCEEDED`，已接受count1024，stdout_overflow=false。 |
| 1024 exact | 生产选择集确实执行 exact1024+TERMINAL+真实canonical receipt验证成功，不以名字存在代替。独立 ProtocolState 也接受前1024。candidate40/auth64未缩短，syn1仅合成负例；源码上下文 `fixture_context`、`run_fixture`、该参数化用例父与子同用run_id，不替换production身份链。 |
| stdout/stderr exact/over | 补充 `boundary_parent_probe.py`：stdout **262144** bytes 是15条全部合法的帧并含真实canonical terminal，正常archive=true；262145 bytes → `STDOUT_STREAM_LIMIT_EXCEEDED`、archive=false。stderr exact262144及over262145与合法stdout terminal组合，分别正常/`STDERR_STREAM_LIMIT_EXCEEDED`。均通过真正reader和生产run，不靠本来非法的长行做唯一oracle。 |
| read error | 真 `_StreamReader.run` 对受控 stream.fileno 抛 OSError，两端及时得到 `STDOUT_STREAM_READ_FAILED` / `STDERR_STREAM_READ_FAILED`，只调用原fake句柄terminate，禁归档；不等生产10800s。 |
| TERMINAL + late failures | 选择集同批terminal/overflow拒绝；独立真实pipe在cleanup时释放的late stderr overflow拒绝；受控 finished.wait 发布四种late stream错误且返回true时均被drain识别。**wait=false情形未通过，见M1。** |
| 同时违反的优先级 | `_consume_stdout` 在 stream 检查前；受控 malformed JSON+stdout overflow实际得到 protocol=`MESSAGE_NOT_JSON`，stream_violation另记stdout limit；不是作者泛称的“时间先到”。不改旧期望码换绿。stdout先于stderr，单stream overflow先于read-error是 `_stream_failure` 的确定顺序。 |
| 记账及有界 | 正常exact流消费后pending0，但stdout_bytes=262144、摘要与完整wire一致，不再把消费后空缓存当流为空。raw保留每端≤262144，chunks保留每端≤262144，parent buffer有限且message_count≤1024；副本和元数据有固定上界。没有输出原始flood/大blob到报告；本目录所有文件合计见integrity清单。hash scope缺口见m1、交接丢帧见M2。 |
| fixture导入/入口 | fixture顶层没有安装hook/导入产品；`__main__` 真实接线先install_boundary_guard再main，main调用scenario，Writer/product才lazy导入production。collection实际导入BOUNDARY_GUARD_INSTALLED=false，新增四项相关测试均执行；不以常量存在证明接线。BLOCKED_EVENTS未放开。 |
| 旧边界 | 除三源及实现报告外diff无新增生产变动，executor/runner旧七项审计、顺序结算的source未改；本轮仅静态比较其不变，没有谎称重新执行七项。10800/600/21600、32KiB/1024/256KiB和固定24/公共合同/control/MANIFEST未改；补充生产默认值及history不重设检查成立。新增drain的deadline缺口见M1。 |

## 原始命令、失败与审查限制

外层是本目录 `hardguard.py`，其源码在任何候选 import 前安装不可卸载审计 hook，拒绝真实进程创建/网络；允许 os.pipe、线程、synthetic sys.audit。完整实际 argv/cwd 记录在各 `.outer.command.json`；runner effective_command 只表示被包裹的候选入口，不能冒充外层实际 argv。外层 `.outer.stdout.log/.outer.stderr.log/.outer.returncode.txt` 与runner `.stdout.log/.stderr.log` 永不共名覆盖。

| 外层标签 | 实际rc | 含义 |
|---|---:|---|
| independent-guard | 0 | 一次guard4全部拒绝；无binding |
| independent-stream-focused | 0 | 恰好18项全部通过，无skip/deselect；新真实fixture运行数0 |
| independent-negative-probe | 1 | 前面负例日志有效；最后sys.settrace调度未建立，harness断言失败；不是候选PASS |
| independent-negative-probe-02 | 1 | 仅为修正调度初始化重试，仍无opcode事件；全部原始失败保留，不据此报竞态 |
| independent-handoff | 0 | 诊断sys.settrace只有call/line事件，paused=false；**不是竞态证明** |
| independent-handoff-monitor | 0 | sys.monitoring实际建立交错，初始15bytes诊断；尚非协议帧 |
| independent-handoff-final | 0 | 最终243bytes合法协议帧+生产父consume证明M2 |
| independent-final-drain | 0 | 专门证实M1及返回后真实late overflow；主动收束所有pipe线程 |
| independent-boundary-parent | 0 | exact/one-over合法协议父读路径与旧固定期限小量补充 |

初始两个失败探针脚本版本在 `independent_probe_attempt01.py/attempt02.py` 按编辑内容恢复保存，用于解释失败；这些重建版本不冒充当时额外封存的hash见证。原始失败日志始终未改。独立观察JSON来自第二失败轮在每个case完成后写盘，race断言前已有真实观测；最终race/drain/boundary另有完整rc0命令与输出。

原 final04 的全部收到文件逐字复制在 `historical-final04/`，完整hash列入integrity。原始 rc=1、11PASS/2FAIL、13真实持有句柄只属于01453ee；两处实际均为PHASE_DEADLINE_EXCEEDED，期望分别NaN/count码。**没有执行新候选真实13，不复用成新PASS。** 作者首轮模块stdout确实保存late-overflow失败（None vs limit码）；本次只读对照它，不复跑全模块。作者“新增19项”与独立AST/实际18不一致，本报告不继承该计数；作者对daemon清理、all-received hash和drain完整性的表述被上述实证限制。

绝无新fixture子进程、网络/模型/GPU/服务/原ledger动作、binding runner、预算退款/清零/新counter/重跑。运行测试解释器本身是外层命令，不计作fixture启动。原counter前后sha256均为 **8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18**：inactive、starts15（implementation15/review0）、reserved180/180、spent8.446、3SETTLED、旧2REFUSED_BEFORE_FORK及新13STOPPED未变，见 `counter-integrity.json`。没有基于spent推导可退预算。

源hash详见 `source-hashes.json`，三个候选文件均与候选git blob逐字相等：supervisor `5d237cb16c4ed529093f1494ca9972bb59ccfd8e06a70c9fc5287db5dd5fbf7d`；fixture `1432a6503c07ebed43e9ce36100c18f9840e51af5f6c8d81472ab7439a66df4a`；test `f8ddc380fb52d675e1117494f146b173ddf65172b18058821bf75d20bd53c43f`。runner before/after与候选相等，独立选择集receipt保存运行前后所有source哈希。

最终校验：全部历史复制件与root逐字相等、manifest所列hash全部相符、counter再次复核不变。`git diff --cached --check` / commit后`git show --check`发现原final04 argv一行及原pytest输出两行的历史trailing whitespace；按原件逐字保留要求未清洗，详见 `final-verification.json`，不虚称该检查全绿。

工作树初始HEAD=`be364409bc1a5df874504656e528b5b8cd514541`，git status干净。**流程偏差**：第一次状态落盘误用不存在的`python`，同一shell后续checkout仍执行，故未达到“先落盘再checkout”的顺序要求；本报告据第一条工具的真实输出追记 `worktree-before.json`，不虚称预先落盘。之后只在本NEW目录写文件、未reset/clean/fetch、未修改root/实现树。该偏差不改变候选源码/测试结果，但作为审查操作限制保留。

本轮完成审查，不签候选或Stage通过。真实13、固定全24、Windows/GPU、A06、原ledger、native descendants清理及StagePASS全部 **NOTPROVEN**。这里的controlled fake handle只证明生产父分支，不证明真实进程custody/清理。

## 当前项目坐标与交接

以下完整大纲只抄自本次root control的 `development_outline`，未增记产品进度：

| 交付 | 阶段 | 已完成/总数 | 状态边界 |
|---|---|---:|---|
| V0 | S0 | 1/2 | 历史NO_GO |
| V0-Min | S1 | 5/5 | 已签仅本范围 |
| V1前置 | R0 | 1/2 | 仅单图子集 |
| V1早期 | R1a | 5/5 | 已签仅单图 |
| V0.1 | S2 | 7/8 | 机器/独审完成，旧范围人签待 |
| V0.2 | S3 | 0/6 | 正式交付未完成 |
| V1（当前） | R1 | 0/4 | UM10早期3/3已签，完整R1待 |
| V1 | M1 | 0/3 | 多镜头设计阶段 |
| V1 | R2 | 0/4 | 未正式交付 |
| V2 | R3/R4 | 各0/4 | 后续范围 |
| V3 | R5a/R5b/R5c | 各0/4 | 后续范围 |

1. 当前坐标：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION，RUNNING。
2. 本批完成：独立限定零进程审查，F0/M2/m1，报告与复现证据提交；实现READY_FOR_REVIEW不等于机器/独审/人签PASS。
3. 最后通过门禁：UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW，621b1bf…，只限已签统一切片。
4. 当前阻塞：S3_P4_STREAM_FRAMING_LIMIT_FINAL_DRAIN_INDEPENDENT_REVIEW；本候选需修复M1/M2。
5. 全局路线：S3-P4离线纠偏仍在原V1衔接路线，V2/V3不激活。
6. 剩余：实现处理已证问题后交root集中裁决；真实13/full24及硬件/账本证据保持NOTPROVEN。
7. 下一责任人：root协调原实现者修复；本审查者不改候选。
8. 授权：本次零进程审查无需新增人批；不派生任何真实预算。
9. 证据：本NEW目录，`integrity.json`绑定所有文件；counter前后不变。
10. 精确停止原因：审查任务完成，候选CHANGES_REQUIRED，等待root归档/回收窗口；不keep-open。本工作区只有已知本审查实例1个，无派生/本轮回收0；全项目其他空间生命周期未在此任务重新盘点，不虚报总存活数，root在worker_done后负责归档回收。
