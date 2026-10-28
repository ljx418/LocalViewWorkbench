# V0-S0 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Stage: V0-S0 / 现有环境与节点基线
Stage state: GATE1_IMPLEMENTATION / RUNNING
Product cases: NOT_RUN
Last passed gate: WP_S0_42_INDEPENDENT_MAJOR_REVIEW_COMPLETE
Baseline commit: 3c69a23d07064a0db5cb05258b237be2415a314a
Baseline product-control fingerprint: sha256:bd4875c1d53ce8a208e35cdb3b3b20110b290eb7f547eb1239b4eb1192764f4a
```

上述 fingerprint 依次绑定 `plans/tasks.json`、`plans/acceptance_cases.json`、`plans/release_gates.json` 的路径和原始字节。基线提交是本地候选身份，不表示产品验收通过，也未推送远端。

WP-S0-24 终态证据已封存为 `8fa8140`，授权已过期且禁止重跑。实现收据报告图片 1/1 PASS、视频 1/1 FAIL，四帧调用完成但语义 Oracle 因缺少 `camera_motion` 拒绝，decision=`NO_GO`；no-cloud、资源、逐调用卸载和最终清理报告通过。当前进入 WP-S0-25 隔离复审，产品四项仍 NOT_RUN，root 尚未作 S0 最终裁决。

WP-S0-25 结论 Fatal 1 / Major 2 / Minor 0，root 正式裁决 `NO_GO`：证据过采集触发 R-03；视频 Oracle 对 `camera_motion` 的 list 要求与 string 合同冲突；运行时 harness 身份未闭合。当前树已在 `664cbc7` 移除过采集进程表并标记为事后脱敏视图；原始提交仅本地隔离，禁止发布或推送。任何后续工作仅限离线预防性纠偏，旧授权不得复用。

项目负责人已授权继续修复。该授权仅开启 WP-S0-26/27 离线纠偏，不授权 live 重跑。实现范围冻结为隐私最小化、string `camera_motion` Oracle 和运行前 harness 自绑定；完成后必须进入 WP-S0-28 独立复审。

WP-S0-28 已确认 correction-09 为 Fatal 0 / Major 0；root 已封存候选 `d1f268f` 与审查 `40f94d6`。这只关闭前瞻性 harness 缺陷，不追溯修复 correction-08。S0 baseline 仍需一次新鲜、身份闭合、最小化证据的 WP-S0-29 运行及 WP-S0-30 独立复审；当前无 live 授权。

项目负责人已明确批准 `AUTH-REQUEST-V0-S0-WP-S0-29-01`，正式记录为 `AUTH-V0-S0-2026-10-27-10`。只允许一次 WP-S0-29；终态收据或任一媒体预算消耗后立即过期，随后必须进入 WP-S0-30，不能自动重跑。

WP-S0-29 已在服务前因 GPU used 6044 MiB > 4096 MiB 停止，图片/视频 0/0、服务/模型 0，授权已随终态收据过期。身份与隐私最小化门禁通过；终态证据封存为 `620a724`。当前只允许 WP-S0-30 离线复审，不得恢复授权或重跑。

WP-S0-30 结论 Fatal 0 / Major 0 / Minor 1，确认 run-level NO_GO 可信且无 owned 残留。当前正式阻塞为 `RESOURCE_BUSY_UNKNOWN_GPU_OWNER`：项目负责人需识别并释放占用；Agent 不得终止非 owned 进程。资源恢复后仍须新授权，0/0 媒体尝试不自动恢复旧授权。

root 已将 Minor 1 冻结为 WP-S0-31/32/33 离线纠偏：只修未来 receipt 对前置阻断的 `NOT_REACHED`、owned-resource absence 与 target-integrity comparison 语义，不改写 correction-10，也不启动或探测服务。离线实现与独立复审完成后，Stage 仍须返回 `RESOURCE_BUSY_UNKNOWN_GPU_OWNER` 门禁，直到项目负责人明确释放资源并另行授权。

WP-S0-31/32 候选已由 root 封存，离线回归 33/33、pack 1073/0、治理 43/0；产品四项仍为 NOT_RUN。当前只允许 WP-S0-33 独立离线复审，reviewer 不得修改候选或启动服务。

WP-S0-33 结论 Fatal 0 / Major 1 / Minor 0：Popen 已创建但 PID 未捕获、wait 超时且仍存活时，correction-11 仍可能把 cleanup 写成 PASS。root 已冻结 WP-S0-34/35/36 correction-12；只允许离线闭合 owned Popen 终态与负例，不授权 live 动作。

WP-S0-34/35 候选已由 root 封存，离线回归 37/37；当前只允许 WP-S0-36 独立复审。产品四项仍为 NOT_RUN，未知 GPU owner 的 live blocker 仍保留。

WP-S0-36 确认 Popen Major 已关闭，但发现 captured owned PID 的 stop-after 残留未进入 `cleanup.proven`，结论 Fatal 0 / Major 1 / Minor 0。root 已冻结 WP-S0-37/38/39，以单一权威公式闭合全部清理子状态；仍不授权 live 动作。

WP-S0-37/38 候选已由 root 封存，离线回归 40/40；当前只允许 WP-S0-39 独立复审。产品四项仍为 NOT_RUN，未知 GPU owner 的 live blocker 仍保留。

WP-S0-39 确认 proof 公式闭合，但发现 cleanup proof=false 未强制最终 decision 降级，结论 Fatal 0 / Major 1 / Minor 0。root 已冻结 WP-S0-40/41/42，使最终 decision、production status 与退出码消费权威 proof；仍不授权 live 动作。

WP-S0-40/41 候选已由 root 封存，离线回归 42/42；当前只允许 WP-S0-42 独立复审。产品四项仍为 NOT_RUN，未知 GPU owner 的 live blocker 仍保留。

WP-S0-42 确认成功出口假绿已关闭，但发现普通控制流的功能失败首因会被 cleanup 次因覆盖，结论 Fatal 0 / Major 1 / Minor 0。root 已冻结 WP-S0-43/44/45，统一 pre-cleanup primary 与 cleanup secondary 绑定；仍不授权 live 动作。
