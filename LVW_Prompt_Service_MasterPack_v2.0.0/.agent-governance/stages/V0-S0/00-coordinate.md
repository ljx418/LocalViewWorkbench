# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE5_INDEPENDENT_EXIT / NO_GO
Product cases: NOT_RUN
Last passed gate: WP_S0_25_INDEPENDENT_REVIEW_COMPLETE
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-24 终态证据已封存为 `8fa8140`，授权已过期且禁止重跑。实现收据报告图片 1/1 PASS、视频 1/1 FAIL，四帧调用完成但语义 Oracle 因缺少 `camera_motion` 拒绝，decision=`NO_GO`；no-cloud、资源、逐调用卸载和最终清理报告通过。当前进入 WP-S0-25 隔离复审，产品四项仍 NOT_RUN，root 尚未作 S0 最终裁决。

WP-S0-25 结论 Fatal 1 / Major 2 / Minor 0，root 正式裁决 `NO_GO`：证据过采集触发 R-03；视频 Oracle 对 `camera_motion` 的 list 要求与 string 合同冲突；运行时 harness 身份未闭合。当前树已在 `664cbc7` 移除过采集进程表并标记为事后脱敏视图；原始提交仅本地隔离，禁止发布或推送。任何后续工作仅限离线预防性纠偏，旧授权不得复用。
