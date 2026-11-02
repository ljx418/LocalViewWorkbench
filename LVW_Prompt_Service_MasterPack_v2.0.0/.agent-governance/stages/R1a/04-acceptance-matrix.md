# R1a Acceptance Matrix

固定分母：`R1A-M01,R1A-M02,R1A-M03,R1A-M04,R1A-M05,R1A-M06,R1A-M07`

```text
sha256(sorted IDs joined by LF with trailing LF)
82a3736ab77ee98e301d7e055a78b160774c9c09692288db89c5a2768bfe39ab
```

| 义务 | 生产路径与 Oracle | 负例/边界 |
|---|---|---|
| R1A-M01 受控媒体 | React→media owner；hash、格式、尺寸、字节、预处理可追 | 损坏、伪装、20MiB/40MP exact 与 one-over |
| R1A-M02 真实分析 | React→job→Ollama→model-run；raw/PromptSpec 同 run且 provider 恰为 1；配置/自定义指导进入请求 | 停止、超时、拒绝、非法 JSON、非 loopback |
| R1A-M03 无模型人工路径 | draft→copy/download；provider 为 0，四输出可编辑导出 | 空稿、Unicode、剪贴板失败 |
| R1A-M04 显式采纳 | 建议不自动覆盖；四输出非空且导出逐字段一致 | dirty draft、raw 默认折叠、重复分析 |
| R1A-M05 真实 React | FastAPI 同源 dist；键盘可用；360/1280/1920 无横溢出 | CDN、临时 UI、绝对外联 |
| R1A-M06 独立质量 | 固定图片隔离复算；观察/推断分离；Fatal=0/Major=0 | 不得用旧样本或旧候选替代 |
| R1A-M07 失败与所有权安全 | fail-closed、run-owned 清理；外部 Ollama 显示 `external` 且控制禁用 | 路径、外联、秘密、非 owned 进程、残留 |

任何 `SKIPPED/BLOCKED/NOT_RUN` 都不计 PASS。本矩阵不替代全局 V1 分母。
