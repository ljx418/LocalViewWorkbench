# N1纠偏03：首批失败后的最小纠正包02（仅静态实现许可）

root采纳真实首批133call/115PASS18FAIL/0SKIP/exit1/cleanup=false，候选46af977已Git完整封存，原始工件/root计划保持。批末14个channel-pump daemon线程是产品关闭失败事实，不能因测试进程最终退出回收而写清理通过。本包不签任何Major关闭。

## 唯一允许修改
只允许tools/v0_s3_native_custody.py、tools/test_v0_s3_native_custody.py、tools/test_v0_s3_native_custody_regressions.py与NEW implementation-native-custody-correction-03/attempt02-preparation（后续执行产物attempt02）。生产native_broker.py在本最小纠正中保持原46af977字节；旧owner/协议/冻结16义务/control/MANIFEST/原报告与失败原件不改。若确有另一个生产broker错误，先提交实际因果证据与最小接口方案askroot，不借本轮改时间安全语义。

A（生产）NativeCustodySession已有self._remaining预算整数，新增同名method被遮蔽。保留原整数语义和evidence字段，重命名deadline剩余方法及所有相关调用（包括两个join路径）。静态检查本三N1模块所有实例属性赋值与同类callable方法重名，及Thread子类与Thread内部_stop等冲突，报告真实发现并修本包范围内明确冲突，不机械新增泛用分析平台。修复需证明start/stop/REFUSED/cancel/heartbeat所有受影响关闭路径真实join，非只把daemon计数忽略。

B（当前证据属时钟场景问题，未证明生产需要少检查）Clock(step=0.6)每调用一次就推进模拟时间，两次读时钟自然越过1秒租约；按到期拒绝并非已证生产误判。禁止通过减少监督侧时钟检查来使该用例绿：保留原生产每步前/后检查以及空轮询期间deadline监督。测试改为ManualClock/显式advance，在启动完成后的受控transport.read/调度事件推进时间，确定性驱动LEASE_EXPIRED/exit4；另保留N03-R07启动动作返回时已到期→拒绝/禁止后续create/Resume/STATUS成功的Oracle。两种场景分开，不能把所有启动前拒绝状态改成运行中exit4。不允许为测试常量消耗删安全检查/加宽lease/延长clean预算。若通过fake事件证明真实控制顺序漏洞，另报最小修复，不能把步进时钟读取次数当实机时间证据。

C（测试）RecordingWin32要能在同一轮触发job_limit失败与close失败。用明确失败点集合，保留单点兼容及稳定码，并断言两个失败点均实际触发；用例组合('job_limit','close')驱动真实Core.arm，失败后的原job/pending/retained_resources事实仍为root冻结N03-R04，不能降低UNKNOWN或引用保留要求。不能只让pytest.raises任意异常通过。

D（测试）第一次stop已释放/关闭的job不能第二次再terminate/close，因此不要求第二次重复抛同一个RuntimeError。第二次stop应保持UNKNOWN及第一错记录，之前成功关闭句柄的close次数不增加；若仍有未关闭资源，原owner仍须可在原清理预算内协调，不能用“幂等”掩盖未确认资源。保留N03-R05首次普通失败后其他独立清理执行、primary/secondary不覆盖的断言。重复close/发包/模型启动均禁止。

## 执行与证据
收到本包后可以静态实施A/C/D与B测试场景修正；不是执行ACK。先对上述精确源/报告脚本提交新Git候选，生成新source/tool/223文件级依赖/stdlib pins、133节点及如增加必要场景节点的精确集合顺序、外部root guard/单次ctypes.dlopen(None)窗口、绝对argv/cwd/<=300s计划，再askroot唯一复验ACK。不能运行候选导入/collection/pytest，不自动补跑，不覆写首批记录。
NEW报告按实际receipt列16回归组的通过/失败：首批原115/18为唯一事实，不能把“新用例14通过”与R04/R05及R06/R11/R14同时失败的矛盾文字照抄；每项从机器reports复算。A就是原M07-M09生命周期义务的有效缺陷，不是无关环境错误。B与C/D分类按本裁决记录，候选/失败后继证据提交SHA精确绑定；不改既有报告只追加勘误。
全程仍仅离线本进程facade/线程/合成文件，不执行真实WindowsAPI/Job/GPU/模型/服务/OS进程/socket/sqlite/媒体/网络/下载/原ledger；原counter仅后续ACK批次外层前后各一次只读，不写退款清零新建复活。所有native/Windows/父崩溃/EOF/I24/产品12/A06/余额/质量/人签未证。FIRST429立即WAIT_BUDGET停，不重试/切路由/接手；FIRST审批拒绝/超时停，不包装绕过。唯一owner不派生Agent，只READY_FOR_REVIEW，不StagePASS。
