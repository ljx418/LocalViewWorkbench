# V0-S1 Architecture And Ownership

## Owner

| 对象 | 唯一 owner |
|---|---|
| V0 合同、Stage packet、固定分母与门禁 | Codex + Sol |
| S1 产品实现与实现收据 | V0 结束前由 `codex_isolated_implementer` 临时代行 Claude Code/DSH；每个 Workpack 单 owner |
| 产品合同/工作流/收据的确定性校验 | 可信本地执行器 |
| 隔离复算和反假绿审查 | `codex_isolated_reviewer`，与实现上下文和写入权限隔离；root Codex 裁决 |
| 本地服务、私有媒体、可见浏览器与付费调用授权 | 人类负责人 |

## 生产所有权

```text
ComfyUI 原生 UI / LVW 静态面板
  ├─ manual draft owner（纯 CPU、无队列）
  │    └─ explicit export owner -> TXT / lvw.v0.result/1 JSON
  └─ controlled image input owner
       -> preprocessing owner
       -> S0 验证的 Prompt Assistant/Ollama 公共入口
       -> immutable raw result
       -> parsed suggestion
       -> explicit adopt only
       -> manual draft owner
```

`raw_response`、`suggestion`、`draft` 和 `draft_epoch` 是不同状态。模型回调只可更新与当前 run token 匹配的 raw/suggestion；不得直接写 draft。人工编辑与导出不进入 GPU 队列，不依赖模型健康。

项目自有代码应落在增量包的 `custom_nodes/lvw_v0_bridge/` 和同源静态 JS 中；目标 ComfyUI 安装只在后续明确授权的安装/验收步骤中触碰。

已验证的 S0 公共节点绑定为 `LVWImagePromptBridge` 与 `LVWVideoFramesPromptBridge`，入口为 Comfy public `/prompt`/`history`。S1 绑定 S0 出口 `dfb00ad...`、产品候选 `138b4486...` 与 Harness `81a77cc...`；不得把测试函数或新别名替代这些生产 owner。公共绑定变化必须停止并重新进入 Gate 0。
