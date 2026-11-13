# S3-P4 production-composition-01 独立审查

结论：**CHANGES_REQUIRED；Fatal 0 / Major 9 / Minor 2**。候选 `7c27a11111ede5bb2eb449211f5450270d884ee3`，对比 `c6bce90eeac384d534ebb7601193693840b5b70d`（源码基线 072）。这是组件审查，不签固定 I01–I24、产品12、Stage PASS 或人工签署；`stage_pass_claim=false`、`product_gate0=false`。

## 1. 身份、授权和原件

审查 HEAD 保持 `204e585f81837d9743869b94030ae941b2d52be4`。开工保存 HEAD、完整 status、index 原始字节和 worker 原源码；新增两个源码原先不存在，另存 absence 记录。逐字节核对 101 份既有 tools 文件：与 c6bce90 一致；四份前轮物化源码属于 review 所有，未被新任务覆盖。唯一既有例外为 `open_lvw_browser.cmd` 的干净 CMD CRLF，与候选 LF 归一化相同，未执行。

只有 controller、composition test、quality_worker 三源按候选 git blob 精确物化。其他 tools 与新候选逐项比对；无 checkout/reset/clean、源码暂存或提交。所有新报告、脚本、临时合成文件均在本目录。`source-preflight.json`、`source-materialization.json`、`initial-state.json`、`initial-index.bin`、`final-state.json` 可复算。

已读 root AGENTS/governance README/parallel/execution-control/docs24、冻结 contract、fixture-acceptance、received-review/remaining-workpack 与作者 received 原始材料；输入摘要见 `input-integrity.json`。author received 的常规文件逐一与精确候选中 implementation 报告 blob 对比，见 `author-crosscheck.json`，不信作者 READY/PASS 标签。

原 counter 仅由外层只读，前后 SHA256 均 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`，inactive、28 starts、240 reserved seconds、12.362 spent seconds；无退款、清零、新 counter、原 grant 复活。原 ledger 未读。旧13仅保留072相同源码范围的既有13 PASS证据，未重跑、未转记为新候选已过13。新 worker.main seam 的兼容验证单列。

## 2. 实际执行与方法

`commands.json` 保存完整 argv/cwd/开始结束/exit；各步骤分别保存 stdout、stderr、guard receipt。所有候选 import 前使用独立 Python audit hook 硬禁 subprocess、socket、fork、exec/spawn/system、sqlite3.connect、原ledger与shared counter读取。selftest 8 次预期拒绝成功；三个候选执行批次 guard denials 全零。禁止能力未靠作者 monkeypatch 单独维持。

事前范围见 `selection.json`：16 个必要新增组合负例、5 个 worker/context/history/fixed-command 兼容节点、自写独立正式 main 全链与攻击反例；未重跑84 integration/123/13/41/186/257。首次集中37节点：33 assertion passed / 4 assertion failed，exit1。四个失败是独审 oracle 假设错误：首行释放/残留失败会阻止后15行，output_contract 因此实际 FAIL；零额度预算不能发布完整收据；关闭 pipe 阻止 phase 后续文件写入，晚到效应表现为合成 provider 调用。原脚本快照和日志完整保留，未将这些失败当作候选漏洞证据。

只纠正失败 oracle，并新增末行释放失败变体，窄复验6节点全部 assertion passed，exit0；未重跑整个集中范围。另对尚未完成的 QS owner 关切窄验2节点：真实 recompute_scores 正例及外来 raw hash 拒绝，exit0。合计45次pytest节点调用、40个唯一节点；最新 oracle 对40节点均可判定，**assertion通过/exit0包含缺陷复现，绝不是产品PASS**。候选主链自身的 summary exit0 也不是验收通过。

独立正例通过正式 `controller.main`，只在 Python 构造位置注入 typed seam；CLI 没有增加 seam 开关。真实 WorkerContext.load → worker.main → run_worker → QualityPhase.run 16行 → ProtocolWriter/真实 os.pipe → ParentSupervisor 真实 reader/66消息/terminal → phase 实际 canonical/sourceplan → ParentOriginalEvidence 真 seal/manifest重核 → 原事实适配 → aggregate12 → O_EXCL summary。driver/spawner/父时钟为显式合成边界；**没有 native 子进程**。未手写 canonical、未用 complete_receipts、未以内层函数直调替代此正例 controller。

正例 run/candidate/hash/root/ordinal/source_bytes/source_sha、82件manifest原件、summary哈希逐项复算见 `positive-chain-verification.json`。所有真实合成文件保留在 pytest-temp。正例fd/thread/reader关闭；异常探针的1个漏fd由独审显式 seam.close收尾，不能算候选已清理。阻塞探针实际35秒返回UNKNOWN，原线程未退出；由独审释放自己的Event并join收尾，未假装线程kill、未用poll=0。全批退出时仅MainThread且fd恢复，见 concentrated-results 与 blocked-thread-late-write。

## 3. 一次汇总的有效发现

以下位置相对 tools；触发来自实际controller主链，除明确标出的纯验证器/spy/静态证据。未修改候选修复任何问题。

| ID / 级别 | 位置 | 触发、预期、实际与证据 |
|---|---|---|
| M01 Major | production_controller:327–330、405–416 | `_bound_receipt` 对 status 字符串使用 `is not`。正常JSON解码的 `"PROVEN"` 与期望值相等而非同一对象，native_custody/gpu/install/rollback/grant均报 PROOF_MISSING:status。预期正确类型和值比较，且准入仍由权威证明；实际正常数据不可达。`native-json-proof-comparison.json`：预算仅受控spy，不读ledger、不spawn；同字面量Python对象反而可过。不能将此bug当作可靠failclosed。 |
| M02 Major | production_controller:334–448；quality_worker:335–342、352–373 | native收据仍只检查run/candidate、调用者JSON的PROVEN/布尔和自算hash；grant不核authorization/scope/额度/deadline/权威签发者；tool_closure甚至不核同run身份。S3BudgetBindingProvider.sealed只证绑定配置形状/身份，不证原ledger授权余额，也未绑定这些native/grant证明的权威。worker默认入口直接构造native driver，没有controller admission能力交接。预期当前能力明确NOT_PROVEN/0spawn，未来由已接受有限owner校验；实际只是当前字符串bug阻住这些不可信引用。原始JSON目前**未成功放开native**；没有尝试修补is或真实启动。`native-json-proof-comparison.json`、`worker-main-default-and-stream.json`及静态代码：factory spy只证worker可达driver构造，不声称真实模型已运行。 |
| M03 Major | production_controller:273–284、613–617、812–835、1125；quality_worker:335 | controller CLI hash可缺省，生产命令不携worker seal，worker.main再次load不验hash。受控driver_factory在已seal的首次load后改driver_arguments路径，第二次main照用已变文档并完成16行/summary，stage_binding仍PASS且引用旧hash。controller_context provenance也错误填worker_context hash，正例即不等于实际controller context hash。预期context/hash从入口到worker/summary不丢失；实际绑定断链。`worker-second-load-context-drift.json`、`canonical-after-manifest-tamper.json`、positive-chain-oracle。 |
| M04 Major | production_controller:141–149、293–319、435–436 | 新 `_read_bounded` 先Path.read_bytes读完整文件，随后才验8MiB；无regular/no-follow/nonblock/受控根读取。8MiB+1完整进入内存后才拒绝。预期有限读取、拒绝FIFO/设备/redirect，不以新不安全read替代owner；实际尺寸限制不能限制实际读取或阻塞。`context-read-bound.json`确认读取长度8388609；FIFO无限阻塞与任意referenced路径为代码推论，未创建阻塞OSfixture或读取未知原件。 |
| M05 Major | production_controller:914–943、1117–1139、1239–1248 | manifest虽实际调用，却在消费/summary前不再用owner核验；`_provenance`另用Path.read_bytes绕过安全owner。ORIGINALS_VERIFIED后改raw，summary仍persist且file_safety PASS；改canonical后summary provenance hash与manifest canonical hash矛盾；将根改为指向本任务原根的symlink也被接受。预期变化/错根保持UNKNOWN且不消费旧seal；实际消费旧manifest。`manifest-after-verify-{tamper,oracle}.json`、`canonical-after-manifest-tamper.json`、`root-after-manifest-symlink.json`。不是ParentOriginalEvidence自身回归。 |
| M06 Major | production_controller:1158–1187 | O_EXCL只保护叶文件，mkdir/open跟随祖先。RECEIPTS_BOUND后将summary目录链接到本报告内另一合成目录，summary实际写到root外，仍SUMMARY_PERSISTED。预期绑定root身份、相对安全目录句柄与全路径no-follow排他落盘；实际根外写入。`summary-outside-{symlink,oracle}.json`，只操作自己合成文件。 |
| M07 Major | production_controller:986–1024、1254–1255 | resource_budget仅看provider_calls_reserved非None，no_overwrite无条件PASS，output_contract只看两字段存在。真实第16行释放失败：15PASS/1FAIL，内部output_contract/resource_budget/no_overwrite仍PASS，顶层12BLOCKED遮住了错误事实；首行释放/残留失败也保留resource_budget/no_overwrite PASS。清理未证时controller还把root_retained/reservation_retained写false，来自parent线程退出而非原cleanup义务。预期按实际全义务非PASS且保留未证预约；实际文件存在/计数存在冒充全义务。`last-row-release-{output-pass,oracle}.json`、`false-pass-*.json`。未声称no_overwrite已实际覆盖人工稿；缺其全义务证据已足以不能PASS。 |
| M08 Major | production_controller:1191–1270、1398–1402 | manifest后删除本任务canonical使_provenance抛FileNotFoundError；run只捕ControllerError且无finally_finish，main返回exit5文本，缺UNKNOWN保留收据，泄漏1个stdin fd。预期异常仍持久保留UNKNOWN/预约并有界finally清理；实际只有顶层异常字符串。`unhandled-read-error.json`（fd9），独审随后显式close回收并记录，不冒充owner清理。 |
| M09 Major | production_controller:1212–1224、1158–1168 | summary已存在的同run在precheck不拒绝，真实phase16行又执行一次，直到最终落盘才UNKNOWN/不覆盖。预期预封存阶段识别已存在终态/预约，不重复发送；实际seam.spawns=1、quality16 PASS、已有summary保持。`summary-preexisting-spawn.json`。这里只合成运行，不称已消耗原ledger。 |
| m01 Minor | production_controller:578–579、586–597、730–738、1296–1326 | 线程daemon=True、terminate/kill为空。阻塞driver在35秒返回时仍活，UNKNOWN/预约保留及worker_thread_finished=false是诚实的；但daemon不是退出证明，不能将此seam当native可清理能力。独审释放Event后synthetic provider_calls从0变1才退出；无phase文件晚到写入（pipe关闭触发BrokenPipe）。`blocked-thread-late-write.json`。应由可协作取消边界控制，无法kill时明确隔离保留，不用daemon解决生命周期。 |
| m02 Minor | quality_worker:333、343–348；production_controller:617 | seam传二进制stderr文件，而worker.main错误处理写str。受控native factory WorkerError在binary stream下变TypeError，被外层误记EXCEPTION TypeError，原拒绝码丢失；默认真实CLI仍用text stderr，不是默认行为回退。预期兼容内部stream类型并保留准确拒绝码。`worker-main-default-and-stream.json`。 |

M01与M02是不同缺口：修正字符串比较不等于授权真实性已实现；当前缺native能力本身不是要求本审真实启动的理由。M04尺寸实测只证先全读，设备/FIFO风险是静态结论。M05/M06所有替换与链接目标均属本审NEW目录；未操作用户媒体、未知原件或原ledger。

## 4. C01–C12 / I01–I24 映射和明确未证明项

逐项机器映射见 `coverage.json`，不将C映射变成新增分母。

| C映射 | 已验证的组件范围 | 缺口/发现 |
|---|---|---|
| C01/I03/I04/I23 | 错hash/candidate/auth/root/投影/schema、缺native证明均0spawn拒绝 | M01–M04；native可信权威、有限grant和worker能力传递未实现 |
| C02/I07 | 正式main→真实phase16行/66消息/pipe/reader/canonical/manifest/summary；精确候选合成身份 | 只有进程内synthetic，非native后代/Windows/工具闭包 |
| C03/I10/I11/I21 | 行/history顺序；duplicate history拒绝且不延deadline；10800/600/21600常量保留 | 不证明真实长运行deadline、所有partial I/O/late stream排列 |
| C04/I13/I14 | 未完worker/错terminal/缺canonical保持UNKNOWN，不重发；fsync失败保留root/预约/已有partial summary | M07–M09、m01/m02；未证明native cleanup、父失联全部组合 |
| C05/I16 | 实际ParentOriginalEvidence.manifest重核可拒前置改写/换根 | M05/M06；重核后真实消费链与写入边界破裂 |
| C06/I19/I20 | aggregate固定12、缺QS/A06/WebP/install/rollback/cleanup稳定非PASS；真实QS owner匹配和错raw拒绝 | M07；输出/预算/不覆盖全义务未证，实际独立评分人未参与 |
| C07/I24 | 正例同run/candidate/projection/sourceplan/raw/manifest字段闭合 | M03/M05来源链错误；准确context hash和消费时root身份未封闭 |
| C08/I22 | preimport硬guard、自测8拒绝，候选执行零受禁动作；最终fd/thread有独审收尾证据 | 仅隔离测试进程清理，不是产品服务/GPU清理 |
| C09/I01/I02/I05/I06 | 工厂/profile/runtime源码与072相同，default worker仍走native构造spy | 本轮不安装、不创建ledger、不扣账；不新签旧组件PASS |
| C10/I17/I18 | 复用residue accessor；unknown观察保留、不删除未知文件；failure-residue实际非PASS行 | M07清理状态/保留事实适配错误；平台reparse语义未证 |
| C11/I15 | 原RecoveryEntry，无自报PID custody、不重发、不终止未知进程 | 真实父崩溃与native后代恢复未证明，历史被覆盖流不要求伪恢复 |
| C12/全24 | coverage逐I机器列owner、已有证据和剩余缺口 | 不签固定24、产品12、新28或StagePASS |

## 5. 日志真实性和历史分母

作者最终原始节点确为123 collection、122PASS/1SKIP（33新组合+84 integration+6 supervisor选点，其中1真进程skip）。两个interim分别118/118PASS、123/122PASS/1SKIP；三批合计364个pytest节点调用、362PASS/2SKIP，是执行次数而非364独立用例。每批还有一条单独composition node（三个不同node ID），不是pytest分母的一部分。最终runner声明candidate为c6bce90、实际composition为a*40/b*64合成身份；只是attestation与synthetic identity，不能冒充精确候选真实native执行。本审另用精确7c27a…合成主链验证。

author原始收据中各run execution_attempts=1只适用于各自那批，不覆盖两个interim。它们历史run-root未保留是作者已披露限制，本审不伪造恢复。received文件与候选blob一致只证材料身份，不将作者outcome PASS转成组件准入通过。旧13原始组件证据与本轮离线接线分母独立，grant仍EXPIRED_NO_REPLAY。

## 6. 后续单包修正建议与边界

root可一次冻结修正包：权威不可用时显式硬拒native；修正类型/相等校验同时接真实有限grant能力，不能仅把is改==后放行自写JSON；worker入口继续携seal与同root能力；原owner的安全读取、manifest消费重核和dirfd/no-follow排他summary贯穿终点；按完整事实生成内部收据及保留语义；所有异常finally收尾并记录UNKNOWN；已存在终态在任何发送前拒绝；收窄可取消thread seam并统一stream类型。只定向验证这些发现，不机械重跑旧全量，不跨到真实native/GPU/原ledger运行。

尚未证明：Windows/native后代custody/GPU释放、真实原ledger动作、真实服务/模型/媒体、完整工具依赖闭包、真实A06、真实独立质量16评分、WebP、安装/回滚、完整I01–I24及产品12、root迁移部署、人工体验/发布。缺失项保持NOT_RUN/BLOCKED。QS合成分数只证明重算和来源拒绝，不代表人类标注或真实内容质量。

## 7. 开发大纲与角色状态

当前权威coordinate：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION；当前阻塞门S3_P4_PRODUCTION_QUALITY_MANIFEST_AGGREGATION_COMPOSITION。implementation新候选已提交待修；机器仅本报告限定离线；独审CHANGES_REQUIRED；未新增人工签署。

V0–V3总纲（完成子项/总数，来自root execution-control快照）：V0-S0 1/2（历史NO_GO）；V0-S1 5/5（仅V0-Min已签）；R0 1/2；R1a 5/5（仅单图切片）；V0-S2 7/8（完整旧S2未签）；V0-S3 0/6；R1 0/4（统一切片3/3和UM10/人签限定范围保留）；V1-M1 0/3；R2 0/4；V2 R3 0/4、R4 0/4；V3 R5a/R5b/R5c各0/4。V2设计批准不等于实施激活。

本任务未派生Agent；review工作区只有本审任务，自身未回收其他窗口，回收数0。跨空间存活数本审未盘点、不宣称已退出；worker_done后由root核对Orca生命周期及时回收此独审窗口。原始证据只在NEW目录，未commit，留root归档。
