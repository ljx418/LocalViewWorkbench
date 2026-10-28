# V0-S1 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Prepared stage: V0-S1 / 图片与独立人工路径
Packet version: 1.0.0
State: WAIT_AUTH / WAIT_GPU_RELEASE_AND_LIVE_05_APPROVAL
Active coordinate: V0-S1 / WP-S1-03 / GATE4_REAL_ACCEPTANCE
Last passed gate: WP_S1_03_GPU_EVIDENCE_CORRECTION_SEALED
Exact stop reason: WAIT_GPU_RELEASE_AND_NEW_EXPLICIT_LIVE_05_AUTHORIZATION
Product cases: NOT_RUN
Prepared-against commit: dfb00ad462d94628f1aa22045061f66a7629ec01
Product bridge candidate: 138b4486fdaeb8d207ef6b5efb63a09865f174b9
Accepted S1 baseline: dfb00ad462d94628f1aa22045061f66a7629ec01
```

本目录是已冻结的 V0-S1 Stage packet。冻结提交完成前，它不改变 `plans/execution-control.json` 的唯一当前坐标；激活后只授权 packet 允许路径内的离线仓库工作，不能继承 S0 的 live 授权。

V0-S0 已以 `dfb00ad...` 正式闭合：public `/prompt`/`history` 可达 `LVWImagePromptBridge` / `LVWVideoFramesPromptBridge`，correction-16 独立复审 Fatal/Major/Minor 均为 0。S1 可执行 WP-S1-00/01/02 的离线实现；WP-S1-03 的目标 Comfy 安装、Ollama 调用和真实图片运行仍须新的逐次授权。产品固定验收仍为 `NOT_RUN`。

WP-S1-00 已以候选 `457b2e8...` 封存：合同/绑定/固定分母、合法与非法结果、20,000 字、图片 exact/one-over 以及晚到回调夹具通过 8/8 离线测试。当前进入 WP-S1-01；这不是产品用例 PASS。

WP-S1-01 最终候选 `a9c816e...` 已封存：公共 `LVWManualPromptOwner`、纯 CPU 七输出、复制、原子 TXT/JSON 导出及路径边界通过 45/45 离线回归；外部动作均为 0。目标 Comfy 导入和系统剪贴板仍为 `NOT_RUN/WAIT_AUTH`，五项产品验收未提升。当前进入 WP-S1-02。

WP-S1-02 最终候选 `2776a0c...` 已封存：公共 `LVWControlledImageInput` 与 `LVWDraftStateOwner`、解码前像素门禁、EXIF/RGBA/缩放记录、run-token 与 draft 隔离通过 59/59 离线回归。`AUTH-V0-S1-2026-10-28-01` 已按请求指纹正式记录；WP-S1-03 必须先封存精确执行候选，再在单图片/单模型调用预算内执行一次本机 loopback live run，并于终态自动过期。

WP-S1-03 Phase A 候选 `65c909f...` 与 harness `322957e...` 已由门禁负责人封存：workflow/API、真实 PromptSpec Oracle、raw/suggestion 分离、Windows wrapper/PID lineage、清理重验证和默认拒绝路径通过 76/76 离线回归。当前只允许先执行授权前置检查；任一目标路径、身份、GPU、进程、端口或 no-cloud 条件失败都必须在图片尝试前终止。

授权前置检查确认请求中绑定的 `COMFY_ROOT/main.py` 与 `COMFY_PYTHON` 均不存在，故在服务、GPU、端口、网络、模型和真实媒体动作前以 `NO_GO` 终止；`AUTH-V0-S1-2026-10-28-01` 已自动过期。候选仍封存有效，但不得搜索或替换为未授权路径；下一步由项目负责人提供实际路径后重新请求一次性授权。

项目负责人现已提供并授权检查 `C:/ComfyUI-aki-v2`，其中真实目标为 `ComfyUI/main.py` 与 `python/python.exe`。当前仅授权离线修正 harness 路径绑定和负例测试；旧授权保持过期，ComfyUI/Ollama/GPU/端口/网络/真实媒体动作仍禁止，修正候选重新封存后再生成新请求。

修正候选 `3c50159...` 与 harness `fba396b...` 已封存，绑定 aki-v2 精确路径、新授权 ID `AUTH-V0-S1-2026-10-28-02`、新 run ID 和不可复用的 `wp-s1-03-live-02` 证据槽；77/77 离线回归通过。当前等待项目负责人明确批准 `AUTH-REQUEST-V0-S1-WP-S1-03-02`。

项目负责人已逐字批准 request-02，正式授权记录绑定请求提交 `83cea5b...` 与 SHA-256 `280ab61...`。仅可执行一次 live-02；任何 mandatory stop、有效图片尝试或终态收据都会使授权自动过期。

live-02 已且仅已执行一次，但 harness 在运行完成后的终态证据序列化阶段触发 `JSONDecodeError`。内存中的路由结论、尝试计数、服务启动计数和目标前后指纹无法恢复，均保持 `UNKNOWN`；五项产品用例继续为 `NOT_RUN`。终端后检查确认 8191/11434 无监听、无匹配进程、无 run-owned 临时目录，但不能替代丢失的运行内目标完整性证明，因此 cleanup 不提升为已完全证明。`AUTH-V0-S1-2026-10-28-02` 已自动过期，禁止重跑；下一步仅允许离线修复序列化并重新封存候选，随后另行申请新的一次性授权。

终态序列化已在候选 `4a2fed4...` 离线修复：脱敏从“已编码 JSON 整串替换”改为“字符串叶节点递归脱敏后再编码”，并绑定新授权 ID、run ID 与不可复用的 live-03 证据槽。定向 18/18、完整离线回归 78/78、候选身份检查均通过，外部动作 0。`AUTH-REQUEST-V0-S1-WP-S1-03-03` 现等待项目负责人逐次明确批准；批准前禁止启动 ComfyUI/Ollama 或执行真实媒体路径。

项目负责人已逐字批准 request-03，正式授权记录绑定请求提交 `60c49f0...` 与 SHA-256 `eecfe5d...`。仅可执行一次 live-03；任何 mandatory stop、有效图片尝试或终态收据都会使授权自动过期。

live-03 已且仅已执行一次并以 `NO_GO` 终止：候选身份、GPU、精确本地模型、no-cloud、服务归属与完整清理均通过，但真实公开 `/prompt` 路径中 `LVWImagePromptBridge` 以 `MEDIA_LIMIT_EXCEEDED / FRAME_LONG_EDGE_LIMIT` 拒绝最长边大于 384 的张量。产品合同与受控输入 owner 均规定图片长边 1024，因此这是生产 owner 之间的边界不一致，不是样本替换理由。授权已自动过期，五项产品用例仍为 `NOT_RUN`；下一步只允许离线修正该不一致并重新封存。

候选 `b248b37...` 已将 bridge 边界对齐冻结的 1024，补齐跨 owner 的 1024 exact 与 1025 one-over 负例，并将失败证据限制为 event/code/subcode/node 稳定字段。定向 58/58、完整离线回归 79/79、候选身份检查通过，外部动作 0。`AUTH-REQUEST-V0-S1-WP-S1-03-04` 等待项目负责人明确批准；批准前禁止 live-04。

项目负责人已逐字批准 request-04，正式授权绑定请求提交 `fbc1a44...` 与 SHA-256 `8bd7277...`。仅可执行一次 live-04；任何 mandatory stop、有效图片尝试或终态收据都会使授权自动过期。

live-04 已且仅已执行一次，在服务启动前以 `GPU_PREFLIGHT_USED_MEMORY_EXCEEDED` 安全停止。图片尝试、模型调用、公开提交、Ollama 和 Comfy 启动均为 0；清理、端口空闲、临时目录移除及目标完整性均通过。harness 未持久化精确 MiB，因此不作数值推断。授权已自动过期，五项产品用例保持 `NOT_RUN`；需要项目负责人释放 GPU，并在新请求封存后重新逐次授权。

候选 `919f7fc...` 已在不改变 4096 MiB 门限的前提下补齐 GPU 超限聚合证据，绑定新的 live-05 证据槽；定向 20/20、完整回归 80/80，外部动作 0。现在同时等待项目负责人确认 GPU 已释放并明确批准 `AUTH-REQUEST-V0-S1-WP-S1-03-05`。
