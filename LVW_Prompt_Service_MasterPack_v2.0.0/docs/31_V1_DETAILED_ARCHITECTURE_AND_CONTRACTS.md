# 31｜V1总体与详细架构：设计1.1.2

状态DESIGN_REVIEW，2026-11-11。本版集中裁决独审F1/M1–M11/m1–m10；原1.0及失败审查保留于reports/v1-redesign/history与d0-review，未宣布发现已独审关闭。当前产品源码、canonical OpenAPI/core schema/DDL和旧R1 packet不改；候选Schema/迁移/overlay需隔离复核，样本实际冻结和产品Gate0尚待。

## 总体与唯一owner

保持一个React/CLI→FastAPI模块化单体→SQLite/受管小工件＋一个GPU lease，Node仅构建，无新微服务/消息集群/向量库/第二套shot。

| Owner | 职责和计划文件 |
|---|---|
| ControlledMediaOwner | media.py/video_kernel.py：有界原片受控引用/SHA，不为每镜头复制整片 |
| SceneRevisionOwner | scenes.py/scene_repository.py：候选切点/真实PTS、边界不可变修订、scene_head CAS |
| ShotRevisionOwner | shots.py/revisions.py/repositories.py：可选镜头绑定、人工head、锁定字段/ETag/显式采纳；模型不直接写人工版本 |
| FrameEvidenceOwner | shot_analysis.py/provider/service：镜头内抽帧、typed机器证据→canonical PromptSpec、raw/stale绑定 |
| PersistentJobOwner | jobs.py/job_repository.py：固定父子计划、claim/attempt/token/CAS/取消/重试/中断 |
| LeaseOwner | resources/provider/runtime/native_runtime：准入/采样/实际释放/本轮进程身份清理，不终止未知进程 |
| CompilerOwner | 纯CPU共享compiler：natural/image/edit/motion；缺英文不伪翻译，切格式0额外调用 |
| UI | 现有frontend/src：时间轴、校订、逐镜头draft/stale/冲突/导出，同源API，不直连模型/DB |

Codex持有合同/设计/验收。Claude只写冻结owner路径；公共合同/迁移/状态机串行，不自行补字段或降阈值。

## 合同兼容裁决与有效合同生成

**F1裁决：旧POST /api/v1/jobs/batch的{items:[AnalyzeRequest]}保持原样且仍属V2。新增POST /api/v1/jobs/shot-batches专管V1最多12镜头、固定分母和边界绑定。** 两者不同语义，不以同一路径替换请求体，也不引入镜头API的第二套版本。

canonical文件作为历史/基础合同不改。候选overlay只允许添加新路径/新method/新组件、补ETag响应头、对scenes/detect与scenes的有限profile标注V1可用；不能替换既有请求/响应Schema。构建时合并baseline+overlay产生effective-openapi，摘要绑定到候选与capabilities。新增Schema组件统一MultiShot_前缀，内部$defs引用转换为组件引用，避免FrameRef等命名冲突；本地registry解析，不联网取Schema。

| 路由 | 唯一请求/响应与语义 |
|---|---|
| POST /scenes/detect | 保留原media_ref_id/profile，新增受限local-shot-v1 profile；202原Job，不调用视觉模型 |
| GET /scenes，PUT /scenes/{id} | body继续canonical Scene。revision=版本，editor只algorithm/human，verified来自元数据；不返回新SceneRevision替换它 |
| 新GET /scenes/{id} | 返回同一canonical Scene；ETag在HTTP响应头，非偷偷加body字段 |
| 新GET /scenes/{id}/revision-info | SceneRevisionInfo：scene_revision_id、scene_id、原Scene、源SHA/hash/etag/time_basis；可用受控revision_id查询该scene的历史，越属404 |
| 既有/规划shot CRUD | canonical Shot保持原形，media/人工head语义保留 |
| 新GET/PUT /shots/{id}/scene-binding | ShotSceneBinding，PUT If-Match使用当前Shot.etag；绑定同media的revision/hash；只改当前关联和etag，不改旧人工head。image/manual无绑定返回两个null |
| 新POST /jobs/shot-batches | BatchAnalyzeRequest：等长有序shot_ids/scene_revision_ids、mode/profile、可选retry_of_parent_id；max12、同源当前绑定，202原Job；明确只接受六个产品模式，不改变旧自由字符串接口 |
| GET /jobs/{id}，cancel | 原strict Job不加字段，父progress_done=terminal_count，progress_total=total |
| 新GET /jobs/{id}/children | BatchChildrenResponse={parent:ParentJob,children:[ChildSummary]}，含deadline_at、budget、固定顺序/全部计划项/未执行计数 |
| 新GET /shots/{id}/analyses/{run_id}/evidence | ShotAnalysisEvidence，公开绑定剔除lease_token，raw仍从原/model-runs/{run_id}取 |
| 新POST /shots/{id}/analyses/{run_id}/adopt | 空对象body、Idempotency-Key及If-Match；事务核对绑定/current head/取消状态，合并人工锁定优先级，创建canonical PromptRevision并记来源；不可采纳stale/cancelled |

通用写入同键同载荷幂等、异载荷409；缺If-Match428/旧etag412。HTTP错误与Job终态分别见机器合同表。既有/manual修订保存视为用户主动编辑，不伪造模型来源；新adopt入口才写model provenance。旧/jobs/{id}/retry留给R2/V2既有单任务语义，不在这里偷换请求。

## 时间、版本与hash

Scene.id是稳定逻辑scene_id；Scene.revision是版本号。底层scene_revision.id是不可变版本ID。scene_head指向当前版本；scene_revision_meta保存scene_id/revision/source_sha256/time_basis/verified/content_sha256/etag。公开算法editor=algorithm对应detector，human对应人工，不引入detected替换旧枚举。

时间t=(source_pts-origin_pts)*num/den，范围[start,end)，VFR不用平均fps或显示序号充真时间。内部边界映射实际解码源帧；全片末端允许验证过的容器终点。DTO有decoded_pts/estimated/unverified与verified对应约束。M1仅verified+decoded_pts可分析；缺失/非单调PTS的detect Job.failed，error_code=SCENE_TIME_UNVERIFIED，details含time_basis和缺失/倒序计数，不伪造Scene。迁移来的未核验旧Scene可查看，启动分析422拒绝，需显式重新核验。

scene_revision_hash=SHA256(UTF8 JSON)，字段严格为media_ref_id、media_sha256、revision、start_pts、end_pts、origin_pts、time_base_num、time_base_den、editor、time_basis、verified；sort_keys=True，separators=(',',':')，ensure_ascii=False，allow_nan=False，verified是JSON boolean。随机revision行ID、created_at、时钟不入hash。强ETag为加引号的scene:<scene_revision_id>:<hash>。实现/迁移共用一个规范函数，禁止两份近似算法。

修改边界append新revision，同事务CAS scene_head；影响项显示stale但旧binding/raw/人工稿都保留。只在用户显式重绑后改shot_scene_binding；新batch要求当前head/association吻合，否则412。模型采纳再次验证绑定，stale409，不能晚到覆盖。

## FrameRef与动作证据

候选ShotFrameRef复制canonical FrameRef的完整形状，包含target_seconds/time_basis，逐镜头只收decoded_pts、非空真实PTS。合法实例原样写model_run_artifacts.frames_json并在原ModelRun.frames返回；不定义同名不同形FrameRef。

一镜头一次模型调用，输入本段1–4个实际不同源帧及0基编号/实际时间，不混入其它镜头。MachineShotResponse只供模型输出人物/场景/动作/双语summary/tags/negative/unknowns，不允许模型填写源SHA/FrameRefs/绑定。服务将真实FrameRefs另加成ShotEvidence，原raw字节不改。

Character、SceneEvidence、Action均有domain=observation|inference和同镜头frame indices；每项描述有zh/en来源文本。actor仅本镜头局部编号，不识别姓名或追踪跨镜头身份；动作变化推断至少两不同时刻，单帧只能姿态。越界帧/不存在actor/重复引用身份/额外字段/无效JSON须失败保留raw，不修话造绿。最多4个人物细节/4条动作，复杂多人场景明确unknown，不承诺穷尽追踪。

确定性适配：将各字段按domain格式化进入canonical Domains.observation或inference；unknowns进入Domains.unknowns。模型不得填user_evidence/creative_intent；它们由人工owner维护。双语summary进入text_zh/en，缺一语言明确缺失；CPU格式化不是翻译。合并优先级沿用人工锁定>shot>scene>配方>模板>机器建议，先出机器建议、只有adopt事务写新head。完整PromptSpec继续供四目标纯CPU编译，原R06闭合。

M1模型profile候选think=false/ctx4096/predict1536/temp0.2，因新结构不能沿用1.8 appearance-only Schema声称已有动作。必须单源pilot验证截断/解析/质量与原GPU硬限，不能下载新模型或凭profile猜已达标。CPU像素/注册只另行标注变化证据，不产生走路/握手标签。

## 可执行存储候选与迁移

候选[迁移SQL](../contracts/v1-multishot-migration.sql)只在内存检验，不用于D0生产DB。R1初始版本1仅建其实际需要核心表；M1版本2补scene最小子集和下列结构，不提前FTS/资产库。已有全baseline表也兼容，旧generic batch_child不改。

| 表 | 载体/事务规则 |
|---|---|
| scene_revision + scene_revision_meta + scene_head | immutable版本/来源hash/time_basis与mutable headCAS；元数据版本唯一；旧ID/值保留，不按位置猜分组 |
| shot_scene_binding | 可选关联，纯图/无media的人工shot没有行，无强行回填；原prompt_revision ID/hash不变 |
| model_run_artifacts | 实际canonical frames_json；R1若已建则沿用，不重写旧帧 |
| shot_analysis_binding | immutable model_run/shot/scene/hash/media/config/attempt/lease_token/cancel_epoch；token只服务端、从attempt.token核对 |
| shot_analysis_evidence | 原typed证据与hash；原model_run.raw_text/parsed_json继续保存raw/PromptSpec |
| revision_source_binding | 显式adopt的新revision绑定真实run及scene版本，manual保存不伪造此关系 |
| shot_batch_parent/item/seal | 父计划hash/截止/总量、有序子Job＋shot/scene/hash、一致性封印；原generic batch_child留给V2 |
| attempt_execution | 实际尝试发模型前记录model_action_at/provider_call_id；model_started由此派生，非由已领CPU任务推断 |

父Job、全部queued子Job、父计划/有序items在同一事务一次性写入，最后insert seal。seal触发器验证数量/ordinal/plan_hash，封印后不可追加/更新/删除计划。worker claim必须join seal，绝不领取未提交/未封印的半套计划。普通Job/Attempt状态可CAS更新，计划不缩分母；所有事务不包解码/模型I/O。模型结果终结同时核对active_attempt_id、attempt.token/lease、cancel_epoch、scene hash，再写ModelRun/附表和Job终态；adopt独立核验当前版本。

迁移前backup并检查版本1/外键/JSON函数，注册deterministic lvw_scene_hash(11args)，BEGIN后DDL+旧行backfill+触发器+version2在同事务。旧scene各保留原ID为逻辑scene_id、不猜历史分组；sourceSHA从原media_ref，verified=False/time_basis=unverified，hash由上述函数算。坏hash/非法editor/引用缺失失败ROLLBACK，不默默丢行或假验证。中途故障/重复版本不得半升级；旧人工稿保留。

## 解码、父子状态与预算

检测阶段单次有界流式低分辨率评分，同时记录紧凑实际PTS索引（仅时间元数据，不存全片像素）；索引磁盘≤16MiB、detect总≤120s，超限显式失败、不截前半当完整。每镜头按索引keyframe seek后只解码所需窗口，最多保留4个≤768源图，不为每镜头重扫整个视频，也不缓存全片tensor。

单GPU，每子分析总420s（准备/模型/解析）＋释放最多30s；准入free>=19047MiB，运行GPU<23552/RAM>=2048/OOM0，取消反馈<=1s、实际释放<=30s，均不改。父预算=450*n+90秒，n1..12，max5490；created_at后固定deadline_at，重启不自动延长，运行时用monotonic剩余预算与持久UTC截止较小值约束时钟回拨。

截止未发模型的项=failed+BATCH_DEADLINE_EXCEEDED+model_startedFalse；活动项先取消/释放，再failed同码；父failed。用户父取消时未完成项cancelled+JOB_CANCELLED，成功项保留；父cancelled。所有子成功父succeeded，其他全终态组合父partial+CHILD_ANALYSIS_INCOMPLETE。terminal_count包括所有终态，不等于成功数；not_executed_count仅表示无实际模型send。超时/资源不足不是可用结果，质量/完整分母不PASS。

显式重试失败项用新shot-batch请求retry_of_parent_id，所选绑定必须对应原failed/interrupted项，创建新父计划、新子Job/attempt并记录retry_of_child_id；旧成功项不重做，旧失败不改写。边界已变须重新分析，不偷用旧绑定。重启running->interrupted，不自动发模型。

完整checkpoint预算独立于一个视频父预算，见docs/32：设计上限72动作/21600秒，同原COMPLETE03账本，执行截止提前180秒留最终清理。即使硬上限每次都420s也不保证单轮一定完成；超出必须完整保留失败，不能截分母或自动续时。清理不明保留预约，不用服务exit0单独造绿。


旧/jobs/analyze保持原单图/整片及shot_id语义；M1绑定分析只由shot-batches明确触发，内部复用分析owner但使用独立profile/response schema，不能给旧请求隐式换模式。config_hash规范字段见机器合同，源media SHA不变但scene hash和实际FrameRefs使镜头输入身份唯一。


展示镜头编号S01/S02为1基，仅供人读；机器帧证据index严格0基F0..F3，实际时间来自PTS而不是展示序号。补充API中的lease_token始终内部；公开evidence的binding只用PublicAnalysisBinding。


## 设计1.1.1：六项Minor集中纠偏（2026-11-11）

独立设计复核确认原22项在设计层解决；新增N1–N6由本次owner纠偏，是否关闭仍待独立复核。旧1.1源与packet保存在reports/v1-redesign/history/design-1.1；不修改旧失败报告或产品验收。

N1/N3：overlay的新增Scene GET和revision-info GET成功响应直接声明强ETag；原Scene PUT 200通过add_response_headers追加同一Header Object。metadata_only逐路径逐方法声明7条reuse路径的x-v1-profile=local-shot-v1，不覆盖原x-product-version或V2语义。合成顺序：深拷贝base，加入不冲突的新方法/前缀组件，再按metadata_merge_rule仅追加不存在的x-*及响应header；不存在的目标、重名header/元数据或其他变更一律失败。原body、参数、状态码不改。

N2：机器合同additive_paths覆盖全部7条路径；additive_operations逐方法列举，包括既有Scene路径的新GET，不能仅比较新路径名。

N4：ShotFrameRef的source_pts、time_base_num/time_base_den只保留非空integer分支；timebase minimum=1。保持canonical FrameRef兼容，旧canonical不改。

N5：确定性转换以plans/v1-multishot-contract.json的canonical_domain_mapping为唯一机器规则。人物按local_actor_id Unicode码点排序，其后场景、其后动作原数组顺序；按自身domain分流。每个非空语言值按zh、en顺序单独生成一条字符串，内容为含kind/ref/lang/text的compact sorted-key JSON，ensure_ascii=False、allow_nan=False；不翻译、不trim、不去重、不改写raw。人物ref为local_actor_id，场景ref为scene，动作及unknown ref为原数组零起始十进制索引。unknowns仅进unknowns且保持原数组顺序。summary双语原样进入text_zh/en，人工域与锁不受影响。

N6：scene_hash.column_mapping冻结全部11个hash字段到数据库的映射，尤其time_base_num←scene_revision.tb_num、time_base_den←scene_revision.tb_den、revision←version。JSON键只能用合同字段名，不能使用SQL别名；verified的0/1先转JSON bool，PTS/timebase/revision须整数且拒绝bool/float/string。旧行source SHA取media_ref.sha256，新meta保留同值。


## 设计1.1.2：D0校验器审查纠偏边界

本轮是同一离线D0内集中修复NM-1–NM-8，不扩大产品范围、固定分母或真实运行预算。NM-5仅消除键名列举的阅读歧义：canonical_domain_mapping中的JSON键集合与输出排序都明确为kind/lang/ref/text，sort_keys=True；其余转换语义与已冻结示例字节不变。所有旧审查、失败日志和收据保留，不修改历史数字以覆盖问题。

NM-1要求校验器保护全部11个字段映射以及迁移中每处lvw_scene_hash的11参数顺序；NM-2要求新Scene GET仍返回canonical Scene完整envelope；NM-3要求畸形输入有稳定诊断与非零退出码，而不是无stdout的未捕获异常。NM-4/NM-8要求输出降级检查、实际使用的pin与默认/显式覆盖来源，覆盖pin的合成副本运行不得冒充权威门禁。NM-6要求四类证据及observation/inference/unknowns路由均有确定性负例，不能只计算人物单例。NM-7以追加更正收据绑定旧原始日志中的真实计数，不改写旧收据/失败日志；新收据由本轮机器日志提取统计。

本次独审findings数组实际为3 Major、5 Minor（NM-1..NM-8）；其summary写6 Minor属于计数差异，原报告保留，由下一独审在新收据中核对并说明，不能凭空制造第九条问题。当前候选不通过D0收口，产品仍R1/WAIT_HUMAN。
