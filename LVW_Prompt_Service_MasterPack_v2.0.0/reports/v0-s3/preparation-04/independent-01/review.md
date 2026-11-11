# S3-PREP-B 离线增量包工具 — 独立审查（independent-01）

- 审查对象：`tools/v0_incremental_package.py` + `tools/test_v0_incremental_package.py`
- root 基准：`2db2fa81e34479e08ea33df7c90a179d1fd99936`
- 工具候选：`1c09cd651478beeb4c1bca026505364051a72892`
- 完整实现收据 tip：`0c96999d9403fc445a8a1b672801cb05f91d6d9b`
- 审查分支：`ljx418/lvw-v1-d0-review`
- 规格 hash：`stage-packet-preparation-b.md` = `cd7076463467ae6545ac86de633a2100ad357f2d2ab5946bf490ddaba2588abd`
- 工具 sha256：`f96e3c064d0e0dee2cbaeeb63b1df39738c3d560020c27f7890e97d820f5eab9`（= 候选 commit 中的 blob `7f50c98a…`，工作树字节与候选 commit 逐字节一致）
- 测试文件 sha256：`047344757e02b17ceccdb9072769db5475ff3ccf6aeff171b890a8080fd5c8eb`（blob `4a6f31da…`）
- 运行环境：Linux 6.18.40.1-microsoft-standard-WSL2 x86_64 / Python 3.12.3 / pytest 8.4.2 / git 2.43.0
- 产品 runtime 调用：0；网络/GPU/模型/媒体/真实宿主配置：未使用；未下载

## 0. 结论

**建议 `CHANGES_REQUIRED`（仅为建议，门禁结论由 root / Codex 裁决）。**

本审查**不授予** S3 产品 Gate0、Stage PASS、人签或发布；也不声称真实 Windows 宿主安装已验证。

发现 **2 个 Fatal、1 个 Major、3 个 Minor**，全部为**可复现**问题，且都集中在 `rollback` 子命令对
**安装收据（install receipt）**的信任边界上：收据中的路径字段被原样当作授权使用，既不做路径合法性校验，
也不与收据记录的 sandbox/session 绑定。三个问题在触发时都**返回 exit 0 且 `status: "OK"`**，
即破坏性越界删除被记为成功（反假绿风险）。

其余部分（build 的 commit 绑定与字节可复算、diagnose 的归档/成员/体积校验、install 的沙箱隔离与
0 写入冲突拒绝、中途失败精确回退、用户改写后回滚拒绝）经独立复算**成立**。

## 1. 合并与工作树状态

```
git status --porcelain            → 合并前为空（clean）
git merge --no-edit 0c96999d…     → Fast-forward，无冲突
```

- 本分支既有审查证据**完整保留**：`reports/v0-s3/preparation-03/` 在合并前的 171 个文件全部仍在 HEAD 上
  （该目录在 HEAD 上共 179 个，多出的 8 个来自 root 基准 `2db2fa8` 本身）。
- 合并相对本分支旧 HEAD 的净差异只涉及 `MANIFEST.sha256`、`plans/execution-control.json`
  与新增的 `reports/v0-s3/preparation-04/`、`tools/` 两个新文件；**没有删除任何既有文件**
  （`git diff --name-status 3814750 0c96999` 中只有 `M`，没有 `D`）。
- `plans/execution-control.json` 的改动来自 root 基准 `2db2fa8` 本身（只把 gate 坐标推进到
  `S3_PREP_B_OFFLINE_PACKAGE_TOOLING`、加 `preparation_addendum`），**不是**被审候选改的，
  固定分母未被改动。

## 2. 变更范围核查（root 基准 → 候选）

```
git diff --stat 2db2fa81… 1c09cd65…
  tools/test_v0_incremental_package.py | 1021 +++++
  tools/v0_incremental_package.py      | 2094 +++++
```

- 被审候选**只新增两个工具文件**，未触碰业务代码、contracts、plans、MANIFEST.sha256、既有报告。
- `1c09cd65 → 0c96999` 只新增 `reports/v0-s3/preparation-04/implementation/`（25 个文件），
  **工具字节未变**（工作树工具 sha256 与 `1c09cd65` 的 blob 一致，已逐字节核对）。
- 实现者的收据 tip 自称"完整实现收据"，其工具来源为 `git_commit`（非脏脚本），与本审查独立复算一致。

## 3. 候选测试套件（独立执行一次）

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<pack> \
python3 -B -m pytest tools/test_v0_incremental_package.py \
  -p no:cacheprovider --basetemp=<自有临时目录> -v
```

结果：**38 passed**，exit 0，耗时 18.87 s（原始输出 `raw/01-pytest.stdout.log`，退出码 `raw/01-pytest.exit.log`）。

- 计数可复现：33 个 `test_` 函数，其中 `test_unsafe_member_names_are_rejected` 参数化为 6 个用例，
  32 + 6 = 38；`pytest --collect-only` 亦收集到 38 个用例。
- 本审查**没有**把实现者的文字结论当作证据：38/38 由本次独立执行得出。
- 用例覆盖了路径穿越/绝对路径/盘符/反斜杠、重复成员、大小写冲突、symlink、exact/one-over 体积边界、
  已有冲突、安装中途故障、用户改写后回滚拒绝、CLI 契约、稳定错误码表、脱敏。
- **用例未覆盖**：被篡改的 install receipt（`owned.files[].install_path`、`staging.path`）、
  跨沙箱同名目标回滚。这是本次 Fatal/Major 的直接原因（见第 6 节）。

## 4. 独立四步真实离线链路（自建执行器）

自建执行器 `probe/chain_independent.py`（**不复用**实现者的 `run_offline_chain.py`），
自有工作根 `/tmp/lvw-indep-01-chain`（含中文与空格的沙箱根/目标目录/哨兵/包名）。

| 步骤 | 命令 | 退出码 |
|---|---|---|
| 1 | `build --repo <repo> --commit 1c09cd65… --out <pkg>` | 0 |
| 5 | `build`（同候选复算到另一文件名） | 0 |
| 2 | `diagnose --package <pkg> --target <t> --sandbox-parent <sp>` | 0 |
| 3 | `install --package <pkg> --sandbox-parent <sp> --target <t>` | 0 |
| 4 | `rollback --receipt <install-receipt> --target <t>` | 0 |

复算量（与实现者 `chain-summary.json` **逐项一致**）：

| 量 | 值 |
|---|---|
| 包 sha256 | `381089ebbe72b3e3810dad12cfe8c138ddb1bcd6451b8a0a5006b9d5ef9e4478` |
| 包大小 | 90461 字节 |
| 同候选重复构建字节相同 | **是**（两次 sha256 完全一致） |
| 成员数 | 32（29 payload + 3 meta） |
| payload 条目数 | 29 |
| 展开字节 | 183540 |
| manifest sha256 | `cec7c45d4227e10ccfa184d9ad9f6c943fd42310f6ae6aa641f7070e66f328e1` |
| 固定集合 fingerprint | `c37d797e27bdfd6e559ac5ddffa30ed39c52dfc24e29db2a95eb93b562db3509` |
| manifest `source_commit` | `1c09cd651478beeb4c1bca026505364051a72892` |
| manifest 工具 sha256 / provenance | `f96e3c06…` / `git_commit` |

**绑定链核对**：包内工具副本 sha256 = 候选 commit 的 `tools/v0_incremental_package.py` blob sha256；
manifest 的 `source_commit`、`tool.sha256`、包 sha256、manifest sha256、payload fingerprint
在 build 收据、diagnose 收据、install 收据、rollback 收据之间互相一致。

**哨兵与清理**：

- 哨兵（`哨兵 文件.txt`）安装前/安装后/回滚后 sha256 三次相同（`93b37d51…`）。
- 安装后 staging 残留：`[]`；回滚后 staging 残留：`[]`。
- 回滚后目标内剩余文件：仅 `哨兵 文件.txt`；剩余目录：`[]`。
- 包使用后已删除（`package_removed_after_use=true`），自有工作根已删除（`work_root_removed=true`）。
  **未提交任何 ZIP 或源码副本。**
- 证据见 `chain-summary.json` 与 `raw/01-build…`、`raw/02-diagnose…`、`raw/03-install…`、`raw/04-rollback…`。

**独立补充的"build 读 commit 而非脏工作树"证明（探针 N7）**：把仓库 `git clone --local` 到自有临时目录，
把 `…/lvw_v0_bridge/core.py` 改成脏内容，再从该 clone 的候选 commit 构建：
构建出的 payload 成员 sha256 **等于 commit blob**、**不等于**脏工作树文件 sha256
（`f9fdd69b…` vs `1886432d…`），且收据记录 `worktree_dirty_path_count=1`。结论成立。

## 5. 生产静态文件集合与依赖审计（29 项）

| 来源目录 | Git 已跟踪文件 | 打进 payload | 覆盖 |
|---|---|---|---|
| `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/` | 24 | 24 | 100% |
| `LVW_V0_RuntimePatch/workflows/` | 5 | 5 | 100% |
| 合计 | 29 | 29 | 100% |

- 两个 allowlist 目录**被 100% 覆盖**，没有"漏打"的生产静态文件。
- allowlist 之外仅有 `LVW_V0_RuntimePatch/manifests/s1-baseline-bindings.json` 未打包；经检索
  **没有任何被打包模块引用它**，属于仓库级准备产物而非 bridge 的运行时依赖 → 不构成缺口。
- 打包模块之间的唯一静态引用是 `native_probe.py → Path(__file__).with_name('_native_av_probe.py')`，
  两者都在 payload 内。
- `web/video_controls.js` 里的 `import … from "../../scripts/app.js"` / `"../../scripts/api.js"`
  指向 **ComfyUI 宿主自带的前端模块**（由宿主以 `/extensions/<node>/web/…` 提供），不属于包 payload。
  目录布局 `custom_nodes/lvw_v0_bridge/web/*.js` 与 ComfyUI 期望一致。
  → **Minor**：包内 `dependencies` 说明**没有列出"宿主须提供 ComfyUI 前端 scripts/app.js、scripts/api.js"**这一前提。
- 体积：包 90461 字节、展开 183540 字节，均远低于 20 MiB 硬上限；上限在 build 与 diagnose/install 两侧分别检查。

## 6. 独立负例（少量、有代表性）

执行器 `probe/negative_probes.py`，全部在自有 `TemporaryDirectory` 内的合成树上运行，
未触碰真实宿主或用户路径。原始 stdout/stderr/退出码在 `raw/probes/`。

| 探针 | 期望 | 实际 | 结论 |
|---|---|---|---|
| N1 篡改收据 `install_path` 路径穿越 | 越界文件不得被删 | **文件被删**（exit 0 / status OK） | **FATAL** |
| N2 篡改收据 `staging.path` | 不得递归删任意目录 | **整目录被删**（exit 0 / status OK） | **FATAL** |
| N3 同名不同沙箱跨目标回滚 | 不得删另一沙箱 | **删除 29 个文件**（exit 0 / status OK） | **MAJOR** |
| N4 谎报 zip 头 file_size 的炸弹 | 非零拒绝 | exit 3 `INTEGRITY_MISMATCH` | 通过 |
| N5 已有非 owned 冲突 | 非零 + 0 写入 | exit 6 `CONFLICT`，树完全不变 | 通过 |
| N6 诊断失败 | target 零写入 | exit 3，target 为空 | 通过 |
| N7 脏工作树 | 仍读 commit 字节 | payload = commit blob ≠ 脏文件 | 通过 |
| N8 Windows 尾随点/空格归一化冲突 | 必须拒绝 | **exit 0 被接受** | MINOR |
| N9 父目录 symlink 逃逸 | 拒绝且 0 写入 | exit 4 `PATH_REJECTED`，外部目录为空 | 通过 |
| N10 用户改写 owned 文件后回滚 | 拒绝且字节不变 | exit 8 `ROLLBACK_CONFLICT`，字节未变 | 通过 |
| N11 安装中途失败 | 精确回退 | exit 7 `INSTALL_FAILED`，预置文件完好，owned 桥目录已回退 | 通过 |

### F-01（Fatal）rollback 用收据里的 `install_path` 越界删除目标外文件

- **位置**：`tools/v0_incremental_package.py:1765-1809`（`command_rollback` 的预检与删除循环）。
  对比：`install` 侧对包内路径有 `_member_name_problems` 校验（`:1025-1039`），**rollback 侧完全没有**。
- **触发**：把交给 `rollback` 的 install receipt 改成 `owned.files[0].install_path = "../../victim.txt"`，
  且 `owned.files[0].sha256` 填成目标外那个文件的 sha256。
- **预期**：拒绝该收据（非零退出 + 稳定错误码），不删目标外任何内容。
- **实际**：exit 0、`status: "OK"`；收据里把 `"../../victim.txt"` 列为正常 `removed_files[0]` 并删除该文件。
- **最小复现**：`probe/negative_probes.py::n1_path_traversal_in_receipt`；
  原始证据 `raw/probes/probe-03.stdout.log`（`status=OK`、`removed_files[0]="../../victim.txt"`、
  `removed_files` 29 项）。
- **合同条款**：stage packet「rollback 按安装 receipt 绑定 session 及 installed hashes 逐项检查，
  无用户改写才移除本轮 owned 文件/目录…不递归删除非 owned 文件，不修改外部原文件」。

### F-02（Fatal）rollback 按收据 `staging.path` 对任意目录做递归删除

- **位置**：`tools/v0_incremental_package.py:1856-1862`（`command_rollback` 的 staging 清理）。
  `staging_path` 直接取自收据，`shutil.rmtree(staging, ignore_errors=True)`，**没有任何路径校验**。
- **触发**：把 receipt 的 `staging.path` 改成目标外任意目录。
- **预期**：拒绝；rollback 只能动自己在收据记录的 sandbox parent 内建的 staging 目录。
- **实际**：该目录被 `rmtree` 整体销毁；rollback 仍 exit 0 / `status: "OK"`，且报告里
  `staging_removed=true`，note 仍写着「only files owned by this install session were removed」——**陈述与事实相反**。
- **最小复现**：`probe/negative_probes.py::n2_staging_path_rmtree`；原始证据 `raw/probes/probe-05.stdout.log`。
- **合同条款**：同 F-01；且违反「未验证的收据字段不得导致删除非 owned 内容」。

### M-01（Major）rollback 只按 basename 绑定目标，可跨沙箱删除

- **位置**：`tools/v0_incremental_package.py:1738-1756`。目标选择只比较
  `Path(receipt["target"]).name != target.name`；收据里的 `sandbox_parent` 与 `session_id` **从不参与校验**，
  rollback 也**不重新验证沙箱 marker**。
- **触发**：在沙箱 A 的 `目标X` 安装，再用 A 的收据对沙箱 B 的 `目标X` 执行 rollback。
- **预期**：因不属于收据记录的 sandbox/session 而拒绝。
- **实际**：exit 0 / `status: "OK"`，把沙箱 B 里的 29 个文件删掉（含 1 个用户文件）。
- **最小复现**：`probe/negative_probes.py::n3_cross_target_rollback`；原始证据 `raw/probes/probe-08.stdout.log`。
- **合同条款**：「rollback 必须核对同一 sandbox/session 和写入身份，不因目标同名便允许跨目标删除」。

### m-01（Minor）Windows 尾随点/空格归一化冲突未拒绝

- **位置**：`tools/v0_incremental_package.py:852-873`（唯一性检查只用 `str.lower()`）。
- 构造 `payload/…/zz.py` 与 `payload/…/zz.py.` 并在 manifest 中如实登记两者 → `diagnose` **exit 0 接受**。
- **限制**：本轮只有 POSIX 沙箱，未在 Windows 上验证；Windows 上两个成员映射到同一文件名，
  若两者内容不同，安装后的哈希复验会失败（fail-safe），因此判为可移植性缺口而非已证实的丢数据路径。
- 原始证据 `raw/probes/probe-12.stdout.log`。

### m-02（Minor）实现者的链路执行器在失败路径上泄漏自有临时根

- **位置**：`reports/v0-s3/preparation-04/implementation/run_offline_chain.py:278-284`
  —— 清理是 `execute()` 的最后一句，此前任何 `raise SystemExit` 都会跳过。
- 宿主 `/tmp` 上残留：3 个前缀为 `lvw 离线包链路 ` 的空目录，以及 1 个
  `lvw smoke 沙箱.*` 目录（内含 89 KiB 的 `pkg.zip`、各步收据与沙箱目标；回滚本身成功，
  目标内只剩哨兵，但目录与包没有删除）。
- 属宿主卫生问题，不是产品缺陷，但与「使用自有临时目录并实测清理」的措辞不符。

### m-03（Minor）`--manifest` 不可读/非法时报 INTERNAL_ERROR(9) 而非 BAD_INPUT

- **位置**：`tools/v0_incremental_package.py:1003-1012`（外部 manifest 的 `json.loads` 未保护）。
- 仅错误码卫生问题，无破坏性后果。

## 7. `verify_pack` 实际覆盖（不把差异机械判为产品失败）

在审查 HEAD 上实跑 `tools/verify_pack.py`（只读，不带 `--write-report`）：

```
passed = 7945, failed = 0, exit = 0
requirements=34, stages=14, test_groups=66, api_operations=38
```

- 旧记录的计数为 7957（更早的 preparation-03 记录为 7717）。
- 计数差异的来源已定位：`MANIFEST.sha256` 由 5050 行增至 5198 行（root 基准 `2db2fa8` 所改），
  加上 verify_pack 的 `json:` 扫描会把新加的 `reports/v0-s3/preparation-04/**.json` 也计入
  （其跳过条件只排除父目录名恰为 `reports`/`previews` 的文件）。
- **实际覆盖结论**：`verify_pack` 只校验 `MANIFEST.sha256` 里列出的文件；
  候选新增的 `tools/v0_incremental_package.py`、`tools/test_v0_incremental_package.py`
  与整棵 `reports/v0-s3/preparation-04/` **不在该清单内（0 条）**，因此**不被其哈希覆盖**。
  本冻结 workpack 明确禁止改 `MANIFEST.sha256`，所以候选无权登记 → **这不是产品失败**，
  只是"该两文件的完整性目前只由本审查的 sha256 记录与 Git blob 绑定保证"。
- 原始输出：`raw/03-verify-pack.stdout.log`（退出码 `raw/03-verify-pack.exit.log`）。

## 8. 不变项与历史合规

- 体积硬上限 `20*1024*1024` 未变（常量 `SIZE_LIMIT_BYTES`）。
- 产品 12 项 / 质量 10 图 6 视频、旧 S2 7/8 均未变：被审候选只动两个 `tools/` 文件与
  `reports/v0-s3/preparation-04/implementation/`，`plans/`、`contracts/` 未被候选触碰。
- 旧 hash review 历史按原判**保持不合规**，本审查**未重开、未补跑媒体**。
- 本审查未修改候选实现后自签；未修改任何 `tools/`、业务、合同、计划、原始日志、manifest 文件。

## 9. 限制

- 仅 POSIX（WSL2）沙箱：**没有**真实 Windows 宿主、ComfyUI 启动、Ollama、GPU、模型、媒体、网络或下载。
  因此本审查**不能**声称真实 Windows 宿主产品安装已被证明；Windows 路径语义只作为 ZIP 内容问题在 POSIX 上探测。
- 未消耗任何产品完整 checkpoint；产品 runtime 调用 = 0。
- 本审查**不授予** S3 产品 Gate0、Stage PASS、人签或发布；门禁结论由 root 作。

## 10. 清理实测

| 项 | 结果 |
|---|---|
| 自有 pytest `--basetemp` | 用后删除并复检（不存在的目录） |
| 自有链路工作根 `/tmp/lvw-indep-01-chain` | 已删除（`work_root_removed=true`） |
| 包 ZIP | 使用后删除（`package_removed_after_use=true`），未提交 ZIP 或源码副本 |
| 自有探针临时根 | `TemporaryDirectory` 退出即删 |
| 仓库副作用 | 除 `reports/v0-s3/preparation-04/independent-01/` 外无新增/修改/删除；仓库内无残留 `__pycache__`、`.pytest_cache` |
| 证据脱敏 | 本目录全部文本/JSON 已做绝对路径脱敏，复扫 `/home/`、`/mnt/`、盘符路径命中 **0**；JSON 全部可解析 |

## 11. 下一动作（建议，最终门禁由 root 裁决）

阻断项：**F-01、F-02、M-01**。

1. `rollback` 侧对**收据中取出的每一个路径**做合法性校验：`owned.files[].install_path` 必须是规范化的
   相对路径且落在 owned 安装前缀之下；`staging.path` 必须位于收据记录的 `sandbox_parent` 内
   且带 `.lvw-v0-stage-` 前缀。
2. `rollback` 必须绑定收据的 sandbox/session：要求解析后的 target 落在收据 `sandbox_parent` 之内，
   重新校验沙箱 marker，且不再用 basename 比对来认定同一目标。
3. 回滚报告必须显式列出被删路径；一旦发生越出 target 的删除，必须是**非零失败**，不得记 `status: "OK"`。
4. 修正后重跑候选测试套件 **+ 本审查的 11 个独立探针**，再重跑一次四步链路并复验清理。
5. （可选，另行授权）把两个新工具文件登记进 root manifest，使 `verify_pack` 能覆盖它们。

---

证据索引：`review.md`（本文）、`independent-review.json`（机器收据）、`chain-summary.json`、
`build/diagnose/install/rollback-receipt.json`、`negative-probes.json`、`raw/`（原始命令/stdout/stderr/退出码）、
`probe/`（本审查自建的最小复现脚本）。
