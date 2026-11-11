# P2B correction-03 独立离线闭环复验

代码结论 **Fatal 0 / Major 0 / Minor 0；C02-M01、C02-M02 在本冻结离线范围闭合，原跨 checkout 消费 M01 与 finally 终态 M02 未回退**。本独审任务完成，建议 root 接受此代码候选并评估后续有限 child 激活；当前 actual child 仍 DRAFT_NOT_AUTHORIZED，未激活。此结论不是实际 Windows/WSL debit/timeout 验收，更不是完整产品 Gate0、Stage、质量或人签。

候选 `9b661800b671c7e4942b906dcbeb1eee319c9ef3`；完整证据 tip `f08d525df9bd76d8e019eb9863903a753f9e5ecb`；合同基准 `6f5576fe4749dc95bb08f43c876d4249c9d2349c`。审查实例未实现补丁；开工 status 干净，从 `0e95ae9` 无冲突快进至指定 tip。只新增本目录。candidate-spec-seal.json 对源代码、合同、allowance、child、执行坐标与 P1 文件按三个提交及工作树封存；P1 protocol/core/shim/authority 未被候选修改。没有更改旧证据、计划、manifest 或 child。

## C02-M01：累计上界

run 的授权/DRAFT闩、source/history 封存之后，首次安装 executable digest 之前调用 reserve_metadata：仅 stat 三个固定角色，然后预留 `WinPySize + 32*WSLSize + 32*LinuxPySize`。unique roles=3 与读取次数明确分离；mode=CONSERVATIVE_NONREFUNDABLE_RESERVATION，actual_digest_bytes=null，剩余额度明列。实际 child 256MiB 不变，本轮未执行其预留或测量安装文件大小。exact 与超限均保守拒绝；通用 Meter.take 仍允许等于自身上限，这与 reserve_metadata 的更严格边界不是矛盾。

独立沿真实跨 OS 源码逐项核对：

| 固定路径 | Windows Python | WSL | Linux Python | 依据 |
|---|---:|---:|---:|---|
| installed | 1 | 1 | 1 | run 固定三角色循环 |
| 两个 factory | 0 | 2 | 4 | role(Python) 各1，加 copied authority.bind_execution 的 execution 各1 Python/WSL |
| 两个 admission | 0 | 0 | 2 | admit_case_plan 的 authority/shim/python 角色循环；前两者是源码 |
| 三个 Windows client | 0 | 3 | 0 | _command 在 nt/wsl-fixture 每次只 digest WSL；load_binding 是 JSON，不 digest Python |
| bad-binding negative | 0 | 0 | 0 | ref hash 错误在 _command 前失败 |
| normal 与 timeout shim+authority | 0 | 4 | 4 | shim tools 循环各1，加 model_action execution 循环各1；timeout 按完整成功路径保守计 |
| fault helper、Observer、terminal | 0 | 0 | 0 | helper 无 authority import；proc birth/journal 是身份数据；terminal 无 executable digest |
| 合计上界 | 1 | 10 | 11 | 不等于实机测量 |

Windows driver 的 source_hashes 只读九个固定源文件；ctypes 取得 process birth 不是 metadata digest。三个 driver 固定由 normal 根启动，phase 枚举只决定固定 action，normal 额外 bad-binding 在 digest 前拒绝；无 JSON 次数输入或 digest retry。helper 根由同 factory 产生且固定替换 shim，不启动另一条 production authority 路线。异常仅终止相应前缀；正常允许的后续 driver 仍已包含在完整总量中。authority 的 samples 在此固定 child 未设置，frozen_files 只有 protocol 源码；不存在未列的安装 executable 分支。1/32/32 因而覆盖该封存 call graph 的成功及失败读取。

combined-raw/metadata-spy.jsonl 的 1/10/11 是固定模拟路线的独立重跑结果，三个文件为合成 1/2/3 bytes，完整模拟路线54 bytes，预留161 bytes；failed-shim另加一次合成读取，不属于生产会重试的路线。不将 spy 等同完整 OS 实测。额外独立 probes 使用7/11/13 bytes，charge775：cap774/775均0读取/0charge，cap776先扣775，然后实际读取合成文件2 bytes并抛EIO，仍扣775、remaining1、actual_digest_bytes=null。静态控制流与这些真实合成证据共同证明先拒绝与失败不退款。

仍保留已披露的 Linux/WSL 和非 OS 逐字节计量限制：这是封存文件大小下的固定调用上界，安装文件并发变化仍依赖原 seal 漂移拒绝，不能声称逐字节 OS 监控。本轮 factory/P1 可读取本机 Linux Python 以构造 fixture，未对这些测试读取做累计OS测量；Windows host executable metadata digest 为0。没有为重证旧26次读取而触碰 host。

## C02-M02 与完整准入

owners 先校验 UUID/journal PID/birth、binding 与已记录身份，再查询 proc；仅 ENOENT/ESRCH 被窄化为一次原身份缺席，PID复用同样计原身份缺席。Permission、格式、绑定/身份矛盾及其他 OSError 均保持 error，two_absences=false。Observer 继续要求两次独立缺席；每个 sample、time、identity/count、deadline_reason、joined/error 均留存。12条确定性轨迹在断言前写入 combined-raw；额外独立 EIO、bad-observed-birth、bad-bound-birth 三条完整结果也先落盘再断言，非法绑定birth在proc查询之前拒绝。未泛 catch 所有 OSError 判退出。

唯一新真实 Linux fault helper：exit0、reaped/readers_joined/pipe_closed；Observer 6 samples、max_interval约0.10633秒、ENTERED、两次缺席、joined=true、error=null，两个新 SQLite calls 均0。完整 request/response/journal/进程结果在 combined.stdout，完整观测在 combined-raw/owned-helper.jsonl。没有启动第二次该 helper。旧109+1失败的 errno 永久 UNKNOWN；当前确定性 ESRCH 修复与完整新轨迹足以关闭当前代码缺陷，不追认历史通过，也不以不可恢复历史轨迹无限阻挡新证明。

回看完整 admission：双独立根、固定 roles/UNC、child/execution/ledger/source seals 均核对，normal driver 来源、helper Observer 根、timeout恢复normal binding 均保留。十类drift拒绝及实际 DRAFT/退休child闩在本组合通过。共享 claim O_EXCL/NOFOLLOW 与同child跨checkout八并发仅一胜仍通过；真实claim未访问。finally 三种故障注入仍写 BLOCKED/EXPIRED，双根登记，debit unknown保留last_observed下界；stderr的三条BLOCKED是预期注入证据。没有任意 argv/kill、新平台或读取原母ledger。

## 一次测试与执行边界

一次组合 **212 passed in 17.66s / pytest exit0 / outer exit0 / 0 skip**。combined-collection.json 保留全部nodeid；collection-reconciliation.json核对旧194＋新18，未重复18子集。十个测试文件中仅runtime-binding新增四个参数化函数（18 cases）；无删除，旧两函数仅适配 owners 参数及提前持久化完整观测。其余P1/oracle函数AST不变。

run_checks.py 复用并重新审阅实施者 parser guard 的边界逻辑，但在本目录单独实现可序列化字段、fsync+replace原子写、每个真实进程立即持久化、collection与逐测试结果持久化；没有修改或重跑实施者runner。启动pytest前audit/Popen guard已经生效，host open被拒绝，任何非允许.exe在进程边界拒绝；其它exec/system/spawn和网络connect/bind也被拒绝。fixture复制authority的外部WSL digest使用合成值。测试进程清单307条（257 git、49 Linux Python、1 parser）均保存在combined-processes.json；这是测试子进程清单，不是P2B实际batch或OS全进程审计。

**实际 Windows parser=1**，不是零Windows。allowance固定测试文件SHA256一致；只运行系统powershell.exe、-NoProfile/-NonInteractive/-Command、精确ParseInput(Base64)语法、调用来源固定测试。30秒/64KiB限制有效，实际0.18060秒、exit0、stdout `PARSE_ERRORS=0\r\n`、stderr空；真实argv/captures在combined-parser.json。不执行解码脚本/CIM。P2B Windows driver=0、WSL process=0、Windows host executable hash=0、实际claim/母ledger/媒体/GPU/模型/服务/network/download/checkpoint=0。没有重读PowerShell可执行文件来封存，OS装载不混称metadata hash。

新owned pytest basetemp和独立probe根已删除；本轮helper/normal根与子进程清理见cleanup.json。fixture上下文还断言自身根删除。没有检查、操作旧failed roots或旧PID；没有为清理而扩大kill权限。

## 历史任务与当前代码结论分离

实施者原raw的77个SHA256SUMS条目全部吻合。directed第一次17+1失败是嵌套root被拒绝，第二次17+1失败是Linux错误使用UNC；directed3为18通过。最终combined stdout明确212通过，stderr traceback发生在pytest返回后的store(receipt)，PosixPath不可序列化，combined.exit=1；因此业务测试绿可独立验证，但外层任务失败不能抹除。implementation receipt是恢复摘要，不冒充当时完整进程清单；丢失的进程清单仍不可恢复。本轮未重跑它，也不机械用元数据失败否定当前独立业务证明。

原实施者推定26次host hash读取（非syscall计数）、旧独审1次未授权parser的范围偏离及其failed outcome全部保留，不被新allowance追认。此次新parser例外仅向前有效。历史UNKNOWN、历史任务/外层失败、当前代码F0/M0/m0分别裁决。

下一动作仅给root：可接受当前代码离线修正；按当前候选/spec/seals与既有限预算另行裁决未来child的激活及一次真实跨OS有限批次，保留现有DRAFT直到root动作。真实Windows debit/timeout和生产Gate0证据仍待，不能把此复验当作产品放行。

十字段：当前坐标R1/WP-R1-U3；本批S3_P2B_CUMULATIVE_HASH_AND_OBSERVER_CORRECTION；已完成独立代码/原raw/一次212测试/6补充probe；最后接受仍621b1bf统一切片；当前实际阻塞为DRAFT和未来有限跨OS证据；实现候选9b6618已复验；机器仅离线通过；独审F0/M0/m0；人工签署无新增；下一责任root裁决，停止原因本独审交付完成。

完整V0–V3大纲及各子项/实现/机器/独审/人签状态原样封存在outline-snapshot.json：V0-S0 1/2（历史NO_GO）、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8（旧范围人签PENDING）、V0-S3 0/6；V1 R1 0/4、V1-M1 0/3、R2 0/4；V2 R3/R4各0/4；V3 R5a/R5b/R5c各0/4。V1-D0准备2/2、统一早期切片3/3有限接受保持。本轮不增加产品完成数，不覆盖当前协调坐标。

作者 ljx418 <1173696783@qq.com>；task_4aa80a825760 / ctx_321141dd4421。
