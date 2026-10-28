# V0-S0 / WP-S0-45 correction-15 独立离线复审

审查日期：2026-10-28（Asia/Shanghai）
审查角色：`codex_isolated_reviewer`
冻结 packet：`ffd0a67e5d189d676ed930b7a227adece24f6121`
候选实现：`81a77cc013243f859167bd00a1971ad1543c2e46`
gate-owner seal/checkpoint：`29069bf35b524afd6f4e22ce01c0ca830989e618`

审查方式：离线独立复算、终态原因静态搜索及临时目录完整 mock fixture；未启动或探测 ComfyUI/Ollama，未访问网络或真实媒体，未修改候选、manifest、坐标或历史 evidence。

## 结论

Fatal **0** / Major **0** / Minor **0**

correction-15 已闭合本轮冻结范围。异常首因、普通控制流 NO_GO/BLOCKED 首因和 READY 后 cleanup 降级三类都能正确区分：既有失败 reason 被保留，cleanup/request-trace 只追加 secondary event；只有 pre-cleanup READY 才由 cleanup proof=false 降级。最终 decision、reason、summary、receipt、production status 与 return code 一致，没有发现 cleanup failure 覆盖已确定 primary 的其他路径。

这只支持 **WP-S0-43/44 离线纠偏可结束并交 root checkpoint**，不支持 Stage PASS 或 live 授权。产品四项仍为 NOT_RUN；S0 的真实外部阻塞仍是 `RESOURCE_BUSY_UNKNOWN_GPU_OWNER`。

## Findings

无 Fatal、Major 或 Minor finding。

## 三类终态独立复算

使用未复用实现测试 helper 的完整 `Probe.run()` 临时 fixture，并额外叠加 request-trace cleanup correlation failure：

- **普通 public route failure + cleanup residual**：image attempt 先失败；captured PID stop-after 非空，proof=false；最终 decision=NO_GO、reason=`PUBLIC_COMFY_ROUTE_FAILED_WITHIN_ATTEMPT_BUDGET`、rc=2、production partial。events 同时保存 `CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN` 与 `OLLAMA_REQUEST_CLEANUP_CORRELATION_FAILED` 两个 secondary，后处理没有覆盖首因。
- **异常首因 + cleanup residual**：attempt 中抛出 mandatory `PRE_MODEL_NON_LOOPBACK_REMOTE_TCP`；cleanup proof=false 且 request trace 随后失败。最终 decision=NO_GO、reason 保持该异常首因、rc=2、production partial，并追加上述两个 secondary。
- **READY + cleanup residual**：图片/视频功能均成功，随后 captured PID residual 使 proof=false；最终降级为 NO_GO、reason=`CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN`、rc=2、production partial。随后 request trace failure 仅追加 secondary，不覆盖 cleanup primary。
- **功能与 cleanup 全绿**：proof=true、无 secondary；最终 READY_FOR_REVIEW、reason=`AUTHORIZED_LIVE_PROBE_COMPLETE`、rc=0、production complete。

另复算既有 owner-enumeration BLOCKED exception：cleanup failure 不覆盖 `WINDOWS_OWNER_ENUMERATION_FAILED`，receipt/summary 仍为 BLOCKED，secondary event 存在。

## 原因绑定与旁路搜索

- `primary_stop_reason` 在 except 路径直接绑定异常 reason；进入 finally 时，若 decision 已为 NO_GO/BLOCKED 且 reason 已确定，则普通控制流 reason 也被捕获为 primary。
- cleanup proof=false 时，有 primary 就只追加 cleanup secondary；只有 decision=READY_FOR_REVIEW 且无 primary 才降级为 cleanup NO_GO，并立即把 cleanup reason 固化为 primary。
- 后续 request-trace failure 检查相同 primary：已有 primary 时只追加 secondary；没有发现其覆盖异常、route、resource、remote、semantic 或 cleanup primary 的路径。
- summary 与 receipt 在全部终态处理后读取同一 `self.decision/self.exact_stop_reason`；production status 由最终 decision 计算；live run 唯一 rc=0 路径仍是最终 decision=READY_FOR_REVIEW。
- 静态搜索没有发现 cleanup proof=false 时返回 0、READY 或 complete 的旁路；`offline_self_check` 的 return 0 不属于 live run。

## proof、Popen 与 NOT_REACHED 回归

- `derive_cleanup_proven()` 仍是唯一公式：owned resources absent AND integrity PASS AND secondary empty；生产代码只调用一次。
- cleanup artifact、run summary、request trace、receipt cleanup 与 cleanup check 继续消费同一 `self.cleanup["proven"]`。
- captured PID residual、lingering Popen、wait exception、双 Popen 任一未退出均 fail-closed；terminate/kill 仍只作用于精确 run-owned Popen。
- identity/preflight 零 owned start 的下游保持 NOT_REACHED；已到达失败保持 FAIL；clean terminal 才允许 cleanup PASS。

## 测试与可复现结果

- `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：43/43 PASS，原 42 项全部保留。
- AST parse、`--help`、`--self-check`：全部 exit 0；self-check 明确 `service_started=false`。
- `python3 -B tools/verify_pack.py --schema`：1081/0；不是产品验收。
- `python3 -B tools/verify_governance.py`：38/0；`--self-test`：43/0，均明确 `product_tests_executed=false`。
- Stage payload manifest 9/9、root manifest 全项 SHA-256 通过。
- 四组独立组合 fixture 结果如上，无真实外部动作。

## 候选、receipt、manifest 与 packet 绑定

- 提交链为 `ffd0a67...` → `81a77cc...` → `29069bf...`。候选相对冻结 packet 只修改两个 harness 文件并新增 correction-15 offline receipt；changed_files 3/3 与 diff 一致，diff 无 whitespace error。
- candidate receipt 使用 pending 零值；gate-owner seal 才绑定 candidate/evidence=`81a77cc...`，并更新 packet/control、execution-control、root manifest 与治理校验，没有实现者自签。
- 两个工具独立 SHA-256 为 `4f3b150d261fd0d9f4a03dbe82051518e6208b4dd5f15eebff67ae310847f5d9`、`8fa6e08555f7cc6073a8688234664c1e1f85fa39826fcbe1f81a0433dfde3e38`，与 receipt、candidate Git blob、当前文件及 root manifest 一致。
- packet、baseline harness、sealed candidate/evidence、角色、测试计数及 acceptance binding 均闭合；固定 acceptance hash 仍为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。

## 历史、外部动作与固定分母

- frozen packet、candidate、seal 三个提交中的 correction-10 tree 始终为 `bb899d4ca0818c84293dab00fd1a1ed8f2c464c7`。
- correction-11 receipt/review blobs 为 `8174a6c874832569ed7fb3bf5f0489486514de35` / `7cbc6193339bf5bea515061513a4ada65f314078`；correction-12 为 `4694ee1a095e20bf8f1db63cb3817388e2f5777e` / `1b1a62b02b8986e1438b20a75e5dfb8303e58678`；correction-13 为 `5759f1e65d29315ad0d717d95bdcb96b6a9104f5` / `1fc8907ad35c20e2aa67bd05a73b89f48b78f72e`；correction-14 为 `207ed6256fe4f1a3ea960449cfcd1ac2508154c7` / `cb437a418d04ab119f9ab81d8c62fbcc99c8afa6`。历史均未改写。
- correction-15 receipt 与本次复审的 Comfy/Ollama starts、service probes、network/model calls、真实媒体读取、下载及 target writes 全为 0。
- `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 全部保持 `NOT_RUN`；分母 4、not_run 4，其余为 0。43 个 fixture 与治理/manifest PASS 不是产品 PASS。

## 审查意见与限制

- **假绿判断**：在 correction-15 冻结范围内未发现 cleanup/primary/exit 假绿。
- **WP-S0-43/44 意见**：Fatal/Major/Minor 均为零，可建议 root 关闭本轮离线纠偏并完成 checkpoint；这不是 Stage PASS。
- **S0 状态建议**：回到 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并释放未知 GPU owner。任何真实运行仍需新的明确授权，不得复用过期授权或自动重跑。
