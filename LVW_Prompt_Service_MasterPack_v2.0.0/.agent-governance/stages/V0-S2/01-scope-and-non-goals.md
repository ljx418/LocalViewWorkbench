# V0-S2 Scope And Non-Goals

## 目标

- 本机接收 MP4/MOV，执行类型、字节、时长、路径和解码边界检查。
- 使用已有 FFmpeg/ffprobe 在 CPU 上按时间轴有界采样默认四帧，最长边 768；保存顺序、PTS、time base、秒值和帧 hash。
- 通过原生 ComfyUI 公共工作流驱动 `LVWVideoFramesPromptBridge`，生成视频描述、运动推断和局限说明。
- 建立请求级单槽资源锁、取消 epoch、晚到丢弃、finally 卸载和自有临时目录清理。
- 完成文件安全、10 次资源/性能分母及取消/卸载真实验收。

## 非目标

- 不开放未经验证的八帧高级配置，不支持远程 URL、长视频、云回退或并行 GPU 推理。
- 不把 R1a React 页面、已有帧数组单测或 V0-S0 探测证据当成 V0.1 PASS。
- 不修改冻结公共 Schema、错误码、阈值或 V0-Min 历史证据。
- 不实施 V0-S3 的增量包、迁移、回滚和 10 图/6 视频最终质量集。
