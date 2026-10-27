# V0-S0 correction-06 Offline Implementation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-14 / GATE1_IMPLEMENTATION。基线候选：078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68；correction-05 原始证据/封存收据：03ce1c48a330effcc79efc9c2b336e4cc62893b4 / 1f8982b。先读 AGENTS.md、本 Stage 全部文件、`reports/v0-s0/correction-05/attempt-video-1.json` 和 live receipt。

本 Workpack 仅授权离线仓库编辑和测试。禁止启动 ComfyUI/Ollama、下载、升级、写目标配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

只允许 `codex_isolated_implementer` 执行 WP-S0-14/15。最小修改 `_request_instruction`，明确 `prompt` 字段必须是基于当前可见事实的具体生成提示，且不得复制/改写请求指令或 `user_instruction`。保持现有 exact-echo Oracle 不变。新增公开 owner 测试，检查 outgoing 指令包含 grounding/anti-copy 义务，并证明用户指令回显与完整请求回显仍失败且清理。

不得改产品合同、公共错误码、响应字段、阈值、目标配置、历史失败或 Oracle 门槛。运行仓库 Python 与 portable Python 的完整 bridge 测试；生成候选提交和 `reports/v0-s0/implementation-receipt-correction-06-offline.json`。最终只能 READY_FOR_REVIEW 或明确 NO-GO/BLOCKED，不能宣布 Stage PASS；WP-S0-16 另需新授权。
```
