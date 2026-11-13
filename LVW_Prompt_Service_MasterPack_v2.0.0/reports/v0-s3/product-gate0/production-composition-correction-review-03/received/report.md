# S3-P4 生产组合纠偏 03：实现报告（唯一实现者，一次集中修复 M04/M06/M08 + meta01/m03 勘误）

**结论：READY_FOR_REVIEW。不是 Stage PASS，不是产品门禁通过，不是人签。**
root ACK（`msg_a618aebaec57`）覆盖的唯一批次已执行：1 次 pytest 调用，
35 collected / 35 invocations / **35 PASS / 0 FAIL / 0 SKIP**，exit 0，wall 12.178 s，
guard 0 denials，FD 无残留，counter 前后未变。详见 §8。

基准候选 `8f375f887f0121ab5a0395f032dd74d8a6f0cf0b`（`8f375f8`，本轮开工时 worktree 的 HEAD，已核对相符）。
冻结裁决来源：`reports/v0-s3/product-gate0/production-composition-correction-03/contract.md`、
`root-decision.json`（Fatal 0 / Major 3 / Minor 2；M05/M07/指定 FD snapshot 修复/P01 本轮已关闭，不重开）、
`received-review/review.md` 与该目录下的实际 JSON 证据。原全量证据已封存 `review-full-evidence.zip`，
原 review 目录仍保留、只读、未改。

## 1. 文件范围（严格按 contract）

允许且**仅**修改：

| 文件 | 变更 |
|---|---|
| `tools/v0_s3_controller_io.py` | M04：外部只读锚点改为**从文件系统根逐级 no-follow 的可信链**并返回每级身份；M06：目录链新增“按 fd 记录每级身份”的机制 |
| `tools/v0_s3_production_controller.py` | M06：PRECHECK 前建立并持有输出链、创建身份与声明路径交叉匹配；M08：独立释放 finally、终态持久化结构化 UNKNOWN、观察失败结构化返回 |
| `tools/v0_s3_quality_worker.py` | M04：外部锚点读取走同一条有界 regular/nonblock 链，并验证祖先与叶身份 |
| `tools/test_v0_s3_production_composition.py` | M04/M06/M08 的定向负例探针 + 正式正例兼容 + **一处已披露的断言变更**（见 §3.0） |
| `tools/test_v0_s3_supervisor.py` | **未改**（digest 与基准一致，见 §6） |

**未改**：`tools/v0_s3_supervisor.py`（固定命令构造）、`tools/v0_s3_quality_phase.py`、
`tools/v0_s3_coordinator.py`、`tools/v0_s3_runtime_binding.py`、`tools/v0_s3_stage_runtime.py`、
`tools/v0_s3_budget_authority.py`、`tools/local_program_authority.py`、`tools/v0_s2_runtime.py`、
公共合同、`plans/execution-control.json`、`.agent-governance/*`、`MANIFEST.sha256`、V2/V3、任何旧证据。

未做 `clean`、未做 `reset`、未批量 `add`；未删除、未覆盖任何旧失败/未知/工件。

## 2. 三个代码 Major 的修复

### M04 — 外部只读依赖锚点的全链可信（`v0_s3_quality_worker.py::_read_through_anchor`）

* **缺陷**：外部 `READ_ONLY_DIRECTORY` 锚用 `os.open(str(path), directory_open_flags())` 打开，
  `O_NOFOLLOW` 只保护**叶目录**；锚的**祖先**未被逐级 no-follow 打开。独审 `M04-external-ancestor.json`：
  把锚的父目录改名保留并换成指向同一目录的 symlink 后，`error=null`、`accepted_outside=true`，
  同 hash 的外部字节被接受——读后只核验叶身份，无法发现这次重定向。
* **修复**（复用既有 owner，未另造通用平台）：
  1. `v0_s3_controller_io.open_read_only_directory_chain(path)` **复用**既有的
     `open_root_directory_chain`：从文件系统根逐组件 `O_NOFOLLOW|O_DIRECTORY` 打开，返回
     **每一级**的 `(path, device, inode)` 身份链；`ROOT_REDIRECTED`（祖先是 link）转成
     `ANCHOR_REDIRECTED`，`SAFE_OPEN_UNSUPPORTED` 原样透传。
  2. worker 的外部锚分支改为：可信链打开 → 锚下各级用 `open_directory_chain_identified`
     逐级 no-follow 打开并**按 fd 记录身份** → 叶用 `read_bounded_at`
     （`O_NOFOLLOW|O_NONBLOCK` + 真实 bound）读取 → 读后 `verify_directory_chain(chain + levels)`
     **验证祖先与叶身份**。
  3. 路径**从不 resolve**：锚的身份是它的字面位置；比较全程字面量、前缀式。任意外部路径
     不会被升级为权限：只有封存 context 声明的锚才被打开。
  4. 所有中间 fd 由明确 owner 在成功、普通异常与 `BaseException` 下关闭
     （`open_root_directory_chain` 逐级关闭父 fd；worker 在 `finally` 关闭锚 fd 与链 fd）。
* **观察边界（如实声明）**：只读检查与磁盘操作**不是原子的**；保证止于上述校验的观察边界，
  本实现**不承诺**路径永不被外部改变。
* **证据**：探针 `test_an_external_dependency_anchor_is_bound_to_its_whole_chain[legal|parent-link]`
  ——合法命名外依赖仍可读；父目录换成 symlink（**同叶、同 inode、同 hash、同字节**）被拒，
  依赖字节从未经该 link 被消费。

### M06 — PRECHECK 前绑定输出链、创建对象与声明路径交叉匹配

* **缺陷**：PRECHECK 只绑定 root，输出目录到 reservation 阶段才打开（PRECHECK 之后的早窗口）；
  `_observe_controller_chain` 用**绝对路径的 lstat** 观察身份，与 `ensure_directory_chain`
  返回的 fd **没有 identity 交叉核验**——先拿到旧 fd、再 lstat 新路径即当成同一对象。
  独审证据：`M06-PRECHECK-temp.json`（新 temp 收到 reservation 与 receipt）、
  `M06-PRECHECK-controller.json`（新 controller 目录收到 reservation/summary/receipt）、
  `M06-create-race.json`（创建返回后、观察路径前替换 → 仍返回 SUMMARY_PERSISTED，
  文件实际写入 held-output 旧目录而**声明路径**指向新的空目录）。
* **修复**：
  1. `_precheck` 在**公开 PRECHECK transition 之前**调用 `_bind_output_identity()`：
     以已绑定的 root fd 相对创建 `temp/s3-production-controller`，并**持有输出 fd**。
  2. **身份来自 fd，不来自路径**：`ensure_directory_chain(root_fd, parts, identities=identities)`
     以 out-param 记录**每一级**的 `(device, inode)`，取值来自该级 fd 的 `fstat`。
     controller 用这些身份合成**声明路径记录**（`path/device/inode`），
     并立即用 `verify_directory_chain` **交叉匹配**声明路径与创建所得的身份：
     不一致即 `CONTROLLER_DIRECTORY_IDENTITY_CHANGED`，descriptor 关闭后再抛。
     （`ensure_directory_chain` 的**返回值仍是 fd 本身**，既有调用方与探针的 `os.fstat(fd)` 语义不变。）
  3. `_observe_controller_chain`（路径 lstat 观察）**已删除**：路径观察不再是身份来源。
  4. reservation / summary / receipt **全生命周期复用同一已绑定目录 fd**，每次写入前
     `_verify_controller_identity()` **重核** root 链 + 输出链的每一级。
  5. 被替换时：**拒绝写入替代对象**（写前校验失败即不写）、**拒绝发布虚假
     `receipt_path`/`summary_path`**（两者只在写成功后才被赋值）、保留已有 partial、
     不在未知根补写失败收据、不删除未知目录；根内 `O_EXCL` 排他写与幂等无重发保留。
  6. **观察边界（如实声明）**：校验与写入是两次独立操作、非原子；保证止于写前那次校验的观察边界。
* **证据**：探针 `test_the_output_chain_is_bound_before_the_public_precheck_transition`
  （PRECHECK transition 时输出 fd 与两级身份链已就位）、`test_a_replaced_output_after_the_precheck_is_refused[root|temp|controller|ancestor]`
  （PRECHECK 后替换 root/temp/controller/根祖先 symlink → 替代对象**零文件**、无虚假路径）、
  `test_the_created_output_directory_is_bound_to_the_descriptor_that_was_opened`
  （创建返回与身份观察之间替换路径 → fd 身份与路径身份不同 → 拒绝，替代目录与 held 目录**都零文件**）。

### M08 — 独立释放 finally 与异常终态

* **缺陷**：终态 `finally` 中 `_persist_receipt` 抛 `KeyboardInterrupt`/`SystemExit` 时，
  `_release_anchors` 在其之后且无独立 finally → **泄漏自有 root/output 两个 FD**（独审
  `M08-cancel-keyboard.json`/`M08-cancel-system.json`：fd 3/4 仍开，fstat 确认目录 inode）；
  `_record_post_release_cleanup` 抛普通异常时 finally 无兜底 → main **exit5、stdout 空、receipt=null**
  （`M08-observer-runtime.json`）；只令终态 `_persist_receipt` 自身 RuntimeError 时
  **exit0/SUMMARY_PERSISTED/receipt_persisted=false**，没有 UNKNOWN/unknown_reason
  （`M08-direct-only.json`）。
* **修复**：
  1. **独立 finally**：终态块改为 `try: … finally: self._release_anchors()`。
     `_finish` / `_persist_receipt` / `_record_post_release_cleanup` 任一抛
     `KeyboardInterrupt`/`SystemExit` 时，**已明确持有的 root/output 锚仍被释放**，
     取消**继续向外传播**，BaseException **不被吞掉**。
  2. **单次持久化失败 = 结构化 UNKNOWN**（`_record_terminal_persistence`）：
     终态收据写不出且本次运行**已取得预约**时 → `state=UNKNOWN_RETAINED`、
     `receipt_persisted=false`、`unknown_reason` 命名该次失败、`cleanup_proven=false`、
     root/预约保留、`refund/resend/archive_allowed=false`。**即使没有 primary 失败也如此**。
  3. **primary / secondary / cleanup 分开**：已有 primary 时，secondary 记入
     `secondary_failure` 与 `secondary_failures`，**不替换** primary；primary 仍是
     `unknown_reason`。持久化**只尝试一次**，无重试循环。
  4. **客观磁盘事实单列**（`_record_disk_actions`，写在收据落盘**之前**，故磁盘收据也带上）：
     `disk_actions.summary_written / summary_path / summary_sha256`，
     并写明 `summary_persisted`（**资格字段**）与 `disk_actions`（**磁盘事实**）含义不同、
     互不替代；已写出的 summary **不假称删除、不假称未发生、不自动重写**，
     磁盘收据**不自证其自身写入**。
  5. **观察失败结构化返回**（`_record_observation_failure`）：
     observer 普通异常 → 返回 `UNKNOWN_RETAINED` + `CONTROLLER_POST_RELEASE_OBSERVATION_FAILED:<Type>`，
     `fd_cleanup_post_release.status=FAILED`、`fd_leaked=null`（**不把未知变成空，也不假称清理成功**），
     `cleanup_proven=false`；**不再**泛化 exit5/空 stdout。
  6. **PRE_RELEASE / POST_RELEASE 分离**：磁盘收据只带 PRE_RELEASE；
     POST_RELEASE 只是返回诊断，`the_persisted_receipt_is_not_rewritten=true`，
     并用 `persisted_receipt_state` 显式命名磁盘收据自带的 state（返回态与磁盘态的差异被命名，不被隐藏）。
  7. `_release_anchors` 仍只关**自有** fd，重复调用是 no-op（属性先置 None 再 close）。
* **证据**：探针 `test_a_failed_terminal_receipt_is_a_structured_unknown`（单普通异常 → UNKNOWN +
  secondary + summary 客观事实）、`test_a_primary_failure_and_a_terminal_persistence_failure_stay_separate`
  （双失败 primary/secondary 分离）、`test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[keyboard-interrupt|system-exit]`
  （KI/SystemExit 传播且**零新增 fd**）、`test_the_release_of_the_anchors_touches_only_its_own_descriptors`
  （重复释放幂等、外来 fd 不受影响）、`test_a_failure_of_the_terminal_observation_is_a_structured_unknown`
  （observer 失败 → UNKNOWN、非 exit5、stdout 非空、磁盘收据未被改写）。

### 3.0 已披露的行为变化：native 路径会留下一个**空**输出目录

M06 要求在 PRECHECK 内建立并持有输出链，而输出目录的创建正是这条链的一部分。
native 路径的拒绝发生在 PRECHECK **之后**（顺序未改：仍是 `_precheck → admission → 拒绝`，
拒绝码 `CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY` 不变、零 spawn 不变），
因此 native 拒绝后 run root 内会留下**空的** `temp/s3-production-controller/`。

据此**唯一**修改了既有断言 `test_the_native_path_is_refused_before_any_spawn`：
由「输出目录不存在」改为「输出目录存在但**为空**，且 run root 下不存在任何
`summary-*.json` / `receipt-*.json` / `reservation-*.json`」——断言被**加强**（多查三类工件文件），
不是被放宽。该 native 拒绝**流程、顺序、拒绝码、零 spawn** 均未改。
M02（可信 native 后端缺失 → 默认硬拒绝）**未重开**。

**如实声明残留**：native 拒绝后 run root 内**确实留下一个空目录**
`temp/s3-production-controller/`。因此本报告**不宣称** native 路径「完全零写入」——
准确的说法是：**零 reservation / 零 summary / 零 receipt / 零 spawn**，
写入面仅为一个空的输出目录（该目录是 M06 要求的、必须被建立并持有的输出链）。
root 已明确接受该测试调整与该残留事实。

## 3. meta01 勘误（报告 Minor）

冻结 owner 的清单**是下面这 7 项**（与 `production-composition-correction-02/received-review/frozen-sources.json`
的 `files` 逐项完全相同，也与本轮独审 `received-review/meta01-oracle.json` 的
`original_frozen_sources` 逐项完全相同；本轮逐项重算 digest，**7/7 与基准逐字节相同**）：

| # | 冻结 owner | sha256 |
|---|---|---|
| 1 | `tools/v0_s3_quality_phase.py` | `90552ea113ccf53a2a1cedff3e3f399642ad932bf0f71bb1f9a57e1adb6e8789` |
| 2 | `tools/v0_s3_coordinator.py` | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c` |
| 3 | `tools/v0_s3_runtime_binding.py` | `5dedecde3e3b7b2236f5666b0790ece8ffc39392888c9ec5d88fa2bb888f520b` |
| 4 | `tools/v0_s3_stage_runtime.py` | `c4815fdc2140961171af938ba5396763260314de2e938a1087ab6b21038b1aad` |
| 5 | `tools/v0_s3_budget_authority.py` | `80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7` |
| 6 | `tools/local_program_authority.py` | `677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787` |
| 7 | `tools/v0_s2_runtime.py` | `a97ea20d02ed80ab4f99f133dd8162331ddba34662bfdcca637fcade40b4dbd2` |

**本次 changed sources 是另外 4 项**（见 §6），与上面 7 项**不互换**：
`tools/v0_s3_controller_io.py`、`tools/v0_s3_production_controller.py`、
`tools/v0_s3_quality_worker.py`、`tools/test_v0_s3_production_composition.py`。
另有 2 项**本轮未改**（digest 与基准一致）：`tools/v0_s3_supervisor.py`、
`tools/test_v0_s3_supervisor.py`。

纠偏 02 报告 §4 列的「7 项」清单（controller_io / production_controller / quality_worker /
quality_phase / supervisor / coordinator / test_production）**归属错误**：其中多数是 changed
sources 而非 frozen owner。**旧报告 `implementation-production-composition-correction-02/report.md`
保留不改**，本报告只做勘误并交叉引用，不据旧报告推断任何历史。

## 4. m03 勘误（报告 Minor）

纠偏 02 报告内部口径不一，本报告按**事实**统一：

* **root ACK 次数 = 3 次真实执行 = 3 次**。事实：root 冻结包内确有
  `production-composition-correction-02/validation-plan-01/ack.json`（`ACK_ONE_NARROWED_GUARDED_BATCH`）、
  `validation-plan-02/ack.json`（`ACK_ONE_ENVIRONMENT_CORRECTED_GUARDED_BATCH`）、
  `validation-plan-03/ack.json`（`ACK_ONE_ATTEMPT03_AFTER_EXACT_PENDING_EDIT`）三个 ACK；
  纠偏 02 报告 §7 标题「两次 root ACK / 两次真实执行」**与事实不符**，
  其 §8.3 与 §10 记录的「三次」才是事实。本报告统一为 **3 次 ACK / 3 次真实执行**。
* **三次作者执行的结果（互不覆盖，全部保留）**：
  * attempt01（ACK-01）：exit 1，**0 collection / 0 test call / 候选未 import**，
    `ModuleNotFoundError: No module named 'pytest'`（`-I` 隐含 `-s`，pytest 8.4.2 只在用户 site）。
  * attempt02（ACK-02）：**19 collected / 19 invocations / 18 PASS / 1 FAIL**，exit 1。
    唯一失败是当时尚未修正的 FD 记账口径断言（链条此前断言均通过）。
  * attempt03（ACK-03）：**21 collected / 21 invocations / 21 PASS**，exit 0。
* **不遗留待 ACK 字样**：纠偏 02 报告 §10「剩余工作」仍写「root ACK 后执行 §7 的唯一批次」，
  而 §8.3/终态已记录 attempt03 完成——本报告不再出现任何「待 ACK」表述。
* **FD8 身份 = UNKNOWN，不作具体归因**。事实仅有两项：(a) 当时 attempt02 的 FD 记账断言
  实得 `[8]`，被报编号为 8；(b) `/proc/self/fd` 的**枚举会复制并关闭自身的一个 fd**，
  因此枚举可以产生“已关闭 fd 的幻影”。**没有**该时刻 fd 8 身份的真实记录，
  故**不断言** fd 8 的具体原因，也**不**据旧报告反向认定一次真实资源泄漏；
  该中间时刻的归属保持 **UNKNOWN**。批次终态无残留的事实（`fd_before == fd_after`、
  仅 MainThread）与此不冲突，两者不是同一断言。
* **argv 的绝对/相对路径等价如实记录**：ACK-01/02/03 中记录的 argv 为**绝对路径**；
  attempt02 与 attempt03 的 `commands.json` 记录为**相对路径**，**cwd 相同**
  （包根），**解析到完全相同的目标**（同一 guard、同一 runner、同一 nodeids 集合与顺序、
  同一 pins），但**argv 字符串并非逐字一致**。本报告不制造「字符串逐字一致」的说法，
  也不据此事推断解释器替换或额外执行。

## 5. 已关闭项：未重开

M01（值比较=类型+值）、M02（可信 native 后端缺失→默认硬拒绝）、M03（context hash 链与 provenance）、
M05（解析文档与封存 bytes 同一）、M07（正式义务无证不 PASS）、M09（发送前阻断重入）、
m01（协作取消与诚实线程保留）、m02（text/binary 错误流保准确码）、指定 FD snapshot 修复、
P01（本轮流程与历史事实勘误）——本轮**不重新实现**，仅保留必要的兼容点（见 §7 的 nodeids）。

## 6. 候选身份与 hash

```
15305e4e3731a0e1533518725cf2bf27186b2b042e86167aee8130586ff8e7b1  tools/v0_s3_controller_io.py
4236725aca2402a0d04cecb08ed458d6ac8084fb3b0c788599b52514e8e0f4e7  tools/v0_s3_production_controller.py
e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592  tools/v0_s3_quality_worker.py
a1f9fd4f890aebc08d72208e72c39f79af5579a42c108d14bfa0dd33d80b848f  tools/test_v0_s3_production_composition.py
7d210429e70761cea633e8f2e64d8a1f01709930068a21de5cbc3c5a519ce6d8  tools/v0_s3_supervisor.py            （本轮未改）
9783239ad1b48b243b6922c88ea8ce0f629544bd03beb16490bfb2e8493cf3e9  tools/test_v0_s3_supervisor.py       （本轮未改）
```

机器可读版本：`candidate.json`（含 7 项 frozen owner 与 4 项 changed sources，两个清单不互换）。
本报告包内的工具与其 digest：

```
9555d48e58f4d86fe2e607cd403686016a946b71ebafd24e88a561bab6681c48  reports/.../implementation-production-composition-correction-03/guard.py
b701f1b9bf70fe30991266283b8a7a4793951e4d65eece66247632b40c83bbae  reports/.../implementation-production-composition-correction-03/run_directed_scope.py
3b575311b0de885b4f027dc4f135773ae34b9c95629dfddff4645c53187c0da7  reports/.../implementation-production-composition-correction-03/outer_counter_read.py
08aef3215e5cf45b5d95cb624be230120b03e8e598d0c9cbe71886837dcf3f60  reports/.../implementation-production-composition-correction-03/candidate.json
```

`guard.py` 与 root 两次 ACK 的 `1fb09dd9a874f0f6108dd482efaf3e12121bc4810efe31430dfc29736ffc1e4c`
（纠偏 02）**只差边界名**，被拒家族与受保护状态完全相同。

## 7. 一次有限执行计划（**已由 root ACK：`ACK_ONCE_ROOT_AMENDED_DIAGNOSTIC_RUNNER`，msg_a618aebaec57**）

静态准备已完成：4 个源文件全部 `ast.parse` 通过；对 4 个源文件做了 AST 级未定义名检查
（仅报出 `__file__`/lambda 形参等检查器自身的假阳性，**无真实未定义名**）；
用 AST 静态提取并核对了 §7.3 的 **35 个 nodeid 全部存在于两个测试文件中**（35/35，无重复）。
**在 ACK 之前没有导入候选、没有 import pytest、没有 collection、没有 compat 执行。**
root 的 ACK 与其唯一修订（批次 FD 诊断）记录于 §8.1；**实际执行的 argv 即 §8.1 所列**
（与本节提交的计划仅第 4 索引的 runner 不同）。

### 7.1 批次构成（1 次受 guard 的 pytest 调用；外层只读 counter 前后各一次）

| 序 | 动作 | 形态 |
|---|---|---|
| 0 | 外层只读 counter（前） | 只读打开 `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`，记录 inactive/28/240/12.362 与 sha256；**不写、不退款、不清零** |
| 1 | **受 guard 的唯一定向批次** | 见 §7.2 的精确 argv |
| 2 | 外层只读 counter（后） | 同 0，只读复核未变 |

### 7.2 精确 argv 与 cwd

```
/usr/bin/python3 -I -B \
  /home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-03/guard.py \
  /home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-03/run_directed_scope.py \
  /home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-03/directed-scope.guard.json
```

cwd = `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`（包根）。
以上为**绝对路径**记录（相对路径等价会如实标注，不声称字符串逐字一致）。

### 7.3 选中 nodeids（35 个唯一节点；DIRECTED 14 + REGRESSION 15 + COMPATIBILITY 6）

```
# DIRECTED —— 本轮三个开放项的真实负例（14）
tools/test_v0_s3_production_composition.py::test_an_external_dependency_anchor_is_bound_to_its_whole_chain[legal]
tools/test_v0_s3_production_composition.py::test_an_external_dependency_anchor_is_bound_to_its_whole_chain[parent-link]
tools/test_v0_s3_production_composition.py::test_the_output_chain_is_bound_before_the_public_precheck_transition
tools/test_v0_s3_production_composition.py::test_a_replaced_output_after_the_precheck_is_refused[root]
tools/test_v0_s3_production_composition.py::test_a_replaced_output_after_the_precheck_is_refused[temp]
tools/test_v0_s3_production_composition.py::test_a_replaced_output_after_the_precheck_is_refused[controller]
tools/test_v0_s3_production_composition.py::test_a_replaced_output_after_the_precheck_is_refused[ancestor]
tools/test_v0_s3_production_composition.py::test_the_created_output_directory_is_bound_to_the_descriptor_that_was_opened
tools/test_v0_s3_production_composition.py::test_a_failed_terminal_receipt_is_a_structured_unknown
tools/test_v0_s3_production_composition.py::test_a_primary_failure_and_a_terminal_persistence_failure_stay_separate
tools/test_v0_s3_production_composition.py::test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[keyboard-interrupt]
tools/test_v0_s3_production_composition.py::test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[system-exit]
tools/test_v0_s3_production_composition.py::test_the_release_of_the_anchors_touches_only_its_own_descriptors
tools/test_v0_s3_production_composition.py::test_a_failure_of_the_terminal_observation_is_a_structured_unknown

# REGRESSION —— 本次改动可能打破的既有节点（15）
tools/test_v0_s3_production_composition.py::test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[projection]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[source_identity]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[parent_budget]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[binding]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[dependency_manifest]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root-temp]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[controller-directory]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root-parent-link]
tools/test_v0_s3_production_composition.py::test_an_ordinary_storage_failure_keeps_a_structured_unknown
tools/test_v0_s3_production_composition.py::test_the_native_path_is_refused_before_any_spawn
tools/test_v0_s3_production_composition.py::test_the_reads_are_bounded_regular_and_never_follow_a_link
tools/test_v0_s3_production_composition.py::test_the_fd_snapshot_ignores_closed_enumeration_entries
tools/test_v0_s3_production_composition.py::test_the_fd_snapshot_detects_a_real_open_descriptor_until_closed

# COMPATIBILITY —— 冻结 owner 的 6 个既有兼容节点（6，与纠偏 02 同集，非新增 compat）
tools/test_v0_s3_supervisor.py::test_the_worker_really_invokes_the_quality_phase
tools/test_v0_s3_supervisor.py::test_the_history_wait_is_announced_before_the_row_finishes
tools/test_v0_s3_supervisor.py::test_a_context_with_a_wrong_seal_is_refused
tools/test_v0_s3_supervisor.py::test_a_context_with_an_unknown_key_is_refused
tools/test_v0_s3_supervisor.py::test_the_production_command_is_the_fixed_worker
tools/test_v0_s3_supervisor.py::test_the_production_command_carries_the_pre_sealed_context_hash
```

**不重跑**：60/71/123/84/13/41/186/257/449/94 等旧分母、原独审 37 例、纠偏 02 的 21 节点批次、
原 ledger、任何 native 执行、任何模型/GPU/服务/下载/用户媒体。

### 7.4 前置 audit guard / 依赖 / 预算 / 日志 / 清理

* **audit guard**：`guard.py`（与纠偏 02 同一份边界，仅换边界名）在**任何候选/pytest import 之前**
  装 `sys.addaudithook`，硬拒 `subprocess.*`、`socket.*`、`os.system`、`os.fork`、`os.forkpty`、
  `pty.spawn`、`os.posix_spawn`、`os.exec*`、`os.spawn*`、`sqlite3.connect`，以及对受保护状态
  （共享 counter、`.lvw-runtime/program02.sqlite`、`original.*.sqlite|.sqlite3|.db`）的 `open`；
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`；收据写在 `finally`，失败也留证。
* **source pins**：runner 在 **import pytest 之前**逐项核验 §6 的 6 个 digest，任一漂移即
  `ROOT_FROZEN_SOURCE_DRIFT` 拒绝。
* **依赖**：沿用 root 已封存并两次 ACK 的已装目录方案——`/home/administrator/.local/lib/python3.12/site-packages`
  **仅在 guard 武装且 source pins 通过之后**才 `sys.path.append`；执行前逐项核验 **223 个已装文件
  的 sha256**（本轮已离线核对：**223/223 无漂移**）；**不执行** `site.main`、**不加载** `.pth`、
  **不放开**插件；`-I` 保留。该依赖范围是**命名文件 scope**，不声称全传递依赖封存。
* **次数/时间**：pytest 调用**至多 1 次**，自然 retry 0、watchdog 0，**wall 上限 300 s**。
* **日志/退出码/证据**：`directed-scope.stdout.log`、`.stderr.log`、`directed-scope.guard.json`、
  `directed-scope.json`、`selection.json`、`fd-thread-cleanup.json`；真实 argv/exit 记入 `commands.json`。
* **FD/线程清理**：runner 批次前后各取一次 `/proc/self/fd` 快照与 `threading.enumerate()`；
  **只允许**本进程 threads/pipe/合成文件。
* **counter**：只在外层只读，前后各一次；固定 hash
  `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive/28/240/12.362；
  **不写、不退款、不清零、不新建、不复活旧 grant**。
* **停止规则**：首次 **429** 立即 `WAIT_BUDGET` 停止，不重试、不切模型/路由、不由他人接手；
  首次**审批拒绝或超时**即停止并 ask root，不包装绕过、不改审批配置。

### 7.5 探针自身的注意点（不复现原独审已说明的错误）

* 有界读断言按**实际读取字节**（`len(block)` 之和）判定，**不**用「请求参数之和」当实际读取量。
* 未创建 seam worker 的场景安全处理，不访问未创建的 worker 对象。
* 坏探针不得误报产品：每条断言都指向产品行为本身。

## 8. 执行结果

### 8.1 root 的 ACK 与唯一修订（`msg_a618aebaec57`）

* root 裁决：`ACK_ONCE_ROOT_AMENDED_DIAGNOSTIC_RUNNER`（`decision`），
  记录于 root 冻结包
  `production-composition-correction-03/validation-plan-01/ack.json`（该文件已随 root 保留）。
* root 已核：6 个 source pin、223 个 dependency pin、3 个 tool pin，以及 35 个节点的**顺序**，
  与本报告提交的计划**全部一致**（`static_pins_and_selection_verified: true`）。
* **唯一修订**：**只改本批的 FD 诊断**——root 使用自己的冻结诊断 runner
  `validation-plan-01/run_root_frozen_scope.py`（sha256 `1072b9119cc3ae4b00ec0e883e7e003fa40fa86c8d9ea0d2ccd6febfe9accba4`）：
  逐条 `fstat` 核验枚举出的名字，`EBADF` 条目过滤，**其他未知或枚举失败返回 None**
  （**不**变成空集），**绝不**忽略高 FD，也**不**对历史 FD8 作身份归因；
  该 runner **显式保持**原 impl 的 `PACK_ROOT` 与 `REPORT` 绝对目录。
* **实际执行的 argv = ACK 的 argv，只有第 4 索引（runner）换为 root 的冻结 runner，其余不变**：

```
/usr/bin/python3 -I -B \
  /home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-03/guard.py \
  /mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/production-composition-correction-03/validation-plan-01/run_root_frozen_scope.py \
  /home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-03/directed-scope.guard.json
```

cwd = `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`。
以上为**绝对路径**记录（相对路径等价会如实标注，不声称字符串逐字一致）。

* **我提交的 runner `run_directed_scope.py`（sha256 `b701f1b9bf70fe30991266283b8a7a4793951e4d65eece66247632b40c83bbae`）
  未被执行**——它与已提交的计划**一并保留**，作为「计划形态与实际执行形态不同」的说明。
  未自行替换 root 的 runner。

### 8.2 本批真实执行（1 次，1 批，无重试）

| 项 | 事实 |
|---|---|
| 起止 | 2026-11-13T12:45:29Z → 2026-11-13T12:45:41Z |
| exit | **0** |
| wall | **12.178 s**（runner 自测；上限 300 s） |
| collected / invocations | **35 / 35**（与 ACK 的 `exact_nodeids` 集合**与顺序**完全一致，未触发 exit4 的 fail-close） |
| 结果 | **35 PASS / 0 FAIL / 0 SKIP** |
| pytest 调用次数 | **1**（自然 retry 0、watchdog 0；未补跑、未追加节点、未自行补 compat） |
| guard | `boundary=implementation-production-composition-correction-03`、`installed_before_the_candidate_import=true`、**denials=[]（0）** |
| FD（root 诊断） | `fd_before=[0,1,2]`、`fd_after=[0,1,2]`、**`fd_leaked=[]`** |
| 线程 | `threads_after=['MainThread']`、`only_the_main_thread_remains=true` |
| counter（外层只读，前后各一次） | 前后**完全一致**：sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive / 28 starts / 240 reserved / 12.362 spent；**未写、未退款、未清零、未新建、未复活旧 grant** |
| 原始证据 | `directed-scope.stdout.log`、`.stderr.log`、`directed-scope.guard.json`、`directed-scope.json`、`selection.json`、`fd-thread-cleanup.json`、`commands.json`、`counter-before.json`、`counter-after.json` |

本轮**零** OS 子进程、零 socket、零 sqlite、零模型/GPU/native/服务/下载/用户媒体动作；
仅本进程 thread、pipe 与合成文件。

### 8.3 逐节点结果（35/35 PASS）

| 组 | 节点 | 结果 |
|---|---|---|
| M04 | `test_an_external_dependency_anchor_is_bound_to_its_whole_chain[legal]` / `[parent-link]` | 2/2 PASS |
| M06 | `test_the_output_chain_is_bound_before_the_public_precheck_transition` | PASS |
| M06 | `test_a_replaced_output_after_the_precheck_is_refused[root\|temp\|controller\|ancestor]` | 4/4 PASS |
| M06 | `test_the_created_output_directory_is_bound_to_the_descriptor_that_was_opened` | PASS |
| M08 | `test_a_failed_terminal_receipt_is_a_structured_unknown` | PASS |
| M08 | `test_a_primary_failure_and_a_terminal_persistence_failure_stay_separate` | PASS |
| M08 | `test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[keyboard-interrupt\|system-exit]` | 2/2 PASS |
| M08 | `test_the_release_of_the_anchors_touches_only_its_own_descriptors` | PASS |
| M08 | `test_a_failure_of_the_terminal_observation_is_a_structured_unknown` | PASS |
| 正例 | `test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary`（真实 16 行 QualityPhase 全链） | PASS |
| 回归 | 5 个 run-root 锚 + 4 个既有输出身份 + 双存储失败 + native 拒绝 + 有界读 + 2 个 fd 快照 | 15/15 PASS |
| 兼容 | 冻结 owner 的 6 个既有兼容节点（与纠偏 02 同集） | 6/6 PASS |

**这些断言通过只证明本轮定向范围内的事实**，不构成产品 12 项、I01–I24、原 ledger、
质量门限、真实 native/Windows/A06 或人签的证明，也**不**是 Stage PASS。

## 9. 剩余边界与不声称项

* I01–I24 固定分母、产品 12 项、真实 native/Windows/A06、原 ledger、质量门限、人类签署
  **均未在本轮证明**；正式 A03/A05/A09 完整义务仍未证（BLOCKED）。
* `stage_pass_claim=false`、`product_gate0=false`、`real_execution_performed=false` 保持。
* 实现者只能报告 **READY_FOR_REVIEW**；独审实例与人类签署保留在各自 owner。
* 本报告**不签 Stage PASS**、不推进 Stage、不修改 control 或产品合同。

## 10. 停止十字段

| 字段 | 本次状态 |
|---|---|
| 当前坐标 | 以 root execution-control 为准：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION |
| 本批完成 | M04/M06/M08 的一次集中实现 + meta01/m03 事实勘误 + root ACK 后的一次受 guard 定向批次（35 collected / 35 invocations / **35 PASS / 0 FAIL / 0 SKIP**，exit 0，wall 12.178 s，guard 0 denials，FD 无残留，仅 MainThread，counter 前后未变） |
| 最后通过门禁 | 本批无新增 Stage 门禁；M05/M07 及指定 FD snapshot 修复的独审关闭保持 |
| 当前阻塞门禁 | S3_P4_COMPOSITION_ANCHORS_PARSE_SEAL_OUTPUT_IDENTITY_RECEIPTS_TERMINAL；实现侧已交 READY_FOR_REVIEW，等待 root 回收与独立审查 |
| 全局路线位置 | 既有统一切片不扩大为完整 R1 或旧 S2 人签 |
| 剩余工作 | root 回收与独立审查（独审关闭 M04/M06/M08/meta01/m03）；产品侧仍缺 I24、产品 12 项、原 ledger、质量门限与人签 |
| 下一责任人 | root（回收与归档）→ 独立审查实例 → 人类签署 |
| 所需授权 | 既有授权足够，无待人批；未要求模型/ledger 补验 |
| 证据目录 | `reports/v0-s3/product-gate0/implementation-production-composition-correction-03/` |
| 精确停止原因 | root ACK 覆盖的唯一批次已执行完毕并如实记录（1 次 pytest 调用，35/35 PASS，exit 0）；按 root 指示交付 READY_FOR_REVIEW，不再就同一封存计划求批、不再自行补例/复跑 |

当前 V0–V3 大纲（直接读取 root control，完成/总子项，不是工时百分比）：

- V0-S0 1/2：基线探索
- V0-S1 5/5：图片与独立人工
- R0 1/2：独立服务复核
- R1a 5/5：单图 React/FastAPI
- V0-S2 7/8：视频与资源控制
- V0-S3 0/6：离线质量与增量包
- R1 0/4：人工业务骨架
- V1-M1 0/3：多镜头拆分与逐镜头人物场景动作
- R2 0/4：任务与正式运行包
- R3 0/4：镜头资产与检索
- R4 0/4：MCP与恢复
- R5a 0/4：证据与建议合同
- R5b 0/4：受控生成交接
- R5c 0/4：集成与完整交付
