# S3-P4 生产组合纠偏 04：实现报告（M08 终态异常统一收口，唯一实现者，一次集中修复）

> 实现者：Claude Code（唯一实现者，禁止派生 Agent）
> 上游：root 冻结包 `production-composition-correction-04`（`contract.md` / `root-decision.json` / `received-review/review.md`）
> 上游裁决：`msg_fdff1d8f63c6`，Fatal 0 / Major 1 / Minor 0，`CHANGES_REQUIRED`，唯一开放项 `M08_TERMINAL_EXCEPTION_AND_OWNED_RESOURCE_LIFECYCLE`
> 基线候选：`6885f7a62b223f5e2c7904a9f929e760396fd88b`（impl HEAD `6ea33bc4ac8a383df8db1be978b077e7ad9d8338`）
> 状态：**READY_FOR_REVIEW**（不签 Stage PASS）

---

## 1. 文件范围（严格按 contract）

| 类别 | 文件 | 说明 |
|---|---|---|
| 改动 | `LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s3_production_controller.py` | 唯一实现源 |
| 改动 | `LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_production_composition.py` | 唯一测试源（新增 5 个定向节点） |
| 新增 | `LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-production-composition-correction-04/` | 本 NEW 报告目录 |

**未改动**：`controller_io` / `worker` / `supervisor` / `QualityPhase` / `coordinator` / `runtime` /
`authority` / `executor` / `fixture`、公共合同、`plans/execution-control.json`、任何 control、
任何 MANIFEST、任何旧证据目录、任何已关闭 owner（`quality_phase`、`coordinator`、
`runtime_binding`、`stage_runtime`、`budget_authority`、`local_program_authority`、
`v0_s2_runtime`）。未跨 owner 扩大：无需 askroot 的最小方案。

本轮**没有**改动 M04 / M06 / meta01 / m03（已关闭，未重开），也**没有**改动 M05 / M07 /
指定 FD snapshot / P01 及更早的关闭项。

---

## 2. M08 的单一根因与本次修复架构

独审指出的是**同一个终态收口缺口**的四个面，而不是四个孤立的失败点。本次按 contract 的
“一次梳理 run 的终态路径”执行：

> **终态的资源释放与诊断分离，收据持久化分离；资源的 owner 在独立 finally 完成有界关闭，
> 任何诊断步骤不得成为生命周期清理的唯一入口。**

### 2.1 终态路径的新结构（`ProductionController.run` 的 finally）

```
finally:                                        # 外层：run 体的收口
  try:
    try:  _release_owned_resources(receipt)     # (1) 生命周期：独立于一切诊断，先做
    except Exception: _record_resource_release_failure(...)
    try:  _record_run_facts(receipt); _finish(receipt, fd_before)   # (2) 诊断
    except Exception: _record_finish_failure(...)
    try:  _record_disk_actions(receipt)         # (3) 磁盘观察（有界失败）
    except Exception: _record_disk_action_failure(...)
    try:  _persist_receipt(receipt)             # (4) 收据持久化（唯一一次）
    except (KeyboardInterrupt, SystemExit): raise
    except Exception: 记为 not persisted
    _record_terminal_persistence(receipt)
    _record_persisted_state_difference(receipt)
  finally:
    _release_anchors()                          # (5) anchor 的独立 finally
  try:  _record_post_release_cleanup(...)       # (6) 释放后的第二观察点（仅诊断）
  except Exception: _record_observation_failure(...)
```

关键性质：

* **清理顺序不依赖易失败字段/哈希/快照观察先成功**：资源释放 (1) 在所有诊断之前；
  诊断 (2)(3)(6) 的任何失败都不会成为清理的唯一入口。
* **`KeyboardInterrupt` / `SystemExit` 不吞**：它们不被 `except Exception` 捕获，继续向上
  传播；anchor 的释放仍是独立 `finally`，因此取消路径下资源照样释放。
* **不关闭未知 FD、不依赖 GC、不按 `/proc` 枚举关闭任意 FD、不 kill 未知进程**：只关闭本轮
  自有资源（seam 自有 pipe + anchor），线程用有界 join，不请求第二次 cancel。

### 2.2 `_release_owned_resources`（新增）：真实自有 pipe 生命周期

* 由 **owner（seam）** 关闭本轮自有管道：`OfflineCompositionSeam.release_resources()` 复用
  既有的幂等 `close()`（`_PipeStream.close` 二次调用不重复关闭），**不发明新的清理平台**。
* 线程核验：`worker._thread.join(timeout)` 有界（`RESOURCE_RELEASE_JOIN_TIMEOUT = 2.0 s`）。
  线程未在界内结束则**保留并如实报告 retained**，不 kill、不追加 cancel。
* 正常结束的 worker 再关闭自有管道**不生成新动作**：`release_resources` 不调用 `cancel()`，
  事实里显式写 `no_new_cancel_was_requested: true`。
* close 失败**如实保留、不假清理**：close 的异常被捕获，join 照常进行，返回事实里带
  `close_failed / close_error / the_close_of_the_owner_failed`，控制器据此把 run 降级为
  `UNKNOWN_RETAINED`（`CONTROLLER_OWNED_RESOURCE_CLOSE_FAILED:<Type>`）。
* `owned_resource_release` 是收据中的新事实（幂等、无 seam 时 `NOT_APPLICABLE_NO_SEAM`）。

### 2.3 `_record_disk_actions` 自身失败：结构化 UNKNOWN（contract 第 1 条）

* 修复前：该方法抛出的 `RuntimeError` 直接逃到 `main` → `exit 5` + **stdout 为空** +
  stderr `S3_CONTROLLER_REFUSED EXCEPTION RuntimeError`，且**没有终态收据**（reservation 和
  summary 已存在）。
* 修复后：`except Exception` → `_record_disk_action_failure`：
  * 返回**结构化 UNKNOWN**：`state=UNKNOWN_RETAINED`、`unknown_reason=
    CONTROLLER_DISK_ACTION_RECORD_FAILED:RuntimeError`、`cleanup_proven=false`、
    root/reservation 保留、`refund/resend/archive_allowed=false`；stdout 非空；退出码 4（非 5）。
  * **已完成 summary 与 reservation 事实保留**：summary 仍是被真正写出的 summary，
    reservation 仍在盘上。
  * **fallback 仅有限直接字段构造**：`_fallback_disk_actions()` 只用 run 自己的事实
    （`_summary_write_completed` / `summary_path` / `summary_sha256`），
    **不重试同一个失败 observer，不看磁盘**。
  * **原失败与次级失败分开**：`_mark_terminal_unknown` 保留既有 primary reason，新失败进
    `secondary_failures` / `secondary_failure`（首个次级失败不被覆盖）。
  * **收据仍然落盘**（此前是没有收据）：持久化的收据携带 fallback 与 UNKNOWN 状态。
  * 若收据已落盘而最终返回状态不同，`persisted_receipt_state` 显式命名两者差异，
    **旧收据不被重写**。

### 2.4 `_finish` 内的诊断异常（contract 第 2 条）

* **第二次 `_fd_snapshot` 抛普通异常**：修复前 exit 0 / `SUMMARY_PERSISTED`、
  `cleanup_failures` 只有 `FINISH:RuntimeError`、**PRE_RELEASE `fd_cleanup` 缺失**。
  修复后：
  * `fd_cleanup` 一定存在，且 `status='UNKNOWN'`、`error='FINISH:RuntimeError'`、
    `fd_after=null`、`fd_leaked=null`（是“未知”，**不是缺失，也不是假的空集**）；
  * run 降级为 `UNKNOWN_RETAINED`（`unknown_reason='FINISH:RuntimeError'`）；
  * **后续观察正常不得追认早先未知**：POST_RELEASE 观察即使成功，状态仍为 UNKNOWN。
* **`_finish` 入口整体失败**：修复前 root/output anchors 被释放，但**真实 pipe FD10 仍开**
  （dev15/inode6349487/mode4480）。修复后资源释放在 `_finish` **之前**且独立于它，
  因此 pipe 由 owner 关闭、线程被有界 join；`_finish` 整体失败时 `fd_cleanup` 同样是
  `status='UNKNOWN'` 的完整条目（不留缺失键）。
* `_finish` 内的其他诊断（source digest / node id）也被单独保护，失败同样命名并降级，
  不再让整段收口丢失。
* **清理顺序**：资源释放 → 观察；不再依赖“观察先成功”。
* **close 失败如实保留**（见 2.2），不假清理。

### 2.5 历史写入事实与当前磁盘观察分离（contract 第 3 条）

修复前 `_record_disk_actions` 用 `os.stat(当前路径)` 是否 regular 来决定 `summary_written`，
`OSError` 被改成 `false` —— 即**一次观察失败可以撤销一次已经发生的写入**。

修复后：

| 事实 | 来源 | 语义 |
|---|---|---|
| `summary_written` | `_summary_write_completed`（**单调事实**，只在写入真正返回成功后置位，永不清除） | 这次运行**写过**summary |
| `summary_path` / `summary_sha256` | 只在写成功后设置 | 写的是哪个文件、什么摘要 |
| `summary_current_visibility` | 一次**有界**的当前观察 | `VISIBLE_REGULAR` / `VISIBLE_NOT_REGULAR` / `UNKNOWN`（具名 errno）/ `NOT_APPLICABLE_NO_SUMMARY_WAS_WRITTEN` |

* `stat` 失败 → `summary_current_visibility.state='UNKNOWN'` + `error='ENOENT'`，
  **`summary_written` 仍为 true**，运行状态不受影响（可见性是诊断事实，不是运行结果）。
* 路径被移动 → 同样是 `UNKNOWN`，**不撤销历史写入**，**不虚构回滚**。
* `summary_persisted`（资格字段）与 `disk_actions`（动作事实）差别保持不变。
* 收据写入仍只由 `_persist_receipt` 的实际成功返回决定，**不用文件存在自证**。

### 2.6 兼容（contract 第 4 条）

单/双 persist 异常、KI/SystemExit 释放、自有 FD 不误关、post observer 异常、正常 16 行
QualityPhase 真实链、M05/M07 与 native 拒绝语义**全部保持**；正式 A03/A05/A09 仍
**BLOCKED**，合成事实不算产品 PASS。

---

## 3. 候选身份与 hash

| 对象 | SHA256 |
|---|---|
| `tools/v0_s3_production_controller.py`（改动后） | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38` |
| `tools/test_v0_s3_production_composition.py`（改动后） | `5ba03b1b45f1d002d813b0619982a532af51ad5e63e78791348a84f711a59758` |
| `tools/v0_s3_controller_io.py`（未改，pin 证明） | `15305e4e3731a0e1533518725cf2bf27186b2b042e86167aee8130586ff8e7b1` |
| `tools/v0_s3_quality_worker.py`（未改，pin 证明） | `e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592` |
| `tools/v0_s3_quality_phase.py`（未改，pin 证明） | `90552ea113ccf53a2a1cedff3e3f399642ad932bf0f71bb1f9a57e1adb6e8789` |
| `tools/v0_s3_supervisor.py`（未改，pin 证明） | `7d210429e70761cea633e8f2e64d8a1f01709930068a21de5cbc3c5a519ce6d8` |
| `tools/test_v0_s3_supervisor.py`（未改，pin 证明） | `9783239ad1b48b243b6922c88ea8ce0f629544bd03beb16490bfb2e8493cf3e9` |

候选 SHA（交付提交）见 `candidate-delivery.json` 的 `candidate_sha`；它由提交本身的 tree
决定，与本报告同提交绑定。

---

## 4. 一次有限执行计划（已由 root ACK：`ACK_ONCE_ROOT_AMENDED_FD_IDENTITY_DIAGNOSTIC`，msg_06f51ccf0df6）

### 4.1 提交的计划与 runner

| 文件 | SHA256 | 说明 |
|---|---|---|
| `submitted-execution-plan-01.json` | `589eb16c90309206f4e6a24ef7051fee85388916763def5af2bc1c7bffdd7ff6` | 提交给 root 的计划（原样保留） |
| `run_directed_scope.py` | `a6520d6c1892ca6ddb820857cc71ecfa785b900ef41d2c0f50cb80ca6cc8ce5d` | **作者提交的 runner，原样保留，未执行** |
| `guard.py` | `49d81b1396845cb2d303bb9179492fb684adb2fd8410d80d2181b3f674fb67b2` | 前置 audit guard |
| `outer_counter_read.py` | `3b575311b0de885b4f027dc4f135773ae34b9c95629dfddff4645c53187c0da7` | guard 外只读 counter |

root 的 ACK 只修订**批次诊断**：root runner 的 FD 快照改为“每个名字用 `fstat` 核验
dev/inode/mode、过滤 EBADF、其他不确定返回 `None` 而非空集、同编号对象替换也能检测”，
并显式保持原 impl 的 `PACK_ROOT` 与 `REPORT`。

> **root runner**：`/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/production-composition-correction-04/validation-plan-01/run_root_frozen_scope.py`
> SHA256 `fe0e30a0a6a53d608a2bc837f7398da382b71f452ea7ad3653cffe98b87acfda`（与 ACK 一致，已核对）
>
> **实际执行的是 root runner；作者提交的 runner 未执行，也未被修改。**

### 4.2 实际执行的精确 argv 与 cwd

cwd（三条命令相同）：
`/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`

```
# 0 counter 只读（前）
/usr/bin/python3 -I -B \
  .../implementation-production-composition-correction-04/outer_counter_read.py \
  /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json \
  .../implementation-production-composition-correction-04/counter-before.json

# 1 唯一一批（guard 先于候选/pytest 导入）
/usr/bin/python3 -I -B \
  .../implementation-production-composition-correction-04/guard.py \
  /mnt/c/workspace/.../production-composition-correction-04/validation-plan-01/run_root_frozen_scope.py \
  .../implementation-production-composition-correction-04/directed-scope.guard.json

# 2 counter 只读（后）
/usr/bin/python3 -I -B \
  .../implementation-production-composition-correction-04/outer_counter_read.py \
  /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json \
  .../implementation-production-composition-correction-04/counter-after.json
```

`-I` 保留（隔离模式、no user site、无 `site.main`、无 `.pth`），`-B` 保留（不写字节码）。
223 个已封存命名依赖由 runner **显式 append** 后核验 digest；无插件 collection。

### 4.3 选中节点（20 个唯一节点；DIRECTED 5 + REGRESSION 15）

**DIRECTED —— 五个受控真实失败（本轮新增节点）**

1. `test_a_failure_of_the_disk_observation_is_a_structured_unknown`（磁盘观察器自身失败）
2. `test_the_observation_of_the_descriptors_at_the_end_of_the_run_is_unknown`（收尾观察失败）
3. `test_a_failure_of_the_finish_releases_the_owned_pipe_and_the_thread`（`_finish` 入口失败）
4. `test_the_fact_of_the_write_of_the_summary_is_not_revoked_by_a_failed_observation`（历史写事实 / stat 失败）
5. `test_a_failure_of_the_close_of_the_owner_is_kept_and_never_a_fake_cleanup`（owner close 失败）

**REGRESSION —— 直接相关兼容（15）**

`test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary`（真实 16 行 QualityPhase 全链）、
`test_a_failed_terminal_receipt_is_a_structured_unknown`、
`test_a_primary_failure_and_a_terminal_persistence_failure_stay_separate`、
`test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[keyboard-interrupt]`、
`…[system-exit]`、`test_the_release_of_the_anchors_touches_only_its_own_descriptors`、
`test_a_failure_of_the_terminal_observation_is_a_structured_unknown`、
`test_the_cooperative_cancel_stops_the_worker_and_the_thread_is_joined`（必要取消）、
`test_a_worker_that_does_not_cooperate_is_retained_and_the_run_stays_unknown`、
`test_an_ordinary_storage_failure_keeps_a_structured_unknown`、
`test_the_fd_snapshot_ignores_closed_enumeration_entries`、
`test_the_fd_snapshot_detects_a_real_open_descriptor_until_closed`、
`test_the_native_path_is_refused_before_any_spawn`（native 拒绝语义）、
`test_the_output_identity_of_the_run_is_bound_before_every_write[root]`、
`test_the_summary_is_never_written_outside_the_bound_root`。

**未跑**：作者 35、独审 27/37/21 整套、60/71/84/13/41/186/257/449/94 分母、已关闭
M04/M06/meta01/m03、整套回归；未自行补 compat。

---

## 5. 本批真实执行结果（1 次，1 批，无重试）

| 项 | 真实值 | 来源 |
|---|---|---|
| exit | `0` | `directed-scope.json` / 外层 returncode |
| wall | `21.762 s`（scope 内）/ `22.068 s`（外层实测含 guard） | `directed-scope.json` / 外层计时 |
| collected / invocations | `20 / 20` | `directed-scope.json` |
| PASS / FAIL / SKIP | **20 / 0 / 0** | `directed-scope.json` |
| 节点集合 | 与 ACK 的 `exact_nodeids` **逐项一致**（runner 在 collection 处断言，不一致即 exit 4） | `selection.json` |
| guard denials | `0`（`denial_count: 0`，`installed_before_the_candidate_import: true`） | `directed-scope.guard.json` |
| FD 前 / 后 | `[0,1,2]` / `[0,1,2]`，**逐个 dev/inode/mode 相同**，`fd_leaked: []` | `fd-thread-cleanup.json` |
| 线程 | 前 `['MainThread']` / 后 `['MainThread']`，`only_the_main_thread_remains: true` | `fd-thread-cleanup.json` |
| counter 前 / 后 | sha256 `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`、inactive、starts 28、reserved 240.0、spent 12.362 —— **前后完全一致** | `counter-before.json` / `counter-after.json` |
| 原失败留存 | 本批无失败；上一轮的真实失败（独审 27 例中的 4 个失败）**原样保留在 root 冻结包中，未删除、未改写、未包装** | root 冻结包 |

原始日志原样保留：`directed-scope.stdout.log`、`directed-scope.stderr.log`（空）、
`directed-scope.guard.json`、`directed-scope.json`、`selection.json`、
`fd-thread-cleanup.json`、`counter-before.json`、`counter-after.json`。

### 5.1 逐节点结果（20/20 PASS）

| 组 | 节点 | 结果 |
|---|---|---|
| M08 定向 | `test_a_failure_of_the_disk_observation_is_a_structured_unknown` | PASS |
| M08 定向 | `test_the_observation_of_the_descriptors_at_the_end_of_the_run_is_unknown` | PASS |
| M08 定向 | `test_a_failure_of_the_finish_releases_the_owned_pipe_and_the_thread` | PASS |
| M08 定向 | `test_the_fact_of_the_write_of_the_summary_is_not_revoked_by_a_failed_observation` | PASS |
| M08 定向 | `test_a_failure_of_the_close_of_the_owner_is_kept_and_never_a_fake_cleanup` | PASS |
| 正例 | `test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary`（真实 16 行 QualityPhase / 真实 pipe / 真实父读 / 真实 canonical / manifest / summary） | PASS |
| M08 兼容 | `test_a_failed_terminal_receipt_is_a_structured_unknown` | PASS |
| M08 兼容 | `test_a_primary_failure_and_a_terminal_persistence_failure_stay_separate` | PASS |
| M08 兼容 | `test_a_cancellation_of_the_terminal_persistence_releases_the_anchors[keyboard-interrupt]` / `[system-exit]` | 2/2 PASS |
| M08 兼容 | `test_the_release_of_the_anchors_touches_only_its_own_descriptors` | PASS |
| M08 兼容 | `test_a_failure_of_the_terminal_observation_is_a_structured_unknown` | PASS |
| m01 兼容 | `test_the_cooperative_cancel_stops_the_worker_and_the_thread_is_joined`（必要取消） | PASS |
| m01 兼容 | `test_a_worker_that_does_not_cooperate_is_retained_and_the_run_stays_unknown` | PASS |
| M08 兼容 | `test_an_ordinary_storage_failure_keeps_a_structured_unknown` | PASS |
| FD 快照 | `test_the_fd_snapshot_ignores_closed_enumeration_entries` / `test_the_fd_snapshot_detects_a_real_open_descriptor_until_closed` | 2/2 PASS |
| native | `test_the_native_path_is_refused_before_any_spawn` | PASS |
| 输出身份 | `test_the_output_identity_of_the_run_is_bound_before_every_write[root]` | PASS |
| 输出边界 | `test_the_summary_is_never_written_outside_the_bound_root` | PASS |

**这些断言通过只证明本轮定向范围内的事实**，不构成产品 12 项、I01–I24、原 ledger、
质量门限、真实 native/Windows/A06 或人签的证明，也**不是 Stage PASS**，也**不构成独审对
M08 的关闭**。

---

## 6. 归档计数勘误（作者 zip 声明 3504 与实际 2878）

独审指出：作者索引声明 `entries: 3504`，而实际 ZIP 成员为 2878；原索引只有聚合数字，没有
逐成员清单，因此**不能**据此声称丢了 626 个文件，也**不能**声称两者一致。

本轮在**只读、不解压、不执行、不跟随 symlink** 的前提下把口径核清
（`archive-count-reconciliation-04.json`，逐成员清单见 `synthetic-run-artifacts.members.json`）：

| 量 | 值 | 口径 |
|---|---|---|
| 作者索引声明 | **3504** | **合成运行根之下的每一个文件系统条目**（regular + 目录 + symlink + fifo） |
| 实际 ZIP 成员 | **2878** | **仅 regular 文件**：ZIP 无目录条目、无 symlink 条目，fifo 从未被打开 |
| 保留树实测 | regular 2878 + 目录 596 + symlink 29 + fifo 1 = **3504** | 与声明口径逐项吻合 |
| 差额 | **626** | = 596 目录 + 29 symlink + 1 fifo，**恰好等于全部非 regular 条目** |
| 逐名比对 | 成员集合 − 磁盘 regular 集合 = **∅**；磁盘 regular 集合 − 成员集合 = **∅** | **没有任何 regular 文件丢失** |

结论（有证）：**不是丢了 626 个文件**；626 是“全条目口径”与“regular 文件口径”之差，
全部由目录、symlink 与那一个 fifo 构成。作者原 ZIP **未修改**。

本轮自身的合成归档（`synthetic-run-artifacts.zip`，sha256
`3339c61e78d085d5fd7baa889de4162d54cdec0eec4572017ea79e6d828d008d`）在索引里**显式写明
口径**，避免同类歧义：`archive_members: 2421`（= regular 文件数）、`directories: 473`、
`symlinks: 20`、`entries_below_the_root_in_total: 2914`，并附逐成员清单
`synthetic-run-artifacts.members.json`。

---

## 7. 剩余边界与不声称项

* I01–I24 固定分母、产品 12 项、真实 native、Windows、A06、原 ledger、质量门限、人类签署
  **均未在本轮证明**；正式 A03/A05/A09 完整义务仍 **BLOCKED**。
* `stage_pass_claim=false`、`product_gate0=false`、`real_execution_performed=false` 保持。
* **自检不能关闭独审的 M08**：独审实例与人类签署保留在各自 owner；本报告只报
  **READY_FOR_REVIEW**。
* 本报告**不签 Stage PASS**、不推进 Stage、不修改 control / MANIFEST / 公共合同 /
  分母 / 旧证据。
* 未新建清理平台、未发明按 `/proc` 枚举关闭任意 FD、未 kill 未知进程、未依赖 GC 或
  历史 FD 忽略、未请求第二次 cancel/spawn。
* 本轮**没有**把上一轮的真实失败包装成成功：原失败原样保留在 root 冻结包中。

---

## 8. 停止十字段

| 字段 | 本次状态 |
|---|---|
| 当前坐标 | 以 root execution-control 为准：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION |
| 本批完成 | M08 终态异常统一收口的一次集中实现 + 归档计数口径勘误 + root ACK（`msg_06f51ccf0df6`）后的一次受 guard 定向批次（20 collected / 20 invocations / **20 PASS / 0 FAIL / 0 SKIP**，exit 0，wall 21.762 s，guard 0 denials，FD 身份前后一致且无残留，仅 MainThread，counter 前后未变） |
| 最后通过门禁 | 本批无新增 Stage 门禁；M04/M06/meta01/m03 与 M05/M07 及指定 FD snapshot 的独审关闭保持 |
| 当前阻塞门禁 | S3_P4_COMPOSITION_ANCHORS_PARSE_SEAL_OUTPUT_IDENTITY_RECEIPTS_TERMINAL；实现侧已交 READY_FOR_REVIEW，等待 root 回收与独立审查 |
| 全局路线位置 | 既有统一切片不扩大为完整 R1 或旧 S2 人签 |
| 剩余工作 | root 回收与独立审查（独审关闭 M08）；产品侧仍缺 I24、产品 12 项、原 ledger、质量门限与人签 |
| 下一责任人 | root（回收与归档）→ 独立审查实例 → 人类签署 |
| 所需授权 | 既有授权足够，无待人批；未要求模型/ledger 补验 |
| 证据目录 | `reports/v0-s3/product-gate0/implementation-production-composition-correction-04/` |
| 精确停止原因 | root ACK 覆盖的唯一批次已执行完毕并如实记录（1 次 pytest 调用，20/20 PASS，exit 0）；按 root 指示交付 READY_FOR_REVIEW，不再就同一封存计划求批、不再自行补例/复跑 |

当前 V0–V3 大纲（直接读取 root control 的 `development_outline`，完成/总子项，不是工时百分比）：

- V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4；V1-M1 0/3；
  R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
