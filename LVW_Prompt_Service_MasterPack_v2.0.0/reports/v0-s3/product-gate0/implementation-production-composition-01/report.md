# S3-P4 生产组合 01：实现报告（离线组合接线）

状态：**READY_FOR_REVIEW**。本报告**不是** Stage PASS，**不是** 产品 Gate0，**不是**
人工签署。本包所有产物都带 `stage_pass_claim = false` 与 `product_gate0 = false`；
离线 seam 的合成正例**没有**让产品十二键变绿（`pass_count = 0`，十二键全部 `BLOCKED`）。

冻结依据：`reports/v0-s3/product-gate0/production-composition-01/contract.md`（冻结架构、
文件范围、状态机、验收映射）、同目录 `fixture-acceptance.json`（13 fixture 组件已独审接受，
`13 PASS / F0 / M0 / m0`，分母固定 24，`stage_pass_claim=false`）、
`received-review/remaining-workpack.md` 与 `received-review/i01-i24-coverage-delta.md`
（固定 I01–I24 的剩余缺口）。

实现 HEAD：`c6bce90eeac384d534ebb7601193693840b5b70d`（仅证据后继，代码基线 `07277a6`）。
旧 grant 已 `EXPIRED_EXECUTION_COMPLETE_PENDING_INDEPENDENT_REVIEW`，本包**未复活**该 grant，
**未**重跑 13 fixture，**未**机械重跑 41/74/186/134/257。

---

## 1. 变更清单（严格遵守 contract 的允许/禁止清单）

| 路径 | 变更 | 性质 |
|---|---|---|
| `tools/v0_s3_production_controller.py` | **新增**：正式 controller、有限 context 准入、native 准入校验、离线组合 seam、原收据适配、十二键汇总、CLI `main` | 新文件（contract 允许的新增文件） |
| `tools/test_v0_s3_production_composition.py` | **新增**：定向组合与负例 33 个用例 | 新文件（contract 允许的新增文件） |
| `tools/v0_s3_quality_worker.py` | **窄改**：`main(argv=None, *, driver=None, stream=None, error_stream=None)`。命令行路径的**行为逐字节不变**（仍由绑定 context 构造 native driver、仍写标准输出/标准错误）；三个关键字参数只是进程内接线，CLI 不可达 | 最小内部接线适配（contract 明确允许） |
| `reports/v0-s3/product-gate0/implementation-production-composition-01/` | **新增**：本报告、义务映射、原始定向证据、真实 run-root 产物 | NEW 报告目录（contract 指定的唯一新报告名） |

**未改动**：`tools/v0_s3_quality_phase.py`（QualityPhase）、`tools/v0_s3_supervisor.py` 及其测试、
`tools/v0_s3_coordinator.py`、`tools/v0_s3_runtime_binding.py`、`tools/v0_s3_stage_runtime.py`、
`tools/v0_s2_runtime.py`、executor/runner/fixture、公共合同、阈值分母、旧证据、旧 control、
`MANIFEST.sha256`、V2 目录、既有 `implementation-integration-01/report.md` 的既有未提交修改。

`tools/v0_s3_coordinator.py` 的摘要与 `composition-run.receipt.json.source_sha256` 一致
（`14e8dd28…f12c`），`tools/v0_s3_quality_phase.py` 一致（`90552ea1…e8789`），
`tools/v0_s3_supervisor.py` 一致（`c669e97f…d848b3`）：本包没有偷偷改动冻结 owner。

---

## 2. 架构：同一个 controller，同一条生产路径

```
CLI(main)  --context <sealed controller context>            # 闭合参数；无 --force、无命令参数
   │
   ├─ PRECHECK        精确 hash / run / candidate / authorization / root identity
   │                  16 行投影（原 phase 解析器）/ source identity / 父预算
   │                  依赖 manifest / binding / 固定生产命令
   │                  └─ native 准入：默认拒绝 → REFUSED_BEFORE_START，0 spawn
   ├─ PLAN_SEALED    ParentOriginalEvidence.seal_plan(16 行) + seal_root + SealedPlan
   ├─ WORKER_SUPERVISED  ParentSupervisor.run()
   │      ├─ build_production_command() → [python, -I, -B, tools/v0_s3_quality_worker.py, --context, …]
   │      └─ worker.main → WorkerContext.load → build_native_driver / 注入 driver
   │             → run_worker → 真实 QualityPhase.run（16 行）→ ProtocolWriter → 真实 os.pipe
   │             → 父真实 reader → 父真实 canonical 校验
   ├─ ORIGINALS_VERIFIED  load_published_execution_receipt / load_source_plan
   │                  + ParentOriginalEvidence.seal_originals + manifest()（含重核）
   ├─ RECEIPTS_BOUND  由本轮真实事实生成 aggregate 输入（不手写 complete_receipts）
   └─ SUMMARY_PERSISTED  aggregate_twelve_keys → 排他落盘（O_EXCL，不覆盖）
```

* **状态机**：`PRECHECK → PLAN_SEALED → WORKER_SUPERVISED → ORIGINALS_VERIFIED →
  RECEIPTS_BOUND → SUMMARY_PERSISTED`；未开始即被拒为 `REFUSED_BEFORE_START`；开始后不明为
  `UNKNOWN_RETAINED`。错误路径不重发、不退款、不换 runid、不换样本；落盘一律 `O_EXCL`。
* **收据适配**：`stage_binding / image_input / video_input / output_contract / no_overwrite /
  file_safety / resource_budget / quality_16_rows` 由本轮 canonical receipt、sealed source plan、
  父 manifest 与绑定事实生成；`a06_isolation / install / rollback / independent_score /
  webp_format / cleanup / no_approval_gate / cancel_release / manual_export` 保持
  `BLOCKED/NOT_RUN` 并带机器可读原因，**不造 PASS**。
* **同源来源链**：context → projection → plan → worker context → canonical → source plan →
  raw（80 件）→ 父 manifest → receipts → summary，每一跳都带 `owner` 与 `sha256`
  （`composition.receipt.json.summary.provenance`）。

### 2.1 投影解析：复用原 owner，不建第二套协议
controller 通过冻结模块中**同一个**解析函数 `QualityPhase._parse_projection` 解析 16 行
（只提供该方法所需的 `projection_bytes` 属性）。冻结的 phase 模块**未被修改**，没有第二套投影
协议；phase 自己会拒绝的投影，controller 在 spawn 之前同样拒绝
（`CONTROLLER_PROJECTION_REJECTED:…`）。若 root 认为应改为公开接口，这是一处**最小内部接口**
候选，但本包不需要改动任何冻结文件即可满足合同。

### 2.2 离线组合 seam：进程内、显式、不可从 CLI 打开
`OfflineCompositionSeam` 只替换三件事：**native driver 的构造**、**OS 子进程**、**单调时钟**；
worker 入口、`WorkerContext.load`、真实 `QualityPhase`、真实协议写入、真实父读取、真实
canonical、父 manifest、十二键汇总**全部是生产实现**。

* seam 是 Python 对象：`ProductionController(context, seam=True)` 被拒（`CONTROLLER_SEAM_INVALID`）；
  context 的键集闭合，序列化一个 `seam` 字段被拒（`CONTROLLER_CONTEXT_KEY_SET_INVALID`）。
* seam 不创建任何 OS 子进程：worker 在**线程**中运行，经**真实 `os.pipe`** 与父通信；
  父的 `_StreamReader` 读的是真实 fd。guard 在候选 import 之前就封锁了
  `subprocess/socket/fork/exec/system/sqlite3.connect`，本轮尝试次数为 **0**。
* 本轮 `fd_leaked = []`：worker 线程结束、两个 reader 到达流尾并被关闭、写端与 stdin 由 seam 关闭。

---

## 3. 真实 native 执行准入：默认拒绝，且今天确实被拒

native 准入不是布尔、不是平台字符串、不是自写能力 JSON，而是**一条被封存并逐项核验的引用链**：

| 元素 | 校验方式 | 本轮状态 |
|---|---|---|
| budget binding | **已接受**的 `S3BudgetBindingProvider`（已接受 loader + validator + identity：run/candidate/child/model/authority root/原账本身份/工具摘要/execution binding/protocol source/expiry） | 在合成绑定用例中**通过**（`verified: ["budget_binding"]`） |
| native custody | 被引用收据必须带 `status=PROVEN` 与 `descendant_handles_closed`/`native_services_stopped` | 缺失 |
| gpu release | `status=PROVEN` + `gpu_released` | 缺失 |
| install / rollback | `status=PROVEN` + `installed` / `rollback_verified` | 缺失 |
| grant | `status=PROVEN` + `grant_active` | 缺失 |
| tool closure | 每个文件路径与摘要现场重算 | 缺失 |

因此 CLI 的真实路径稳定停在 `REFUSED_BEFORE_START`，`spawn_attempts = 0`，且**不写任何候选业务产物**
（`temp/s3-quality` 不存在）。**没有** `--force`、没有可开启真实执行的开关、没有平台字符串旁路。
controller 从不打开原账本、不扣账（`original_ledger_touched_by_this_controller=false`，
扣账 owner 仍是原 authority）；合成绑定用例前后原账本字节与 mtime 不变。

---

## 4. 定向范围与一次集中执行的结果

范围在执行前固定（contract：一次集中跑正例与失败路径，不机械回归）：

| 组 | 命令 | 节点 | 结果 |
|---|---|---|---|
| A 新组合 | `tools/test_v0_s3_production_composition.py` | 33 | 33 PASS |
| B 兼容（被复用组件） | `tools/test_v0_s3_integration.py` | 84 | 84 PASS |
| C 兼容（被改动文件） | `tools/test_v0_s3_supervisor.py -k "worker or context or production_command"` | 6 | 5 PASS / 1 SKIP |
| 合计 | | **123** | **122 PASS / 0 FAIL / 1 SKIP** |

唯一 SKIP：`test_a_protocol_violation_is_refused[early_exit-WORKER_EXITED_WITHOUT_TERMINAL]`，
原因由被测代码自己给出：“the finite fixture process machine gate is not bound by the root”。
共享 counter 为 `active=false`、额度 `EXPIRED`，机器门未开 → 该**真进程**用例被跳过，
既不算失败也不算通过；本包没有去绑定它，也没有复活过期 grant。

真实组合运行（`composition.receipt.json`，node `0019baba027122fb05ca00e624bcfb91`）：

* 66 条协议消息、16 行全部 `PASS`、无协议违规；
* 父真实读到 canonical（`temp/s3-quality/qd-receipt.json`，55136 字节，摘要
  `5f2a09e0ca070469db3db39cc353f14e514b1ee4eaed0cad126e6d649b10f278`）；
* 父封存 1 件 canonical + 1 件 source plan + 80 件 raw，并消费 manifest 重核；
* 收据：`8 PASS（离线范围事实）/ 9 BLOCKED`；十二键**全部 BLOCKED**，`pass_count = 0`；
* worker 退出码 0、`fd_leaked = []`、`closed_streams = ["stdout","stderr"]`。

---

## 5. C01–C12 与 I01–I24 的实际映射

机器可读版本：`obligation-mapping.json`（含每个 I01–I24 的 `this_package` / `evidence` / `gap`）。

| 映射 | 状态 | 本包实际证明 | 仍缺 |
|---|---|---|---|
| C01 / I03 I04 I23 | PROVEN_NEGATIVE_OFFLINE | 缺/错 context、hash、root、candidate、authorization、投影均在 spawn 前拒绝，0 spawn、无业务产物 | 目标平台的真实 native 准入 |
| C02 / I07 | PROVEN_OFFLINE | 正式 worker 入口 + 真实 phase 16 行 + 真实协议 + 真实 canonical 落盘 + 正式 controller 消费 | native 依赖闭包、真实 worker 进程、真实媒体 |
| C03 / I10 I11 I21 | PROVEN_OFFLINE | 真实行/历史次序被父接受；首次宣布固定期限；重复晚到被拒且不延期；10800/600/21600 保留；注入时钟驱动父期限 | 真实满时长运行与真实 child 期限 |
| C04 / I13 I14 | PROVEN_NEGATIVE_OFFLINE | worker 拒绝 / canonical 被改 / canonical 缺失 / 终态引用越界 → 无成功汇总，保留根与预约，不退款不重发不归档 | 产品 owner 的真实 cleanup 失败路径 |
| C05 / I16 | PROVEN_NEGATIVE_OFFLINE | controller 真实调用 manifest 并消费重核；根被迁移、原件被改、原件缺失均拒绝 | Windows reparse/junction 边界 |
| C06 / I19 I20 | PROVEN_OFFLINE | 本轮真实收据 → 真实 `aggregate_twelve_keys`；缺 QS/A06/WebP/cleanup/安装回滚非 PASS；旧 9 不能补绿；独立分由已接受 QS owner 重算（匹配则 PASS、不匹配则 BLOCKED） | 真实独立评分、真实 A06 隔离、WebP 收据、安装与回滚收据 |
| C07 / I24 | PROVEN_OFFLINE | context→projection→plan→canonical→source plan→raw→manifest→summary 同源链；外来收据被拒；summary 只写一次 | native 后代 custody 与 GPU 释放 |
| C08 / I22 | PROVEN_OFFLINE | 候选 import 前独立硬 guard；本轮 0 次尝试；测试临时根清理**不**冒充产品服务清理 | 仅本离线包的边界，不是 native 运行许可，也不是 A06 证明 |
| C09 / I01 I02 I05 I06 | PROVEN_NEGATIVE_OFFLINE | native 准入真实走已接受预算权威（loader/validator/identity 全跑），原账本不开不扣；安装与回滚被要求且缺失 | 真实首次 default 绑定、warm 关闭、目标平台 S2 默认回归、真实安装基线 |
| C10 / I17 I18 | PROVEN_OFFLINE | 生产残留 accessor 被真实使用；空残留有证，未知残留保留自身错误，绝不读成空，controller 不删除任何文件 | 目标平台真实残留；Windows junction/reparse |
| C11 / I15 | PROVEN_OFFLINE | 恢复只协调既有证据：不重放、不重发、不退款、不归档、不按文件 PID 杀进程；离线无 custody → 恢复 BLOCKED | 真实父崩溃与真实子进程持久归属 |
| C12 / 全 24 | PROVEN_OFFLINE | 逐 I01–I24 给出本包实际范围、证据与缺口（见 `obligation-mapping.json`） | **未签任何一项 I01–I24；固定 24 分母不变；未建新 28 分母** |

---

## 6. 仍缺的真实准入（本包不证明、不伪造）

1. Windows 上的真实 native 执行与真实 worker 进程；
2. native 后代 custody 与 native 服务的有界释放；
3. 真实 GPU 释放；
4. 真实 A06 隔离；
5. 原账本的真实消费与扣账；
6. 十六行的真实独立质量评分（16 行执行 ≠ 内容质量通过）；
7. WebP 格式产品收据；
8. 产品安装基线与安装回滚收据；
9. 产品服务的真实 cleanup 收据；
10. 固定 I01–I24 的整体与产品十二键。

后续真实准入须由 root 在母授权内另行冻结并封存（本包不要求人类重复批准，也不自行发起）。

---

## 7. counter、预算、重试与临时环境

* 共享 counter `/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json` **只读**观察：
  运行前后 sha256 相同（`acbdb8b1…23b98`），`active=false`、`starts_total=28`、
  `reserved_wall_seconds=240`、`spent_wall_seconds=12.362` 不变。
  **未**写入、**未**退款、**未**清零、**未**新建 counter。
* 自然 retry **0**、watchdog **0**。首次 429 → 立即 `WAIT_BUDGET` 停止，不重试、不换
  provider/model/account/Harness/Codex 接手（本次未触发）。首次审批拒绝或超时 → 停止并 ask root，
  不包装、不改审批（本次未触发）。
* 临时环境 `.claude/settings.local.json` 为 root 创建，本包**未触碰**，当前 sha256 仍为
  `7e6320a5…8010c1b0`；由 root 在完成后按 hash 恢复，本包不自删。

---

## 8. 兼容旧组件的范围

* `tools/v0_s3_quality_worker.py`：`main` 的命令行行为不变（新增参数只做内部接线）；
  既有 `WorkerContext` / `run_worker` / `ProtocolWriter` 的调用点未改。
* `tools/test_v0_s3_supervisor.py`：5 个 worker/context/生产命令节点全部通过（1 个真进程节点
  因机器门未开而跳过）。
* `tools/test_v0_s3_integration.py`：84 节点全部通过（coordinator、父原件证据、十二键聚合、
  残留 accessor、runtime/profile 工厂、预算绑定 provider 均未受影响）。
* `tools/v0_s3_quality_phase.py`、`tools/v0_s3_supervisor.py`、`tools/v0_s3_coordinator.py`、
  `tools/v0_s3_runtime_binding.py`、`tools/v0_s3_stage_runtime.py`：**字节未变**（见收据
  `source_sha256`）。

---

## 9. 证据文件

| 文件 | 内容 |
|---|---|
| `report.md` | 本报告 |
| `obligation-mapping.json` | C01–C12 与 I01–I24 的机器可读实际映射与缺口 |
| `run_composition_checks.py` | 本轮的受控 runner（进程内执行，零 OS 子进程） |
| `composition-run.receipt.json` | 本轮总收据：唯一 node、执行次数、源码 hash、实际 argv、退出码、组合状态、定向范围、guard 计数、counter 前后只读观察 |
| `composition.receipt.json` | 组合本身的完整收据：状态机、命令、父证据、manifest、收据、十二键、来源链、FD/线程清理 |
| `directed-scope.node-results.json` | 123 个节点的逐节点结果 |
| `directed-scope.stdout.log` / `.stderr.log` | 定向范围的原始输出 |
| `run-root/` | 真实 run-root 产物：16 行输入、canonical、source plan、80 件 raw、父 manifest、summary |
| `interim-run-01/`、`interim-run-02/` | 开发迭代期的两次完整运行收据与日志（保留，不覆盖、不删除）。两者的 run-root 与最终运行等价（canonical 收据含 run-root 路径，故摘要随目录而变），未重复保留其 run-root |

收据必备字段对照：唯一 node `0019baba027122fb05ca00e624bcfb91`、执行次数 1、源码 hash
（`composition-run.receipt.json.source_sha256`）、实际 argv（runner 与固定生产命令两条）、
退出码（runner 0；组合内 worker 0）、run-root/plan 原始产物来源（`summary.provenance` 与
`run-root/`）、FD 与线程清理（`fd_cleanup`：无泄漏、reader 关闭、worker 线程结束）。

---

## 10. 交付

单候选实现 + 本 NEW 报告 + 原始定向证据 + 兼容旧组件范围 + 仍缺真实准入的清单。
本实现者只报告 **READY_FOR_REVIEW**；**不**宣布 Stage PASS，**不**宣布产品 Gate0，
**不**代替人工签署，**不**自行发起真实准入。
