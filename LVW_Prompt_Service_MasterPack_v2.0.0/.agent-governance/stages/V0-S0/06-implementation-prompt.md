# V0-S0 Implementation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / BLOCKED。基线提交：3c69a23d07064a0db5cb05258b237be2415a314a。先读 AGENTS.md、本 Stage 全部文件、docs/13_V0_IMPLEMENTATION.md、plans/acceptance_cases.json、plans/execution-control.json、reports/v0-s0/authorization.json 和 reports/v0-s0/independent-review.md。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

WP-S0-01/02 已停止，图片与视频均达到两次有效尝试上限。不得再次启动服务或重复媒体/模型请求。当前只允许离线修正坐标、验证器、收据清单和枚举，并形成纠偏包。补充 raw 证据或职责合规的重新执行需要新的明确授权、非 gate-owner 实现会话和新的 run_id；旧失败账本必须保留。

交付：changed files、contract changes or none、commands/exit codes、production path、fixed denominator status、artifact hashes、private/external action count、risks、exact stop reason。最终状态只能写 READY_FOR_REVIEW 或明确的 WAIT/BLOCKED/NO_GO，不得宣布 Stage PASS。
```
