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

首轮授权和失败继续保存在 `reports/v0-s0/authorization.json` 与失败账本中。WP-S0-05 独立复审结论为 Fatal 0 / Major 5 / Minor 2；root 门禁在 `9e8f62a34c11c6b9068959cf5831091470cdfb65` 裁决 NO-GO。bridge 候选封存在 `078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68`。WP-S0-08 因 owned Ollama 非 loopback TCP 在模型前停止，证据/收据封存在 `9256c063128624672dfb5b258b7576406ff339ac` / `cd42fd65d79041d230a6c651159911fa9b31ee35`。当前只允许 WP-S0-10 以 Windows 原生进程内 no-cloud 环境注入重做 preflight；不得进入 V0-S1 或自行审查。
