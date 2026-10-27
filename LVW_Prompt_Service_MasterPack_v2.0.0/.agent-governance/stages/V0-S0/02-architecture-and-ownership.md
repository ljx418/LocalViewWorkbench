# V0-S0 Architecture And Ownership

## 权威与 owner

| 对象 | 唯一 owner |
|---|---|
| PRD、架构、合同、Stage 门禁 | Codex + Sol |
| WP-S0-01/02 原计划实现运行 | Claude Code + MiniMax（额度不可用；首轮发生角色偏差并已封存） |
| WP-S0-04 纠偏实现运行与收据 | `codex_isolated_implementer`，与 root gate owner 隔离 |
| WP-S0-06/07 离线 bridge 实现与测试 | `codex_isolated_implementer`，仅写仓库内 `LVW_V0_RuntimePatch/` |
| WP-S0-08 新候选真实验证 | 同一实现 owner；另需有限运行记录，不得由 root 执行 |
| WP-S0-09 三次 checkpoint | `codex_isolated_reviewer`，只读候选和新鲜证据 |

纠偏候选只新增一个 `custom_nodes/lvw_v0_bridge` 薄扩展。它拥有 Comfy 注册节点到 loopback Ollama `/api/chat` 的连接、严格响应 oracle、raw/suggestion 分离与 `keep_alive=0` 清理；不得复制 Prompt Assistant、修改其源码或暴露远程 Provider。视频基线路径最多接收四个已受控缩小帧，按帧顺序逐次视觉调用，避免四图同请求的显存峰值；完整视频文件边界仍留给 V0-S2。
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
