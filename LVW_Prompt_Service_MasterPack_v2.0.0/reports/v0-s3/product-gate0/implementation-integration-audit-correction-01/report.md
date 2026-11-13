# S3-P4-OFFLINE 审计守卫纠偏报告（implementation-integration-audit-correction-01）

状态：**READY_FOR_REVIEW**（实现者自检结论）。**不是** Stage PASS，**不是** 产品 Gate0，
**不是** 人工签署，**不是** 真实 fixture 运行证明。本轮**只做零进程纠偏与零进程定向验证**，
没有执行任何带机器绑定（machine binding）的 runner，没有启动任何真实子进程，没有接触
网络/模型/GPU/服务，没有写入原共享 counter，没有消耗剩余 60 秒池。

- 基线 HEAD：`763f3d561772ec8efa7aafe597b62ac77a3b7969`
- 候选：**承载本报告的提交**（自引用不可得，SHA 由 root 以 `git rev-parse HEAD` 读取）
- 变更合同：**none**（未改任何公共合同、门限、固定 24 分母、`plans/execution-control.json`、
  global MANIFEST、V2、coordinator/supervisor/quality_worker/fixture/S2 钩子/qualityphase/旧证据）
- 交接对象：root 复核候选与预算，独立裁决修复候选与两个遗留 PENDING charge

---

## 1. 失败根因（一处修复，完整链条）

root 的失败证据：`reports/v0-s3/product-gate0/fixture-audit-correction-01/decision.json`
与同目录 `finite-fixture-implementation-02.*`（13 收集 / 13 失败 / 外层退出码 1）。
失败链如下，每一步都由真实日志字节支持：

1. **第二个守卫**：旧 `run_guarded_checks.py` 在**模块导入时**执行 `sys.addaudithook(_audit_hook)`。
   `tools/test_v0_s3_supervisor.py` 为调用 `finalize_session` 等函数，在收集期以
   `lvw_s3_guarded_runner` 为名再次导入同一文件，于是**同一进程内存在两个审计钩子**，
   且**每个模块实例各有一份自己的 `PROCESS_GATE`**（旧代码里它是模块级字面量）。
2. **第二次否决**：第一个钩子（生产 entry 的钩子，`gate["executor"]` 已绑定真实 executor）
   先执行 `admit()` → **真实 charge 落账**（counter 出现 PENDING），随后第二个钩子
   （别名实例的钩子，其 `PROCESS_GATE["executor"] is None`）落入通用封禁分支 →
   `OfflineBoundaryViolation: offline boundary violation: subprocess.Popen ...`
   （`finite-fixture-implementation-02.stdout.log` 第 50/98 行，类名正是
   `lvw_s3_guarded_runner.OfflineBoundaryViolation`，即别名实例的类）。
   **审计事件 `subprocess.Popen` 在 fork 之前抛出**，所以**真实子进程从未被创建**。
3. **两个 PENDING 永久占槽**：前两次准入留下 2 条 `PENDING` charge（无 pid、无 handle）。
   `max_concurrent = 2`，于是余下 11 次准入全部被 `CPU_CONCURRENCY_LIMIT` 拒绝
   （stdout 日志第 128/203/291/380/465 行），旧 audit 先记 2 个 PENDING 的现象由此产生。
4. **收据谎报**：旧收据 `cleanup_proven = true`、`executor_session.children = []`、
   `fixture_process_starts = 2`——**零个句柄**却宣称清理全部成功，且把"准入次数"标成
   "process starts"。**receipt 的 `fixture_process_starts=2` 绝不是成功 fork**，本报告不再沿用该读法。

**结论：根因是"守卫所有权不唯一"，不是预算、不是绑定、不是 fixture 本身。**
本轮用一个修复同时消除第 1–4 步。

## 2. 修正内容（只改允许清单内三份源码）

允许范围：`reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py`、
同目录 `executor.py`、`tools/test_v0_s3_supervisor.py`，以及本新证据子树。

### 2.1 守卫：进程内唯一 owner（对应要求 1）

- 新增**进程级守卫注册表** `lvw_s3_offline_guard_registry`（存于 `sys.modules`，非模块私有）：
  持有 `owner_id`、`hook_installed`、`hook_install_count`、`install_attempts`、
  **唯一一份 `process_gate`**、唯一一份 `violation_class`。
- `install_offline_guard()` 幂等：真正安装钩子时 `hook_install_count += 1`；之后任何调用
  只 `install_attempts += 1` 并返回**同一个 owner_id**。
- **安装点移到 `__main__` 生产引导**：`if __name__ == "__main__":` 块内先
  `install_offline_guard()` 再 `main()`，因此守卫仍然早于 `import pytest` 与任何候选导入。
  `main()` 开头再调用一次（幂等），保证任何入口都不会出现"无守卫跑 pytest"。
- **模块导入不再安装钩子**：别名导入只拿到同一个注册表/同一份 gate/同一个 violation 类，
  **不产生第二个 gate，也就不会否决生产 entry 的准入**。
- 未移除任何安全钩子、未捕获吞掉任何违规、未泛化任何白名单；
  `BLOCKED_EVENTS` 原样保留，零网络/零任意子进程边界保持
  （`--mode guard` 自检四个事件仍全部被拒，见 §4 命令 3）。

### 2.2 执行器：Popen 返回句柄前的异常必有终态（对应要求 2）

- `executor.spawn()` 用 **thread-local token** 把 charge 与**同一线程**的操作系统动作绑定
  （审计事件在调用 start 的同一线程内抛出，绑定是精确的）。
- `spawn()` 现在捕获 `Popen` 抛出的一切异常，并按证据分两类结算，**绝不留下 PENDING**：
  - **`REFUSED_BEFORE_FORK`**（新增内部终态）：仅当异常携带**本执行器签发的 `CpuGateError`**
    且带 `lvw_before_fork` 标记时——即守卫在审计事件内拒绝，位置**可证在 fork 之前**，
    孩子**确未创建**。此时 charge 进入终态、**释放并发槽**、不释放预算。
  - **`UNKNOWN`**：其余一切 `Popen` 异常**可能有副作用**。charge 记为 `UNKNOWN`、
    **继续占槽**、会话转为 uncertain、**保留 owned root**，绝不"一律免费释放"。
- `reap()` 另外把**所有已准入但从未产生句柄**的 charge 结算为 `UNKNOWN` 并写进 proofs，
  作为 `ADMITTED_WITHOUT_HANDLE` 证据（这是旧收据漏掉的那一类）。
- **累计 starts 与历史 charge 绝不减少/退款/重置**：`SharedCounter.charge/finish` 未改，
  记录只被追加与结算，槽位释放只改**状态**不改计数。
- 原共享 counter 未被本轮触碰；两条旧 `PENDING` **未由本实现者补写**，其裁决留给 root。

### 2.3 收据：admitted_attempts 与 proven handles 分开（对应要求 3）

- 旧字段 `fixture_process_starts` **保留原值原义**（= 审计钩子准入次数），并新增
  `fixture_process_starts_semantics` 明确写出"不是创建/成功进程数"。
- 新增 `admitted_attempts`、`child_handles_obtained`、`proven_child_handles`、
  `charges_without_handle`（逐条含 `outcome`）、`admission_refusals{count,codes}`。
- `executor_session` 内新增同义账本：`admitted_attempts` / `child_handles_obtained` /
  `proven_child_handles` / `charges_without_handle` / `charge_ledger`。
- `finalize_session()` 新增 `UNSETTLED_CHARGE` 判定：**本会话仍有未结算 charge 时，
  `cleanup_proven=false` 且退出码非 0**，owned root 保留。**零孩子不再伪装 cleanup PASS。**

### 2.4 零进程负例（对应要求 4，全部落在真实调用链上）

`tools/test_v0_s3_supervisor.py` 新增 8 条用例（不是只测 helper 或常量存在）：

| 用例 | 证明的事实 |
|---|---|
| `test_the_module_alias_shares_the_one_guard_and_never_installs_a_second_hook` | 多次 import runner 不重复注册钩子；别名与生产 entry 共享同一 gate/registry/owner |
| `test_the_production_entry_owns_the_guard_and_the_alias_shares_its_owner` | **生产 entry** 安装守卫且 `hook_install_count == 1`；主/别名共享同一 owner（非 runner 进程内 skip） |
| `test_the_single_guard_admits_a_start_once_and_is_never_vetoed_twice` | 手工抛审计事件（零 fork）：守卫**只准入一次**、**不被第二钩子否决** |
| `test_the_offline_boundary_still_blocks_a_process_and_a_socket` | 进程负例与网络负例守卫**仍真实触发** |
| `test_a_refused_start_that_never_forked_is_settled_and_frees_its_slot` | fakePopen 模拟审计拒绝：charge=`REFUSED_BEFORE_FORK`、槽位释放、**失败后新合法准入不被错误 PENDING 卡住** |
| `test_an_unknown_start_keeps_its_charge_its_slot_and_the_root` | fakePopen 模拟未知异常：charge=`UNKNOWN`、**仍占槽**、会话 uncertain、根保留 |
| `test_the_finalizer_never_claims_a_proven_cleanup_with_an_open_charge` | 有未结算 charge 时 finalizer 不得宣称清理成功 |
| `test_the_machine_accounting_separates_the_admissions_from_the_created_handles` | 收据把"准入次数"与"实际获得/可证明的句柄"分成两个数字 |

## 3. 需要 root 审查的内部新增（不构成公共合同变更）

1. **新内部 charge 终态 `REFUSED_BEFORE_FORK`**（`executor.py`）：仅在"守卫在审计事件内拒绝、
   位置可证在 fork 之前、且拒绝由本执行器签发"时使用；该状态**不占并发槽**，
   charge 记录仍保留在 counter 中，starts 计数不变。
2. **新内部收据字段**：`admitted_attempts`、`child_handles_obtained`、`proven_child_handles`、
   `charges_without_handle`、`admission_refusals`、`fixture_process_starts_semantics`，
   以及 `executor_session` 内的 `charge_ledger` 等。
3. **新 finalizer 失败码**：`UNSETTLED_CHARGE`、`CHARGE_LEDGER_FAILED`。
4. 以上均为**执行器内部状态说明与收据字段**，未改 `s3-integration-offline-contract-01.md`
   或任何公共合同/门限/分母；**请 root 裁决其是否接受**。

## 4. 命令与真实退出码（本轮实际执行）

全部命令均在 worktree 根 `/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement`
下、包根 `LVW_Prompt_Service_MasterPack_v2.0.0` 内执行；**无一条命令带机器绑定**。

| # | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 1 | `python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py --mode suite --label audit-correction-targeted --modules tools/test_v0_s3_supervisor.py --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-01` | **0** | 92 收集 / **79 passed, 13 skipped**（13 = 机器门未开的 fixture 用例） |
| 2 | `python3 -B .../run_guarded_checks.py --mode focused --label audit-correction-focused --modules tools/test_v0_s3_supervisor.py --select "alias or production_entry or single_guard or offline_boundary or refused_start or unknown_start or finalizer_never or machine_accounting" --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-01` | **0** | **8 passed, 84 deselected**（本轮新增 8 条纠偏负例） |
| 3 | `python3 -B .../run_guarded_checks.py --mode guard --label audit-correction-guard --outdir reports/v0-s3/product-gate0/implementation-integration-audit-correction-01` | **0** | 四个越界事件（Popen/bind/connect/system）**全部被拒** |
| 4 | `python3 /tmp/lvw-audit-oracle/oracle.py <包根> <前置 runner>` | **0** | 缺陷复现 + 修正 oracle（§5） |
| 5 | `python3 -m pytest tools/test_v0_s3_supervisor.py -q -p no:cacheprovider --no-header -rN` | **0** | 78 passed, 14 skipped（裸 pytest，非生产入口，仅供比对） |

**未执行**（本轮明令禁止）：任何带 `--binding` 的 runner、任何真实 fixture 场景、
任何网络/模型/GPU/服务调用、任何对原 counter 的写、旧 71/257 整套重跑。

## 5. 问题复现与修复 oracle

`audit-correction-oracle.txt` 是**零进程**的可复现 oracle：它**手工抛出**
`sys.audit('subprocess.Popen', ...)`（解释器在 fork 之前抛的同一个事件），
因此**不创建任何操作系统子进程**，却能观察守卫链的完整行为。

对照结果（同一进程内先后加载，先修正后缺陷，以利用"钩子不可卸载"这一事实）：

| 观察 | 结果 |
|---|---|
| 修正后的别名导入后 `hook_install_count` | **1**（无第二钩子） |
| 修正后的别名与生产 entry 的 gate | **同一个对象** |
| 修正后的别名：`sys.audit('subprocess.Popen')` | 准入 **1** 次，**无否决** |
| 前置（763f3d5）别名与生产 entry 的 gate | **不同对象**（第二个 gate owner） |
| 前置别名：`sys.audit('subprocess.Popen')` | 准入 **1** 次后被 **第二个钩子否决**（`OfflineBoundaryViolation: offline boundary violation: subprocess.Popen ...`） |

前置一列**逐字复现了生产失败**：第一钩子已准入并 charge，第二钩子随后否决，
于是 charge 停在 PENDING、无句柄、并发槽被占死。这与
`finite-fixture-implementation-02.stdout.log` 第 50/98 行的异常类型与来源模块一致。

oracle 脚本全文见 `audit-correction-oracle.txt` 末尾（root 可原样重跑）。

## 6. 原始日志与证据清单（本目录）

| 文件 | 内容 |
|---|---|
| `audit-correction-targeted.stdout.log` / `.stderr.log` / `.receipt.json` | 命令 1 的原始 stdout/stderr 与机器收据（exit 0，92 收集，79 passed / 13 skipped，`hook_install_count=1`，`admitted_attempts=0`，`proven_child_handles=0`，`cleanup_proven=true`，`source_unchanged_during_run=true`，`owned_root_removed=true`） |
| `audit-correction-focused.stdout.log` / `.stderr.log` / `.receipt.json` | 命令 2 的原始 stdout/stderr 与机器收据（exit 0，8 passed / 84 deselected） |
| `audit-correction-guard.stdout.log` / `.stderr.log` / `.receipt.json` | 命令 3 的原始守卫自检输出与收据（exit 0，四个事件全拒） |
| `audit-correction-oracle.txt` | §5 oracle 的完整输出与其脚本全文 |
| `audit-correction-counter-readonly.txt` | 原共享 counter 的**只读**快照（`active=false` / `starts_total=2` / `reserved=120` / `spent=2.896` / 两条 PENDING 原样保留），证明本轮未写原账本 |

## 7. 预算、授权与环境（只读确认）

- **重试环境变量（只读确认，均为 0）**：`CLAUDE_CODE_MAX_RETRIES=0`、
  `CLAUDE_CODE_RETRY_WATCHDOG=0`。本轮**未发生 429**，未重试、未换供应商/账号/Harness，
  未由 Codex 接手；未请求任何审批，因此不存在"首次审批拒绝"。
- **root 建的临时设置未被本实现者修改**：
  `worktree/.claude/settings.local.json`（创建时 sha256
  `7e6320a52b689bfe6ff1441909c74d04f1a9620f75684d6d4bbff6508010c1b0`），
  结束由 root 按 hash 恢复。
- **原共享 counter 未被触碰**（§6 末行证据）：`active=false`、`starts_total=2`、
  `reserved=120`、`spent=2.896`、两条 `PENDING` 原样；剩余 60 秒池**未被本轮自动消耗**，
  是否继续释放由 root 独立裁决。
- 本轮**未派生任何 Agent**，全部改动由单一实现者完成。

## 8. 仍未证明项（本轮不能声称的结论）

1. **真实 fixture 进程行为未证明**：13 个机器门用例本轮全部 skip（无绑定），
   `test_the_fixture_clean_terminal_is_verified_by_the_parent` 等**仍需** root 的绑定与
   进程授权才能取证。**本报告不替代那一次真实运行。**
2. **旧的两个 PENDING charge 未被解决**：其裁决（结算为 `UNKNOWN` 还是别的终态）属 root；
   本实现者**不补写**原 counter，`REFUSED_BEFORE_FORK` 也**没有**被回填到那两条历史 charge。
3. **`REFUSED_BEFORE_FORK` 在真实链路中的可达性**：该终态由"守卫在审计事件内拒绝且拒绝
   由本执行器签发"触发。在单守卫架构下，真实链路的拒绝发生在 **charge 之前**（不产生 charge）；
   本轮已用 fakePopen 精确复现"已 charge 后被拒绝"的记账与清理分支，
   但**真实进程链路上该分支尚未被一次真实运行证明**。
4. **`install_attempts=7` 不等于多次安装**：生产 entry、`main()` 与 5 条用例共发起 7 次
   幂等安装请求，`hook_install_count` 恒为 **1**（收据 `guard` 段可查）。
5. **两套账本的一致性**：收据的 `admitted_attempts` 取自执行器账本，
   `fixture_process_starts` 取自门计数；真实绑定运行中二者应相等，本轮无绑定运行可证。
6. **Stage / Gate0 / 人签**：均未触及；本实现者只报 `READY_FOR_REVIEW`。

## 9. 交接

- 本实现者**只报 READY_FOR_REVIEW**，不签 Stage PASS、不签产品 Gate0。
- 请 root 独立裁决：修复候选、`REFUSED_BEFORE_FORK` 与新收据字段是否接受、
  两条遗留 PENDING charge 的处置、以及是否/何时释放剩余 60 秒池做那一次真实 fixture 运行。
- 本轮完成即归档并释放窗口，默认不 keep-open。
