# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE1_IMPLEMENTATION / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_17_INDEPENDENT_NO_GO_REVIEW_COMPLETE
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-17 独立复审由 root 采纳为 Fatal 0 / Major 3 / Minor 2、NO-GO。项目负责人随后关闭非 owned ComfyUI；只读复检确认旧 PID 48820/43252 与 8191/11434 listener 均消失，Windows-native 与 WSL GPU 均为 1530 MiB used / 22609 MiB free，证据见 `reports/v0-s0/gpu-owner-clearance.md`。当前只允许 WP-S0-18/19 离线修复 harness 的 Windows-native GPU preflight、超时 cleanup 相关性和首因保留；不得启动服务、重用旧授权或进入 V0-S1。
