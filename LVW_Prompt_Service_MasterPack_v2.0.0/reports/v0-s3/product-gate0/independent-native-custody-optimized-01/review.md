# N1 optimized-01 独立审查

结论：**CHANGES_REQUIRED，Fatal 0 / Major 1 / Minor 0**。实际定向结果为 **13 PASS / 1 FAIL / 0 SKIP**，失败是必要 R07 夹具 owner/oracle 引用缺陷，不是可降级的辅助详情。没有 Stage PASS，不正式关闭或降级旧 M2/M3 两个 Major。

唯一候选 `1a34fbbe318fbe240823a2bf2f09517a98294744`；规格 ADR16、N1-OPTIMIZED-01/1.0 及机器政策。T10 精确 Git blob SHA256 为 `f89ef38a7fcb0f48a47f9498ed1c9100c6f0832df57257c7b27e7c5461ad3ee0`，512164 bytes / 9806 lines。源码均用 `git show CANDIDATE:path` 读取，没有使用 review 工作区旧 HEAD/脏源码。详细字段、原始证据路径与哈希见 findings.json / source-binding.json；旧22审查仅用于查找待复核路径。

## 四项义务

| 义务 | 独立源码结论 | 实际证据与边界 |
|---|---|---|
| N1-OPT-01 | **CLOSED_STATIC**。T10:5091–5124 的 verdict 使用完整错误历史；794–860 在写失败后追加 E、刷新并有限重试；5499–5644 的内层、精确外层 catch、最终 finally 均消费该 verdict，已捕获 sentinel 不再免除 E。真实原始 O 优先，其次首个精确 K，再普通失败；实际调用者亦硬断言 proof。 | R07 在4158失败，后面的 controlled_failure 五子场景没有到达，没有 controlled 收据；不把整组已运行冒充 writer 负例已验证。 |
| N1-OPT-02 | **CLOSED_STATIC（stale-proof 机制）**。794–860 在失败 E 入历史后、重试落盘之前重新计算 callable verdict；5615–5644 再计算并拒绝成功。双写失败只留内存失败，不承诺持久化。 | 本轮实际 FAIL 来自 R07，未触发 final-writer/stale-proof 分支；不能借这次无关 FAIL 将旧缺陷降为 Minor。 |
| N1-OPT-03 | **CLOSED_STATIC（所列 publication 路径）**。文档在 body 前创建；recovery/creation/tightener 在优先级前发布；dispatch/await/retry/interrupted/R12 不再等待 happy facts；startup 有独立 cleanup 文档和 joins；R06/R11/R13/R14 增加 finally 内发布。逐条读了普通错误最终消费者，而非仅查 helper 名字。 | 实际 R02/R09/R12 文档有动作、真实 liveness 和原始值；R07 zero-salvage 在 O 正在展开时保存 O、stop、全部 drain 与实际清理。stop-only 文档的动作/空错误不单独证明实际清理，alive=None 也不能当完成。缺必要 raw/原始错误/身份/清理依然阻断；重复辅助阶段详情仅可能符合例外。本轮 R07 缺的是必要 owner oracle，不符合例外。 |
| N1-OPT-04 | **CLOSED_STATIC（已观察 owner 的 query-failure fallback）**。6244–6408 在可失败查询前独立保存真实 owner/thread，inflight 失败仍按身份合并已持有 owner，逐个 guarded settle(5)，lookup 失败回退原 thread，guarded join(10)；known owner 无法确定 thread 会写 UNKNOWN 并拒绝成功。发布在所有动作后、优先级前。 | R09 实际 interrupted-start 有 owners_attempted=1、liveness_known=true、owner_alive=false、无清理错误；未注入 inflight/lookup 的 E/K，故不正式关闭该负例验证义务。 |

上述源码修复结论不等于旧 Major 正式关闭，也不等于每条异常分支已实际运行。确切触发、oracle、negative、terminal、cleanup、uncertainty 已逐项登记。

## Major OPT-R07-OWNER-01：返回后从可清空槽重读 pump

真实收据在 T10:4158 失败。zero-public-chain 原始事实为：reply wait 和 queue get 均 `[0.0]`；admission 时真实 pump attached、已进入 read、没有 EOF、实际 error=None；gate released=true；public start 返回 `UNKNOWN_RETAINED`，broker_retained=true，原 broker pid4242、PARENT_ORIGINAL_HANDLE。其后的 `zero_pump_frames=null`、finished=false、context=false 必须结合生成表达式解释，不能直接诊断成生产 pump 未退出。

T10:3998–4018 在 ZeroTighteningWaiter 中取得的真实 pump 仅存于局部变量，随后未交给返回后 oracle。T10:4067 重新读取 `zero_session._pump`；4103–4104 的 None 分支生成 frames=null，4094–4095 和4115–4117 的同一 None 分支生成 false。因此本次检测的是缺失的瞬时引用，没有读取真实对象的 finished/context/error；error-is-none 的默认值也不能证明真实 pump error。

生产 custody:1795–1816 将启动超时带入 `_close_broker`，2110–2131 调用 `_stop_background`。1585–1664 对真实 pump 停止并有界 join，确认已结束后允许 `_pump=None`；若仍 alive 则保留引用并记失败。admission/read 与 observer 的真实 started 事实排除了“从未启动”清空分支。结合原始条件默认值，**这是夹具丢失实际对象观察引用的证据，不是生产 owner 丢失或 pump 未退出的证据**；该归因来自精确源码与 raw，未依赖实现者静态结论。

生产1393–1469 的 `_background_threads['pump']['thread']` 保留实际对象，T10:1142–1172 的 `_session_owners` 正从该表取得对象，observer 也保留实际 thread。zero-salvage 的 `session:background-pump` 实际 joined=true/alive=false；另有 heartbeat、channel drain、read worker 全部 joined/dead，generation8 稳定、quiescent=true。**后续 fixture join 不能冒充产品返回即清理**：public start 返回仍明确 UNKNOWN_RETAINED，原 broker/channel 的未完成清理与错误保持；后来的 stop/drain 是另一个时间点。本次没有在返回时保存真实 pump 的 frames/error，不能补造这些值或承诺修复后必然通过。

最小合法修复仅在新冻结的 T10 夹具：在 admission、收紧截止时间前独立持有实际已附着 pump；返回后检查该同一对象的真实 finished/alive/error/context/broker，并用生产后台表及 observer 的真实引用核对身份。若瞬时 session._pump 已 None，必须同时证明 held object 实际 finished/dead 及生产确认 join 后清空的具体路径；非空则必须仍是该对象。未知、仍 alive、foreign context、缺引用或实际 error 均不得 PASS。保持 production default launcher/public start、真正 event/queue 的 exact0、admission noEOF/error-None、超时原因、真实 returned UNKNOWN_RETAINED、原 broker 保留以及 fixture 有界清理的全部安全断言；不能仅删除 identity 断言、替换为私有 take/helper pump、人工置 finished 或放宽时限。没有生产 broker/custody 修改依据。

这是必要 oracle/真实对象身份缺失，故 **Major**。owner 为可见 ClaudeCode 夹具实现者；退出条件为最小修复候选重新冻结、独审并经 root 单独 ACK 后有限复验，保留本轮真实 FAIL。审查者未修改或重跑候选。

## 原始结果复算与身份

初次目录为空，曾记 RUNTIME_PENDING；仅在主控明确通知已交付后重新读取，没有轮询等待。随后 before/after、guard 和 runner 原始收据均齐全。plan SHA256 `16549d45fcd87e274b7abc05f1dcc69a95ea06850ea77bb793443e45832d8ff1` 与 root ACK 一致；60 source pins、3 tool pins、223 dependency pins 重新只读哈希均一致。固定 runner 在候选/pytest import 前核验这些 pins；原始 collected/selected 顺序及实际 traceback 与候选匹配。内部 `aaaa/bbbb` 是合成 fixture plan，不能冒充外层候选/授权身份。

独立从 reports 数组计数：14 个唯一 call，13 passed、1 failed，无 skip/setup/teardown 隐藏失败；pytest_exit=1。FD before/after 的0/1/2号三元身份完全相同，无新增或复用 FD、无 unknown；两次 filtered3 为枚举过程已失效项，不作为有效 FD。threads before/after 均仅 MainThread。guard 的8类 selftest 拒绝均在，runtime_denials=[]；唯一 ctypes.dlopen(None) preload 窗口在 candidate 前关闭，guard finally 收据完整。before/after 均证明同一精确 parent 与 counter MISSING/errno2，仅证明不存在，不证明历史余额或复活授权。批次 CPU 清理成立，**没有缺失的 after/guard/runner 批次终态收据**，没有产品终态验收。

## 未验证与下一门槛

189 个顶层测试身份/顺序/签名/decorators 以精确 Git blob AST 作为数据复算：117+16+24+18+14=189，与22一致；T10 assert-test multiset 无删除。此为静态身份核对，不是实际189执行或全面语义等价证明。**14 不等于189，更不等于产品29**。

生产 broker/custody SHA256 仍为 `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` / `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581`，仅复用 source-review13 的未变静态范围。其9项原生不确定性 N03-R16、N05-R06/R07/R08/R24、N07-R08、N10-R12/R13/R14 全部仍未证实；Windows/原生清理/GPU/端口/服务/sampler/parent-crash/stdin EOF 未获证。

下一必要验证：先冻结最小 R07 owner/oracle 修复并独审，再由 root 派生有限受控复验；确保 R07 后续 controlled writer 分支真正到达，并补对应故障负例和 query-failure fallback 的真实证据，之后仍需固定189、准入真实主链、产品29和必要人签。本报告不新增运行许可。

仅生成本目录 review.md、findings.json、source-binding.json；临时仅保存三个精确源码 blob 静态阅读。无候选 import/compile/collection/pytest、模型/GPU/服务/DB/原生API，无子agent，无旧报告修改、递归复制、checkout/reset。协调采用 orchestration 技能 `/home/administrator/.agents/skills/orchestration/SKILL.md` 及 `orca-ide skills get orchestration`；worker_done 仅结算任务，不证明物理窗口退出。

十字段：坐标 V1/R1/WP-R1-U3/S3_P4；本批独审已交付；最后通过 UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前阻断 Major OPT-R07-OWNER-01；路线 OPT-B→OPT-C；剩余最小修复/独审/有限复验/正式checkpoint；下一 owner 主控与实现者；授权 本轮只读，已有单批ACK不延伸；证据 本目录与绑定的 attempt01 raw；停止 CHANGES_REQUIRED F0/M1/m0。实现 READY_FOR_REVIEW、机器 targeted FAIL、独审有阻断、无新增人工签署，四类状态分开。

完整 V0–V3 大纲（权威 execution-control 完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
