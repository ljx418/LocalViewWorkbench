# V0-S0 correction-12 Offline Owned-Popen Cleanup Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-34+35 / GATE1_IMPLEMENTATION / RUNNING。先读 correction-11 候选与 WP-S0-33 的 M-01。

本 Workpack 仅离线，禁止启动/探测 ComfyUI/Ollama、读取真实媒体或复用已过期授权。只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-12 offline receipt；不得修改产品 candidate/合同/门限或任何历史 evidence。

每个已赋值的 owned Popen 都必须证明退出；wait timeout/异常或 `poll() is None` 必须 fail-closed。只可清理本 run 精确创建的 Popen，不得终止未知进程。保留 correction-11 的 NOT_REACHED/FAIL 状态语义，并新增完整 run-level lingering-Popen 负例和正常退出正例。

运行定向负例、完整 harness 回归、AST/help/self-check 与治理校验，输出 `READY_FOR_REVIEW` 离线收据并停止；不得 Stage PASS，产品四项保持 NOT_RUN。随后交由隔离 reviewer 执行 WP-S0-36。
```
