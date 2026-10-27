# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE4_REAL_ACCEPTANCE / WAIT_AUTH
Product cases: NOT_RUN
Last passed gate: WP_S0_23_CORRECTION_08_OFFLINE_HARNESS_SEALED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-22/23 已封存候选 `57f7718`：PowerShell 使用显式 UTF-8 bytes/strict decode，进程或端口枚举失败先落 fail-closed preflight；终态清理期二次异常不再覆盖首因且仍生成 BLOCKED receipt。离线测试 24/24、pack 1029/0、治理 42/0。服务/网络/媒体动作仍为 0，产品四项仍 NOT_RUN。当前等待项目负责人为 WP-S0-24 签发新的候选绑定有限运行授权；在此之前不得启动 ComfyUI/Ollama。
