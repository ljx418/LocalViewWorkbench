# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE3_CHECKPOINT / CHECKPOINT
Product cases: NOT_RUN
Last passed gate: TARGET_RUNTIME_AUTHORIZED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

首轮授权和失败继续保存在 `reports/v0-s0/authorization.json` 与失败账本中。项目负责人在 `reports/v0-s0/authorization-rerun-02.json` 明确批准新的隔离实现会话，并授权 Codex 暂代 Claude Code/DSH 角色直到 V0 出门。WP-S0-04 的原始证据已封存在 Git 提交 `1d4d7303fb670f772825fc3aa488ecf1b1846a96`，正式实现收据封存在 `511020e0b26e2fe3706094297fb7b433f5bd54ff`。当前只允许隔离审查会话执行 WP-S0-05 离线复算；在其完成前不得裁决 `STAGE_BASELINE_COMPLETE`，更不得进入 V0-S1。
