# V0-S0 correction-08 Offline Harness Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-22 / GATE1_IMPLEMENTATION / RUNNING。先读 Stage 2.7.0、correction-07 raw/receipts、WP-S0-21 report 与 harness commit `82975ae...`。

只允许 `codex_isolated_implementer` 修改 `tools/v0_s0_live_probe.py`、其测试和 correction-08 offline receipt。不得启动服务、修改产品 candidate/Oracle/门限或历史 evidence。

PowerShell 子进程显式设 UTF-8 输出；Python 接收 bytes 并 strict decode。非 UTF-8 fixture 必须稳定返回 `WINDOWS_OWNER_ENUMERATION_FAILED` 且写 preflight artifact。receipt finalization 对缺失 artifact安全，始终保留首因并生成完整 BLOCKED receipt。保持所有既有 fixture。

输出 READY_FOR_REVIEW/NO-GO/BLOCKED 和离线收据，不得 Stage PASS。WP-S0-24 未授权，产品四项保持 NOT_RUN。
```
