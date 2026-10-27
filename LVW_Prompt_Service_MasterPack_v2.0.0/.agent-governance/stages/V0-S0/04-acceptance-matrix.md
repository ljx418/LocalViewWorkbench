# V0-S0 Acceptance Matrix

Stage 固定分母为 `V0-A01,V0-A02,V0-A09,V0-A10`，指纹：

```text
sha256(sorted IDs joined by LF with trailing LF)
78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42
```

| 义务 | 生产路径 | Oracle | 负例/边界 | S0 出口含义 |
|---|---|---|---|---|
| V0-A01 图片入口探测 | 真实注册节点/API→Ollama | 非 demo raw、input hash、digest | 无效格式、超像素只记录能力 | 有可实现性结论，不是质量 PASS |
| V0-A02 四帧探测 | ffprobe/有界采样→真实多帧入口 | 顺序/时间/帧 hash、无全片 GPU tensor | 短片/VFR/重复帧能力记录 | 有界路径已识别，不是 6 片 PASS |
| V0-A09 资源基线 | 实际目标进程与 GPU/RAM 观测 | 真实采样和命令原始输出 | 冷/热、占用冲突分开 | 形成基线，不是 10 次 P95 PASS |
| V0-A10 取消/卸载能力 | 真实 owner 的取消与 `/api/ps` | 控制终态和资源终态分开 | 晚到、他人占用、不 kill | 能力/缺口有结论，不是最终 PASS |

S0 checkpoint 允许的结论只有 `STAGE_BASELINE_COMPLETE`、`NO_GO`、`BLOCKED`、`WAIT_BUDGET` 或 `WAIT_AUTH`。四个产品用例仍保持 `NOT_RUN`，直到各自完整分母在后续正式验收中执行。

## correction-03 固定 Oracle

- 公开生产 trace 必须从 Comfy `/prompt` 的 `LVW` 注册 class_type 到 bridge owner，再到同一 run 的 loopback Ollama raw、history 输出和释放终态；direct `/api/chat` 不可替代。
- 图片/视频可用性要求至少一个非空 observation；视频还要求非空 motion 或明确的逐帧变化/无变化结论。输出与规范化后的请求指令相同视为 `NO_USABLE_OUTPUT`。
- 所有视觉请求输入最长边默认不超过 384，`num_ctx<=2048`、`num_predict<=768`；视频最多四帧且逐帧视觉调用，不允许四图同请求。
- S0 资源基线逐次峰值必须 `<23552 MiB`，否则仍为 NO-GO；这不替代 V0-A09 十次/P95 分母。
- 每个启动过 owned service 的 run（含 pre-model 失败）必须有当次 stop、最终 listener/process、临时目录和 `/api/ps` 证据。零云调用只按观测事实陈述：模型请求目标固定 loopback，并记录 owned Ollama PID 在窗口内的远程 TCP 连接；不得再以未生效环境变量单独证明。
