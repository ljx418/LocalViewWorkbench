# V0-S0 correction-03 Real Verification Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-12 / GATE4_REAL_ACCEPTANCE。候选提交：078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68；WP-S0-10 证据/收据：78e7285ef8a2371c07207d99a7c46944aeaee873 / aa06455f04373cf1a168cbf2b403f400d96270b6。先读 AGENTS.md、本 Stage 全部文件、`reports/v0-s0/authorization-correction-05.json` 和 correction-04 raw/receipt。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

只允许 `codex_isolated_implementer` 按 `AUTH-V0-S0-2026-10-27-05` 执行 WP-S0-12。基于 correction-04 harness 新建 correction-05 harness，只把 Comfy `main.py` 和 cwd 经 `wslpath -w` 转换；继续用 Windows-native no-cloud wrapper，并重新证明至少 10 秒/5 样本 owned PID remote TCP 空集，之后才可启动 fresh temp-base Comfy 及各一次图片/视频尝试。

不得改候选、合同、阈值、目标配置或历史失败，不得改防火墙/注册表/永久环境，不得调用云/付费 Provider、下载、启动可见浏览器或 kill 非 owned 进程。遇到 no-cloud 未生效、远程连接、显存 `>=23552 MiB`、未知 owner 或清理缺口立即停止。交付仅限 `reports/v0-s0/correction-05/` 和新 live receipt；最终只能 READY_FOR_REVIEW 或明确 NO-GO/BLOCKED，不能宣布 Stage PASS。
```
