# V0-S2 Architecture And Ownership

| 对象 | 唯一 owner |
|---|---|
| Stage packet、固定分母、门禁 | `codex_gate_owner` |
| V0-S2 产品实现 | `codex_v0_s2_implementer` |
| 确定性检查与结构化收据 | `local_ci` |
| 隔离复算与反假绿 | `codex_v0_s2_independent_reviewer` |
| 真实媒体/GPU/Comfy/Ollama 授权 | `AUTH-PROGRAM-V1-LOCAL-01` 子授权策略 |
| 人工体验与发布选择 | 项目负责人 |

```text
local MP4/MOV
  -> VideoMediaOwner (path/size/type/duration/stream limits)
  -> run-owned ffprobe + ffmpeg CPU sampler (4 bounded frames)
  -> frame manifest (index/PTS/time_base/time/hash)
  -> native ComfyUI API workflow
  -> LVWVideoFramesPromptBridge (ordered, one frame per provider call)
  -> raw per-frame evidence + video suggestion
  -> explicit adoption/manual export
```

`VideoMediaOwner` 拥有文件、探测、抽帧和临时目录；Bridge 只接受已经有界的帧，不承担视频文件安全。资源 owner 持有单槽锁、run token、cancel epoch 和自有子进程句柄；不得终止外部 Comfy/Ollama/FFmpeg 进程。
