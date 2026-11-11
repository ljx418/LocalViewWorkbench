# S3-P2B 独立审查：工具需纠正，实机部分完成，生产 NO_GO

候选 `34de7b54a529a8947d63736c6f1bd345828cad57`；证据 tip `210fb1e130ac749e9537bda895472b7a3b5101f9`；root `7e33e6112d9df330ef4385773e41072a7c2f5469`。审查者未实现候选。起始工作树干净，`git merge --no-edit 210fb1e130ac749e9537bda895472b7a3b5101f9` exit 0，从 f5b63a0 快进，无冲突。已读 AGENTS、治理入口、执行索引、execution-control、完整 P2B 合同/child、implementation-p2-binding 全部原始文件及 P1 独审边界。

**代码 Fatal 0 / Major 2；工具 CHANGES_REQUIRED；真实 P2B PARTIAL / NO_GO_FOR_PRODUCTION。** 原 worker outcome=failed 保留，不能由 batch exit0、READY_FOR_REVIEW 字段或本次 167 项绿测覆盖。独审任务完成不等于候选通过。未签产品 Gate0、Stage、质量、人签或发布。

## A：一次性汇总可复现缺陷

| ID | 位置/复现 | 影响与最小修正 |
|---|---|---|
| P2B-M01 Major | `tools/v0_s3_runtime_binding.py:123–139,209–219`：唯一消费依据是 checkout-relative BASE 下 consumed.json。`probes.py` 在两个新 owned 合成 root，用相同 child 字节/hash 和 candidate，均 preflight→run→EXPIRED；原根重入正确拒绝，但换根再次消费成功。探针模拟 Git identity 和不存在的合成工具路径，实机启动及额外 debit 均0；不是重用旧 child。 | 原合同明确不得改路径取得第二轮。复制相同候选的干净 checkout 时 ROOT/BASE 自然改变，而 child 不绑定唯一消费 owner；源 hash 与 HEAD 并不解决跨根 replay。需 root 冻结 child 身份→唯一消费登记位置，跨 checkout 共用原子 claim；输出目录只能是该 claim 的属性，不能是容量 authority。不要求修改真实 model ledger，也不允许本审查实施新平台。 |
| P2B-M02 Major | `tools/v0_s3_runtime_binding.py:285–294`：finally 中 `owners()`/`meter.check()`可在终态落盘前抛错。探针只注入 wall-budget 异常，实际得到 consumed=RUNNING、无 cross-os-lifecycle；保留 stdout/exit。 | 必须在预算超限/观察失败时仍写有限 BLOCKED/UNKNOWN terminal、消费状态及保留根；终态写入不再依赖成功通过预算检查/owner 观察。现有 consumed 文件仍阻止同根重入，所以这不是退款或已证实重复扣额；缺陷是必需终态证据被异常跳过。与 M01 一并修复，禁止凭 RUNNING 新建同 child。 |

以上为本次代码 Major 的完整集合。统一计量与 Meter.run 管道判定应随有限 owner 纠偏强化：meter仅计外层stdout/stderr，内部结果JSON未计；外层循环只跟随直接进程存活，join失败没有独立失败条件，driver判断只检查exit_code。现有实机线程/pipe均已闭合，未把这些静态弱点冒充本批真实泄漏或新增已复现 Major；下一冻结方案须以全部管道闭合和错误优先作为终态准入。

安全边界核查：wsl-fixture 客户端 `_command` 要求实际 Windows，发行版固定 Ubuntu-24.04，根必须 /tmp/lvw-s3-p2b-*，精确 UNC 大小写/中文空格映射；load_binding 要 marker，shim 要 tempfile 下原 ROOT 及 ledger.resolve 在同 fixture 根。生产 profile 明确拒绝 wsl-fixture，wsl/local-wsl 原库 samefile 分支未放宽。schema 仍 lvw.s3-budget/1 精确键集，仅内部 transport 增枚举；没有任意argv/HTTP服务/journal参数/kill API。请求 UUID 先 canonical 校验，owner 文件在已校验 ROOT/.s3-owned-requests 下独占创建，拒绝目录 symlink，记录 request/binding/PID/birth；RETURNED_FROM_AUTHORITY 由 finally 写入，并不等价成功，必须看真实回执。

源码、child、tool、execution、approval、有效期、model/hash/nonce 全量匹配；process error优先，无exit0回退、重试、退款或settle0。`authorize_model_action` 与 `decode` 相比 P1 root **逐字节不变**（函数 hash 见 fingerprints）。local_program_authority/core、P1两份测试及旧业务接线字节保持；改动只在两处获准客户端/shim、新harness/test及实现证据。固定九个路径不扫描模型/私有数据；版本命令不启动服务，不导入torch。安装 hash 在 run 内 discovery 后、命令前 installed-seal 封存，初始 preflight 只有路径和源码 hash，应如实描述两阶段，而非声称预先已知安装二进制 hash。

## B：原实机证据能证明什么

| 义务 | 已证明与保留缺口 |
|---|---|
| 正常跨 OS | Windows Python 3.12.10 实际 os.name=nt → 固定 wsl.exe → Ubuntu-24.04 /usr/bin/python3 3.12.3 →候选 shim；正常 UUID a3c9bd41-19b3-48e6-8368-3ef585bc2764 全量回显，合成SQLite calls=1，0模型send。实际中文空格和UNC通过；大小写变体拒绝仅合成。不是生产原库扣额。 |
| 拒绝 | 实机坏 binding hash 在客户端拒绝、缺 child 的 wrapper exit1；均0send。正常 wrapper PID27240、缺child PID19396、超时 PID28452 有 Windows creation time。stdout/stderr有hash、退出值、pipe_closed=true、三个线程false、reaped/joined=true。 |
| 超时 | timeout request d47e558a-78b0-4f94-a7d6-b21c5514babe 的 wrapper 实际 TIMEOUT、exit1；外层 Windows driver 捕获异常后 exit0。这两个 exit 值对象不同，exit0不是请求成功。外层直接 driver PID1666078 是Linux interop观察身份，不是Windows Python native PID。 |
| remote | 正常 shim PID1666044/start4877478，正常记录 RETURNED_FROM_AUTHORITY，随后不同birth/不存在。超时 shim PID1666148/start4877530 在 elapsed=1.001864s 仍同birth活着、state ENTERED；外层9.578212s退出，所以预设11/13/19s采样未发生。最终观察在20s锁释放timer.join之后，记录同birth不存活；既有最终消失事实接受，但不能推出10s边界立即清理、自然退出、成功扣额或远端exit code。未重新读取当前进程状态。 |
| 保留 | timeout UNKNOWN_RETAINED，累计已观测calls=1；不把此值当超时请求结果。fixture `/tmp/lvw-s3-p2b-中文 Space-v3m0dsi2` FAILED_RETAINED 和 reservation 全部保留，0远端kill、0退款、0settle0。本审查仅对登记fixture文件做有界stat清单，无SQLite查询/事务/authority调用，也无旧进程信号。 |
| 坏回执 | **真实跨OS坏回执未跑**。P1不变函数在相同Windows实机正常路径已实际执行全量echo比较；平台无关部分由本次预先允许的27个三入口×九故障回归支持，其中wrong_nonce/bad_json/lost_receipt/exit0-error是明确替身注入，真实Linux合成shim先扣后篡改，0send且不退款。不能把这些叫Windows坏回执实测。 |

## 预算与证据充分性

原始 wall=21.303025s，最长直接命令9.578212s，内层授权timeout<=10s，均在本次限额内。9个固定metadata文件共169,955,221字节是输入hash读取，不是输出；存在/hash/realpath/版本区别保持，Comfy/Ollama版本字段null不补造，metadata不代表完整依赖锁或真实Comfy可运行。

**owned启动保守上界28<=64**：7条外层直接命令 + 3个wsl wrapper + 3个shim=13；再保守加3个Windows Python native对应进程（Linux interop PID可能已含表示，宁可重计）、batch owner 1及其git 2、成功preflight owner/git 3、前置零访问失败的preflight/run owner/git 6，共28。依据固定源码/Popen/原始命令记录；库方法不spawn，timer/drain是线程。此为任务owned显式启动和native对应上界，**不是捕捉所有WSL系统服务/隐式后台进程**，原合同无需整机服务普查；若root另定义包括全系统间接活动则该不同口径UNKNOWN，不补造历史测量。

**输出保守上界16,130,808<16,777,216字节**：7×2×1MiB外层buffer + 3×2×32768内层buffer + 已登记fixture全部文件124,958 + 提交实现证据全部80,602 + 1MiB余量覆盖被覆盖的normal/result/plan/owner JSON及SQLite瞬时journal。源码固定少于16次此类写/事务，每次64KiB足够覆盖固定小JSON和该单row 12KiB库；最终目录无pycache，复制源码也计入。该界故意重复计日志与序列化收据，比实际stdout/stderr3880更保守。audit.stdout记录初始15,082,232上界，output-bound-supplement明确记录随后静态余量，不回写过去测量。此计算证明已知批次输出容量够，不声称现有meter已统一强制所有写入；未来owner仍需统一计量。没有因169MB输入误判16MiB输出超限。

全部实现证据 manifest hashes一致；候选与tip源码相等；来源及hash见 fingerprints。脱敏preflight的hash与raw preflight hash自然不同，不能直接用脱敏字节声称验证raw链；已有receipt保留raw hash，独审验证脱敏证据自身manifest与源码绑定，不称重新读到原执行root所有raw字节。原child已消费EXPIRED，零访问预检失败与其后的唯一实际batch严格分开。

## 最小缺口、下一动作与授权

生产运行前必须先修 M01/M02 并独审有限owner；P2B不是生产协调器，真实原库身份绑定、生产服务/断外联/原workflow/质量等仍由后续准确合同冻结，不能从fixture通过扩权。

原合同要求owned身份和退出证明：本批正常/超时远端最终消失已证明，不应为“取得独立远端数字exit code”单独再开批——该数字及整机服务普查不是额外原合同硬门限。真实缺口是缺少timeout边界至最终消失的有界观察链和Windows Python本体native身份，无法把当前证据用于生产超时回收保证；真实坏回执场景也未满足原冻结生命周期案例。若root接受不变echo代码＋实际正常同路径＋合成故障作为坏回执平台无关充分性，可明确裁决该窄项，不得写实机已跑；否则在下次集中补证。

建议一次集中纠偏，先root新freeze最小owned request生命周期合同，**本审查不实现cleanup**：同一绑定root与request UUID确定journal，Windows driver启动即记native PID/birth；wrapper返回时与短有界deadline内采样对应remote PID/birth，记录单调时间、pipe/thread与最终缺席。若仍存活，仅在root明确冻结精确root/request/PID/birth重核协议后允许该request的有界回收，unknown保留reservation/FAILED_RETAINED，不要求整机进程平台。正常、缺child/hash、坏回执helper和超时在同一新batch完成，helper明确不是生产已扣额shim；失败终态仍消费。

需要新有限child（建议 S3-P2B-CORRECTION-01，仅root派生，不复活01）：绑定修正candidate/contract/hash、唯一共享消费owner、安装路径/seals与输出根；batch1、wall<=1200s、owned<=64、单命令<=30s、输出<=16MiB、合成debit<=16，真实ledger/model/media/服务/GPU/network/download/checkpoint全0。优先复用现存metadata证据，若需重验安装hash必须在新child明确列项，不以本报告启动发现。无需再让人类批准同范围CPU动作；只有新cleanup能力的精确合同由root定夺。旧批次状态永不改为通过，任何无法补算的历史budget记UNKNOWN/NO_GO。

## 定向验证、清理与交接

`run_checks.py` 各一次：实现者原三文件范围83 passed，另七份P1/旧回归84 passed；不是全仓或verify_pack。`checks.json`有完整argv、cwd、exit0及耗时；check-1/2.stdout/stderr原样保留。独立 `probes.py` exit0，合成Git/工具故障注入，仅控制流复现，不是实机；新TemporaryDirectory均验证删除。`audit_evidence.py` exit0，仅源码/登记证据读取及fixture文件大小；audit补充计算不是重跑。新目录外没有修改，旧FAILED_RETAINED未删。

十字段：当前R1/WP-R1-U3、S3_P2B_FINITE_WINDOWS_WSL_BINDING；目标为独立审查；完成代码/原始证据/167定向测试/聚焦probe；修改仅本独审目录；合同分母未变；验证见checks/probes/fingerprints；缺陷F0/M2；实机仍部分完成NO_GO；本审查真实模型/母ledger/媒体/preview/GPU/服务/network/download/完整checkpoint/新实机batch均0；下一责任root集中裁决和冻结，当前停止原因是独审交付完成而候选未过。

完整大纲来自execution-control（附outline-snapshot）：V0-S0 1/2历史NO_GO，V0-S1 5/5，R0 1/2，R1a 5/5，V0-S2 7/8（旧人签未补），V0-S3 0/6；V1 R1 0/4、M1 0/3、R2 0/4；V2 R3/R4各0/4；V3 R5a/R5b/R5c各0/4。V1-D0准备2/2、统一早期切片3/3保持既有有限机器/独审/人签，当前产品Gate0仍阻塞。本报告不增加任何阶段完成数。

独审 task_d2dd595f2099；作者 ljx418 <1173696783@qq.com>。
