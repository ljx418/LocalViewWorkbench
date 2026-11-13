# S3-P4 流纠偏第二轮（实现侧交付）

标签：`stream-correction-02`；角色：implementation（唯一 ClaudeCode 实现者，**未派生任何 Agent**）；
基准：`626d37cf59bfc69324c1a9f886a65cd3f8c56964`；依据：`reports/v0-s3/product-gate0/stream-correction-review-01/{root-decision.json,received/review.md}`（F0 / M2 / m1，root 采纳全部）。

**结论：READY_FOR_REVIEW（不是 StagePASS，不是 product_gate0）。** 本轮只做零进程代码与定向测试；新候选
**没有**取得真实 13/13 fixture PASS，旧 11 PASS/2 FAIL 仍只属于旧候选 `01453ee`/`626d37c`，本轮不改写该
结论。真实复验需要 root 依据母授权另行裁决有限机器预算；本实现者不自行发起、不自行推断剩余额度
（spent 8.446s 不得反推可退 171s），不退款、不清零、不新建 counter、不跑带 binding 的 runner。

## 1. 范围（两源 + 一源未改 + 新报告目录）

| 文件 | 改动 | sha256 |
|---|---|---|
| `tools/v0_s3_supervisor.py` | 终局 drain 的**单一共享有界截止**与 EOF 证明、尾帧拒绝、reader 的**原子游标交接**、诚实的 hash scope | `8e60509d8412479ed8ed7497d35642be26b1027445aae328a027f1237ba6ee42` |
| `tools/test_v0_s3_supervisor.py` | 12 项零进程定向检查 + fake child 的管道保真（`close_streams`） | `3a665215e9fa1a434d043fe67e3a49d74ae420b633d099d698442cd480c921c1` |
| `tools/fixtures/v0_s3_supervisor_fixture.py` | **未改**（本轮无必要；`write_raw` 原始字节语义与 `blocking_persistence` 的故意不完整帧保持） | `1432a6503c07ebed43e9ce36100c18f9840e51af5f6c8d81472ab7439a66df4a`（与上一轮逐字相同） |
| `reports/v0-s3/product-gate0/implementation-integration-stream-correction-02/` | 本报告与全部工件（新增） | — |

未改动：executor/runner、已独审 7 项边界、其余 production owner、公共合同/门限/阈值、固定 24 项、旧证据、
控制 MANIFEST、V2。旧 `reports/v0-s3/product-gate0/implementation-integration-01/report.md` 的既有修改与**全部**
失败/未跟踪工件原样保留，未清理、未 `git add` 全量。

## 2. 三个已证问题的根因与修正

### 2.1 M1（Major）：终局 drain 未证明流结束，未决流仍能发布可归档成功

- **根因**：`tools/v0_s3_supervisor.py` 的 `_drain_streams()` 对两个 reader **各等 0.5s** 并**忽略
  `Event.wait()` 的返回值**；随后只要没有 stream 失败，`self.violation` 仍是 `None` → `unknown_outcome=False`
  → `archive_allowed=True`、`next_phase_allowed=True`。`child.poll()==0`（句柄已退出）被当成了"reader 已结束"，
  但真实 `os.pipe` 的写端仍被持有，两个 reader 仍阻塞在 `read`。同一缺口还有第二条：**真实管道已 EOF 但
  `stdout_buffer` 仍有 14 字节未闭合 JSON 片段**时，drain 也不拒绝。
- **修正**（`tools/v0_s3_supervisor.py`）：
  - **一个绝对有界 drain deadline**：`_drain_deadline()` = `min(now + DRAIN_TIMEOUT_SECONDS, effective_phase_deadline,
    child_deadline)`，**两个 reader 共用**该 deadline（`_await_readers` 用同一个 `end` 依次等待），**不再每流
    额外加 0.5**，也**不越出**原 child/phase 剩余截止；**根本没有剩余时间时连一次都不等**（`budget <= 0` 直接
    返回）。该 deadline 在一次运行内**只算一次并缓存**，process-exited 分支与终局 drain 共用同一截止，
    原先"每流 2.0s"的旧等待也被换成了这一机制（总等待从"2×2.0s + 2×0.5s"降为**一个 0.5s 预算**）。
  - **EOF 证明**：drain 后逐 reader 检查 `reader.finished.is_set()`。未证 → `drain_violation` =
    `STDOUT_STREAM_DRAIN_INCOMPLETE`（stdout 先，stderr 后，与 `_stream_failure` 的既有次序一致）→
    `protocol_violation`（**无更早违例时**）→ `unknown_outcome=True` → 根/预约保留、`archive_allowed=False`、
    `next_phase_allowed=False`、`refund_allowed=False`、`resend_allowed=False`。**canonical receipt 已核验且
    TERMINAL 合法也不能归档**。
  - **尾帧拒绝**：EOF 已证但 `stdout_buffer` 仍有未闭合非空尾帧 → 稳定码 `MESSAGE_INCOMPLETE_FRAME`。
  - **既有更早违例保持主因**：协议违例/stream 失败/期限违例仍是对外主因，排空失败**独立记录**在
    `drain_violation` 与 `notes` 中；`blocking_persistence` 原场景仍以 `PHASE_DEADLINE_EXCEEDED` 拒绝，
    **未偷改原 Oracle**。
  - **不冒充完成**：不用 daemon 属性、不用 `child.poll()==0` 冒充 reader 完成；**不杀**仍在活动的 reader
    线程或任何未知进程；父**只关闭自己拥有且已结束**的读端（`_close_owned_streams`），未证时**诚实留证保留**。
- **Oracle**（真实 `os.pipe` + 真实 `_StreamReader` + 真实 `ParentSupervisor`）：
  - 未证 EOF：`drain_violation=STDOUT_STREAM_DRAIN_INCOMPLETE`、`stdout_drain_complete=False`、
    `stderr_drain_complete=False`、`terminal_received=True`、`canonical_receipt_verified=True`、
    `root_retained=True`、`archive_allowed=False`；`cleanup.proven_stopped=True` 与 `stdout_drain_complete=False`
    **同时成立**（句柄已退出 ≠ 流已结束）。
  - 共享截止：未证 EOF 时整轮 `run()` 耗时 **< 2×0.5s**（实测 **0.029s**，被 phase/child 剩余截止裁掉），
    对照基线同场景 **1.0008s**。
  - 尾帧：EOF 已证 + 14 字节未闭合片段 → `protocol_violation=MESSAGE_INCOMPLETE_FRAME`、`incomplete_frame=True`、
    `archive_allowed=False`。
  - 正常及时 EOF：`protocol_violation=None`、`drain_violation=None`、两个 `*_drain_complete=True`、
    `canonical_receipt_verified=True`、`root_retained=False`、`archive_allowed=True`。
- **内部码新增**：`STDOUT_STREAM_DRAIN_INCOMPLETE`、`STDERR_STREAM_DRAIN_INCOMPLETE`、`MESSAGE_INCOMPLETE_FRAME`。
  **公共协议未改**：`EVENTS`、`MESSAGE_KEYS`、`PROTOCOL_SCHEMA`、`FIXTURE_SCENARIOS`（13）逐项断言未变；
  `Job` enum 与产品合同未触及。
- **风险**：中。终局语义变严：真实 worker 若留下持有管道写端的后代，现在会被**拒绝**而不是假成功——这正是
  M1 的要求，但意味着真实 13 场景的 `blocking_*` 用例的终局码可能与旧观察不同（真实复验仍 NOTPROVEN）。

### 2.2 M2（Major）：有界完整帧在 retain/take 交接中失去解析机会

- **根因**：旧 `_retain` 是 `self.chunks.append(block)`，旧 `take` 是 `chunks = self.chunks; self.chunks = []`。
  父把旧列表换走并 join 空列表后，reader 的**已绑定** `list.append` 仍把整块放进那个被消费的旧列表 →
  `received` 记了全块，父却再也读不到 → 预算内完整帧**只进了 hash，没进 ProtocolState**。
- **修正**：**原子游标交接**（不是换列表）。reader 只 append 到**唯一** `_blocks` 列表；父的 `take()` 先读
  `end = len(self._blocks)`，再取 `_blocks[_cursor:end]`，再把 `_cursor = end`。三步在 GIL 下各自原子，
  **任何顺序都不会丢块**：父读 `end` 之后才到达的块落在 `end` 之后，下一次 `take()` 一定拿到。
  - **临界区内无 `os.read`、无等待、无外部回调**：reader 的关键路径只有一次 `list.append`，父**不持锁**，
    因此父不会因持锁 I/O 失去 deadline 监督。
  - **内存/字节上限未扩大反而减半**：旧实现同时持有 `chunks` + `received`（≤2×256KiB），新实现只有一份
    `_blocks`（≤256KiB）。
  - **统一快照**：`_StreamReader.snapshot()` 一次性给出 `total_observed / kept_bytes / hashed_bytes /
    hash_scope / sha256 / retained_bytes / overflow / error / complete`，`evidence()` 每端只取**一次**快照，
    不再混用两个时刻。
- **Oracle**：受控交错（`sys.monitoring` 的 INSTRUCTION 事件，只对生产 `_retain.__code__` 生效，在首个 CALL
  前暂停 reader）下，**父先接线**再取字节：基线 `parent_message_count=0`（帧被孤立），本候选
  `parent_message_count=1`、`reader_raw_bytes=243`、`reader_error=null`、`finished=true`。**没有删探针**，
  **没有换成高概率普通循环**：真实 `os.pipe` + 真实 `_StreamReader.run/_retain/take` + 生产父 `_consume_stdout`，
  未替换 `chunks` 为自定义列表、未改生产函数。
- **与独审原探针的差异（如实说明）**：独审 `handoff_probe.py` 自己先 `take()` 两次、**之后**才把 reader 交给父。
  在本候选上该探针的 `second_take_bytes=243`（帧**不再被孤立**，可取到），但探针自己已把字节取走，故
  `parent_message_count` 仍为 0；基线上 `first=0, second=0`（帧被孤立、根本取不到）。两者的差别已由探针
  同时记录在工件中（`review_probe` 段），不是靠文字断言。
- **风险**：低—中。reader 的 `chunks`/`received` 两个公开属性被 `_blocks` + `_cursor` 取代；全仓 grep 复核
  **无其它消费者**（`tools/v0_s3_quality_worker.py` 只导入 `PROTOCOL_SCHEMA`，fixture 只导入三个上限），
  独审探针用到的 `raw()`/`total` 保留。

### 2.3 m1（Minor）：超限摘要实际是预算内 prefix，报告却称 all-received

- **根因**：超限时 reader 保留预算内 prefix、丢弃越界尾巴，但 `evidence()` 的 `stdout_sha256` 是对
  `reader.raw()`（= prefix）的摘要，而 `stdout_bytes` 是**观察到**的字节；旧报告称其为"全部已收字节"。
- **修正（诚实 prefix 方案，不保留无界字节）**：
  - `stdout_hash_scope` / `stderr_hash_scope` 三值：`all_observed`（该流送达的全部字节）、
    `prefix_within_budget`（超限后只覆盖预算内 prefix）、`in_flight_prefix`（取快照时还有块在途）。
  - `stdout_hashed_bytes` / `stderr_hashed_bytes`（摘要真正覆盖的字节数）与
    `stdout_total_observed` / `stderr_total_observed`（该流**观察**到的字节数）**分列**，
    `stdout_bytes`/`stderr_bytes` 保持旧义（= 观察到的总字节）。
  - 摘要**只**被称为它覆盖的那一段；**不再**称"子方全部发送量"或"全部 observed"。
  - 旧兼容字段的解释写在 `evidence()` 的 docstring 与本报告：`stdout_bytes`=该流送达总字节、
    `stdout_bytes_retained`=父尚未消费的字节（父缓冲 + reader 未取走的块）、`stdout_sha256`=**reader 保留
    字节**的摘要。
- **Oracle**：stdout 真实 `os.pipe` 观察 262145 字节 → `stdout_overflow=True`、
  `stdout_hash_scope='prefix_within_budget'`、`stdout_hashed_bytes=262144`、
  `stdout_total_observed=262145`、`stdout_sha256=sha256(b'x'*262144)`，
  且 `stdout_sha256 != sha256(全部262145)`；stderr 同样（262145 → `STDERR_STREAM_LIMIT_EXCEEDED` +
  prefix scope）；**恰好 262144** 的两端 → `hash_scope='all_observed'`、`hashed_bytes==total_observed==262144`、
  摘要与整条 wire 相等。**消费前后 hash 可复算**：消费后 `sha256(reader.raw())` 与证据里的摘要一致
  （消费只移动游标，不动保留字节）。
- **风险**：低。新增证据字段是**增量**，旧字段语义未变；全仓无其它消费者。

## 3. 关键实现约束的满足方式（非"仅字符串/常量"证明）

| 要求 | 实现方式 | 定向检查 |
|---|---|---|
| 终局 drain 证明**两** reader 的 EOF/完成 | `_record_drain_state()` 逐 reader 检查 `finished.is_set()`，缺一即 `drain_violation` | `test_the_drain_without_a_proven_end_of_the_stream_is_not_archived`、`test_a_normal_bounded_run_with_a_proven_end_of_the_streams_succeeds` |
| **一个**绝对有界 drain deadline，两 reader 共用，受 child/phase 剩余截止裁剪 | `_drain_deadline()` 缓存单一绝对截止；`_await_readers` 用同一 `end` | `test_the_drain_uses_one_shared_bounded_deadline`（<2×0.5s）、`test_the_drain_never_waits_beyond_the_child_deadline`（<0.10s） |
| 无剩余时间**不得**等固定额外时长 | `budget = deadline - clock()`；`budget <= 0` 直接返回，零等待 | 同上（实测 0.029s，基线 1.0008s） |
| 未证 EOF ⇒ unknown/根/预约保留、禁 archive/nextphase/refund | `drain_violation` → `protocol_violation` → `unknown_outcome=True` → `retained` | `test_the_drain_without_a_proven_end_of_the_stream_is_not_archived`（逐字段断言） |
| EOF 已证但有未闭合尾帧 ⇒ 稳定拒绝 | `_refuse_an_incomplete_frame()` → `MESSAGE_INCOMPLETE_FRAME` | `test_a_trailing_partial_frame_after_the_terminal_is_refused` |
| 既有更早违例保持主因 | `_drain_streams()` 顺序：stream 失败 → `_record_drain_state()` → `_refuse_an_incomplete_frame()`；更早违例不被覆盖 | `test_a_late_read_error_is_not_hidden_by_the_terminal`（主因 `STDERR_STREAM_READ_FAILED`，排空失败独立记录） |
| 不用 daemon/poll=0 冒充 reader 完成 | 判据只有 `reader.finished.is_set()`；句柄退出与流结束是两个字段 | 同上第一例（`cleanup.proven_stopped=True` 与 `stdout_drain_complete=False` 同时成立） |
| 关闭自己拥有的资源；不杀未知线程/进程 | `_close_owned_streams()` 只关**已结束** reader 的读端；活动 reader 一概不动 | 第一例（活动 reader 保持活动，父不杀它） |
| 不丢预算内完整帧；临界区无 I/O/等待/回调 | 单一 `_blocks` + 游标；reader 关键路径只有 `list.append` | `test_the_controlled_handoff_keeps_the_frame`（受控交错） |
| 统一 received/chunks/total/overflow/error 快照 | `_StreamReader.snapshot()`；`evidence()` 每端一次快照 | `test_the_hash_scope_of_an_overlong_stream_is_honest`、`test_the_raw_digest_survives_the_consumption` |
| 公共协议/Job enum 不改 | `EVENTS`、`MESSAGE_KEYS`、`PROTOCOL_SCHEMA`、`FIXTURE_SCENARIOS` 逐项断言 | `test_the_frozen_caps_of_the_protocol_are_unchanged`（本轮扩充） |
| 原 Oracle 不偷改 | `blocking_persistence` 仍以 `PHASE_DEADLINE_EXCEEDED` 拒绝；NaN 仍 `MESSAGE_NONFINITE_NUMBER`；计数仍 `MESSAGE_COUNT_EXCEEDED`；恰好 1024 仍合法 | `test_the_blocking_partial_frame_stays_incomplete`、`test_the_nonfinite_frame_is_complete_and_is_refused`、`test_the_message_count_negative_case_fits_the_frozen_byte_caps`、`test_the_parent_accepts_exactly_the_message_limit`（**本轮未改这四项的期望**） |

## 4. 基线对照（同一探针打旧候选 626d37c 的源，零进程）

```
git show 626d37cf59bfc69324c1a9f886a65cd3f8c56964:LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s3_supervisor.py \
  > /tmp/lvw-s3-correction02-baseline/tools/v0_s3_supervisor.py
# 基线源 sha256 = 5d237cb16c4ed529093f1494ca9972bb59ccfd8e06a70c9fc5287db5dd5fbf7d（与独审 recorded 源哈希逐字相同）
python3 -B reports/v0-s3/product-gate0/implementation-integration-stream-correction-02/stream_correction_02_baseline_probe.py \
  /tmp/lvw-s3-correction02-baseline
```
真实外层 returncode = **0**（探针自身是闸门：基线必须复现缺陷、候选不得复现，否则 rc=1）；
工件 `stream-correction-02-baseline-probe-01.outer.stdout.log`（stderr 空）。实测：

| 场景 | 基线 626d37c | 本候选 |
|---|---|---|
| 受控交错的父消息数 | **0**（243 字节完整帧被孤立；`reader_raw_bytes=243` 仍在，`parent_message_count=0`） | **1**（帧到达 ProtocolState） |
| 独审原探针（自己先 take 两次） | `first=0, second=0`（帧被孤立） | `first=0, second=243`（帧可取，未被孤立） |
| 未证 EOF 的终局 | `archive_allowed=True`、`next_phase_allowed=True`、`protocol_violation=null`、耗时 **1.0008s** | `archive_allowed=False`、`root_retained=True`、`drain_violation=STDOUT_STREAM_DRAIN_INCOMPLETE`、耗时 **0.029s** |
| EOF 后 14 字节未闭合尾帧 | `archive_allowed=True`、`protocol_violation=null` | `protocol_violation=MESSAGE_INCOMPLETE_FRAME`、`incomplete_frame=True`、`archive_allowed=False` |

探针用 `sys.monitoring`（tool id 5，INSTRUCTION 事件）建立**真实受控交错**，不依赖自然调度概率；未替换
生产列表、未改生产函数；**零进程、零网络、零模型/GPU/服务、零 ledger**。

## 5. 实际执行的命令、真实外层退出与工件

外层重定向文件名与 runner 自身日志文件名**全部不同**（`*.outer.stdout.log` vs `*.stdout.log`），无覆盖。

### A. 基线对照探针（零进程）

见第 4 节。外层 rc=**0**；工件 `stream-correction-02-baseline-probe-01.outer.*`。

### B. runner guard 自检（`--mode guard`，不启动真实进程）

```
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode guard \
  --label stream-correction-02-guard-01 --outdir reports/v0-s3/product-gate0/implementation-integration-stream-correction-02
```
真实外层 returncode = **0**；`stream-correction-02-guard-01.stdout.log`：`connect`/`bind`/`Popen`/`system`
四项全部 `offline boundary violation: …`（拒绝发生在审计事件、fork 之前，**未创建任何进程**）。

### C. 外层 guard 之下的定向零进程检查（`--mode focused`，无 binding → 不启动进程）

```
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode focused \
  --label stream-correction-02-focused-02 --modules tools/test_v0_s3_supervisor.py --select <expr> \
  --outdir reports/v0-s3/product-gate0/implementation-integration-stream-correction-02
```
（`--select` 原文见 `stream-correction-02-focused-02.select.txt`）真实外层 returncode = **0**；
runner 日志 `stream-correction-02-focused-02.stdout.log`：**`27 passed, 2 skipped, 118 deselected`**，
收据 `collected_count=29`。2 skipped 全部是 "the finite fixture process machine gate is not bound by the root"
（`[nonfinite_number-MESSAGE_NONFINITE_NUMBER]`、`[message_flood-MESSAGE_COUNT_EXCEEDED]` 这两个**真实进程
场景**在无 root 机器绑定时被正确跳过；**期望码一字未改**）。
收据：`exit_code=0`、`outcome=PASS`、`cleanup_proven=true`、`owned_root_removed=true`、
`admitted_attempts=0`、`child_handles_obtained=0`、**`fixture_process_starts=0`**、
`machine_binding_present=false`、`source_unchanged_during_run=true`、`runner_unchanged_during_run=true`、
`guard.hook_install_count=1`、`handshake_confirmed=true`、`audit_hook_installed_before_product_import=true`、
`host_subprocess=blocked`。
`stream-correction-02-focused-01.*` 为**加完最后两项 hash 检查之前**的一轮（同样 rc=0），保留为证据，未覆盖。

### D. 受影响模块全量回归（`tools/test_v0_s3_supervisor.py`，外层 guard 之下）

```
python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode suite \
  --label stream-correction-02-module-02 --modules tools/test_v0_s3_supervisor.py \
  --outdir reports/v0-s3/product-gate0/implementation-integration-stream-correction-02
```
- `stream-correction-02-module-02.outer.*`：真实外层 returncode = **0**，
  **`134 passed, 13 skipped in 61.94s`**（13 skipped = 13 个需 root 机器绑定的场景测试；guard 之下另 1 个
  "非 runner 生产入口"用例被执行）。收据 `collected_count=147`、`fixture_process_starts=0`、
  `proven_child_handles=0`。
- `stream-correction-02-module-01.outer.*`：加最后两项 hash 检查之前的一轮（rc=0，`132 passed, 13 skipped`），
  保留为证据。

### E. 新增的零进程定向检查清单（12 项，全部通过）

| 检查 | 覆盖 |
|---|---|
| `test_the_drain_without_a_proven_end_of_the_stream_is_not_archived` | 未证 EOF ⇒ 未知/保留/禁归档（逐字段） |
| `test_the_drain_uses_one_shared_bounded_deadline` | 两 reader 共用**一个**预算（<2×0.5s） |
| `test_the_drain_never_waits_beyond_the_child_deadline` | 无剩余时间不等固定时长（<0.10s） |
| `test_a_late_overflow_after_the_terminal_is_not_a_success` | 晚到的 overflow 不被已返回的证据掩盖 |
| `test_a_late_read_error_is_not_hidden_by_the_terminal` | 晚到的 read error 保持主因、排空失败独立记录 |
| `test_a_trailing_partial_frame_after_the_terminal_is_refused` | EOF 后未闭合尾帧稳定拒绝 |
| `test_a_normal_bounded_run_with_a_proven_end_of_the_streams_succeeds` | 正常及时 EOF 成功且可归档 |
| `test_the_hash_scope_of_an_overlong_stream_is_honest` | stdout 超限的 scope/hashed/observed/可复算 |
| `test_the_hash_scope_of_the_error_stream_is_honest` | stderr 超限同上 |
| `test_the_hash_of_an_exact_stream_covers_everything_it_delivered` | 恰好上限的完整摘要与消费后可复算 |
| `test_the_raw_digest_survives_the_consumption` | 消费前后 raw 与摘要不变（流不被说成空） |
| `test_the_controlled_handoff_keeps_the_frame` | `sys.monitoring` 受控交错下帧必达 ProtocolState |

`test_the_frozen_caps_of_the_protocol_are_unchanged` 本轮**扩充**：三个新内部码、`DRAIN_TIMEOUT_SECONDS=0.5`、
`EVENTS`/`MESSAGE_KEYS`/`FIXTURE_SCENARIOS(13)` 逐项断言。

### F. 一处测试保真修正（如实说明）

旧 `FakeProcess` 只暴露写端且由测试持有，**子进程"退出"后写端仍开着**，reader 永远看不到 EOF——这是测试
替身的失真，不是产品行为（真实 `Popen` 的子进程退出时其管道写端随进程关闭）。本轮给 `FakeProcess` 增加
`close_streams()`：子进程"退出"时关闭其写端（`close_streams()` 幂等）。受影响的是**既有测试的夹具保真**，
**既有 Oracle 一字未改**（`blocking_persistence` 仍 `PHASE_DEADLINE_EXCEEDED`、NaN 仍
`MESSAGE_NONFINITE_NUMBER`、计数仍 `MESSAGE_COUNT_EXCEEDED`、恰好 1024 仍 `root_retained=False`）。

方法约束：只用 `os.pipe` + 线程 + 受控 fake reader/handle 驱动**真实** reader 与**真实** `ParentSupervisor`；
**未启动任何 OS 子进程/fixture、未联网、未用模型/GPU/服务、未访问原 ledger**（runner 收据
`fixture_process_starts=0`、`proven_child_handles=0`、`machine_binding_present=false`）。

## 6. 未完成 / 明确不做

1. **新候选的真实 13 场景 fixture 复验未执行（NOTPROVEN）**：本轮无机器绑定、无预算授权；原 counter
   `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json` 只读复核，sha256 前后均为
   **`8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18`**，`active=false`、
   `starts_total=15`（implementation 15 / independent_review 0）、`reserved_wall_seconds=180.0`、
   `spent_wall_seconds=8.446`、`suspension_reason=ORIGINAL180_POOL_FULLY_RESERVED_FINAL04_11PASS_2FAIL`
   —— **未退款、未清零、未新建 counter、未跑带 binding 的 runner**。**不得**从 `spent 8.446` 反推可退 171s。
2. **旧 11 PASS/2 FAIL 不改**：那属于旧候选 `01453ee`/`626d37c`；本轮不改写该结论，也不把它冒充新候选成绩。
3. **不签 StagePASS、不签 product_gate0**：本报告只报 `READY_FOR_REVIEW`；真实 13 PASS、固定全 24、
   Windows/GPU、A06、原 ledger、native descendants 清理与 StagePASS 全部 **NOTPROVEN**。
4. 未改 executor/runner、未改公共合同/门限/阈值/固定 24/旧证据/控制 MANIFEST/V2、未动其余 production owner。
5. 未清理旧工件：旧 `implementation-integration-01/report.md` 的既有修改与全部失败/未跟踪工件原样保留，
   未 `git add` 全量；本轮只提交两源 + 新目录。

## 7. 工件清单（本目录）

| 文件 | 说明 |
|---|---|
| `report.md` | 本报告 |
| `stream_correction_02_baseline_probe.py` | 基线/候选对照探针（受控交错，零进程，自身是闸门） |
| `stream-correction-02-baseline-probe-01.outer.*` | 探针真实执行：外层 rc=0，stdout 为完整 JSON 实测 |
| `stream-correction-02-guard-01.*` | runner `--mode guard` 自检（四事件全拒，外层 rc=0） |
| `stream-correction-02-focused-01.*` | 加完最后两项 hash 检查前的定向轮（rc=0，保留） |
| `stream-correction-02-focused-02.*` | 最终定向轮（27 passed / 2 skipped，外层 rc=0） |
| `stream-correction-02-module-01.outer.*` | 加最后两项 hash 检查前的模块回归（rc=0，保留） |
| `stream-correction-02-module-02.outer.*` | 最终模块回归（134 passed / 13 skipped，外层 rc=0） |
| `stream-correction-02-*.receipt.json` | runner 收据（含 guard 握手、零进程、源未变证明） |
