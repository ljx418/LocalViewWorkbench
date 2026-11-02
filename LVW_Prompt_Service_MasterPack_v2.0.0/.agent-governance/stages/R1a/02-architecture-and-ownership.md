# R1a Architecture And Ownership

| 对象 | 唯一 owner |
|---|---|
| Stage packet、固定分母与门禁 | Codex gate owner |
| 产品实现与实现收据 | `codex_r1a_implementer` |
| 确定性测试与构建记录 | `local_ci` |
| 隔离复算与反假绿审查 | `codex_r1a_independent_reviewer` |
| 真实 Ollama、媒体、浏览器授权与人工签署 | 项目负责人 |

```text
React static dist (same origin)
  -> FastAPI media owner -> job owner -> Ollama loopback adapter
  -> raw + immutable parsed suggestion -> explicit adopt -> editable draft
  -> local TXT/JSON export

React runtime panel -> /api/v1/runtime/status
  -> fixed start/reset/stop actions + local control header
  -> backend runtime owner -> only its own Ollama child/proxy
```

系统模板定义 JSON 输出和安全边界；内容配置定义描述详细度；最多 800 字的自定义指导是低优先级附加信息，不能覆盖 schema、loopback、未成年人或非法内容边界。前端不得复制后端终态规则。外部启动的 Ollama 状态为 `external`，控制按钮必须禁用。
