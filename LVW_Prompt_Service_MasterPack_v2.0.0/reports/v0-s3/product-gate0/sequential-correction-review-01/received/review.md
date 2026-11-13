# S3-P4 顺序槽位纠偏隔离独审 01

结论：**CHANGES_REQUIRED；Fatal 0 / Major 3 / Minor 0**。候选 `4e999043d08005829969bf5020048759557ecee9` 相对 `7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0` 修复了正常顺序复用，但尚不满足冻结的失败关闭、幂等关联和固定准入截止要求。不得恢复 fixture；stage_pass_claim=false，product_gate0=false。

本实例未参与实现、未继承作者通过结论、未派生 Agent。已读 root AGENTS、治理 README、parallel-execution、当前 execution-control、执行总纲、冻结 offline contract、fixture-final-03 的 finding/task，以及 audit-correction-review-02 的 root-decision/received review。引用哈希见 root-reference-hashes.json；当前坐标快照单独保存，不以候选的旧控制文件冒充当前状态。

## 一次汇总：位置、触发、预期、实际与复现

| 严重度 | 位置与触发 | 预期与实际 | 复现与证据 |
|---|---|---|---|
| **M1：结算失败仍准入一个新 charge** | executor.py:654、667–668、956–980。仅一个原 handle 已退出，仍有一个空闲槽；finish 抛 CpuGateError、返回 False，或 False 后 charge_state 抛 CpuGateError | 预期：本次 admit 在新 charge 前失败关闭；实际：starts 1→2，返回 ADMITTED。CpuGateError 虽将 uncertain=true，但 `_check_session` 已在协调前执行；False/读 gate 错误连 uncertain 和 settlement_error 都未设置。两槽占满时同样故障返回 CPU_CONCURRENCY_LIMIT、starts 保持2，掩盖了根因。普通 OSError 会传播而拒绝本次 admit，不能把这一分支误报为放行 | negative_probes.py，negative-results.json 的 finish_gate_capacity1、finish_false_capacity1、finish_read_gate_capacity1，与全部 capacity2 对照。10个矩阵案例均实际调用 admit；finalizer 都非零、cleanup=false、保留根，故这不是宣称旧 finalizer M2 全面失守，而是新增 before-next-admission 路径违反相同失败关闭义务 |
| **M2：幂等终态只按名称接受，未关联原始身份，导致假 cleanup** | executor.py:965–968、984、1139–1159。已有同 index 的 settled STOPPED，但持久 exit_code=77、原 handle=0；或持久 pid/birth 属于其它身份；另用返回 foreign index53 的 charge_state 测试分支关联 | 预期：只有原 charge/原 handle/pid/birth/退出码的对应终态才算幂等，冲突保持失败与根。实际：finish 返回False后仅检查 settled 与 STOPPED/TIMED_OUT，即置 settlement_persisted=true；reap 随后只信本地标志跳过核对。补充诊断为新准入 charge 注册并退出第二个原 fake handle，排除未注册 pending 遮蔽：三种冲突均 final exit0、cleanup=true、根删除。foreign-index案例的第0条磁盘 charge 甚至仍 STARTED/settled=false | idempotency_deadline_probes.py；idempotency-deadline-results.json 的 unmasked_wrong_exit / wrong_pid_birth / foreign_index。wrong_exit/pid由真实 SharedCounter.finish 预先持久化冲突；foreign_index是读接口故障注入，不声称正常 SharedCounter 自发返回其它index。UNKNOWN终态对照保持 cleanup=false/exit4/根保留；不能将此对照推广为所有幂等均正确 |
| **M3：新增协调跨截止后不复核准入窗口** | executor.py:654、667–668；协调执行 poll、finish、charge_state 的同步I/O | 预期：新增协调完成时若已跨固定 admission_deadline，拒绝新 charge；实际：模拟 finish 的有限I/O延迟令单调时钟推进到原 deadline+0.001，本次返回 ADMITTED、starts1→2；紧接下一次才 SESSION_ADMISSION_WINDOW_CLOSED。截止值未重设，然而本次入场已越界 | idempotency_deadline_probes.py 的 reconciliation_crosses_deadline；idempotency-deadline-results.json 含实际 clock/deadline/starts。只注入 clock 与 finish延迟效果，不真实等待、不改限额/共享预算。此项是新增协调插在检查与charge之间造成的边界缺口，不借此重开未改动的旧截止实现 |

F0 的限定依据：未见生产源码/公共合同/24分母/阈值或原预算被改写；真实进程/网络路径受外层 pre-import 守卫阻断，实际 runner handles/fixture starts 均0，原 counter字节不变。发现的三个有复现的局部门禁缺陷按 Major 记录；不把零真实运行推导成产品安全/质量通过。m0 表示本轮没有另外独立的 Minor，作者新增测试对失败语义的错误期待已归入M1，不重复计数。

M2补充的 local_marker_disk_divergence 在 synthetic 文件里明确制造“本地已成功、磁盘随后恢复STARTED”的分歧，finalizer同样可假cleanup；其前提是证据发生分歧，**不是正常路径自行丢失持久化的证明**，只支持“本地标记不能独自替代持久证明”的要求，不另计发现。其它session的完整运行未执行；foreign_index / foreign birth证实分支不校验关联，未把合成数据冒称另一真实session。

## 正常路径与失败矩阵的实证

正常两live拒绝第三；仅一个退出后恰好准入一个，再次拒绝；未知退出仍占原槽。独立 sequential13 通过真实 admit/register 驱动，累计starts=13、13条原charge、峰值1≤2；原句柄退出后只在下一admit的协调结算，末尾才一次最终清理，无逐case全局reap/revoke/watchdog停机、无新阈值、无删除charges/退款。第一个 charge 的 finished_wall 在最终清理前后不变；保留reserved60且spent按session一次记录。它证明正常顺序累计行为，不证明13真实fixture。

诊断的 synthetic-normal-watchdog 版本使用原 `_ensure_watchdog`，没有替换/停用看护。初版为隔离同步分支曾将 `_ensure_watchdog` stub为空，初版脚本、日志、结果另存 initial-* 和 synthetic/，不能用其正常路径结果证明看护保持；发现该证据局限后，移除stub、用全新本目录诊断根重新跑必要独立矩阵及补充探针。当前 negative*.log / idempotency-deadline*.log 和 synthetic-normal-watchdog/ 是正式诊断证据；focused15与guard4从始至终只各执行一次。所有初版工件保留，不覆盖历史失败。

矩阵的真实结果（每种分别测1/2个已退出原handle）：

| 故障 | 一个已退出+一个空槽 | 两个已退出占满 | 最终证据/根 |
|---|---|---|---|
| finish CpuGateError | **ADMITTED，starts+1，uncertain=true** | CONCURRENCY_LIMIT，starts不变 | cleanup=false，非零，根保留 |
| finish False | **ADMITTED，starts+1，uncertain=false** | CONCURRENCY_LIMIT，starts不变 | cleanup=false，非零，根保留 |
| finish OSError | OSError传播，starts不变 | OSError传播，starts不变 | REAP_FAILED:OSError，根保留 |
| finish False + charge_state CpuGateError | **ADMITTED，starts+1，uncertain=false** | CONCURRENCY_LIMIT，starts不变 | cleanup=false，非零，根保留 |
| finish False + charge_state OSError | OSError传播，starts不变 | OSError传播，starts不变 | REAP_FAILED:OSError，根保留 |

原handle未证退出不被正常协调释放；UNKNOWN不被当作幂等成功；无重复finished_wall/退款证据。异常矩阵的普通错误仍在raw日志及final failure_reasons，owned根保留。M1既不增加max_concurrent也不释放失败的原槽，却错误使用另一个空槽；其严重性不能仅靠occupied仍≤2否认。

## 源码与旧边界复核

审查了 executor 全部新增/变更段：SharedCounter.charge_state（只按index读，且没有budget_id验证）、admit中的协调插点、custody的新标志、整段reconcile和reap幂等分支；同时审查真实charge/finish/session检查、spawn/credential/custody/watchdog/stop/finalizer调用链及测试新增224行，未仅看新增测试名字。

候选测试追加7个函数而不是只增加6个名称，其中 `test_a_settlement_that_the_counter_refuses_keeps_its_concurrency_slot` 明确先让失败后的下一admit成功，再以满槽的后一次拒绝收尾；它只证明槽位未释放，不能作为失败关闭的Oracle。这解释了focused15通过与M1并存。其余正常顺序、live、unknown、finalizer、源/窗口/owner测试有相应实际断言；没有削弱旧断言或质量阈值。

run_guarded_checks.py相对基准字节未变。guard4实际日志来自候选 OfflineBoundaryViolation，分别阻止connect/bind/Popen/system；生产runner确认单owner和安装握手。focused选择包含真实guard refusal相关测试；审查的nonce/thread/executor/charge一次性消费代码未改。外层bootstrap在任意候选import前已安装，候选hook安装后保留独立fallback；只有已审测试文件中的显式synthetic audit事件可放行，实际subprocess内部调用帧不在白名单，真实进程/网络仍被拒绝。独审守卫不回答候选安装握手。

原四项关闭依据保留。原M1凭据/M3安装/m1实际命令无本轮真实回归证据，不自动重开；原M2的最终失败保根行为在普通错误矩阵继续成立，但新增协调有M1、幂等有M2，不能因旧四项关闭而豁免。原per-child 10s、termination margin/stop次数、session60、pool180及cleanup30的数值/最早截止算法均未改；固定24和角色16/8保持。M3说明新增工作仍需在实际准入前复核旧边界，不能仅验证deadline数值没变。

作者的基准反证不执行：只读复算 baseline-7ed2116.executor.py与git原blob完全一致（baseline-readonly-check.json）；基准admit不逐child结算、reap才finish的逻辑支持原起因。作者6failed及通过总结不是本报告结论来源。

## 实际执行、退出、skip与限制

完整argv/cwd/时间/真实外层returncode和stdout/stderr哈希分别在 focused.outer.json、guard.outer.json、negative.outer.json、idempotency-deadline.outer.json；原始流完整保留。可复现的父调度命令（相对包根）：

```sh
python3 -B reports/v0-s3/product-gate0/independent-sequential-correction-01/run_once.py
python3 -B reports/v0-s3/product-gate0/independent-sequential-correction-01/run_diagnostics.py
```

run_once.py具体仅启动：launch.py --mode focused --label independent-sequential-focused --outdir <本目录绝对路径> --modules tools/test_v0_s3_supervisor.py --select "slot or reconciliation or sequential or finalizer"；随后launch.py --mode guard --label independent-sequential-guard --outdir <同目录>。launch以runpy执行未修改runner的__main__，无binding参数。run_diagnostics.py依次执行negative_probes.py、idempotency_deadline_probes.py，各自候选导入前装外层守卫；诊断只构造本报告目录内synthetic counter/binding和fakehandles，不执行带binding runner。

| 项目 | 结果 | 真外层退出 | skip/限制 |
|---|---|---|---|
| 唯一focused | 15 passed，92 deselected | 0 | 0 skipped；92项不计PASS |
| 唯一guard | 4/4候选拒绝，hook_install_count=1 | 0 | 无fixture启动 |
| 正式独立矩阵 | 18个观测案例完整保存，断言证据捕获成功 | 0 | **退出0表示诊断完成，包含已复现缺陷，不是候选通过** |
| 正式补充矩阵 | 4个不受pending遮蔽的幂等对照+1个截止反例 | 0 | 同上；只有fake handles/合成故障 |

没有机械复跑49/57/100/71/257或基准整套。没有原ledger、服务、模型、GPU或网络动作。真实13fixture、全I01–I24集成、Windows服务/后代/GPU/A06、原生QualityPhase组合、产品十二项质量与必要人签仍 **NOTPROVEN**。无Stage PASS。

## 候选与原预算

候选源码SHA256（均匹配git候选blob，candidate-source-hashes.json）：

- executor.py：`5cf65a5ebc119bfc79c8a9ceb4dd5f28967010ca82642996273a3f63abed03f5`
- run_guarded_checks.py：`da688b1502dcf625bbbf883c5e7e519d0c4c386a51fafa15539a69e2331d1005`
- tools/test_v0_s3_supervisor.py：`e58585c03edb512b4b8285b48e917c5b23b0218b5986038cca47a0ac86d6dd3d`

原counter只以Path.read_bytes读取并复制快照，未用候选SharedCounter打开它、未写/退款/重置/消费最后60秒。前后SHA256均为 `39f2838e02c33b3903e4c9b23316242abe9e75e4e3592127238a88fa627bbe15`，字节一致；inactive，starts2，reserved120，spent2.896，原2charge=REFUSED_BEFORE_FORK，2session=SETTLED。root单独历史裁决文件hash与counter引用一致；原历史失败/原始spent保持，不把新分类当成补运行。

起始worktree status为空、HEAD=da25380a95b11fdbd6a1dd6a6e532ce1fce110b2，已在checkout前写worktree-before.txt，随后按授权checkout --detach候选，无fetch/reset/clean。初始状态文件一开始放在仓库顶层reports，发现实际包为子目录后移入本目录，顶层空目录已移除；最终所有新增工件只在本独审目录。root和实现worktree、公共合同、控制、MANIFEST均未写。

## 十字段交接与完整路线

完整V0–V3大纲（完成/列明子项）：V0-S0 1/2，V0-S1 5/5，R0 1/2，R1a 5/5，V0-S2 7/8，V0-S3 0/6，R1 0/4，V1-M1 0/3，R2 0/4，R3 0/4，R4 0/4，R5a 0/4，R5b 0/4，R5c 0/4。S0历史NO_GO，S1/R1a仅已签子集，S2为7/8未签；V2/V3未激活。本轮实现/机器产品验收/独审/人签分别为：只读候选审查 / 未新增产品验收 / CHANGES_REQUIRED F0M3m0 / 未签。

1. 当前坐标：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING。
2. 本批完成：隔离顺序纠偏独审，focused15一次、guard4一次、独立故障矩阵，F0M3m0。
3. 最后通过门禁：621b1bf统一切片UM10及范围内人签，非本候选Stage。
4. 当前阻塞：本报告M1/M2/M3；真实13fixture与全24/产品门禁仍NOTPROVEN。
5. 全局路线位置：见上述唯一control完整大纲，未修改完成度。
6. 剩余工作：root裁决并退回实现纠正三个缺口；独立新候选复验后才能考虑新绑定。
7. 下一责任人：root；本实例不改实现、不恢复fixture。
8. 所需授权：本轮只读/零进程授权已足够，无新人批问题；后续实执行由root另绑有限门禁。
9. 证据目录：reports/v0-s3/product-gate0/independent-sequential-correction-01/；evidence-hashes.json绑定全部报告/脚本/日志/诊断原件。
10. 精确停止原因：本次审查交付完成且发现3 Major，等待root归档回收；无StagePASS。

未派生/回收其它Agent，回收数0；未独立盘点全项目窗口，不能猜当前各空间存活数。本窗口worker_done确认后由root及时归档回收，默认不keep-open。
