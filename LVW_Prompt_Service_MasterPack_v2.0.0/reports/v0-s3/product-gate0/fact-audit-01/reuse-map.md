# S3 生产复用与最小接线建议

基准 e2eb0cbbb6cae058f8b5da4da8a6775c63060d40。事实、建议、未知严格区分；没有Stage/Gate0裁决。readiness-matrix.json含十二项实际函数path:line+signature，budget-proposal.json含逐项调用矩阵，source-index.json给提交和字节hash。

## 可复用事实与不能复用的历史结论

公开Comfy API由 `tools/v0_s2_driver.py:389 S2SystemDriver.submit(self, graph)` POST `/prompt`，history必须验证prompt_id和实际graph；`nodes.py:19 IS_CHANGED`让分析每次新鲜，不把缓存当推理。image API workflow的controlled input→image bridge，与video API workflow的LVWVideoPromptOwner是真生产路径。`video_api.py:64 analyze(...)`及98行注册的workbench/status/cancel是视频GUI与headless的共享入口；不以测试直接call core替代公开运行。

九项现成phase复用条件：`CumulativePhase.run(self, segment)`（cumulative_phase.py:205）先online后offline，在线一次真图，随后24个累计公开提交；`PublicPhase.run(self)`（public_phase.py:206）15项=decoder1+文件负例10+结构类别4；`run_browser_phase(driver, *, config, binding, fixture, node_executable, node_sha256, authorize_launch, authorize_action, verify_bindings, run_offline)`（browser_phase.py:24）驱动真实headless Comfy；`CancellationPhase.run`与`FaultPhase.run`由browser_handlers.py:32 default_offline_runner顺序衔接；`WarmPhase.run(self)`（warm_phase.py:157）20次固定热测。`StageSequence.run`（stage_sequence.py:118）将其串起，硬校验default45/warm20提交并只列九项，不能直接当十二项S3 runner。reuse是函数逻辑和Oracle复用，既有CLI/旧授权与旧9PASS不复用。

`reports/v0-s2/full-v0-auto-08/receipt.json:1`为719c74559393a6489b2f630a1e0d3bc3303eb655的历史机器九项、20热测与归档hash；原始归档引用位于外部STATE，不因引用存在宣称本轮重读验证。原S2仍7/8。live15只证明621b1bf386db71bfe08ca2f533fa8ec396b0504b统一切片。批准handoff可进入S3 toward V1，不待重复人批；两个历史收据均不能拼成新S3十二项PASS。所有新执行必须在同一父run命名空间记录各child/phase身份；若root冻结某次新执行同时覆盖多项，必须预先写清交叉映射，不能事后挑正例。

## A06 最小宿主接线（建议，未实施）

包owner `tools/v0_incremental_package.py` 的 command_build(args):1382、command_diagnose(args):1527、command_install(args):1851、command_rollback(args):2465 已独审，仅提供sandbox文件层操作。 `_read_sandbox_marker:433`要求magic/tool；`_require_not_production_host:410`拒绝真实Comfy路径；install拒绝既有bridge/workflows/lvw冲突，rollback交叉验证持久ownership/preimage。不要移除这些防护或扩展/重测已通过准备工具。

最小连接是把通过install产生的**同一个隔离target**用作Comfy `--base-directory`，而不是另copy源码插件后声称包已运行。`StageRuntimeFactory._deploy:101`现在总是copytree bridge，因此需要一个受控“已安装包hash验证”注入点替换这一步；原_copy等媒体处理只作用新run input，原宿主不写。`_prepare:158`目前mkdtemp后创建input/output/temp/custom_nodes，和已安装target冲突，需要有限target/root factory参数，不能直接复用原函数原样启动。其 `_user_root:136`验证实际CLI，S2SystemDriver.start_comfy:397和comfy_wrapper:25已有 `--base-directory`/独立user/cache/temp与禁止自动启动/禁API节点/禁其他custom nodes配置，可用中文空格命名受控target验证参数引用。

只读复用既有Comfy main、其Python/PyTorch/CUDA/site-packages及既有frontend、Ollama exe/模型store、已装FFmpeg/native PyAV、PowerShell、nvidia-smi、Node/Playwright/Chromium。仅包内bridge/workflows与允许素材进入owned隔离根；不拷Comfy/PyTorch/权重构造第二发行版，不升级、不改C:/Comfy永久配置。历史指针 `tools/v0_s2_bindings.py:13 TARGETS`、`stage_runtime.py:32 TOOL_KEYS`和full08封存记录不是当前安装可用性证据；live15/bindings.json不含完整native Comfy依赖，不能替代新binding。本轮未读任何这些工具实际文件，也未运行版本/模型/进程探测。

A06必须先绑定“原workflow”的确切bytes/hash/允许节点/模型成本；新安装前可先运行原图建基线，安装后运行包内图/片/人工，停止原owned进程后rollback，再在恢复的同一隔离宿主启动原图真实执行。当前没有可直接认可的已冻结原图身份，故rollback模型成本null；若root选择无模型的原图仅能证明该具体原图，不夸大成所有原Comfy生成工作流。旧workflow若依赖现有自定义节点，现有whitelist只有lvw_v0_bridge会拒绝；必须限定必要依赖而非开放全插件。

已有 `no_cloud_remote_gate:476` 仅OLLAMA_NO_CLOUD日志+十秒Established连接样本且只筛11434，非OS outbound阻断/attempt观测；离线环境变量、浏览器route规则也不证明进程外联零尝试。缺少适用于整个owned进程树、保留loopback、可撤销且不永久改系统的外联阻断与尝试记录方案；root需冻结此项最小runtime适配及证据，不能用HTTP失败/无成功连接冒充。

owned清理复用 `S2SystemDriver._prove_listener_owned:118`、`_kill_bound(pid,start_ticks,*,allow_absent=False):147`、`_snapshot_descendants:176`、`cleanup:260`，证明original PID/birth/wrapper/listener及子进程退出，不杀普通GUI；`NativeRuntime.cleanup:269`含sampler；`OwnedArchive.__call__(self,context,cleanup):82`先留raw与manifest后处理根；stage_sequence.py:82 close对browser callbacks、sampler、tree和监听终态再核对。A06需要同样先关闭后rollback，保留失败根而不虚报已清理。无证据时close_retaining_reservation。

## Graphical / headless / raw-scoring 边界

原生图形入口：Comfy UI workflow + `web/video_controls.js:5`扩展，注册真实工作台、选择/预览、显式采纳、取消和下载；`video_json.js:58 resultJson`保持raw字节。Headless使用同UI `tools/v0_s2_browser_acceptance.cjs`，parent `BrowserHandlers.callbacks:95`负责提交许可与native证据连接；`run_browser_phase`有浏览器所有权/回调关闭，`browser_evidence.py:95`起的生产raw/字段/模型/事件Oracle可复用。旧headless允许不等于可见浏览器自动化授权。已签React前端只能作后续人签证据导航，不能替代原Comfy十二项，也不需要本轮改React。

质量生产端只读脱去预标字段的source asset id/hash与冻结prompt；`quality-set.frozen.json`**内嵌 observable_facts/unknown/prohibited_assertions**，不可整个对象传执行prompt或交给模型。建议根packet冻结执行投影`{asset_id,source_sha256,media_kind,reference,prompt_sha256}`，分离评分端输入。原image history输出raw/suggestion在 nodes.py:50；video_api.py:64输出raw/suggestion/metadata；core.py:497逐帧调用并把原文存frame_raw_responses，异常保存prior_frame_raw_responses。必须独立保存每帧raw与错误，不以最后compiled suggestion代替原话。

新质量driver复用submit/history/owner，逐项固定16槽写 `{run_id,child_id,candidate,asset_id,source_sha256,prompt_sha256,request_hashes,raw_path,raw_sha256,error,cleanup_receipt}`；没有raw仍保留槽并FAIL。独立scorer随后取得冻结预标hash+原raw+rubric，五维0..2/总>=8/零关键幻觉，最终图>=8/10、片>=5/6；执行器不自评。可以给独立人员/隔离审查上下文评分，不要求再调用被测模型，自然模型预算0；若未来额外用模型评分则必须显式纳入动作预算，不隐含免费。四格预标不足以证明连续动作/运镜全时序真值，未知保留、过度断言计错，尚缺完整时序验证规则不应自动PASS。此调查未打开原人类留样或expected，也未看媒体。

## 建议的最少允许修改面（供root定夺，不是授权白名单）

1. 新 `tools/v0_s3_checkpoint.py`：薄编排，准确packet/candidate/children/账本路径；不复制S2 stage_checkpoint。建议接口 `prepare(packet_path,candidate_sha,ledger_path)` / `execute(child_path)`；实际签名待root冻结。复用phase/OwnedArchive，增加A06/quality路由，接run内raw导出；一份新协调器足够，不新增通用平台。
2. 新 `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py`（建议名）：有限debit adapter，连接COMPLETE03同库authority；配合 `core.py`默认chat与`video_transport.py`interruptible chat两个发送点。不要改业务提示词/输出合同来回避质量。
3. `tools/v0_s2_runtime.py`：profile写入COMPLETE03精确child身份及预留边界、preload debit；`benchmark.py`和`video_evidence.py`：受控新scope验证分支，保留旧历史验证语义、max20/4/PID/time限制。已有phase Oracle通过这两个validator，不需要逐个复制修改。
4. `tools/v0_s2_stage_runtime.py`：有限root/deploy/profile budget注入，支持包实际target与质量阶段的新owned runtime，避免factory默认45/19/copytree硬编码被当S3完整合同。`tools/v0_s2_driver.py`仅在启动传递受控child通道/target配置必要时改，不改通用shell/路径能力。
5. 质量driver可放新协调器的有限函数；独立评分记录可直接JSON按docs06冻结，不需要开发新评分验证平台。只有root认为必须分文件时才新增 `tools/v0_s3_quality.py`，输入分离按上节；不改quality-set/预标/素材准备工具。
6. A06临时网络策略/观测和原workflow绑定是尚未知接口，可先设计为协调器内有限 `run_isolated_package_case(binding,package,original_workflow)`；如平台能力必须独立模块，才新增 `tools/v0_s3_offline_runtime.py`。不在此建议中假称现有实现可用。根packet/Workpack/运行收据由root创建；本worker仅新审计目录。

不需改 `local_program_authority.py`预算政策：调用方显式ledger足够避免worktree新库；model_action的全局ROOT和跨OS文件路径则需adapter明确运行在正确authority上下文。也不改旧S2 coordinator历史slot逻辑、准备工具、全局合同/分母、旧签署、React/FastAPI业务。预算提案两child只是候选分配，不替root决定effective_full语义或发授权。
