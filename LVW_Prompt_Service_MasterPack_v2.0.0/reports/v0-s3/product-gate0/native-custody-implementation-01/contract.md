# N1：父侧Windows原始托管基础，离线实现包01

基线HEAD13e77492361648dc90a414f7fd37f0bb8b8c3634（产品源b95de076）。先读本目录architecture-decision.md与readiness01/received源码映射。唯一ClaudeCode实现owner，禁止派生Agent。

## 文件所有权
仅新增tools/v0_s3_native_custody.py（父内部adapter/闭合计划验证）、tools/v0_s3_native_broker.py（Windows stdlib broker原语/固定入口）、tools/test_v0_s3_native_custody.py及NEW reports/v0-s3/product-gate0/implementation-native-custody-01。现有controller/worker/supervisor/coordinator/QualityPhase/driver/runtime/budget/authority/fixture/executor/public合同/control/MANIFEST和旧证据全部不改。只做可随后接入的薄基础，当前所有native拒绝点保留；没有动态装载、自定义module/callback/Shell接口，不建设服务平台。

## 生产形态与权力来源
父controller将来直接启动Windows broker，持有原Popen及私有控制通道；broker与quality_worker是兄弟，由父分别掌握，worker不创建/授予broker权力。本包提供封闭计划解析/生命周期接口与Windows ctypes原语代码，但不修改现有launcher以启用运行。真正Windows执行尚未证，只能标NOT_PROVEN；本包测试用typed injected Win32 façade，假实现只能进程内调用，绝不能通过CLI序列化或以平台字符串/JSON伪装真实能力。

父内部接口建议validate_launch_plan / NativeCustodySession.start, stop, evidence；尽量少类。计划精确闭合键：schema(lvw.s3-native-custody-plan/1)、run_id、candidate_sha、authorization_sha256、lease_expires_at、max_runtime_seconds、roles。字符串长度/精确int-not-bool、有限数、sha、期限和预算正数验证；max_runtime_seconds<=21600且<=父有限child剩余，期限只收紧；无剩余预算拒绝。roles仅COMFY/OLLAMA，可选SAMPLER；每role闭合工具绝对exe路径+sha256、固定参数所需数据、相对runroot日志引用。不能接受任意完整argv/shell/script/eval/env；角色固定命令形态从既有授权工具装配，不编造未知参数。遇实际命令/工具合同缺项askroot，不替用户猜新配置。定义计划/通道schema在新模块内部，不改变旧strict Job/WorkerContext/协议/1。计划自己hash不证明grant真实有效，记录grant_authority=NOT_VERIFIED直到未来父authority接线，本包无PROVEN admission产出。

Windows broker用已装Windows Python标准库ctypes（无pip/pywin32/下载/外部包）。Windows API声明必须64bit指针安全、CreateProcessW参数引用正确、last-error保存；Windows加载仅在显式native入口延迟执行，Linux import不尝试WinDLL。不支持平台在任何创建前稳定拒绝，禁止降级为无约束Popen。

每轮创建独立Windows Job Object：KILL_ON_JOB_CLOSE且不允许breakaway；服务创建必须CREATE_SUSPENDED，父broker取得原process/thread HANDLE→AssignProcessToJobObject成功→ResumeThread，绝不能先运行再纳管。失败（包括Job受限嵌套/assign拒绝）只终止本轮刚创建且仍悬停的原句柄，确认退出并关闭thread/process/job自有句柄；不终止外部PID，不允许无Job重试。COMFY/OLLAMA/SAMPLER只能由该broker创建，子代继承Job约束；服务进程不继承控制通道/job句柄/非必要handle，broker独占Job及stop权。记录原句柄关联birth/exe/hash和role，仅作证据，不通过JSON/PID重建权限。Windows同机Job查询边界有界（沿用当前后代cap17，不允许无限缓冲），未知/超限不当零。

私有通道闭合命令仅STATUS/STOP，绑定run/candidate/auth+唯一session nonce+严格递增sequence；不接worker提供路径、PID、Shell或外部命令。每frame<=32KiB，总数<=1024，stdout/stderr各<=256KiB，新增文本<=8MiB；超限/EOF/心跳或绝对lease到期触发本轮Job有界停止并保留UNKNOWN证据，不能延长期限。不能仅靠心跳防父崩溃，读通道不得阻塞broker期限检查；实现可使用单个有界队列+读取线程/轮询，并说明Windows stdin EOF须后续实测，不能承诺父崩溃保障已证。控制通道只由父持有，nonce匹配本身不是跨会话创建权证明。重复STOP幂等，不重复创建/模型/退款。

状态：NEW→VALIDATED→ARMED(job已创建)→RUNNING→STOPPING→RELEASED或UNKNOWN_RETAINED。原生停只用owned job/original handles，不按名字枚举全机、不接管已有服务。停止/等待都有界；超时/部分创建/关闭失败保留逐句柄结果和UNKNOWN，不把资源泄漏当成功；BaseException仍执行自有资源清理并传播。资源清理不依赖日志/诊断先成功（继承M08教训）。真实Job active=0、原进程退出、句柄closed分别记录；GPU/端口/HTTP/采样器证明仍NOT_PROVEN交后续owner，本包不能签native_cleanup或GPU_RELEASED。不能用终止WSL wrapper等价Windows服务已释放。

## 最小验收设计
通过fake Win32 façade记录生产owner实际调用与持有关系：成功必须CreateSuspended→AssignJob→Resume顺序；bool/int/finite/未知role/任意argv拒绝且0create；Create/Assign/Resume每个失败点只处理已持有本轮句柄；外来同PID/记录不能stop；部分角色启动失败、job查询未知/超限、close失败、诊断失败、取消、重复STOP、EOF/期限到期、控制nonce/seq/extra键/边界exact+one-over、所有句柄清理。对纯状态/IO原语驱动真实新owner，不按常量存在或自述签PASS。预期native NOT_PROVEN与旧默认拒绝状态保持。无需复跑旧M08/35/20/15整套、无需启Windows真实进程或模型来为本包填绿。

先静态代码/AST，不导入候选/pytest；准备精确选中测试节点/argv/cwd/source-tool-dependency pins/前置guard/<=300秒/raw logs/FD线程清理后askroot ACK一次整批。guard在任何候选/pytest前硬拒OS subprocess/socket/fork/exec/spawn/system/sqlite及原counter/ledger读；只有本进程facade和合成文件。无实际Job/Windows API执行/服务/模型/GPU/用户媒体/网络/下载，全部真正native验证后续单独有限子授权。当前原counter若需观察仅guard外前后只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98 inactive28/240/12.362；不写清零退款/复活。保存全部失败，不自动补跑或追加compat。

若发现Win32最小接口/已有固定命令不足，先askroot具体方案，不得自行授予新范围或静默造成功。FIRST429立即WAIT_BUDGET停、不重试/切路由/由Codex接手；FIRST审批拒绝/超时停askroot，不包装绕过。交付候选+真实实现收据READY_FOR_REVIEW，不签StagePASS。此包是离线代码授权，不激活native启动许可。
