# 同候选 R07 retest 实际失败独审

**CHANGES_REQUIRED：Fatal 0 / Major 1 / Minor 0。** 独立复算 attempt02 为 **0 PASS / 1 FAIL / 0 SKIP**，实际 read-worker 未清理，不能列辅助 Minor，不能进入依赖该义务的 N2 实施或宣布 Stage PASS。

候选仍为 `62e0d429dd78418220235359d068ae28d7b37e6e`，T10 SHA256 `2a8e951b357068e835f6c7d276062395d83dc691ad5e51afde5c9e1da6cb64ac`。只读取精确 Git blob 的相关生命周期段及已完成原始结果，未重做全面静态审查、未执行候选或测试。此前7233efd静态报告、cfee57a及attempt01失败均保留。

## 原始事实与身份复算

主控 targeted-plan-02 的 SHA256 `1fd5a31c2ff3917a331f6f7e83f054d2ec3c40653d5532dabf1e9e4c0339dc12` 与 root ACK 相同，候选与唯一 R07 selected/collected 一致。60 source pins、3 tool pins、223 dependency pins 独立只读重算均无差异；ACK 引用的独审 findings 哈希也一致。固定 runner 在 candidate/pytest import 前验证 pins，实际 traceback 与候选4500行对应；fixture内aaaa/bbbb不是外层身份依据。完整输入和证据哈希见 source-binding.json。

runner 63.032秒、guard 63.167秒，pytest_exit=1，唯一 call failed；4500行抛出 `AssertionError(zero_verdict)`，错误为 `zero: the owner launch:channel:read:read-worker was left behind`。FD before/after 的0/1/2身份三元组完全一致、无unknown、无新增/复用；filtered3只是失效的枚举FD。**threads_before=[MainThread]，threads_after=[MainThread, lvw-native-custody-pipe-read]，cleanup_proven_for_batch=false**。无FD差异不补足线程清理。

before/after 原始观察均齐全，精确parent/counter均MISSING/errno2，仅证明不存在、不复活历史计数。guard 8类selftest拒绝完整，runtime_denials=[]，唯一ctypes.dlopen(None)窗口已CLOSED；stdout保留实际FAIL，stderr为空。before/after/guard/runner批次终态收据均存在；这只证明运行已结束并留下失败，不证明其线程自主清理。

zero-public-chain 的真实held pump：finished=true、alive=false、error=None、frames=1，与admission holder、production background table、observer原对象、STARTED/context/broker等所有身份约束为true；实际reply/queue wait均[0.0]，轨迹完整。public start仍是UNKNOWN_RETAINED、broker_retained=true、PARENT_ORIGINAL_HANDLE/pid4242，失败原因保留CUSTODY_CHANNEL_TIMEOUT及reader/handle不完整事实。此前pump引用修复因此得到实际硬断言支持，**不能据此宣称整个R07或其后五个controlled子场景通过**。

## Major OPT-R07-CLEANUP-02

zero-salvage 的 original=null，说明zero body硬oracle已通过，失败产生于finally清理自身。三轮drain均观察同一`launch:channel:read:read-worker` STARTED、alive=true、joined=false，quiescent=false、proof_failure非空。外层parent-salvage保存该原始AssertionError；再三轮drain仍发现原observer线程 `lvw-native-custody-pipe-read#124376958014512` alive。其id与zero registry相同，不能把parent自身read-worker已结束的行当作zero worker已结束。最终runner线程快照再次确认遗留；五个controlled文件不存在，保持未运行。

已证实的控制流空档：T10的zero finally（4353起）释放zero_gate和zero_api.frames_ready，捕获真实public stop，然后调用`_drain_owners`；1354起drain及574起`_salvage_threads`只枚举和有界join，没有独立请求该worker停止。broker StreamChannel.close（5546–5668）在原deadline耗尽且其drain仍alive时，明确跳过read endpoint.close；原始stop事实正是reader_finished=false、read_end_closed=false、thread_handle_released=false。broker endpoint.close（5004起）本应调用stop_accepting/request_cancel，但该路径在上述早退下尚未到达。

Api seam（T10 R07 Api.read_stream/cancel_synchronous_io）仅让frames_ready唤醒合成read；read_stream本身有30秒wait并在锁外等待。**操作返回不是worker退出**：broker worker.run（4016–4141）完成一代请求后继续等_requests，只有stop/cancel设置停止标志才会离开循环；单纯join或Event.set没有此语义。故“channel在最后一次产品close时还活着→稍后drain结束→read worker完成请求但继续等任务→fixture只join”是一条具体可达、可复现的夹具收尾缺口，不需要放宽生产截止时间或制造新框架。

**确定性边界：** 收据确证实际线程遗留、上述夹具缺少独立stop/cancel、生产仍保留owner并报告UNKNOWN_RETAINED；没有证据证明生产丢失owner。当前raw没有该worker最后的等待帧、stop标志、generation或endpoint close/cancel调用轨迹，因此不能把“当时必然idle”或“必然卡在Api.read_stream”当成已执行事实，也不能完全排除另一生产同步故障。read Event有界/已释放更不能直接推出线程已结束。此层未知不影响清理Major阻断，亦不授权猜测性生产修改。

最小必要修复候选范围是**T10 R07 zero夹具收尾**：在保存产品返回/stop原始状态后，对真正登记、仍保留的zero endpoint/worker补足显式、有界stop/cancel及安全顺序join，使用现有fixture总界；保留真实对象、所有错误和代际清理证据，不续期产品deadline、不清registry/retained owner、不绕开实际句柄或改成假stopped。保持public default start、exact0、noEOF、timeout、UNKNOWN_RETAINED和原broker安全断言；不能删除hard cleanup verdict或把daemon/CPU进程退出当自主退出。现有证据不支持修改生产broker/custody。

若需把实际idle分支进一步确证，最小下一证据是在后续root允许的有限复验里记录**该同一held worker**的stop/inside/completion状态和endpoint close/cancel是否调用；仍alive时补一处真实等待帧即可。不另造诊断平台、不在本轮追加运行；若这些事实否定当前可达路径，再按事实另冻生产范围。

退出oracle：原产品返回状态先封存；fixture显式协调后实际channel drain和原read worker都退出、必要thread handle释放、最终owner generation稳定、threads_after仅MainThread且FD身份无漂移。负例中任何alive/unknown/缺必要结果继续FAIL。保存本次真实失败，修复后重冻源码/guard/命令/预算、root ACK有限复验，再独审清理；N2依赖保持阻断。

旧M2/M3静态范围及189身份只引用7233efd/cfee57a，不重新全面展开。writer失败/重试、early-body/secondary publication和interrupted-start查询失败负例仍未运行；R07尚未通过，常规通过也不替代负例。原9项原生未知 N03-R16、N05-R06/R07/R08/R24、N07-R08、N10-R12/R13/R14 不变；1次R07不等于14/189或产品29，无native/GPU/端口/服务/父崩溃证明。

仅写本新目录review.md/findings.json/source-binding.json并显式提交；未修改候选、旧报告或收据，无candidate import/pytest/native/model/GPU/service/DB、无轮询/代跑/子agent。十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批运行证据独审完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；阻断实际read-worker清理Major；路线OPT-B→OPT-C；剩余最小清理修复及有限复验/正式checkpoint；下一owner主控与夹具实现者；授权本轮只读、无新运行ACK；证据本目录绑定attempt02；停止CHANGES_REQUIRED F0/M1/m0。实现封存、机器FAIL、独审有阻断、无新增人签分别记录。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
