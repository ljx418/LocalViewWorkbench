# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE3_CHECKPOINT / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_19_HARNESS_CANDIDATE_SEALED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-20 在任何 service start 前因 Win32_Process/CIM 输出无法按 UTF-8 解码而 BLOCKED；Windows/WSL GPU 数值门禁为 1584 MiB 且一致，但 owner/port 分类未完成，所以 Ollama/Comfy/model/image/video 均 0。封存 harness 随后因缺少 `preflight-baseline.json` 在自动收据阶段发生二次异常。原始证据/收据为 `f196c4be0c6252cbb5a5df1c15486121f3c0486f` / `f4f9c01`。当前只允许 WP-S0-21 离线独立复算，不得重跑、修补证据或进入 V0-S1。
