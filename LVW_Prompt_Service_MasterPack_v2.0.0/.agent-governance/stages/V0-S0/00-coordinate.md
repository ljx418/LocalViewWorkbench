# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE3_CHECKPOINT / BLOCKED
Product cases: NOT_RUN
Last passed gate: WP_S0_15_OFFLINE_CANDIDATE_SEALED
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-17 独立复审已完成并由 root 采纳为 Fatal 0 / Major 3 / Minor 2、NO-GO。后续 Windows-native 只读探测定位到非本轮 owned 的 ComfyUI PID 48820（父 PID 43252，`Start_ComfyUI_Stable.bat`），其启动早于 correction-06 且解释了模型前约 23 GiB 未归属占用。root 未终止或修改该进程。当前 Stage 因 `NON_OWNED_COMFY_GPU_OWNER_ACTIVE` 进入 BLOCKED；项目负责人关闭该 ComfyUI 后，必须先用 Windows-native GPU owner 枚举证明环境干净，再冻结任何新运行。不得重用旧授权或进入 V0-S1。
