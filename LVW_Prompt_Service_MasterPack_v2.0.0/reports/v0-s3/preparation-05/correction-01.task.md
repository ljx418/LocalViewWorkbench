# S3-PREP-C correction-01 — 三项控制流缺陷一次纠偏

Codex裁决：原工具e1798f33为CHANGES_REQUIRED，独审700cef748c57ba79be0ad686ca67a10cce589644确认Fatal0/Major3。本批只修 tools/s3_sample_preparation.py 和 tools/test_s3_sample_preparation.py，新增文本证据限reports/v0-s3/preparation-05/implementation/correction-01/。原child/原preview/原raw/原预标/质量集/独审/其它代码/manifest均不改。原真实run32项被独立复算且未观察源漂移/wall/output超预算，预览和预标可按原候选身份复用；不得重绑定到新候选，不重跑真实child，不加新素材/模型槽。

## MAJ-01 源变动是整体终态

对固定清单检测到文件大小/内容hash/读取期间身份变化，以及原已固定文件消失，均停止处理后续候选，明确SOURCE_CHANGED终态、非零、未处理项NOT_RUN。不能mark_not_eligible后continue。区分同hash坏格式素材本来不可解码的NOT_ELIGIBLE与冻结源变动。测试精确证明第二文件resolve/stat/hash/decode都未进入。原源不写、不删、不追随symlink，拒绝证据保留。

## MAJ-02 一个单调deadline治理所有有成本工作

向probe、每次frame extraction、图片decode/渲染、contact sheet/index及最终决策传播全局deadline。每次工作前确认剩余额度，子进程timeout取剩余预算与原per-process cap较小者，<=0不启动；deadline达到后不能继续4帧。工作完成后和最终决策重新检查实际单调时间，超限必须BUDGET_EXHAUSTED非零，不标完成。停止/回收仅owned进程，清理必须有独立有限收尾且报告生产预算已超时，不以finally清理把实际超时隐去。Python同步图片CPU操作不伪称可随时中断：若不能提供硬截止，应使用本轮owned有界子进程或其它可验证有界执行，禁止无限阻塞。不要改借用的v0_s2 runner，优先局部adapter封装。exact已完成工作在上限处与one-over区分，新工作remaining<=0不启动。

## MAJ-03 临时+保留输出同一预算，超限为黏性失败

沿用冻结child/accountant的临时与保留bytes总口径，不将最终decision只看retained。一次曾超过限制不得因删除staging而转成功。受控写入之前预留/限制空间，写入期间有界，不能只对成品事后stat。可采用受限writer/预留明确上界或受控输出流，机制由实施者选最小方案；所有thumb/frame/sheet/index均纳入。decoder输出不能在长运行期间无限增长，仅控制本轮owned进程和文件。达到预算后停止后续工作/增长，保留原始错误与实际测量，cleanup删除owned staging但不洗掉超限状态。工具操作元数据/终态receipt单独说明，不借其名保存额外preview媒体绕过上限。exact/one-over、超限后清理/最终状态及伪成功反例必须覆盖。

## 边界与一次交付

修同根因时顺带修L01错误started_at：分别捕获UTC墙钟与monotonic，wall用单调差值，旧1970收据不改写；收据里常量与实测字段明确标注，不引入OS级监控平台。其它已披露非阻断L02-L07保持说明，不扩大安全重构。只改上述两工具并新增correction-01/，合同/阈值/正式样本集合不变。Claude套餐额度耗尽，本次由Orca可见的Codex实现窗口替代；与独审Codex保持不同实例/工作区。

先阅读独审review.md与三个聚焦反例script/json；原45用例保留功能覆盖且不降oracle，添加驱动公开owner/CLI的回归：大小变化不再碰第二源，probe推进clock后不再调用frame、frame阶段剩余timeout与不再继续后帧，渲染/最终超时拒绝，临时output超限清理后仍失败，受限增长/拒绝后无后续写入。所有输入合成，不能stat/hash/probe/decode真实testSource，也不访问原保留preview（没有必要）；可读原JSON证据。不要因旧child过期生成新真实授权。

一次新候选测试套件及原三项反例的适配复验，必要公共CLI合成正常链路仍通过，保存命令/stdout/stderr/exit、测试矩阵/oracle变化、文件hash、候选Git commit、owned临时与进程实测清理。无需真实媒体回归：原成功run不受异常修法影响且预览/标注已冻结，独审将复算算法/身份是否仍可复用。超时测试不可只assert常量存在或mock returncode；至少一个真实owned子进程验证停止/reap，其他用可控clock/adapter检验调用顺序。预算0模型/GPU/服务/网络/下载/源媒体/真实完整checkpoint。最多两次同路线无进展则交接，不无限重试。只READY_FOR_REVIEW，完成提交代码与追加证据并worker_done full SHA，保持窗口可见。Git作者ljx418 <1173696783@qq.com>。
