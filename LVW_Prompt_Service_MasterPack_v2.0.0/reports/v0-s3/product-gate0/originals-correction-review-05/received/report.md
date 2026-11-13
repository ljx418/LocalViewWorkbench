# S3-P4 原件纠偏 05：O1 重走窗口的内容状态比较补齐，D1 报告勘误

- **候选基准**：`b27b0d17b71371e37002aabc5f69a030872b9177`（root-decision `originals-correction-05/root-decision.json`，`status = CHANGES_REQUIRED`，Fatal 0 / Major 1 / Minor 1）。
- **本批只处理 root 接受的两项**：O1（`accepted`：`O1 path-rewalk fstat content metadata omitted`）与 D1（`accepted`：`D1 report429 fallback wording`）。
- **不重开**：O2 FIFO（`closed`，本轮 Linux 合成离线边界内保持关闭）、H / C / S / A、旧 stream M1/M2（`closed`）。本批**未**触碰它们的实现；它们的既有定向节点只作为「不回退」的重跑范围被调用（见 §3.3）。
- **交付状态**：`READY_FOR_REVIEW`。本批**不**宣布 Stage PASS，**不**宣布产品 Gate0，**不**推进任何开发分母；Gate0 仍关闭，等待 root 与隔离独审裁决。

---

## 1. O1（Major，残留）：重走窗口内的内容状态必须与已验证摘要同一状态

### 1.1 根因（与独审记录一致）

`tools/v0_s3_coordinator.py` 的 `ParentOriginalEvidence._read_original_safely` 是 seal 与 manifest 共用的唯一安全读取程序，它做四件事：

1. `_open_inside_root(relative, category)`：**第一次**沿 no-follow dirfd 路径链打开原件，返回句柄与祖先身份链 `chain`；
2. `before = os.fstat(descriptor)`：读前真实 `fstat`；
3. `_digest_handle(descriptor, ...)`：从**同一句柄**取摘要与长度；`after = os.fstat(descriptor)`：读后真实 `fstat`；
4. `_refuse_a_changed_window(before, after, length, ...)`：比 type / dev / ino / size / ctime / mtime / 实际长度；随后 `_refuse_a_changed_path(relative, chain, before, category)`：**第二次**沿 no-follow dirfd 路径链重走，取真实 `fstat`。

残留缺陷在第 4 步的第二段：`_refuse_a_changed_path` 拿到第二次真实打开的句柄后，`os.fstat(descriptor)` 的结果**只**与第一次的 `before` 比较了 **type / dev / ino**（外加路径链 `chain`），**漏掉**这次 `fstat` 自带的 **size / ctime / mtime**，也没有把**实际读取长度**与这次 `fstat` 的 size 对齐。

因此：独审在第二次 `os.open` 成功、**FD 返回给候选之前**对**同一对象**做 `modified / same / grow / truncate` 时，候选随后的真实 `fstat` **已经能看到**变化，却因为只比身份而全部放行——`same` 字节不改变摘要（其余六个发布旧摘要），seal 与 manifest 两条路线共 **8 个场景**全部错误接受。

> 参照量（与独审记录一致）：`ORIGINAL` 的 SHA256 = `962f85a27854336f3286ad54b49321f62525043b5f3508b2ecc887fdd6e7550e`；`MODIFIED` 的 SHA256 = `688e0feb4f52dfcc5abd3d0cda746e71ca32c700a66a609160103a0bb8f1b746`。

### 1.2 修复（唯一实现改动）

**唯一改动**：`tools/v0_s3_coordinator.py` 的 `_refuse_a_changed_path`。该方法**已经**在第二次重走中取得了真实 `fstat`（`info`），修复只是把这次**已取得**的内容元数据与**本次已验证摘要的同一稳定状态**（`before`，即 `observed` 摘要所用的那一组状态；`_refuse_a_changed_window` 已保证 `before` 与 `after` 的 size/ctime/mtime 一致且 `length == before.st_size`）做完整比较：

| 比较项 | 修复前 | 修复后 |
|---|---|---|
| type（regular） | ✅ | ✅（不变） |
| 身份 dev / ino | ✅ | ✅（不变） |
| 路径链 `chain` | ✅ | ✅（不变） |
| **size** | ❌ 漏 | ✅ `info.st_size == before.st_size` → 否则 `S3_ORIGINAL_CHANGED:<category>` |
| **ctime** | ❌ 漏 | ✅ `info.st_ctime_ns == before.st_ctime_ns` → 否则 `S3_ORIGINAL_CHANGED:<category>` |
| **mtime** | ❌ 漏 | ✅ `info.st_mtime_ns == before.st_mtime_ns` → 否则 `S3_ORIGINAL_CHANGED:<category>` |
| **实际长度** | ❌ 漏 | ✅ `length == info.st_size` → 否则 `S3_ORIGINAL_CHANGED:<category>` |

配套的最小自述更新（非行为改动）：

- 模块 docstring 的边界条目：补上「重走以**一次最后的真实观察**（type / 身份 / size / ctime / mtime / 消费长度）结束，该观察即检查的边界」，并明确「不承诺该观察之后文件不变、不是多文件原子快照」。
- `_read_original_safely` docstring：补上「重走比较的是它**真正打开**的那个对象的**内容状态**……并且是用**该窗口内的观察**拒绝，**不是**再额外开一次」。
- `manifest` 的自述字段：`original_read_boundary` 由 `verified_open_to_digest_end_then_path_rewalk` 如实更新为 `verified_open_to_digest_end_then_path_rewalk_with_final_content_state_observation`；`original_open_primitive = no_follow_dirfd_nonblock` 不变。

### 1.3 边界声明（不夸大）

- **边界 = 最后一次实际元数据观察**（即第二次重走句柄上的 `fstat`）。检查覆盖「已验证打开 → 摘要结束 → 路径重走 → 最后一次内容状态观察」这一整段窗口；**不承诺**该观察之后文件不再变化，也**不**承诺多文件的原子快照（每个原件各自检查，整批不被冻结）。
- **没有第 3 次 / 第 4 次打开**：修复**复用**了程序本来就会做的那一次 `fstat`，**没有**新增任何打开或重走。定向证据里每一例的 `opens_of_the_artifact` 恒为 **2**（第一次已验证走 + 一次重走），新节点 `test_an_original_that_does_not_change_during_the_rewalk_is_accepted` 与两个拒绝节点都断言这一点。
- **重复 fstat / check 没有升级成无界重试**：本次新增的全部比较都是**同一份已取得状态**上的常量次比较，没有循环、没有递归重检。
- **未新建监控、服务、守护进程，也未扩大任何权限**：候选源里没有新增任何线程、定时器、后台任务或权限提升；本批的受控故障全部发生在**本进程**内。

### 1.4 保持不变的既有义务（不得回退）

- no-follow dirfd 路径链（`O_NOFOLLOW|O_DIRECTORY` 逐级打开，祖先是链接即拒绝）；
- 根 identity（`_bound_root_fd` 比对 `[dev, ino]`）；
- 非阻塞打开（`O_NONBLOCK`，特殊文件不会被打开本身阻塞）；
- FIFO 拒绝（`O2`，本轮未重开，仅作为不回退项被调用）；
- FD 清理（拒绝路径上每个句柄都被关闭；见 §4 描述符 4→4）；
- **部分 seal 不发布**（`seal_originals` 在中途拒绝时 `self.originals` 保持原值，见 `test_a_failed_seal_publishes_no_originals`）。

### 1.5 反假绿对照（真实复现失败）

同一批**新节点**打在**旧源**上必须真实失败。旧源取自基准提交 `b27b0d1` 的 Git blob `3da0268e5ea02b23866914825d4cf3fc64167239`（文件 SHA256 `814589e88f4d3d32a498bca7fc14de8d7b9efff852f25bdcfe7651bb5017860e`，与独审记录的候选 coordinator SHA 一致），在**独立的 scratch 树** `/tmp/lvw-oc05-control` 中与**本轮新测试文件**（SHA256 `bde478e5…`，与候选逐字节相同）一起运行：

- `control-old-candidate.outer.stdout.log`：**`8 failed, 2 passed in 0.35s`**，pytest 真实退出码 **1**；
- 8 个失败全部是 `Failed: DID NOT RAISE <class 'tools.v0_s3_coordinator.S3IntegrationError'>`——即旧源在重走窗口内**确实接受**了 `modified / same / grow / truncate`（seal 与 manifest 各 4 例）；
- 2 个**正例**（未改变的原件在重走窗口内必须被接受）在旧源上**通过**——证明这些用例不是恒红断言，而是**精确命中**了旧源的缺口。

对照树中的旧源与新测试文件的 SHA 都写进了 `run.receipt.json` 的 `control_binding`，可逐条复核。被对照的旧源原件保留在本目录 `control-old-candidate.coordinator.py`（SHA256 `814589e88f4d3d32a498bca7fc14de8d7b9efff852f25bdcfe7651bb5017860e`）。对照用的 scratch worktree 在对照跑完后已 `git worktree remove --force` 清除，未在工作树里留下任何登记残留；如需复跑，可用同一条命令重建：`git worktree add --detach /tmp/lvw-oc05-control b27b0d17b71371e37002aabc5f69a030872b9177`，再把本轮的 `tools/test_v0_s3_integration.py` 复制进去。

---

## 2. D1（Minor，报告表达）：勘误与承认

### 2.1 对前轮报告 §6 的文字勘误（不改历史报告）

前轮报告 `implementation-originals-correction-04/report.md` §6 第 70 行原文为：

> 「首次 429 即 `WAIT_BUDGET` 停止：不重试、不换模型/供应商/账号，**交给 Harness 或 Codex 接手**。」

**这句话是错的。** 正确的规则是：

- 首次 429 必须**立即停止**，写入 `WAIT_BUDGET` 并**报告 root**；
- **禁止**自动重试、**禁止**自动换 provider / model / account、**禁止**把工作交给 Harness 或 Codex 接手、**禁止**任何其他「换载体接手」的自动接管；
- 必须由**用户**对**这一次中断**给出**明确的恢复或接手批准**之后才可继续；没有该批准就停在 `WAIT_BUDGET`。

按 root 裁决，本勘误**只写在本 NEW 报告**，**不修改**任何历史报告；历史报告保留原样并以本节为它的勘误说明。

**同时如实声明**：本轮**没有** 429、**没有**审批拒绝、**没有**审批超时、**没有**任何自动接手的证据。上述文字错误是**报告表述错误**，**不得**被推定为本轮发生了实际越权；本轮的实际行为与正确规则一致（见 §5）。

### 2.2 早期原始日志丢失的承认

- 前轮（纠偏 04）的 `failed-attempts.json` 记录了两次真实失败尝试（owner 探针的一处 import 语法笔误、探针 Oracle 自身的一次误判），**当时那两次的原始 stderr 已被同 step 的下一次运行覆盖，且至今未恢复**。本轮**不重建、不伪造**这些原始流；只能说「历史原始流不完整」。
- 本轮的规则：**新鲜日志先归档、后写**；**原始退出码不得被覆盖**。运行器 `run_guarded_checks.py::run_step` 在写任何新日志前，先把同名旧日志 `rename` 为 `<label>.archived-<mtime>.<原名>`，并在收据的 `archived_logs_of_an_earlier_attempt` 里逐条列出。
- **本轮自身的一次失败尝试即按该规则留存**：第一次跑 `owner-probe` 时退出码为 **1**（本轮探针的 Oracle 写错：它把「consume 路线上**改动前**就已存在的旧 seal 摘要」误判为「过期摘要被发布」；候选本身当时已正确拒绝，理由 `S3_ORIGINAL_CHANGED:raw`）。该次失败的真实原始 stderr 保存在 `owner-probe.archived-1794560515.owner-probe.outer.stderr.log`，**未被第二次运行覆盖**；探针的 Oracle 修正后重新运行，退出码 0。两次运行的 stdout/stderr/guard 收据都独立落盘。

---

## 3. 定向执行：pre-import guard、原始收据、日志归档

### 3.1 候选 import 前的硬 guard

`implementation-originals-correction-05/hardguard.py` 在 **pytest、任何插件与候选模块之前**安装审计钩子（`sys.addaudithook`），拒绝：`subprocess.*`、`socket.*`（connect/bind/getaddrinfo/`__new__` 等）、`os.fork` / `os.forkpty` / `os.exec*` / `os.spawn*` / `os.posix_spawn`、`os.system`、`pty.spawn`、`sqlite3.connect`，并拒绝打开受保护状态（`shared-counter.json`、`*ledger.sqlite/.sqlite3/.db`、`original.sqlite`）。guard **自己**不启动进程、不开 socket、不读 counter 与原 ledger——counter 只由**外层** runner 只读哈希。

三份 guard 收据（`*.guard.json`）均为 `installed_before_candidate_import: true`、`denials: []`：说明 pytest 启动、插件加载、候选 import 与全部合成动作都发生在 guard 之后，且**没有**任何一次真实动作被触发。

### 3.2 零 fixture / 零网络 / 零模型 GPU / 零下载 / 零用户原件

本批只允许**同进程**的 thread、`pipe`、`mkfifo`、受控的 `os.open` / `os.read` 包装与本 NEW 目录内的合成根。外层只启动 **guard 解释器本身**来跑这些零 fixture 检查；**未**启动 fixture 进程、**未**启动绑定 runner、**未**调用任何服务、**未**触碰任何用户原件或产品根。

### 3.3 定向范围（只少量必要定向）

| 步骤 | 内容 | 节点/场景 | 真实退出码 |
|---|---|---|---|
| `owner-probe` | 独立原探针的适配（§3.4） | 8 重走 + 10 读窗 + 2 FIFO + 1 合法 + 4 fail-closed | **0** |
| `directed-originals` | 既有原件义务（不回退）+ 新增重走义务 | **41 个精确 node id** | **0**（`41 passed in 0.52s`） |
| `control-old-candidate` | **反假绿对照**：同样的新节点打旧源 | 10（新 8 + 正例 2） | **1**（`8 failed, 2 passed in 0.35s`，**预期失败**） |

- **明确的新增缺口只有一处**：重走窗口（8 项 + 2 正例）。因此本批的定向范围 = 上一轮已关闭的 31 个原件义务节点（作为**不回退**重跑）+ 12 个新节点 = 41，**不**是 74 / 186 / 134 / 257 的任何全套，**不**重跑已关闭的 H / C / S / A 与 stream M1/M2 全套。
- 41 个 node id 全量写在 `run.receipt.json` 的 `directed_nodes` 里，逐条可复核；pytest 只调用被选节点，不冒称 deselected，也不冒称全量通过。

### 3.4 独立原探针的适配（`owner_probe.py`）

探针是独审原探针 `originals-correction-05/received-review/probe_final.py` 的适配：同样的受控触发（受控 `os.open` 在内核打开成功、**FD 返回给候选之前**改动同一对象，即改动落在重走窗口内），同样的真实 owner（`ParentOriginalEvidence` 本体），同样的「触发必须真发生 + 改动必须在对象状态中可观察 + 不得靠 exit 0 判绿」的 Oracle。

`owner-observations.json` 逐例落证（真实原件 metadata 与 hash，不是标志位）：

| 触发 | 路线 | 拒绝理由 | `opens_of_the_artifact` | size 前→后 | mtime/ctime 前→后（ns） | 触发后实际 SHA256 | 过期摘要被发布 |
|---|---|---|---|---|---|---|---|
| same_length_rewrite | seal | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→8 | 1794560759664219721→1794560759664641183 | `688e0feb…` | false |
| same_bytes_rewrite | seal | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→8 | 1794560759665651077→1794560759666071623 | `962f85a2…` | false |
| growth | seal | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→13 | 1794560759667976291→1794560759668203302 | `659a2afd…` | false |
| truncation | seal | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→3 | 1794560759669224258→1794560759669414909 | `70acd28f…` | false |
| same_length_rewrite | consume | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→8 | 1794560759664999682→1794560759665340055 | `688e0feb…` | false |
| same_bytes_rewrite | consume | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→8 | 1794560759666963625→1794560759667473562 | `962f85a2…` | false |
| growth | consume | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→13 | 1794560759668613251→1794560759668914490 | `659a2afd…` | false |
| truncation | consume | `S3_ORIGINAL_CHANGED:raw` | 2 | 8→3 | 1794560759669698276→1794560759669978497 | `70acd28f…` | false |

`same_bytes_rewrite` 一行是本缺陷的关键证据：**字节没变、size 没变**（8→8），只有 **ctime/mtime 变了**——旧源正是在这里漏检；修复后仍被拒绝。

### 3.5 原始收据、原始日志与 counter

- `run.receipt.json`：每个 step 的**完整 argv、cwd、真实退出码、耗时、stdout/stderr 路径、guard 收据路径、被归档的旧日志清单**；另有 `candidate_sources`（两个候选源的 SHA256）、`report_files`、全部 41 个 node id、`control_binding`、`counter_before/after`。
- 原始 stdout/stderr 逐 step 独立落盘：`owner-probe.outer.stdout.log` / `.stderr.log`、`directed-originals.outer.stdout.log` / `.stderr.log`、`control-old-candidate.outer.stdout.log` / `.stderr.log`，以及各自三份 `*.archived-<mtime>.*` 归档（§2.2 的失败尝试即在其中）。**没有任何一次失败命令被包装成成功**：runner 的退出码取自 `subprocess.run` 的真实返回码，失败就是失败。
- **共享 counter 仅外层只读**：运行前后 SHA256 均为 `8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18`，`active=false`、`starts_total=15`、`reserved_wall_seconds=180`、`spent_wall_seconds=8.446` **不变**；**未**退款、**未**清零、**未**新建 counter、**未**跑 binding runner。

---

## 4. 受控故障的边界与清理

- 受控故障只发生在**本进程合成的根**（`implementation-originals-correction-05/synthetic-roots/`，21 个独立合成根）；**没有**触碰任何用户原件、产品根或真实 ledger。
- 每个触发都有明确 Oracle：owner 必须拒绝、拒绝理由必须落在 `S3_ORIGINAL_*` 家族、触发必须真发生（`trigger_fired`）、改动必须在**同一对象**的状态中可观察（`change_observable_in_the_object`）、被打开次数必须恰为 2、过期摘要不得被发布。不满足即断言失败——**不允许**「exit 0 即通过」。
- **清理**：全部线程 `join`（`all_threads_joined: true`）；FIFO 在探针结束时 `unlink`，证据目录内**残留 FIFO 数为 0**（`find … -type p` 实测 0）；描述符数前后一致（**4 → 4**，`leaked: 0`）；FIFO 场景的 Oracle **从不**另开写端解除堵塞（`write_end_opened_by_the_oracle: false`），写端只在断言失败后的受控恢复里使用。
- **部分 seal 不发布**：seal 路线 4 个重写例与 consume 路线 4 个重写例中，`published_sha256` 在 seal 路线为 `None`（`self.originals` 仍为空），在 consume 路线为**改动前**的旧 seal 值且**未被当作 verified 发布**——manifest 以 `S3_ORIGINAL_CHANGED:raw` 拒绝，`reverification.verified` 从未为真。

---

## 5. 启动环境与停止规则

- **自然 env 已核实**（本进程 env 实测，非本轮临时设置）：`CLAUDE_CODE_MAX_RETRIES=0`、`CLAUDE_CODE_RETRY_WATCHDOG=0` → **自然 retry 0 / watchdog 0**。
- **首次 429 即停止**：`WAIT_BUDGET` + 报告 root；**不重试、不换 provider/model/account、不换载体（Harness / Codex）接手**；必须由用户对**这一次中断**明确恢复或接手批准后才继续（规则文本见 §2.1 的勘误）。
- **首次审批拒绝或超时即停止**并 ask root；不包装、不绕过、不改审批配置。
- **本轮无 429、无审批拒绝、无审批超时、无任何自动接手**；因此这些规则本轮**未被触发**（不是「已按规则处理」，而是「未发生」）。
- **临时 env**（`.claude/settings.local.json`，`created_sha256 = 7e6320a52b689bfe6ff1441909c74d04f1a9620f75684d6d4bbff6508010c1b0`）由 **root** 按 hash 恢复；本轮**未删除、未改动**该文件（实测 SHA 仍为 `7e6320a5…`）。

---

## 6. 未证明 / 不冒称的部分（全部 NOT_PROVEN）

- 真实 13 场景成绩：**NOT_PROVEN**（本轮零 fixture、零 fixture 进程；不重跑、不冒称）。
- 固定 24 完整执行：**NOT_RUN / NOT_PROVEN**。
- 产品 12 项与真实产品运行：**NOT_PROVEN**。
- Windows / junction / reparse point / native 调用：**NOT_PROVEN**（本轮只证明 POSIX/Linux 语义）。
- GPU / A06 真实隔离 / 实际独立 QualityPhase 质量集合 / 原 ledger：**NOT_PROVEN**，本轮未触碰。
- root migration、真实服务后代/父崩溃恢复：**NOT_PROVEN**。
- 合成结果**不**扩大为任何真实质量、原生清理或 Stage PASS；本批**不**推进分母，Gate0 仍关闭。

---

## 7. V0–V3 开发大纲与当前坐标

来源：`plans/execution-control.json` 的 `development_outline`（完成数/声明数，不是主观百分比）。

| Stage | 交付 | 完成/总数 | 实现 | 机器验收 | 独审 | 人签 |
|---|---|---|---|---|---|---|
| V0-S0 | V0 | 1/2 | ARCHIVED | NO_GO_HISTORICAL | COMPLETED_WITH_BLOCKERS | NOT_SIGNED |
| V0-S1 | V0-Min | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| R0 | V1前置 | 1/2 | PARTIAL_REUSED | SINGLE_IMAGE_SUBSET_ONLY | NO_SEPARATE_R0_VERDICT | NO_SEPARATE_R0_SIGNOFF |
| R1a | V1早期切片 | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| V0-S2 | V0.1 | 7/8 | IMPLEMENTED | COMPLETE_FIXED9_PASSED | COMPLETE_FATAL0_MAJOR0_MINOR0 | PENDING |
| **V0-S3** | **V0.2** | **0/6** | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R1 | V1 | 0/4 | EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING | EARLY_SLICE_UM10_ONLY | EARLY_SLICE_FATAL0_MAJOR0 | EARLY_SLICE_APPROVED_FULL_R1_PENDING |
| V1-M1 | V1 | 0/3 | DESIGN_ONLY | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R2 | V1 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R3 | V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R4 | V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5a | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5b | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5c | V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |

- **当前坐标**：`stage_id = R1`、`workpack_id = WP-R1-U3`、`gate = S3_P4_OFFLINE_INTEGRATION_PREPARATION`、`state = READY`；目标版本 **V1**，下一交付目标 **V0.1**。
- **本批完成**：S3-P4 原件纠偏 05 的 O1（重走窗口内容状态比较）与 D1（报告勘误 + 日志丢失承认）；**本批不改变任何分母**。
- **精确停止原因**：本批为实现者交付，状态 **READY_FOR_REVIEW**；Stage PASS 与产品 Gate0 的裁决权在 root 与隔离独审。

---

## 8. 交付物清单

| 类别 | 路径 |
|---|---|
| 源 1 | `tools/v0_s3_coordinator.py`（唯一行为改动：`_refuse_a_changed_path` 增加 size/ctime/mtime/实际长度比较；其余为 docstring 与 `original_read_boundary` 的如实自述更新）SHA256 `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c` |
| 源 2 | `tools/test_v0_s3_integration.py`（新增 8 个重走义务节点 + 2 个正例节点 + 辅助函数 `mutating_reopen` / `install_reopen`；既有节点未改）SHA256 `bde478e54a048a4824b5c54db2b4c06da2d19845f56554a53817dccfeadd7e40` |
| NEW 目录 | `reports/v0-s3/product-gate0/implementation-originals-correction-05/`：`report.md`、`hardguard.py`、`pytest_entry.py`、`owner_probe.py`、`run_guarded_checks.py`、`run.receipt.json`、`owner-observations.json`、`control-old-candidate.coordinator.py`（被对照的旧源原件）、3 份当前 guard 收据、6 份当前原始 stdout/stderr 日志、18 份归档副本（每个 step 的 stdout/stderr/guard 各一份 × 6 次运行，含本轮失败尝试的原始 stderr）、`synthetic-roots/`（21 个合成根证据） |
| 未改 | supervisor 及其测试、executor、runner、fixture、qualityworker、其余 owner、公共合同、阈值、固定 24、控制 MANIFEST、V2、**全部历史报告**（含 `implementation-originals-correction-04/report.md` 的 §6 原文——勘误只写在本报告）；旧未跟踪工件与旧 `implementation-integration-01/report.md` 修改一律保留 |
| Git | 未 `clean`、未 `reset`、未 `git add -A`；只暂存本轮的两个源与本 NEW 目录 |
