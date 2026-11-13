# S3-P4 原件集中纠偏 04：O1 读取窗口的改动被拒绝，O2 特殊条目不再阻塞

- 状态：**READY_FOR_REVIEW**。本报告不宣布 Stage PASS、不宣布产品 Gate0、不宣布固定 24 PASS、不宣布真实 13 场景成绩。
- 基准：`56a1c5051812b27e8484781890918af3bb9feb41`（root 决定 `originals-correction-04/root-decision.json`，采纳独审 F0/M2/m0：O1「读取窗口内的改动被接受并发布旧 verified」、O2「final 常规文件检查之前的 FIFO 同步阻塞 open」）。
- 实现 HEAD（交付前）：`a6b527a8cd2699ede62883b3dea3ffaafb24fdf3`（相对基准只有报告追加，源相同）。本轮交付的新候选 = 本报告所在提交。
- 范围：`tools/v0_s3_coordinator.py`、`tools/test_v0_s3_integration.py` 与本 NEW 目录 `reports/v0-s3/product-gate0/implementation-originals-correction-04/`。supervisor 及其测试、executor、runner、fixture、qualityworker、其余 owner、公共合同、阈值、固定 24、控制 MANIFEST、V2、旧报告、旧失败收据一律未改。
- 已关闭项：独审已关闭的 H、C、S、A 在本轮**不动**（不重构已关闭源、不重跑其全套）。本轮只集中关闭 O1 与 O2。
- 交付源的 SHA256：`tools/v0_s3_coordinator.py` = `814589e88f4d3d32a498bca7fc14de8d7b9efff852f25bdcfe7651bb5017860e`；`tools/test_v0_s3_integration.py` = `104a08c6207658051293fe65331455779b7a961480065b934b8bc191de450224`。

---

## 1. O1（Major）：seal 与 manifest 共用同一安全读取程序，读窗口内的改动一律拒绝

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_coordinator.py`：`ParentOriginalEvidence._read_original_safely`（唯一的安全读取程序，seal 与 verify 共用）、`_refuse_a_changed_window`、`_refuse_a_changed_path`、`_compare_identity_with_the_seal`、`_compare_content_with_the_seal`、`_open_inside_root`（现返回句柄与**祖先身份链**）、`_seal_one`、`verify_originals`、`seal_originals`；模块级 `_digest_handle`（摘要仍取自同一已验证句柄） |
| 触发 | 独审同款受控触发：在已验证句柄上包装 `os.read`，先从句柄读出 ORIGINAL，再**在该块返回之前**写入改动；随后真实读到 EOF |
| Oracle | 读取程序对**同一句柄**在读前 `fstat`、读后 `fstat`，两次都必须满足：常规文件、类型不变、身份 `(st_dev,st_ino)` 不变、`st_size` 不变、`st_ctime_ns` 不变、`st_mtime_ns` 不变，且**实际消费长度 == 读前的 `st_size`**；读后还要从绑定根**安全逐层重新走一遍路径**：根身份、每个祖先目录身份、最终分量身份都要与第一次走过的链一致，最终分量用**实际已打开的句柄** `fstat` 与已验证句柄比较。任一不符即抛错，**不发布旧 verified**。摘要与旧 entry 匹配而当前文件已改，不再是放行理由 |
| 负例 | ① 读中**同长度改写**（ORIGINAL→MODIFIED，8 字节）→ `S3_ORIGINAL_CHANGED:<category>`；② 读中**同字节重写** → `S3_ORIGINAL_CHANGED:<category>`（摘要不变，只有对象时间能看出，故必须核时间）；③ 读中**增大** → `S3_ORIGINAL_CHANGED`；④ 读中**截断** → `S3_ORIGINAL_CHANGED`；⑤ 读中**对象替换**（unlink + 新建）→ `S3_ORIGINAL_REPLACED`（路径重走发现已不是同一对象）；⑥ 读中**路径变成链接** → 拒绝（`S3_ORIGINAL_*`）；⑦ 读中**祖先被替换**（祖先目录换名后另建同名目录）→ `S3_ORIGINAL_REPLACED:<category>`（祖先身份链不同）；⑧ 读中**根被替换** → `S3_SELECTED_ROOT_REPLACED`。以上 8 种在**初次 seal** 与**消费 manifest** 两条路径上都被拒绝 |
| 不退回旧写法 | 路径重走用 `os.open(..., O_NOFOLLOW|O_NONBLOCK, dir_fd=父目录)` + `fstat`，比较的是**两个已打开句柄的身份**，不存在「先 `lstat` 再普通 `open`」的窗口，也不存在「只比摘要」就放行的情况 |
| 部分发布 | `seal_originals` 只在全部引用成功后整体赋值 `self.originals`；失败时 `self.originals` 保持原值（首次封存失败时为 `{}`），不发布半份新封存 |
| 边界（明确声明） | 该检查覆盖的窗口是「已验证打开 → 该句柄摘要结束」以及其后的「从绑定根重走路径」。它**不**声称返回后文件永不变，也**不是**整批原件的文件系统原子快照：每个原件各自检查，整批不冻结。未新增任何监控、后台线程或平台服务 |
| 正例 | 根内常规文件封存后 `manifest()` 通过：`reverification.verified=true`、3 项复核、hash 与长度与真实字节一致（`962f85a2…` / 8 字节） |
| 证据 | `owner-observations.json` 的 `O1_seal_window` 与 `O1_consume_window`（16 条触发各自的拒绝原因、`trigger_fired`、`change_observable_in_the_object`）；`tools/test_v0_s3_integration.py` 的 `test_the_seal_refuses_an_original_that_changes_during_the_read[5]`、`test_the_manifest_refuses_an_original_that_changes_during_the_read[5]`、`test_the_manifest_refuses_an_ancestor_that_is_replaced_during_the_read`、`test_the_manifest_refuses_a_root_that_is_replaced_during_the_read`、`test_the_manifest_refuses_a_path_that_became_a_link_during_the_read`、`test_a_failed_seal_publishes_no_originals` |

## 2. O2（Major）：final 常规文件检查之前不再对 FIFO/特殊条目同步阻塞 open

| 项 | 内容 |
|---|---|
| 路径 | `tools/v0_s3_coordinator.py`：模块级 `_non_block_open_supported`、`_safe_open_supported`、`_directory_open_flags`（`O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK`）、`_final_open_flags`（`O_RDONLY|O_NOFOLLOW|O_NONBLOCK`）；`ParentOriginalEvidence._bound_root_fd`（能力核对 + 标志被内核接受）、`_open_inside_root`（最终分量以 `O_NONBLOCK` 打开后立刻 `fstat`）、`_read_original_safely`（类型检查在读之前） |
| 触发 | 真实 `os.mkfifo`：① 初次 seal 时位置就是 FIFO；② 已封存的 raw 被换成 FIFO（无写端） |
| Oracle | 最终分量以**非阻塞、不跟随链接**的方式打开，打开后**立刻** `fstat`：不是常规文件即拒绝（设备、目录、链接、FIFO、socket 一律拒绝），拒绝发生在任何读取之前；父的同步核验留在监督期限之内，不靠另开写端解除堵塞 |
| 能力核对 | `_safe_open_supported()` 要求 `O_NOFOLLOW`、`O_DIRECTORY`、`O_NONBLOCK` 存在且 `os.open` 支持 `dir_fd`；此外绑定根本身就是一次**真实**能力核对——内核必须接受安全标志，`EINVAL/ENOSYS/EOPNOTSUPP` 直接 `S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED` fail closed。**不**以预检 `exists/lstat` 当作无竞态的保证 |
| 负例 | ① 初次 FIFO → `ORIGINAL_NOT_A_REGULAR_FILE`，**无写端**、不阻塞；② 封存后 raw 变 FIFO → `S3_ORIGINAL_REPLACED:<category>`，**无写端**、不阻塞；③ 平台缺 `O_NOFOLLOW` → `S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED`；④ 平台缺 `O_NONBLOCK` → `S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED`；⑤ 重复拒绝 12 轮后**描述符数不变**（4→4） |
| 线程与清理 | 负例用**同进程**线程跑 owner 调用并设 2 秒上界；线程为 daemon，若断言失败则由 `finally` 打开 FIFO 写端**受控释放**并 `join`，任何失败都不留下挂起线程。测试自身不引入 `subprocess` |
| 平台边界 | 只证明 POSIX（Linux ext4，`O_NOFOLLOW`/`O_DIRECTORY`/`O_NONBLOCK`/`dir_fd`）。**不**声称 Windows、junction、reparse point、native 调用已证明；WSL 字符串不作为 Windows 证据 |
| 证据 | `owner-observations.json` 的 `O2_fifo_at_the_seal`、`O2_fifo_after_the_seal`（`blocked_on_the_fifo=false`、`elapsed_seconds=0.0`、`write_end_opened_by_the_oracle=false`、`thread_settled=true`）、`descriptors`（`before=4`、`after=4`、`leaked=0`）、`fail_closed`；`tools/test_v0_s3_integration.py` 的 `test_the_seal_refuses_a_fifo_without_a_writer_and_without_blocking`、`test_the_manifest_refuses_a_fifo_that_replaced_a_sealed_raw`、`test_a_refused_original_leaks_no_descriptor`、`test_a_platform_without_the_safe_primitives_fails_closed` |

## 3. 既有 O 义务未回退

`test_parent_seals_the_plan_and_the_originals`、`test_parent_refuses_an_ancestor_link_out_of_the_bound_root`、`test_parent_refuses_a_link_on_the_artifact_itself`、`test_the_manifest_refuses_an_original_that_changed_after_the_seal`、`test_the_manifest_refuses_an_original_that_was_replaced`、`test_the_manifest_refuses_an_original_that_vanished`、`test_the_manifest_refuses_a_replaced_root`、`test_the_manifest_refuses_an_ancestor_link_after_the_seal`、`test_parent_refuses_a_foreign_or_changed_original`、`test_parent_refuses_a_replaced_selected_root`、`test_parent_refuses_an_incomplete_plan` 在本轮定向运行中全部通过。

原因码保持兼容：祖先/最终链接 → `S3_ORIGINAL_REDIRECT_FORBIDDEN:<category>`；丢失 → `S3_ORIGINAL_UNREADABLE:<category>`；换对象（含 inode 复用，靠 `ctime_ns/mtime_ns` 区分）→ `S3_ORIGINAL_REPLACED:<category>`；内容/长度变化 → `S3_ORIGINAL_CHANGED:<category>`；根被替换 → `S3_SELECTED_ROOT_REPLACED`；缺安全原语 → `S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED`；seal 阶段非常规文件 → `ORIGINAL_NOT_A_REGULAR_FILE`；超过 8 MiB 上限 → `ORIGINAL_EXCEEDS_BOUND`（上限 exact / one over 由 `test_the_size_bound_of_an_original_is_exact_and_one_over` 覆盖）。

`manifest` 文档新增两个自述字段：`original_open_primitive = "no_follow_dirfd_nonblock"`、`original_read_boundary = "verified_open_to_digest_end_then_path_rewalk"`；旧的 `no_follow_dirfd` 值不再成立，故如实更新。

---

## 4. 定向执行：pre-import guard、外层与 runner 日志分离、原始收据

- **候选 import 前的独立 guard**：`implementation-originals-correction-04/hardguard.py` 在 pytest、插件与候选模块**之前**安装审计钩子，拒绝 `subprocess.*`、`socket.*`、`os.fork/forkpty/exec*/spawn*/posix_spawn`、`os.system`、`pty.spawn`、`sqlite3.connect`，并拒绝打开受保护状态（`shared-counter.json`、`*ledger.sqlite/.sqlite3/.db`、`original.sqlite`）。两次运行的 `guard.json` 均为 `denials: []`、`installed_before_candidate_import: true`。
- **零 fixture / 零网络 / 零模型 GPU / 零下载 / 零用户原件**：本批只允许同进程 pipe/thread、`mkfifo`、受控 `os.read` 包装与本目录内的合成根；外层只启动 guard 解释器本身来跑这些零 fixture 检查，**未**启动 fixture 进程、绑定 runner 或任何服务。
- **原始收据与真实日志**：`run.receipt.json`（每个 step 的完整 argv、cwd、真实退出码、耗时、stdout/stderr 路径、guard 收据）、`owner-probe.outer.stdout.log` / `.stderr.log`、`directed-originals.outer.stdout.log` / `.stderr.log`、`owner-probe.guard.json`、`directed-originals.guard.json`、`owner-observations.json`。外层日志名与 runner 自身日志名分离，本轮日志名是新的，未伪造任何日志。运行器在写新日志前**先归档**同名旧日志（`*.archived-<mtime>.*`，收据里逐条列出），因此任何一次失败尝试的原始 stdout/stderr 都不会被下一次运行覆盖。
- **定向结果**：`owner-probe` 退出码 0（0.508 s）；`directed-originals` 退出码 0（0.687 s），`31 passed in 0.50s`（11 个既有原件义务节点 + 20 个新定向节点，按精确 node id 调用）。两次运行均 0 SKIP、0 deselected（只调用被选节点，不冒称 deselected）。收据 `run.receipt.json` 里的 `candidate_sources` 与 `report_files` 与当前工作树的实际 SHA256 逐条一致。
- **本轮更早的两次失败尝试（如实记录）**：`failed-attempts.json` 记录了本轮 owner 探针的两次真实失败：① 探针文件的一处 import 语法笔误（`SyntaxError`，entry 退出码 1）；② 探针的 `root_replaced` 触发第二次运行时因兄弟目录已存在而未真正发生（探针自己的 Oracle 拒绝该次运行，entry 退出码 1）。两次都是**本轮探针/运行器自身的错误，不是候选源的产品缺陷**；它们当时的原始 stderr 文件被同 step 的下一次运行覆盖了（当时运行器还没有归档机制），此处只保留命令、真实退出码与捕获到的错误行，未重建、未伪造日志；运行器随后改为「先归档再写」。
- **开发期旁证（非交付收据）**：整个 `tools/test_v0_s3_integration.py` 模块在开发期跑过一次，`74 passed`；该次运行**不属于**本轮交付证据，也**不**重开任何已关闭项，交付证据仍只有上面两次受 guard 的定向运行。
- **反假绿对照**：把基准的旧 coordinator 临时换回工作树后，**同一批 31 个节点**有 **17 个失败**（O1 的 seal 侧 5 条 + manifest 侧 4 条 + 祖先/根/链接 3 条 + FIFO 2 条 + 描述符泄漏 1 条 + 缺原语 fail closed 1 条 + 部分发布 1 条），证明这些用例真的覆盖 O1/O2，而不是恒真断言；对照使用 2 秒上界的受控线程，不留下挂起线程，对照后立即恢复候选源。原始输出保留在 `control-old-candidate.stdout.log`（`17 failed, 14 passed in 6.75s`，pytest 退出码 1），被对照的旧源保留在 `control-old-candidate.coordinator.py`（SHA256 `a026a857…`）。注意：manifest 侧的 `growth` 在旧源上**不**失败，因为旧源靠摘要差异就能发现增长——这正是旧源只覆盖内容变化、不覆盖同字节改写的证据。
- **共享 counter**：仅由外层只读。运行前后 SHA256 均为 `8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18`，`active=false`、`starts_total=15`、`reserved_wall_seconds=180`、`spent_wall_seconds=8.446` 不变；未退款、未清零、未新建 counter、未跑 binding runner。

## 5. 受控故障的边界与清理

- 受控故障只发生在**本进程合成的根**（`implementation-originals-correction-04/synthetic-roots/`，每个用例一个独立合成根）；没有触碰任何用户原件、产品根或真实 ledger。
- 每个触发都有明确 Oracle：owner 必须拒绝、拒绝原因必须落在 `S3_ORIGINAL_*` / `ORIGINAL_*` / `S3_SELECTED_ROOT_REPLACED` 家族、触发必须真的发生（`trigger_fired`）、改动必须可观察（`change_observable_in_the_object`）；不满足即断言失败，不允许「exit 0 即通过」。
- 清理：FIFO 在探针结束时被 `unlink`，不留在证据目录；线程全部 `join`；描述符数前后一致（4→4）；受控故障的合成文件与 raw 作为证据保留在本目录。
- 探针中的 `write_end_opened_by_the_oracle` 明确记录为 `false`：Oracle 本身从不靠另开写端解除堵塞，写端只在**断言失败后的受控恢复**里使用。

## 6. 启动环境与停止规则

- 自然 env 已核实：`CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0`（本进程 env 实测，非本轮临时设置）。
- 首次 429 即 `WAIT_BUDGET` 停止：不重试、不换模型/供应商/账号，交给 Harness 或 Codex 接手。首次审批拒绝或超时即停止并 ask root，不包装、不绕过、不改审批配置。临时 env（`.claude/settings.local.json`，`created_sha256=7e6320a5…`）由 root 按 hash 恢复，本轮未删除、未改动。
- 本轮无 429、无审批拒绝、无审批超时。

## 7. 未证明 / 不冒称的部分（全部 NOT_PROVEN）

- 真实 13 场景成绩：**NOT_PROVEN**（本轮零 fixture、零 fixture 进程；不重跑、不冒称）。
- 固定 24 完整执行：**NOT_RUN / NOT_PROVEN**。
- 产品 12 项与真实产品运行：**NOT_PROVEN**。
- Windows / junction / reparse point / native 调用：**NOT_PROVEN**（本轮只证明 POSIX/Linux 语义）。
- GPU / A06 真实隔离 / 实际独立 QualityPhase 质量集合 / 原 ledger：**NOT_PROVEN**，本轮未触碰。
- root migration、真实服务后代/父崩溃恢复：**NOT_PROVEN**。
- 本轮不宣布 Stage PASS、不宣布产品 Gate0、不推进任何开发分母；Gate0 仍关闭，等待 root 与隔离独审裁决。

## 8. 交付物清单

| 类别 | 路径 |
|---|---|
| 源 1 | `tools/v0_s3_coordinator.py`（唯一改动：安全读取程序、非阻塞安全打开、路径重走核对） |
| 源 2 | `tools/test_v0_s3_integration.py`（新增 20 个定向节点 + 辅助函数；既有节点未改） |
| NEW 目录 | `reports/v0-s3/product-gate0/implementation-originals-correction-04/`：`report.md`、`hardguard.py`、`pytest_entry.py`、`owner_probe.py`、`run_guarded_checks.py`、`run.receipt.json`、`owner-observations.json`、`failed-attempts.json`、4 个 guard 收据、4 个原始 stdout/stderr 日志与其归档副本、`control-old-candidate.stdout.log` 与 `control-old-candidate.coordinator.py`（反假绿对照原始输出与被对照旧源）、`synthetic-roots/`（合成证据） |
| 未改 | supervisor 及其测试、executor、runner、fixture、qualityworker、其余 owner、公共合同、阈值、固定 24、控制 MANIFEST、V2、旧报告、旧失败收据；旧未跟踪工件与旧 `report.md` 修改一律保留 |
| Git | 未 `clean`、未 `reset`、未 `git add -A`；只暂存本轮的两个源与本 NEW 目录 |
