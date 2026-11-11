# P2B correction-05：终态发布的一致性（Codex冻结，仅离线）

精确8a21d64独审bf1767e结论F0/M1，227完整测试通过与容量/ref证明保留；M1复现共享claim终态写失败后内存BLOCKED、disk index READY、本地consumed READY、shared RUNNING。这是会造成假绿的已证局部写失败路径，非全存储不可用。未来actual child03仍DRAFT，本轮无实机。

仅改tools/v0_s3_runtime_binding.py和tools/test_v0_s3_runtime_binding.py，追加implementation-p2-binding-correction-05/。不改P1/bridge/shim/预算policy/业务/质量/源数据/旧证据/合同/child/plan/manifest。不再重做分阶段EvidenceStore或放大边界；协议32KiB、详情1MiB、小终态16KiB、总16MiB与预留机制全部保留。

## 最小提交协议与语义

消费与决定分离：共享claim/local consumed的status EXPIRED只说明一次性容量已消费，不复制READY_FOR_REVIEW为自身决定。采用终态引用语义（例如result=TERMINAL_REFERENCE_NOT_DECISION、terminal_path/hash、child/candidate身份），只有已发布canonical index+两个引用对齐且artifact refs完整才是可接受成功；读单个consumed不得当通过。新内部schema/字段完整记收据，公开产品API不变。

终态开始先落小FINALIZING/NOT_PASS索引，不先写READY；计算最终摘要bytes/hash（无hash环，index只反向引用初始claimhash）。共享claim与local consumed的EXPIRED/ref都安全写入成功后，最后一个可失败发布步骤才原子替换canonical index为READY。成功publish之后不再做能把结果翻成失败的附加持久化/验证；CLI状态必须与已发布索引一致。

任何claim/local/index写失败立即转BLOCKED/UNPROVEN，并尽力有界落相同的小BLOCKED索引与消费引用。不能在捕获错误后沿用预先构造的成功expired对象；不保留可误读为成功的READY index或consumed。共享claim永久不可更新时保留最初RUNNING/独占tombstone、不unlink、不退款，不新建身份；索引明确claim_finalization=UNPROVEN和错误，返回非零。local永久失败同理，不能只说terminal_persisted=true就代表整组finalization完成。

明确分开terminal_index_persisted与finalization_proven；保留兼容terminal_persisted字段时定义清楚，接受条件必须包含status与最终一致性。强制verify helper或等价实际读取核对最终hash/身份；避免循环hash（final claim引用final index，index不引用final claim hash）。存在临时未对齐过程时canonical状态只FINALIZING不PASS；无任何已发布READY前置于必要消费引用完成。

最后publish失败后有界一次BLOCKED持久化和引用修正即可，不递归重试、不卡死；全存储不可写保留已有claim/phase证据和有限stderr，非零+UNPROVEN，不虚报。已持久phase不能被终态修复删除/覆盖。

## 固定失败矩阵（驱动公开run）

沿用真实same-factory/文件/角色/admission/SQLite、最大三phase替身驱动公开run，不仅手调terminal。独立注入共享claim EXPIRED写失败、local consumed写失败、READY index最后publish失败、早期index失败、局部瞬时失败与持续失败；部分成功写入后错误也覆盖。每例保存返回值、disk index、两消费记录、refs/hash与实际持久状态，断言不存在磁盘READY与返回BLOCKED的矛盾，也不存在任何消费记录自身READY结论；完整成功链必须索引READY且两引用hash相同、EXPIRED、artifact可验证。

全存储不可写单独测试best-effort，不把局部故障当它；容量/phase1在后期失败仍保留、未知debit不写假0、shared一次消费不退都保持。老227功能/oracle保留，允许按新内部引用语义改旧正例的字段断言，但对应通过/拒绝义务不能删，逐项记oracle迁移。新增测试在断言前留全量观测，根因已经可复现，不盲复跑历史。

## 验证与产物

只新owned tmp/Linux helper/SQLite；无actual driver/WSL/host hash/真实claim/母ledger/旧retained/PID/媒体/GPU/模型/服务/network/download/checkpoint。allowance05对既有固定纯Parser.ParseInput静态测试实现/独审各最多1次，仍纯parse、固定source hash、30s/64KiB，其它.exe一律拒绝。先定向新矩阵，最终完整受影响组合一次；所有raw/命令exit/实际parser次数/清理可序列化保存。未来03 child DRAFT/旧IDs拒绝，不能自行激活。

历史directed4 raw tar内合成SQLite/源码副本已由独审1145条目hash确认；root接受保留现有不可变历史作为离线证据，非产品风险，不静默删除。今后新报告只文本索引/hash与必要raw，合成DB/重复源码保留runtime或删除前记hash，不再新增此类Git二进制archive。不要把归档称纯文本。

完成只READY_FOR_REVIEW，提交候选与追加证据worker_done full SHA、精确测试与内部schema变化/失败矩阵/清理风险。Git作者ljx418 <1173696783@qq.com>。两次同路线无新证据/进展止交接，不新增实机重试，不签Stage/Gate0/质量/人签。
