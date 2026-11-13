# 顺序槽位纠偏第二轮独立复审

候选 `01453ee07b4774a55711c5cf5642c12d0394a35c`，基准 `4e999043d08005829969bf5020048759557ecee9`。结论：**M1 CLOSED、M2 CLOSED、M3 CLOSED；F0 / M0 / m0（限本轮冻结故障模型）**。不签 StagePASS，product_gate0=false；原四项审计关闭裁决继续保留。本实例未参与实现、未派生 Agent，没有采用作者19/19或基准11fail代替独立结论。

## 裁决与可复现证据

| 项目 | 位置与原触发 | 预期、实际与关闭依据 |
|---|---|---|
| M1 CLOSED | executor.py:741–758、981–1005、1074–1118；一个退出+空槽、两个退出占满；finish CpuGateError/OSError/False，读终态 CpuGateError/OSError | 应在新增charge前失败关闭，而非先准入一次再靠满槽拒绝。独立 `finish_*_capacity{1,2}` 14例包括原10例及只读失败而finish保持真实的4例：全部 `CPU_RECONCILIATION_UNSETTLED`，starts不变，原charge STARTED/settled=false，本地uncertain=true、账本UNKNOWN；finalizer非零、根保留。容量2也返回显式结算错误，不靠CONCURRENCY_LIMIT。证据 negative-results.json、negative.stdout.log、assessment.json。 |
| M2 CLOSED | executor.py:124–171、459–473、981–1005、1074–1107、1276–1329；原wrong-exit/wrong-pidbirth/foreign-index、UNKNOWN、本地已结算标志与磁盘分歧 | 应关联原预算/绑定counter/index/role/scenario/argv/原handle pid+birth/exit/state，协调与reap同义。原4个冲突均不准入，starts=1，没有新增pending掩盖cleanup；finalizer均exit4、cleanup=false、保根，原foreign-index的磁盘charge仍开放。另6个身份变体验证budget/role/scenario/argv/birth/state；磁盘STARTED及UNKNOWN与本地成功冲突均不补写修好。3个合法精确已结算记录即使finish被设为False/抛错仍正常cleanup，旧charge字段不变，finished_wall不重写、reserved60不退款。 |
| M3 CLOSED | executor.py:701–713、741–758；协调poll/finish/charge_state有限I/O跨固定截止 | 新charge前再次检查原deadline和uncertain。独立3种操作×3边界：deadline−0.001可准入；==deadline、deadline+1拒绝且starts1不增，原deadline始终不变。另协调后设置uncertain的观测以SESSION_UNCERTAIN_CUSTODY拒绝，无charge。不是只在入场前把时钟调过截止；延迟效果发生在真实协调调用内部。 |

全部58个观测及逐项判据见 assessment.json，脚本退出0只证明诊断执行完整；本报告的关闭结论来自实际charge/持久记录/终态/清理的逐例核验。矩阵组成：14结算错误、3正常、4原终态冲突、1本地STARTED分歧、9截止、1协调后uncertain、6身份、3合法终态、1本地UNKNOWN分歧、16个finalizer组合。

最后16例覆盖“原记录未结算/已经结算 × 读CpuGateError/OSError × finish真实/False/CpuGateError/OSError”。其中两个未结算+真实finish案例cleanup=true：首次读失败后，真实SharedCounter.finish成功写入该原charge的终态，既无本地已结算标志冲突、也无声称幂等成功。这是实际成功首次持久化，不是吞掉失败finish或信任本地标志；其余14个组合全部非零、保根。协调路径对同样读错误一律先拒绝新charge。未将“所有读错误都必须永远禁止成功结算”添加为冻结合同外的新要求。

正常路径独立13次admit/register及原fake handle退出，starts=13、保留13条原charge、观测峰值1≤2，末尾一次finalizer，首条finished_wall不变、reserved60保留。两live拒第三，一个退出后仅准入一个；UNKNOWN原退出保槽。看护使用候选原_ensure_watchdog，未stub、未扩大期限/预算。真实fixture、Windows原句柄不在这些合成结果的证明范围。

## 源码与原关闭边界

已逐段审查全部246行executor差异和351行监督测试差异，并阅读SharedCounter charge/finish、session检查、custody、watchdog、reap及原runner finalizer/guard调用链。集中规则真实用于协调和reap；预算由绑定counter的charge_state核验，counter来源是当前executor绑定路径，不增加通用平台/任意内存篡改模型。原handle身份取register时保留的entry pid/birth，admission取原本地charge，未信新terminal自报身份。

作者改写原错误测试的Oracle符合冻结失败关闭义务：明确starts=1、occupied=1<2、第一次即CPU_RECONCILIATION_UNSETTLED、后续SESSION_UNCERTAIN_CUSTODY及最终保根。它不再允许失败后先增加一次charge。测试返回形状修改有对应实际断言，未缩减固定24、改阈值或公共合同。旧max_concurrent2、24/16/8、child10s、session60、pool180、cleanup30及最早截止语义保留。

runner相对4e99904字节完全相同。旧credential一次性/原thread/action关联及安装握手代码无差异；本次focused含真实guard拒绝、无句柄未知、开放charge及finalizer等相邻测试，guard4实际拒绝来自候选OfflineBoundaryViolation，hook_install_count=1。完整实际命令由外层argv与runner receipt绑定，不把base命令冒充完整执行命令。旧audit-correction-review-02/root-decision.json的四项关闭依据保留，未见本轮实际回归；没有机械重跑旧整套或重开已关闭项。

## 实际执行与边界

仅执行一次无binding候选focused和一次guard：

```sh
python3 -B reports/v0-s3/product-gate0/independent-sequential-correction-02/run_once.py
python3 -B reports/v0-s3/product-gate0/independent-sequential-correction-02/run_diagnostics.py
python3 -B reports/v0-s3/product-gate0/independent-sequential-correction-02/assess.py
```

run_once顺序启动launch.py --mode focused --label independent-sequential02-focused --outdir <本独审绝对目录> --modules tools/test_v0_s3_supervisor.py --select "slot or reconciliation or sequential or finalizer"，再launch.py --mode guard --label independent-sequential02-guard --outdir <同目录>。launch在pre-import边界后runpy执行候选原runner，未传binding；完整argv/cwd/时间/真实外层returncode及stdout/stderr hash在focused.outer.json、guard.outer.json。run_diagnostics只启动本目录negative_probes.py，完整外层在negative.outer.json。

| 执行 | 结果 | 外层returncode | skip/限制 |
|---|---|---|---|
| focused唯一一次 | 25 passed、92 deselected | 0 | 0 skip；92不计PASS |
| guard唯一一次 | connect/bind/Popen/system四拒绝 | 0 | 实际fixture/runner句柄0 |
| 独立必要故障矩阵唯一一次 | 58观测保存，逐项assessment成立 | 0 | 合成counter/fakehandles，不是产品验收 |

独立outer_boundary.py在任何候选import前已装；候选安装后仍有独立fallback，候选hook的握手不由独审代答。仅允许已审测试内显式synthetic sys.audit事件，真实subprocess内部调用不在白名单；网络/真实进程始终阻断。诊断由前轮原独审脚本保留触发重建，原脚本/raw正式矩阵复制在references中；未执行作者反转Oracle、未复跑基准整套。没有fixture/服务/网络/模型/GPU/原ledger动作，没有带binding runner。

## 证据完整性及流程偏差（一次汇总）

作者原件只读复制于author-preserved/，全部文件清单和hash见author-files.json，receipt逐流核对见author-receipt-stream-checks.json。初期Oracle错误、反证脚本错误/崩溃、同名重定向覆盖均已披露，不能因后续通过而称旧字节仍在：

- initial-negative的原结果/流和outer保留，外层1；错误把未知退出剩余空槽也要求拒绝，属于探针Oracle错误，未构成候选缺陷。
- initial-baseline-proof.stdout.log保留11fail的运行内容；但initial-baseline-proof.receipt.json引用stdout hash `2e8d5f…`，现存同名文件hash `b694b3…`，不能视为原收据所指旧流完整。漏runner那一次stderr已被覆盖，作者报告文字和残存外层stdout不足以重造丢失stderr或旧真实外层退出；本独审没有补造。
- 初次focused receipt引用pytest stdout hash `ce77cd…`，现存同名文件为receipt输出hash `9d9c29…`，旧pytest stdout缺失，不据其宣称原始25项日志完整，也不补造缺失独立外层退出。
- focused-final的stdout/stderr与收据hash匹配，外层stdout保留；本独审新鲜focused25及必要矩阵也完整。最终baseline-proof的11fail原件及hash匹配，基准executor hash与git 4e99904 blob一致；仅只读核对，不把形状适配失败当全部语义反证。
- 作者自行删除env-only临时设置已有root恢复记录，此为作者清理偏差，不归为协调者清理、不另索人批。

以上探索/记录偏差已明确披露且新鲜有效证据完整，本轮不重复计为Major，也未形成待修候选Minor。作者报告“初版两次原件都保留”的宽泛语句须按上述明确缺失理解。

本独审生成探针时曾把构造脚本暂存/tmp/lvw-review-build.py，随后移入本目录build-probes.py；这是“只在独审目录新建”操作范围的一次短暂偏差，未修改候选/root/实现树、原counter或合同，不隐瞒为全程只写本目录。构造脚本未执行候选，候选导入只发生在独立guard内。其余持久新增均限本目录，无reset/clean/fetch。

## 绑定、风险与交接

initial.json在checkout前写入：HEAD=ac66247abf07f200a031e0c21c469cff470d218c、status为空，然后本实例checkout --detach到目标候选。所有源码匹配候选git blob，candidate-source-hashes.json绑定：

- executor.py：0565c967724fd1d921c342f6cac5b89541efa1c88596e845e877f64ac5ece818
- runner：da688b1502dcf625bbbf883c5e7e519d0c4c386a51fafa15539a69e2331d1005
- test_v0_s3_supervisor.py：e77be87bd0e3c1e6a2a6c4f3ed31dd204fbc6760785460ecf2ee8e42484bf840

原counter仅read_bytes：前后SHA256均39f2838e02c33b3903e4c9b23316242abe9e75e4e3592127238a88fa627bbe15；inactive、starts2、reserved120、spent2.896、2REFUSED_BEFORE_FORK、2SETTLED。initial.json与counter-after.json原件绑定，未写/退款/清零/消耗最后60秒。

F0依据是源码/合同/阈值/固定分母/预算未被更改，外层边界下实际fixture句柄0、原counter不变；不是对真实平台安全的认证。M0依据是上述原三种触发及必要组合均按实物证据成立；m0限定没有新的候选待改Minor。限制明确保留：真实13fixture、全I01–I24、Windows服务/后代/GPU/A06、真实QualityPhase、原ledger、产品十二项质量与人签全部NOTPROVEN，不能由合成58或focused25推导StagePASS。

十字段交接：1 当前R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION；2 本批三项独审关闭F0M0m0；3 最后通过仍621b1bf统一切片UM10范围内人签；4 当前真实运行及产品门禁未证明；5 路线见下；6 剩余root裁决及后续另绑定真实验证；7 下一责任人root；8 本轮无新增授权需求、不恢复旧binding；9 本目录review/receipt/raw/hash；10 审查完成等待归档回收，默认不keep-open。

完整V0–V3大纲（root当前control原件已复制）：V0-S0 1/2、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、V0-S3 0/6、R1 0/4、V1-M1 0/3、R2 0/4、R3 0/4、R4 0/4、R5a 0/4、R5b 0/4、R5c 0/4；V2/V3未激活，历史S0 NO_GO与S2未签保留。实现=只读候选复审；机器产品验收=未新增；独审=本轮有限范围CLOSED；人签=未新增。

本实例未派生或回收其它Agent（回收数0），未另行盘点项目所有窗口，不能猜存活数。worker_done后交root归档回收本窗口。
