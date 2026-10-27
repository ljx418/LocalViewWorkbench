# V0-S0 correction-06 Independent Review Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-17 / GATE3_CHECKPOINT。候选：138b4486fdaeb8d207ef6b5efb63a09865f174b9；WP-S0-16 原始证据/封存收据：d337866d5f6bbb49f04d75ec0b4b1b79ba5d587e / 25ac028。先读 AGENTS.md、本 Stage 全部文件、全部 correction-03..06 收据及 correction-06 raw。

只允许 `codex_isolated_reviewer` 做离线只读复算并写 `reports/v0-s0/independent-review-correction-06.md`。禁止启动 ComfyUI/Ollama、修改候选/证据、下载、外部调用或代替 root 作 Stage 裁决。

独立核对：candidate/authorization/evidence commit；26 个 changed files 与 24 项 manifest；真实 Comfy `/prompt` 与异常；120 秒超时根因边界；cleanup 请求 200→chat 499 的并发时序是否应等同 cleanup failure；最终 `/api/ps`、端口、owned PID、temp 与 target integrity；GPU 23521/23552；0 remote；视频 0 次与产品四项 NOT_RUN。必须保留历史 NO-GO，不接受实现者自述。

报告 Fatal/Major/Minor，每项给位置、触发条件、预期、实际和证据；明确哪些是候选问题、环境/性能问题或 harness 假阴性。只能给审查建议，不能宣布 Stage PASS。root 根据报告决定 NO-GO、BLOCKED 或新纠偏包。
```
