# V0-S0 correction-11 Offline Observable-State Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-31+32 / GATE1_IMPLEMENTATION / RUNNING。先读 correction-10 live receipt 与独立复审的 Minor 1。

本 Workpack 仅离线，禁止启动/探测 ComfyUI/Ollama、读取真实媒体或复用已过期授权。只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-11 offline receipt；不得修改产品 candidate/合同/门限或任何历史 evidence。

身份或 Windows-native service preflight 在零 owned service start 时停止，所有后续派生检查写 `NOT_REACHED`。cleanup 仍保持 `proven=false`，但显式区分 `owned_resources_absent=true` 和 `target_integrity_comparison=NOT_REACHED`。只要 owned service 已启动或检查实际执行，真实失败仍写 `FAIL`，不得被降格为未到达。

运行定向负例、完整 harness 回归、AST/help/self-check 与治理校验，输出 `READY_FOR_REVIEW` 离线收据并停止；不得 Stage PASS，产品四项保持 NOT_RUN。随后交由隔离 reviewer 执行 WP-S0-33。
```
