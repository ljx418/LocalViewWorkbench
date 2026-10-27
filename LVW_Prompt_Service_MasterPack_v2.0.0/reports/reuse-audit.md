# V0-S0 复用审计

审计日期：2026-10-27  
证据性质：已授权的本地公开入口和真实模型可行性探测；不是 V0 产品验收。  
应用候选：`3fb04084c50f0ef9b6bd133fe77f90bea44e6ffa`。

## 结论

ComfyUI 0.37.0、Prompt Assistant 2.0.6 与本地 Ollama 0.32.8 可以启动，`gemma4:26b` 确有视觉能力。原生 Ollama 单图在显式关闭 thinking 后可以返回合法 JSON，并能在 `keep_alive=0` 后卸载。

Prompt Assistant 不能原样成为 V0 生产 owner：实时节点配置只提供智谱/xFlow 远程选项；Ollama 模型发现路由因 `ModelListService` 未定义而 500；视频节点默认 5 帧且先接收完整帧批次；视频辅助路由接受并回传绝对路径。四帧原生 Ollama 能完成视觉推理，但两次均未生成可解析的完整 JSON，不能宣称合同通过。

因此最小路径已收敛为：项目自有 `lvw_v0_bridge` 负责手动编辑/导出、路径边界、有界 ffmpeg 采样、Ollama loopback 调用、结构化解析/失败码、raw/suggestion/draft 隔离和清理；只复用 ComfyUI 宿主、Prompt Assistant 可借鉴的 UI/规则以及本地 Ollama，不直接暴露现有危险路由。

V0-A01、V0-A02、V0-A09、V0-A10 仍为 `NOT_RUN`。S0 只可给出 baseline 结论，不能给出任何产品用例 PASS。

## 真实复用判定

| 对象 | 判定 | 真实证据 |
|---|---|---|
| ComfyUI 运行时 | 复用 | loopback 启动成功；公开 object registry 可查；结束后 owned 进程和端口清零。 |
| Prompt Assistant `ImageCaptionNode` | 不直接复用 | 节点真实注册，但 live service 选项没有 Ollama，默认指向未授权远程 Provider。 |
| Prompt Assistant `VideoCaptionNode` | 不作为 V0 视频 owner | live registry 显示默认 5、最大 32，输入是 IMAGE batch/VIDEO；源码与运行信息均不能证明有界解码。 |
| Prompt Assistant `/models/list` | 不复用 | `llm` 与 `vision` 两次查询均返回 HTTP 500，稳定错误为 `ModelListService is not defined`。 |
| Prompt Assistant video info/frame | 禁止无包装暴露 | 真实请求接受授权根中的绝对路径并在响应回传绝对路径。 |
| ffmpeg / ffprobe | 复用 | 对 3.343 秒视频按四个分箱中心逐次解码，每次仅一帧；得到 4 个 572×768 帧及独立 hash。 |
| Ollama `/api/chat` | 在 LVW 适配层后复用 | 单图第二次请求产生合法 JSON；四帧两次均因格式/长度失败，必须由适配层控制 Schema、token 和错误终态。 |
| Ollama `keep_alive=0` | 条件复用 | 三次观察均在 5 秒复核时 `/api/ps` 为空，GPU 回到约 4.17 GiB 的 Comfy 基线。 |

## Major 风险

1. Prompt Assistant 的本地模型发现 API 在真实运行中崩溃，且节点没有可选 Ollama 模型。
2. 视频 owner 会在选帧前接收完整视频帧表示，默认 5 帧，不满足 V0 固定 4 帧和内存上界。
3. 视频接口允许任意存在的绝对路径并回传路径；必须由项目 owner 阻断。
4. 四帧输出在两个有效尝试中都不是完整合法 JSON；不能用 HTTP 200 或“看起来有内容”作为合同 PASS。
5. 峰值显存单图 22,397 MiB、四帧最高 22,738 MiB，虽低于 23 GiB 门槛，但余量有限；最终 V0-A09 必须执行各 10 次和系统 RAM 观测。
6. 本轮实际探测由门禁负责人完成，而冻结 Workpack 指定 Claude Code + MiniMax；必须由隔离审查者复算，不能自签 Stage PASS。

## S1/S2 实现边界

- S1 先完成无模型可用的人工编辑、显式采纳、复制、TXT/JSON 导出和 draft epoch。
- 单图通过 LVW adapter 直接调用本地 Ollama 或经重新验证的公共入口；禁止默认远程 Provider。
- 每次模型响应保留 raw；解析失败返回 `PARSE_PARTIAL`/`NO_USABLE_OUTPUT`，不得覆盖 draft。
- S2 使用 ffprobe 获取时长，再以 4 个分箱中心逐次调用 ffmpeg 单帧解码；不得把整片视频加载成 tensor。
- 所有媒体路径先映射为允许根和相对引用，响应及证据不返回绝对路径。
- 模型调用必须固定 `think=false`、Schema、token 上限、超时、两次有效尝试上限及 `keep_alive=0`，并把 `done_reason=length` 视为失败。

## Checkpoint 建议

S0 已获得足够的真实信息来选择最小实现路径，建议提交隔离独立审查。只有审查确认候选/证据绑定、重试账本、绝对路径漏洞、进程清理和产品 `NOT_RUN` 未被篡改后，Codex 才可裁决 `STAGE_BASELINE_COMPLETE`。
