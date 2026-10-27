# V0-S0 correction-03 Real Verification Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-10 / GATE4_REAL_ACCEPTANCE。候选提交：078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68；WP-S0-08 停止证据：9256c063128624672dfb5b258b7576406ff339ac。先读 AGENTS.md、本 Stage 全部文件、`reports/v0-s0/authorization-correction-04.json`、WP-S0-08 raw/receipt、两轮独立审查和 gate decision。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

只允许 `codex_isolated_implementer` 按 `AUTH-V0-S0-2026-10-27-04` 执行 WP-S0-10。必须由 Windows `cmd.exe` 或 PowerShell 在同一 run-owned wrapper 内设置 no-cloud 环境后启动 Ollama；先证明 server raw 为 true 并完成至少 10 秒/5 样本的 owned PID remote TCP 空集，才可启动 fresh temp-base Comfy 及各一次图片/视频尝试。

不得改候选、合同、阈值、目标配置或历史失败，不得改防火墙/注册表/永久环境，不得调用云/付费 Provider、下载、启动可见浏览器或 kill 非 owned 进程。遇到 no-cloud 未生效、远程连接、显存 `>=23552 MiB`、未知 owner 或清理缺口立即停止。交付仅限 `reports/v0-s0/correction-04/` 和新 live receipt；最终只能 READY_FOR_REVIEW 或明确 NO-GO/BLOCKED，不能宣布 Stage PASS。
```
