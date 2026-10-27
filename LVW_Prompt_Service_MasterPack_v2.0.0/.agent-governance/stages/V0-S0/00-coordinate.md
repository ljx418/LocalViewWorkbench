# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE4_REAL_ACCEPTANCE / RUNNING
Product cases: NOT_RUN
Last passed gate: TARGET_RUNTIME_AUTHORIZED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

首轮授权和失败继续保存在 `reports/v0-s0/authorization.json` 与失败账本中。bridge 候选封存在 `078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68`。WP-S0-08 的非 loopback 停止证据已封存；WP-S0-10 随后证明 no-cloud true 和 10.02 秒/9 样本/0 非 loopback，但 Windows Python 收到 WSL `main.py` 路径而在媒体前 BLOCKED，证据/收据为 `78e7285ef8a2371c07207d99a7c46944aeaee873` / `aa06455f04373cf1a168cbf2b403f400d96270b6`。当前只允许 WP-S0-12 做确定性 Windows 路径转换后重跑；不得进入 V0-S1 或自行审查。
