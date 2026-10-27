# V0-S0 Implementation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-04 / RUNNING。基线提交：3c69a23d07064a0db5cb05258b237be2415a314a。先读 AGENTS.md、本 Stage 全部文件、docs/13_V0_IMPLEMENTATION.md、plans/acceptance_cases.json、plans/execution-control.json、两份授权、首轮失败账本和独立审查。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

首轮 WP-S0-01/02 已停止且旧预算不得复用。新授权只允许 `codex_isolated_implementer` 执行 WP-S0-04：创建新 run_id，以确定性 harness 捕获 raw 与退出码，图片/视频各最多两次，保存至 `reports/v0-s0/rerun-02/`。禁止 root gate-owner 会话执行探测，禁止删除旧失败、改合同/分母、写目标配置、下载、外部 Provider 或进入 V0-S1。

交付：deterministic harness、raw redacted logs、changed files、contract changes or none、commands/exit codes、production path or explicit NO_GO、fixed denominator status、artifact hashes、private/external action count、risks、exact stop reason。最终状态只能写 READY_FOR_REVIEW 或明确的 WAIT/BLOCKED/NO_GO，不得宣布 Stage PASS。
```
