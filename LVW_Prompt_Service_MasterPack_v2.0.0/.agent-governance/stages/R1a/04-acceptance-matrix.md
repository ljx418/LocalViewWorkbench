# R1a Acceptance Matrix

冻结分母：`R1A-M01,R1A-M02,R1A-M03,R1A-M04,R1A-M05,R1A-M06,R1A-M07`

```text
sha256(sorted IDs joined by LF with trailing LF)
82a3736ab77ee98e301d7e055a78b160774c9c09692288db89c5a2768bfe39ab
```

| 义务 | 生产路径 | Oracle | 负例/边界 |
|---|---|---|---|
| R1A-M01 受控媒体 | React→multipart→media owner | hash、格式、尺寸、字节、预处理可追 | 损坏、格式伪装、20MiB exact/one-over、40MP exact/one-over |
| R1A-M02 真实分析 | React→job API→Ollama adapter→model-run | raw 与 PromptSpec 同 run；真实 provider 调用恰为 1 | Ollama 停止、超时、非法 JSON、非 loopback |
| R1A-M03 无模型人工路径 | React draft→copy/download | provider 调用为 0；四输出可编辑导出 | 空稿、Unicode、剪贴板失败 |
| R1A-M04 显式采纳与四输出 | 单次建议→确认→显式采纳→四输出 | 建议不自动覆盖；导出逐字段一致且不重复分析 | dirty draft、缺中文/负向、raw 默认折叠 |
| R1A-M05 真实 React | Vite build→FastAPI 同源 dist | 无 CDN/Node 生产服务/Gradio；键盘可用 | 360/1280/1920、水平溢出、raw 展开状态 |
| R1A-M06 单图独立质量复核 | 固定真实图片→隔离审查 | 观察与推断分离；语义可用；Fatal/Major=0 | 失败不得用旧样本替换 |
| R1A-M07 同源、loopback 与失败安全 | 上传/API/静态服务/运行清理 | fail-closed、外联预阻断、run-owned 清理 | 路径、外联、秘密、模型失败、dirty draft、非 owned 进程 |

R1a 工程出门需要同一候选的机器检查和独立审查；随后仍必须由项目负责人完成人工体验签署。任何 `SKIPPED/BLOCKED/NOT_RUN` 都不能计为通过。

本矩阵只定义 R1a 早期切片门禁，不替代或重解释全局 V1 的 `A01/A02/A03/A05/F01/Q01/X01`；后者保持原始分母并在后续 V1 Stage 验收。
