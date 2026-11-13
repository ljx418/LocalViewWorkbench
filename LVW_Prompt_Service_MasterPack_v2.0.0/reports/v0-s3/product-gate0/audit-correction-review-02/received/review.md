# S3-P4 纠偏独立复验 02

完整路线（root 当前 execution-control 的 completed/total，未因本轮增加）：V0-S0 1/2，V0-S1 5/5，R0 1/2，R1a 5/5，V0-S2 7/8，V0-S3 0/6，R1 0/4，V1-M1 0/3，R2 0/4，R3 0/4，R4 0/4，R5a 0/4，R5b 0/4，R5c 0/4。S0历史NO_GO保留；R0/R1a仅已签子集；V2/V3未激活。当前为 R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING。

结论：候选 `7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0` 相对 `74ff021934afef661f8c7e8c1c4f11b26f7c3360` 的原 **3 Major + 1 Minor 四项纠偏均已复验关闭**；本轮允许的故障模型内 **Fatal 0 / Major 0 / Minor 0**。这是守卫与失败记账的限定独审结论，不是 Stage PASS，不开放 fixture，不改历史 PENDING。

## 独立性、范围和执行边界

本实例未参与实现，未派生其他 Agent。依据 root AGENTS、治理 README/parallel-execution、当前控制、执行总纲、冻结 offline contract、`audit-correction-review-01/root-decision.json` 和 `received/review.md`、原 `negative_probes.py` 与原始 stdout/stderr/receipt/history 复验；引用原件 SHA256 在 `root-reference-hashes.json`。未执行或以作者 `CONVERTED_ORACLES_OK`、作者汇总作为结论；独立诊断由本实例编写。

初始 git status 为空，HEAD 为 `516f430ba4fca9722c6bbb9d0982e671fbb93408`，随后仅在现有 review 工作区 detach 到候选，无 fetch、reset、clean 或源改动。流程偏差如实记录：初始状态先由工具原始输出保存，尝试写磁盘时误用不存在的 `python`，shell 后续仍完成 checkout；因此 `initial-state.json` 是紧接 checkout 后依据已保存原始输出落盘，不能声称它在 checkout 前已写成文件。未影响候选或原工件。

所有新增文件都在本目录，保留 synthetic 诊断根/计数/绑定供检查，不删除已有工件。候选源、合同、门限、I01–I24 分母、全局 MANIFEST、坐标及原共享 counter 均未修改。针对三份源码检查了实际 diff 和调用链：`implementation-integration-01/executor.py`、同目录 `run_guarded_checks.py`、`tools/test_v0_s3_supervisor.py`。其它生产 coordinator/QualityPhase/worker/S2 runtime/supervisor/fixture 未发生该 diff 的变化；作者新增诊断文件不是本轮执行入口，也未执行。

外层 `outer_boundary.py` 在任何候选 import 前注册 bootstrap 硬守卫；候选注册后，在候选 hook 后追加独立 fallback，再用独立无副作用握手证明 fallback 已在场。bootstrap 在 fallback 未就位时禁止进程/网络事件；fallback 对真实 subprocess 内部、fork/exec/spawn/system 与网络动作继续拒绝，仅允许已检查的测试/诊断文件内显式 `sys.audit` 的 Popen/posix_spawn 合成事件通过。实际 Popen 的调用帧位于 subprocess.py，会被 fallback 拦截；这不是给 fixture argv 放行。guard4 日志记录的是候选 hook 的 `offline boundary violation`，未把外层拒绝冒充候选正例。两个独立守卫均不回答候选 handshake。

`launch.py` 以 runpy 执行未修改生产 runner 的 `__main__`，确保其 main/install/pytest 顺序真实，同时获得 pre-import 外层边界。未向 runner 提供任何 binding。synthetic 诊断仅用测试 helper 创建本目录内虚拟 counter/binding、stub Popen/handle，绝不启动 fixture；不是原机器 binding runner。系统审查 Python/进程外采集命令不计为 fixture 子进程。

## 原四项逐项判断

| 原项 | 位置与触发 | 预期及本轮实际 | 状态、证据 |
|---|---|---|---|
| M1 当前拒绝来源、绑定和一次性 | executor.py:137、665、685、713、750；runner.py:499。原普通 RuntimeError+marker+同模块 CpuGateError、旧合成外层类型，以及旧真实 guard 拒绝/整份凭据复制重放 | 原 copied-marker、错误 nested type、旧外层均 UNKNOWN、occupied=1、open，非零且留根。真实 hook 通过 Popen audit 准入后，在 posix_spawn audit 生成当前凭据，匹配 executor ID、charge index、thread ID、action nonce 后才消费；正例确实 REFUSED_BEFORE_FORK。复制已消费整份旧凭据保持 UNKNOWN；在真实 hook 拒绝尚未 unwind 时复制的**未消费**整份凭据，包装为普通外层后在下一 action 重放，也保持 UNKNOWN；跨 executor 的旧真实错误不能释放新 charge | CLOSED；focused 的 real_guard_refusal/copied_marker/replayed_real_guard，加 `negative-probes.stdout.log` 中 copied_marker_gate、old_synthetic_outer、copied_entire_old_credential、unconsumed_copy_next_action、cross_executor_old_real |
| M2 finish 失败不得假终态/cleanup | executor.py:750–825、951–1110；runner.py:234–394。finish 返回 false、CpuGateError 或 OSError；无句柄真实 guard 拒绝/普通 start 异常，以及取得 stub handle 后 | 9种组合全部 counter 仍 PENDING（无句柄）或 STARTED（有句柄），admitted=1、occupied=1、open 非空，finalizer 非零并保留 owned root，cleanup=false。真实拒绝凭据已消费且 finish 失败的组合也成立，不会把本地 REFUSED 字段盖过 counter PENDING。普通 I/O 抛错可保留本地 ADMITTED/HANDLE；这同样是 open 而非假终态。reap 对持久化失败为 UNKNOWN/proof persisted=false 或显式 REAP_FAILED，finalizer 不删除根 | CLOSED；focused settlement_failed/proof_of_a_child；独立矩阵 genuine_refusal_*、ordinary_failure_*、handle_*；synthetic 原 counter 文件原样保留 |
| M3 安装证明与 failclosed | runner.py:499、558、580、601、832–880。显式 API 异常、真实 CPython 已有策略抛 RuntimeError 导致静默拒绝、已有旧 hook/alias | 正常安装与 alias 幂等 count=1、握手增加。新 registry 注册失败不能由旧 registry 的真实 hook 或 alias 应答；新 handshake=0、installed=false、count=0；main 返回5，重试不假成功。额外用**全新解释器**执行 install_before_import_probe，显式及静默失败前后 pytest/_pytest/tools/executor 模块列表均为空，main 未进入测试或候选导入 | CLOSED；focused guard_installation；`early-install.stdout.log`、原始 stderr、early-*.receipt.json、early-install.outer.json；不只依赖已导入 pytest 的单元测试 |
| m1 完整有效命令与原调用 | runner.py:400、456、959–990。modules/select/binding/hash/role/candidate；orig_argv 不存在或程序调用 main | 本次真实 focused receipt.command 完整保留 modules/select；无 binding 未虚构 binding。独立构造全部参数的 effective command 保留 binding/hash/role/candidate（只构造，未执行）。本次真实 orig_argv 是 launch.py，因此诚实报告 programmatic，outer_matches_effective=false，argv 是实际送给 runner 的参数。UNKNOWN 无 orig_argv 与匹配 process 语义另经纯数据分支检查；没有把其当直接进程启动实测 | CLOSED；focused complete_effective_command、两份真实 receipt 与 outer.json，negative-probes.stdout.log 的 invocation |

原负例没有被弱化为只检 marker+ValueError；最初 marker+真实 CpuGateError、同外层类、counter 持久化故障和真正 CPython 静默拒绝条件都保留。M1 正例异常由生产 hook 自己发出，不靠手工造 violation 自证。未将修改 executor 内存、重写 action nonce、修改 registry/installed hook 内部数据的任意恶意进程内存攻击提升为本轮新增威胁；凭据绑定是本轮正常链路/异常复制重放的防护，不宣称进程内密码学隔离。

M2 不把 proof.proven（已观察 handle 退出）与 persisted（counter 写成终态）混用；两者分别记录，cleanup 要求持久化成功。重复 reap 对已经 settled 的 charge 可能保守失败；未因此误报 cleanup=true 或减少计数。本轮未验证真实 child 清理。

## 实际命令、结果和未执行项

指定两次生产 runner 检查各只执行一次，外层无管道、未掩盖退出；执行脚本 `run_once.py` 保存 subprocess.run 的真实 returncode 与原始 stdout/stderr。相对于包根，实际外层为：

```sh
python3 -B reports/v0-s3/product-gate0/independent-audit-correction-02/launch.py --mode focused --label independent-audit02-focused --outdir reports/v0-s3/product-gate0/independent-audit-correction-02 --modules tools/test_v0_s3_supervisor.py --select "refused_start or machine_accounting or real_guard_refusal or copied_marker or replayed_real_guard or settlement_failed or proof_of_a_child or guard_installation or complete_effective_command"
python3 -B reports/v0-s3/product-gate0/independent-audit-correction-02/launch.py --mode guard --label independent-audit02-guard --outdir reports/v0-s3/product-gate0/independent-audit-correction-02
python3 -B reports/v0-s3/product-gate0/independent-audit-correction-02/negative_probes.py
python3 -B reports/v0-s3/product-gate0/independent-audit-correction-02/install_before_import_probe.py
```

| 执行 | 原始结果 | 真实外层退出 | skip / 未执行 |
|---|---|---|---|
| focused | **10 passed, 90 deselected in 0.93s**，collected_count=10 | 0 | 0 skipped；90项是选择器外未执行，不计PASS |
| guard | connect/bind/Popen/system **4/4** 候选拒绝，hook_install_count=1 | 0 | 无 skip；无 fixture 准入 |
| 独立负例矩阵 | 3原形异常、旧完整凭据/跨 executor/未消费副本重放、9结算故障组合、完整 invocation、安装故障断言均成立 | 0 | stub handle，不是实进程 |
| 安装早期探针 | 显式/静默拒绝各 main=5，pytest/产品导入前后空；旧hook/alias不能应答当前注册实例；正常幂等成功 | 0 | 无 skip；负例的5是预期被捕获，不是生产运行通过 |

两份生产 receipt 均 admitted_attempts=0、child_handles_obtained=0、proven_child_handles=0、fixture_process_starts=0、source_unchanged_during_run=true。fake counter 数字只代表 synthetic 测试，不混入原共享预算。没有机械复跑57/100/92/71/257，也没有借 deselected 补绿。没有执行实际13 fixture、完整I01–I24、Windows服务/后代/GPU/A06、真实原生QualityPhase组合、产品12项质量、原ledger；这些均为 **NOTPROVEN**，其禁止原因是本次零进程/零服务/零模型授权边界及仍冻结机器准入，而不是测试通过。

## 回归影响与历史 PENDING

M1影响未来进程启动失败的并发占位释放，M2影响失败结算、最终收据与根保留，M3影响 pytest/产品导入前的硬边界，m1影响可复跑证据。原两项正例从手造异常改为生产 hook，旧断言（累计准入仍递增、refused 可释放本次并发槽、admissions 不等于 handles）保留；新增测试没有改产品质量门限/timeout/24分母。当前证据只支持四项关闭及其相邻失败回归，不能替代未修改生产集成义务。

原 history run01 的 stderr 是9个旧参数化 nodeid not found、collected=0、receipt exit4；run02 stdout 为13 failed，前两项 clean_terminal/blocking_callback 的完整 traceback 都在 `/usr/lib/python3.12/subprocess.py:1823` 的真实 sys.audit、OS创建前被旧 alias hook 拒绝，余下 CPU_CONCURRENCY_LIMIT。原 receipts 的 cleanup_proven=true 是历史错误，不改写；没有独立历史外层退出材料时不补造。

可延续原独审给 root 的建议：用原始两段 traceback、准确 argv/scenario、counter index0/1 和原件哈希另立历史 pre-fork 拒绝裁决，认定未取得孩子的历史失败；不能仅因 pid=null、新分类器或本轮10项通过自动对账。此建议不写 counter，不退款、不清零，不消费最后60秒，不授权恢复 fixture。

原 counter `counter-before.json` 与 `counter-after.json` 字节相同，SHA256 均为 `8cc8ed9ac56f92db817bfc79dacfb69145adf8ade6f7c4605551ca7dd4f5dc37`：active=false，2 PENDING，admitted2，reserved120/180，spent2.896，review starts0。详见 counter-equality.json。两失败 run 与预算均保留。

## 源与证据绑定

三源 SHA256（也与 git 候选 blob 完全一致；baseline和末态在 candidate-source-hashes.json）：

- executor.py：`1cafd73ffef7230ca088b49d408f4ce4b69f5be10e238cb6710fa1e8a78d0787`
- run_guarded_checks.py：`da688b1502dcf625bbbf883c5e7e519d0c4c386a51fafa15539a69e2331d1005`
- tools/test_v0_s3_supervisor.py：`52aa2dbe2332a3f740c0fdc9d8131132aa2c765eccff4208c82ceb2e439c4815`

两 runner 收据包含执行前后10源 hash；日志、收据、诊断脚本、synthetic 原件及本报告 SHA256 全部列于 evidence-hashes.json（清单自身不自引用）。root-reference-hashes.json 绑定原审查材料和历史原件；旧证据没有改写。工作区最终只新增本目录；全局 MANIFEST 未动。

## 十字段交接

1. 当前坐标：root-control.snapshot.json 所记 R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION/RUNNING；不改候选中历史控制文件。
2. 本批完成：隔离四项纠偏复验、focused10一次/guard4一次、独立零fixture故障矩阵和早期安装探针，F0/M0/m0。
3. 最后通过门禁：621b1bf统一切片UM10与原人签，非本候选产品Stage。
4. 当前阻塞：历史2PENDING待root独立裁决；真实13fixture、24集成及产品Gate0证据未证明。
5. 全局路线位置：本报告首段完整计数；各正式Stage/实现/机器验收/独审/人签不得相互替代。
6. 剩余工作：root决定四项关闭、历史裁决及任何后续机器准入；完整运行与产品验收另保留。
7. 下一责任人：root；本独审不实现、不更改原账、不恢复fixture。
8. 所需授权：本轮任务已足够，无新人批问题；后续必须由root另绑候选/有限执行门禁。
9. 证据目录：reports/v0-s3/product-gate0/independent-audit-correction-02/。
10. 精确停止原因：独审交付已完成，进入root归档回收窗口；stage_pass_claim=false、product_gate0=false。

本实例没有创建或回收其它窗口；当前各工作区实际Agent存活数没有独立盘点，不猜测数量。回收数0；本窗口保留到worker_done确认，随后由root归档回收，默认不keep-open。
