# S3-PREP-C 独立审查与视觉预标（接续定稿）

审查完成，**Fatal 0 / Major 3**。建议 root 对工具控制流裁决 CHANGES_REQUIRED；不签 Stage PASS、Gate0、质量通过、人工签署或发布。原真实运行证据可复核，不能据其成功推断异常控制流正确；已消费 child 不续期、不重跑。

候选 `e1798f33ba51dcadbf9f0333641d62d14a801491`；证据 tip `335a8b973ab9b0fe192c03f59e608f9976658238`；root `20e408db8371a1058a5c44c059d1601caf964d85` 在历史中，已独立核实。候选、脚本、规格及工具hash见 independent-review.json / raw/continuation-verification.json。

## 接续来历与边界

首次检查只有指定independent-01目录未跟踪，HEAD已为证据tip。协调者确认其来自旧dispatch `ctx_f9a99284a861` 的Claude独审草稿：HTTP429 Token Plan额度耗尽，旧worker已停止、ptyKilled=true；授权本dispatch `ctx_464e91f112d9` 保留接续，无需重merge。原四份草稿复制保存在 raw/superseded-draft-*，明确仅为未完成历史，不是当前结论。原build-prelabels.py也是旧撰写脚本，不应再用于生成最终预标；最新作者脚本为 raw/finalize-continuation.py。

本接续独审亲自阅读候选代码与证据、复算派生树、查看全部32候选。读过前代理草稿后进行视觉复核，因此不是第二次从零盲标；仍盲于LVW历史识别raw、人工稿和expected答案。未查找这些答案，未按模型表现选样。C13界面文字仅作为批准预览的可见内容，不采信页面质量/模型声明。

未访问原testSource文件（stat/hash/probe/decode均0），未重跑真实child；0 GPU/推理/模型API/服务/网络/下载/完整checkpoint。仅原runtime根内只读查看已登记预览，无媒体进入Git，无上传/发布，无原预览重生成。未删除任何原产物或历史残留。旧S2仍7/8、原生人签PENDING；CHANGE-V1-S2-HANDOFF-01允许本次准备，不把旧人签列为本批阻塞。

## 测试与集中证据核对

原独审一次命令：`PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tools/test_s3_sample_preparation.py -q -p no:cacheprovider --basetemp=<owned-temp>`。原stdout为 **45 passed in 21.30s**、EXIT=0；源码45个test函数，与实现者声称一致。按接续指令未重复跑套件。原清理记录为87条/29,544,179 bytes，路径删除后不存在；这是原worker记录，不能说本会话亲见其测试过程。

本次在自有TemporaryDirectory执行3个聚焦检查脚本，均exit0：continuation-check.py（绑定核对及大小/deadline两个反例）、output-budget-counterexample.py、refusal-owned-check.py。它们成功复现下面三项行为失败，**exit0不表示工具通过**。合成媒体仅在临时根，未调真实decoder；另启动1个自有Python sleep子进程，超时后returncode=-15且reaped，未操作其它PID。各临时根已实测不存在；证据见同名stdout/stderr/exit及JSON。

- 工作树script/test/borrowed runner逐字节匹配候选Git blob；child/catalog/holdout/packet hash复算保留。当前已装Python/FFmpeg/ffprobe可执行文件与Pillow Image.py hash吻合preflight。不是完整依赖树绑定，也不证明原运行每一刻未发生替换。
- 首次preflight拒绝原因holdout.content_sha256_exact与原4个0保留。build_preflight读取元数据/Git/工具及源根目录，不读取selected文件；异常/拒绝preflight的合成prepare/resolve_source边界调用0。malformed JSON抛异常但仍先于源访问。没有完整OS审计，0不是syscall实测。
- holdout确为11留样加2个FREEZE元数据hash：无遗漏、无未知extra；并未减分母或去排除。只读FREEZE元数据，未读取其expected文件。
- 单一真实run保持32=32 eligible+0 not_eligible+0 not_run。12 ffprobe、48 frame、60条命令退出0；60条command hash与runtime原文吻合，stdout/stderr的hash/bytes与已提交原日志吻合。
- 32次hash与20次图片decode有逐候选收据/控制流支撑，不能说都有独立OS日志；源hash与child逐项相同但未重hash原片。记录admitted/hash bytes均83,043,322，wall为13.293s；wall是收据单调差值，未声称逐命令时钟独立复算。
- 对收据登记342个保留文件重新测量hash/size，全吻合，总计3,963,572 bytes；100个index相对链接有效；staging已不存在。记录staging累计1,493,073 bytes，原run两项之和低于83,886,080。详见raw/continuation-verification.json，包含全部相对路径/hash/大小。
- decoder磁盘IO明确 **NOT_MEASURED_NOT_CLAIMED**。原run零模型等收据常量与源码路径相容，不当作可排除一切外联的OS证据。

## 一次性汇总的阻断发现

### MAJ-01 — 源大小变化未全局终止（Major）

位置 `tools/s3_sample_preparation.py:1540`。检测冻结源变化后整体SOURCE_CHANGED终态，不访问后续候选。 大小不符只mark_not_eligible然后continue；合成a.jpg追加字节后，b.jpg仍hash/decode，最终PREPARATION_COMPLETE_READY_FOR_REVIEW。

证据：`raw/continuation-verification.json#/synthetic/size_change`。异常源路径不满足本批failclosed义务；原run未显示实际源大小变化。 由实现者统一大小/内容漂移的整体终止语义并补定向负例；不得复活已终态child。

### MAJ-02 — 全局wall期限不控制视频操作且超时可标完成（Major）

位置 `tools/s3_sample_preparation.py:1274`。全局1200秒预算在媒体处理与终态判定中生效。 deadline只在候选入口/hash中检查；probe及4次frame无剩余预算；假probe把clock推进到1201后仍调用4次frame且终态完成。

证据：`raw/continuation-verification.json#/synthetic/deadline`。不止前草稿声称的最多45秒尾差；一次视频可经历20+4*45秒子进程上限，另有渲染/清理时间，不能据此给全局硬上界；本次原run记录13.293秒未超限。 传播剩余deadline、每个有成本操作前检查并将超预算计入终态；由实现者补负例。

### MAJ-03 — output预算临时bytes超限仍可返回完成（Major）

位置 `tools/s3_sample_preparation.py:1638`。OutputAccountant宣称临时及保留bytes共同受output上限约束，超预算不能标准备完成。 循环仅事后检查accountant.total；最终decision仅看retained_bytes；合成100000上限、402532 staging、21578 retained返回PREPARATION_COMPLETE_READY_FOR_REVIEW。

证据：`raw/output-budget-counterexample.json`。临时bytes从最终失败判定消失；本次原run 3963572 retained+1493073 staging均低于83886080，未观察真实超限。 由实现者把实际累计output超限状态写入失败终态并限制操作期间增长；不删除旧证据/原预览。

这三项是候选工具的控制流缺陷，不是原run已越界的断言；没有重写原preflight/receipt。原草稿Fatal0/Major0及“最多45秒超时”结论已被本接续发现取代，不能引用为当前通过依据。

## 非阻断限制

- **L01 started_at使用monotonic作epoch**：1970时间戳不能作真实开始墙钟；wall_seconds_used为单调差值收据值，不是逐命令时钟独立复算。
- **L02 审计测量边界**：首次拒绝的4个0、network/model/owned/source修改标记部分是常量；以代码路径及原日志支持，不是完整OS审计，不能排除一切外联或源并发改变。32hash/20decode由逐候选收据与代码支持，60子进程有命令/exit日志；decoder IO明确NOT_MEASURED_NOT_CLAIMED。
- **L03 原45测试审计钩子范围有限**：仅patch builtins.open/os.scandir，不是完整syscall审计；没有覆盖大小漂移和视频处理中deadline，也未发现临时output完成误判。
- **L04 工具绑定时间点及范围**：当前Python/FFmpeg/ffprobe文件和Pillow Image.py hash与preflight一致；command_run未再次重算已装工具hash，Pillow不是全安装树绑定；只支持记录的工具文件，非整个OS不变。
- **L05 不覆盖终态为顺序单owner保证**：CLI先检查receipt/runtime存在；不是全局child消费锁/原子exclusive receipt创建，不能证明任意改路径或并发调用都被阻止；本任务保持已消费child，不尝试绕过。
- **L06 异常preflight终止无源访问但错误结构不统一**：合成malformed JSON在command_run抛JSONDecodeError；prepare/resolve_source边界均0，未建runtime；不能声称返回了统一拒绝JSON。
- **L07 盲态接续边界**：本次读过原独立草稿后观察，非第二次从零盲标；原代理声称80文件已看为历史记录，本次实际打开32文件观察全部32候选，视频48格来自12张contact sheet。未读项目raw/人工稿/expected。

## 32项真实视觉预标及建议集

本次实际用本地view_image打开 **20张缩略图+12张视频contact sheet=32文件**，覆盖C01–C32；视频共观察48格，未单独打开48个frame文件，不声称看过完整视频。原代理80个viewed仅以prior_agent_reported_viewed保留。每项实际打开的file/hash以prelabels.json中`preview_refs.viewed=true`标记；其余仅登记引用。事实锚点为单图内容或f01–f04，全部标签重新按本次可见内容保守撰写。

修正包括：C01半透明区域不能认定为后期光带；C05有至少两个人物局部；C10绿色区域不能称绿幕；C14双手抬起而非叉腰；C23反光移出visible_text且不声称说话；C30未见可靠手机；C31不从4帧断言4机位/3切换；C32小水印不猜。未推断年龄、身份、人物关系或制作来源。视频actual_pts/切点/精确镜头数/连续运动/运镜/遮挡/声音均UNKNOWN，容器参数单独标记为收据事实。

唯一建议集（不是冻结）：

- 图片10：**C01 C03 C04 C07 C10 C12 C13 C14 C15 C18**。
- 视频6：**C23 C31 C22 C24 C30 C32**。

依据构图、场景、光照、人物局部/反射/群像、文字、姿态与可观察状态差异；未用项目模型结果/得分。修正旧选集C10/C14的源ID/hash错配。C27改为C30以减少与C31同车道环境潜在重叠并增加室内沙发姿态场景；未要求清除水印或新增内容审批。C05低信息不等于质量不合格，也不能据可得分排除，最终预标保留其未知义务。

视频视觉近似簇C23/C25/C28及C26/C27/C29/C31均如实记录；不证明同演员、制作来源或“只有4制作簇”。C18/C20、C07/C11/C19、C09/C16/C24有构图近似。C24确为竖幅。残余相似与全语料代表性不足保留。

**六片无法仅凭四帧证明原A12完整动作/运镜/快切/遮挡义务覆盖**；真实时序真值与完整类别槽位仍有缺口，不能悄换其它源或缩分母。10+6、>=8/10、>=5/6、关键幻觉0不变。root负责最终选集/规格冻结及发现裁决，预标是独立Agent观察、不是人签或LVW评分，候选资格不等于语义质量通过。

## 执行大纲与交接

以下来自唯一execution-control，未增加完成子项：

|阶段|已完成/总数|当前边界|
|---|---|---|
|V0-S0 基线探索|1/2|历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS|
|V0-S1 图片与独立人工|5/5|已签仅V0-Min|
|R0 独立服务复核|1/2|仅R1a前置单图子集可确认；不把完整视频/Q01算通过|
|R1a 单图React/FastAPI|5/5|已签仅单图切片；完整V1未完成|
|V0-S2 视频与资源控制|7/8|Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain.|
|V0-S3 离线质量与增量包|0/6|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R1 人工业务骨架|0/4|最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。|
|V1-M1 多镜头拆分与逐镜头人物场景动作|0/3|用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署|
|R2 任务与正式运行包|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R3 镜头资产与检索|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R4 MCP与恢复|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5a 证据与建议合同|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5b 受控生成交接|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5c 集成与完整交付|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|

十字段：当前坐标R1/WP-R1-U3/S3_PREP_C_BOUNDED_QUALITY_CANDIDATE_PREVIEWS；本批完成独审/32预标/10+6建议；最后通过门禁为统一切片UM10及其范围人签（计划记录，未在此复验）；当前阻塞门禁S3_PRODUCT_GATE0_INDEPENDENT_QUALITY_LABELS_AND_RUNTIME_BINDING；全局路线S3 toward V1准备；剩余工作为三项工具缺陷裁决/修复与质量规格冻结；下一责任人root及其指定实现者；本批无需新增授权、旧child禁止重用；证据目录即本independent-01；停止原因是授权审查任务已完成并交回裁决，非人签等待、非Stage通过。
