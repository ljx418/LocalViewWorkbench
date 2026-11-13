# S3-P4 生产组合纠偏 02：实现报告（唯一实现者，一次集中修复 M04/M05/M06/M07/M08 + P01 勘误 + meta01 勘误）

**结论：READY_FOR_REVIEW。不是 Stage PASS，不是产品门禁通过，不是人签。**

基准候选 `7dc76ffeec685959f5906c612e58f7e1fc081425`（`7dc76ff`）。
冻结裁决来源：`reports/v0-s3/product-gate0/production-composition-correction-02/contract.md`、
`root-decision.json`、`execution-scope-correction.json`（Fatal0 / Major6 / Minor1；
M01/M02/M03/M09/m01/m02 关闭，M04/M05/M06/M07/M08 开放，P01 流程 Major，meta01 报告 Minor）。
原独审顶层证据保留在 `.../production-composition-correction-02/received-review/` 与
`review-full-evidence.zip`，原独审目录 `.../independent-production-composition-correction-01/` 未改。

## 1. 文件范围（严格按 contract）

允许且**仅**修改：

| 文件 | 变更 |
|---|---|
| `tools/v0_s3_controller_io.py` | 新增锚定打开/身份校验原语（逐层 no-follow 根链、目录链身份、目录相对有界读、外部只读锚） |
| `tools/v0_s3_production_controller.py` | M04/M05/M06/M07/M08 的全部接线（锚点读取、同一 bytes 解析+封存、根/祖先/输出目录身份链、正式义务与合成事实分离、终态持久化兜底） |
| `tools/v0_s3_quality_worker.py` | M04：五类实际引用改为经封存 context 声明的锚点读取 |
| `tools/test_v0_s3_production_composition.py` | 五个定向探针 + 正式正例 + 必要兼容点 |
| `tools/test_v0_s3_supervisor.py` | 仅 worker 引用兼容（context 增加声明锚点） |

**未改**：`tools/v0_s3_supervisor.py`（固定命令构造）、`tools/v0_s3_coordinator.py`、
`tools/v0_s3_quality_phase.py`（QualityPhase/runtime/authority/executor/runner/fixture）、
公开合同、阈值、旧证据、`plans/execution-control.json`、`.agent-governance/*`、`MANIFEST.sha256`、V2/V3。

## 2. 五个代码 Major 的修复

### M04 — 实际 worker 引用的锚点（原 `worker.py:88–96,212–220`）

* **缺陷**：五类引用（projection / source_identity / parent_budget / binding / dependency_manifest）
  走 `_read_sealed → read_bounded_regular`，只对**叶子** nofollow；把引用父目录换成指向
  root 外的 symlink，五者全部接受新解析路径；相同 hash 不阻止对象/祖先替换。
* **修复**：worker context 新增**封存声明的锚点集** `reference_anchors`
  （`RUN_ROOT` + `READ_ONLY_DIRECTORY`，锚点路径与名称写在被封存的 context 文档内）。
  - RUN_ROOT 锚：从文件系统根逐层 `O_NOFOLLOW|O_DIRECTORY` 打开并记录整条链的身份；
    引用相对根 fd 逐层 nofollow 打开，叶子 `O_NOFOLLOW|O_NONBLOCK` + 真实 bound 读取。
  - READ_ONLY_DIRECTORY 锚：锚目录本身 nofollow 打开并记录 (dev,ino)，锚下文件相对锚 fd 逐层 nofollow 读取，
    读后再校验锚身份；替换锚或替换文件均被拒。
  - 依赖清单自身声明的目录必须是已声明锚之一；清单内文件必须落在该锚内，否则 `WORKER_DEPENDENCY_FILE_OUTSIDE_THE_DECLARED_ANCHOR`。
  - 引用若不在任何声明锚内 → `WORKER_REFERENCE_OUTSIDE_DECLARED_ANCHORS`（不再任意父路径读；
    resolve 后的路径不被当作原身份，比较全程为字面量、前缀式）。
  - context 文档自身仍是“可信本地入口”：叶子 nofollow + 调用方给的 seal 校验（seal 保护内容，
    锚点保护对象与祖先）。run 数据引用默认必须在封存 run root 内。
* **证据**：探针 `test_an_actual_worker_reference_is_read_through_its_anchor`（5 个用例，把引用父目录
  移走并换成指向 root 外的 symlink → 五个方法全部以 `WORKER_ANCHOR_*` 拒绝；root 外字节存在但未被消费）。

### M05 — 解析文档与封存 bytes 同一（原 `controller.py:1287–1330,1369,1604`）

* **缺陷**：先 `load_published_execution_receipt` 解析磁盘文件，之后才 `_read_bounded_in_root` 重新读 bytes；
  manifest 重核的是**新** bytes，内部判定仍是**旧**解析 → 可发布“旧解析 + 新 seal”的矛盾结论。
* **修复**：
  1. canonical receipt 的 bytes **只读一次**，经**已绑定的根 fd**（`read_bounded_in_root_at`）读取；
  2. 冻结 loader（`load_published_execution_receipt` / `load_source_plan`）通过既有 `boundary=` 接缝
     **验证这同一批 bytes**（新增 `_SealedBytesBoundary` 只供给 bytes，不触碰文件系统，不改动冻结 owner）；
  3. controller 把 loader 返回的文档与**自己解码的同一 bytes**做严格交叉核对
     （canonical JSON 比较，类型敏感：`true`≠`1`，`1`≠`1.0`）→ 不一致即
     `CONTROLLER_CANONICAL_PARSE_NOT_BOUND_TO_BYTES` / `CONTROLLER_SOURCE_PLAN_PARSE_NOT_BOUND_TO_BYTES`；
  4. 封存仍是父所有者的独立观察，digest 与所读 bytes 不一致即 `CONTROLLER_ORIGINALS_CHANGED_BEFORE_SEAL`。
  * 结论：被适配/计分的文档 == 被 hash 的 bytes == 被封存的 bytes，否则拒绝；不再有“二次 unsafe 读取弥补”。
* **证据**：探针 `test_the_parsed_canonical_receipt_is_bound_to_the_bytes_that_were_hashed`
  （loader 返回非本批 bytes 的文档 → 拒绝、无 summary、根与预约保留）；
  既有消费边界用例 `test_an_original_that_changed_after_the_verification_is_refused` 继续有效。

### M06 — 根/祖先/输出目录身份（原 `controller.py:1172–1230,1667–1724`）

* **缺陷**：每次按绝对路径重新 open root；换普通 controller 目录仍写 summary+receipt，换 root/temp 仍写 receipt，
  换 root 父祖先为 symlink 则把 receipt 写到 root 外。
* **修复**：
  - PRECHECK 建立并**持有**：root 的逐层身份链（从 `/` 起，每层 nofollow）、root 的 (dev,ino)、
    输出目录 `temp/s3-production-controller` 的身份（创建与使用同一 fd，descriptor 相对）。
  - reservation / summary / receipt **全生命周期复用同一受控 dirfd**，写前校验根链 + 输出目录链身份；
    根、root/temp、输出目录、父祖先被换成 symlink 或换成别的对象 → 拒绝
    （`CONTROLLER_ROOT_IDENTITY_CHANGED` / `CONTROLLER_DIRECTORY_IDENTITY_CHANGED`），
    **不**在新 root 或 root 外写 reservation/summary/receipt。
  - 根内 O_EXCL 排他写保留；失败 partial 不删除；安全落盘不可达时 stdout 仍返回结构化状态。
* **证据**：探针 `test_the_output_identity_of_the_run_is_bound_before_every_write`（4 个用例：
  换 root / 换 root-temp / 换普通 controller 目录 / 换 root 父祖先为 symlink →
  均拒绝、summary 未写、终态 receipt 明确 not persisted、root 外无任何 summary/receipt）。

### M07 — 正式三义务无证不 PASS（原 `controller.py:1462–1490`）

* **缺陷**：`output_contract`/`no_overwrite`/`resource_budget` 用同名正式收据承载**缩小后的合成事实**
  （16 行 raw+suggestion 存在 / 本次 artifact 独占写 / reserved<=capacity）并给 PASS。
* **修复**：
  - 三个**正式**收据永远不是 PASS：必要子条件确实失败 → `FAIL`（写明失败的子条件）；
    没有失败但完整义务无证据 → `BLOCKED`（写明缺什么）：
    A03 四视图 + JSON/TXT 导出 + 格式切换 0 额外推理；A05 已有人工稿在非法 JSON/超时/OOM/未答下的保护与继续导出；
    A09 目标机 GPU/RAM/冷热/P95/0-OOM 完整矩阵。
  - 本次真实观察到的合成事实**另列**：`composition_facts`（kind `lvw.s3-composition-fact/1`，
    名称 `composition_fact_*`，scope `OFFLINE_SYNTHETIC_COMPOSITION`，
    `not_a_formal_product_obligation=True`），不进同名正式收据、也不填十二键。
  - 已修正语义保留：真实失败行（15PASS1FAIL、release/residue/provider 失败）仍是内部 FAIL，
    cleanup 语义与 residue 证据不变，顶层 12 键不遮盖内部状态。
* **证据**：探针 `test_a_formal_obligation_is_never_a_pass_of_a_synthetic_run`
  （三正式收据 BLOCKED + 事实单列 + 十二键无 PASS）。

### M08 — 终态持久化的普通异常兜底（原 `controller.py:1689–1724,1866–1876,2026–2028`）

* **缺陷**：finally 中的 `_persist_receipt` 只捕 `ControllerIOError`/`ControllerError`；
  受控 `RuntimeError` 使终态持久化再次失败并**逃逸** finally → exit5 / stdout 空 / 只有泛化 `EXCEPTION` 文字，
  收据与未知终态丢失。
* **修复**：
  - `_persist_summary` 与 `_persist_receipt` 捕获**普通 Exception**（不含 KeyboardInterrupt/SystemExit）：
    summary 侧 `CONTROLLER_SUMMARY_PERSISTENCE_FAILED:<Type>`（原失败）、
    receipt 侧 `CONTROLLER_RECEIPT_PERSISTENCE_FAILED:<Type>` 且 `receipt_persisted=false`（二次失败），
    两者**分别保留**；`_finish` 与 `_persist_receipt` 都在 try 内，finally 本身不再逃逸；
  - run() 始终返回结构化 receipt（state UNKNOWN、root/预约保留、refund/resend=false、
    `receipt_persisted=false`、`receipt_persistence_error` 明确）；
  - stdout 写失败也被显式命名（`STDOUT_WRITE_FAILED:<Type> STATE:<state>`），不吞取消；
  - KeyboardInterrupt/SystemExit 不吞，finally 的 FD/线程清理仍执行。
* **证据**：探针 `test_an_ordinary_storage_failure_keeps_a_structured_unknown`
  （summary 与 receipt 写入均抛 RuntimeError → exit=EXIT_UNKNOWN、结构化 UNKNOWN、两个失败分别可读、
  无逃逸、无空 stdout）。

## 3. P01 事实勘误（流程 Major，如实勘误，不改 counter、不补绿）

* **已发生的越包边界动作**：纠偏 01 的四批兼容回归**直接** `python -m pytest`、**未**套前置 audit guard；
  其中 budget 批（17 PASS）含真实 SQLite Fixture、8 次成功 + 1 次超额的业务 shim 调用（`program_budget._exchange` 真实 `Popen`），
  runtime 批（94 PASS）含 `test_correction02_factory_admission_and_owned_helper`（未 mock `_exchange`，断言真实 helper 的 exit/reap/reader/pipe）。
* **精确总数：UNKNOWN**（无运行时审计；不据通过日志伪造整个四批的精确启动数；
  外层 pytest/guard 解释器本身不充作 fixture 证据）。
* **越包事实**：上述至少 10 个真实业务 shim/helper 子进程与合成 SQLite 事务**超出本纠偏包**
  （冻结的最小定向 + pre-import guard + 零 OS fixture/SQLite 边界）。
* **counter 不变 ≠ 无额外动作**：原 counter 仍为 inactive / 28 starts / 240 reserved / 12.362 spent，
  hash `acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98`；
  该 counter 只能证未经该 counter 累计，**不能**证其他 helper 未启动。
  本次**不改、不退款、不清零、不新建 counter、不复活旧 grant**，也**不以未审计的额外日志做零动作证据**。
* **旧声明撤回**：纠偏 01 “全批零进程”声明就四批整体**撤回**（仅受 guard 保护的定向证据范围仍可单列复核）。
* **无证据声称**：原 ledger / 网络 / 模型 / GPU 被使用、或旧 13 fixture 被重放——均无证据，不作此声称。
* **后续执行**：严格分两步——第一阶段只做代码/测试编辑与文本/AST 静态检查（不导入候选、不 pytest、不 collect、不 compat、
  不跑任何实际业务 helper 或 SQLite）；第二阶段在 root 对**整批精确计划** ACK 之后，只跑该一批。

## 4. meta01 勘误（报告 Minor）

冻结源数量是 **7**，不是 8：实际冻结清单为
`tools/v0_s3_controller_io.py`、`tools/v0_s3_production_controller.py`、`tools/v0_s3_quality_worker.py`、
`tools/v0_s3_quality_phase.py`、`tools/v0_s3_supervisor.py`、`tools/v0_s3_coordinator.py`、
`tools/test_v0_s3_production_composition.py`（7 项，逐 hash 一致）。
旧报告 `implementation-production-composition-correction-01/report.md` **保留不改**；
本报告纠正计数，不据旧报告推断任何 429 历史。

## 5. 已关闭六项：未重开

M01（值比较=类型+值）、M02（可信 native 后端缺失→默认硬拒绝）、M03（context hash 链与 provenance）、
M09（发送前阻断重入）、m01（协作取消与诚实线程保留）、m02（text/binary 错误流保准确码）
本轮**不重新实现**，仅保留必要的兼容点（见 §7 的 nodeids）。

## 6. 变更文件与 hash（候选身份）

```
100a9c676f8dce219b551cb94db4d1fd23ba6bedd7af9aff9f949a692f3adc76  tools/v0_s3_controller_io.py
517d1e4b89e5bef3f57ddd123ad15d1bb9426d438e5c512f420d9bd11359890f  tools/v0_s3_production_controller.py
6bac34ebc6f6ee32e3b9cc13768dabb59ac8ceb901188cd29ebb3d333f32c3bb  tools/v0_s3_quality_worker.py
a5be735e79f325558728b9ea647b97760d01a0d749ddad9434671b9da6aa6196  tools/test_v0_s3_production_composition.py
9783239ad1b48b243b6922c88ea8ce0f629544bd03beb16490bfb2e8493cf3e9  tools/test_v0_s3_supervisor.py
1fb09dd9a874f0f6108dd482efaf3e12121bc4810efe31430dfc29736ffc1e4c  reports/.../implementation-production-composition-correction-02/guard.py
fe94493d1d6f6de917be916487f09cb49024eaf48dbabd226cf556c8211bd28e  reports/.../implementation-production-composition-correction-02/run_directed_scope.py   (未执行，见 §7.0)
3662b4a1be3be9b50028b8ffd1f0b260e562dfc7f260e39c421091c4e21bd934  reports/.../implementation-production-composition-correction-02/run_root_frozen_scope_attempt03.py  (root 冻结)
```

## 7. 验证计划与两次 root ACK / 两次真实执行

计划期间**没有**先行执行任何一轮验证；每一步都先有 root 的 ACK，ACK 不是新增人批。

### 7.0 ACK 链

| 轮次 | root ACK | 形态 |
|---|---|---|
| 计划 ACK | `production-composition-correction-02/validation-plan-01/ack.json`（`ACK_ONE_NARROWED_GUARDED_BATCH`） | 收窄为 DIRECTED 六函数（13 节点）+ 6 兼容点 = 19 唯一节点；root 冻结 runner `run_root_frozen_scope.py`（sha256 `9761d119…`），collection 集合/顺序不符即 exit4，源码 hash 漂移在 pytest import 前拒绝 |
| 环境纠正 ACK | `production-composition-correction-02/validation-plan-02/ack.json`（`ACK_ONE_ENVIRONMENT_CORRECTED_GUARDED_BATCH`） | 保留 `-I -B` 与原 guard；root 冻结 runner `run_root_frozen_scope_attempt02.py`（sha256 `1956dab8…`）：guard 武装且 5 个 source pin 核验后，仅追加已存在的 `/home/administrator/.local/lib/python3.12/site-packages`，先校验固定已装包文件 hash，不执行 `site.main`/`.pth`，不放开插件 |

本报告目录中的 `run_directed_scope.py`（我第一版 runner，sha256 `fe94493d…`）**未执行**：
root 否决了整个 composition 文件的执行，改为 root 自有的冻结选点 runner；该文件保留作为“计划与实际执行形态不同”的说明。

### 7.1 批次构成（每批 1 次受 guard 的 pytest 调用；外层只读 counter）

| 序 | 动作 | 命令形态 |
|---|---|---|
| 0 | 外层只读 counter（前） | 只读打开 `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json`，记录 inactive/28/240/12.362 与 sha256；**不写、不退款、不清零** |
| 1 | **受 guard 的定向批次** | `python3 -I -B <report>/guard.py <report>/run_root_frozen_scope_attempt02.py <report>/directed-scope-attempt02.guard.json`，cwd = 包根 |
| 2 | 外层只读 counter（后） | 同 0，只读复核未变 |

### 7.2 argv（真实执行的精确形态）

```
/usr/bin/python3 -I -B \
  .../implementation-production-composition-correction-02/guard.py \
  .../implementation-production-composition-correction-02/run_root_frozen_scope_attempt02.py \
  .../implementation-production-composition-correction-02/directed-scope-attempt02.guard.json
```

cwd = `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0`。
guard：`sys.addaudithook` 先于任何候选/插件 import 安装；`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`；
pytest 以 `--basetemp <report>/pytest-temp -p no:cacheprovider` 运行。

### 7.3 选中 nodeids（19 唯一节点，全部来自冻结的两个文件；与 root `validation-plan-02/ack.json` 的 `exact_nodeids` 逐条一致）

```
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[projection]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[source_identity]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[parent_budget]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[binding]
tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor[dependency_manifest]
tools/test_v0_s3_production_composition.py::test_the_parsed_canonical_receipt_is_bound_to_the_bytes_that_were_hashed
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root-temp]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[controller-directory]
tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write[root-parent-link]
tools/test_v0_s3_production_composition.py::test_a_formal_obligation_is_never_a_pass_of_a_synthetic_run
tools/test_v0_s3_production_composition.py::test_an_ordinary_storage_failure_keeps_a_structured_unknown
tools/test_v0_s3_production_composition.py::test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary
tools/test_v0_s3_supervisor.py::test_the_worker_really_invokes_the_quality_phase
tools/test_v0_s3_supervisor.py::test_the_history_wait_is_announced_before_the_row_finishes
tools/test_v0_s3_supervisor.py::test_a_context_with_a_wrong_seal_is_refused
tools/test_v0_s3_supervisor.py::test_a_context_with_an_unknown_key_is_refused
tools/test_v0_s3_supervisor.py::test_the_production_command_is_the_fixed_worker
tools/test_v0_s3_supervisor.py::test_the_production_command_carries_the_pre_sealed_context_hash
```

### 7.4 独立 pre-import guard

`guard.py`（sha256 `1fb09dd9…`，root 两次 ACK 均复用同一文件）用解释器 audit hook 拒绝并记录：
`subprocess.*`、`socket.*`、`os.system`、`os.fork`、`os.forkpty`、`pty.spawn`、`os.posix_spawn`、
`os.exec*`、`os.spawn*`、`sqlite3.connect`，以及对受保护状态的 `open`：
共享 counter、`.lvw-runtime/program02.sqlite`、任何 `original.*.sqlite|.sqlite3|.db`（报告目录内合成文件除外）。

### 7.5 有限预算 / 次数 / 日志 / 清理策略（实际执行值）

* **次数**：attempt01 1 次、attempt02 1 次（两次都是 ACK 覆盖的执行，非自动重试）；自然 retry 0、watchdog 0。
* **时间**：attempt02 wall 14.892 s（上限 300 s）。
* **日志**：attempt01 → `directed-scope.stdout.log`/`.stderr.log`/`directed-scope.guard.json`（原文件保留未覆盖）；
  attempt02 → `directed-scope-attempt02.stdout.log`/`.stderr.log`/`directed-scope-attempt02.guard.json`；
  机器证据 → `directed-scope.json`、`selection.json`、`fd-thread-cleanup.json`；真实 argv/exit → `commands.json`（三条记录）。
* **FD/线程清理**：runner 批次前后各取一次 `/proc/self/fd` 快照与 `threading.enumerate()` → `fd-thread-cleanup.json`。
* **counter**：只在外层只读，未写/未退款/未清零/未新建/未复活旧 grant。

## 8. 执行结果（真实记录）

### 8.1 attempt01（validation-plan-01 ACK，argv 未变）

* exit **1**，`ModuleNotFoundError: No module named 'pytest'`（`run_root_frozen_scope.py:130`）。
* 原因：pytest 8.4.2 只装在用户 site（`/home/administrator/.local/lib/python3.12/site-packages`），
  argv 的 `-I` 隐含 `-s`（不加载用户 site）。`-I` 来自我第一轮提问所写的 argv。
* **0 collection / 0 test call / 候选未 import / 0 OS 子进程 / 0 socket / 0 sqlite / 0 counter 动作**；
  guard 已武装、denials=0；5 个 source pin 在该行之前已核验通过（无漂移）。
* 原文件全部保留；未自动修复复跑，交 root 裁决（`msg_2e8340bdcbf1` → validation-plan-02 ACK）。

### 8.2 attempt02（validation-plan-02 ACK，精确 argv 真实执行）

* exit **1**（测试失败），wall 14.892 s，START 2026-11-13T11:57:40Z / END 11:57:55Z。
* **19 collected / 19 invocations / 18 PASS / 1 FAIL / 0 SKIP**；collection 集合与顺序与 ACK 完全一致（未 fail-close）。
* guard：`denials=0`、`denial_count=0`；0 OS 子进程、0 socket、0 sqlite、0 模型/GPU/native/服务动作。
* 进程级 FD/线程：`fd_before == fd_after == [0,1,2,4]`、`fd_leaked=[]`、`threads_after=['MainThread']`、
  `only_the_main_thread_remains=true` → **批次结束无任何描述符残留、无线程残留**。
* counter：外层只读**两次**（前 `counter-before.json`、后 `counter-after.json`）——两次均为
  inactive / 28 starts / 240 reserved / 12.362 spent、sha256 `acbdb8b1…`，**前后完全一致**；
  未写、未退款、未清零、未新建 counter、未复活旧 grant（外层读共 2 次，即 ACK 的 `external_counter_reads`）。

**逐节点结果**：

| 节点 | 结果 |
|---|---|
| `test_an_actual_worker_reference_is_read_through_its_anchor[projection|source_identity|parent_budget|binding|dependency_manifest]` | 5/5 PASS（M04） |
| `test_the_parsed_canonical_receipt_is_bound_to_the_bytes_that_were_hashed` | PASS（M05） |
| `test_the_output_identity_of_the_run_is_bound_before_every_write[root|root-temp|controller-directory|root-parent-link]` | 4/4 PASS（M06） |
| `test_a_formal_obligation_is_never_a_pass_of_a_synthetic_run` | PASS（M07） |
| `test_an_ordinary_storage_failure_keeps_a_structured_unknown` | PASS（M08） |
| `test_the_worker_really_invokes_the_quality_phase` 等 6 个兼容点 | 6/6 PASS |
| `test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary` | **FAIL**（仅 FD 记账断言） |

**唯一失败的性质（如实）**：正式 16 行组合正例的**链条本身全部成立**——失败点之前的断言均通过
（state=SUMMARY_PERSISTED、六步 transitions、16 行 PASS、manifest reverification、provenance、
summary/receipt 落盘、receipt_persisted=True、worker 线程 finished/retained=False），
失败只发生在**本次新增的“每次运行 FD 记账”**断言上：`fd_cleanup['fd_leaked'] == []` 实得 `[8]`。

* 定性：这是本轮引入的**记账口径缺陷**，不是观测到的资源泄漏。泄漏集合按 fd **编号**做差集，
  而本轮 controller 全程持有两个锚 fd（绑定根 + 输出目录），且 loader 不再打开 artifact boundary，
  改变了编号分配，使一个“在收据快照之后才释放”的描述符编号落进差集。
* 进程级证据与之一致：批次终态无残留。被报的 fd 8 在快照时开、之后关闭；
  **在不再执行一次的前提下不能断言 fd 8 的确切归属**，故不据此宣称闭合。
* 处置：按 ACK 的失败策略，未自动修复复跑、未追加 compat/collect，已交 root 裁决（`msg_01bdc0063ebb`）。

### 8.3 五项闭合状态（以 attempt03 为准）

| 项 | 状态 | 依据 |
|---|---|---|
| M04 实际 worker 引用锚点 | **闭合**：定向探针 5/5 PASS | attempt03（attempt02 亦 5/5） |
| M05 解析文档与封存 bytes 同一 | **闭合**：定向探针 PASS | attempt03（attempt02 亦 PASS） |
| M06 根/祖先/输出目录身份 | **闭合**：定向探针 4/4 PASS | attempt03（attempt02 亦 4/4） |
| M07 正式三义务无证不 PASS | **闭合**：定向探针 PASS | attempt03（attempt02 亦 PASS） |
| M08 终态持久化普通异常兜底 | **闭合**：定向探针 PASS | attempt03（attempt02 亦 PASS） |
| 正式 16 行组合正例 | **闭合**：整链 PASS（含 FD 记账断言） | attempt03 |
| FD 快照口径（根的发现） | **闭合**：两个新节点 PASS，正例 FD 断言 PASS | attempt03 |
| P01 / meta01 | 已如实勘误（§3、§4） | 本报告 |
| 真实 native / Windows / A06 / 原 ledger / 质量门禁 / Stage PASS / 人签 | **仍未证**（§9） | — |

三次尝试的真实结果互不覆盖：attempt01 = 0 collection（pytest 不可导入）；attempt02 = 19 节点 18 PASS 1 FAIL
（唯一失败为当时尚未修正的 FD 记账口径，链条此前断言通过**不等于**整个正例 PASS）；attempt03 = 21 节点 21 PASS。

## 9. 剩余边界与不声称项

* 真实 native 执行后端、真实 Windows/A06 隔离、原 ledger、质量门禁、Stage PASS、人类体验签署**均未证**；
  可信 native backend 缺失是已批准的明确空缺，本轮不要求新增真实验证。
* 正式 A03/A05/A09 义务未证（BLOCKED）；四输出/格式切换 0 推理、人工稿异常保护、
  真实资源与性能矩阵未证，保留原目标，不要求本轮跑实际模型补证。
* `stage_pass_claim=false`、`product_gate0=false`、`real_execution_performed=false` 保持。
* 实现者只能报告 READY_FOR_REVIEW；独审实例与人类签署保留在各自 owner。

## 10. 停止十字段

| 字段 | 本次状态 |
|---|---|
| 当前坐标 | root control：R1 / WP-R1-U3 / S3_P4_OFFLINE_INTEGRATION_PREPARATION；产品完整 R1 仍未完成 |
| 本批完成 | 五个开放代码 Major 的实现与闭合（attempt03：21 节点/21 PASS/0 FAIL/0 SKIP）、P01 与 meta01 事实勘误、FD 快照口径修正与两个正反例节点；三次尝试的真实记录全部保留 |
| 最后通过门禁 | 仅本批无竞争合成正式链与已关闭六项的既有定向证据（上一批）；本批无新增 Stage 门禁 |
| 当前阻塞门禁 | S3_P4_COMPOSITION_ANCHORS_PARSE_SEAL_OUTPUT_IDENTITY_RECEIPTS_TERMINAL；实现侧已交 READY_FOR_REVIEW，等待 root 回收与独立审查 |
| 全局路线位置 | 既有统一媒体早期切片已签；当前 S3 接线准备不补完整 R1/旧 S2 人签 |
| 剩余工作 | root ACK 后执行 §7 的唯一批次，回收失败/日志/hash，补齐 §8；随后独审 |
| 下一责任人 | root（回收与归档）→ 独立审查实例 |
| 所需授权 | 既有授权足够，无待人批；未要求模型/ledger 补验 |
| 证据目录 | `reports/v0-s3/product-gate0/implementation-production-composition-correction-02/` |
| 精确停止原因 | 三次 root ACK 覆盖的真实执行已完成并如实记录（attempt03：21 节点/21 PASS，exit 0，guard 0 denials，counter 未变）；按 root 指示交付 READY_FOR_REVIEW，不再就同一封存计划求批 |
