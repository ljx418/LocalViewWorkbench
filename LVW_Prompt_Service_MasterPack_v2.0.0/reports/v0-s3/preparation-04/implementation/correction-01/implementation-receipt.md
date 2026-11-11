# S3-PREP-B correction-01 实施收据 — 安装所有权与回滚信任边界纠偏

- 纠偏合同：`reports/v0-s3/preparation-04/correction-01.task.md`（冻结，未改）
- 原 packet：`reports/v0-s3/preparation-04/stage-packet-preparation-b.md`（冻结，未改）
- 独审报告：`reports/v0-s3/preparation-04/independent-01/review.md`（只读，未改）
- 门禁裁决：`reports/v0-s3/preparation-04/codex-review-decision-01.json`（CHANGES_REQUIRED：F-01/F-02/M-01）
- 修复工具候选 commit：`ef8c065346a8f7d78b28b238207e7550444d897e`
- 状态：**READY_FOR_REVIEW**（不授予 Stage PASS，不授予产品 Gate0，不授予人签）

## 0. 范围与授权自检

| 项 | 值 |
|---|---|
| 真实媒体 / 宿主 / 模型 / GPU / 服务 / 网络 / 下载 | **0** |
| 产品 runtime 调用 | **0** |
| 产品完整 checkpoint 消耗 | **0** |
| 修改的工具文件 | `tools/v0_incremental_package.py`、`tools/test_v0_incremental_package.py`（仅此两个） |
| 新增目录 | `reports/v0-s3/preparation-04/implementation/correction-01/`（仅此一个） |
| 未触碰 | 业务代码、`contracts/`、`plans/`、`MANIFEST.sha256`、原 packet、独审证据、原 `implementation/` 证据 |
| 产品公共 API / schema | **未修改**（manifest schema 仍为 `lvw.v0-incremental-package-manifest/1`） |
| 本轮内部 schema | 收据 `lvw.v0-incremental-package-receipt/2`、所有权记录 `lvw.v0-incremental-package-ownership/1` |

**原始失败完整保留**：原 `implementation/`（25 文件）与 `independent-01/`（含全部 raw 失败证据）一字未改；
`review.md` 所述 F-01/F-02/M-01 的原始复现证据仍原样可查。本轮证据一律写在新的 `correction-01/` 下。

## 1. 纠偏合同逐条落实

### 1.1 原则 1 — 回滚先全量预检，第一项修改之后才有删除

实现位置：`tools/v0_incremental_package.py::command_rollback`、`_validate_owned_entries`、
`_validate_owned_directory_entries`、`_validate_relative_within_target`、`_validate_preimage_entries`、
`_assert_no_symlink_escape`。

* 外部收据的 `owned.files[] / owned.directories[] / owned.created_directories[] / preimage /
  staging / target / sandbox_parent / session_id` **一律不是删除授权**；只有**目标内所有权记录**
  所绑定的安装才被承认。
* 严格类型校验：owned 条目必须是对象列表；`install_path` 必须是 str；`sha256` 必须是 64 位小写
  hex；`length` 必须是非负 int（bool 被显式排除）；`owned.directories` /
  `owned.created_directories` / `preimage.files` / `preimage.directories` 必须是列表。
* 严格集合/唯一性校验：owned 文件集合内按 **Windows 归一化键**（去段尾随点与空格 + 小写）判重；
  目录集合同样判重。
* 路径必须为规范 POSIX 相对路径（`PurePosixPath(v).as_posix() == v`），且落在原 owned 安装前缀
  `custom_nodes/lvw_v0_bridge/` 或 `workflows/lvw/` 之内（目录条目落在 `custom_nodes` / `workflows` 之下）。
* 拒绝：`..`、`.`、空段、绝对路径、`//` UNC、盘符（`^[A-Za-z]:`）、反斜杠、尾随 `/`、
  Windows 段尾随点/空格、Windows 保留设备名（`CON`/`PRN`/`AUX`/`NUL`/`COM1-9`/`LPT1-9`）、
  非规范写法、Windows 归一化后的大小写/尾随点冲突。
* symlink / reparse 逃逸：逐段检查路径上没有任何 symlink 段，且 `resolve()` 后仍在 target 之内。
* **任一项拒绝时，目标整树、外部 victim、哨兵零写入零删除**：全部校验在任何 `unlink`/`rmdir`
  之前完成；实证见 `negative-probes.json` 的 N15/N16 与 pytest 的
  `test_every_tampered_receipt_path_field_is_rejected_with_zero_side_effects`、
  `test_F01_tampered_receipt_install_path_is_rejected_and_victim_survives`。

### 1.2 原则 2 — 目标内本轮所有权记录

新增：`OWNERSHIP_SCHEMA_VERSION = "lvw.v0-incremental-package-ownership/1"`，
记录文件名 `OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"`（写在 target 根）。

记录绑定字段：

| 字段 | 含义 |
|---|---|
| `target_identity` / `target_identity_sha256` | 规范化 target 绝对路径及其 sha256 |
| `sandbox_parent` / `sandbox_parent_sha256` | 沙箱父目录身份 |
| `sandbox_marker.sha256` | 沙箱 marker 文件身份（回滚时重新读取并复验） |
| `session_id` | `sess-` + 完整 uuid4 hex（32 hex，不可碰撞） |
| `source_commit` / `manifest_sha256` / `package_sha256` / `payload_fingerprint_sha256` | 源 candidate / manifest / 包 / 固定 payload 集合 |
| `owned.files / owned.directories / owned.created_directories` | 本轮 owned 集合 |
| `staging.path / staging.path_sha256` | 本轮自建暂存目录的绑定 |
| `install_hash` | 上述身份字段规范化 JSON 的 sha256（记录自身完整性） |

* 该记录**不是**外部收据的重复自述：它在安装事务内写进目标内部，回滚读取的是目标里的真实文件，
  再与外部收据、沙箱 marker **交叉核对**。判定所有权不靠 basename，也不靠“同样的文件 hash”。
* 记录自身路径/内容校验：`install_hash` 与内容不符即 `ROLLBACK_CONFLICT`；记录文件本身的 sha256
  与收据 `ownership.sha256` 不符也判不一致。
* 用户改写记录 → 拒绝（不覆盖用户文件）：`install` 时若记录路径已存在 → `CONFLICT` 且用户字节不变；
  回滚时记录被改写 → `ROLLBACK_CONFLICT`，owned 文件一个都不删。
* 同名不同 target/sandbox、session 不符、缺/错 marker、缺失/冲突所有权记录、被改 owned 清单
  → 全部非零（见 §3 负例 N3/N9/N12/N13/N14）。
* **脱敏收据仍可用显式 `--target`**：脱敏只影响收据里的路径字符串，身份由
  `target_identity_sha256` / `sandbox_parent_sha256` / `staging.path_sha256` 绑定，脱敏**不放宽**
  任何身份校验（负例 N17 证明脱敏收据仍能正常回滚；pytest 另证脱敏收据缺 `--target` 时稳定 `BAD_INPUT`）。

### 1.3 原则 3 — 不再以收据 staging 路径做递归删除

* `install` 在**同一事务内**清理本轮自建的暂存目录（`_remove_owned_staging`），清理前校验：
  目录名带 `.lvw-v0-stage-` 前缀、位于本轮沙箱父目录之内、不是 symlink；任一条不满足即**不删除**。
* `rollback` **不再**调用 `shutil.rmtree` 处理任何收据里的路径。它只确认本轮绑定的 staging 终态：
  记录里的 `staging.path_sha256` 与收据的必须一致、目录名必须是暂存前缀、必须位于记录的沙箱父目录
  之内；**若 staging 仍残留 → 稳定 `ROLLBACK_CONFLICT` 并保留诊断，不清理未知目录**。
* 安装失败的暂存清理同样只指向本次函数实际创建且身份已确认的目录；失败回退只删本轮 owned 项，
  不移除非 owned 内容（负例 N11 证明预置用户文件完好、owned 桥目录已回退）。

### 1.4 原则 4 — 所有权记录与安装同一事务边界

* `install` 的事务顺序：stage → 原子 rename commit → 安装后逐项 hash 复验 → 清理 staging →
  **写所有权记录（事务最后一步）**。
* 记录落盘失败 → 走与安装失败相同的回退路径（回退已 commit 的 owned 项、移除已写的记录、
  清理 staging）并以非零退出；因此**不存在「已安装但无法安全回滚」的无记录终态并报 OK**。
* 回滚安全移除所有权记录；用户新增的非 owned 内容保留（目录因含用户内容而保留并被报告，
  不算回滚失败）。
* 结构化终态只记录实际成功删除与实际剩余：失败时非零 + 稳定错误码；**不伪造**
  `staging_removed` / `sentinel_unchanged`：
  * `staging_removed` 只在实测 staging 确实不存在时为 true，并同时给出
    `staging_state: "absent_before_rollback"` 与 `staging_deleted_by_rollback: false`
    （明确表示回滚本身没有做任何递归删除）；
  * `sentinel_unchanged` 由 `preimage_drift` 实测推出（不是常量 true）；
  * `ownership_record.removed` 反映记录是否真的被删除。

### 1.5 同根因与低风险纠偏

* Windows 语义不再只 `lower()`：冲突检测改用 Windows 归一化键（去段尾随点/空格 + 小写）；
  路径解析时顺带拒绝段尾随点/空格与保留设备名（独审 m-01 已闭合：N8 现在 `PATH_REJECTED`）。
* 外部 `--manifest` 不可读 / 非法 JSON / 非对象 → 稳定 `BAD_INPUT`（不再落到 `INTERNAL_ERROR`）
  ——独审 m-03 已闭合。
* **旧执行器保留历史**：原 `implementation/run_offline_chain.py` 一字未改（它有 m-02 的失败路径
  泄漏，属历史事实，保留不覆盖）。
* **新增本轮 runner**（`implementation/correction-01/run_offline_chain.py`）用
  `try/finally` + 自有 `TemporaryDirectory` 覆盖**所有**失败路径：即使某一步 `raise`，`finally`
  也会清理本轮自建临时根并把清理实测写进 `chain-summary.json`
  （`temp_root_cleanup.removed = true`、`exists_after_cleanup = false`）。
* 只清理本轮自己创建、路径可证明的临时根：**不扫删 `/tmp` 前缀**，不删除任何未知目录，
  不删除独审失败证据。详见 §6 遗留项。

## 2. 公共 CLI 合同（本轮）

| 子命令 | 参数 | 状态码 |
|---|---|---|
| `build` | `--repo --commit --out [--receipt-out] [--redact-root ...]` | 0 / 非零 |
| `diagnose` | `--package [--manifest] [--target] [--sandbox-parent] [--receipt-out] [--redact-root ...]` | 0 / 非零 |
| `install` | `--package --sandbox-parent --target [--manifest] [--session-id] [--receipt-out] [--redact-root ...]` | 0 / 非零 |
| `rollback` | `--receipt [--target] [--receipt-out] [--redact-root ...]` | 0 / 非零 |

稳定错误码与退出码（**未新增、未改动**）：`OK=0`、`BAD_INPUT=2`、`INTEGRITY_MISMATCH=3`、
`PATH_REJECTED=4`、`SIZE_LIMIT=5`、`CONFLICT=6`、`INSTALL_FAILED=7`、`ROLLBACK_CONFLICT=8`、
`INTERNAL_ERROR=9`。

本轮新增的**拒绝路径**及其错误码：

| 情形 | 错误码 |
|---|---|
| 收据里的 owned 路径非法（穿越/绝对/盘符/反斜杠/非 owned 前缀/Windows 非法名/集合冲突） | `PATH_REJECTED` (4) |
| 收据 preimage 路径非法 | `PATH_REJECTED` (4) |
| 所有权记录缺失 / 被改写 / install_hash 不符 / 文件 sha256 与收据不符 | `ROLLBACK_CONFLICT` (8) |
| 收据与所有权记录交叉核对不一致（owned 清单、source_commit、manifest/包 hash、target/sandbox/marker 身份、session） | `ROLLBACK_CONFLICT` (8) |
| 沙箱 marker 缺失 / 身份不符 | `ROLLBACK_CONFLICT` (8) |
| 本轮 staging 仍有残留 | `ROLLBACK_CONFLICT` (8) |
| 脱敏收据缺 `--target`、收据不可读/非法 JSON/无 session | `BAD_INPUT` (2) |
| 所有权记录路径已被用户文件占用 | `CONFLICT` (6) |

工具版本 `1.0.0 → 1.1.0`；收据 schema `/1 → /2`；新增所有权记录 schema `/1`。

## 3. 测试与负例

### 3.1 定向测试（公共 CLI）

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -m pytest \
  tools/test_v0_incremental_package.py -p no:cacheprovider \
  --basetemp=<自有临时目录> -v
→ 70 passed，exit 0
```

原始证据：`raw/05-pytest.stdout.log`（退出码 `raw/05-pytest.exit.log`）。

* 原 38 项功能覆盖**全部保留、无删除、无 skip、无恒通过改写**。
* 新增 32 项公共 CLI 回归，全部针对本轮纠偏：
  * F-01：`test_F01_tampered_receipt_install_path_is_rejected_and_victim_survives`、
    `test_F01_rejected_rollback_leaves_the_install_rollback_capable`
    （拒绝后状态未破坏，改回合法收据仍可正常回滚）。
  * F-02：`test_F02_tampered_receipt_staging_path_is_rejected_and_victim_dir_survives`。
  * M-01：`test_M01_cross_sandbox_same_basename_rollback_is_rejected`、
    `test_rollback_on_a_target_without_an_install_is_rejected`。
  * 所有权记录：`test_install_writes_ownership_record_and_rollback_removes_it`、
    `test_rollback_rejects_a_missing_ownership_record`、
    `test_rollback_rejects_a_tampered_ownership_record`、
    `test_rollback_rejects_an_ownership_record_with_a_rewritten_owned_list`、
    `test_install_refuses_to_overwrite_an_existing_ownership_record_file`、
    `test_failed_install_leaves_no_ownership_record`、
    `test_rollback_rejects_a_residual_staging_directory_without_deleting_it`。
  * 收据全部路径字段：`test_every_tampered_receipt_path_field_is_rejected_with_zero_side_effects`
    （11 个参数化突变：owned install_path 的穿越/绝对/盘符/反斜杠/越前缀、owned directories、
    created directories、preimage path、staging path、target、session）。
  * 脱敏：`test_rollback_works_with_a_redacted_receipt_and_an_explicit_target`、
    `test_redacted_receipt_without_target_is_rejected`。
  * 同根因低风险：`test_windows_trailing_dot_space_and_reserved_names_are_rejected`（4 个参数化）、
    `test_windows_trailing_dot_collision_with_an_existing_member_is_rejected`、
    `test_unreadable_external_manifest_is_rejected_as_bad_input`。
* **新 oracle 记录**：安装成功后目标内新增一份所有权记录（`test_install_writes_ownership_record_and_rollback_removes_it`），
  回滚后该记录被安全移除、目标树回到只剩哨兵与原有用户文件。原链路的哨兵不变与实际删除证明
  （`removed_files` 29 项、`removed_directories` 5 项）全部保留。

### 3.2 独立负例（沿用独审脚本的适配副本 + 本轮追加）

脚本：`implementation/correction-01/probe/negative_probes.py`
（**复制适配**自 `independent-01/probe/negative_probes.py`，历史证据未改）。
结果：**17/17 全部符合期望**，原始 stdout/stderr/退出码在 `raw/probes/`。

| 探针 | 期望 | 实际 | 结论 |
|---|---|---|---|
| N1 收据 install_path 路径穿越 | victim 不得被删 | victim 仍在 | 通过（F-01 已闭合） |
| N2 收据 staging.path 任意 rmtree | 目录不得被删 | 目录完整保留 | 通过（F-02 已闭合） |
| N3 同名不同沙箱跨目标回滚 | 另一沙箱 owned 文件删除数 = 0 | `b_installed_files_removed=0` | 通过（M-01 已闭合） |
| N4 zip bomb 谎报 file_size | 非零拒绝 | exit 3 `INTEGRITY_MISMATCH` | 通过 |
| N5 已有非 owned 冲突 | 非零 + 0 写入 | exit 6 `CONFLICT`，树不变 | 通过 |
| N6 诊断失败 | target 零写入 | exit 3，target 未写 | 通过 |
| N7 脏工作树 | 仍读 commit 字节 | payload = commit blob ≠ 脏文件 | 通过 |
| N8 Windows 尾随点/空格归一化冲突 | 必须拒绝 | exit 4 `PATH_REJECTED` | 通过（m-01 已闭合） |
| N9 父目录 symlink 逃逸 | 拒绝且 0 写入 | exit 4，外部目录为空 | 通过 |
| N10 用户改写 owned 文件后回滚 | 拒绝且字节不变 | exit 8，字节未变 | 通过 |
| N11 安装中途失败 | 精确回退 | exit 7，预置文件完好、owned 已回退 | 通过 |
| N12 所有权记录缺失 | 非零且 owned 一个不删 | exit 8，29/29 保留 | 通过（本轮新增） |
| N13 所有权记录被改写 | 非零且整树不变 | exit 8，整树不变 | 通过（本轮新增） |
| N14 session 不符 | 非零且整树不变 | exit 8，整树不变 | 通过（本轮新增） |
| N15 收据全部字段被篡改 | 逐项非零 + 整树不变 + victim 不变 | `all_rejected=True all_unchanged=True` | 通过（本轮新增） |
| N16 预检失败 | 零写入零删除 | exit 4，整树不变、victim 不变 | 通过（本轮新增） |
| N17 脱敏收据 + 显式 `--target` | 仍可正常回滚 | exit 0，回滚后只剩哨兵 | 通过（本轮新增） |

## 4. 一次真实离线包链路（绑定修复候选 `ef8c0653…`）

执行器：`implementation/correction-01/run_offline_chain.py`（try/finally + 自有临时根）
证据：`build-receipt.json`、`diagnose-receipt.json`、`install-receipt.json`、`rollback-receipt.json`、
`package-manifest.json`、`chain-summary.json`、`raw/01..04-*.{command,stdout,stderr,exit}.log`。

| 步骤 | 命令（脱敏） | 退出码 |
|---|---|---|
| 1 | `python3 <tools/v0_incremental_package.py> build --repo <repo-root> --commit ef8c065346a8f7d78b28b238207e7550444d897e --out <work-dir>/LVW_V0 增量包.zip --receipt-out … --redact-root <work-dir> --redact-root <repo-root>` | 0 |
| 2 | `… diagnose --package <work-dir>/LVW_V0 增量包.zip --target <work-dir>/隔离 沙箱根/隔离 目标 目录 --sandbox-parent <work-dir>/隔离 沙箱根 …` | 0 |
| 3 | `… install --package … --sandbox-parent … --target … --receipt-out …` | 0 |
| 4 | `… rollback --receipt … --target … --receipt-out …` | 0 |

### 4.1 候选与可复算量

| 量 | 值 |
|---|---|
| 候选 commit（解析后） | `ef8c065346a8f7d78b28b238207e7550444d897e` |
| 工具 sha256（工作树 == 候选 blob） | `b383d2e9292ada578cc8b90b9bcea8b15ce8c49cb439c0ccec6abcc65d899931` |
| 包内工具副本 sha256 | `b383d2e9292ada578cc8b90b9bcea8b15ce8c49cb439c0ccec6abcc65d899931`（== 候选 blob） |
| manifest `source_commit` | `ef8c065346a8f7d78b28b238207e7550444d897e` |
| 包 sha256 | `2c74a8d0c91cb078bd3e5f8f258359e0f0352914aa8966f40f88ad97a33cf898` |
| 包大小 | 98983 字节 |
| 成员数 | 32（29 payload + 3 meta） |
| payload 条目数 / 展开字节 | 29 / 183540 |
| manifest sha256 | `173568308385c260ab01c0c2287c632414dee7154b0706a1d9271b67b2efb589` |
| 固定集合 fingerprint | `c37d797e27bdfd6e559ac5ddffa30ed39c52dfc24e29db2a95eb93b562db3509`（与原链路**一致**：payload 未变） |

> 包 sha256 与原链路不同是预期的：包内携带的是**新候选**的工具副本与新 manifest。
> 旧证据（`implementation/`、`independent-01/`）仍绑定旧 SHA，未被改绑。

### 4.2 预先固定的哈希与回滚后复核

| 对象 | 固定前 sha256 | 回滚后 sha256 | 结论 |
|---|---|---|---|
| 哨兵 `哨兵 文件.txt` | `403252aaeacc926cc64bddc9ddce43085c8a1d88e114758e2297760f1d0f239a` | 同上 | 未变 |
| 非 owned 内容 `用户 原有 文件.txt` | `86a435d765f27e79c2e04f6e6f404f75d92033a7e09d373864822145e7c4e5a1` | 同上 | 未变 |
| 外部 victim `外部 victim.txt`（在 target 与沙箱之外） | `f6e7143a399cb789f96a9c46669b6847aaaf219ae272412bdcd4f040f97a48cd` | 同上 | 未动 |

`fixed_hashes_unchanged = true`；`preimage_drift = []`；`sentinel_unchanged = true`。

### 4.3 本轮本地所有权生命周期

| 阶段 | 事实 |
|---|---|
| 安装后 | 目标内存在 `.lvw_v0_incremental_ownership.json`；`install_hash = 228def3580608a30fe239958e1317d737677e5c22166e391b549994730ff3df7`；记录文件 sha256 `a797265cef275b16819c1738f62713da10dc26ac58430328ba30ec0db964a3e4`（与收据 `ownership.sha256` 一致）；`session_id = sess-931891cfbcb647ac89d20bb76d360d48` |
| 安装后暂存残留 | `[]`（install 事务内已清理自有 staging） |
| 回滚后 | 记录已安全移除（`ownership_record.removed = true`）；`present_after_rollback = false` |
| 回滚后暂存残留 | `[]`；`staging_state = "absent_before_rollback"`、`staging_deleted_by_rollback = false`（回滚未做任何递归删除） |
| 回滚删除 | `removed_files` 29 项；`removed_directories` 5 项（`custom_nodes/lvw_v0_bridge/web`、`workflows/lvw`、`custom_nodes/lvw_v0_bridge`、`workflows`、`custom_nodes`） |
| 回滚后目标内剩余 | 仅 `哨兵 文件.txt`、`用户 原有 文件.txt`（用户原有内容保留） |

### 4.4 临时清理实测

| 项 | 结果 |
|---|---|
| 本轮链路临时根（`lvw-corr01-离线包链路 *`） | `existed_before_cleanup=true` → `removed=true` → `exists_after_cleanup=false` |
| 链路包 ZIP 与临时副本 | 随临时根一并删除，**未提交 Git**（本目录只有 JSON/日志，无 ZIP、无源码副本） |
| 本轮 pytest `--basetemp` 目录（6 个精确路径） | 已逐个删除并复检不存在 |
| 独立负例探针临时根 | `temp_root_removed_after_run=true`（`TemporaryDirectory` 退出即删） |
| 本轮 `/tmp` 残留 | 复扫 `lvw-corr01-*`：**0** |

## 5. 失败保留与未改动的历史

* 独审 F-01/F-02/M-01 的原始复现脚本、原始 stdout/stderr/退出码：仍在
  `independent-01/raw/probes/`，**未改、未删**。
* 原实现的链路执行器 `implementation/run_offline_chain.py`（含 m-02 的失败路径泄漏）**保持原样**，
  作为历史事实保留；本轮另起 `correction-01/run_offline_chain.py` 修正该模式。
* 原 `implementation/` 的 25 个文件与 `independent-01/` 的全部文件**一字未改**。
* `MANIFEST.sha256`、`plans/`、`contracts/`、业务代码**未改**。

## 6. 遗留项与限制（如实记录）

### 6.1 原实现遗留的宿主临时根（本轮**未删除**，记为限制）

独审 m-02 记录了原实现失败路径在宿主 `/tmp` 上的残留。本轮按合同
「仅核实由本实现者此前创建**且能以记录证明**的精确临时根，才清理；不扫删 `/tmp` 前缀或未知目录，
不能删除审查失败证据」处理，逐项核实如下：

| 精确路径 | 记录证明 | 内容 | 本轮处置 |
|---|---|---|---|
| `/tmp/lvw smoke 沙箱.McucN0` | 有：`/tmp/lvw_smoke_sb.txt` 内 `SANDBOX=/tmp/lvw smoke 沙箱.McucN0` | 14 文件 / 1 目录 / 174518 字节（含原实现 smoke 的 pkg.zip、各步收据与 stdout） | **不删**：该目录是独审 m-02 直接引用的原始残留证据，按「不能删除审查失败证据」保留 |
| `/tmp/lvw smoke 沙箱.tj7KZA` | 无记录 | 4 文件 / 1 目录 / 714 字节 | **不删**：无记录可证明所有权，禁止前缀扫删 |
| `/tmp/lvw 离线包链路 15ar1jkf` | 无记录 | 空目录 | **不删**：同上 |
| `/tmp/lvw 离线包链路 iupsl92p` | 无记录 | 空目录 | **不删**：同上 |
| `/tmp/lvw 离线包链路 qcjychxp` | 无记录 | 空目录 | **不删**：同上 |

按合同「无法证明所有权的遗留目录记限制即可，不阻止本轮代码安全修复」，此项**只记限制**，
不阻塞本轮纠偏；本轮代码修复与证据交付不依赖对其做任何删除。

### 6.2 本轮修复的边界（如实声明）

* 所有权记录是**局部持久记录**，用于防「外部收据被替换 / 重绑到别的 target 或 sandbox」。
  它**不是**密钥服务或平台级防篡改：能对本机目标目录有写权限的同权限行为者，可以同时改写
  记录并重算 `install_hash`。合同明确不要求对此作不现实承诺，本轮也不作此承诺。
* 判定所有权时同时使用「规范化 target 身份 + 沙箱 marker 身份 + 不可碰撞 session +
  源 candidate/manifest/payload 集合 + 安装 hash + owned 清单逐项 hash 复验」，
  **不使用 basename 判定**，也不使用「同样的文件 hash」单独判定。
* 全部验证仍在 POSIX（WSL2）沙箱内完成：**没有**真实 Windows 宿主、ComfyUI 启动、Ollama、
  GPU、模型、媒体、网络或下载。Windows 路径语义只作为 ZIP/路径内容问题在 POSIX 上探测。
* 本轮**不授予** S3 产品 Gate0、Stage PASS 或人签；实现者只报告 READY_FOR_REVIEW。

## 7. 结论

F-01、F-02、M-01 三项阻断已在公共 CLI 层闭合并由独立负例复算；m-01、m-03 两项低风险纠偏
同轮闭合。原始失败证据完整保留，一次真实离线包链路从修复候选 `ef8c065346a8f7d78b28b238207e7550444d897e`
重新跑通，哨兵/非 owned 内容/外部 victim 三方哈希均未变，临时清理实测通过。

**状态：READY_FOR_REVIEW。**

作者：`ljx418 <1173696783@qq.com>`
