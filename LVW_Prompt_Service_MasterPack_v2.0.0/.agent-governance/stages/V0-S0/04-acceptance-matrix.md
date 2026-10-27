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
