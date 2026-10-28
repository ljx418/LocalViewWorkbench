# V0-S0 correction-13 Offline Cleanup-Proof Authority Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-37+38 / GATE1_IMPLEMENTATION / RUNNING。先读 correction-12 候选与 WP-S0-36 的 M-01。

本 Workpack 仅离线，禁止启动/探测 ComfyUI/Ollama、读取真实媒体或复用已过期授权。只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-13 offline receipt；不得修改产品 candidate/合同/门限或任何历史 evidence。

定义唯一公式：`cleanup.proven = owned_resources_absent && target_integrity_comparison == PASS && secondary_cleanup_failures empty`。完整 run fixture 必须证明 captured PID stop-after 非空时 proof/check 均失败，干净终态才 PASS；保留 Popen 与 NOT_REACHED 全部回归。

运行定向负例、完整 harness 回归、AST/help/self-check 与治理校验，输出 `READY_FOR_REVIEW` 离线收据并停止；不得 Stage PASS，产品四项保持 NOT_RUN。随后交由隔离 reviewer 执行 WP-S0-39。
```
