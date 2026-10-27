# V0-S0 Risk And Authorization Register

| ID | 风险/动作 | 分类 | 默认状态 | 停止/清理 |
|---|---|---|---|---|
| AUTH-01 | 读取目标机安装目录和版本 | 外部/私有 | GRANTED | 仅 COMFY_ROOT / TEST_SOURCE；日志脱敏路径 |
| AUTH-02 | 使用真实图片/视频 | 私有数据 | GRANTED | TEST_SOURCE 或生成的非私有夹具；只记录 hash，不打包原媒体 |
| AUTH-03 | 调用本地 Ollama/Comfy | 外部运行 | GRANTED | 仅 loopback 既有服务；每探测最多两次有效重试；核对 owned request/process |
| AUTH-04 | 可见浏览器 | 高干扰 | 未申请 | S0 默认不用；若必要单独授权并静音、owned PID、finally 清理 |
| AUTH-05 | 下载/升级/写配置 | 环境变更 | 禁止 | 发现需要即停止并提变更请求 |
| R-01 | 未知 GPU 占用 | 资源 | 阻断探测 | 不 kill 他人进程；记录 RESOURCE_BUSY |
| R-02 | 节点/模型能力不匹配 | 技术 | 可产生 NO_GO/BLOCKED | 保留失败，不临时换模型降门槛 |
| R-03 | 证据泄漏路径/媒体/凭据 | 隐私 | Fatal | 停止发布，清理本轮受控副本并保留脱敏事故记录 |
| R-04 | 预算或重试耗尽 | 成本 | WAIT_BUDGET | 不降低分母；保存 checkpoint |
| R-05 | 语义空响应通过类型 schema | 假绿 | 阻断 | 非空 observation、视频变化 oracle、prompt-echo 拒绝 |
| R-06 | 视频视觉批处理超 23 GiB | 资源 | 阻断 | 最长边 384、逐帧调用、每次 raw 资源序列 |
| R-07 | no-cloud 配置自报未生效 | 网络 | 阻断无云声明 | 固定 loopback；真实运行记录 owned PID 远程连接观察 |

## 纠偏授权

`AUTH-V0-S0-2026-10-27-02` 建立新的 run 预算，并由人类明确批准两个隔离 Codex 会话临时替代 Claude Code 与 DSH。它不追溯修改首轮失败，不授权 root gate owner 充当实现者或独立审查者，也不授权任何云/付费 Provider。

授权必须写明目标机器、允许根/端点、样本、Provider/网络、可见界面、最大重试/成本、证据目的地和清理。AUTH-01/02/03 已由 `reports/v0-s0/authorization.json` 固化；该授权不包含下载、升级、写配置、云/付费 Provider、可见浏览器或远端推送。

WP-S0-06/07 是纯离线仓库操作，现已授权。WP-S0-08 不复用 `AUTH-V0-S0-2026-10-27-02` 的已消耗运行预算；开始前必须生成新的有限运行记录，明确候选 SHA、临时挂载/恢复方法、有效尝试数、连接观测和逐 run 清理。用户对本机 ComfyUI/Ollama 的总体有限启停授权仍有效，但不得由此扩展到下载、永久配置写入、云 Provider 或可见浏览器。

`AUTH-V0-S0-2026-10-27-03` 已绑定候选 `078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68` 与收据 `2df895318ae1278452a399622fb29f41eb3dce73`。它只允许 run-owned 临时 Comfy base、8191/11434 loopback、两份固定 hash 样本、每类最多两次有效尝试和远程连接观察；不允许永久安装写入。

该授权在 owned Ollama 出现非 loopback TCP 后以 0/0 有效媒体尝试终止，证据封存于 `9256c063128624672dfb5b258b7576406ff339ac`。离线诊断证明 WSL 环境变量未传入 Windows 子进程。`AUTH-V0-S0-2026-10-27-04` 只授权 Windows 原生进程内环境注入的新路线；server log 未报告 no-cloud true 或任一远程 TCP 出现时，仍须在模型调用前停止。

correction-04 已证明 no-cloud true、10.02 秒/9 样本/0 非 loopback，但因 `main.py` 未转换为 Windows 路径在 Comfy 启动前终止。`AUTH-V0-S0-2026-10-27-05` 仅授权 correction-05 修正两个 Windows 路径参数并复用相同已证明的网络门禁；不增加媒体尝试或环境变更权限。

correction-05 已完成且其运行预算耗尽：图片公共路径通过；视频第 1 帧因模型复制用户指令而由 `PROMPT_ECHO` Oracle 阻断。WP-S0-14/15 仅是离线仓库操作。任何 correction-06 真实运行必须在新候选提交后另立授权记录，旧授权不可解释为自动重试许可。

项目负责人另行授权 V0 结束前由隔离 Codex 实现实例临时代行 Claude Code/DSH；这是角色载体授权，不是外部动作授权。root gate owner、实现实例和独立审查实例仍须隔离。

WP-S0-14/15 的新候选 `138b4486fdaeb8d207ef6b5efb63a09865f174b9` 已通过双解释器离线测试。`AUTH-V0-S0-2026-10-27-06` 为该 SHA 建立一次新的单图 1 次、四帧视频 1 次真实预算，继续使用 Windows-native no-cloud 与 correction-05 相同的网络、显存、清理和目标完整性门限；任一媒体尝试消耗或终态收据产生即过期。

该授权已由 WP-S0-16 的单次图片尝试和终态收据消耗，不得复用。真实 chat 超时；卸载请求 200、chat 随后 499、最终模型/端口/PID/temp/目标完整性均清理。严格 trace 判定和最终清理证明之间的语义差异必须由 WP-S0-17 独立审查，不得由实现者自行改判。

WP-S0-17 与 root 的 Windows-native只读复核确认：非本轮 owned 的 ComfyUI PID 48820 在 correction-06 前已由 PID 43252 / `Start_ComfyUI_Stable.bat` 启动，且仍在 GPU 进程清单中。不得终止非 owned 进程；在项目负责人关闭它并重新证明 GPU owner/总占用前，Stage 状态为 BLOCKED。

项目负责人已关闭该进程；复检确认旧 PID/端口消失且 GPU used 降至 1530 MiB。BLOCKED 已解除，但这不是 live 授权。WP-S0-18/19 先离线固化 Windows-native preflight：服务前 used `<=4096 MiB`，不得存在目标 Comfy/Ollama/授权端口 owner；否则停止。WP-S0-20 必须另立单次授权，并作为同路线第二次且最后一次有效尝试。

`AUTH-V0-S0-2026-10-27-07` 已绑定产品候选 `138b448...`、harness `82975ae...` 和离线收据 `2f8ac30...`。它只允许一次图片和一次视频，且 pre-service gate 未通过时服务启动数必须为 0。任何有效媒体尝试或终态收据产生即过期；同路线再次失败后禁止继续重跑。

该授权已产生终态 BLOCKED 收据并过期，不得复用。pre-service GPU 数值通过，但 CIM 输出解码失败导致 owner/port gate 未完成；服务和媒体尝试均为 0。是否签发纯 harness 编码纠偏及后续授权，必须等待 WP-S0-21 独立复审。

WP-S0-21 已确认补建收据无假绿且有效媒体 0/0。WP-S0-22/23 仅离线修复 PowerShell UTF-8 与原子 failure-finalization。任何 WP-S0-24 运行仍需新授权；不得把旧授权恢复或延长。

WP-S0-22/23 候选已封存为 `57f771823a625eabd3fd746d352f5936d37380a2`，离线收据证明 24/24 回归通过且外部动作全为 0。旧授权仍保持过期；当前状态为 `WAIT_AUTH`。WP-S0-24 的新授权必须显式绑定该 harness 候选、产品候选 `138b448...`、图片 1 次/视频 1 次预算、loopback/no-cloud/GPU/cleanup 门限与终态即过期规则。

项目负责人已签发 `AUTH-V0-S0-2026-10-27-08`，完整满足上述绑定。仅 WP-S0-24 实现实例可执行；终态收据或任一有效媒体尝试产生后立即过期，随后必须停止并转 WP-S0-25 独立复审。

WP-S0-24 已产生终态收据并消耗图片 1 次、视频 1 次预算，授权现已过期且不得重跑。终态证据提交 `8fa8140` 报告视频语义 Oracle 缺少 `camera_motion`，decision=`NO_GO`；该结论及网络、资源、清理证明必须由 WP-S0-25 独立复算。

Correction-09 候选 `d1f268f` 已由 WP-S0-28 独立确认关闭隐私最小化、string Oracle 与 harness 自绑定三项前瞻性缺陷。旧 live 授权仍全部过期。WP-S0-29 只有在项目负责人另行明确绑定产品/harness SHA、固定样本、图片 1 次/视频 1 次、loopback/no-cloud、资源/清理门限和终态过期后才可执行。

待授权条款已固化为 `reports/v0-s0/authorization-correction-10.request.json`。该文件的 `status=PENDING_PROJECT_OWNER_APPROVAL`、`is_authorization=false`、`does_not_authorize_execution=true`，只能作为请求导航；不得加入 `authorization_records` 或触发运行。项目负责人明确同意后，root 必须另建正式授权记录并绑定其提交 SHA。
