# S3 集成离线合同 01：有限接线、父监督、残留与十二项汇总

状态：冻结内部实现合同；只准离线开发和零进程定向测试。有限 Python fixture 进程执行另须本合同的机器绑定门禁；不激活真实产品运行。承接已接受 P3B `6c9a0a07c66060e53b00e690ebdd98047167511d`、独审 `eda30de5655e6262061ce658aeb33044f0a068e9`。旧草案/旧候选为历史，公共产品合同、分母和当前 V1 Stage 不变。

## 范围、唯一 owner 与顺序

一个集成 Workpack（S3-P4-OFFLINE），A/B/C 连续实现，一次交付与集中独审。

| 实现段 | 唯一职责和文件 |
|---|---|
| A | `tools/v0_s3_coordinator.py` 的 S3InstalledRuntimeFactory 继承已接受 InstalledPackageRuntimeFactory；`tools/v0_s2_stage_runtime.py` 仅加默认无效果的 profile 参数 hook，不改已接受 P3A owner |
| B | `tools/v0_s3_supervisor.py` 掌握原始 worker 句柄、固定截止和有界协议；`tools/v0_s3_quality_worker.py` 是固定生产 worker 入口，实际调用 QualityPhase；不执行传自 worker 的父 Python 回调 |
| C | `tools/v0_s2_runtime.py` 的受控视频残留 accessor；coordinator 的父原件证据封存/校验和十二项汇总；不复制旧 phase、authority 或 archive |

测试文件固定 `tools/test_v0_s3_integration.py`、`tools/test_v0_s3_supervisor.py`。唯一新受控子进程 fixture 是 `tools/fixtures/v0_s3_supervisor_fixture.py`，枚举场景，不是任意 Shell/Python 执行平台。新文本收据在 `reports/v0-s3/product-gate0/implementation-integration-01/`。P3B 质量模块只允许添加默认关闭的进度 sink 及准确插入点，不改验证/评分/阈值/保留上限/原始证据；若无需 hook，保持文件不变。

## A：首次 profile 接线

S2 `_profile_binding_parameters(*, root, label, baseline)` 默认返回空字典，现有 S2 调用及 profile 字节语义保持。S3 子类要求已绑定的 provider，返回唯一允许增量键 `s3_budget_binding`；在 `_prepare` 第一次排他 write_native_binding/write_warm_binding 时传入，不先写 LOCAL01 再覆盖。不新增 authority/debit 实现，复用 program_budget 的 validate_config/load_binding/s3_profile。

provider 结果须绑定准确 run/candidate/child SHA、原 authority/ledger 身份、tool/source/expiry；缺失/错 run/candidate/child/authority/ledger 皆在首个模型发送前拒绝。生产完整 profile/账本准入仍由现有已接受 owner 负责，不能把形状检查替代真实原账本验证。只在 fixture 中构造虚拟身份；真实账本本包禁止访问。

## B：父监督合同

父方只从已封存命令计划启动 worker，持有原始 Popen/process handle 和出生身份；不得用子进程自报 PID 授予终止权。生产入口只启动固定 quality_worker，不能以 fixture 路径或动态 import/任意 argv 代替。worker 只重建已绑定数据上下文，不反序列化 Python callback。NativeRuntime 的真实服务/后代 custody 与父独立清理未证明时，真实准入拒绝，不以终止 Python 当作 Windows/GPU 已释放。

协议为 UTF-8 JSONL，schema `lvw.s3-supervision/1`，闭合键：schema/run_id/candidate_sha/authorization_sha256/sequence/event/payload。sequence 为严格递增整数，所有身份精确匹配；事件仅 STARTED、ROW_STARTED、HISTORY_WAIT_STARTED、ROW_FINISHED、PROGRESS、TERMINAL。row 事件绑定预先封存的16行 asset/ordinal；每行历史开始仅一次，进度不能重设截止、换样或制造结果。TERMINAL 仅携带已绑定根内 canonical receipt 的相对引用/长度/hash，不能把内存 PASS 当原始结果；父读取实际 bytes 验证。

父 phase 截止从启动起固定10800s，历史等待从该行首次 HISTORY_WAIT_STARTED 起固定600s，均取 child 剩余期限更早值（真实 child 最大21600s）；超限不延长。父循环不能调用可能阻塞的 observer/fsync/worker callback。测试可注入缩尺 deadline，生产默认值不能改；阻塞 callback/持久化必须实际停止所持有的 fixture 进程，不是返回 timeout 文本。进度 sink 如需新增，只在 worker 内发送协议，历史开始必须在可能阻塞的真实历史等待前发出。

父记录完整16行计划后才允许发送，工作未开始保留 BLOCKED，发生后不明记 FAIL/UNKNOWN，分母不缩水。异常、超时、失联、协议越界撤销后续动作，有限协作取消后仅终止原持有 worker；真实服务清理另核验原 PID/birth/HTTP/sampler/GPU，无法证明则保留原根和预约、不归档、不继续下一 phase、不退款或自动重发。恢复入口只协调清理及已有证据，不重放推理；没有原 custody/看护证据时保持 BLOCKED，不根据磁盘自报 PID 杀进程。真实父崩溃保障未验证则明确保留 NOTPROVEN。

每条消息≤32KiB，≤1024条；每个 stdout/stderr≤256KiB，新增文本证据≤8MiB。有序终态唯一；重复/乱序/额外字段/非有限数/坏身份/坏引用/超长/提前退出/未决 I/O 均稳定拒绝。证据必须保留实际退出、截止、动作计数、清理、失败与源绑定。

## 父原件证据与 C

父在 worker 发送前封存 run/candidate/child、16行投影、root identity、实际源 hash/bytes；终态后父在自己掌握的根/证据目录独立保存 canonical/source-plan/raw 的长度/hash 清单。worker 不能仅改其内存返回值来替代该父清单。对被选择的原根重核所有绑定；父原件清单缺失/外来/变更拒绝。QS 仍在原绑定根存在时读取/独立评分，随后交既有 OwnedArchive；归档后逻辑根迁移若未接通，明确 BLOCKED，禁止改写旧 run_root、拼接别轮或声称任意 archive 可信。无需新密码学签名平台。

NativeRuntime 增加 `bind_video_snapshot_root(run_root)` 和只读 `video_snapshot_residue()`；S3 工厂在自己已验证的根上绑定一次。根须等于工厂 evidence 的 owned_run_root，根/temp 原始身份重核；未绑定、缺根、替换、匹配项 symlink/reparse、I/O、超限均 UNKNOWN/异常，不能返回假空。只枚举该 temp 第一层的 `lvw-video-*`，不跟随链接、读取外部内容或删除任何文件。每次最多观察512个第一层条目、最多256个残留名；exact/one-over 验证内部资源边界，不宣称 native Windows 已测。空与清理后为空分别留证，不能改写为从无残留。

S3 汇总固定 V0-A01…A12 十二键；旧 S2 九项和45+20发送是既有 phase 事实，不能等同新十二项 PASS 或完整总账。复用原 phase/安装/归档 owner，质量16行、WebP格式补项、A06、安装回滚和每个阶段绑定分别登记。缺任一原始必需收据/独立评分/真实隔离或清理，保持 NOT_RUN/BLOCKED/FAIL。所有本包输出 stage_pass_claim=false；没有真实准入不得调用真实 sequence。代码可以组合但不能用 fixture 收据给产品计 PASS。

## 固定离线验收集合（24项，全部初始 NOT_RUN）

I01 默认首次 profile 接线；I02 warm 首次接线；I03 缺失/错run/candidate/child拒绝；I04 原 authority/ledger 身份拒绝；I05 默认 S2 保持；I06 复用真实安装工厂；I07 实际 QualityPhase worker/16行/原始终态组合；I08 阻塞 callback 实际终止；I09 阻塞持久化实际终止；I10 history 固定截止及重发不延长；I11 phase/child 最早截止；I12 协议重放/错序/超长/假身份拒绝；I13 异常退出/失联/未决I/O；I14 清理失败保留根预约；I15 恢复不重发/不信自报PID；I16 父原件清单与选根绑定；I17 残留空/存在/缺根/读取失败；I18 残留超限/替换/符号链接；I19 十二键完整且旧九项不能补绿；I20 无独立质量分不能通过；I21 P3B新增hook的必要回归；I22 零真实模型/账本动作；I23 源/工具/fixture/预算拒绝；I24 原始退出/实际停止/清理/候选绑定。

每项建立生产入口→测试驱动→Oracle→负例→终态→清理映射；不能用常量/名称存在、exit0独立证明。此24项只用于新离线集成，不替换产品十二项或旧门禁。

## 有限 CPU fixture 准入（当前尚未开放）

沿用 COMPLETE03 已批准的离线代码验证，0产品模型动作/0真实完整checkpoint/0真实服务。候选、supervisor、worker、fixture 与工具实际 hash 未冻结前，所有测试继续使用零 subprocess/network 的 pre-import guard。实现者先完成代码及静态计划，以 Orca ask 提交精确文件/哈希/argv/进程场景，root 自动核验并签有限机器绑定；不是新人工授权，不可凭本合同直接运行进程。

只有 `s3-integration-python-01.binding.json` 的 Linux Python、固定 `-I -S -B`、已冻结脚本/场景和明确依赖路径可准入；无 shell/WSL/PowerShell/native exe/网络/浏览器/FFmpeg/GPU。fixture 子入口自身在任何产品导入前阻断网络和后代进程。实际 QualityPhase/Pillow 需要的已有依赖路径须显式绑定，不下载或靠隔离模式隐式信任环境。

整包最多24次 fixture 启动（实现≤16，独审≤8），最多并发2、每次≤10s；含进程的验证累计墙钟≤180s，最后30s只清理。真实句柄、启动/预算收据与退出持续绑定，未知不放大预算或重启。每个执行候选/脚本变更须重新封存实际 hash；共享计数不能清零。根/fixture/argv未审定时 root 不发执行 ACK。guard selftest 不启动真实进程；新进程白名单不得反向放开 P3B 旧零进程运行。

## 出门及后续

实现者 READY_FOR_REVIEW，隔离独审复算，root 集中裁决；不机械重跑 P1/P2B/P3A/P3B 全套，仅对实际 hook/接线变更跑必要回归。A06实机权限/隔离、原生服务后代/GPU释放、注册表驱动的安装前和回滚后基线、原账本 debit、最终A/B预算及新鲜真实12项/质量/人签仍阻止产品 Gate0。FIRST Claude429立即停止，不重试/换路由/自动接手。
