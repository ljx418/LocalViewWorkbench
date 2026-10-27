# V0-S0 Architecture And Ownership

## 权威与 owner

| 对象 | 唯一 owner |
|---|---|
| PRD、架构、合同、Stage 门禁 | Codex + Sol |
| WP-S0-01/02 原计划实现运行 | Claude Code + MiniMax（额度不可用；首轮发生角色偏差并已封存） |
| WP-S0-04 纠偏实现运行与收据 | `codex_isolated_implementer`，与 root gate owner 隔离 |
| 确定性文件/hash/分母校验 | 可信本地执行器 |
| 独立复算 | `codex_isolated_reviewer`，与实现会话及 root gate owner 隔离；这是人类批准的临时 DSH 替代 |
| 私有路径、真实媒体、服务调用授权 | 人类负责人 |

## 调用边界

```text
授权的只读 inventory
  -> 本机版本/路径/注册表摘要
  -> 获授权的真实单图与四帧探测
  -> 原始日志/资源观察/哈希
  -> 实现收据
  -> CI 结构检查
  -> 隔离独立审查
  -> Codex checkpoint
```

禁止任意 Shell 能力暴露给模型，禁止远程 URL 媒体，禁止把本地路径、Cookie、原图或原视频写入公开证据。目标系统 owner 保持为 ComfyUI/Prompt Assistant/Ollama；S0 不重写其状态。
