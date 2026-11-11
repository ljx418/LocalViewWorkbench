# S3-PREP-C correction-02 独立局部闭环复验

建议 **ACCEPT_TOOL_ONLY**，Fatal 0 / Major 0；原 IC-MAJ-01 触发闭合，原 MAJ-01/02/03 保持已闭合。本实例未实现补丁，仅新增本独审目录；最终裁决归 root，不签 Stage PASS、产品 Gate0、质量通过、人签或发布。

候选 `9fc71b9551959c351016939196056b98b25a8acc`，完整证据 tip `bc5c0145fce51fbb5204c7eaa2f976ff06be1fb3`，root 基准 `08daf12b87340eb5fcdd64c3d4444ee686ef712b`。初始 HEAD `d3b6d5e58f37b171c04add3a939350e078b65a51`、git status --short 空；git merge --no-edit 指定 tip 无冲突快进。候选/规格/执行控制/冻结身份 SHA256 详见 raw/bindings.json，局部完整 diff 见 raw/candidate.diff。

## 局部源码结论

MediaAdapter._run 先保留 on_result 中真实 exit_code、捕获 bytes/hash 和 error，再移除失败 frame 私有 payload。probe_video 在解析 JSON 前检查 error；extract_frame 在写文件前检查 error，无 budget 也适用。_prepare_video 同时防御带 error 的自定义 adapter 返回，不把 probe document 或 frame 文件当有效媒体。

VIDEO_PROCESS_OUTPUT_LIMIT 对 probe 触发不可清除的 probe_capture_limit_exceeded，终态 PREPARATION_FAILED_PROBE_CAPTURE_LIMIT_EXCEEDED；prepare 的外层 BudgetStop 停止剩余源，清理不会清除 accountant.failure。这里是 stdout+stderr 合计 4MiB metadata 捕获上限，未声称 80MiB preview 媒体预算超限。真实 exit0 保持在日志而 CLI 因失败返回1。原 ffmpeg 输出上限仍映射 output_budget_exhausted，timeout 仍映射 wall_budget_exhausted；普通损坏媒体非零退出的拒绝语义、正常 probe/frame、采样/渲染算法不变。

## 一次完整套件与独立反例

精确套件命令、环境和临时根见 raw/suite-command-cleanup.json：PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tools/test_s3_sample_preparation.py -q -rP -p no:cacheprovider --basetemp=/tmp/s3-independent-correction-suite-2k4qrj47/pytest。本轮只执行一次，**77 passed in 21.68s，exit0**，stderr 空。原 71 项整个测试文件是新文件逐字不变前缀，新增 6 项；原函数/辅助/oracle 全保留。四个显式 runner error（probe/frame × 有/无 budget）、正常对照、timeout 与旧 output 语义复用本次套件证据，不再重复完整套件。

自写 raw/probe-overflow-owner.py 从本人原 owner 反例适配，用现有合成 Package 辅助准备两个源与 CLI 参数，只将授权/绑定 guard 限于合成包；真实 adapter、run_bounded、pipe reader 和错误传播均未替换。frame 设拒绝钩子并计数，第二源独立计 resolve/stat/hash/decode。记录的 CLI 为直接 command_run 公共处理器返回码，不冒称另外启动了 CLI OS 进程；驱动自身 exit0 表示断言成功，不是准备工具成功。

|独立变体|真实 probe OS exit|runner error|CLI return|捕获 stdout/stderr bytes|frames|第二源 resolve/stat/hash/decode|
|---|---|---|---|---|---|---|
|合法 JSON + stdout 超限|0|VIDEO_PROCESS_OUTPUT_LIMIT|1|4194304 / 0|0|0 / 0 / 0 / 0|
|合法 JSON + stderr 合计超限|0|VIDEO_PROCESS_OUTPUT_LIMIT|1|112 / 4194192|0|0 / 0 / 0 / 0|

两次实际终态均 PREPARATION_FAILED_PROBE_CAPTURE_LIMIT_EXCEEDED，sticky_failure 均 probe_capture_limit_exceeded，第二源 not_run。捕获后的 JSON 仍合法，独立重新计算捕获 bytes 的 SHA256 并与 adapter 一致，说明拒绝来自 runner error 而非 JSON 偶然损坏。完整 argv、真实 returncode、error、capture limit/bytes/hash、receipt、PID、wait 观察、CLI stdout/stderr/exit 在 raw/probe-overflow-owner.json 及 stdout/stderr.cli.*；驱动 stdout/stderr/exit 另行保存。大块捕获空白未重复存储，精确内容由驱动 payload 及长度确定，hash 已实测。

为有界选择短子进程实际退出后读取状态的时序，Popen 仅包装 poll：在真实 reader 启动后 process.wait(timeout=2)，再调用原 poll；没有赋值 returncode，没有改 production runner，没有 mock reader error。每次 poll 的实际 wait/poll 返回及耗时均记录。两变体本轮首试都得到真实0，没有 -15 试次。本证据证明该时序下原漏洞闭合，不声称自然调度必定 exit0。

实现者保留的历史也已核对：draft matrix 4失败/2通过（缺 Image 导入），first matrix 6通过；first suite 76通过/1失败，原始 assert -15 == 0 保留；最终 matrix 6通过、suite 77通过。-15 那次能证明 error 被拒绝但不满足 exit0 重现条件，不能拿它充当目标成功证据。其最终 poll 包装与本轮同样等待真实退出，不改 reader；补跑及原因已披露。本人未重跑其历史套件。

## 清理、身份和剩余边界

独立两次 probe 的 Popen returncode=0；os.waitpid 抛 ChildProcessError 证明已 reap，cleanup child 也 reaped，staging_removed=true，两个自有 TemporaryDirectory 均实测不存在。完整套件临时根清理前3778 entries/2712 files/48785610 bytes，清理后不存在；只清理本轮 owned 根/句柄，没有扫描或操作其它进程。全部命令 raw 在本目录，执行结果保留。

base→tip 改动仅两工具与实现 correction-02 证据；contracts/plans/stage packet/manifest/冻结集/旧独审历史/原 run 无 diff。底层 runner 字节未改，三个 render 函数 AST 与顶层常量保持。冻结16=10+6、原预标 hash 与原成功 receipt 身份核对完成，旧 receipt 逐字匹配 `335a8b973ab9b0fe192c03f59e608f9976658238`，preview 来源仍 `e1798f33ba51dcadbf9f0333641d62d14a801491`，没有重绑新候选，也未访问 preview 或真实源。

本轮0真实 testSource/旧 preview/新真实 child/模型/GPU/服务/网络/下载/产品完整 checkpoint；有合成 CPU 子进程。零动作据执行路径，不宣称完整 OS 审计。Linux/WSL 工具限制及 L02–L07 已披露非阻断限制继续保留；信任 decoder 不产生脱离子孙、pipe cap 限保留buffer而非总内核流量等原边界不扩大。没有新具体可复现阻断，不建议风格重构。

十字段：当前 R1/WP-R1-U3/S3_PREP_C_RUNNER_FAILURE_PROPAGATION_CORRECTION；本批完成独立只读审查/77套件/2个目标反例；最后通过门禁统一切片UM10及范围人签；当前工具IC-MAJ-01建议闭合待root裁决，产品Gate0未通过；全局路线S3→V1准备；剩余root工具裁决和产品Gate0；下一责任人root；本范围无需新授权；证据目录本 independent-correction-02；停止原因本次限定独审任务完成。

完整V0–V3大纲及实现/机器/独审/人签四权状态按 execution-control 原样保存于 receipt.json，未增加任何产品完成数。当前Stage R1。

|阶段|交付|已完成/总数|
|---|---|---|
|V0-S0|V0|1/2|
|V0-S1|V0-Min|5/5|
|R0|V1前置|1/2|
|R1a|V1早期切片|5/5|
|V0-S2|V0.1|7/8|
|V0-S3|V0.2|0/6|
|R1|V1|0/4|
|V1-M1|V1|0/3|
|R2|V1|0/4|
|R3|V2|0/4|
|R4|V2|0/4|
|R5a|V3|0/4|
|R5b|V3|0/4|
|R5c|V3|0/4|
