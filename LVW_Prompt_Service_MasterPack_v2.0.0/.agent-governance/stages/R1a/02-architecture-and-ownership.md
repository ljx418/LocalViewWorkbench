# R1a Architecture And Ownership

## Owner

| 对象 | 唯一 owner |
|---|---|
| Stage packet、OpenAPI 子集、固定分母与门禁 | Codex gate owner |
| 产品实现与实现收据 | `codex_r1a_implementer` |
| 确定性测试与构建记录 | `local_ci` |
| 独立复算与反假绿审查 | `codex_r1a_independent_reviewer` |
| 真实 Ollama、测试媒体及浏览器体验授权与签署 | 项目负责人 |

## 生产路径

```text
React static dist (same origin)
  -> FastAPI /api/v1/media
  -> controlled media owner (hash, limits, EXIF, resize, run-owned file)
  -> /api/v1/jobs/analyze -> single local worker -> Ollama loopback adapter
  -> /api/v1/jobs/{id} -> /api/v1/model-runs/{id}
  -> raw + parsed suggestion (immutable machine result)
  -> explicit adopt -> browser draft (editable)
  -> local TXT/JSON download (no model call)
```

后端拥有媒体边界、任务状态、Ollama 调用与机器结果；前端拥有显示状态、未保存人工稿和显式采纳动作。前端不复制后端校验或任务终态规则。

## 界面方向

- 主题：本地影像分析光台，而不是管理后台。
- 色彩：`porcelain #eef2f3`、`ink #172630`、`cobalt #285bd4`、`signal orange #c75b32`、`sage #617a72`。
- 字体：Windows 本地 `Bahnschrift` 用于标题和状态数字，`Segoe UI Variable` / `Microsoft YaHei UI` 用于正文；无远程字体。
- 布局：桌面 42/58 左右分栏；左侧图像光台和运行轨迹，右侧结果分层与可编辑输出；窄屏按操作顺序纵向排列。
- 唯一强调元素：图像周围的取景框刻度，用于表达“观察范围”，不添加无意义渐变、玻璃卡片或散乱动效。
