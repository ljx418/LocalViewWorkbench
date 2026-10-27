# V0-S0 Non-Owned GPU Blocker Handoff

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-17 / GATE3_CHECKPOINT / BLOCKED。独立报告：`reports/v0-s0/independent-review-correction-06.md`；blocker：`reports/v0-s0/gpu-owner-blocker.md`。

当前没有可执行的 Agent Workpack。项目负责人必须先关闭非本轮 owned 的 ComfyUI PID 48820 / 父 PID 43252。Agent 不得自行 kill、重跑、改候选或复用旧授权。

进程关闭后，root 先以 Windows-native `nvidia-smi.exe` 与只读进程查询复核总显存、PID、命令行和 owner，且确认 8191/11434 无未知 listener；通过后才能签发新的 harness 修复/真实运行 packet。

不得将“进程已关闭”自动解释为真实运行授权、Stage PASS 或 V0-S1 入口。所有历史失败、固定分母 NOT_RUN 和门限保持不变。
```
