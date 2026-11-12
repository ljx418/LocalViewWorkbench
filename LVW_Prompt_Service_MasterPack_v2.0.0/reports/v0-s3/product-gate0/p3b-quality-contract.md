# S3-P3B：公开生产工作流质量执行与独立评分（内部冻结合同1.0）

root拥有架构/验收；ClaudeCode实现，另窗独审。本批是S3离线产品验收接线，前置P1/P2B/P3A已各自限定接受。完整S3产品Gate0、实机profile/A06/回滚/固定十二项仍未就绪，本合同不许可真实运行。

## 范围与模块所有权

只新增tools/v0_s3_quality_phase.py、tools/test_v0_s3_quality_phase.py和reports/v0-s3/product-gate0/implementation-p3b/文本证据。不改既有产品owner、提示词、工作流、生产API/Schema、原S2阶段、authority/ledger、P3A工具、质量集/预标/样本/模板或固定分母。不另建通用验收平台。

同一冻结批次连续实现两个Workpack：QD 公开工作流质量执行；QS 独立评分收据复算。两包分别局部测试/收据，最后一次相关组合检查，交独立窗口集中审查。实现者只READY_FOR_REVIEW。

## 输入隔离

唯一执行输入是同目录quality-execution-inputs.frozen.json的精确字节SHA（在packet登记），16个有序行、10图6片，别名/媒体种类/SHA/字节数固定。此投影由root从quality-set.frozen.json静态生成，不含prelabels、caption、expected、评分维度答案、原目录语义或人工稿。执行模块不得读取/导入完整质量集或预标；父协调器负责将原媒体按别名受控准备到run_root/input，冻结实际源与profile/工具身份。没有真实source则拒绝，不调样/重排/替换。后续真正模型请求只有公开graph给出的media reference、现有model/mode/instruction，不能将标签嵌入提示词。测试可构造相同16行结构的独立synthetic投影与相应显式预期hash，不得冒称其为正式质量集。

QualityPhase为无CLI的可组合内部phase（具体keyword签名可合理确定，必须含driver/run_root/run_id/candidate_sha/authorization_sha256/projection及预期hash、同源工作流source_identity和原有限authorize）。parent负责真实profile、模型digest、媒体准备、子授权、单GPU、原process ownership与后续archive；phase不自行启动/停止/下载服务，不修改账本或另建预算扣额。每次公共动作仍调用原authorize并resource_observer，禁止直接调用内部BridgeOwner代替真实graph提交。

## QD：固定16项执行

run()只能执行一次，预先创建完整16行终态记录；未执行/缺失不移出分母。先校验全部行结构、唯一ID/源SHA/别名、工作流候选hash、run/candidate/child身份，以及已准备文件plain/non-symlink/size/hash；生产source上限图20MiB、片256MiB沿用，不新增宽限。源有任何不符时提交数0。文件读取流式有界，不能一次读取256MiB。图/片hash重复和跨行同名拒绝。

经现有S2SystemDriver.submit→真实Comfy /prompt→/history完整路径：image_reverse_prompt_v0.api.json用原节点，input_reference替换1.inputs.image_reference；需要图像受控metadata时沿CumulativePhase现有公开manual metadata观察图方式，不改产品图/owner。video_reverse_prompt_v0.api.json替换1.inputs.video_reference。model固定候选已有gemma4:26b，原mode=realistic、user_instruction空、timeout_seconds=120；工作流字节/源hash须属于candidate source_identity。禁止模板常量充结果、缓存/旧history补样、内部私有分析调用或Mock被记为真实验证。

记录每次graph/hash、prompt_id、实际history、before/after provider完整日志及hash/bytes、独立复算chat行计数（使用现有count校验），严格history prompt_id与graph相等、执行status/公开node输出匹配，prompt_id跨行唯一。先保存实际raw字符串的UTF8原字节与suggestion/metadata分离，再做结构验证；失败时保留已有raw/history，不能改写拒答/异常为成功。图raw是Ollama envelope字符串；片raw是frame_raw_responses及每帧原字符串，均保留。图公开metadata绑定源SHA/bytes/输出尺寸/hash，schema沿现有验证器；片复用public_video_oracle验证四帧raw、frame时间/序号/SHA和4次provider调用，并额外检查完整graph相等与规范PromptSpec。image每次1chat，video每次4chat，总34上限；before日志必须是after日志原前缀，不接受清空/重写。日志/实际debit的关系由正式协调器另行复算，本phase不能声称已证明母账本。

每行检查前后owned listener PID/birth不漂移、模型库存/资源释放及视频临时snapshot无残留，复用公开owner已有资源释放证据与默认图release_preload路径，不造release标记。资源/进程/清理不明或超动作预算立即停止后续提交，原16行保留，剩余BLOCKED；确定已释放的单样本拒答/结构失败可继续下一行但该行FAIL，绝不自动重试。raw质量未评分前quality_status=NOT_RUN；execution_status的PASS仅表示结构/调用/清理已验证，不能生成Stage或质量PASS。

每样本历史等待至多600s；总phase至多10800s，轮询有间隔且总次数不超过6000，0自动重试、16次public submit最多、34次chat最多。不包含新模型warm/preload请求。父budget不足以承载时必须拒绝而非请求额度扩展。本批仅实现这些有限规则，不能执行真实请求。新artifact每件<=8MiB、总<=128MiB、文件<=256，持久化失败停止提交并清楚报告UNPROVEN；不覆盖既有phase目录/receipt，输出路径仅本轮run_root/temp/s3-quality下，防逃逸/symlink/重放，source/root身份应在受控回调交接后核对。完整原raw在上限内才可声称保留；超限明确失败，不悄悄截断当可评分。原父OwnedArchive接管真实raw归档/删除，不把pytest teardown当产品清理。

## QS：独立评分复算

同模块的独立纯校验/聚合入口接受QD执行收据+实际artifact根、独立评分收据；执行路径不调用它。评分收据必须绑定run_id/candidate/projection hash、每行asset_id/source_sha/raw SHA、reviewer/session身份，读取actual raw artifact复算hash/长度/安全路径，不能用suggestion或人工稿hash替代。独立性由角色/运行隔离收据证明，字符串reviewer字段本身不证明独立。

评分不调用模型、不按关键词假装语义评价；独立审查者给出五维0..2及关键幻觉数/依据。维度严格为quality-set冻结的五项，关键幻觉数须为非负整数；bool/非整数/越界/未知维度拒绝；S3固定只有16行，不混入M1质量18段或V1 Q01分母。重复/外来行、错run/源/rawhash拒绝。缺少评分或execution非PASS的行必须质量FAIL/未满足，保留16分母，不能靠评分满分救绿。单样本总>=8且关键幻觉0才可用；aggregate图>=8/10、片>=5/6、全体关键幻觉0。未评分原始run不可以aggregate PASS；输出质量结论只属于该绑定的16项，仍stage_pass_claim=false。四帧未知连续性/物理运镜不自动得分；语义判断由独立评分证据承担，程序不自造真值。

## 离线验收与派发约束

测试直接驱动新phase的完整16行状态机和真实graph构建/原production oracle；只替代native HTTP/provider边界，不只测常量或私有helper。至少一个适当小的生产BridgeOwner/真实node集成用synthetic provider证明新driver观察到的是公开生产输出语义；不得真实解码testSource或调用模型。原owner可生成内存/临时非私有小fixture，不把synthetic结果声称实机。固定16、1/4/34调用计数、先保存raw再拒绝、错history/graph/duplicateID/日志改写、源/路径/身份漂移、拒答/timeout、清理失败停后续、缺/重复/旧评分、exact/oneover预算与artifact、bool分数等负例都要明确Oracle。未执行原16行和无残留/保留证明必须核对。

每包运行定向pytest，最后两包组合+必要shared oracle相关检查一次；不重跑P3A全套121/P2B237/全项目。0实际Windows/WSL/PS/parser/hosthash/媒体/GPU/模型/服务/网络/download/real ledger/full checkpoint；受控Python/Git新synthetic临时目录，守卫subprocess/network在导入前生效，raw命令/退出码/用例数/清理真实保存，只提交文本，不提交DB/包/源码副本。遇合同歧义按Orca ask停止依赖工作，一次汇总，不擅改阈值。

ClaudeCode首次HTTP429立即停止该实现任务并报告WAIT_BUDGET，保留原错误与候选；不重试、不切模型/账号/Harness，不自动请求Codex继续。只有用户针对本次中断明确授权Codex接手方可改owner；旧概括授权无效。root仍只架构/协调/门禁，独立审查另窗。两次同路线无新证据停止交接，失败日志保留。
