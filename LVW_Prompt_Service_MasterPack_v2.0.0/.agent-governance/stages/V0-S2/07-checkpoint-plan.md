# V0-S2 Checkpoint Plan

## Gate 0

R1a 人工体验签署存在；合同、FFmpeg、Comfy、Ollama、样本和 owner 唯一；Stage 分母 4、V0.1 累计分母 9 均冻结。

## Gate 1–2

每次编辑只跑媒体 owner、采样、文件安全、取消/晚到和工作流定向测试。每个 Workpack 收据记录文件、合同变化、命令/退出码、生产路径和风险。

## Gate 3 离线 checkpoint

统一执行 V0-S2 子树、合同负例、工作流 JSON、V0-Min 回归、Harness 语法、manifest/治理和反假绿扫描。失败一次性汇总纠偏；不得生成产品 PASS。

## Gate 4 真实 checkpoint

子授权绑定候选、Harness、四类固定视频及恶意集 hash、FFmpeg/元数据适配器/Comfy/Ollama 身份、端口/进程、10+10 分母、一次 checkpoint 与清理。先单个代表视频闭环，再运行固定完整分母；代表样本不能替代分母。

在完整 Stage checkpoint 前，允许母授权内单独封存的原生解码组件校准：只执行公开 LVWControlledVideoInput、一次视频/四帧，不启动 Ollama、不调用模型、不启动浏览器；必须绑定当前离线检查覆盖的执行字节、安装库字节、样本、进程预算和清理。最多一次初次校准及一次有新证据的纠正尝试，不得拼接为正式 Stage 正例，也不消耗或放宽完整分母。每次仍须新鲜子授权及终态收据。

## Gate 5 独立出门

公开工作台体验还须验证：服务端当前 run 快照显式采纳；非空人工稿二次确认；等待采纳时编辑/取消/新 run 不覆盖；保留已采纳来源后重新分析；GPU 忙或模型离线时 CPU preview、复制、TXT/JSON 导出；剪贴板失败、页面移除和下载 URL 清理。必须走 `POST /lvw/v0/video/workbench` 与真实原生面板，不用 VM 替代浏览器；用户导出不能当作可信执行收据。

隔离 reviewer 复算帧时间/hash、provider 次数、P95、峰值、取消时钟、端口/进程/临时目录和九项累计状态。Fatal=0、Major=0 且所有固定项 PASS 才可裁决 `V0.1_ACCEPTED`；这不等于 V0.2/旧 V0 出门。

## 原生执行与释放证据补充（1.0.6）

内部决策见 reports/v0-s2/native-runtime-release-decision-01.md。同一安装版 Python 提供单调时钟；显存冷基线须先于预加载绑定。卸载确认和空模型清单后，还须在共享 30 秒内连续三次、间隔至少一秒，测得显存不高于冷基线+1024 MiB。仅逻辑卸载不得标记资源释放。保存原始采样与释放起点，测量汇总独立复算；缺证据保持隔离。原生适配器及合成单测不替代完整 Stage runner 和真实运行。

## 原生取消证据补充（1.0.13）

见 reports/v0-s2/native-cancel-evidence-decision-01.md。默认路径日志模式与 warm 模式隔离，候选/子授权/根进程出生时间/有效期/次数绑定。准备期取消须证明未进入 GPU/Provider；推理期取消须关联实际请求、公开取消确认、连接关闭、卸载、空模型清单与独立显存采样。不能用 socket 关闭替代物理释放，不能伪称精确 GPU 内核停止时刻。日志终态持久化完成前结果不可采纳；写入失败隔离并拒绝采纳。当前只完成合成测试，完整父运行、真实取消及浏览器保稿仍待验证。

## 公开取消执行补充（1.0.14）

见 reports/v0-s2/public-cancellation-phase-decision-01.md。准备期、模型驻留推理期各一次公开提交/取消；固定同一 Comfy TCP 对端，提交前证明进程身份，断线禁止重连。错过窗口不重试、不替换样本。原始请求图、history、状态、ack、Ollama 日志、原生终态和独立采样共同复算。父运行仍须负责故障、浏览器保稿、累计回归及最终清理；两项子检查不等于 Stage 分母通过。

## 故障与原生子进程清理补充（1.0.15）

见 reports/v0-s2/owned-provider-fault-decision-01.md。默认运行最后一次受控停止本轮 Ollama，必须由实际活动请求、模型驻留、精确原生进程出生身份及终态共同证明。只清理已封存的自有子进程，PID 复用保留新进程，快照之外的子进程拒绝猜测归属。故障时产品保持 failed/unknown 与推理隔离，父运行独立证明显存释放；人工预览、隔离重入拒绝和失败采纳拒绝仍走公开入口。显式 Comfy-only 私有进程采样交接必须保留原始覆盖证据，不把死去的 Ollama 私有内存记为零，不替代热基准。真实浏览器、累计分母与最终独立审查仍待执行。

## 短片与导出精度补充（1.0.16）

参见 reports/v0-s2/short-video-and-lossless-export-decision-01.md。离线门禁覆盖真实 owner 的 1–4 帧分支、零/超限/重复/倒退/空窗口负例与清理；生产 JS 覆盖超安全整数 PTS 的原始 source 导出、缺失来源拒绝和编辑/重分析时快照保留。合成 FFmpeg 结果/DOM 不能替代原生兼容性或真实浏览器。四帧固定样本和热基准仍须四帧；不得用少帧通过它们，也不得增加未授权媒体准备尝试。

## 原生浏览器 worker 补充（1.0.17）

见 reports/v0-s2/native-browser-worker-decision-01.md。真实原生页面上传、两次明确的 UI 队列、采纳/导出/剪贴板/取消/离线保稿/节点移除须保留九项子检查；不使用 set_content 或模型 Mock。一个延迟采纳场景仅转发真实后端原始字节，必须保留前后相同 hash。worker 必须受候选/子授权/nonce 绑定的实时父进程监督，父进程独立复算 history/provider/source/cancel/sampler；协议单测不是浏览器验收。S2 启动新增显式临时 user-directory，安装版 CLI/前端/SDK 能力与完整父运行仍待核验，未授权真实浏览器提前试跑。

浏览器父授权顺序纠正（1.0.18）：preflight 回复新增精确 owned_run_root，批准且根一致后才创建 worker 证据目录/读取目标；拒绝或错根保留九项 NOT_RUN，由父执行器生成拒绝终态。历史 directed01 保留，依据见 reports/v0-s2/native-browser-root-authorization-correction-01.md。

## 父监督端与独立进程证明补充（1.0.22）

见 reports/v0-s2/browser-supervisor-decision-01.md。父端在授权核验之前不读通信管道、不写日志；十二类权限由实际证据回调决定，记录原始 JSONL、stderr、退出码和计次。等待回调时持续采样，拒绝重放、重复提交、越额和缺失证据的 exit 0。独立核验实际 Linux 子进程出生身份、ELF 字节和新 profile 的 inode/启动参数；清理只读证明不授予任意终止/删除权限。合成回调及 Python 进程夹具仅证明监督机制，不替代真实 Comfy、四帧来源、导出内容、取消/故障、累计分母和完整父运行。

## 公开/原生日志及实际导出关联补充（1.0.23）

见 reports/v0-s2/browser-analysis-evidence-decision-01.md。父端复算公开 owner/图、四帧固定 PTS、原生来源、四次真实 Provider/raw/释放和持久成功，再允许采纳；实际下载须对齐实际采纳响应，保留大整数 PTS、旧来源和人工编辑。原始采纳响应及剪贴板字节纳入浏览器证据。窗口断线时停止挂起回调。原生组件02已实测解码及清理，但不替代公开视频推理、浏览器、固定完整分母和独立验收。两个原生组件尝试均已消耗，不再追加组件重试。

## 运行回调接线补充（1.0.24）

见 reports/v0-s2/browser-handler-wiring-decision-01.md。十二类父回调接入 Runtime 公开入口、原生日志、Provider 前缀和独立采样；浏览器与适配器共享总提交预算，失败仍计次。取消终态采集 RPC60秒/监督55秒，为既有30秒释放留证据窗口，取消反馈1秒门限不变。离线阶段只按取消→采样交接→故障顺序执行，前段失败后段NOT_RUN；停止须核验真实自有根身份和端口，不能只信布尔回执。完整绑定/进程启动、九项终态复算及 Stage 父运行仍未完成，不以合成回调测试代替真实验收。

## 浏览器阶段与九项终态复算补充（1.0.25）

见 reports/v0-s2/browser-terminal-phase-decision-01.md。实际下载/采纳/剪贴板/迟到字节/新运行取消/离线保稿/DOM移除，与父端原生、公开history、Provider和清理证据一起复算；只看PASS标签或exit0不通过。阶段协调器在实际完整父预检授权后绑定并启动唯一Node Worker，独立核验其身份、监督和归档；不单独产生授权或Stage PASS。浏览器断线信号须传入离线阶段内部授权与资源检查，回调排空前不能删除父运行目录。完整实际依赖绑定、累计回归及默认/热父编排仍待完成。

## 累计回归与固定阶段顺序补充（1.0.26）

见 reports/v0-s2/cumulative-stage-sequence-decision-01.md。当前候选重新驱动 V0-Min 五项公开入口，不继承历史 PASS；在线图片/视图先行，故障停止自有 Ollama 后再运行离线人工/状态回调。累计24次公开提交、一次图片 Provider 调用。完整顺序固定为累计在线→公开15项→浏览器九项（取消/故障）→累计离线→默认清理归档→全新同模型热基准20项→清理归档。默认提交45次、热基准20次。候选/子授权/run/用例集合不符、清理未证实、采样终态失败均不得继续；浏览器或回调状态不明时保留根目录，不重复盲清理。实际依赖绑定、运行时工厂、原始证据归档和完整子授权入口仍未闭合，因此编排实现和合成测试不等于可执行真实完整验收，更不等于 Stage PASS。

## 依赖封存机制、真实运行时工厂与受控归档补充（1.0.27）

见 reports/v0-s2/bound-runtime-archive-decision-01.md。完整子运行须将实际安装目录/工具绑定交给有限字节封存器；全量重验与短 RPC 关键文件检查必须区分。默认/热工厂接入实际 NativeRuntime、固定样本暂存、原生绑定写入、no-cloud/模型身份、实际进程命令行与新鲜用户目录、公开节点和资源采样。样本/身份或准备失败保留原始异常与一次清理/归档结果。归档先复制并复核原始证据、持久化清单，再删除经 inode 绑定的自有根；超限、损坏或未知链接均失败保留。Windows junction 通过实际原生属性/唯一目标证明并非递归删除，不以 WSL 的链接解释代替。实际路径解析、完整子授权/预算/终态过期与可执行 CLI 仍未闭合；原生效果仍 NOT_RUN。

## 完整父命令与母授权子收据补充（1.0.28）

见 reports/v0-s2/full-parent-executor-decision-01.md。完整入口为 `python3 -B -m tools.v0_s2_stage_checkpoint`：prepare 只读仓库并创建有限子授权；execute 必须带明确真实执行开关，先原子认领外部状态槽位，再解析/封存实际安装和固定样本，调用既有 StageSequence。仅初次和纠正候选复验两槽；重放、第三槽、旧证据或未知清理均拒绝。浏览器控制端口在首次连接前由原始 Node/socket inode/内核 loopback 监听共同绑定。终态先关闭已预分配的授权标志，公开收据失败也不能恢复新工作权限。母授权已授予本范围，packet 的 PROGRAM_CHILD_REQUIRED 仅表示可派生权限，仍须新鲜整包离线门禁和完整绑定子收据；不重复请求人工批准，不代表 Stage PASS。运行坐标只在 execution-control.json 更新，冻结规格保持不变。

## NTFS 文件身份精度纠正（1.0.29）

见 reports/v0-s2/lossless-native-identity-decision-01.md。实际仓库 NTFS inode 已超过 JavaScript 安全整数，原生浏览器 profile 采用 BigInt 读取和十进制字符串传递，父端按 uint64 无损复核。离线修正后只允许显式替换尚未认领、未执行的子授权，保留旧字节和过期记录并使用新授权身份；已认领/终态槽位绝不能重置。须新整包门禁覆盖修正代码后再绑定；真实 checkpoint/recheck 分母和预算不变。


## 1.0.30｜明确批准的单槽补充与残留根接管

项目负责人批准 AUTH-REQUEST-V1-S2-SUPPLEMENTAL-01；精确请求与独立批准记录见 reports/v0-s2/authorization-s2-supplemental-01.{request,approval}.json。原母授权每Stage一次checkpoint＋一次复验计数不改，两个旧槽均保持消耗，仅此明确批准的 full-supplemental-01 可额外完整运行一次，无补充复验或第四槽。

先完成受限授权／清理工具的离线实现及完整检查，冻结 final candidate，再生成 supplemental-cleanup-01 一次性子授权。仅接管批准的当前 device/inode，不恢复／伪造缺失的原始 lease；拒绝未知内容，校验原生 Junction 指向本根 outside-input，归档诊断，非递归删除链接，删除已核实文件树。禁止新testSource读取、模型、GPU、服务、浏览器和进程终止；原生命令最多4次、链接删除最多1次。清理成功并封存原始与脱敏终态后，才能生成 full-supplemental-01 的候选／Harness／样本／端口／进程／预算绑定子授权。两种子运行均为原子一次性认领，失败不得重启或改名重试。

命令（所有 prepare 均只读仓库证据）：

```bash
python3 -B -m tools.v0_s2_supplemental prepare-cleanup --candidate <FINAL_SHA> --offline-receipt reports/v0-s2/offline-checkpoint-22/receipt.json
python3 -B -m tools.v0_s2_supplemental cleanup
python3 -B -m tools.v0_s2_stage_checkpoint prepare --slot full-supplemental-01 --candidate <FINAL_SHA> --offline-receipt reports/v0-s2/offline-checkpoint-22/receipt.json
python3 -B -m tools.v0_s2_stage_checkpoint execute --slot full-supplemental-01 --execute-native-checkpoint
```

完整运行沿用65公开提交／83 Provider调用／20预加载／2次Comfy与Ollama启动／1次headless及其它原预算、固定四项和累计九项、全部失败和清理阈值。授权撤销或变化拒绝新工作；保留原有已归属清理权限。清理失败、出现不明内容或完整补充终态后，额外授权自动失效。机器结果不签署Stage、人类体验或V1发布。


## 1.0.31｜先资源准入，再完整运行

项目负责人批准 AUTH-REQUEST-V1-S2-RESOURCE-READY-01。原三次失败和授权终态保留，仅新增 full-resource-ready-01 一个完整槽位、无额外复验；不重置旧槽。新增 resource-admission-01 一次性子运行，先冻结候选／工具／期限／预算并通过完整离线门禁，再认领子授权后查询资源。最多三组采样，间隔1秒，执行最长60秒；最多3个PowerShell＋3个其内的原生NVIDIA查询（合计6个原生命令）及3个WSL查询。只记录GPU读数、可用RAM、目标端口／进程计数，不读取媒体，不启动模型、服务、浏览器或终止进程。

准入沿用GPU占用<=4096MiB、Windows可用RAM>=2048MiB、8191/11434无监听、无现有目标运行进程，并核对Windows／WSL原读数。任一忙碌／未知／不一致则记录稳定失败与原始输出，关闭子授权及本次批准，不认领完整槽位，不反复轮询。三组全满足才允许同最终候选的完整 child；完整 child 仍执行全部新鲜安装字节封存、正式启动前检查、固定四项／累计九项和原全部预算。准入不是产品PASS，也不替代正式资源／取消／性能验收。

执行顺序：
```bash
python3 -B -m tools.v0_s2_resource_admission prepare --candidate <FINAL_SHA> --offline-receipt reports/v0-s2/offline-checkpoint-23/receipt.json
python3 -B -m tools.v0_s2_resource_admission probe
python3 -B -m tools.v0_s2_stage_checkpoint prepare --slot full-resource-ready-01 --candidate <FINAL_SHA> --offline-receipt reports/v0-s2/offline-checkpoint-23/receipt.json
python3 -B -m tools.v0_s2_stage_checkpoint execute --slot full-resource-ready-01 --execute-native-checkpoint
```

本批准绝对期限最多6小时，child受其期限约束；终态、撤销或越界后停止新工作，已归属清理保留。此前残留根均已清理，本次不允许新根接管。仅增加授权／准入／诊断证据运输和测试；插件、公开合同、质量与资源门限、固定样本／模型／分母不改。


## 1.0.32｜已批准的验收器纠偏复验

项目负责人批准 AUTH-REQUEST-V1-S2-ORACLE-CORRECTION-01，随后通过明确Goal解除文档审阅hold，沿用现行全部门禁。仅新增 full-oracle-correction-01 一个完整槽，额外完整复验0；资源准入子运行 resource-admission-oracle-correction-01 最多一次。全部四次失败、归档和过期授权保持不变；不复活旧slot、不采纳docs/25提案。

新scope复用原有限准入的三组读数、60秒、6个原生/3个WSL命令与4096MiB/2048MiB原阈值，并要求相同最终候选的新准入终态才认领完整运行。母授权、原始批准和本次恢复记录、固定样本/模型/分母/预算、旧终态/清理与候选后代允许改动逐项校验。文档修订d26f8ff为用户单独要求并接受的固定基准，其后只许授权传输/测试/相关收据更改；不能任意改产品或文档规则。

prepare只读仓库和受控历史证据，probe才认领新准入并做已批准的有限真实探测。最终候选必须先通过完整离线门禁，再按顺序执行准入与完整运行。CLI入口为tools.v0_s2_oracle_authorization的prepare/probe，再以tools.v0_s2_stage_checkpoint的prepare/execute选择full-oracle-correction-01；准确候选与offline收据记录到唯一坐标，不手工替换运行产物。

本次scope最长6小时，完整child受其到期约束；准入失败/撤销/完整终态后自动过期，已归属清理保留。人工签署、独立审查和Stage PASS不由此授权替代。
