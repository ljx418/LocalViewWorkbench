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
  -> run-owned ffprobe or isolated native Python/PyAV metadata probe
  -> run-owned FFmpeg CPU sampler (4 bounded frames)
  -> frame manifest (index/PTS/time_base/time/hash)
  -> native ComfyUI API workflow
  -> LVWVideoPromptOwner -> VideoRequestOwner -> BridgeOwner (ordered, one frame per provider call)
  -> raw per-frame evidence + video suggestion
  -> explicit adoption/manual export
```

`VideoMediaOwner` 拥有文件、探测、抽帧和临时目录；Bridge 只接受已经有界的帧，不承担视频文件安全。资源 owner 持有单槽锁、run token、cancel epoch 和自有子进程句柄；不得终止外部 Comfy/Ollama/FFmpeg 进程。

元数据适配遵循 `reports/v0-s2/decoder-binding-decision-01.md`：复用已安装 PyAV 18 与 FFmpeg 7.1，不下载；元数据子进程不积累/返回帧，不加载模型。它输出同一内部探测文档，帧采样仍由 FFmpeg CLI 执行。必须单独验证 Windows 原生公开节点兼容性；包存在、Linux 结果和 Mock 均不能替代。

原生工作台 CPU 控制扩展遵循 `reports/v0-s2/change-decision-video-workbench-01.json`：`POST /lvw/v0/video/workbench` 的 preview 复用 ManualDraftOwner，不获取 GPU 锁、不进执行队列、不写文件/剪贴板；adopt 只读取 VideoRequestOwner 当前成功快照，按原有字段投影四输出。浏览器显式采纳后保存该来源快照，后续 JSON 导出只合并经 owner 验证的人工字段与来源及编辑标志，不复制后端编译规则。导出是用户可编辑产物，不是可信执行收据；V0 没有业务数据库或页面刷新恢复保证。
