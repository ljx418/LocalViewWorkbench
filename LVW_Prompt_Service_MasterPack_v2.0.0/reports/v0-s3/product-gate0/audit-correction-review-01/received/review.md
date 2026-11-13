# S3-P4-OFFLINE 审计守卫与启动前记账独审

结论：**CHANGES_REQUIRED，Fatal 0 / Major 3 / Minor 1**。这是纠偏范围意见，不是产品 StagePASS；候选 `74ff021934afef661f8c7e8c1c4f11b26f7c3360` 对比 `763f3d561772ec8efa7aafe597b62ac77a3b7969`。独审没有读取作者的 report 判定；先读冻结合同、root 指令和原始失败日志/收据，再独立执行定向检查。没有修改候选源、冻结合同、MANIFEST、坐标或原 counter，没有执行带 binding 的 runner。

## 工作区及证据

独审工作区 `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-review` 的初始 `git status --porcelain=v1` 为空；随后由本审查者 detach 到指定候选。只新增本目录。root 主包只读，未切换 root 或实现者工作区。原始状态记录见 `initial-state.txt`；root 权威文件身份见 `root-reference-hashes.json`。root 当前坐标是 R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION/RUNNING，阻塞为纠偏独审与预算对账，候选中旧 READY 坐标没有被改写。

所有执行命令均在本隔离包根运行：

```sh
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode focused --label independent-audit-focused --modules tools/test_v0_s3_supervisor.py --select "alias or production_entry or single_guard or offline_boundary or refused_start or unknown_start or finalizer_never or machine_accounting" --outdir reports/v0-s3/product-gate0/independent-audit-correction-01
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode guard --label independent-audit-guard --outdir reports/v0-s3/product-gate0/independent-audit-correction-01
python3 -B reports/v0-s3/product-gate0/independent-audit-correction-01/negative_probes.py
```

前两条各执行一次：focused **8 passed / 84 deselected**，外层退出 0；guard **connect/bind/Popen/system 四事件全部拒绝**，外层退出 0。原始 fd 日志、runner 收据和真实外层 stdout/stderr/exit 均保存，非 shell pipeline 的退出。negative probes 外层退出 0 表示复现断言成立，不表示候选通过。其独立硬守卫在任何候选 import 之前安装，禁止 socket 事件、fork/exec/spawn/Popen/system；仅临时 synthetic counter 与 stub Popen，不创建任何 fixture 孩子，也不调用原 counter。脚本以 API 故障注入和复制异常属性验证任务明确要求的边界，不把任意内存恶意修改当威胁模型。最后增加真实 CPython addaudithook 静默拒绝探针后保存的日志为最终脚本的一次完整输出。

## Major 1：REFUSED_BEFORE_FORK 不验证真实 guard 来源或当前 charge

位置：`implementation-integration-01/executor.py:91-101,651-683`；`tools/test_v0_s3_supervisor.py` 新增 refused_start / machine_accounting 测试。

触发：已准入的当前 start 在 Popen 返回句柄前抛出普通 RuntimeError，复制 `lvw_before_fork=True` 和同模块 `CpuGateError` 到 `gate_error`；或抛出先前保存、与当前 start 无关的 OfflineBoundaryViolation。期望：只有本次真实 guard audit refusal 与本 executor/current charge 的一次性证据才释放并发槽；错误外层类型、复制标记、旧拒绝均 UNKNOWN 并保留。

实际：分类函数只检查布尔属性及内部错误的类，不检查外层 guard 类型、拒绝是否由 hook 发出、executor、线程动作 nonce、charge index 或一次性消费。两种负例均得到 `REFUSED_BEFORE_FORK`，occupied=0、open_charges=[]、cleanup_proven=true、owned root 被删。仅 marker 搭配 ValueError 的对照确实 UNKNOWN/occupied=1/root保留，因此问题是信任凭据不足，非所有异常都被释放。

证据：`negative-probes.stdout.log` 的 `wrong_outer_class` 和 `stale_guard_error`；上面的第三条命令可复现。生产 `spawn` 的 TLS token 绑定了“本线程最近准入”，却没有把 error 绑定到该 token；伪造/重放的错误会被错误归给新 charge。当前正例测试本身手工构造 violation + CpuGateError，没有经真实 guard 链，恰好把未经验证的声明当成可信正例。

建议：guard 内部生成与当前 executor、charge、线程动作关联、不可复用的拒绝凭据；executor 只消费真实关联凭据。外层类型校验也需要，但单独添加类检查仍挡不住 stale_guard_error。普通错误仍保守 UNKNOWN。这里没有声称当前无 binding runner 已实际逃逸，也没有模拟真实子进程。

## Major 2：charge 持久化终态失败仍可假 cleanup

位置：`executor.py:656-683,914-940` 与 runner `finalize_session` 的 open-charge 判断。

触发：启动前拒绝路径中 `counter.finish` 抛出 CpuGateError（如真实 counter 变为不可读/失效）；它已从 `_pending` 移除该 index。期望：持久化失败仍为 open charge，finalizer 非零并保留 owned root 和诊断信息。

实际：catch 只设 `uncertain=True`，随后仍将本地 outcome 写成 REFUSED_BEFORE_FORK；`unsettled_charges()` 不看 uncertain 或原 counter 状态。reap 无 child、无 pending 返回 []；finalizer 报 cleanup_proven=true、exit=0、删除 root，而 synthetic counter 原记录仍 **PENDING**、occupied=1。会形成本轮明确禁止的“无孩子却假 cleanup”。

证据：`negative-probes.stdout.log` 的 `failed_finish` 同时保留原 counter_state=PENDING、uncertain=true、open_charges=[]、cleanup_proven=true。第三条命令可复现。该探针只注入真实 API 可返回的 CpuGateError，未更改生产代码/原 counter。正例拒绝凭据本身在此用现有候选认可的合成形式，以隔离此独立持久化错误；修复 Major 1 后仍需独立保证 finish 失败不被本地终态掩盖。

建议：成功、明确持久化之前不得将 charge 从待结算状态移除；失败/返回未结算均保持 UNKNOWN/open 并使 finalizer 保留根、非零。不能只修 receipt 文案。

## Major 3：安装被拒后仍宣称 guard 已安装，后续不再尝试

位置：`run_guarded_checks.py:371-391`，尤其 386-390；main 及 __main__ 重复调用没有补救。

触发：sys.addaudithook 注册失败，或已有审计策略 hook 在 `sys.addaudithook` 事件上抛 RuntimeError，使 CPython 静默拒绝新增 hook。期望：必须证明本 hook 已活跃才能设置 installed 状态，任何拒绝/失效都禁止导入 pytest/产品和执行测试。

实际：先置 hook_installed=True、count=1，再调用 API。显式异常后的第二次安装直接返回 owner；真实 API 静默拒绝也返回 owner，声明已安装但 harmless audit probe 从未被目标 hook 收到。main 随后会继续进入 pytest。所要求的 failclosed 安装检查没有实现。

证据：`negative-probes.stdout.log` 中 `installation_failure` 的 API 仅调用一次，以及 `real_api_silent_rejection` 的 reported_installed=true/count=1/owner_returned=true/probe_seen=[]。第三条命令可复现。静默拒绝测试使用真正 sys.addaudithook 和已有 hook 的拒绝行为；不是修改注册表绕过守卫。独审的外层强制守卫始终在，不进行任何可能逃逸的操作。

建议：以无副作用、与 owner 绑定的 audit 握手确认目标 hook 已安装，并在进入 pytest/产品前确认活动状态；登记成功前不能承诺 installed。失败退出并保留失败证据。不要通过删除守卫换绿。

## Minor 1：receipt.command 不是实际完整命令

位置：`run_guarded_checks.py:663-667`（command 重建）。

触发：本次 focused 命令带 --modules/--select；历史运行还有 --binding/--binding-sha256/--role/--candidate-sha。期望：command 能准确复跑同一执行，或明确标记仅为 base command。

实际：command 只保留 mode/label/outdir，忽略这些控制执行内容的参数；例如复跑本次 focused receipt.command 将因缺 --select 而拒绝。argv 字段保存了参数，collected_nodeids 与原始日志可交叉核验，故不扩大成运行造假；调用端 sys.executable/-B 的信息由本次外层记录补齐，历史缺失的外层退出凭证不猜测。

证据：本次 focused receipt 的 argv 对比 command；历史两收据也存在同类缺失。上面第一条命令仅运行一次即可见；不需要重复套件。建议直接保存完整实际启动参数或明确 base_command 语义。

## 已成立的纠偏部分及未改集成影响

正常生产入口：__main__ 在 main 前安装，main 又在 pytest 与 `_load_executor_module` 之前调用安装；runner 顶部仅标准库和定义，没有先导入产品。alias import 不再安装 hook，使用 sys.modules 的同一 registry/class/gate，8项检查的 production-entry 用例未 skip，单 owner/hook count=1。四事件自检确实仍拒绝 host process/network。没有发现删 guard 换绿；但以上 Major 3 表明登记字段不是安装成功证明。

普通 OSError/错误 nested type 的未知启动走 UNKNOWN，保留并发槽及 owned root；pending 无句柄最终被 reap 转 UNKNOWN，focused 的 finalizer_never 检查通过。TLS admission 在 spawn 开头清空、成功/失败后消费，避免按跨线程 FIFO 错取本次 spawn charge；`register` 仍有旧 FIFO fallback，当前生产 spawner 使用 spawn，不从测试便利接口推导生产并发已实测。TLS 不等于异常来源认证（Major 1）。

取得句柄后：`_take_custody` 先将原 handle 纳入 children，再 mark_started；普通登记异常仍留下 children 供最终 reap。watchdog setup 异常有 stop/reap。构造 custody entry 时读取 birth/clock 早于 append 的旧有间隙仍存在；本轮未将任意内存破坏/时钟实现主动抛错提升为新增故障，不声称实子进程 custody 已通过。reap 对 exit 不明保留 UNKNOWN 并保留看护；本轮没有运行真实 cleanup，因此不能用这些静态路径替代 I08/I09/I13/I14 的实进程义务。

diff 中仅 runner/executor/监督测试三份可执行源变化；coordinator、QualityPhase/worker、S2 runtime/stage_runtime、supervisor 和 fixture 源未变。新的 runner/记账错误可影响其证据可信度与未来 fixture 准入，不能将旧集成义务删掉。I01–I24 原24项分母不变；本次只检查守卫与失败记账，不重新宣布这24项通过。

## 两个历史失败 run 的原始复算

原件副本放在 `history/`，来源路径与字节哈希见 `history-source-hashes.json`；未读取它们的 execution-report 总结。

| run | 原始 node/日志 | 退出 | admission / 原 handle | 预算 |
| --- | --- | --- | --- | --- |
| finite-fixture-implementation-01 | collected=0；stderr 九个旧参数化 nodeid not found，stdout no tests ran | receipt=4；没有独立外层退出工件可用，不猜测 | counter charges=[]、children=[]、starts=0 | reserve60，spent0.708 |
| finite-fixture-implementation-02 | collected=13；stdout 13 failed，前两项完整 traceback 在 subprocess.py:1823 的 sys.audit 中被 alias offline guard 拒绝，后11项 CPU_CONCURRENCY_LIMIT | receipt=1；本轮未见原外层直接退出记录，不把 receipt 当外层实测 | counter admitted=2、children=[]、pid/birth null；没有取得句柄证明 | cumulative reserve120，spent2.896=0.708+2.188 |

旧收据 `fixture_process_starts=2` 是审计准入次数，不能解释为创建两个孩子；created/proven handles 不能从缺字段猜成一个旧的正式数值。原始 children=[]、pre-fork traceback 能证明这两次未取得句柄且在该 OS 动作前拒绝，并不等同完成了13 fixture检查。旧 cleanup_proven=true 是存在两 PENDING 时的错误结论，必须保留原文作为历史失败证据，不回写成通过。

候选新增 admitted_attempts / child_handles_obtained / proven_child_handles 分开统计，legacy 字段附了明确语义；本次无 binding 两收据这些值均为0。合成拒绝测试 admission=1、proven=0 数值区分成立；但 Major 1/2 使 charges_without_handle 的状态真实性和 cleanup 仍不能信任。proven_child_handles 是取得 handle 且退出已证明的计数，不能冒充成功工作数。

只读对账建议给 root：原始 run02 前两条 traceback 均完整显示同一实际 argv/scenario（clean_terminal、blocking_callback）在原 sys.audit、OS fork 前由第二 alias hook 直接拒绝，并与 counter index0/1 的顺序/命令和时间关联；因此可由 root 另立、绑定原件哈希的历史终态裁决，将两笔认定“历史 pre-fork 拒绝、从未取得孩子”，不是重跑成功。不能仅靠 pid=null/children=[]/新 candidate 的分类器自动认定；这里提供的是原始 traceback 的关联证据。实际 counter 仍 inactive，两笔 PENDING 没改动；任何后续 reconciliation 都需 root 明确处理和留痕，保留 admitted2、spent2.896、reserved120以及两失败 run，不退款、清零、复活或自动消耗最后60秒。本审查不授权恢复 fixture。

`counter-before.json` 和 `counter-after.json` 原始 bytes 相同：SHA256 `8cc8ed9ac56f92db817bfc79dacfb69145adf8ade6f7c4605551ca7dd4f5dc37`；见 `counter-equality.json`。active=false、2 PENDING、starts_total2、reserved120/180、spent2.896、独审starts0全部保持。

## 限制、交接和完整路线

实际13 fixture、Windows 服务/后代/GPU/A06、I07 生产原生 QualityPhase 组合、全12产品用例、独立质量及原 ledger 均 **NOTPROVEN**。零 fixture 子进程、零网络访问、零模型/GPU、零原账本、零服务；系统 shell/Python审查命令本身不计为 fixture。没有机械复跑92/71/257项，没有新增预算，未继承作者通过结论。

当前坐标见上；本批完成独审与有限零进程复算；最后已通过产品范围仍为621b1bf统一切片的UM10与原签署；当前阻塞为本报告3 Major；下一责任人为root集中裁决并交实现者修正，非缺新人类GPU授权。证据目录即本目录；停止原因为独审交付已完成、候选纠偏仍须修复。独审没有创建/回收其他Agent；各空间真实存活总数本轮未盘点，不填推测值；root接到worker_done后立即归档并回收本窗口，默认不keep-open。

唯一 execution-control 的完整 V0–V3 路线计数（completed/total，非主观进度）：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3 0/4、R4 0/4、R5a 0/4、R5b 0/4、R5c 0/4。实现、机器验收、独审与人签继续分开；本报告没有修改任何子阶段计数。

所有候选可执行源哈希见 `candidate-source-hashes.json`，测试收据/日志/脚本/原始历史副本哈希见 `evidence-hashes.json`。本报告可单独归档，源候选不改动。
