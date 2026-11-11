# COMPLETE03 与原生路径兼容事实

本报告只对基准 e2eb0cbbb6cae058f8b5da4da8a6775c63060d40 作静态核对；函数精确签名、文件 SHA256、最后修改 commit 见 source-index.json。以下路径均相对 MasterPack。没有调用 authority 模块，未 reserve、bind、transaction、settle 或创建数据库。

## 权威库定位与只读结果（已验证）

`tools/local_program_authority.py:14–17` 以模块文件所在 ROOT 上两级派生 LEDGER，而不是以固定项目身份定位。因此 worker 默认会指到 `/home/administrator/orca/workspaces/LocalViewWorkbench/.lvw-runtime/lvw-prompt-service/program02.sqlite`，绝不能把这个位置当原累计库。本轮未访问此默认位置。

原 root `/mnt/c/workSpace/videoWorkLine/LocalViewWorkbench/LVW_Prompt_Service_MasterPack_v2.0.0` 上两级是 `/mnt/c/workSpace/videoWorkLine`。已提交 `reports/unified-media/live-15/authorization.json:12` 明文绑定 `/mnt/c/workspace/videoworkline/.lvw-runtime/lvw-prompt-service/program02.sqlite`；`bindings.json:1` 是历史工具绑定，`independent-live-15/readonly-ledger.json:1` 保存原 child_path、child_hash、bindings_path、bindings_hash；`live-15/receipt.json:113` 结算3动作、1完整、72秒。授权文件状态 ACTIVE_ONE_SHOT 不能覆盖账本已结算状态。

仅对上述两个大小写精确路径调用 is_file：均存在。分别 sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)，只 SELECT sqlite_master/children 聚合，均成功，均返回26行、全部active=0、calls累计29、checkpoint累计8、非CPU elapsed累计1506秒；没有写 SQL/BEGIN/transaction。两路径结果一致，未据此额外声称文件系统 inode 同一。无需广搜。当前表结构为：

```sql
CREATE TABLE children (run TEXT PRIMARY KEY, stage TEXT, cap INTEGER, seconds INTEGER,
full INTEGER, cpu INTEGER, starts TEXT, issued REAL, expires REAL,
calls INTEGER DEFAULT 0, checkpoint INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
elapsed INTEGER DEFAULT 0, child_path TEXT, child_hash TEXT,
bindings_path TEXT, bindings_hash TEXT)
```

汇总公式：model=Σ(active!=0 ? cap:calls)，full=Σ(active!=0 ? full:checkpoint)，production_seconds=Σ非cpu(active!=0 ? seconds:elapsed)。对应1024/24/172800上限的本次读数差额为995/16/171294；这只是瞬时账面差额，不是已预留或保证可用容量，也不包含任何新S3执行。与已封存live15汇总相容。保留历史消费，不能建新库/拷库扩容。下一正式执行需同库重新原子检查。

## API 的精确语义

- `reserve(run, stage, budget, seconds, full, *, ledger=LEDGER, root=ROOT, cpu_fixture=False)`，124行：先验证ACTIVE/APPROVED/project_owner/hash链；COMPLETE03存在而无效绝不回退LOCAL02。run必须1..80字符字母数字开头；stage在批准列表；budget仅允许api_starts/ollama_starts/comfy_starts/headless_browser_starts/provider_calls/full_checkpoints/model_calls/downloads/cloud_calls/paid_calls/holdout_model_calls，值为非负严格int，后四者必须0。seconds严格int，1..21600；full严格bool，budget.full_checkpoints须与int(full)相等。cap=max(model_calls,provider_calls)，非两者之和，<=128。CPU fixture不许full/cap/api/ollama/comfy starts，headless可用。唯一run永不重放。COMPLETE03仅全局累计，跳过旧分stage/full/start次数限制；CPU不计生产seconds。active=1时整份cap/seconds/full均占用。异常包括WAIT_AUTH scope、WAIT_BUDGET child ceiling/global exhausted、identity already used；错误不会产生成功预留。显式传原ledger与当前冻结root，不能依赖默认值。
- `bind(run, child, *, ledger=LEDGER)`，189行：要求存在active=1且未child_hash；保存child绝对resolve路径和文件hash。并不验证child内容/schema/期限。无效为unreserved/already bound child；文件不存在/JSON无关I/O会原样异常。必须在子文件全部冻结后调用一次。
- `bind_execution(run, bindings_path, *, ledger=LEDGER)`，231行：bindings对象各value须有path/sha256，先逐文件验hash；存在active=1、calls=0、未bindings_path才保存绝对路径/hash。无绑定child先决/期限检查；因此编排层负责完整顺序与范围。失败为runtime tool identity mismatch 或 execution bindings already sealed or child inactive。不存在文件、JSON/字段错误也直接失败。
- `model_action(child_path)`，198行：无ledger/root参数；读child，调用模块全局ROOT的approved/program_paths，校验program（允许None或当前approval相对路径）与program_sha256；使用child.budget_ledger。要求row active恰好1、未过期、child绝对路径/hash精确相等、calls<cap；逐frozen_files与samples验hash，execution_bindings_required时校验绑定文件及各工具hash。所有通过后在原子事务中 calls+=1、checkpoint=full，随后调用方才发送。异常WAIT_BUDGET expired/altered/exhausted、program changed、source/sample/tool drift。接口不知道推理/加载/卸载类型，不自动检验PID、端口、模型digest、stage；这些需外层绑定。冻结文件相对ROOT，绝对sample Path会保留绝对性。failed send、timeout、cancel均不得回退已扣动作。
- `settle(run, observed_calls, *, ledger=LEDGER)`，244行：只接受active=1与严格int observed_calls==row.calls；ceil(now-issued)<=seconds才写active=0和elapsed；保留calls/checkpoint。返回actual_model_actions/effective_full_checkpoint/zero_model_startup/elapsed。清理、归档是调用方必须证明的前置，不是函数自动检查。次数不符或超时则抛错并保留全额预留，不能以日志缺失当0。
- `close_retaining_reservation(run, *, ledger=LEDGER)`，263行：只将匹配active=1更新2，无匹配时静默无操作。active2禁止model_action/settle，却在totals按真值保留cap/seconds/full；不是退款、不是清理已证。重复close不再改变。没有公开active2恢复/补结算API，不能自行改SQL。
- `transaction`，91行会mkdir、CREATE TABLE、BEGIN IMMEDIATE，因此即便只想取totals也不能调用它来做只读调查；本轮完全绕过该模块，使用URI mode=ro。SQLite/文件/JSON基础异常未统一包装，调用方须保留错误并fail closed。

## 哪些旧层不兼容，最小接线位置

1. `tools/v0_s2_stage_checkpoint.py:43,130,143,175,218,275,426,482` 是旧LOCAL01/slot/lease文件账本与S2 packet/hash逻辑；`BUDGET:60` provider83和preload20是不同计数，不能直接把旧budget传reserve（含大量不允许key）。不能调用旧execute/prepare当S3入口，也不能只改PROGRAM字符串。以新薄协调器调用已有phase/factory，显式同库reserve→完整child→bind→installed binding→bind_execution。
2. `tools/v0_s2_runtime.py:115,133` 写旧program_id/scope且固定7200秒；`benchmark.py:24`、`video_evidence.py:17`验证同旧ID/scope。前者固定20请求/10图10片，后者max_runs<=64/单run最多4 provider attempt。这些是计量/所有权护栏，不应移除；新增精确COMPLETE03 child/hash/scope绑定分支，由子授权剩余时间限制新profile。仅旧fixture来源校验 `stage_inputs.py:35,49` 的LOCAL01应保留为历史来源证明，不是新许可。
3. 原V0 Provider没有全局sqlite扣额：默认图片 `core.py:324` chat；默认视频/热图片/热视频 `video_transport.py:163` chat、195行附近实际connection.request；`video_evidence.py:59`只内存attempt+日志；`benchmark.py:184` only warm事件。必须在两条实际chat发送边界接相同authority，避免在submit统一扣一次（视频4次，文件负例0次）。`tools/v0_s2_runtime.py:208` preload在发送前另扣一次；cleanup keep_alive0不扣模型。local日志与HTTP access log只能佐证，不能替代先扣账本。
4. 已签统一服务 `lvw/backend/app/provider.py:493–525` 已按LVW_AUTHORIZATION_CHILD调用model_action，但不是原生Comfy路径；其日志provider_call_started在扣额之前，不能简单按事件数settle，拒绝扣额时可能没有对应send。`reports/unified-media/authority.py:80,133,142`仍用默认program.LEDGER，直接从worker调用会走错库。可借用接口形状，不能照搬整套R1授权/harness。
5. 跨Windows Comfy与WSL authority是实际接线缺口：增量包只含bridge/workflows，native Python不能假定可import仓库tools或访问WSL `/mnt/c`字符串。建议root冻结一个有限的内部debit适配接口（如`authorize_model_action(child_identity, action_kind, request_id)`），由拥有原库的同一authority执行并返回已扣收据后才发送；传输可为有限本机控制通道，不新增通用调度/任意shell。具体传输、超时与未知返回保留预留由root选择。不要把SQLite复制进安装包，或把Linux child路径直接用于Windows。
