# S3-PREP-C correction-01 独立闭环复验

建议 **CHANGES_REQUIRED_TOOL_ONLY**：Fatal 0 / Major 1（本轮新发现的剩余边界缺陷），原 MAJ-01/02/03 的原始反例均已闭合。root 最终裁决；不签 Stage PASS、Gate0、质量通过、人签或发布。原成功预览仍按原身份复用，此发现不声称旧真实 run 曾超限。

审查候选 `eef2fe8fc4afc8fc737643185fcd2789f1103195`，完整证据 tip `f409d8c85359b51ce5abfa27fec6e9ae9a1d4da2`，root 基准 `bee7b345eafb2327b77520664949169d31e055c3`。初始 HEAD 700cef748c57ba79be0ad686ca67a10cce589644，git status --short 空；指定 merge 为 fast-forward，无冲突。实现和审查实例分离，未修改候选。唯一新增本目录。候选/规格 SHA256、完整只读 diff、原 45 个测试名见 raw/bindings.json 与 candidate.diff。

## 一次性阻断汇总

**IC-MAJ-01 — probe runner 失败在 exit=0 时仍被接纳。** `tools/s3_sample_preparation.py:1013` 仅对 kind=ffmpeg 的 VIDEO_PROCESS_OUTPUT_LIMIT 设置黏性失败；probe_video 在 :1030 仅看 exit_code，忽略 entry.error。因此短命 probe 已退出 0，但 reader 发现 stdout+stderr 超限时，run_bounded 依约先 on_result(returncode=0)，再抛输出限制错误；adapter 仍解析被截断但语法合法的 JSON，owner 继续帧提取并计 eligible。

独立真实 owned Python 可执行文件作为合成 probe，输出合法容器 JSON 后跟超过 4 MiB 的空白。未替换 runner、未伪造 returncode；frame adapter 仅合成 8×8 JPEG，未读取真实视频。raw/probe-overflow-owner.json 实测：probe_exit=0、probe_error=BridgeError:MEDIA_LIMIT_EXCEEDED:VIDEO_PROCESS_OUTPUT_LIMIT、frames_after_failure=4、eligible=1、decision=PREPARATION_COMPLETE_READY_FOR_REVIEW、sticky_failure=null；输出 metadata=4,202,311、累计媒体/index=17,784 bytes。脚本 exit0 的含义是成功复现缺陷，绝非工具通过。前一个 raw/probe-failure.json 已单独确认错误与有效 document 同时返回。两次均临时根实测消失。

建议局部修正 adapter：runner 有错误时一律不得以 returncode=0 接纳结果；probe 输出限制也须传播明确失败并停止后续媒体工作，保留错误日志。补覆盖“正常 OS exit + reader 输出超限 + 可解析截断 JSON”的 oracle。该项是本轮新定位的未覆盖控制流，不声称由此次补丁首次引入。无需平台重构或真实媒体回归。

## 原三项闭合与独立观察

- **MAJ-01 已闭合原触发**：大小变化、文件消失、同大小 hash 变化、读期间追加四种自写负例均 SOURCE_CHANGED_TERMINAL；第二源 resolve/stat/hash/decode 各 0、NOT_RUN。读期间负例真正包裹读取句柄，在首块读出后改变 synthetic 源，触发 fstat 身份比对，不只是预制异常。套件另覆盖 CLI 非零、inode 替换、hash 后消失。路径策略拒绝仍与源漂移区分。
- **MAJ-02 已闭合原触发**：probe 或第一 frame 把时钟推进至 1200/1201，调用序列分别只有 probe 或 probe+frame，全部 BUDGET_EXHAUSTED。独立实际 CPU sleeper 分别替换 thumbnail/sheet/index，经真实 fork render 限时退出、reaped，owner 不报完成。真实 owned decoder sleeper 获得小于 .08 秒的剩余 timeout，returncode=-15，第二次调用未启动进程。套件真实验证 frame timeout=min(45,剩余10)，最终 exact=1200 可完成、1201 必败；UTC started_at 与单调 elapsed 分离。
- **MAJ-03 已闭合原触发**：合成 padded staged frame 在 100000 预算下写出 100634 bytes，立即拒绝、无后帧，staging 清理后 sticky_failure=output_budget_exhausted 仍在，retained=0 不能洗成成功。这是用不受限 fake adapter 重现旧反例；真实 adapter 使用 pipe cap。独立 video owner 基线与 exact/one-under 总预算覆盖 staging+thumbnail+sheet+index，exact 完成、少 1 byte 拒绝且累计写入不超过 cap。RLIMIT_FSIZE 实测预先 charged staging128、剩余896，逐字节 flush 写入 exact896 成功、897失败且磁盘仍896；parent RLIMIT 不变。真实 owned stdout flood 捕获最多1024、黏性拒绝、没有 frame binary 写入日志。真实非零退出7的 decoder 即使输出有效 JPEG 也未写 frame。剩余的 probe 失败漏洞单列 IC-MAJ-01，不能据这些局部闭合宣称整个输出失败链已通过。

## 测试、命令与清理

一次完整套件：`PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tools/test_s3_sample_preparation.py -q -rP -p no:cacheprovider --basetemp=<owned TemporaryDirectory>/pytest`，**71 passed in 21.51s，exit0**。未重复全套、未运行 verify_pack。原测试模块完整字节前缀保留，45 个 test 函数及其辅助/断言没有删改，新增参数化项使收集数为71。独立20项聚焦观察不是71项的替代；另有2项 probe 失败观察。

命令、stdout/stderr/exit 见 raw/run-suite.py、suite.*、probes.*、probe-failure.*、probe-overflow-owner.*、bindings.*。首版自写审计钩子把 multiprocessing 打开的整数 fd 当路径，造成4个 cleanup child 报错；整套原始 draft-* 保留并明确无效于清理证明。修正本目录探针以允许 fd 后执行20项聚焦探针一次，最终 stderr 空，所有 owner staging 删除/cleanup child reaped；不重跑71套件、不改候选。首版 TemporaryDirectory 最终亦清理，未留历史残余。

套件清理实测与前后根路径见 suite-command-cleanup.json；有效探针根 181 entries / 203804 bytes 后不存在，首版185 entries /203809 bytes 后不存在。最终 overflow-owner 根19 entries /4217748 bytes 后不存在。只删除各脚本自己创建的 TemporaryDirectory；未扫描/删除历史残留。CPU 子进程事件以及 decoder 退出见 probe-results.json、suite.stdout.log；没有操作未知 PID。

## 边界审计与保留风险

fork 子进程内 setrlimit，不改变 parent；每个可信 render 函数只新写一个目标，单文件 RLIMIT cap 在此调用模型中约束剩余预算，不能泛化为任意子进程全磁盘配额。父侧轮询有deadline，join为0/1/1秒；cleanup独立2/1/1秒，均仅持有本轮 Process handle。runner 只 terminate/kill 自己 Popen 的直接进程；终止wait各2秒、reader join各2秒，已 poll 退出后的 wait不再等待活进程。仍依赖可信解码器不产生脱离子孙进程，不扩大为通用OS隔离。

pipe 捕获 stdout+stderr 合计有界；drainer 可在停止反应前读/丢弃额外 bytes，cap约束保留buffer而非声称所有内核pipe流量为零。ffmpeg image2pipe stdout只保存为受限staging媒体，日志保留byte/hash、不拷贝二进制帧；probe JSON、stderr、command、runtime/terminal JSON 属操作元数据，单次capture上限4MiB、固定候选/调用数限制总量，单独报告，不纳入媒体/index累计。IC-MAJ-01说明有界capture本身不等于正确失败终态。

成功 render 收到结果后可能为回收尚未退出的子进程发送terminate；不能仅用负returncode判定计算失败，需区分已收到完整结果和无结果退出。无结果/异常返回不被thumbnail当成功；index失败进入internal_error。清理和终态文本写入位于有限收尾，非硬实时OS审计；无法承诺对任意阻塞文件系统syscall强制全局截止。Linux/WSL-only 为已披露工具限制，不要求本轮Windows移植、不代表产品宿主验收。L01已修；L02–L07（OS审计不完整、审计钩子/依赖绑定/顺序单owner/异常JSON结构/原盲态限制）按原边界保留，不新增非阻断平台改造。

## 冻结与旧证据复用

只读 Git 证明：base→tip 仅两工具与实现correction证据变更；contracts/plans/stage packet/manifest/quality-set/旧独审与原run目录无diff。thumbnail/sheet/index三个算法AST逐字相同，顶层采样/转换/硬限常量全同；frame transport由文件改pipe但原scale、quality、offset、像素/格式/EXIF与采样独立性义务未降低。正式16源hash/预标、10+6与8/10、5/6、关键幻觉0保持。旧run receipt逐字匹配335a8b973ab9b0fe192c03f59e608f9976658238；预览归属仍e1798f33ba51dcadbf9f0333641d62d14a801491，不重绑eef2fe8。此处只读Git/已提交JSON，不访问原testSource或原preview，不重新计算真实媒体hash。

本轮0真实testSource/原preview访问、0真实child复用、0模型/GPU/服务/网络/下载/产品完整checkpoint；有合成CPU/decoder进程，不把“0真实child”误写成0子进程。零动作依据执行路径和合成输入约束，不声称OS全审计。新增异常集合仅准备工具纠偏，S3 product Gate0未通过。

## 执行坐标与交接

十字段：当前R1/WP-R1-U3/S3_PREP_C_CONSOLIDATED_CONTROL_FLOW_CORRECTION；本批完成只读审查/71测试/22有效聚焦观察；最后通过为统一切片UM10及范围人签；当前工具阻塞IC-MAJ-01；路线S3→V1准备；剩余为root裁决及局部修正、产品Gate0；下一责任人root；无需新增真实授权、旧child不复活；证据目录本independent-correction-01；停止因为审查任务完成，不因待人签、不代表Stage通过。

下表从execution-control读取，未增加任何正式完成项；实现/机器/独审/人签四字段原值完整保存在receipt.json的development_outline。

|阶段|已完成/总数|范围|
|---|---|---|
|V0-S0|1/2|历史NO_GO|
|V0-S1|5/5|已签V0-Min|
|R0|1/2|单图前置子集|
|R1a|5/5|已签单图切片|
|V0-S2|7/8|机器/独审完成，原人签未补|
|V0-S3|0/6|准备不等于产品验收|
|R1 当前|0/4|统一切片3/3已签，完整R1未完成|
|V1-M1|0/3|设计准备|
|R2|0/4|未正式交付|
|V2 R3|0/4|未正式交付|
|V2 R4|0/4|未正式交付|
|V3 R5a|0/4|未正式交付|
|V3 R5b|0/4|未正式交付|
|V3 R5c|0/4|未正式交付|
