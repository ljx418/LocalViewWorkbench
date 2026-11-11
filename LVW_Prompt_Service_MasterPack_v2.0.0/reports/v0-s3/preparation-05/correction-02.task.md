# S3-PREP-C correction-02 — IC-MAJ-01 reader/runner失败优先

原MAJ-01/02/03已由独审d3b6d5e58f37b171c04add3a939350e078b65a51验证闭合；当前工具仍CHANGES_REQUIRED_TOOL_ONLY，唯一剩余阻断IC-MAJ-01。候选eef2fe8/交付f409d8c为本次基线，root协调新commit含完整独审原始证据。此任务只局部修复MediaAdapter的runner错误传播，不新建平台、不改采样/渲染/质量集/预算/产品合同。

原因：run_bounded合法地先on_result(returncode=0)，再抛VIDEO_PROCESS_OUTPUT_LIMIT；_run已记录error，probe_video却只看exit_code、仍解析被截断但合法JSON；原owner于是继续4帧并标完成。完整真实owned合成复现：independent-correction-01/raw/probe-overflow-owner.json与对应脚本。不是原真实run曾越界的断言。

修复义务：任何runner/reader error都不能因OS exit0变可用成功，无论probe还是frame。检查共用adapter/owner的错误出口，禁止含error的probe document进入后续frame，禁止含error的frame字节写作有效媒体。对输出capture上限错误不分ffprobe/ffmpeg，设置不可被清理或解析成功洗掉的失败并整体终止后续候选/媒体工作；timeout继续受原global deadline治理。错误原因明确区分probe capture metadata上限与preview媒体80MiB总量，不声称后者已超限。普通非零退出的损坏媒体NOT_ELIGIBLE语义可保留，不能为统一错误处理扩大为任意新scope要求。保留error、真实exit_code、捕获bytes/hash与限制；不能抹掉合法exit0来伪造OS失败，终态应因runner failure非零。即使没有budget对象，单独probe/extract的owner也不能接纳带runner error结果。

允许只改tools/s3_sample_preparation.py、tools/test_s3_sample_preparation.py，新增reports/v0-s3/preparation-05/implementation/correction-02/。原71测试功能/oracle保留，旧raw/预览/child/标注/quality-set/其它代码/计划/manifest不变。优先共用的一处错误处理/两操作拒绝分支，避免大重构。

测试最小矩阵：1真实owned合成probe输出合法JSON+超过4MiB空白且OS exit0；2合法小JSON+stderr超合计capture；3runner显式error+parseable JSON/valid frame不接纳；4普通正常probe/frame链路与timeout/原输出黏性语义不回退。至少一项通过真实run_bounded而非伪造returncode，parent owner证明错误后frames=0、later source resolve/stat/hash/decode=0、非零失败终态、owned子进程已退出reap、临时目录清理。保留原反例作为旧失败，不改其历史输出。定向新增测试后一次完整新套件，记录真实命令/exit/raw/候选SHA/工具hash与清理。probe输出为合成操作元数据，不读取任何真实源/旧preview。

预算0真实testSource/原preview/新真实child/模型/GPU/服务/网络/下载/产品完整checkpoint。原成功run仍按e1798f33/335a8b97身份复用，不重绑新代码；正式10+6冻结不变。Linux/WSL工具及L02-L07已披露限制保留，本轮不要求Windows移植或完整OS审计。最多两次同路线无进展须交接，不能无限重试。完成只READY_FOR_REVIEW，提交工具候选与新证据并worker_done full SHA/精确测试与剩余风险；Git作者ljx418 <1173696783@qq.com>。实现与独立审查用不同Codex窗口/worktree，不自签。
