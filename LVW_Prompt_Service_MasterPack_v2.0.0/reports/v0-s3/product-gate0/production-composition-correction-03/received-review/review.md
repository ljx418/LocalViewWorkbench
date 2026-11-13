# 生产组合纠偏02独立审查

结论：**CHANGES_REQUIRED，Fatal 0 / Major 3 / Minor 2**。候选 `8f375f887f0121ab5a0395f032dd74d8a6f0cf0b`，基准 `7dc76ffeec685959f5906c612e58f7e1fc081425`。M05、M07关闭；M04、M06、M08仍开放。FD snapshot的指定修复已独立验证，取消路径的真实锚点FD遗留归入M08；P01的本轮流程与历史事实勘误通过，meta01仍未准确纠正。原M01/M02/M03/M09/m01/m02不重开。

本报告是独审交付，不是产品I24、产品12项、Stage PASS或人签。所有有效发现一次列在下文；作者21PASS不作为关闭依据。

## 独立执行与证据边界

执行前只作文本/AST/哈希检查，保存 `initial-state.json`、`initial-index.bin` 与 `materialization.json`。自身HEAD为 `204e585f81837d9743869b94030ae941b2d52be4`；8项相关源码原字节均等于基准，随后只物化候选5变化源。91个tools顶层Python源码均冻结并逐项匹配候选（实际数量以 `all-source-candidate-comparison.json.checked_count` 为准）；supervisor、coordinator及原冻结owner没有额外修改。索引字节完全不变，未checkout整树/reset/clean/add/commit；既有未跟踪报告保留。未改变任何CMD文件及其CRLF。

冻结 `plan.json` SHA256 `220ee51f57b508f9e70f6a71cbeff48855c869f11c388fdb2fff242f2919b231`，协调者 `msg_7400c44baf53` ACK后执行一次。精确argv、cwd、起止时间、exit都在 `exit.json`；argv为 `/usr/bin/python3 -I -B <NEW>/guard.py <NEW>/runner.py <NEW>/guard.json`，cwd本review包根。独立37个case，0次pytest.main/collection，不执行作者21节点或旧大套件；14.992秒，exit1，stdout/stderr分别保留在 `stdout.log`/`stderr.log`，未超时，未复跑。

37个调用记录为26断言通过、11断言失败，其中8个是下文有效缺陷复现，3个是本审探针限制，**不能把37或26充作产品通过数**：

- `M04-io-exact`真实读取成功16bytes，read请求为[17,1]，最后请求返回EOF；探针对“累计请求参数≤17”的断言过强，不能据此声称真实读入超界。静态循环按实际累计bytes保证≤limit+1；lying-size探针单次实际读17后拒绝。原日志不改。
- `M06-PRECHECK-root`和`M06-PRECHECK-ancestor`在main完成后，测试包装器访问未创建的seam._worker抛AttributeError，未保存完整返回值。这两个独立探针无效，不算产品缺陷或通过；不自动修复重跑。M06其他6个替换探针及创建接缝已有足够有效证据。
- `M05-type-bool`增加了原文档不存在的provider_call_count=True，实际证明文档不一致拒绝，不独立证明既有数值字段1→true替换。类型敏感性另由 `_same_document` 调用canonical_json的实际代码核验：JSON true/1/1.0编码不同；不冒称该case动态验证了数值替换。

独立audit hook在任何候选/pytest导入之前武装，拒绝subprocess/socket/fork/exec/spawn/system/sqlite3.connect及原counter/ledger open；6个自检仅 `sys.audit` 事件，无真实动作。runtime denials为空。本轮仅本进程thread、pipe、合成文件与既有命名依赖；无OS业务helper、网络、models/GPU、真实native/服务、下载或用户媒体。guard之后核源码/工具/依赖pins，再显式append已装 `/home/administrator/.local/lib/python3.12/site-packages`；pytest仅提供MonkeyPatch并满足fixture模块导入，无插件运行、site.main或.pth加载。沿用plan02已封存命名依赖pins（pytest/Pillow等），这是命名文件scope，不能声称全传递依赖封存或没有使用已有Python二进制扩展。

counter仅guard外前后各一次只读：`counter-before.json`/`counter-after.json`，固定hash `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive/28/240/12.362不变。没有写/退款/清零/新counter/旧13grant复活。counter不变仅为该counter事实，零业务动作依据本轮前置guard和冻结执行范围。

## 有效Major

### M04 OPEN：外部READ_ONLY_DIRECTORY锚点仍只保护叶目录

位置：`tools/v0_s3_quality_worker.py::_read_through_anchor` 外依赖分支；`tools/v0_s3_controller_io.py::open_read_only_directory`（313起）。

五个真实worker访问器在run-root父组件换symlink时全部拒绝，合法外部命名依赖正例也成功。但外部锚点由 `os.open(str(path), directory_open_flags())` 打开，O_NOFOLLOW只作用于锚点叶目录，未从可信根逐层打开锚点祖先。

独立 `M04-external-ancestor.json`：先构造封存context明示的synthetic dependency-parent/deps及命名文件，通过真实 `WorkerContext.dependency_manifest()` 校验正例；将dependency-parent移到同报告owned outside目录，用symlink替换原父目录，再调用真实方法。**error=null、accepted_outside=true**，同hash的外部bytes被接受。锚点来源虽明确，祖先仍可换成symlink，读后的叶目录identity核验无法发现此重定向。

要求：外锚也须有明确可信链并逐级no-follow，不能退回leaf-only。本轮有界、regular/nonblock、unsupported failclosed与FD关闭没有发现另一个有效缺陷；不以这些已改善处关闭祖先缺口。

### M06 OPEN：输出链晚于PRECHECK绑定，且创建fd与观察path未关联

位置：`ProductionController::_precheck/_bind_root_identity/_controller_directory_descriptor/_observe_controller_chain`（1250–1370附近）。PRECHECK只绑定root，输出目录到reservation阶段才打开； `_observe_controller_chain` 随后用绝对path的lstat观察，与ensure_directory_chain返回的fd没有identity交叉核验。

有效独立证据：

- `M06-PRECHECK-temp.json`：PRECHECK后将已有temp改名保留并建普通新temp。新temp收到**reservation和receipt**；state UNKNOWN_RETAINED不能掩盖新对象写入，receipt_persisted=true。
- `M06-PRECHECK-controller.json`：PRECHECK后controller目录换成普通新对象，新目录收到**reservation、summary、receipt**，返回SUMMARY_PERSISTED。
- `M06-create-race.json`：真实ensure_directory_chain返回后、观察路径前，改名保留该目录并创建新普通目录。已持有fd inode2893253，当前路径inode2893254；仍返回SUMMARY_PERSISTED/receipt_persisted=true。三个文件实际写入held-output旧目录，而声明receipt_path/summary_path指向新的空目录。这证明创建与使用之间的fd/path身份断链，不是假想竞争，也没有改动原生产判定owner。
- RECEIPTS_BOUND后换root/temp/controller普通对象、换root父祖先symlink四例全部拒绝summary和receipt，确有改善；不能覆盖较早窗口。

要求：PRECHECK建立并持续持有输出链，创建所得fd必须与记录身份一致，reservation/summary/receipt全生命周期复用；路径替换拒绝并保留partial。以上原件均保留，未删除、未在未知目录补写收据。

### M08 OPEN：终态取消漏anchors；observer普通异常再逃逸；单独持久化失败不转UNKNOWN

位置：`ProductionController.run` finally（2284–2313附近）、`_persist_receipt`（2089起）、`_record_post_release_cleanup`（1395起）。

修复有效部分：直接令 `_persist_receipt` 自身RuntimeError，并先令 `_bind_receipts` ValueError，`M08-direct-double.json`得到结构化UNKNOWN，primary `CONTROLLER_UNEXPECTED_EXCEPTION:ValueError`与secondary `CONTROLLER_RECEIPT_PERSISTENCE_FAILED:RuntimeError`分开，receipt_persisted=false、FD归零；真实write函数双RuntimeError的 `M08-write-double.json`同样通过。

剩余有效问题：

- `M08-cancel-keyboard.json` / `M08-cancel-system.json`：终态 `_persist_receipt` 自身抛KeyboardInterrupt/SystemExit。异常确实向外传播，worker线程已结束，但 `_release_anchors`位于该调用之后，未被独立finally保护。分别留下自有root/output两个FD：3/4，实际fstat确认目录inode分别2894401/2894430与2894612/2894641。不是os.listdir内部复制FD。本审先保存证据，再调用已捕获controller对象自己的 `_release_anchors()`清理，未关闭未知FD；批次终态干净不抹去产品返回时的泄漏。
- `M08-observer-runtime.json`：新增 `_record_post_release_cleanup`抛普通RuntimeError，finally中没有兜底，main返回exit5、**stdout空、receipt=null**，stderr仅`S3_CONTROLLER_REFUSED EXCEPTION RuntimeError`。在已释放anchors之后新增的观察不能破坏结构化终态。受控异常注入证明异常收口，不声称真实procfs当时故障。
- `M08-direct-only.json`：只令终态 `_persist_receipt`自身RuntimeError，summary已写成功；返回**exit0、SUMMARY_PERSISTED、receipt_persisted=false**，没有UNKNOWN/unknown_reason。虽然持久化未证被披露，仍不满足约定的终态存储异常结构化UNKNOWN要求。

要求：普通异常保留主次失败与持久化未证，observer异常不得逃出结构化返回；anchors释放必须跨KeyboardInterrupt/SystemExit，且取消仍继续传播，不被吞掉。

## 关闭项与FD修复

**M05 CLOSED**：`M05-disk-window.json`经真实原loader及 `_SealedBytesBoundary`先解析16PASS，再将磁盘canonical改成15PASS1FAIL。父owner封存新bytes时被 `CONTROLLER_ORIGINALS_CHANGED_BEFORE_SEAL`拒绝，UNKNOWN、无summary，旧文档没有配新hash发布。`M05-invalid-loader.json`将真实canonical kind变为invalid，原loader仍返回`QS_CANONICAL_RECEIPT_KIND_INVALID`拒绝，非绕过原校验。`_verify_originals`对canonical与sourceplan的同批安全读bytes经原boundary校验、严格解码交叉核对，封存digest再比对；正例所有manifest canonical/source_plan/raw实际hash以及controller/worker provenance逐项匹配。承诺只到最后观察边界，不承诺返回后永久不变或多文件原子快照。类型探针限制见上，不据错误命名夸大动态覆盖。

**M07 CLOSED**：独立positive真实16行QualityPhase、pipe、parent reader、canonical与manifest链成功，A03/output_contract、A05/no_overwrite、A09/resource_budget正式三收据均BLOCKED，composition_facts另列且不填正式同名键，顶层0产品PASS。`M07-provider-refusal.json`保留真实失败；`M07-last-release.json`最后一行release失败得到15PASS1FAIL，正式义务不PASS，root/reservation保留且cleanup_proven=false。合成事实不替代四输出、格式切换0推理、人工稿异常保护或真实性能资源义务。

**FD snapshot指定修复 CLOSED；不为原FD8追认身份**：逐条fstat，EBADF条目过滤；非EBADF未知条目保留并标注；enumeration OSError返回None。`FD-real.json`真实打开本审自有文件FD被检出，关闭后才消失；`FD-unknown.json`该真实FD的fstat受控EACCES仍在open+unverified_entries；`FD-enumeration.json`为null，未伪造空集。正例snapshot包含closed_entries且当前open均可核验，正常返回无新FD。

原root stdlib探针只证明os.listdir(fd)会列出已关闭的复制FD，**不能证明attempt02的FD8原身份**。作者§8.2所谓“快照时开、之后关闭/改变编号分配”的具体归因缺独立身份记录；旧批次末尾无残留也不能追认该中间时刻。本文不把这段文字反向判成真实FD8资源泄漏。

PRE_RELEASE收据明确命名controller持有的root/output anchors并从该时点差集排除；POST_RELEASE诊断仅返回值新增，正例持久receipt确实没有`fd_cleanup_post_release`字段。未用GC、忽略FD8/高编号、丢弃未知项或关闭非自有FD制造通过。批次最后fstat身份前后完全相同，线程仅MainThread（`cleanup.json`）；M08取消中间真实泄漏单独保留。

## P01与报告Minor

**P01本轮关闭**：历史四批direct pytest、至少10业务shim/helper和syntheticSQLite越包事实已正确撤回零动作声明，精确总数UNKNOWN；不从旧counter不变推断无额外动作。root validation-plan01/02/03 ACK链及fd-snapshot-correction裁决已读。静态核runner/sourcepins/dependency pins/期望nodeids和收集顺序，原stdout/stderr/guard保留于root received及NEW `P01-author-plan-audit.json`：attempt01缺pytest、0collection/0call、exit1；attempt02 19/19、18PASS1FAIL、exit1；attempt03 21/21PASS、exit0。没有重跑这些节点。

作者attempt02/03 commands记录脚本及guard日志参数是相对路径，ACK是绝对路径，**argv字符串并非逐字一致**；cwd相同，解析到完全相同目标，runner/guard哈希一致，nodeids集合/顺序及pins一致。该命令字面差异如实保留，不制造解释器替换或未经ACK额外执行的结论。封存证据未见本纠偏02新增未ACK pytest/compat/helper/sqlite；不能将静态与给定日志扩大为未知终端历史的全局零动作证明。

**meta01 OPEN，Minor**：7而非8的数字已改，但作者§4换成新的7源清单，仍未纠正原冻结清单归属。已核 `received-review/author-candidate.json.frozen_sources` 与原独审 `frozen-sources.json.files`逐项完全相同：quality_phase、coordinator、runtime_binding、stage_runtime、budget_authority、local_program_authority、v0_s2_runtime。作者新列的controller_io/production_controller/quality_worker/supervisor/test_production等不是该原frozen清单。证据 `meta01-oracle.json`。旧报告不改。

**m03 NEW OPEN，Minor，报告前后矛盾与无证FD8定性**：作者§7标题仍“两次root ACK/两次真实执行”，§7.5仍attempt01/02，§10剩余工作仍“root ACK后执行唯一批次”，但§8.3/终态已记三次尝试与attempt03完成；§8.2对FD8归因超出当时身份证据，后文却承认不能断言确切归属。要求统一最终报告口径、保留历史失败与UNKNOWN，不据措辞虚构实际资源泄漏。本Minor合并记录这些同一报告一致性问题，不重复增加Major。

## 输入与工作区完整性

作者synthetic archive SHA256 `49a290b66ea80eefe458ca2767d4d5ffdf059eb99e008d08650eb94e73164fd3`，4025 entries，与其index完全一致。只读逐成员计算hash，并与原impl目录逐项比对：3993 regular bytes + 32 symlink元数据全部一致，0 mismatch（`archive-vs-original-readonly.json`）。链接目标仅视作元数据，不执行、不跟随；全程未解档。原review-full-evidence.zip也逐成员只读记录hash与路径/链接metadata；含78链接，未解档、未执行其目标。原impl证据目录没有写入。

`final-integrity.json`保存HEAD/index/status和源归属，所有冻结源码/工具pins未漂移。NEW `archive-integrity.json`提供完整成员列表/hash；未把链接metadata当命令。三次作者原始流与guard、counter保持原件，不覆盖失败证据。

## 固定未证范围及停止状态

I01–I24固定分母、产品12项、真实native/Windows/A06、原ledger、质量门限与人签均未在本轮证明；正式A03/A05/A09完整义务仍未证。不签StagePASS，不推进Stage，不修改control或产品合同。

| 停止字段 | 事实 |
|---|---|
| 当前坐标 | 以root execution-control为准：R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION |
| 本批完成 | 一次ACK的37-case独立审查、静态证据审计、3Major/2Minor汇总 |
| 最后通过门禁 | 本轮无新增Stage门禁；M05/M07及指定FD快照修复独审关闭 |
| 当前阻塞 | M04/M06/M08；meta01/m03报告修正 |
| 全局路线位置 | 既有统一切片不扩大为完整R1或旧S2人签 |
| 剩余工作 | root集中裁决并派发修复；不得以本报告补产品PASS |
| 下一责任人 | coordinator/root |
| 所需授权 | 无新增人类授权请求；后续执行仍按冻结ACK流程 |
| 证据目录 | 本NEW独审目录 |
| 精确停止原因 | 已完成本次审查交付；一次批次执行完毕，不自动补例/复跑；交root归档 |

当前V0–V3大纲（直接读取root control，完成/总子项，不是工时百分比）：

- V0-S0 1/2：基线探索
- V0-S1 5/5：图片与独立人工
- R0 1/2：独立服务复核
- R1a 5/5：单图React/FastAPI
- V0-S2 7/8：视频与资源控制
- V0-S3 0/6：离线质量与增量包
- R1 0/4：人工业务骨架
- V1-M1 0/3：多镜头拆分与逐镜头人物场景动作
- R2 0/4：任务与正式运行包
- R3 0/4：镜头资产与检索
- R4 0/4：MCP与恢复
- R5a 0/4：证据与建议合同
- R5b 0/4：受控生成交接
- R5c 0/4：集成与完整交付
