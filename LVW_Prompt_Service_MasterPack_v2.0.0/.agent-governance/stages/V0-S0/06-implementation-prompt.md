# V0-S0 correction-03 Real Verification Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-08 / GATE4_REAL_ACCEPTANCE。候选提交：078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68；收据提交：2df895318ae1278452a399622fb29f41eb3dce73。先读 AGENTS.md、本 Stage 全部文件、`reports/v0-s0/authorization-correction-03.json`、两轮独立审查和 gate decision。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

只允许 `codex_isolated_implementer` 按新授权执行 WP-S0-08。使用 fresh run-owned Windows temp base，把封存 bridge 复制到临时 `custom_nodes`，从原 Comfy main 以 127.0.0.1:8191 启动；不写原安装。Ollama 仅 127.0.0.1:11434 与固定 digest。图片与视频各最多两次有效尝试；视频用四个 384-long-edge 有序帧。保存 `/prompt`、history、raw、oracle、GPU/RAM、owned PID/listener/remote TCP、`/api/ps` 和每条 run 清理证据。

不得改候选、合同、阈值、目标配置或历史失败，不得调用云/付费 Provider、下载、启动可见浏览器或 kill 非 owned 进程。遇到远程连接、显存 `>=23552 MiB`、未知 owner 或清理缺口立即停止。交付仅限 `reports/v0-s0/correction-03/` 和 live implementation receipt；最终只能 READY_FOR_REVIEW 或明确 NO-GO/BLOCKED，不能宣布 Stage PASS。
```
