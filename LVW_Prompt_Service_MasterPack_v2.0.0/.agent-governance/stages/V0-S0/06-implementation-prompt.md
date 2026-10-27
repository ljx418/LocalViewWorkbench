# V0-S0 correction-07 Offline Harness Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-18 / GATE1_IMPLEMENTATION / RUNNING。先读独立报告、`gpu-owner-blocker.md`、`gpu-owner-clearance.md`、correction-06 probe/raw 和本 Stage 2.4.0 packet。

只允许 `codex_isolated_implementer` 新增 `tools/v0_s0_live_probe.py`、对应离线测试及 correction-07 offline receipt。不得启动 ComfyUI/Ollama、修改产品候选/合同/阈值、写目标配置或复用旧授权。

Windows-native preflight 必须早于任何 service start：GPU used `<=4096 MiB`；无 Comfy portable Python、Ollama、8191/11434 listener；Windows/WSL GPU 总量差异必须明确记录。修复 timeout cleanup 假阴性和顶层 KeyError，保留 stable history 首因。所有分支均以确定性 fixture 自测。

交付只能 READY_FOR_REVIEW/NO-GO/BLOCKED，不得宣布 Stage PASS。WP-S0-20 尚未授权；所有历史失败、固定分母 NOT_RUN、120 秒、23552 MiB 和内容 Oracle 保持不变。
```
