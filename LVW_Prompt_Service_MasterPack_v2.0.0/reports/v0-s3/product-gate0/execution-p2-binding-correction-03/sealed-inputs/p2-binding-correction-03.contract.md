# P2B correction-03：累计metadata预算与确定性进程消失观测（Codex冻结）

独审0e95ae9确认原跨root消费M01与finally终态M02限定修复通过；当前d339e53仍F0/M2，新增C02-M01重复metadata digest未累计、C02-M02 ESRCH未作窄化缺席且历史轨迹不足。旧批次/失败/偏离不改写，actual child继续DRAFT，禁止任何P2B实际batch/母ledger/真实claim/媒体/GPU/模型/服务/network动作。

## C02-M01 先覆盖所有读取的保守预留

本固定路线允许使用不退款保守预留，不必建设跨进程监控平台。精确区分unique metadata roles=3、hash attempt次数、实际测量bytes与charged upper-bound。在未来实际首次可执行文件digest之前，仅stat三个固定文件并预留一个覆盖全部固定factory/admission/Windows client/shim/authority（含失败路径）重复读取的字节上界；预留失败则0digest/0Windows，不能读后发现预算不足。失败/提前返回不退该预留。不能继续只记首次三文件bytes为累计实际。

root允许候选上界：WindowsPythonSize*1 + WSLExeSize*32 + LinuxPythonSize*32。实现必须列代码实际固定case/调用表证明每角色次数不超过该界；若无法证明，用较合适的更严格有限上界并交root，不能自行加child256MiB额度。预算引用DRAFT child现有256MiB，文件distinct3不变。所有Windows driver只允许固定case集合，禁止在json手填额外次数绕静态上界。源代码/fixture JSON哈希与这三个安装exe hash分类明确。

收据写mode=CONSERVATIVE_NONREFUNDABLE_RESERVATION、role_sizes/read_count_bounds/charged_bytes/remaining_budget；actual_digest_bytes未测则null/NOT_MEASURED，不把reserve伪称逐字节实测。字节公式、unique角色数和所有隐式复制authority的digest路径在测试中用spy+合成小文件推导，exact/one-over在首digest前拒绝，异常/部分读取仍保留reservation。P1真实预算policy/role/path/hash检查不改；本地未知安装变化不伪称被完整OS监控，既有封存/漂移拒绝语义保留。

## C02-M02 窄化处理与完整轨迹

仅对已经由fixture/request UUID/binding/PID/birth绑定的Linux proc身份查询，FileNotFoundError/ENOENT与ProcessLookupError/ESRCH记一次该原身份缺席，继续要求两次独立观察；相同PID不同birth也记原身份缺席。PermissionError、格式/JSON/绑定/身份矛盾都保持UNKNOWN/BLOCKED，不能泛catch OSError当退出。不得扩任意PID/kill能力，不访问旧PID/root。

在任何observer断言之前就将完整result（error、samples、times、截止原因、identity、two_absences/joined）写入新raw；若测试失败，finally也保存现有轨迹。确定性矩阵覆盖alive→ENOENT/ESRCH→两次absent、PID复用、首次已RETURNED、PermissionError/坏journal、deadline/无identity/停止/线程异常。一次正常Linux owned helper可验证真journal/退出，不能无限重复以“稳定通过”。旧109+1历史没有完整观察，原因永久保留UNKNOWN；此次证明可复现的ESRCH路径修复及新轨迹完备，不要求猜出当时errno，也不以复跑绿追认历史通过。

## 测试范围与一个明确例外

原实现推定26次wsl.exe hash与独审1次PowerShell parser偏离均保留，不追认为旧约束合规。为避免旧回归与本轮边界冲突，从本合同起实施者与独审各允许最多一次下述既有测试的真实PowerShell语法解析（合计2次，分别原始记录），不是P2B实际批次：test_s2_warm_benchmark.py::test_generated_lineage_script_parses_in_native_powershell_without_executing_queries。只准系统WindowsPowerShell powershell.exe、-NoProfile -NonInteractive -Command，命令完整符合现有Parser.ParseInput(Base64解码字符串)且仅输出PARSE_ERRORS计数；不得执行解析字符串/CIM查询/Invoke-Expression。单次<=30s，命令/输出<=64KiB，0服务/网络/模型/GPU；源测试文件hash见offline-parser-allowance-03.json。其它.exe或host路径进程一律在Popen边界拒绝；host executable digest仍0。PowerShell可执行本身由OS装载不是“metadata hash读取”，不得混淆为零Windows调用。记录实际parser invocation=0或1、原始argv/真实exit/stdout/stderr；没有发生则不称实测，超限/非白名单即停止。本例外只授权未来本两阶段，不抹除过去独审偏离。

只允许修改tools/v0_s3_runtime_binding.py和tools/test_v0_s3_runtime_binding.py；新增reports/v0-s3/product-gate0/implementation-p2-binding-correction-03/。不改production protocol/authority/业务/旧raw/child/contract/plan/manifest/正式16。先新定向测试，最终组合一次；原194功能/oracle保留（数字随新增case变，不能删失败测试/跳过算通过）。所有新fixture阻断/mnt/c的实际metadata读取，复制authority外部WSL seal仅以合成值替代、真实SQLite事务保持；不要再次读真实exe来证明保护有效。

完整同factory helper/normal/timeout admission、M01/M02及新两项集中交付，由不同窗口独审。实机DRAFT闩不变：未激活preflight/run 0Windows driver/WSL/host hash/real claim。两次同路线无进展停止交接，不无限重试；不需要人类再次授权代码检查。Git作者ljx418 <1173696783@qq.com>。只READY_FOR_REVIEW，worker_done候选/证据full SHA、原始测试/声明口径/parse次数/清理/风险，不签Stage/Gate0/质量/人签。
