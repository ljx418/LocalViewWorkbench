# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE3_CHECKPOINT / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_15_OFFLINE_CANDIDATE_SEALED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

首轮授权和全部失败继续保存在 `reports/v0-s0/` 失败账本中。候选 `138b4486fdaeb8d207ef6b5efb63a09865f174b9` 的 WP-S0-16 单次真实运行已终止：no-cloud/远程连接/资源/最终清理门禁通过，但图片 chat 在 120 秒 `MODEL_TIMEOUT`，视频未运行；严格 trace 又因 cleanup 200 先于 chat 499 记账而判为顺序/清理失败。原始证据和封存收据为 `d337866d5f6bbb49f04d75ec0b4b1b79ba5d587e` / `25ac028`。当前只允许 WP-S0-17 独立复算真实超时、cleanup 语义、候选绑定及全部历史失败；不得重跑或进入 V0-S1。
