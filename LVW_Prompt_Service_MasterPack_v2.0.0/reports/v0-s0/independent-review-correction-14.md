# V0-S0 / WP-S0-42 correction-14 独立离线复审

审查日期：2026-10-28（Asia/Shanghai）
审查角色：`codex_isolated_reviewer`
冻结 packet：`b1a4a19542b6448057f4f079c55ff52c37c6941c`
候选实现：`c654f8e01bd059aa41a539c6aa8ac4f86f701320`
gate-owner seal/checkpoint：`b597caf7d962cabb1cc429146f9644635da23891`

审查方式：离线独立复算、最终出口静态搜索及临时目录完整 mock fixture；未启动或探测 ComfyUI/Ollama，未访问网络或真实媒体，未修改候选、manifest、坐标或历史 evidence。

## 结论

Fatal **0** / Major **1** / Minor **0**

correction-14 已关闭前次“proof=false 仍 READY/rc0/complete”的直接绕过：功能成功但 cleanup proof=false 会得到 NO_GO、rc=2 和非 complete；功能成功且 proof=true 才得到 READY、rc=0 和 complete。summary、receipt、production status 与 return 也都读取 finally 后的最终 decision。

但“已有 primary stop reason 不得被 cleanup 覆盖”只对异常路径成立。public route、GPU/resource 或 remote stop 等正常控制流失败会先设置 NO_GO/exact reason，却不会给局部变量 `primary_stop_reason` 赋值；若随后 cleanup proof=false，候选会用 cleanup reason 覆盖原功能首因，且不追加要求的 secondary cleanup event。因此本轮仍不能建议关闭离线纠偏。

## Finding

### M-01 — Major — 非异常功能首因会被后续 cleanup failure 覆盖

- **位置**：`tools/v0_s0_live_probe.py:997-1024,1115-1120`；`tools/test_v0_s0_live_probe.py:434-477` 只覆盖“功能全绿”两分支，既有首因保留测试只覆盖 preflight exception。
- **触发**：public image/video route、resource stop、remote stop 或 semantic Oracle 通过正常控制流先设置 `decision=NO_GO` 与精确 stop reason；finally 又得到 `self.cleanup["proven"]=false`。
- **预期**：原功能/资源首因保持不变；cleanup failure 作为 `secondary_cleanup_failure` 事件追加。最终仍为 NO_GO/rc2/non-complete，但不得用清理结果覆盖较早首因。
- **实际**：`primary_stop_reason` 初始为 None，仅在 `except` 中赋值。正常控制流设置 NO_GO 时它仍为 None，所以 proof=false 分支进入 `else`，把 `exact_stop_reason` 改成 `CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN`，也不会追加同名 secondary event。
- **独立证据**：完整临时 `Probe.run()` fixture 先让 image attempt 失败，原应得到 `PUBLIC_COMFY_ROUTE_FAILED_WITHIN_ATTEMPT_BUDGET`；再让 captured wrapper PID stop-after 非空，使 cleanup proof=false。实际输出为 decision=NO_GO、rc=2，但 exact reason=`CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN`、secondary cleanup event=false，image attempts=1/video=0。首因已丢失。
- **复现**：在 pack 根目录导入 `tools.v0_s0_live_probe`；临时 Probe 令 identity/preflight/service gates 到达并通过，image attempt 返回 false；令 Popen 退出但 captured PID stop-after 非空，其他终态干净，request cleanup correlation 为 true。执行 `run()` 并读取 receipt/events。全程不启动服务、不访问网络或媒体。
- **建议**：不要用“是否经过 except”定义首因。cleanup proof 形成前若当前 decision 已不是初始/READY，或 exact reason 已是明确的先行失败，应保留它并追加 secondary cleanup event；只有功能路径原为 READY 且无先行失败时，cleanup false 才成为新的主因。新增 route failure + cleanup failure、resource stop + cleanup failure 的完整 run 负例。

## 最终出口与旁路搜索

- 功能成功 + captured PID residual：proof=false、cleanup check=FAIL、decision=NO_GO、exact cleanup reason、rc=2、production status=`PARTIAL_OR_FAILED_PUBLIC_COMFY_TRACE`。
- 功能成功 + clean stop-after/Popen/listener/temp/integrity/secondary：proof=true、cleanup PASS、decision=READY_FOR_REVIEW、rc=0、production status complete。
- summary 和 receipt 在 proof 绑定之后读取 `self.decision/self.exact_stop_reason`；production status 也在最终 decision 后计算；run 唯一成功 return 是 `decision == READY_FOR_REVIEW`。静态搜索没有发现 proof=false 可直接返回 0/READY 的其他 live 出口；`offline_self_check` 的固定 return 0 不是 live run。
- M-01 不会制造 READY/rc0，但会破坏冻结的首因保留与失败可诊断性。

## cleanup authority 与历史回归

- `derive_cleanup_proven()` 仍是唯一公式：resources absent AND integrity PASS AND secondary empty；生产代码只调用一次。
- cleanup artifact、run summary、request trace、receipt cleanup 与 cleanup check 继续直读 `self.cleanup["proven"]`，无平行 proof 计算。
- captured PID residual、lingering Popen、wait exception、双 Popen 组合仍 fail-closed；clean terminal 才 PASS。
- identity/preflight 零启动后的下游 NOT_REACHED、reached failure=FAIL、Popen start 计数与精确 owned terminate/kill 均无回归。
- exception 首因路径仍正确：preflight exception 后 cleanup failure 不覆盖 `WINDOWS_OWNER_ENUMERATION_FAILED`，并追加 cleanup secondary event；缺口仅在非异常首因路径。

## 测试与可复现结果

- `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：42/42 PASS，原 40 项全部保留。
- AST parse、`--help`、`--self-check`：全部 exit 0；self-check 明确 `service_started=false`。
- `python3 -B tools/verify_pack.py --schema`：1079/0；不是产品验收。
- `python3 -B tools/verify_governance.py`：38/0；`--self-test`：43/0，均明确 `product_tests_executed=false`。
- Stage payload manifest 9/9、root manifest 全项 SHA-256 通过。
- 独立“route 首因 + cleanup failure”fixture 稳定复现 M-01；无真实外部动作。

## 候选、receipt、manifest 与 packet 绑定

- 提交链为 `b1a4a19...` → `c654f8e...` → `b597caf...`。候选相对冻结 packet 只修改两个 harness 文件并新增 correction-14 offline receipt；changed_files 3/3 与 diff 一致，diff 无 whitespace error。
- candidate receipt 使用 pending 零值；gate-owner seal 才绑定 candidate/evidence=`c654f8e...`，并更新 packet/control、execution-control、root manifest 与治理校验，没有实现者自签。
- 两个工具独立 SHA-256 为 `158c8da7e828e16ca63162c010489dba3dd06226d47522f68ea85c1ab8592306`、`c63b802a570b4c9328acd37e342e26bd5b8d7ee23345314c8e8a2258cff650c3`，与 receipt、candidate Git blob、当前文件及 root manifest 一致。
- packet、baseline harness、sealed candidate/evidence、角色、测试计数和 acceptance binding 均闭合；固定 acceptance hash 仍为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。

## 历史、外部动作与固定分母

- frozen packet、candidate、seal 三个提交中的 correction-10 tree 始终为 `bb899d4ca0818c84293dab00fd1a1ed8f2c464c7`。
- correction-11 receipt/review blobs 为 `8174a6c874832569ed7fb3bf5f0489486514de35` / `7cbc6193339bf5bea515061513a4ada65f314078`；correction-12 为 `4694ee1a095e20bf8f1db63cb3817388e2f5777e` / `1b1a62b02b8986e1438b20a75e5dfb8303e58678`；correction-13 为 `5759f1e65d29315ad0d717d95bdcb96b6a9104f5` / `1fc8907ad35c20e2aa67bd05a73b89f48b78f72e`。历史均未改写。
- correction-14 receipt 与本次复审的 Comfy/Ollama starts、service probes、network/model calls、真实媒体读取、下载及 target writes 全为 0。
- `V0-A01`、`V0-A02`、`V0-A09`、`V0-A10` 全部保持 `NOT_RUN`；分母 4、not_run 4，其余为 0。42 个 fixture 与治理/manifest PASS 不是产品 PASS。

## 审查意见与限制

- **假绿判断**：未再发现 proof=false 返回 READY/rc0/complete；但 M-01 会改写真实首因，属于失败证据语义失真。
- **WP-S0-40/41 意见**：不建议通过 READY_FOR_REVIEW checkpoint；补齐所有非异常首因 + cleanup failure 的保留逻辑与负例后再复审。
- **S0 状态建议**：不得 Stage PASS、不得推断 live 授权。即使离线 Major 清零，也只能返回 `BLOCKED / RESOURCE_BUSY_UNKNOWN_GPU_OWNER`，由 project_owner 识别并释放未知 GPU owner；真实运行仍需新授权。
