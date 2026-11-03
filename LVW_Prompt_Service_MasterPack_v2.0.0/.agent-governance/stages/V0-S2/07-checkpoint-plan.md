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
