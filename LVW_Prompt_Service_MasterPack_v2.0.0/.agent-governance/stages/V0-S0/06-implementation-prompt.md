# V0-S0 correction-03 Offline Implementation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-06 / GATE1_IMPLEMENTATION。纠偏基准提交：9e8f62a34c11c6b9068959cf5831091470cdfb65。先读 AGENTS.md、本 Stage 全部文件、docs/13_V0_IMPLEMENTATION.md、plans/acceptance_cases.json、plans/execution-control.json、两轮独立审查和 gate decision。

授权仅覆盖现有本地 ComfyUI/Ollama 的 loopback 启停与查询、COMFY_ROOT/TEST_SOURCE、生成的非私有夹具、单图和有界四帧探测。禁止下载、升级、写配置、调用云/付费 Provider、启动可见浏览器、读取 Cookie 或推送远端。

只允许 `codex_isolated_implementer` 执行 WP-S0-06/07。允许路径仅为 `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/`、`LVW_V0_RuntimePatch/tests/` 和 `reports/v0-s0/implementation-receipt-correction-03.json`。不得启动 ComfyUI/Ollama、调用模型、修改目标安装、Prompt Assistant、产品合同/分母/阈值或历史证据。

实现一个可由 Comfy 注册并真实执行的薄 bridge，核心 transport/oracle 可在无 Comfy 环境下测试。定向测试必须驱动公开 node owner，覆盖正常与负例、逐帧上界、loopback、超时、semantic fail-closed、prompt echo、keep_alive 和清理。交付实现收据、文件清单、命令/退出码和风险；最终只能 READY_FOR_REVIEW 或明确停止状态。
```
