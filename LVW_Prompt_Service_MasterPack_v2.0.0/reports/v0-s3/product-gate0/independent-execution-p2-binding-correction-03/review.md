# Child03 actual evidence 独立审查

结论：**Fatal 0 / Major 0 / Minor 1**。本次已保存文本足以支持 child03 的三项 EXPECTED_BOUNDARY 与最终一致性，建议 root 在明确接受下述证据披露后作限定 P2B 裁决；本审查不代作该裁决，不签完整产品 Gate0、Stage、质量、人签或发布，不授权 P3 执行。

证据 tip `b7e36beefe3cbe4c7b32f66a99bd4ddfec506fb8`；执行候选 `975747218d0d002521d98e56c46b9da2c52ee612`；已审代码 `da6e7b5ed351baca3b74f003cfcf3622c4b382d6`。初始 HEAD `3afbe150f8b1bd2bdc56aee86a244ac7449558ee`、工作树干净，按指示 merge --no-edit 快进，无冲突。只新增本目录。已读 AGENTS、治理README、执行索引、child03 activation、C01–C05、原237项独审、实际 report/verification/outer-raw/runtime-evidence/registry；协调坐标仅 git show 读取 `92239ba210bc466808de2cbf5bbcbdd3fdbf1569`，未合入该提交。

## 一次性问题汇总

**C03-m01（Minor，持久化信息缺口）**：`tools/v0_s3_runtime_binding.py:731–746` 将 lock acquired/released 和 wrapper_return_monotonic 写入 `life`，而 `persist_phase` 与 `terminal` 没有将这些字段持久化。C01要求明确上锁/释放时刻，本批22件工件不能复原这些精确时间。不能拿13秒 timer 常量当实测释放时刻，也不能从 remote 缺席推断由谁 kill 或锁释放导致退出。该缺口不推翻已保存的原生 TIMEOUT/exit1、完整独立观察轨迹、两次缺席及资源保留，因此不升级为阻断；root 可明确接受限定结论，未来若继续此工具应保存这些时间字段。本任务不补写历史、不实现、不重跑。其余没有新增 Fatal/Major/Minor。

## 可复算绑定与终态

`verify.py` 为本审查独立编写的文本复算器，仅标准库读取提交文件并用 git show/rev-parse读取对象，不导入产品模块，不执行候选。一次执行 exit0；46件 SHA256SUMS 文件、22 refs、3 command、6 observer均通过，细项与摘要见 `receipt.json`。没有重跑237、Parser或历史归档。源码 SHA256/Git blob、引用 sha/bytes、命令 argv摘要与原始流 sha/bytes均列在 receipt。

两工具 SHA256分别为 `5dedecde3e3b7b2236f5666b0790ece8ffc39392888c9ec5d88fa2bb888f520b`、`b2020ea472509619956dabe1f9c20a92440f6a14760108d2afd2ca22fc5483f0`，与 activation、candidate、tip、原已审代码逐字节一致；preflight九个源/授权文件亦匹配。七个 sealed inputs与执行候选及当前文件逐字节一致；child/activation/C05/preflight hash链匹配，旧DRAFT合同被明确的后续 activation激活，不复活旧ID。

外层 preflight及actual各保存一组 stdout/stderr/exit，两个原始exit均0、stderr为空；preflight stdout摘要与保存JSON匹配，actual stdout与canonical READY一致。结合唯一claim代码和记录支持本批一次preflight/run，文本证据不是整台OS所有调用的全局审计。

Canonical schema3 SHA256 `aaf47d75809a1c743d8cb9898c809198009db744f27d12f4f59cd93341ddef18`，READY_FOR_REVIEW、terminal_index_persisted=true、finalization_proven=true、claim_finalization=PROVEN、无terminal errors。shared-claim保存副本与local consumed字节/对象一致，schema2 EXPIRED且结果为 TERMINAL_REFERENCE_NOT_DECISION；两者terminal path/hash、child/candidate/preflight完全匹配。剥离终态新增字段、恢复RUNNING并按claim_once的原始序列化，复算初始claimhash `0e8968e5741b01facd50ea9dcd1e3e4558e5da5cf2ac15c9bc5e5ee34268fb28`，没有final claim/index哈希环。没有读取当前原canonical claim或当前进程；裁决针对保存时的证据。

每件ref均为 details下单层owner相对路径、无symlink、实际bytes/hash一致，单件≤1MiB，index≤16KiB。三命令base64严格还原，两流实际均0字节，空流SHA256匹配，raw_complete/threads_joined/pipe_closed均真、reader_errors空、exit0。这是Windows driver外层捕获；嵌套协议stdout在response仅保存摘要，不能声称保存了全部嵌套原始管道字节。

源码EvidenceStore.save用exclusive create、flush/fsync后追加ref；命令finally存capture、observer线程finally及finish各存一份，persist_phase存native/response后才complete_phase并推进下一phase。序号000–006、007–013、014–020和其内部refs对应此顺序。terminal先FINALIZING、staged确定bytes，写两个EXPIRED引用并读回验证，最后os.replace发布canonical；成功发布后不再有可失败持久化。这与原C05独审一致，未拿report字段代替源码/原始工件核验。

## 实际边界及观察

| Phase | 本批原始证据支持的结论 |
|---|---|
| normal | 实际Windows Python native身份 → 固定 C:\\Windows\\System32\\wsl.exe / Ubuntu-24.04 → 候选真实shim/authority → synthetic SQLite，DEBITED、最后观测总数1；bad-binding-hash在发送前拒绝，model_sends=0 |
| bad-receipt | 独立helper根、不同shim hash，源码明确不调用authority，故意把request_id改成零UUID；真实native wrapper exit0被客户端按严格echo以S3_BRIDGE_RECEIPT_INVALID拒绝，0send、helper SQLite观测0；假DEBITED不是生产扣额 |
| timeout | Windows native wrapper OS exit1/error TIMEOUT，S3_BRIDGE_PROCESS_FAILED、0send；remote当时同birth两次缺席，预期failclosed通过，不是请求成功，不声称remote独立数字exit或因果kill |

Native Python PID为40864/41580/28852，native WSL wrapper为26200/38332/19916，各自Windows creation time；interop与remote Linux PID/start_ticks分别保存，不混用身份。三个新UUID及remote PID/birth互不相同；具体身份见receipt。observer finish/finally三对均来自同一采样链，线程内部finally时joined=false、调用方finish后joined=true是合理先后，不把前者漏报。逐样本重算monotonic严格递增、身份不漂移、ENTERED与absence计数一致；每phase最终joined=true/error=null/two_absences=true。

| Phase | samples | 最大间隔秒 |
|---|---:|---:|
| normal | 7 | 0.10645423399546416 |
| bad-receipt | 8 | 0.10619850300281541 |
| timeout | 94 | 0.10731954199582106 |

全部≤160次、≤30秒、间隔≤0.25秒。timeout phase初存debit actual=null、last_observed=1，后续SQLite文本快照再观察1；未把未知值初始化为0。close_retaining_reservation只把active变2，未refund或settle0；UNKNOWN_ACK reservation保留，此行为由源码及成功走到终态的记录支持，审查未打开DB验证。已保存cleanup对两根均AUDIT_RETAINED，保留理由/登记清晰；这是登记留存，不能说全部临时物已删除或当前仍无进程。

## 预算与证据限制

保存wall=14.639913143997546秒/1200；process conservative reservation由10+8+4+4复算26/64，不冒充全OS进程数。三角色metadata按104952×1 +258048×32 +8020928×32复算265032184/268435456，余3403272；CONSERVATIVE_NONREFUNDABLE_RESERVATION，actual_digest_bytes=null/NOT_MEASURED。仅三角色hash与旧seal一致，其余旧metadata未重验，不扩大成完整环境证明。

output计费13454867/16777216为固定调用图保守计费，detail实测sum=126988，detail reserved=8388608、terminal reserve=65536；不同口径不相加冒充实际写入。wall/output原计数不是审查新实测累计I/O；文件sha/长度是本次文本复算。fixture两根、runtime及outer capture位置由registry登记；未读它们，也未读取program02.sqlite、任何合成DB、旧失败根/当前PID、host executable或删除AUDIT_RETAINED。

本审查新增实际preflight/run/test/Parser/Windows/WSL/hosthash/GPU/model/service/media/network/download/checkpoint全部0，无ledger/claim写和进程信号。原批模型/母ledger/GPU/service/media/network/download/checkpoint0由冻结路径、代码及现存记录支持，不宣称OS级全审计。原失败/UNKNOWN与旧tar保持原状。原237独审的崩溃/存储不可写可留UNPROVEN、非数据库多文件事务、临时根非耐久备份、固定预算包络非任意损坏DB保证等限制继续保留。

## 交接与产品缺口

十字段：1 当前R1/WP-R1-U3/PREPARING_NEXT_STAGE，S3 P2B actual child03独审；2 本批只读证据审查已完成；3 最近已接受统一切片621b1bf/UM10范围不变；4 F0/M0/m1、root限定接受仍待；5 目标完整V1，按S3前置路线；6 后续P3设计及产品Gate0、增量包/安装回滚/离线验证、独立10图6片质量集、累计十二项、后续独审/必要人签仍未完成；7 下一owner仅root；8 无新增实机权限或预算申请；9 本目录review/receipt/verify及上游原raw；10 停止于独审交付，不签产品通过。

唯一协调坐标92239ba的大纲：V0-S0 1/2（历史NO_GO）；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；当前R1 0/4；V1-M1 0/3；R2 0/4；V2 R3 0/4、R4 0/4；V3 R5a 0/4、R5b 0/4、R5c 0/4。统一早期切片实现/机器/独审/人签仅该切片，不补签历史S2或完整V1；完整逐项状态原样保存在receipt.development_outline。
