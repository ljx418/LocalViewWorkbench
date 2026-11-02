# V0-S2 Implementation Prompt

```text
仅在 V0-S2 packet 激活后实施。以本机真实 MP4/MOV 为输入，先由 VideoMediaOwner 做允许根、类型、字节、时长和解码边界，再用已有 FFmpeg 在 CPU 上按时间轴有界采样默认四帧，记录 PTS/time base/秒值/hash。通过原生 ComfyUI 公共工作流驱动现有 LVWVideoFramesPromptBridge；不得让 Bridge 直接信任文件路径或全片解码。

实现单槽资源 owner、cancel epoch、晚到丢弃、finally 卸载和自有临时目录清理。不得修改冻结合同、阈值或分母，不得开放八帧、云回退、远程 URL、并行 GPU 或终止非 owned 进程。离线完成后只报告 READY_FOR_CHECKPOINT；真实运行须先生成母授权范围内的候选绑定子授权收据。
```
