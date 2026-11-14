# N1 66600a1 非最终独立静态预审

**建议 CHANGES_REQUIRED；本范围静态 Fatal 0 / Major 6。六个 Major 均有剩余可达生产缺口，按 M03/M05/M06/M07/M08/M09 各合并一项，不对子路径重复计数。** 这不是 Stage 裁决、最终独审、动态复算或新运行许可。修复子项在下文明确标 CLOSED_STATIC_WITHIN_SCOPE，不能把本结论理解为原修复全无效，也不以 137/175 数量裁决。

候选仅为 `66600a1bd692c0149fc7724b624997bf2f40dcc1`。B 指 candidate/v0_s3_native_broker.py，C 指 candidate/v0_s3_native_custody.py；所有行号是保存的候选原 blob 行号，numbered.txt 可逐行复核。两源从实现库 `git show <commit>:<path>` 读取，未读取正在改动的 test09 字节来形成生产结论。

| 源 | SHA256 | 原 blob |
|---|---|---|
| B | 06cf8da96b681cc7430d48cad6187790aea132e738896f29345e3ec3b41e1913 | 见 candidate-pins.json |
| C | f8191be1ce25b9b859a3471a3c91e61a1f5821a16a4096989b9c24d76e691e34 | 见 candidate-pins.json |

## 边界与证据

已读根 AGENTS、governance README/roles/anti-false-green/parallel-execution、control、docs24；correction07 原完整 F0/M6 报告、contract/18 义务；correction05 contract/24 义务；correction08 contract、close-cancellation-decision-01 与 error-evidence-preservation-01 两后继决定、counter-lifecycle-correction-01、validation-plan-02 的 JSON/ACK。authority-hashes.json 绑定原件；历史报告只用于缺口分母和义务，不继承其候选结论。

最新 raw 只读自 `native-custody-correction-09/correction08-artifacts.zip`；逐成员哈希、收据及 F5 摘取在 raw-intake-audit.json。plan SHA256=`0e6c5fceaf017618dc53ab5b42f4d44bace38879c374a193fc30ff151a169696`，175 selected/collected 顺序与 plan 相同，175 call、174PASS/1FAIL/0SKIP、exit1、35.36934161186218 秒、批末 cleanup=true。原 guard runtime_denials=[]、可信 preload 后 CLOSED；这些是封存作者运行事实，本审没有重跑或把它签为独审通过。

F5 主场景真实类组合有第一 stop 原 thread HANDLE 未释放/retained=1、第二 stop retained=0/原 HANDLE 释放、broker 不再保留，cleanup_deadline 相同的事实。局部事实有效，不外推其他启动/取消/清理分支。失败子场景 raw 的来源是 CHANNEL_CLOSE；缺 external_cancel_published 同步，不能证明 external 先于 close，更不能据此凭空认定生产吞错。外部取消第二 stop、普通错两 stop、partial frame 两 stop 尚未执行到，不计 PASS。以下 M09 发现来自另外的明确候选控制流，不以这个失败 raw 当证据。

本审只执行 Git 只读、文本/JSON/AST/哈希操作。候选 import/collect/pytest/probe/作者脚本执行均为 0；未调用真实业务进程、Windows API、Job、GPU、模型、服务、网络/socket/sqlite、下载或用户媒体；未读、重建原 counter/ledger，未申请动态 ACK。历史原 counter 连续性仍 UNAVAILABLE_NOT_PROVEN，旧 grant 仍 EXPIRED_NO_REPLAY，封存 absence 不是当前余额核对。工具进程只是本审 Git/静态解析与最终 Orca 回报，不是候选业务执行。

## M03 — API 局部控制 HANDLE 修复成立，Core 仍在未确认退出时关闭最后控制 HANDLE（OPEN）

**确定位置：B2789–2830、B2839–2877、B2680–2700、B1814–1879。**

已闭合子项：B900–1006/B1332–1394 将 API 的 exit confirmation 与 CloseHandle 分开；Terminate/Wait 未确认时 process 留 API 表，thread 独立处理，release_retained 后续可恢复。B1254–1309 保留 primary 与 `lvw_cancelled` 原对象关联；release_retained 收集取消后抛首对象。这些不再按原 API 缺口重报。

剩余触发：Core 已取得一个原 process，assign 失败（该 process 尚未进 Job）或 stop 的 wait_process 返回 False/抛 ordinary/KI/SystemExit，record.exited 仍 False。Core.stop 仍继续 release_records，B2852–2858 对 thread/process 无条件 `_close_handle(kind, handle)`，未检查 `record['exited']`；成功即 pending.take、record[key]=None。即使在 release_records 增加简单跳过，末尾 pending pass 当前也只保护 reader，不保护未退出 process。

预期：未确认退出的 process 原控制 HANDLE 留在具名 Core/record owner，后续原 deadline 内仍可 terminate/wait；实际：CloseHandle 成功即可消掉最后控制引用，而 process 可以继续存活，尤其未分配 Job 的 suspended child。Job close 不是该未分配进程的补救。UNKNOWN/错误字符串无法恢复原 HANDLE。

原 blob 直接证据：`for key, kind in (('thread_handle','thread'), ('process_handle','process'))` 后只有 handle-is-None 检查即 close，随后 `if closed: record[key] = None`。不是把 handle live 等同 process live 的 fake 推断。

最小建议：在 record/pending 共同 close eligibility 中要求 process EXIT_CONFIRMED；未确认时原 handle 留表/留 record。thread/pipe 仍独立安全收尾；恢复确认退出后统一通知各表并只关一次。未来最小独立 probe：实际 Core 类 + 原语 facade，assign 拒绝、terminate 拒绝/Wait False，但 CloseHandle 本可成功；断言 process close 调用为 0、原对象可达，再放行退出只恢复一次。本审未运行。

## M05 — 顺序 handover 已修，但 API recovery 不参加同一所有权临界区（OPEN）

**确定位置：B855–878 与 B964–995；实际交接入口 B2059–2088/B2223–2235。**

已闭合：Core 收到 pipe pair 后通过 WindowsApi.handover 在 `_table_lock` 下 register + forget，正常成功后 API retained 不再含两端；B1461–1540 的 SetHandleInformation 取消/失败会逐端独立清理，close 取消原对象与 primary 并存并传播。不能继续声称“成功 pipe 永远留 API 表”或“原 partial cancel 一定吞掉”。

剩余确定交错：恢复线程进入 release_retained，在 B965 读取并持有 pipe_read entry/原 handle 后暂停；Core 在另线程完成 handover（持 `_table_lock`，登记 pending/reader 并从 API forget）；恢复线程恢复，在 B994 `_close_quietly(handle,...)` 对已成功移交原端点 CloseHandle。release_retained 的遍历、entry 取得和 close 均不持 `_table_lock`，也无 ownership claim/转移复核；handover 的锁不能排斥它。原 read 端此时可以由活 reader 使用。

预期：API 恢复与交接是同一个所有权决策，移交后恢复再不能独立关闭；实际：恢复的局部旧 entry 成为第二个仍可关闭的 owner。这是实际 API 恢复入口与 Core handover 的交错，不是 owner 名字或顺序测试的推测。

最小建议：恢复先在同锁下 claim 仍 API-owned 的原 entry，handover 与 recovery claim 互斥；不能只在 close 前无锁 get 一次。阻塞 wait 不宜长期持全表锁，可用每 entry 的明确状态/代完成移交协议。未来 probe：两个 event 精确暂停 recovery entry claim/close，使真实 Core handover 完成后再放行，验证它拒关已移交 HANDLE；不需 Windows 真调用，本审未运行。

## M06 — 普通/取消隔离及活 reader 保护改善，pending 成功关闭却未通知 reader owner（OPEN）

**确定位置：B2485–2565、B2702–2746、B2415–2448。**

已闭合：`_close_one_reader` 在 wait/join 的 ordinary/KI/SystemExit 后重新询问 alive；`_PendingResources.close_all(protect=_pending_handle_in_use)` 由实际 reader owner_ref 保护，旧“取消后 pending 必关活 read 端”不再成立。`_wait_one_process` 现显式重抛 KI/SystemExit，外层逐 process 收尾后抛原对象。`_close_handle` 成功按原对象 identity 清 retained，旧 record 直接恢复成功仍遗留 retained 的具体缺口已闭。

剩余确定触发：一个已真正停止的 reader，其首次 `_close_one_reader` 的 CloseHandle 失败（ordinary 或取消），reader.handle 留原值且 pipe_read 仍 pending；同一次 stop 的末尾 pending pass 这次 CloseHandle 成功。B2724 `_note_closed_handle` 只清 Job、record 的 process/thread 及 retained，**没有把该 reader.handle 置 None**。下一次公共 Core.stop（已有失败，_released=False）仍进入 `_close_readers`，B2495 handle 非 None，随后再次 CloseHandle 同一已成功关闭的原 read HANDLE。Win32 HANDLE 值复用时不能依赖第二次 close 必报 invalid。

预期：pending 成功应同步所有实际 owner，成功项永不双关；实际：pending/retained 已清、reader 仍持陈旧原 handle，再次恢复可双关。此处不重复原 record retained 问题，后者源码已修。

最小建议：统一 on_closed 按原 identity 通知 reader（含 handle=None/关闭事实）与 Job/record/retained；所有成功关闭路径走同一通知。future probe：真实 Core + stopped `_BoundedStreamReader`，首 reader close 精确失败、pending close 成功，第二次 stop 断言该 identity 只一次成功 close、reader/pending/retained 同步，不靠 GC。未运行。

## M07 — endpoint/closer 原启动 owner 已改善，launcher 仍绕过原 channel、丢失未完成资源（OPEN）

**确定位置：B4084–4138、B5433–5489、B5304–5336、B5370–5430。**

已闭合：B3726–3763 在 worker.start 前将原 worker 登记 endpoint；start 后抛错/wait_ready 取消仍可由 endpoint 到达，join RuntimeError 返回未完成而非允许关 file。C1430–1477 保留 closer 原线程列表，C2184–2204 将 join RuntimeError 标 START_UNKNOWN/UNKNOWN，旧“未启动等于已退出”已闭；不因这些名字再虚报旧缺口。Popen 成功后在 hash 前 B5530 持久 retain 原 process，hash 取消不再丢该引用。

剩余同根因三条实际路径：

1. StreamChannel 在 custody.retain 后启动 drain，Thread.start 实际启动后抛 KI/异常，channel_factory 的赋值尚未完成，故 `_adopt_broker_process` 的局部 channel 仍 None。B5473–5475 走 `_terminate_and_close_process(... close_pipes=True)`；B5420–5430 直接关原 stdin/stdout。custody 虽持有原 channel，launcher 不查询它，活 worker 仍可能在这些 file 上 IO。保留引用本身没有阻止先直关活 file。
2. channel 已正常构造（构造尾 custody.forget(self)），BrokerProcess 构造抛错，B5466 channel.close **返回不完整 facts 而不抛错**，例如真实 worker 仍 alive。这里只对抛异常 retain channel，忽略返回事实；没有 broker 接收它，原 channel/endpoint/HANDLE 失去具名恢复入口（线程自引用不等于恢复 owner）。
3. recovery 表通常先有 Popen process、后有 partial channel。`_LauncherCustody.release` 按原顺序先 process helper（默认直关 pipes），仍可绕过活 channel；随后 channel.close 只要 return 就 B5333 记 released、最终从表删去，不核 reader/endpoint/HANDLE facts。B5330 对取消一律吞掉并 continue，不在安全收尾后抛首取消对象。

预期：同一 launch 的原 process/channel/endpoint 是有链接的 custody；先由 channel 协调 file，任何未确认事实均保留原 owner，各安全步骤后传播取消。实际：局部 channel=None、方法 return 被误当完整释放，恢复表还可再次直关活 file。这些与旧 M07 是同一生命周期根因，不另计多项 Major。

最小建议：先登记一个本 launch 的持久 owner，再两阶段构造/移交 channel；外层异常通过该 owner 找 partial channel，而非仅局部赋值。process helper 在 channel 已取得任何端点后永不自行关该两 file。retain/forget 以完整实际 facts 为准，release 顺序及取消聚合由同 owner 协调；成功项不重复。未来 probe：真实 channel.start 已启动后 KI、BrokerProcess ctor fail + channel incomplete 正常 return、release 时原 thread HANDLE fault 三场景，各先存返回事实，再测试 owner 有界 salvage。未运行。

## M08 — 部分状态机修复成立，共享 context/期限和副作用准入仍未贯穿（OPEN）

**确定位置：C1667–1698/C2333–2343；B685–761、B3488–3553、B3699–3790、B3832–3875、B4180–4183、B4674–4727、B4858–4862、B5496–5547、B5604–5620。**

闭合子项：Core.arm 已在 create_job 前拒过期；两次 create_pipe 之间及后、CreateProcess 返回先登记后核、assign/Resume/reader 前均有预算检查。worker cancellation check 与 IN_IO 意图现同 `_condition` 锁，NOT_FOUND 使用自己的 pause，完成按 `_completed >= _submitted`，旧 done 事件不再放行；partialwrite 每段调用 `_current_write_deadline` 读取当前 endpoint binding。正常/超期 StartupOwner.settle 现真实 join，不能再声称 `_finished` 一置位就成功。UNKNOWN 同锁、父双向1024 check/commit、STOP/STOPPED 消费预留及 broker 单线程 budget 接线保持关闭。

剩余原子缺口：

- **先副作用、后准入。** read/write 若 worker 缺失就 `_start`，其中 worker.start 前无取消/过期检查；`_await` B3774 先 worker.submit，再 B3777/B3784 检查 cancel/deadline。即使调用进入时已经过期或 cancel 已 set，真实 worker 仍可拿请求、进入 blocking read；不是只创建无业务线程。worker.run 的准入只看它自己的 `_cancelled`，不看这个调用 cancel 或 context。
- **相同 context 对象还未覆盖实际预算。** 子进程 main 把 Core.context 交 Channel/WindowsEndpoint，但 WindowsApi 只 bind 一个 absolute 数值，StartupOwner 只持启动数值；父 Session 调 launcher 的三参数没有 context，launch_broker 创建 StreamChannel 时 context=None，BrokerProcess 也不持 Session 的原 context，Session 在整个 launcher 返回后才 bind deadline。故 Popen/hash/channel/worker startup 尚在未绑定窗口。
- **cleanup 已发布但下层仍按长 absolute 等待。** B3699 `_effective_deadline` 与 B3832 `_current_write_deadline` 读 context.absolute_deadline，却不读 context.cleanup_deadline_value；Channel._remaining 只读本地 `_deadline`。真实子链收到 STOP→Core.stop 发布 now+5s cleanup→B4858 `_reply(STOPPED)`→StreamChannel.write，再 main finally channel.close；transport 从 Loop.run 仅绑定原 lease absolute，Core.stop 没向它 bind cleanup。其 WriteFile/cancel/join 可一直采用原长 lease，超过唯一5s清理预算。不是“默认 context 只供单测”的问题，main 正式路径如此。
- **cancel retry 不动态收紧。** request_cancel 循环只比较进入时的 deadline 数值 B3547；在 NOT_FOUND 期间另线程 bind 更短 cleanup，循环不重读有效 context，pause 也不裁到最新余量；外层 join 事后重算不能缩短已经耗掉的取消循环。launcher `_terminate_and_close_process` deadline=None 仍每次默认5s，实际 launch_broker 调 adopt 未传 deadline，release_retained_launches 默认也没有冻结原截止。
- **StartupOwner 异常出口未真实 join。** `_run_startup` 的非 timeout/cancel BrokerError 分支 B4685–4689 直接 release_inflight(owner) 并 raise，未 settle；_run 在 put 后尚未实际退出即可被释放。KI/SystemExit/ordinary 非 BrokerError 由 await_result 抛出也跳过本函数的 join。成功和 timeout 分支已修，不代表这些出口成立。

最小建议：父/子各用自己的实际 context，构造前传到底；所有动作前后核、submit 与原代准入原子协调；effective deadline 取 call/bound/absolute/已发布cleanup 最小值，每个 cancel retry/partialwrite/wait/join 重读；launcher 不得默认重新给5s；StartupOwner 所有出口在 finally 真实 bounded join 后才 release_inflight，未退出保留 owner。未来独立 probe 最小集合：过期 read/已取消 submit 零 primitive；STOP 后 transport 读共享 cleanup；NOT_FOUND 中途 tighten；startup ordinary BrokerError 的 put 后真实线程尾声。未运行，不要求新 ACK。

## M09 — 主恢复、按代等待和首 reader error 重试已修，close 仍可掩盖真实 IO 错/overflow（OPEN）

**确定位置：B3369–3427、B3765–3790、B4235–4263、B4185–4233、B4305–4402、B5115–5155；C1993–2066。**

闭合子项：BrokerProcess 在 channel_closed=True 但 `_channel_complete` 未全确认时再次协调真实 channel；WindowsEndpoint 每次重算 retained/alive，已退出 worker 的 thread HANDLE 失败可继续恢复，file_closed 不封死 HANDLE。C1956–1991 创建新 generation/event，C2084–2143 等待当前代；首次/重复 stop 已调用 `_await_close`，真实 closer join 的 helper 确实接到公共链路。strict REQUIRED_CLOSE_FACTS/zero facts 未放松。B5115 首 reader error 从 previous 恢复，新的不同 code 留 secondary，不因下次 None 或资源全关而抹首错。`_ChannelCancel.set` 首 owner 在同锁先绑定后 set，外部/未知先设置的 flag 不被 close 重贴标；partial buffer 在 finally 留 PARTIAL_FRAME。这些原缺口在明确范围内 CLOSED_STATIC_WITHIN_SCOPE。

**剩余 A：取消 flag 抢在结果读取前，吞掉已经发生的普通读取故障（不是失败 raw 的 external 次序争议）。**

可达交错：本代已 submit，_await 上一片 wait_done 超时，准备下一轮；此时真实 worker 的 read_stream 抛 `BROKER_STREAM_READ_FAILED`（或 OSError），worker.run 已将首错写 worker.error 并 _complete；暂停 endpoint 的调度，另线程正常 channel.close 将自己的 token 设到 cancel；endpoint 恢复在 B3777 先见 cancel，调用 _cancel/join，B3782 创建并 stamp 一个新的 BROKER_PIPE_CANCELLED。B3789 原本能读取 worker.error 的分支被跳过；drain 的 `_record_reader_error` 见 source is current close_source，B4250–4261 将它记正常 close_cancellation 并 return，原真实读取错从未进入 channel._error。

预期：已发生的本代普通错误保留为首错，close cancellation 只能是并列事实，Session 保持 UNKNOWN 且不能据无错释放 broker；实际：端点清理成功时 channel_reader_error=None，严格资源 facts 可以全真，Session._perform_close 可 self.broker=None。给新错误贴的 source 是“close 设置过 flag”的真实来源，却不是原 IO 错误的来源；仅 token identity 正确仍不足以证明本代失败由 close 引起。

最小建议：worker 按代保存原 outcome（原 error 对象/来源/序号），endpoint 在取消前后协调同一代结果，已发布错误优先保留，取消请求不能覆盖结果；channel 接受明确由本 close 终止本代 IO 的取消，资源完成事实仍独立。future probe 精确事件暂停 `_await` 在下一次 flag check 前，让真实 primitive fault 完成并发布，再设 close flag，两次真正 Session.stop 都必须保留原错误；这是新独立交错，不使用缺同步的旧失败作结论。未运行。

**剩余 B：overflow 没进入 close error 历史。**

B4199–4205 的完整带换行 oversize frame/超 max_frames 仅 `_overflow=True; return`，此前 B4192 已清 `_buffer`，finally 不生成 PARTIAL_FRAME，`_error` 可仍 None。read() 会抛 CHANNEL_OVERFLOW，但 close facts 只取 `_error`（B4368），不带 overflow，BrokerProcess 也只查 channel_reader_error，Session 的 strict close 判断没有 overflow。close 与消费 read 竞争或发生在 read 消费前，真实 overflow 可表现为资源全关/reader无错；即使 Session 曾因 read 抛错锁 UNKNOWN，原 broker 仍可按这些无错 close facts 被丢弃。

预期：overflow 和已有错误不能因 close 丢出持久 reader error 历史；实际：只保留在 channel 内部标志，跨 owner facts 不完整。最小建议：在 overflow 产生处持久记录非空具名 error（同时保留 overflow 原事实），通过同一 sticky 首错/secondary 通道传两次 stop。future probe：真实 StreamChannel 接受一条 newline oversize frame、在消费 read 前 close，再真实 Session 两 stop，原 error/facts/broker retained 均可核。未运行。

上述 A/B 属同一 M09 错误证据与恢复释放根因，合并一项；并不重报“BrokerProcess retry 总会清空首 error”——该具体源码已修。正常本地 close 的取消事实也从未被本审当作 HANDLE 释放证明。

## 原子义务矩阵（新18组）

状态仅指本范围静态子义务；任何 CLOSED_STATIC_WITHIN_SCOPE 均不等于动态或产品 PASS。

| 义务 | 静态结论及剩余 |
|---|---|
| N07-R01 | API未确认退出留控制HANDLE CLOSED_STATIC_WITHIN_SCOPE；Core同义务仍OPEN，见M03。 |
| N07-R02 | API恢复确认后close/首取消对象 CLOSED_STATIC_WITHIN_SCOPE；共同context/原截止归M08 OPEN。 |
| N07-R03 | 顺序API→Core→reader交接 CLOSED_STATIC_WITHIN_SCOPE；与API recovery原子互斥OPEN，见M05。 |
| N07-R04 | inherit取消与两端独立收尾、primary/取消原对象 CLOSED_STATIC_WITHIN_SCOPE。 |
| N07-R05 | wait/join普通/KI/SystemExit后的活reader保护 CLOSED_STATIC_WITHIN_SCOPE；原线程启动中覆盖仍NEEDS_DYNAMIC。 |
| N07-R06 | wait/exit_code取消重抛且后续record独立处理 CLOSED_STATIC_WITHIN_SCOPE；实际取消覆盖NEEDS_DYNAMIC。 |
| N07-R07 | direct record/reader成功清retained CLOSED_STATIC_WITHIN_SCOPE；pending成功不清reader原handle OPEN，见M06。 |
| N07-R08 | 实际endpoint启动前登记、join未启动不当结束 CLOSED_STATIC_WITHIN_SCOPE；wait_ready/start未返回的实际线程交错NEEDS_DYNAMIC，预算准入OPEN归M08。 |
| N07-R09 | Popen hash取消持久owner CLOSED_STATIC_WITHIN_SCOPE；partial channel/constructor失败/release恢复OPEN，见M07。 |
| N07-R10 | closer not-started RuntimeError→UNKNOWN CLOSED_STATIC_WITHIN_SCOPE；真实start未返回晚到收口NEEDS_DYNAMIC。 |
| N07-R11 | 同锁intent、NOT_FOUND重试、同代完成 CLOSED_STATIC_WITHIN_SCOPE；动态tighten取消循环OPEN，见M08。 |
| N07-R12 | 每段endpoint bind收紧 CLOSED_STATIC_WITHIN_SCOPE；实际context的cleanup未进入每段OPEN，见M08。 |
| N07-R13 | Core arm/pipe/late create预算改善；endpoint/launcher/APIfacade/child transport共同预算仍OPEN，见M08。 |
| N07-R14 | success/timeout真实settle CLOSED_STATIC_WITHIN_SCOPE；普通错误及取消出口join/release OPEN，见M08。 |
| N07-R15 | 真链定向HANDLE first1→second0有封存事实；全错误分支NEEDS_DYNAMIC，候选普通错/overflow保存仍OPEN，见M09。 |
| N07-R16 | endpoint每次重算及HANDLE恢复 CLOSED_STATIC_WITHIN_SCOPE；局部raw支持，全部分支NEEDS_DYNAMIC。 |
| N07-R17 | 当前代event/generation等待接线 CLOSED_STATIC_WITHIN_SCOPE；所有竞争到达时刻NEEDS_DYNAMIC。 |
| N07-R18 | 首次/重复公共stop接真实closer join CLOSED_STATIC_WITHIN_SCOPE；cancel/ordinary所有嵌套finalizer出口仍需独立动态覆盖，不签全通过。 |

## 继承24组核对

| 义务 | 当前候选静态核对 |
|---|---|
| N05-R01 | NUL取得即retain、Close失败原对象恢复 CLOSED_STATIC_WITHIN_SCOPE。 |
| N05-R02 | attribute/NUL/process清理独立、primary/取消对象关联已修；API过程同context预算OPEN归M08。 |
| N05-R03 | partial pipe ordinary/cancel清理已修；成功handover与recovery并发仍OPEN归M05。 |
| N05-R04 | record/pending取消后继续其他安全步骤成立；pending通知reader漏同步OPEN归M06。 |
| N05-R05 | ordinary wait不跳后record、KI/SystemExit明确重抛成立；不外推process退出/控制handle。 |
| N05-R06 | reader owner_ref保护实际alive成立；pending成功后reader旧引用OPEN归M06，start inflight全组合NEEDS_DYNAMIC。 |
| N05-R07 | Session背景STARTING预登记/晚到stop event保持；真实线程未返回交错NEEDS_DYNAMIC。 |
| N05-R08 | Session实际启动后抛错的原owner保持；NEEDS_DYNAMIC覆盖取消到达。 |
| N05-R09 | closer具名失败与not-started UNKNOWN已修；公共链已接join，NEEDS_DYNAMIC。 |
| N05-R10 | Popen即时retain改善；partial channel/返回不完整facts/recovery OPEN归M07。 |
| N05-R11 | Core已过期arm拒创建、late create先接管成立；endpoint/start/submit与跨层预算仍OPEN归M08。 |
| N05-R12 | Session/Core各自context锁内首deadline发布 CLOSED_STATIC_WITHIN_SCOPE；不是所有层已共享的证明。 |
| N05-R13 | Core reader/process逐次余量成立；API/launcher/channel仍非唯一cleanup，OPEN归M08。 |
| N05-R14 | endpoint await每片读新bound成立；start/submit先行及cancel retry固定数值OPEN归M08。 |
| N05-R15 | worker同锁代/NOT_FOUND真实重试及HANDLE恢复已修；动态cleanup观察仍OPEN归M08。 |
| N05-R16 | UNKNOWN同state_lock检查赋值，AST与4287090相同，CLOSED_STATIC_WITHIN_SCOPE。 |
| N05-R17 | 父收发同budget_lock check+commit、write序列锁；broker loop单owner，CLOSED_STATIC_WITHIN_SCOPE。 |
| N05-R18 | Session.stop terminal send、decode STOPPED/REFUSED、BrokerLoop收STOP/reply终态均用reserved=0，CLOSED_STATIC_WITHIN_SCOPE。 |
| N05-R19 | public stop真实channel不完整时可恢复已接通；其他错误分支OPEN归M09/NEEDS_DYNAMIC，不用fake事实代替。 |
| N05-R20 | Windows endpoint恢复时重算retained/alive、file幂等及HANDLE重试、Posix重复成功事实成立；NEEDS_DYNAMIC全分支。 |
| N05-R21 | BrokerProcess不直关channel file成立；launcher仍可绕过endpoint OPEN归M07。 |
| N05-R22 | 缺/None/False资源facts failclosed保持；真实故障因上游取消/overflow没进入facts OPEN归M09。 |
| N05-R23 | public stop与_current generation/closer实际join接线成立；startup错误出口仍OPEN归M08，真实全部线程NEEDS_DYNAMIC。 |
| N05-R24 | 175原顺序封存一致；兼容检查如下，不能将未到子场景/测试salvage计产品PASS。 |

## 已关闭兼容项保持及限制

M01 `_require_directory_name`、m01 `_freeze/LaunchPlan`、M02 Windows固定宽度/prototype、M04 `WindowsApi.job_process_ids`、M11 nonce/错误映射均独立核对当前文本，关键AST与4287090完全相同，见 compatibility-static-check.json。M04仍以完整header/allocated/returned/count一致/17上限/内联array拒不完整；M11仍非Windows在目录创建前拒绝，nonce由os.urandom(16).hex默认生成，原错误码映射未退化。M10 role_command AST不变，必要旧sampler/controller/runtime等13项production pins从同commit原blob核对与冻结plan相等，见 same-commit-production-pin-check.json；没有执行它们。没有因预审新发现推翻已关闭M04/M11/M01/M02/M10/m01。

raw fake COMPLETE_CLOSE_FACTS只证明父接口处理某种声明，不能证明实际worker/HANDLE终态；本报告未使用其通过来裁决真实链。test09进行中不在本候选审查范围，新候选是否复用两源、机器证据重绑定与动态复算由root另行决定。

## 完整性与停止交接

开工保存 review/implement 两库 HEAD、index、HEAD tracked diff、cached diff原文及哈希；before-source-hashes.json保存两工作区和根包现有工具源码哈希。两候选blob只写本NEW目录，未checkout/reset/clean/add/commit、未物化tools。批准的review `tools/open_lvw_browser.cmd` SHA256仍为 `f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04`，保留CRLF。最终 workspace-after.json 分别说明本review不变项与其他owner并行变化，不能把另一owner测试提交归成本审修改。无本审候选线程/业务资源待salvage。

完整V0–V3大纲（control原数，不增加）：V0-S0 1/2（历史NO_GO）、V0-S1 5/5（仅V0-Min）、R0 1/2（前置子集）、R1a 5/5（单图切片）、V0-S2 7/8（旧范围未签）、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3/V2 0/4、R4/V2 0/4、R5a/V3 0/4、R5b/V3 0/4、R5c/V3 0/4。

十字段：当前坐标=R1/WP-R1-U3/RUNNING（S3_P4_OFFLINE_INTEGRATION_PREPARATION）；本批完成=66600a1两生产原blob、六Major原子缺口静态预审及封存raw只读核对；最后通过门禁=621b1bf统一切片live15范围；当前阻塞=control的S3_P4_N1_CORRECTION08_FAILED175_CANCEL_ORDERING及本报告静态缺口；全局路线位置=上述完整大纲；剩余工作=root决定生产纠正/新候选重绑定与有限独立动态复算，N2/I24/产品/质量/余额/人签不替代；下一责任人=root门禁owner；所需授权=本静态范围已授权，本审不申请动态；证据目录=本NEW independent-native-custody-prereview-08；精确停止原因=非最终静态预审完成，CHANGES_REQUIRED，不签Stage或最终独审，worker_done后交root归档释放。

容量：本worker未派生/回收任何Agent；已收到根任务包的每工作区1/project3容量与launch记录，本审不额外创建窗口。其他窗口当前生命周期未重新盘点，不伪报实时存活数；本worker完成即按委派约定由root归档释放。

最终完整性实测：review HEAD/index/HEAD tracked diff/cached diff四项逐字不变，三处快照中的生产源码与批准CMD hash均未变化；实现库HEAD/index由并行实现owner变化，唯一工具源码hash变化为test_v0_s3_native_custody_correction07.py（test09范围），实现库tracked diff/cached diff仍与开工相同。本审未读取其新测试文本作为结论，也未修改或还原该变化，详见workspace-after.json。
