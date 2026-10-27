# V0-S0 Implementation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WAIT_AUTH。先读 AGENTS.md、本 Stage 全部文件、docs/13_V0_IMPLEMENTATION.md、plans/acceptance_cases.json 和 plans/execution-control.json。

没有一份逐次明确授权时，只允许运行：
python3 tools/verify_pack.py --schema
python3 tools/verify_governance.py --self-test
随后停止，不读取目标机私有目录，不调用 Comfy/Ollama，不使用真实媒体。

授权后按 WP-S0-01、WP-S0-02 顺序执行。只读盘点；禁止下载、升级、写配置、改公共合同、改固定分母、删除失败证据或进入 V0-S1。所有真实运行绑定样本 hash、model digest、命令/退出码、环境和清理证明。最多两次有效重试；无新证据则停止。

交付：changed files、contract changes or none、commands/exit codes、production path、fixed denominator status、artifact hashes、private/external action count、risks、exact stop reason。最终状态只能写 READY_FOR_REVIEW 或明确的 WAIT/BLOCKED/NO_GO，不得宣布 Stage PASS。
```
