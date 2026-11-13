# S3-P4 stream correction02 独立零进程审查

结论：**CHANGES_REQUIRED；Fatal 0 / Major 3 / Minor 2**。审查工作完成，不宣布 StagePASS 或产品 Gate0。候选 `e3c507227d534c56d571c6324729644f9dbac1ac`，基准 `626d37cf59bfc69324c1a9f886a65cd3f8c56964`；只有 supervisor 与其测试两处源变化，其余 owner 的发现属于本次额外只读审计，未授权修改这些 owner。

本实例未参与实现、无子 Agent。范围严格为本进程线程、真实 os.pipe、合成文件与 fake handle 驱动生产 owner。Windows/native/GPU/A06/原 ledger/真实质量集合均未验证；本候选原 13 个真实进程场景仍 **NOT_PROVEN**，I01–I24 不是本轮 24PASS。

## 原三项关闭情况

| 原项 | 结论 | 独立证据 |
|---|---|---|
| M1 未证明 EOF 的 drain 成功 | CLOSED，限本次零进程 owner 范围 | `observations.json` phase_clip/child_clip/shared/zero_remaining；合法 terminal+真实 canonical 不能掩盖两流未完，unknown/根/预约保留，archive/nextphase/refund/resend 均拒绝。共享耗时 0.50033s，phase 0.02906s、child 0.03902s、无剩余 0.00022s；缓存的单一绝对 deadline 与最早边界一致。晚 stderr 真实 overflow 后先前结果仍拒绝；新增测试亦验证 readerror、EOF 尾帧及合法 EOF 成功。 |
| M2 retain/take 孤立完整帧 | CLOSED，仅单 reader/单 parent 消费者 | `reader_append_handoff`：monitoring 暂停生产 `_retain` CALL 前，parent 先消费，再 release，完整 STARTED 真正进入生产 ProtocolState，count 0→1、raw 243bytes。`parent_cursor_handoff`：暂停生产 take 捕获 end 后，reader append，再交接及再次消费，count=1，cursor=1/block=1；没有替换生产列表。 |
| m1 hash scope / 原流字节语义 | OPEN（Minor S） | 稳定 EOF exact/oneover/消费后摘要通过，但实际交错 snapshot 不一致，未完成流仍可报告 all_observed。不能把“GIL 下多步原子”自述当证明。 |

## 有效发现，一次汇总

### Major H：已完成行的 history deadline 会错误中断后续行

位置：`tools/v0_s3_supervisor.py:555`（仅 HISTORY_WAIT_STARTED 添加期限）、`:565` `_fix_history_deadline`、`:578` `_deadline_state` 遍历所有期限；`:604` run 使用拒绝码。`ROW_FINISHED` 没有结束该行期限的有效期。

触发与实测：`probes.py` 经独立前置 guard，真实 pipe 依次给生产 parent 投递 I01 ROW_STARTED/HISTORY_WAIT_STARTED（fake clock=0）、I01 ROW_FINISHED（10）、I02 ROW_STARTED/HISTORY_WAIT_STARTED（500），再于601运行生产 `run()`。phase=1000/child=2000，I02 正确期限=1000；I01 已结束但遗留 deadline=600。实际 `protocol_violation=HISTORY_DEADLINE_EXCEEDED:I01`，终止持有 fake handle、保留根预约，合法后续行被中断。预期是已完成行不再约束后续行，仍保留首次开始/禁止重发审计记录，不能通过删记录允许同一行重复开始。

证据：`observations.json:history_completed_row_expiry` 含完整实际消息、期限和生产返回 evidence；`probes.stdout`，实际 exit=0 表示成功复现错误。此为现有 owner 的行为缺陷，不是基于字典未删除的静态猜测。

### Major C：缺 cleanup 收据时汇总仍给出 12/12 PASS

位置：`tools/v0_s3_coordinator.py:436` `aggregate_twelve_keys`、`:45` TWELVE_REQUIREMENTS、`:489` 可选 cleanup 分支。

触发：传入本 owner 接受的全部命名 aggregate receipts，run/candidate 一致、状态 PASS，真实隔离和 independent 标志 true，但**完全不提供 cleanup**。实测 `pass_count=12`、其余数=0，每个 key PASS；`stage_pass_claim=false/product_gate0=false` 仍在，但不能修正内部全绿事实。预期按照冻结合同“缺任一必需原始收据/清理保持非 PASS”，缺清理证明不得全绿。作者 `test_twelve_keys_are_exactly_twelve_and_complete` 所用 complete_receipts 同样没有 cleanup，既有测试不能作为本义务证明。

证据：独立 `owner_probe.py` → `owner-observations.json:all12_without_cleanup` 和 `owner.stdout`（exit=0）。同时独立反例确认旧 S2 九项不能补绿、缺 independent_score 的 A11/A12 不会 PASS（`observations.json:aggregator_negative`）；并未把合成 receipts 当真实产品通过。这是真正的 owner 汇总假绿，不能仅作为静态接线缺口搁置。

### Major O：父原件 manifest 接受祖先目录链接指向绑定根外的原件

位置：`tools/v0_s3_coordinator.py:338` `_resolve_inside_root` 仅 lstat 最终文件；`:87` `_digest_file` 同样只检查最终对象；`:354` seal_originals；`:380` verify_selected_root 只核根 identity。

触发：本报告下建立真实 synthetic bound root，根 identity 校验成功；root/redirect 是指向本报告另一个 synthetic 目录的链接。使用合法相对引用 redirect/canonical.json/source.json/raw.bin。实测三类原件均被封存，raw 摘要精确等于根外 `EXTERNAL_SYNTHETIC_RAW`，manifest 仍标记原绑定 root。预期拒绝任何经链接逃出该根的原件，不能以相对路径无 `..` 或最终文件为 regular 掩盖祖先链接。

同一原件绑定义务的补充实测：封存后改 synthetic raw，再调用 verify_selected_root 和 manifest，前者仍成功、后者原样返回旧 digest；此方法不证明原件未改。需要最终消费者重核原件，但该串接未在生产调用中找到，不能把“根身份重核”称作“全部原件重核”。不把未找到消费者本身另算缺陷。

证据：`owner-observations.json:symlink_escape/changed_raw`，含实际根、resolve 后路径、清单、新旧 SHA；`owner_probe.py`，`owner.stdout`，exit=0。所有目标均是本 NEW 目录内的自建文件，无读取用户私有外部文件。

### Minor S（原 m1 未闭合）：snapshot 多步发布可混读，完成标志与摘要不一致

位置：`tools/v0_s3_supervisor.py:310` run 的 append→total→finished 发布，`:372` snapshot 尤其386–404；`:909` evidence 依赖 snapshot。

受控交错一：Python3.12 sys.monitoring 只给生产 snapshot 开 INSTRUCTION，在 offset104（kept 已捕获、total 尚未读取）暂停 snapshot 线程。真实管道 producer 再送 hello 并 EOF，reader 实际完成后释放 snapshot。结果 `complete=true,total_observed=5,hashed_bytes=0,sha256=空摘要,hash_scope=in_flight_prefix`；真实 raw=hello、真实 SHA=2cf24d…b9824，没有单一状态同时满足这些字段。

受控交错二：在生产 reader.run offset382 的 STORE_ATTR total 前暂停，真实 world 已 append，但 total 尚未发布。snapshot 报 `hashed_bytes=5,total_observed=0,complete=false`。这直接推翻“GIL 保证多步原子”；单 append/list cursor 的正确性不延伸到多字段一致快照。

第三例：活跃 reader 的空流尚无 EOF，snapshot 却为 `hash_scope=all_observed,complete=false`，稍后真实又到 later；因此只能叫已观察前缀，不能称全流。稳定 EOF 下 exact 262144 和 oneover 262145 的 observed/hashed/scope/raw 及消费后哈希已由定向断言复算，不否定该局部修复。预期是在一个一致发布状态上取快照；完成与否要进入 scope 判据。当前明确证据是诊断/证据一致性问题，未证明绕过 drain 拒绝，故保留 Minor 而不凭空升级成假成功 Major。

证据：`observations.json:snapshot_completed_publication/snapshot_before_total_publication/unfinished_scope`，真实监控 opcode 位置、raw hex 和最终快照均保留。

### Minor A：作者把历史真实 11PASS/2FAIL 同时归给 626d37c，证据归属不准确

位置：root `stream-correction-review-02/received/report.md` 开头、§6。历史 final04 原 receipt 明确 `candidate_sha_claim=01453ee07b4774a55711c5cf5642c12d0394a35c`、collected=13、outcome=FAIL。真实11PASS/2FAIL只属于01453ee；626是后续零进程纠偏候选，不能写成01453ee/626共同拥有该真实成绩。本次只读指出，不改作者或历史证据。

## 实际验证、命令、失败和保护边界

先核对自身初始 HEAD `677a0f7bab066983f3a51082523a2245b3022fc3` 与 clean status；旧 independent-stream-correction-01 等工件均存在，未覆盖、未清理。随后只 checkout 两个干净受跟踪源到精确候选；全部其余 tools 源与候选一致，HEAD 本身不伪称候选。候选 source SHA256：

- supervisor：`8e60509d8412479ed8ed7497d35642be26b1027445aae328a027f1237ba6ee42`
- test：`3a665215e9fa1a434d043fe67e3a49d74ae420b633d099d698442cd480c921c1`

`state.json/source.diff/source-checkout-status.txt` 记录源绑定；root AGENTS、governance、control、冻结合同、附约、上一轮 received review 与原探针均已读取，引用 hash 见 `root-reference-hashes.json`。本地缺失的 fixture 附约从 root 精确路径读取，没有创建替代合同。

所有候选 import 都由新写的 `hardguard.py` 先安装 sys.addaudithook，再 runpy 进入候选/测试；独立于实现 runner。禁止所有 subprocess/socket 审计事件、fork/exec/spawn/system，并拒绝原 shared-counter/ledger 数据库打开。guard selftest 实际拒绝 Popen/system/fork/exec/socket.__new__ 五项，0 OS child；普通探针无拒绝事件。没有 binding、fixture 子进程、网络、服务、下载、模型/GPU、原 ledger 动作。

完整原始 argv/cwd/stdout/stderr/实际 exit 见 `commands.json`。五个受 guard 的入口均使用 `python3.12 -B <NEW>/hardguard.py <NEW>/<entry> <NEW>/<label>.guard.json`：

| 入口 | 实际 exit | 计数/含义 |
|---|---:|---|
| run_selected.py | 0 | **17 collected / 17 passed / 0 skipped / 0 failed**：新增12 + 原 Oracle/caps 必要5；没有整模块运行。 |
| collect_added.py | 0 | **30实际收集，0执行**：原 correction01 新增18 + correction02新增12；清单来自 AST 差分再逐 nodeid 实际 collect，未抄作者数字；不混作30PASS。 |
| probes.py | 0 | 独立行为探针：两种交接、两种 publication 交错、未完scope、4 drain边界、晚overflow、history期限、旧9/缺QS；exit0表示所有探针断言符合实测预期，包含成功复现缺陷。 |
| owner_probe.py | 0 | 缺cleanup全12绿、祖先链接逃逸、封存后原件变更；exit0表示复现。 |
| guard_selftest.py | 0 | 5项拒绝成功，不是真实进程测试。 |

失败保留：初次脚本 here-doc 路径重复 pack 前缀，shell exit2、未创建脚本，后续找不到 guard 也exit2；没有候选 import。原 selected.stdout/selected.stderr 和 setup-failure.md 保留，纠正后使用 selected-02 新文件名，没有覆盖失败。未重跑134全模块/135/121/117/71/257、原18没有重新执行全套、原13没有真实进程执行。没有把跳过、collect-only 或缺陷复现计 PASS。

FakeProcess.close_streams 仅显式关闭 fake 持有写端，未改生产 _StreamReader；真实 EOF positive 的 oracle 合理，但不能据此推断所有原生后代已退出。独立 held-pipe negative 故意不关写端，仍验证生产拒绝；该 fake 修正没有隐藏本轮已测流未完失败。fixture 源与626逐字相同（SHA `1432a6503c07ebed43e9ce36100c18f9840e51af5f6c8d81472ab7439a66df4a`），旧 blocking_partial/NaN/count 三个关键生成/Oracle 函数 AST 完全相同，见 oracle-integrity.json；exact count 保留原 root_retained 断言并实际通过。

独立探针所有 pipe 写端自有，结束时关闭并 join 自有 reader/producer，probes 最后断言只剩主线程；不把 daemon 当清理。自建 synthetic 文件与 pytest-temp 保留在 NEW 内供复核，未删除旧工件。owner synthetic ancestor symlink 在记录后解除，目标原件保留；不触碰任何生产根。

counter 外层只读 hash 前后均 `8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18`，inactive、15 admissions、180 reserved、8.446 spent，见 counter-integrity.json。未退款、清零、新counter或执行binding runner，不能从spent推算可退额度。

## 其余集成 owner 与范围边界

一次性固定 I01–I24 的生产路径、既有证据定位、独立结果和未证明缺口见 `i01-i24-audit.md/json`。profile 默认/warm 均沿 inherited preparation 的首次 exclusive writer 注入单一 s3_budget_binding，默认 S2 {} hook 保持；provider复用 accepted loader/validator；实际 QualityPhase 接线是 run_worker→QualityPhase(...progress_sink)→phase.run，不是用 clean_terminal fixture冒充质量运行。既有 fake-driver 16行 evidence存在，native driver/dependency closure未证明。

residue accessor 使用绑定 root/temp fd、identity核对、只读第一层及512/256边界，静态没有发现本轮新增反例；旧exact/oneover证据不重新记本轮PASS。ParentOriginalEvidence和aggregate_twelve_keys目前只找到测试调用，完整生产phase/archive/最终汇总串接仍缺证；这类静态集成缺口不自动宣告StageNO-GO，也不额外制造缺陷。上列H/C/O均已真实调用生产owner复现，须交root裁决，审查者不改其余owner。

## 当前坐标、完整大纲与交接

以下仅从 root control 的 development_outline 读取，不增加产品完成数；各实现/机器/独审/人签详细原值保留在 root-control-summary.json。

| 交付 | 阶段 | 已完成/总数 | 边界 |
|---|---|---|---|
| V0 | V0-S0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-Min | V0-S1 | 5/5 | 已签仅V0-Min |
| V1前置 | R0 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| V1早期切片 | R1a | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0.1 | V0-S2 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0.2 | V0-S3 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V1 | R1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1 | V1-M1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| V1 | R2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R4 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5a | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5b | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5c | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

1. 当前坐标：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING。
2. 本批完成：限定零进程独审；原M1/M2 closed、m1 open，F0/M3/m2；没有产品机器通过或人签。
3. 最后通过门禁：UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW，621b1bf，仅已签统一切片。
4. 当前阻塞：本次H/C/O实测问题交root集中裁决；真实13、全24和native/质量证明仍缺。
5. 路线：S3-P4离线纠偏承接既定V1路线，不激活V2/V3。
6. 剩余：root分配原owner修复权限、决定新候选和复验范围；本worker不修改代码/控制/旧证据。
7. 下一责任人：root；报告与原始证据在NEW目录，可按精确候选与命令复算。
8. 授权：零进程审查，0真实预算动作；不存在新的机器准入或退款。
9. 证据：source/hash/commands/实际日志/独立观测/固定24审计/完整outline及integrity清单。
10. 停止原因：任务完成，发送一次worker_done后结束，不keep-open；当前已知本工作区1审查实例、无派生/本轮回收0，其他空间存活数本任务未复盘，不能虚报；root在结算后回收本窗口。
