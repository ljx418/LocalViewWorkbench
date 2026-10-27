# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE1_IMPLEMENTATION / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_21_INDEPENDENT_BLOCK_REVIEW_COMPLETE
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-21 独立复审已封存为 `b72c23e`，结论 Fatal 0 / Major 2 / Minor 0、BLOCKED：CIM 隐式 UTF-8 解码与缺失 preflight artifact 的收据二次崩溃均为 harness 缺陷；补建收据忠实、无假绿，服务/媒体 0/0，旧授权已过期但最终有效媒体预算未消耗。当前只允许 WP-S0-22/23 离线修复编码和 failure-finalization，不得启动服务、修改产品候选或进入 V0-S1。
