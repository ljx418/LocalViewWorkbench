# P2B correction-04：分阶段持久化与小终态（Codex冻结，仅离线）

实际执行candidate4c3ed0b / reviewed tool9b661800的唯一child S3-P2B-CORRECTION-02已EXPIRED/BLOCKED。工具write对所有JSON统一32KiB，最终life混合commands/fullphase/observer/cleanup超限，两次terminal写失败；缺失内存数据不可重建为真实观察。claim过期不是lifecycle通过。原failed、terminal_persisted=false、真实合成debit下界1及FAILED_RETAINED、UNKNOWN清理完整保留。

本次采用分阶段工件+小终态的不同技术方案，先合成完整三阶段最大负载闭环再独审；不准任何新Windows/WSL实机batch，下一child03只DRAFT。没有新产品目标/质量阈值变化，也不修改P1协议或扩大32KiB通信消息上限。仅改tools/v0_s3_runtime_binding.py、tools/test_v0_s3_runtime_binding.py；新证据implementation-p2-binding-correction-04/。预算policy/bridge/authority/业务/合同/计划/manifest/旧raw/child/质量16只读。

## 固定工件合同

终态cross-os-lifecycle.json schema更新为小摘要：status/candidate/child/preflight、已观察budget/debit、三phase判定、cleanup状态、errors与artifact_refs；UTF8<=16KiB。详情和全部stdout/stderr/observer不内嵌该摘要。每引用包含owned相对path、sha256、bytes、kind；逐个机器验证能解析且字节hash一致，禁止任意外部路径/symlink。EXPIRED claim链接小终态，避免自引用hash环（终态可记初始claim hash，finalclaim可记终态hash）。共享claim唯一性与不退款保持。

固定明细类型仅phase(normal/bad-receipt/timeout)、observer、command capture、cleanup/retention。控制/协议JSON仍<=32KiB；详细磁盘工件有专用<=1MiB单文件上限、全批16MiB约束，不通用放宽write或协议decoder。可用有限JSON/JSONL，记录/line有界；一份小EvidenceStore或函数足够，不建立新平台/数据库/通用服务。

每个phase完成后立刻持久其native身份、真实回执/error/echo/最后已知debit与对应observer，再允许下一phase；失败也保留完整原始错误。Meter.run在finally保存实际命令及stdout/stderr/exit/error/pipe/threads和已捕获前缀，不等总terminal。observer的完整sample/time/error/cutoff先持久再做断言/aggregate。需要可在observer过程中逐条append+fsync的JSONL保存前缀；至少保证finish与异常finally均写出，不因后续phase/terminal异常失去先前观察。

stdout/stderr按原始bytes或可无损恢复的有界文本分块保存，并记录hash/长度，不以UTF8 replacement冒充raw完整。不给日志写图片/媒体二进制；本CPU协议只身份/摘要。为证明总量，可将本harness外层每stream cap固定256KiB（P1通信32KiB不变），确保三命令/两流与所有工件预算上界可算；实际所有写入和base64/JSONL开销计入全批16MiB，不能只计原始bytes。声明保守预留和实际测量，之前metadata1/32/32预留不退不变。

终态独立预留64KiB，可容纳<=16KiB索引及有限失败/claim更新；工件详情写入失败不能让索引超过上限。预算耗尽/序列化/观察异常仍写小BLOCKED/UNKNOWN终态，已保存artifact_refs不丢，不退款/settle0，不因cleanup删除把失败洗成功。底层存储全部不可写时保留最初exclusive claim与有限stderr、非零明确unproven，不虚报。状态通过仅当必须三phase工件/观察/预算/claim对齐全部持久。

## 完整离线链路，禁止只测writer

必须驱动公开run owner，从fake授权/preflight/sharedclaim开始，实际同factory创建normal/helper、按真实阶段顺序处理三phase、observer与commands，直到小终态与EXPIRED。仅最终Windows进程/host executable identity为合成替身，SQLite/角色/文件持久化真实，用已有安全fixture避免/mnt/c和真实registry。不要只手写一个小life调用terminal。

最大规模fixture包含每phase合法角色/binding/nativeidentity，observer最多160个采样/每次最多4owner、长中文空格owned路径、完整命令stdout/stderr捕获及错误metadata；其序列化原单文档明确>32KiB，旧方案确实无法容纳。新方案全链落盘、hash/bytes守恒、terminal<=16KiB、所有必需引用可解析、claimEXPIRED、总实际/保守输出<=16MiB。缺失/篡改工件不能PASS。最大test不调用真实Windows/WSL，不读原fixture/PID/母ledger/媒体。

再验证：第一phase成功后第二phase异常，第一份明细仍在；observer/第三phase/cleanup异常均有小BLOCKED终态；详情写失败不丢先前工件；output exact/one-over黏性、真实未知debit不写初始0、终态source身份不变。原212功能/oracle保留，新增最大链路必须覆盖test previously missing。既有helper/admission、M01/M02、metadata累计、窄化ESRCH和DRAFT闩不回退。不要重跑实机来发现容量问题。

## 测试边界

仅新的owned tmp/Linux helper/SQLite，0actual Windows driver/WSL/host executable digest/真实CPU claim/母ledger/源媒体/旧preview/旧failed root/PID/GPU/服务/network/download/checkpoint。原warm benchmark Parser.ParseInput静态测试实现/独审各额外允许最多1次（allowance04，未来限定，不追认过去），与03相同固定源hash/纯parse/30s/64KiB；其它.exe进程边界拒绝。先定向最大链路，最终组合一次，完整raw/机器计数/原始parser输出与临时清理可序列化保存。

下一child S3-P2B-CORRECTION-03当前DRAFT，只支持该新ID且DRAFT预检0资源/claim；旧所有ID拒绝，不改child。root待独审后另行激活，执行候选仅data变更且工具blob完全比对。此次不做实际清理原失败根或当前旧PID；其真实历史保持UNKNOWN。最后只READY_FOR_REVIEW、提交候选及追加证据并worker_done full SHA，不签Gate0/Stage/质量/人签。两次同路线无进展交接，严禁盲开新批。Git作者ljx418 <1173696783@qq.com>。
