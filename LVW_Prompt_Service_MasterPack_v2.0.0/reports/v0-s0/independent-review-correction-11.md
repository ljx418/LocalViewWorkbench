# V0-S0 / WP-S0-33 correction-11 独立离线复审

审查日期：2026-10-28（Asia/Shanghai）
审查角色：`codex_isolated_reviewer`
冻结 packet：`75ec3865b55dda0abf8ec888ecdabbf639daac79`
候选实现：`b8a08e06e60df6c1c9a156e1dab0b55d483fded7`
gate-owner seal/checkpoint：`94fabe4bb04af48322d5dcea2070f035c1d75c18`

审查方式：离线独立复算；未启动或探测 ComfyUI/Ollama，未访问网络或真实媒体，未修改候选、manifest、坐标或历史 evidence。

## 结论

Fatal **0** / Major **1** / Minor **0**

WP-S0-31 的主要状态映射已实现：identity mismatch、GPU preflight stop、owner/listener 枚举异常在零 owned service start 时把未执行的下游检查标成 `NOT_REACHED`；已经到达的失败仍为 `FAIL`；`cleanup.proven`、`owned_resources_absent` 与 `target_integrity_comparison` 也已拆字段。候选还正确把“`Popen` 已返回但 wrapper/listener PID 尚未捕获”计为一次 service start。

但是，独立 fixture 复现了同一 Popen/PID 边界的清理假绿：若已返回的 owned `Popen` 在 finally 的 `wait(timeout=5)` 后仍存活，而 wrapper/listener PID 仍为空，超时会被静默忽略；只要端口、temp 与 target hash 表面正常，收据仍可写 `owned_resources_absent=true`、`cleanup.proven=true`、cleanup check=`PASS`。因此 WP-S0-31/32 **不建议 READY_FOR_REVIEW 出口通过**，不能据此返回下一次真实运行门禁。Stage 不得 PASS；root 仍保留裁决权。

## Finding

### M-01 — Major — Popen 存活但 PID 未捕获时清理可假绿

- **位置**：`tools/v0_s0_live_probe.py:670-673,703-706,971-978,1023-1032,1081-1084,1159-1166`；`tools/test_v0_s0_live_probe.py:318-338`。
- **触发**：owned PowerShell wrapper 的 `subprocess.Popen` 已成功返回，随后 PID 文件/监听 PID 捕获或 no-cloud readiness 失败；finally 中该 `Popen.wait(timeout=5)` 超时，且授权端口尚未监听。
- **预期**：Popen 返回即算 service start；在 `poll()`/wait 不能证明进程终止时，owned resource absence 必须为 false，cleanup 必须 fail-closed，且 reached cleanup check 必须为 `FAIL`。成功清理必须同时证明所有已创建的 owned Popen 已退出，不能只证明捕获到的 PID、端口和 temp 不存在。
- **实际**：service start 计数已从 PID 改为 `self.ollama_proc/self.comfy_proc`，这一点正确；但 finally 对两个 `proc.wait(timeout=5)` 的所有异常直接 `pass`，没有把超时加入 `secondary_cleanup_failures`，也没有把 `proc.poll() is None` 纳入 `owned_resources_absent` 或 `summary.cleanup_proven`。`observable_check_statuses` 随后会把这个已到达的 cleanup 写成 `PASS`。
- **独立证据**：纯离线 mock fixture 令 `start_services()` 设置一个 `poll() is None`、`wait()` 抛 `TimeoutExpired` 的 `ollama_proc`，然后模拟 reached no-cloud failure；final listeners 为空、pre/post integrity 相等、temp 不存在。实际输出为 `process_starts=1`、`mock_proc_still_running=true`，同时 `owned_resources_absent=true`、`cleanup.proven=true`、`target_integrity_comparison=PASS`、`cleanup_check=PASS`，进程返回码仍未出现。fixture 返回总体 rc=2/NO_GO，但清理子结论是假绿，未来可污染下一次运行。
- **复现**：在 pack 根目录导入 `tools.v0_s0_live_probe`，以临时目录构造 `Probe`；mock identity/preflight 为 PASS、target integrity 前后均 `[]`、listeners 始终 `[]`；让 `start_services` 赋值上述 lingering proc 后抛 `OLLAMA_NO_CLOUD_TRUE_NOT_OBSERVED_IN_SERVER_RAW`，执行 `run()` 并读取临时 receipt。该复现只使用 mock 与临时文件，不启动服务、不访问网络或媒体。
- **建议**：把每个已赋值的 Popen 当作 owned resource 直到明确 `poll() is not None`；将 wait timeout/异常记录为稳定的 secondary cleanup failure，并把 Popen 存活状态纳入 `owned_resources_absent` 与 `cleanup.proven`。新增集成负例断言 start=1、proc alive 时 absence/proven/PASS 均不可为真，同时保留真正退出后的成功 cleanup PASS 分支。

## 分支语义独立复算

- `reached_checks` 在 identity、service preflight、no-cloud、remote TCP、path conversion、image/video route 的实际入口处设置；`observable_check_statuses()` 对未进入的分支返回 `NOT_REACHED`，对已进入的分支按实际布尔值返回 PASS/FAIL。
- identity mismatch fixture：identity=`FAIL`，其余全部 `NOT_REACHED`，service starts=0，cleanup proven=false、owned absent=true、target comparison=`NOT_REACHED`。
- GPU >4096 MiB fixture：identity=`PASS`、preflight=`FAIL`，后续与 cleanup=`NOT_REACHED`，start_services 未调用。
- enumeration exception fixture：preflight=`FAIL`，下游=`NOT_REACHED`；若最终 listener/integrity 枚举自身失败，cleanup 正确升级为 reached `FAIL`，不会掩盖首因。
- reached no-cloud failure 的纯状态测试保持 no-cloud=`FAIL`、remote=`NOT_REACHED`、cleanup=`FAIL`；完整运行代码对 no-cloud/remote/path/route 的 reached 标记也在调用前设置。
- success cleanup 的映射测试在所有 checks reached、cleanup proven、owned absent、target comparison PASS 时全部 PASS；但 M-01 说明当前“proven/absent”的计算缺少 Popen 退出条件，所以完整成功证明尚未闭合。
- Popen start 计数本身已修正：receipt 的 Ollama/Comfy starts 分别由 `self.ollama_proc is not None` / `self.comfy_proc is not None` 计算，不再等待 wrapper/listener PID。

## 测试与可复现结果

- `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：33/33 PASS；实现收据所述“原 30 项 + 3 项”一致。
- AST parse、`--help`、`--self-check`：全部 exit 0；self-check 明确 `service_started=false`。
- `python3 -B tools/verify_pack.py --schema`：1073 passed / 0 failed；这是文档/合同校验，不是产品验收。
- `python3 -B tools/verify_governance.py`：38/0；`--self-test`：43/0；均明确 `product_tests_executed=false`。
- Stage payload manifest：9/9 SHA-256 通过；root manifest 全项通过。
- 独立 lingering-Popen fixture：稳定复现 M-01，输出见 finding；没有真实外部动作。

## 候选、receipt、manifest 与 packet 绑定

- 提交链为 `75ec386...` → `b8a08e0...` → `94fabe4...`。候选相对冻结 packet 仅改 `tools/v0_s0_live_probe.py`、`tools/test_v0_s0_live_probe.py` 并新增 correction-11 offline receipt；候选 diff 无 whitespace error。
- seal commit 将 receipt 的 candidate/evidence 从 pending 零值绑定为 `b8a08e0...`，并由 gate owner 更新 packet coordinate/control、execution-control、root manifest 与治理校验；没有把 seal 改写成实现者自签。
- 候选两工具的独立 SHA-256 分别为 `46066be5c08892b73113b9557dc72ef57b8dab459579e540989e0a9122370248`、`85712b09586d80b0988c1dc9cb97455d41f10110be5d07adf237fe1498456983`，与 receipt `artifact_sha256`、候选 Git blob 当前字节及 root manifest 一致。
- correction-11 receipt 的 `changed_files` 精确列出候选的 3 个路径；packet commit、baseline harness、candidate/evidence、acceptance hash 和角色字段均闭合。固定 acceptance hash 独立复算为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。

## 历史、外部动作与固定分母

- 从冻结 packet `75ec386...` 到候选、再到 seal，correction-10 目录 tree object 始终为 `bb899d4ca0818c84293dab00fd1a1ed8f2c464c7`；correction-10 live receipt blob 始终为 `9c2d7d8bbad8f653189d132e686c0eac78987547`，其独立复审 blob 始终为 `cdbb541f4cc41cc90b34800403af1d72a4f0f189`。历史字节未被改写，原 Minor 1 仍作为历史事实保留。
- correction-11 是纯离线 workpack：收据记录 Comfy/Ollama starts、service probes、network/model calls、真实媒体读取、下载、target writes 全部为 0；本次独立复审同样没有这些动作。
- `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 仍全部 `NOT_RUN`，分母 4、not_run 4、pass/fail/blocked/skipped 皆 0；不得把 33 个 fixture 或 manifest/governance PASS 记为产品 PASS。

## 审查意见与限制

- **假绿判断**：存在，范围为 M-01 的 owned cleanup 子结论；不表示本离线 workpack 启动了服务，也不改写 correction-10 的真实 NO_GO。
- **WP-S0-31/32 意见**：当前候选不应通过 READY_FOR_REVIEW checkpoint。修复并独立覆盖 lingering Popen 后，才可重新判断是否关闭 correction-10 Minor 1。
- **S0 状态建议**：不得 Stage PASS、不得推断 live 授权。即使 M-01 修复完成，运行门禁仍应回到既有 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并释放未知 GPU owner；任何新鲜真实运行仍需 root 另行签发新授权。
