# S3-P4-OFFLINE 集成批次 A/B/C 实现报告

状态：`READY_FOR_REVIEW`（实现者自检）。**不是** Stage PASS，**不是** 产品 Gate0，
**不是** 人工签署。本包所有输出都带 `stage_pass_claim = false` 与
`product_gate0 = false`。

合同：`reports/v0-s3/product-gate0/s3-integration-offline-contract-01.md`
（已冻结的内部实现合同）。承接已接受的 P3B 组件
`6c9a0a07c66060e53b00e690ebdd98047167511d` / 证据 `833c8476f03ef96983cbc84871a8ea24fb42449e` /
独审 `eda30de5655e6262061ce658aeb33044f0a068e9`。

## 1. 根处置合并

`ROOT_DISPOSITION_COMMIT = c92e0bf` 已用 `git merge c92e0bf --no-edit` 合并进本实现
worktree（快进，合并基点为 `833c847`）。合并前后无关状态保持不变：工作树只多出
处置提交自带的冻结合同/验收/绑定文档，本批次没有改写其中任何一份。

## 2. 变更路径（只限允许清单）

| 路径 | 变更 | 性质 |
|---|---|---|
| `tools/v0_s2_stage_runtime.py` | 新增私有钩子 `_profile_binding_parameters(*, root, label, baseline)`（默认返回空字典）与 `_write_profile_binding(driver, root, label, baseline)`；`_prepare` 的首次排他 profile 写入改为调用后者 | 窄改动。S2 既有调用参数与 profile 字节完全不变 |
| `tools/v0_s2_runtime.py` | 新增 `bind_video_snapshot_root(run_root)` 与只读 `video_snapshot_residue()`，以及 `os`/`stat` 导入与四个绑定状态字段 | 窄改动。既有方法未改 |
| `tools/v0_s3_coordinator.py` | **新增**：`S3BudgetBindingProvider`、`S3InstalledRuntimeFactory`（继承已接受的 `InstalledPackageRuntimeFactory`）、`ParentOriginalEvidence`、`aggregate_twelve_keys` | 新文件 |
| `tools/v0_s3_supervisor.py` | **新增**：协议编解码、`SealedPlan`、`ProtocolState`、`ParentSupervisor`、`RecoveryEntry`、冻结命令计划 | 新文件 |
| `tools/v0_s3_quality_worker.py` | **新增**：固定生产 worker 入口，实际调用已接受的 `QualityPhase`，说父协议 | 新文件 |
| `tools/fixtures/v0_s3_supervisor_fixture.py` | **新增**：13 个枚举场景的 fixture 入口，导入前自装零网络/零后代进程守卫 | 新文件 |
| `tools/test_v0_s3_integration.py` | **新增**：A 段与 C 段的离线义务测试 | 新文件 |
| `tools/test_v0_s3_supervisor.py` | **新增**：B 段的协议/截止/父持有句柄/worker/恢复测试，以及机器门未开时被跳过的 13 个 fixture 进程用例 | 新文件 |
| `tools/v0_s3_quality_phase.py` | 仅新增**默认关闭**的 `progress_sink` 与三个插入点（`ROW_STARTED`、`HISTORY_WAIT_STARTED`、`ROW_FINISHED`、`PROGRESS`） | 可选 hook，默认关闭；验证/评分/阈值/保留上限/原始证据未改 |
| `reports/v0-s3/product-gate0/implementation-integration-01/` | **新增**：新的受控 runner、义务映射、机器绑定提案、本报告与收据 | 新子树 |

未改动：旧 productowner/contract/quality/projection/prelabel/prompt/workflow/authority/
ledger/P1/P2B/P3A 实现、旧报告、旧 runner、旧 manifest、坐标、V2。
`tools/v0_s3_stage_runtime.py` 的 `InstalledPackageRuntimeFactory` 被**继承**，没有改动、
没有替换、没有复制成 source-copy 工厂。

## 3. A 段：首次 profile 接线

生产调用路径：

```
S3InstalledRuntimeFactory._profile_binding_parameters(root, label, baseline)
  -> S3BudgetBindingProvider.parameters(...)          # 只返回 {'s3_budget_binding': ...}
     -> program_budget.load_binding(ref)               # 已接受的 loader
     -> program_budget.validate_config(binding)        # 已接受的 validator
     -> _check_identity(): run / candidate / child / model / authority root /
        ledger identity / tool digest / execution binding / protocol source / expiry
  -> StageRuntimeFactory._write_profile_binding(...)   # 钩子在写之前解析
  -> NativeRuntime.write_native_binding / write_warm_binding   # 已接受的生产写入器
     -> program_budget.s3_profile(value, binding)       # 已接受的封存
     -> 排他创建 temp/lvw-native-profile.json | temp/lvw-warm-profile.json
```

* 绑定出现在**第一次且唯一一次**排他写入里。没有先写 LOCAL01 再覆盖：写入器用
  `open('x')` 排他创建，第二次写入必然失败。
* 缺失或错 run/candidate/child/model/authority/ledger/tool/expiry 一律在**首个模型发送前**
  拒绝（provider 在 profile 写入之前抛错，因此 profile 文件根本不会产生）。
* 真实账本本包**未访问**：provider 只读封存的绑定文档与其 execution 绑定，不打开
  `ledger_path`。真正的扣账 owner 仍是既有 authority；形状检查不替代真实原账本验证。
* 默认 S2 行为不变：默认钩子返回空字典，既有 S2 调用的参数集与 profile 字节完全一致。

实际生产路径测试使用**显式 fake runtime 接缝**：只替换操作系统相关的原语
（listener birth、native clock、服务启动、registry 读取、sampler、resource observer）、
受保护部署、公开引用准备与 Comfy CLI 身份检查（这三项各自需要 Windows 主机进程或
包安装）。**生产 profile 写入器、残存 accessor 与全部校验都是真实现**，不是 fake。

## 4. B 段：父监督

* 协议：UTF-8 JSONL，schema `lvw.s3-supervision/1`，闭合键
  `schema/run_id/candidate_sha/authorization_sha256/sequence/event/payload`；
  事件仅 `STARTED / ROW_STARTED / HISTORY_WAIT_STARTED / ROW_FINISHED / PROGRESS / TERMINAL`。
* 拒绝规则稳定：额外/缺失键、错 schema、未知事件、重复 JSON 键、非有限数、
  序列不严格递增、身份不符、行不在封存计划内、同行重复 history 开始、终态引用形状
  不合法、超长消息、消息数超限——每条都有独立机器可读 code。
* 截止：phase 自父启动起固定 10800s；history 自该行**首次** `HISTORY_WAIT_STARTED` 起
  固定 600s；两者都取 child 剩余期限（最大 21600s）的更早值；超限不延长。
* 父持有原始 Popen 句柄与出生身份（从自己创建的句柄读取，绝不采用 worker 自报 PID）。
  父循环只做非阻塞读取与状态推进，不执行 worker 传来的回调，也不跑同步 child observer；
  读取线程只读字节，不写、不回调。
* 违规/超时/失联后：撤销后续动作 → 关闭标准输入请求协作取消 → 冻结宽限后只终止
  **自己持有的** worker 句柄 → 记录真实退出。原生服务/GPU 清理由原 owner 另证，
  本包显式记 `native_cleanup_proven = false`。
* 未知结局保留原根与预约：不归档、不退款、不重发、不继续下一 phase。
* 父原件证据：父在 worker 发送前封存 run/candidate/child、16 行计划、投影摘要与根
  身份；终态后父**自己**读取选中根内的 canonical receipt / source-plan / raw 的真实
  长度与 hash。worker 改内存返回值无法替代该清单。
* 恢复入口只协调清理与已有证据：不重放推理、不重发、不按磁盘自报 PID 杀进程；
  没有原 custody 证据时保持 `BLOCKED`。
* worker 入口 `tools/v0_s3_quality_worker.py` **真的**构造并运行已接受的
  `QualityPhase`（不是重复的 fake QualityPhase，也不是通用序列化回调），
  只重建已绑定的数据上下文（路径/摘要/闭合枚举），不接受任何 Python callback。

## 5. C 段：残留与十二项汇总

* `bind_video_snapshot_root(run_root)` 要求根等于工厂 evidence 的 `owned_run_root`，
  以 `O_DIRECTORY|O_NOFOLLOW` 打开根与 `temp` 并钉住对象身份；绑定只发生一次。
* `video_snapshot_residue()` 只读、只枚举该 temp 第一层的 `lvw-video-*`，不跟随链接、
  不读外部内容、不删除任何文件；每次最多观察 512 个第一层条目、最多 256 个残留名。
  未绑定、缺根、根被替换、匹配项是符号链接/reparse、I/O 失败、超限一律是显式异常，
  **绝不返回假空**。空与清理后为空分别留证。
* 十二项汇总固定 `V0-A01…A12` 十二键。缺必需收据 → `NOT_RUN`；收据失败 → `FAIL`；
  独立质量分 / 真实 A06 隔离 / 清理证明缺失 → `BLOCKED`；只有完整且身份匹配的通过
  收据才是 `PASS`。旧 S2 九项的 phase 收据 kind 不同，**不能**补绿；旧 45+20 发送
  不当作新十二项 PASS 或总账。

## 6. 本地实际检查、真退出与失败记录

全部执行都经**新受控 runner**
`reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py`：
审计守卫在 pytest / 插件 / 任何产品或测试导入**之前**安装，禁用插件自动加载、
禁用 cacheprovider、禁字节码；原始 stdout/stderr 在 fd 层捕获，真退出码写在其旁。

| 运行 | 标签 | 真退出 | 结果 |
|---|---|---|---|
| 守卫自检（不启动任何进程） | `final-guard` | 0 | 4/4 事件被阻断（connect/bind/Popen/system） |
| 本批次集成套件 | `final-integration-suite` | 0 | **71 passed, 13 skipped**（13 个为待机器门放行的 fixture 进程用例） |
| 已接受 P3B 质量相位套件（必要定向回归） | `regression-p3b-quality-phase` | 0 | **257 passed** |
| 机器门负例（候选自己的提案不得开门） | `gate-negative-proposal` | 1 | runner 拒绝提案：`machine binding is not a sealed root binding` |

中间失败记录（按合同保留原始日志，不重写历史）：

| 标签 | 真退出 | 失败内容 | 处理 |
|---|---|---|---|
| `integration-suite`（第 1 轮） | 1 | 13 failed / 58 passed：warm 顺序规则、provider 参数名、残留目录层级写错、canonical 字节数断言、foreign original 的 OSError 泄漏、被替换根 inode 复用、协议序列号未递增、reader 竞态 | 逐条定位并修正实现或测试 |
| `integration-suite`（第 2 轮） | 1 | 2 failed / 69 passed：warm 顺序规则读反（需要默认根已关闭）、终态引用逃逸未捕获 | 改为经归档 owner 关闭默认根；`_derive_row_status` 捕获 `SupervisionError` |
| `integration-suite`（第 3 轮） | 1 | 1 failed / 70 passed：终态引用逃逸在派生行状态时未捕获 | 同上 |
| `final-integration-suite` | 0 | 71 passed / 13 skipped | 最终一次 |
| `regression-install-handoff` | 1 | 55 errors：该已接受套件需要 `git init` 主机进程，在零进程守卫下不可运行 | 保留为已知未运行的必要回归，不在本批次绕过 |

`tools/test_s3_install_handoff.py`（覆盖被改动的继承 `_prepare`）需要 `git init`
主机进程，超出零进程授权范围，**保持 NOT_RUN**，本包不以任何替代方式声称其通过。

## 7. 生产调用路径清单

* A：`tools/v0_s3_coordinator.py::S3InstalledRuntimeFactory._profile_binding_parameters`
  → `S3BudgetBindingProvider.parameters` → `program_budget.load_binding` /
  `validate_config` → `StageRuntimeFactory._write_profile_binding` →
  `NativeRuntime.write_native_binding|write_warm_binding` → `program_budget.s3_profile`。
* B：`tools/v0_s3_supervisor.py::ParentSupervisor.run` → `ParentSupervisor._spawn`
  （固定 worker 命令）→ `ProtocolState.accept` → `_terminate_owned_worker` →
  `_verify_terminal_receipt` → `_derive_row_status`；子进程侧
  `tools/v0_s3_quality_worker.py::run_worker` → `QualityPhase.run`。
* C：`tools/v0_s2_runtime.py::NativeRuntime.bind_video_snapshot_root` /
  `video_snapshot_residue`；`tools/v0_s3_coordinator.py::ParentOriginalEvidence` /
  `aggregate_twelve_keys`。

## 8. 24 项内部义务映射

完整映射见 `reports/v0-s3/product-gate0/implementation-integration-01/obligation-mapping.json`。
汇总：PASS 19 项，PARTIAL_BLOCKED_MACHINE_GATE 5 项（I08、I09、I10、I12、I13、I24 中
零进程部分已证、真实进程部分待门），无一项用常量、名称存在或 exit0 独立充数。
这些义务**不替换**产品十二项，也不替换旧门禁。

## 9. 有界 CPU 计数与清理

* 本批次实际启动的 fixture 进程数：**0**。已执行的总墙钟全部是零进程守卫下的
  单元/集成执行。
* 守卫计数：每个收据都记录 `fixture_process_starts` 与 `fixture_process_limit`；
  `final-integration-suite` 为 `starts = 0`、`binding = false`。
* runner 自有临时根每次运行后删除（收据 `owned_root_removed = true`）。
* 待门放行的部分：总计 24 次 fixture 启动上限（实现 ≤16、独审 ≤8）、并发 ≤2、
  每次 ≤10s、含进程验证累计墙钟 ≤180s、最后 30s 只清理；输出 256KiB/stream、
  消息 32KiB、消息数 1024、新增文本证据 ≤8MiB。**预算不重置。**

## 10. 机器门（尚未开启）

当前权限只允许源编辑与**零 subprocess/网络**的守卫测试。fixture 进程放行**尚未**绑定。
本包提交的是**提案**，不是授权：

`reports/v0-s3/product-gate0/implementation-integration-01/machine-binding-proposal.json`
（`kind = S3_INTEGRATION_MACHINE_BINDING_PROPOSAL/1`，`execution_permitted = false`）。

受控 runner 只接受 `kind = S3_INTEGRATION_MACHINE_BINDING/1` 且
`execution_permitted = true` 的根封存文档；提案会被 runner 拒绝。候选自带的
宽松 subprocess monkeypatch 不构成可信白名单：白名单只来自根绑定，argv 必须
精确等于冻结前缀 + 一个枚举场景，计数受共享预算约束。

## 11. 未闭合的集成风险（明确保留）

* 真实 A06 隔离（网络隔离后端与尝试观测）——未证明。
* Windows 原生服务后代与 GPU 物理释放——未证明，本包显式 `native_cleanup_proven = false`。
* 注册表驱动的安装前基线与回滚后基线——未证明；安装/回滚收据由聚合器登记，缺一即
  `NOT_RUN`/`BLOCKED`。
* 原账本真实扣账——未证明；本包不访问原账本。
* 最终 A/B 预算与新鲜真实十二项/质量分——未证明。
* 产品 Gate0 与人工发布签署——未做，`stage_pass_claim = false`。
* 真实父崩溃看护、原生 custody 交接、归档后逻辑根迁移——按合同保持 `BLOCKED`，
  不用 Linux fixture 冒充实现保证。
* 父硬看护标志不得在原生清理证明之前或超出已证 Linux 范围提升。

## 12. 结论

实现者自检完成，状态 `READY_FOR_REVIEW`。本包不宣布 Stage PASS、不宣布产品 Gate0、
不宣布人工签署。真实 fixture 进程证据等待 root 在既有 COMPLETE03 授权内签有限机器
绑定。
