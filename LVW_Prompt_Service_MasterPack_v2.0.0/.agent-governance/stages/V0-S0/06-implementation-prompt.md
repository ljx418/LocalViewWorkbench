# V0-S0 correction-14 Offline Cleanup Exit Binding Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-40+41 / GATE1_IMPLEMENTATION / RUNNING。先读 correction-13 候选与 WP-S0-39 的 M-01。

本 Workpack 仅离线，禁止启动/探测 ComfyUI/Ollama、读取真实媒体或复用已过期授权。只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-14 offline receipt；不得修改产品 candidate/合同/门限或任何历史 evidence。

最终 decision 必须消费 `self.cleanup["proven"]`：false 且无更早首因时强制 NO_GO/rc2/非 complete production status；已有首因时不得覆盖；true 且功能路径全绿才允许 READY/rc0。保留单一 proof 公式和全部前序回归。

运行定向负例、完整 harness 回归、AST/help/self-check 与治理校验，输出 `READY_FOR_REVIEW` 离线收据并停止；不得 Stage PASS，产品四项保持 NOT_RUN。随后交由隔离 reviewer 执行 WP-S0-42。
```
