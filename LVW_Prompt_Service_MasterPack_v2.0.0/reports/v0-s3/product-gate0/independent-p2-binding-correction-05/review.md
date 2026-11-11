# P2B correction-05 独立局部闭环复验

建议 root 接受本次局部纠正：**Fatal 0 / Major 0 / Minor 0；C04 M1 已闭合**。仅针对最终候选 `da6e7b5ed351baca3b74f003cfcf3622c4b382d6`、base `57373135ab629bcd08c429fd18477fb516c94dfb`，不签 Gate0、Stage、质量、人签或发布。本人未实现补丁；起始工作树干净，从 bf1767e fast-forward 到指定 tip，无冲突，仅追加本目录。

已读 AGENTS、治理README、执行索引/坐标、完整 C05 合同、allowance05、C04 公共 run 失败反例和 C05 交接。实际 child03 仍为 DRAFT_NOT_AUTHORIZED。未来 child 仅建议 root 在接受此局部修复后另行核对候选/合同绑定、有限预算及实际准入再冻结激活；本次不自动激活，也不复活旧 ID。

## M1 闭合证据与必要内部 schema

局部代码 diff 只涉及工具与测试。terminal 先发布 FINALIZING_NOT_PASS，生成最终确定 bytes/hash 并写 terminal-candidate.json，先写 shared/local 两份 EXPIRED 引用，再实际读回 staged bytes、身份、hash、artifact refs，最后 os.replace 发布 canonical cross-os-lifecycle.json。成功发布之后只有内存字段赋值及返回，没有可失败的持久化/验证将状态改成 BLOCKED。run 的 finally 返回与 CLI 成功条件均匹配。

lvw.p2b-terminal/3、lvw.p2b-consumption/2 的 result 固定 TERMINAL_REFERENCE_NOT_DECISION；消费文件自身没有 READY 决定。index 只引用初始 RUNNING claim hash，最终两消费 ref 指向 index hash，没有环。terminal_index_persisted 只代表最终返回决定索引已写入；terminal_persisted 是兼容别名，不能证明整组提交完成。finalization_proven 表示发布前两消费与工件已经读回核验；即使 PROVEN，status=BLOCKED 仍拒绝。接受必须 READY + 两引用身份/hash一致 + 工件一致，不能凭 flag 或文件存在。

独立 probe.py 保留 C04 的原 public maximum 入口与三 phase 图，使用真实 factory、双角色、admission、SQLite，仅 host/observer 边界是明确替身。在 run 已安装全部测试边界后，于 os.replace 注入实际 ENOENT：将指定写入送往本轮 owned 根中不存在的父目录，让内核产生真实 OSError。三个独立 probe 各运行一次，非重跑整个矩阵；错误源/目标/errno、返回值和最终三文件逐字节状态均在 directed-independent-probes.json，实际命令 stdout/stderr/exit 保留。

| 独立故障 | 返回 / canonical | shared | local | 最终一致性 |
|---|---|---|---|---|
| 共享 claim EXPIRED 永久失败 | BLOCKED / BLOCKED | 原 RUNNING tombstone | EXPIRED 引用 | UNPROVEN |
| local consumed 永久失败 | BLOCKED / BLOCKED | EXPIRED 引用 | 不存在 | UNPROVEN |
| READY 最后 publish 失败 | BLOCKED / BLOCKED | EXPIRED 引用 | EXPIRED 引用 | UNPROVEN |

三例原成功 oracle 均如期拒绝；无 canonical READY 与 return BLOCKED 矛盾，无消费记录自身成功决定，无 refund/unlink/重置身份。已持久 phase1、三阶段和 debit=1 保留。三个 staging 文件仍包含预备 READY，它们是非权威准备物，原始 raw 完整保留，不能当已发布成功，也没有为了“修正”审查而删除。

## 完整组合与逐项回归

仅一次最终完整受影响组合：**237 collected / 237 passed / 0 failed / 0 skipped，178.88s，exit 0**；collect 保存实际 nodeids，旧 227 全部保留，加新 10；结果及精确耗时见 receipt.json、combined-counts.json、combined-collection.json 和 combined.stdout。没有重演实现者中间 19 setup failures 或 18+1，也未运行无关全仓。旧内部字段迁移逐项见 oracle-migration.json 与 candidate.diff：九个旧 public nodeid/原阶段、debit、容量及 ref 拒绝义务保留；新增 local hash/EXPIRED、finalization_proven 约束；仅故障注入路径允许 RUNNING tombstone。原始实现失败 raw 不变。

本次新套件直接提供 transient/permanent shared/local/publish、shared-afterwrite、early-index 与 all-storage 十矩阵证据；不再重复第二遍。all-permanent 同时拒绝终态 cleanup detail 和全部 terminal 控制写，返回 BLOCKED，canonical 不存在，shared RUNNING，local 不存在，terminal_index_persisted=false/finalization_proven=false。该例明确是未证，不把局部失败替代全存储不可写，也不虚称已经落盘终态。

verify.py 从本轮文本 raw 独立重算每个 artifact bytes/hash、两消费身份/hash、初始 RUNNING claim 反向 hash、preflight hash；成功路径 22 refs、六份 160×4 observer（三 phase finish/finally）与三个 stdout 262144 bytes / stderr 256000 bytes，包含非UTF8内容，base64 字节及摘要全部可复算。每件 <=1MiB、终态 <=16KiB、整体逻辑字节 <=16MiB，容量详情在 verification.json。逻辑字节不冒充磁盘块分配或累计 I/O；metadata 1/32/32预留、不退额度、ESRCH/Unknown、双 fixture 角色、唯一 claim、retired ID 与 DRAFT 闩均由保留组合覆盖，不扩大重审。

## 边界、清理与已知限制

runner 在开始时即使用可序列化 metadata 和同目录原子替换落盘，collect 清单先写，stdout/stderr/exit 持续捕获；使用 -B、PYTHONDONTWRITEBYTECODE=1、owned basetemp、-p no:cacheprovider。每个新 fixture 删除前保留文本 size/hash inventory；组合及独立 probe owned 根与 fixture 清理均有记录。没有新增合成 DB/重复源码归档，所有新产物仅脚本、文本索引与必要 raw。

allowance05 固定源 hash 校验后仅一次系统 PowerShell -NoProfile -NonInteractive，固定 Parser.ParseInput 模板、30s、64KiB 命令/捕获；actual argv、exit、raw/base64 在 combined-parser.json。没有执行被解析源或 CIM。其它 .exe 与 /mnt/ 文件读取由 Python audit/Popen 拒绝，0 denial；这不是 OS 沙箱证明。0 actual Windows driver/WSL/host executable hash/真实 claim/母 ledger/历史 tmp/PID/媒体/GPU/模型/服务/network/download/checkpoint。原 actual execution02 丢失的证据不能由本次合成测试重建。

非阻断已知限制：进程崩溃或底层存储不可写仍可能留下 FINALIZING/缺少终态，必须 UNPROVEN；无自动恢复/身份重置。多文件协议不是事务性数据库提交，准备文件永不具备授权含义。固定 fixture 写入预留是有限调用图的保守包络，不是任意损坏数据库无限增长的保证。历史五 tar / 1145 条目沿用 C04 独审及 root 明示保留例外，本次仅复算压缩文件 SHA，未再遍历条目；其中 SQLite/源码快照历史仍保留，不称纯文本。本轮没有新增缺陷或重分类这些已知限制。

十字段：1 当前 R1/WP-R1-U3/S3_P2B_FINALIZATION_PUBLICATION_CONSISTENCY；2 本批局部独立复验；3 最近接受统一切片621b1bf范围不变；4 原M1闭合；5 目标V1，S2仍7/8；6 剩余root裁决与未来有限child；7 下一owner root；8 不新增人工请求、不激活actual03；9 本目录收据/raw/hash；10 独审完成，非产品签署。

V0–V3大纲（唯一 execution-control）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；当前 R1 0/4；V1-M1 0/3；R2 0/4；V2 R3 0/4、R4 0/4；V3 R5a 0/4、R5b 0/4、R5c 0/4。实现已提交，离线机器结果与本次独审分别记录；未新增人工或阶段签署。

本次最大成功链实测：detail 4513904 bytes，evidence tree 4523009 bytes，两 fixture 296290 bytes，合计 4819299 bytes。
