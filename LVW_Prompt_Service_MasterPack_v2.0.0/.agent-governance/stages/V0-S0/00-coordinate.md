# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE4_REAL_ACCEPTANCE / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_12_IMAGE_PUBLIC_PATH_PASS_VIDEO_ORACLE_STOP
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

首轮授权和全部失败继续保存在 `reports/v0-s0/` 失败账本中。bridge 候选 `078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68` 在 correction-05 已由真实 Comfy `/prompt` 驱动：图片路径通过，Windows-native no-cloud、0 非 loopback、峰值 22137 MiB 和最终清理均通过；视频第 1 帧返回非空观察但把 `user_instruction` 原样写入 `prompt`，Oracle 以 `NO_USABLE_OUTPUT/PROMPT_ECHO` 正确阻断。原始证据/封存收据为 `03ce1c48a330effcc79efc9c2b336e4cc62893b4` / `1f8982b`。当前只允许 WP-S0-14/15 在仓库内强化模型交接指令并执行离线负例；不得复用旧 live 授权、进入 V0-S1 或自行审查。
