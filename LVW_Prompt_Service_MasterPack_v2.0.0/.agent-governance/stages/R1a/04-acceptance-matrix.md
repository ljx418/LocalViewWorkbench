# R1a Acceptance Matrix

冻结分母：`A01,A02,A03,A05,F01,Q01,X01`

```text
sha256(sorted IDs joined by LF with trailing LF)
fe6c7d1620ca1ff7a0f9f594699f66660d05fa2aa80544cb04ad9cec3f9df1a5
```

| 义务 | 生产路径 | Oracle | 负例/边界 |
|---|---|---|---|
| A01 受控媒体 | React→multipart→media owner | hash、格式、尺寸、字节、预处理可追 | 损坏、格式伪装、20MiB exact/one-over、40MP exact/one-over |
| A02 真实分析 | React→job API→Ollama adapter→model-run | raw 与 PromptSpec 同 run；非 demo | Ollama 停止、超时、非法 JSON、非 loopback |
| A03 无模型人工路径 | React draft→copy/download | 0 模型调用；中文/英文/负向可编辑 | 空稿、Unicode、剪贴板失败 |
| A05 四输出 | 单次建议→显式采纳→四输出 | 切换/编辑/导出不重复分析 | 缺中文、缺负向词、raw 不可编辑 |
| F01 真实 React | Vite build→FastAPI 同源 dist | 无 CDN/Node 生产服务/Gradio | 360/1280/1920、键盘、200%、reduced motion |
| Q01 质量复核 | 固定真实图片→独立人工评分 | 观察与推断分离；语义可用 | 失败不得用旧样本替换 |
| X01 安全与失败 | 上传/API/静态服务 | fail-closed、无任意路径/URL/云回退 | 路径、外联、秘密、错误不覆盖草稿 |

R1a 工程出门需要同一候选的机器检查和独立审查；随后仍必须由项目负责人完成人工体验签署。任何 `SKIPPED/BLOCKED/NOT_RUN` 都不能计为通过。
