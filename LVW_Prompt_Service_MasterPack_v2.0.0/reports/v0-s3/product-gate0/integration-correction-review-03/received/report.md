# S3-P4 集成集中纠偏 03：H / C / O / S / A 一次合并修复

- 状态：**READY_FOR_REVIEW**。本报告不宣布 Stage PASS、不宣布产品 Gate0、不宣布固定 24 PASS。
- 基准：`e3c507227d534c56d571c6324729644f9dbac1ac`（root 决定 `integration-correction-03/root-decision.json`，采纳独审 F0/M3/m2）。
- 范围：`tools/v0_s3_supervisor.py`、`tools/v0_s3_coordinator.py`、`tools/test_v0_s3_supervisor.py`、`tools/test_v0_s3_integration.py` 与本 NEW 目录。executor / runner / fixture / 其余 owner / 公共合同 / 枚举 / 阈值 / 固定 24 / 控制 MANIFEST / 旧工件 / V2 一律未改。
- 上一轮已关闭项：M1（EOF drain）、M2（帧交接）保持关闭，其行为在本轮被原样保留并由本报告的探针再次复算。

---

## 1. 五项修正：路径 / 触发 / Oracle / 负例

### H（Major）已完成行的 history 期限不再约束后续行

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_supervisor.py`：`ParentSupervisor._fix_history_deadline` / `_close_history_deadline` / `_deadline_state`（`history_deadlines`、`history_records`、`history_completed`）；`ProtocolState.accept` 的行事件分支（`rows_started`、`rows_finished`） |
| 触发 | 独审原探针场景：I01 在 fake clock 0 发 `ROW_STARTED`+`HISTORY_WAIT_STARTED`（期限 600），clock=10 发 `ROW_FINISHED`，clock=500 I02 发 `ROW_STARTED`+`HISTORY_WAIT_STARTED`（期限 min(1100, phase 1000, child 2000)=1000），clock=601 继续运行 |
| Oracle | 601 时刻 `deadline_state` 必须为 `None`：已结束行的期限只约束它自己的等待，不得中断后续行；I02 自身 600s、phase、child 三个期限仍各自 exact（等于期限不拒绝）/`oneover`（超 1 单位即 `HISTORY_DEADLINE_EXCEEDED:I02` / `PHASE_DEADLINE_EXCEEDED`）有效 |
| 负例 | ① I01 结束后重复 `ROW_STARTED` → `MESSAGE_ROW_STARTED_REPEATED`；② 已结束行重新开始 → `MESSAGE_ROW_REOPENED`；③ 已结束行再发 `HISTORY_WAIT_STARTED` → `MESSAGE_ROW_REOPENED`；④ 重复 `ROW_FINISHED` → `MESSAGE_ROW_FINISHED_REPEATED`；⑤ 重复 `HISTORY_WAIT_STARTED` → `MESSAGE_HISTORY_STARTED_REPEATED`。审计不靠删除换取重复：`history_records` 保留 `first_start`/`deadline`/`completed_at` |
| 证据 | `observations.json:history_completed_row_expiry`（`state_at_601=null`、I01 `{first_start:0, deadline:600, completed_at:10}`、I02 `{first_start:500, deadline:1000, completed_at:null}`、`history_completed=["I01"]`、`protocol_violation=null`）；`tools/test_v0_s3_supervisor.py::test_a_finished_row_does_not_constrain_the_later_rows`、`test_the_history_deadline_of_the_active_row_is_exact_and_one_over`、`test_the_phase_and_the_child_deadline_stay_exact_and_one_over`、`test_the_history_audit_is_kept_and_a_row_is_not_reopened`、`test_a_finished_row_does_not_stop_the_run` |
| 未改 | 固定 600 / 10800 / 21600 未动；期限不可延长、不可重发延长的语义未动 |

### C（Major）缺 cleanup 收据不得 12/12 PASS

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_coordinator.py`：`TWELVE_REQUIREMENTS`（12 个键全部新增 `cleanup`）、`CLEANUP_RECEIPT`、`_receipt_status`（缺失 → `RECEIPT_MISSING`）、`aggregate_twelve_keys` 的 cleanup 证明检查与汇总字段 `cleanup_receipt_required` / `cleanup_proven` |
| 触发 | 传入本 owner 接受的全部命名收据（run/candidate 一致、`stage_pass_claim=false`、`independent=true`、`real_isolation=true`）但**不提供 cleanup** |
| Oracle | `pass_count == 0`、`not_run_count == 12`，每键 `status=NOT_RUN` 且 `reasons` 含 `cleanup:RECEIPT_MISSING`；cleanup 收据合法且 `cleanup_proven is True` 时 12/12 PASS（正例补合法**本轮**清理收据） |
| 负例 | ① 缺 cleanup → 12×NOT_RUN；② `cleanup_proven=False` → 12×BLOCKED（`cleanup:CLEANUP_UNPROVEN`）；③ `cleanup_proven="true"`（字符串）→ 12×BLOCKED；④ 缺 `cleanup_proven` 字段 → 12×BLOCKED；⑤ cleanup `status=FAIL` → 12×FAIL（失败优先）；⑥ cleanup 属另一 candidate → 12×FAIL（`cleanup:BINDING_MISMATCH`）；⑦ cleanup 属外来 kind → 12×NOT_RUN（`cleanup:RECEIPT_KIND_NOT_ACCEPTED`）；⑧ cleanup 声称 `stage_pass_claim=true` → 12×BLOCKED（`cleanup:RECEIPT_STAGE_PASS_CLAIM_INVALID`） |
| 边界 | 固定的 12 键集合与产品分母未变；cleanup 是**全局**清理义务，故 12 键的 `required_receipts` 都显式列出 `cleanup`，`reasons` 显式体现原因。旧 S2 九项、缺 independent/QS、无真实隔离的负例继续拒绝 |
| 证据 | `owner-observations.json`（`all12_without_cleanup` = 0 PASS/12 NOT_RUN、`all12_with_legal_cleanup` = 12 PASS）；`tools/test_v0_s3_integration.py::test_a_missing_cleanup_keeps_every_key_not_run` 等 8 个新用例 + `test_twelve_keys_are_exactly_twelve_and_complete`（正例） |

### O（Major）父原件的祖先链接与根逃逸被拒绝，且最终清单调用重核

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_coordinator.py`：`ParentOriginalEvidence._bound_root_fd` / `_reference_parts` / `_open_inside_root` / `_seal_one` / `seal_originals` / `verify_originals` / `verify_selected_root` / `manifest`；模块级 `_no_follow_open_supported`、`_digest_handle`（旧的 `_digest_file` 已删除，避免留下 TOCTOU 路径） |
| 触发 | 合成绑定根 + 根内 `redirect` 指向根外目录的祖先 symlink，用 `redirect/canonical.json`、`redirect/source.json`、`redirect/raw.bin` 三个引用封存 |
| Oracle | 逐层 `O_NOFOLLOW` 打开（每个路径分量从**其父目录的 dirfd** 打开）+ `fstat` 身份核对 + **摘要取自同一已验证句柄**；祖先链接必须被拒绝（`S3_ORIGINAL_REDIRECT_FORBIDDEN:<category>`），不得只查最终 `lstat`；不得存在 `exists/resolve` 预检后普通 `open` 的窗口 |
| 负例 | ① 祖先 symlink 逃逸 → 拒绝且 `evidence.originals == {}`；② 最终分量本身是链接 → `S3_ORIGINAL_REDIRECT_FORBIDDEN`；③ 封存后改写原件 → `manifest()` 拒绝（`S3_ORIGINAL_CHANGED`/`S3_ORIGINAL_REPLACED`）；④ 封存后以另一文件替换（同字节、inode 可能复用）→ `S3_ORIGINAL_REPLACED`（身份含 `ctime_ns`/`mtime_ns`）；⑤ 封存后原件丢失 → `S3_ORIGINAL_UNREADABLE`；⑥ 封存后根被替换 → `S3_SELECTED_ROOT_REPLACED`；⑦ 封存后祖先目录变成链接 → `S3_ORIGINAL_REDIRECT_FORBIDDEN`；⑧ 平台缺少安全原语 → 显式 `S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED` fail closed |
| 消费边界 | `manifest()` 现在就是消费边界：它先调用 `verify_originals()`（独立重开、比对身份/变更时间/长度/hash），任一不符即抛错，不再输出旧清单。根 identity **不**等价于原件未变 |
| 正例 | 纯根内常规文件（`canonical.json`、`temp/source.json`、`temp/raw.bin`）封存通过、`manifest()` 重核通过、`reverification.verified=true`、3 项全部复核 |
| 平台边界 | 本实现只用 POSIX `openat` 语义（`O_NOFOLLOW`/`O_DIRECTORY`/`dir_fd`）；**未**声称 Windows / junction / reparse 已证明，WSL 字符串不作为 Windows 证据；不扩大任何系统权限（只读、只在本根内） |
| 证据 | `owner-observations.json`（`symlink_escape.escape_reason=S3_ORIGINAL_REDIRECT_FORBIDDEN:canonical`、`changed_raw` 的四个拒绝原因）；`tools/test_v0_s3_integration.py::test_parent_refuses_an_ancestor_link_out_of_the_bound_root` 等 7 个新用例 |

### S（Minor）流快照一致发布，完成标志与摘要同一状态

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_supervisor.py`：`_StreamReader` 的发布状态机（`_publish_lock`、`_digest`、`_kept`、`_complete`、`_published`、`_publish_locked`、`_publish_end`、`_publish_error`）、`_stream_state()`、`_retain()`（append + digest + total + 发布为一次临界区）、`snapshot()` |
| 触发 | 独审原受控 publication 交错：① 在 `snapshot` 读到发布状态之后暂停，生产者送入 `hello` 并 EOF，reader 实际完成后释放；② 在 reader 读到字节之后、发布之前暂停（`run` 中 `_retain` 调用点） |
| Oracle | 快照必须是**同一时刻**的状态：`hashed_bytes == kept_bytes`、`sha256` 等于原始字节对应前缀的摘要、`total_observed >= kept_bytes`、scope 与 complete 互相一致；**未 EOF 的流即使为空或 hashed==observed 也只能是已观察前缀**（`hash_scope='observed_prefix'`），不得声称全流；临界区内无 `os.read`/等待/外部回调，父的期限不被 reader 阻塞 |
| 负例 | 旧混读状态 `complete=true` 且 `hashed_bytes != total_observed`、以及 `hashed_bytes==5 && total_observed==0` 的混读都必须不再出现（探针显式断言其不成立）；`prefix_within_budget` 与 `all_observed` 语义保持不变 |
| 实现要点 | 原子性来自 reader 自己的锁与不可变发布状态，不依赖 GIL 的多步原子性；有界内存与 caps 未扩大（`MAX_STREAM_BYTES` 仍为 256KiB，摘要为滚动 sha256）；游标帧交接（M2）与 EOF/drain 逻辑未回退 |
| 证据 | `observations.json:snapshot_completed_publication`、`snapshot_before_total_publication`、`unfinished_scope`；`tools/test_v0_s3_supervisor.py::test_the_snapshot_never_mixes_two_moments`、`test_the_reader_publishes_the_bytes_and_the_total_together`、`test_an_unfinished_stream_is_only_an_observed_prefix` |

### A（Minor）历史真实成绩的事实更正（只在本报告追加，不改旧工件）

- 历史 final04 的真实收据 `reports/v0-s3/product-gate0/fixture-final-04/finite-fixture-implementation-04.receipt.json` 与 `…node-results.json` 明确：`candidate_sha_claim = 01453ee07b4774a55711c5cf5642c12d0394a35c`、`collected_count = 13`、`pytest_summary_line = "2 failed, 11 passed in 5.43s"`、失败项为 `nonfinite_number` 与 `message_flood`。
- 因此：**真实 11PASS/2FAIL 只属于 `01453ee`**。`626d37c` 与 `e3c5072` 是其后的**零进程**纠偏候选，**没有任何真实 13 场景结果**，不得与之共有该成绩，也不得把零进程计数当作 13 场景 PASS。
- 旧报告、旧收据、旧失败工件一律未改写、未删除；本条只在本 NEW 报告中追加。

---

## 2. 执行、边界与机器收据

### 2.1 自然环境核实

- `CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0` 在启动时即为此值，未修改、未包装、未改审批配置；本轮未出现 429，未换模型/账号/供应商。
- 解释器：`/usr/bin/python3`（CPython 3.12.3，`sys.monitoring` 可用）。pytest 8.4.2。

### 2.2 pre-import 硬 guard

`implementation-integration-correction-03/hardguard.py` 在 pytest、任何插件与任何候选/测试模块导入**之前**安装 `sys.addaudithook`：

- 拒绝 `subprocess.*`、`socket.*`、`os.exec/os.spawn/os.posix_spawn/os.fork/os.forkpty/pty.spawn`、`os.system`；
- 拒绝打开 `shared-counter.json` 与任何 `ledger*.db/.sqlite/.sqlite3`；
- 每次拒绝都记入 `*.guard.json`（`observed denials`）。

五个入口全部经由该 guard 运行，guard 收据显示 `installed_before_candidate_import=true`。

### 2.3 命令、退出码与计数

统一入口：`python3 -B reports/v0-s3/product-gate0/implementation-integration-correction-03/run_guarded_checks.py`（外层日志名 `*.outer.stdout.log` / `*.outer.stderr.log`，不覆盖 runner 自身的日志；原始流、真实退出码、argv、cwd、源哈希全部写入 `run.receipt.json`）。

| 入口 | 实际 exit | 结果 |
|---|---:|---|
| `probes.py`（独审原探针的适配） | 0 | 12 组观测全部符合修正后的期望，含成功复现旧缺陷的对照断言 |
| `owner_probe.py`（协调器 owner 探针） | 0 | 缺 cleanup 非全绿、祖先链接拒绝、改写/替换/丢失/根替换四项拒绝、合法根内文件封存与复核通过 |
| `focused-supervisor`（定向） | 0 | 41 passed / 11 skipped / 103 deselected |
| `focused-integration`（定向） | 0 | 25 passed / 29 deselected |
| `affected-modules`（受影响集合回归，一次） | 0 | **186 passed / 14 skipped / 9 deselected**（两个被改模块共 209 收集项） |

- 受影响集合说明：本轮改了两个 owner 模块及其两个测试模块，因此**受影响集合就是这两个模块**；该回归只跑一次，不是机械重跑。`tools/test_v0_s3_quality_phase.py`（257）、`test_v0_s3_runtime_binding.py`、S2 各模块、fixture、executor、runner **均未重跑**（它们未被本次改动触及）。
- 9 个被显式 deselect 的用例是**有限 CPU fixture 的机器门禁**用例（`test_the_single_guard_admits_a_start_once…` 等，名单见 `run.receipt.json:machine_gate_tests_deselected`）：它们会**真实**创建 fixture 子进程，需要 root 的机器绑定；本批为零进程纠偏批，没有该绑定，硬 guard 在 `affected-modules` 中实际拒绝了其中一次 `subprocess.Popen`（`run.receipt.json` 中 `affected-modules.guard_denials=["subprocess.Popen"]`），该次拒绝发生在 `test_an_unknown_start_keeps_its_charge_its_slot_and_the_root` 期望的拒绝分支内，测试通过。executor、fixture、runner 本轮未改，不受本次修正影响。
- 原始流：`*.outer.stdout.log`、`*.outer.stderr.log`（真实字节，未重建、未遮蔽退出码）；探针观测 `observations.json`、`owner-observations.json`；机器收据 `run.receipt.json`、每个入口的 `*.guard.json`。

### 2.4 共享计数器（只读）

`/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json` 在批次前后**只读**核对：

- `sha256 = 8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18`（前后一致，`counter_unchanged=true`）
- `active=false`、`starts_total=15`、`reserved_wall_seconds=180.0`、`spent_wall_seconds=8.446`

未退款、未清零、未新建 counter、未带 binding 跑真实 run，未从 spent 反推可退额度。

### 2.5 本批的源哈希

| 文件 | sha256 |
|---|---|
| `tools/v0_s3_supervisor.py` | `c669e97f06f2d90061a1a8cedf859db454c5783daf6591418f7ff13bb9d848b3` |
| `tools/v0_s3_coordinator.py` | `a026a8576d7433199b5202059243f972bbbfeeead1a38c7aac241ec665b3164d` |
| `tools/test_v0_s3_supervisor.py` | `683bf1e2344355c6507c2f7bd3f58c2d781bc6e9f1969f723e2138695ff088c7` |
| `tools/test_v0_s3_integration.py` | `1bee589688e0d343c228ac0faf267b20cc1dbeacf831ab38ca87badb9edb5814` |
| `…/probes.py` | `927fb65d0a91c88ed4c98840a497e32c00b7baa8c353a718de26f591953b1685` |
| `…/owner_probe.py` | `caa2e4e503f044e6ede274f5706fef6d50184ba28aa8f4cff548dc00513c6b7e` |
| `…/hardguard.py` | `6ecaa1b5e236f7fda6abd2c4da12312d1746ebf7cb18e65f7473f900ce7f6db2` |
| `…/run_guarded_checks.py` | `d7bbe520a762e54a8d0c065e010b97a59202dc6e518c57e6312f4b0bc9ca277d` |
| `…/pytest_entry.py` | `6df6964df9f3386dcaf71ac54e4efcc55fce4b9693a1c86ad38e8af84c7e0d42` |

候选提交 SHA 见 `candidate-delivery.json`（随本报告同批提交后的交付记录）与交接消息。

---

## 3. 未验证的限制（明确保留 NOT_PROVEN）

- **真实 13 场景**：本候选**没有**任何真实进程执行结果。原 13 场景的真实成绩仍只属于 `01453ee`（11PASS/2FAIL）。本候选的真实 13 仍是 `NOT_PROVEN`。
- **固定 24**：I01–I24 本轮未跑，不是 24PASS；I01–I24 仍为新离线集成的固定集合，不是产品十二项。
- **Windows / native / junction / reparse / GPU / A06 实机 / 原生服务后代与显存释放 / 原账本 debit / 实际质量 / 归档与根迁移**：全部**未验证**，不在本批范围，也不得因本报告而声称 PASS。本报告的 O 项证明只覆盖 POSIX 的 no-follow 打开语义；`root migration` 仍未验证，`verify_selected_root` 对不同路径仍直接拒绝。
- **产品十二项**：V0-A01…A12 的真实产品收据仍然缺失；本批的 12 键聚合只是离线 owner 的行为证明，`stage_pass_claim=false`、`product_gate0=false` 不变。
- **原生 QualityPhase / native driver / 依赖闭包**：未证明。
- **A06 隔离、安装回滚、注册表基线**：未验证。

## 4. 清理

- 本批**零**产品进程、零网络、零模型/GPU 服务、零原账本动作；硬 guard 记录到的唯一拒绝是 `affected-modules` 中一次被期望的 `subprocess.Popen` 拒绝。
- 自建的合成根与合成文件（`owner-outside-bound-root`、`phase_clip`、`child_clip`、`shared`、`zero_remaining`、`history` 与 `observations.json` / `owner-observations.json`）保留在本 NEW 目录内供复核；`owner-bound-root` 在探针的最后一步已被替换根占用（替换本身是被拒绝的证据，替换根为空目录，git 不跟踪空目录），**未**触碰任何生产根、任何用户原件、任何旧工件。
- 临时环境变量由 root 在本批结束后恢复；本 worker 未自行增删任何环境变量，未改审批配置。

## 5. V0–V3 开发大纲（来自 `plans/execution-control.json:development_outline`，不因本批增加任何产品完成数）

| 交付 | 阶段 | 已完成/总数 | 边界 |
|---|---|---|---|
| V0 | V0-S0 | 1/2 | 历史探索已结束且 NO_GO 保留；V0-Min 按后续范围签署，不回填 S0 PASS |
| V0-Min | V0-S1 | 5/5 | 已签仅 V0-Min |
| V1前置 | R0 | 1/2 | 仅 R1a 前置单图子集可确认；不把完整视频/Q01 算通过 |
| V1早期切片 | R1a | 5/5 | 已签仅单图切片；完整 V1 未完成 |
| V0.1 | V0-S2 | 7/8 | Full08 fresh cumulative 9/9, offline 541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0.2 | V0-S3 | 0/6 | 已有设计，未完成正式交付；本批只推进 S3-P4 离线纠偏的实现侧，**不**增加 S3 的完成子步 |
| V1 | R1 | 0/4 | 最小统一图视频切片 3/3、UM10 机器与独审通过，用户已确认当前前端与基本视频反推；完整 R1 四子项仍 0/4 |
| V1 | V1-M1 | 0/3 | 用户批准纳入 V1；设计/合同审查中，未实现、未测试、未签署 |
| V1 | R2 | 0/4 | 已有设计，未完成正式交付 |
| V2 | R3 | 0/4 | 已有设计，未完成正式交付 |
| V2 | R4 | 0/4 | 已有设计，未完成正式交付 |
| V3 | R5a | 0/4 | 已有设计，未完成正式交付 |
| V3 | R5b | 0/4 | 已有设计，未完成正式交付 |
| V3 | R5c | 0/4 | 已有设计，未完成正式交付 |

1. 当前坐标：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION / RUNNING。
2. 本批完成：H/C/O/S/A 五项一次合并修复的实现与定向证据；**没有**产品机器通过，没有人工签署，没有 Stage PASS。
3. 最后通过门禁：UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW，621b1bf，仅已签统一切片。
4. 当前阻塞：真实 13 场景、全 24、native/Windows/GPU/A06/原账本/实际质量与根迁移均未证明。
5. 全局路线位置：S3-P4 离线纠偏承接既定 V1 路线，不激活 V2/V3。
6. 剩余工作：root 集中裁决 + 隔离独审复算；机器绑定与真实 fixture 执行仍需 root 的有限预算决定。
7. 下一责任人：root（本 worker 已完成并交接，不 keep-open）。
8. 所需授权：本批未新增任何授权；真实 fixture 执行仍需 root 的机器绑定。
9. 证据目录：`reports/v0-s3/product-gate0/implementation-integration-correction-03/`。
10. 精确停止原因：本批任务完成，发送一次 worker_done 后结束；不宣布 Stage PASS。

## 6. 交接

- 交付：新候选（两个 owner 模块 + 两个测试模块 + 本 NEW 目录）、五项路径/触发/Oracle/负例、机器收据与原始日志、未验证限制与清理。
- 旧工件与旧 `report.md` 的既有修改**保持原样**，本 worker 未做全量 `git add`，只提交本批授权范围内的文件。
- 状态：**READY_FOR_REVIEW**（不是 Stage PASS，不是产品 Gate0，不是 24PASS）。
