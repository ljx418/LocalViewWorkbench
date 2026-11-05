# V0-S2 Acceptance Matrix

Stage 固定分母：`V0-A02,V0-A07,V0-A09,V0-A10`

```text
sha256(sorted IDs joined by LF with trailing LF)
32a72139e0c12e0e6d040274024b53bb2dba2f2864b68b840aa215cf739a2a7f
```

| 义务 | 生产路径与明确 Oracle | 负例/边界 |
|---|---|---|
| V0-A02 视频有限抽帧 | MP4/MOV→media owner→ffprobe 或受控 PyAV 元数据→FFmpeg→4 帧→Comfy 公开 owner→Bridge；四帧顺序、PTS/time base/秒值/hash 可复算；真实 provider 每帧一次 | 静态、跟拍、快切、VFR；0/1/4/5 帧；重复时间戳；不开放 8 帧 |
| V0-A07 文件安全 | 公共文件入口→允许根→自有临时目录；失败前无 GPU/provider 动作 | 路径穿越、绝对/UNC、reparse、伪扩展、损坏、>256MiB、>60s、元数据提示注入 |
| V0-A09 资源与性能 | 冻结 profile；热图 10 次、热四帧 10 次、另记冷加载；原始逐次采样计算 P95 | GPU `<23552 MiB`、host RAM `>=2048 MiB`、图 P95 `<=180s`、四帧 P95 `<=300s`、OOM=0；污染环境停止 |
| V0-A10 取消与卸载 | 公共取消→cancel epoch→子进程/worker 停止→晚到丢弃→资源 released | 反馈 `<=1s`；实际停止后 `<=30s` 释放；正常/失败/取消；外部占用不抢占、不误杀 |

V0.1 累计出门还需同一发布候选回归 `V0-A01/A03/A04/A05/A08`。任何 `SKIPPED/BLOCKED/NOT_RUN` 不计 PASS；历史 S0/S1/R1a 结果只可按冻结证据复用规则使用。

边界口径补充（1.0.16）：docs/13 已允许短片 1–3 个不同采样时间点并警告；默认、四类固定样本及热视频基准继续各四帧。0/5 帧失败；manifest 重复/倒退 PTS 失败；两个窗口选择同一个实际帧只能保留一次，不能复制为两次观察。静态相同像素在不同实际 PTS 可保留。浏览器导出的 source 整数须保持服务端精度。此补充不缩小任何固定分母，真实短片/原生 EOF 兼容性仍待证明。


1.0.34批准纠偏：A09运行峰值/性能等硬限不变；冷启动改为已绑定模型profile的空闲/预测预算，不使用4096MiB桌面占用上限。当前V0实际ctx2048/predict768不提高；基线允许0..23551MiB真实值，释放仍相对基线+1024且有独立总峰值监控。同设备先后读数取保守max_used/min_free，保留差额诊断而不要求差值<=128MiB或total-used-free<=256MiB。见批准change-decision-gpu-admission-01.json及stage-control.gpu_admission_policy。
