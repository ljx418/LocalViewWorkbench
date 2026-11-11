# correction-04 独立离线审查 — CHANGES_REQUIRED

审查精确候选/证据 tip `8a21d6497bca6e2fc20d5c79fd28ac10daa4c42c`，base `ad2f89948db091d1fc9f64cd857eff6c5c1ef4cf`。工作区初始干净，HEAD `3cf5efc07d748fa5d09969d3f7f22e722c25b48b`，按指令 fast-forward merge，无冲突；本人未实现该候选。只新增本目录，未改候选、合同、计划、manifest、child、原始失败或实际运行状态。

**一次性 F/M 汇总：Fatal 0 / Major 1。建议 root 暂不接受本候选为可激活代码，child03 继续 DRAFT。** 这不是 Stage、Gate0、质量、人工或发布签署。

## M1：终态提交后 claim 失败仍留下可误读为成功的持久证据

位置 `tools/v0_s3_runtime_binding.py:494–503`，`terminal()` 先写成功 index，再构造成功 expired 对象，随后分别尝试共享 claim 和本地 consumed。`attempt()` 捕获写入错误仅改内存 life，已经写入的 index 不再降级；同一个成功 expired 对象仍写入 consumed。原实现的终态失败重写分支在此 diff 中被删除。

`probe.py` 用同一个公开 run 和实际 factory/角色/admission/SQLite、三阶段最大 observer/capture，仅让 owned `shared.claim` 的 EXPIRED 写入抛出 OSError；不是直接手工构造 terminal。实际结果：run 返回 BLOCKED、terminal_persisted=true；磁盘 `cross-os-lifecycle.json` 仍 READY_FOR_REVIEW 且 terminal_errors=[]；共享 claim 仍 RUNNING；本地 consumed 却 EXPIRED/result=READY_FOR_REVIEW。原成功断言正确拒绝，独立 probe exit=0 表示成功复现缺陷，不能计作产品正例通过。原始 stdout/stderr、完整 receipt、已经持久的 phase/raw 在 probe-* 中。

这违反必须 claim/终态对齐才通过的冻结合同；局部写失败不应伪装完全存储不可用，更不能仅依赖调用方看到内存 BLOCKED。建议在 finalization 出错时有界持久 BLOCKED/UNKNOWN index，停止写成功 consumed；能安全更新共享 claim 时写 EXPIRED/BLOCKED 并重绑最终 hash，不能更新时明确 unproven/RUNNING，保留 exclusive claim，不退款、不重新激活。需要覆盖 shared claim 与 local consumed 两种失败，验证持久索引/收据与返回值一致，避免 hash 环。此处只提修复，不修改候选。

## 最终版本验证与容量

一次完整受影响组合：**227 collected / 227 passed / 0 failed / 0 skipped，47.26s，exit 0**。机器 nodeid 清单在 combined-counts.json；旧212保留，新增退休 child02 一项与 correction04 的14项，合计227。未重复14子集、未跑全仓/verify_pack。实现的225发生于最终窄修前，最终14仅定向覆盖；绝不称实现已 final225 全过。本审查另有一个独立公共 run 故障 probe，不并入227。

最大成功链路三 phase normal/bad-receipt/timeout，每 phase 160 samples ×4 owner，observer finally 与 finish 各保存一份；真实同factory绑定文件/角色/admission/SQLite，host 身份、Windows进程和observer输入是明确合成替身。长中文空格路径，三个 command 的 stdout 各262144 bytes、stderr 各256000 bytes，包含非UTF8 bytes，base64解码长度与sha256全部匹配，raw_complete=true。旧 life 序列化1,203,376 bytes，确实超过32768；终态5133 bytes，22引用，detail实际4,513,827 bytes。当前磁盘 evidence tree 4,522,688 + 两factory 289,608 = **4,812,296 bytes**；保守 meter **13,449,403 bytes** <=16MiB。统计是逻辑文件字节，不冒充块分配或累计磁盘IO次数。

8MiB detail reserve、64KiB terminal reserve、3MiB固定fixture写入预留、每command两流各256KiB均保留；detail实际编码开销计入8MiB而不再重复收费，raw pipe与持久base64是两层有意保守预留，不把预留额称实际写入。save在写前扣actual，不成功不退；每件1MiB，控制JSON/P1仍32KiB，terminal16KiB。真实落盘另行复算，没有仅凭预付就认定物理字节受控。fixture预留是固定源码/有限调用图的保守包络，不是通用SQLite任意写入限额；该离线样本不能证明任意外部损坏或异常磁盘无限扩张也受约束。

九个当前完整链路 raw refs 均相对路径/无symlink/字节/hash可复算；成功与phase2/phase3/observer/cleanup/detail/serialization/native/output八种异常保留正常phase1。异常终态BLOCKED、claimEXPIRED；输出one-over保存prefix且raw_complete=false。store负例覆盖missing/tamper/symlink、exact/one-over和黏性output。先持久 native/response/binding snapshots/observer/command 后推进，command exception 原文另存，终态只preview。完整底层存储不可写不能据此宣称已持久：代码无法写index时不会写EXPIRED，必须保留原claim并报unproven；本轮未另造全盘不可写探针，不能用局部故障正例替代该事实。

旧 shared claim跨root/exclusive并发、finally异常、metadata1/32/32不退预留、ESRCH与Unknown、helper固定角色/UNC/normal driver来源、03 DRAFT零资源与退休ID拒绝均包含在该组合；没有借机全项目审计。M1表明已有测试通过仍未覆盖终态提交后的claim错误。

## 原实现产物包装与可复算性（独立于M1）

对可信Git中的5个tar.gz只读流式检查，1145文件条目逐个比对archives.json中的size/hash；拒绝绝对路径、..、symlink/hardlink/特殊成员，每条<4MiB、每档累计<128MiB，不解压、不执行快照、不读host。37个历史terminal记录逐个重新核对refs与EXPIRED terminal hash；**37是终态验证记录数，不是37个pytest测试，也不加到227**。

directed4归档实际含18份SQLite与90份Python source snapshot；其它4档没有SQLite/source快照。故交付不是“仅文本”。这些条目的来源是公开合成factory测试拷贝、owned tmp、固定合成child/binding与源码快照；结合源代码和清理记录，归类为合成测试产物而非母ledger/真实claim/媒体。未执行归档中的代码或数据库；hash相符证明完整性而非凭hash证明任意数据的语义隐私。

包装范围是新implementation证据目录，未发现更改旧raw/合同/计划/child。治理README对runtime数据默认不提交的原则与此次把SQLite/source藏入压缩包存在交付惯例差异，应由root显式处置；不能把tar格式本身称为产品安全漏洞，也不能把它描述成纯文本已满足惯例。建议后续将合成SQLite/重复源码放受控runtime，Git保留文本索引、hash、来源和受控访问指针；保留现有失败与归档历史，勿静默删除。此项为非阻断包装建议，不扩大M1结论。本审查新factory拷贝只保存文本hash索引后清理，详情/raw命令仍可复算。

## 边界、清理和历史

同一runner guard先拒绝其它.exe/host open，含间接/mnt/读取，审查期间0实际driver/WSL/host executable digest/真实claim/母ledger/旧retained/PID/媒体/GPU/服务/network/download/checkpoint。Linux helper/SQLite只用本轮owned tmp。allowance04固定test hash通过，唯一纯Parser.ParseInput **1次**，NoProfile/NonInteractive，30s与64KiB限制；actual argv、exit、stdout/stderr及base64见combined-parser.json，未执行解码脚本或CIM。guard拒绝事件0，不把无拒绝等同操作系统级沙箱证明；这是受审测试代码的Python audit/Popen边界。

combined-receipt.json确认basetemp删除；每public case清理记录确认两个factory原根消失；probe临时根删除，未知/历史根完全未动。新报告factory快照删除前的逐文件size/hash在fixture-cleanup.json；新raw是文本JSON/base64，不新提交SQLite或运行时源码副本。原execution02终态仍是EXPIRED/BLOCKED、terminal_persisted=false、debit下界1、FAILED_RETAINED与UNKNOWN；其丢失内存证据永不可由本轮合成观察或重查旧PID重建。

## 十字段及V0–V3大纲

1. 当前坐标 R1 / WP-R1-U3 / S3_P2B_PHASE_DURABILITY_AND_COMPACT_TERMINAL_REDESIGN。
2. 本批工作：精确8a21独立离线代码、组合、证据及包装审查。
3. 最近接受：621b1bf386db71bfe08ca2f533fa8ec396b0504b统一切片，范围不扩展。
4. 当前阻断：P2B_FULL_SIZE_EVIDENCE_PERSISTENCE；M1未闭合。
5. 全局路线：V1准备，旧S2保持7/8。
6. 剩余：修复终态提交后错误的持久一致性、有限针对复验及root裁决。
7. 下一owner：root协调修复/独审，之后才考虑新child。
8. 授权：无新人工请求，无实际child激活。
9. 证据：本目录receipt、原始日志、hash索引和review。
10. 停止原因：审查完成，CHANGES_REQUIRED；不是Stage接受。

来自execution-control原坐标/大纲：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；当前R1 0/4；V1-M1 0/3；R2 0/4；V2 R3 0/4、R4 0/4；V3 R5a 0/4、R5b 0/4、R5c 0/4。实现已提交，机器227通过，独审M1待修复，人工签署未新增；四者不互代。
