# V0-S0 correction-15 Offline Primary/Secondary Binding Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-43+44 / GATE1_IMPLEMENTATION / RUNNING。先读 correction-14 候选与 WP-S0-42 的 M-01。

本 Workpack 仅离线，禁止启动/探测 ComfyUI/Ollama、读取真实媒体或复用已过期授权。只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-15 offline receipt；不得修改产品 candidate/合同/门限或任何历史 evidence。

进入 cleanup 前已确定的 NO_GO/BLOCKED decision/reason 均视为 primary；cleanup failure 只追加 secondary event。只有 pre-cleanup READY 才由 cleanup 降级。完整 fixture 必须覆盖普通 public route failure 加 cleanup failure，保留所有前序回归。

运行定向负例、完整 harness 回归、AST/help/self-check 与治理校验，输出 `READY_FOR_REVIEW` 离线收据并停止；不得 Stage PASS，产品四项保持 NOT_RUN。随后交由隔离 reviewer 执行 WP-S0-45。
```
