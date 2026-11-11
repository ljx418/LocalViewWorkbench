# S3-PREP-B 离线增量包工具 — 实现收据

- 范围：**S3-PREP-B 离线准备**。不是产品 Gate0，不是 Stage PASS，不是 V0.2/V1 验收，
  不构成人工签署。
- 冻结实施合同：`reports/v0-s3/preparation-04/stage-packet-preparation-b.md`
- 唯一 root 基准：`2db2fa81e34479e08ea33df7c90a179d1fd99936`（本任务唯一基准，fast-forward 合入，0 冲突）
- 工具候选 commit（本轮真实链路的绑定候选）：**`1c09cd651478beeb4c1bca026505364051a72892`**
- 工具 SHA256：`f96e3c064d0e0dee2cbaeeb63b1df39738c3d560020c27f7890e97d820f5eab9`
- 实现者只能报告 READY_FOR_REVIEW；Stage 裁决由 Codex 门禁负责，独立审查由另一实例执行。

---

## 1. 变更清单

只写入合同允许的三个位置，未触碰任何其它工具、合同、业务代码、计划、manifest 或历史证据。

| 路径 | 变更 | 说明 |
|---|---|---|
| `tools/v0_incremental_package.py` | 新增 | 唯一生产 owner。stdlib only，无第三方依赖，无任意 shell 执行接口。 |
| `tools/test_v0_incremental_package.py` | 新增 | 定向测试 38 项。 |
| `reports/v0-s3/preparation-04/implementation/run_offline_chain.py` | 新增 | 真实离线链路执行器（证据可复现）。 |
| `reports/v0-s3/preparation-04/implementation/implementation-receipt.md` | 新增 | 本收据。 |
| `reports/v0-s3/preparation-04/implementation/implementation-receipt.json` | 新增 | 本收据的机器可读版本。 |
| `reports/v0-s3/preparation-04/implementation/package-manifest.json` | 新增 | 本轮包的文本 manifest（外部副本）。 |
| `reports/v0-s3/preparation-04/implementation/{build,diagnose,install,rollback}-receipt.json` | 新增 | 机器收据（已脱敏）。 |
| `reports/v0-s3/preparation-04/implementation/raw/*` | 新增 | 原始命令、stdout、stderr、exit、chain-summary。 |

提交序列（作者一律 `ljx418 <1173696783@qq.com>`）：

| commit | 内容 |
|---|---|
| `4bfa7e5d6c4348817324082a31c9c114ba3e0ab5` | feat：工具与定向测试 |
| `319e602a427671cab47df16c9da3ff5d57b80564` | fix：stdout 与收据绝对路径脱敏 |
| `1c09cd651478beeb4c1bca026505364051a72892` | fix：stderr 诊断绝对路径脱敏（**本轮绑定候选**） |

未修改：`MANIFEST.sha256`、`plans/`、`contracts/`、`LVW_V0_RuntimePatch/`（业务代码）、
`reports/` 下任何既有证据、旧 packet、governance stage 文件。

---

## 2. 只读审计（Workpack 第 1 条）

**现有构建/安装能力盘点（只读 Git 跟踪文件，未扫描本机）：**

- `tools/` 下无任何增量包 owner。唯一使用 `zipfile` 的是 `tools/verify_pack.py`，用途是文档/合同
  结构校验，不是打包 owner。
- 最接近“安装”语义的是 `tools/v0_s2_native_component.py`：它把
  `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge` 用 `shutil.copytree` 复制进一个合成 run root
  （`run_root/custom_nodes/lvw_v0_bridge`），并按相对前缀比对哈希。它是**测试夹具**，不是安装/回滚
  owner：不生成 manifest、不做体积上限、不做路径安全、不用沙箱 marker、不产生安装收据、不支持回滚。
  → **不能复用为安装/回滚 owner**；仅复用其“同根隔离 Comfy 目录布局”的既有约定
  （`custom_nodes/lvw_v0_bridge`）。
- `.agent-governance/stages/V0-S3/stage-control.json` 存在，但没有任何可执行的打包/安装产物，与
  `docs/24_EXECUTION_MASTER_PLAN.md` 的记录一致（“安装/回滚命令与构建脚本目前尚无该目录的成套产物”）。
- 差异已记入本收据第 1 节；未新增第二套调度系统，未做全面重构。

**生产模块静态文件缺口审计（合同要求“有缺口先报告，不擅自扩大”）：**

- 生产模块实际需要的静态文件全部落在合同允许范围内：`custom_nodes/lvw_v0_bridge/` 下 22 个已跟踪
  `.py`（含 `native_probe.py` 通过 `Path(__file__).with_name(...)` 加载的同目录
  `_native_av_probe.py`）、`web/` 下 2 个已跟踪 `*.js`、`workflows/` 下 5 个已跟踪 `.json`，合计 **29 项**。
- `LVW_V0_RuntimePatch/manifests/s1-baseline-bindings.json` 虽被 Git 跟踪，但**没有任何生产模块引用**；
  全仓唯一读取者是 `LVW_V0_RuntimePatch/tests/test_s1_contract_fixtures.py`。它是 S1 测试绑定夹具，
  不是生产 payload 缺口，故按合同排除（tests / 绑定夹具本就不入包）。
- 结论：**未发现生产静态文件缺口**，未扩大 payload 范围。
- 附加 fail-closed 扫描：payload 内容若含 Windows 盘符绝对路径、POSIX 家目录绝对路径、
  PEM 私钥头或常见 API key 形态，build 直接以 `PATH_REJECTED` 拒绝。当前 payload 扫描结果为 0 命中。

---

## 3. 公共 CLI 合同（冻结）

四个子命令已冻结，语义不变。全部命令：结构化 JSON 写 **stdout**，诊断写 **stderr**，
非零退出码表示失败，异常不会被吞成成功。每个子命令都有 `--help`。

```
build     --repo <dir> --commit <sha> --out <file.zip> [--receipt-out <file>] [--redact-root <dir>]...
diagnose  --package <file.zip> [--manifest <file.json>] [--target <dir>] [--sandbox-parent <dir>]
          [--receipt-out <file>] [--redact-root <dir>]...
install   --package <file.zip> --sandbox-parent <dir> --target <dir> [--manifest <file.json>]
          [--session-id <id>] [--receipt-out <file>] [--redact-root <dir>]...
rollback  --receipt <file.json> [--target <dir>] [--receipt-out <file>] [--redact-root <dir>]...
```

`--redact-root` 可重复；给定后，收据文件、stdout JSON 与 stderr 诊断中的绝对路径统一替换为
`<redacted-root>/...`，用于提交脱敏证据。

### 3.1 稳定错误码与退出码

| 错误码 | 退出码 | 典型触发 |
|---|---|---|
| `OK` | 0 | 成功 |
| `BAD_INPUT` | 2 | 参数缺失/非法、候选不可解析、沙箱 marker 缺失或 magic 不符、收据 schema 不符 |
| `INTEGRITY_MISMATCH` | 3 | 包内字节与 manifest 的长度/SHA256 不符、条目集合不符、Git 对象身份不符、工具副本与 manifest 不符 |
| `PATH_REJECTED` | 4 | 路径穿越、绝对路径、盘符、反斜杠、重复成员、大小写冲突、symlink 成员、目标越出沙箱、生产宿主路径 |
| `SIZE_LIMIT` | 5 | 压缩包或展开 payload 超 20 MiB；zip bomb |
| `CONFLICT` | 6 | 输出已存在（不覆盖）、目标已含 owned 安装路径 |
| `INSTALL_FAILED` | 7 | 安装中途故障（含已 commit owned 项的回退）；回滚无法完全清理 |
| `ROLLBACK_CONFLICT` | 8 | 回滚前发现 owned 文件被用户改写或已缺失 |
| `INTERNAL_ERROR` | 9 | 未预期异常（不被吞掉为成功） |

### 3.2 输出 JSON schema（顶层键）

- 公共失败信封：`{schema_version, command, status:"FAILED", tool, error_code, message, detail}`。
- `build`：`schema_version, command, status, tool{name,version,sha256,provenance}, repo,
  source_commit, requested_commit, worktree_dirty_path_count,
  package{path,sha256,size_bytes}, manifest{sha256,member,item_count},
  payload{expanded_bytes,fingerprint_sha256,items[{install_path,source_path,source_blob_id,length,sha256}]},
  excluded_entries[], checks[], limits{size_limit_bytes}`。
- `diagnose`：`schema_version, command, status, tool, package{path,sha256,size_bytes},
  manifest{sha256,source_commit,item_count}, payload_expanded_bytes, checks[],
  target{path,exists,writable,checks[]}, note`。
- `install`：`schema_version, command, status, session_id, tool, source_commit,
  package{path,sha256,size_bytes}, manifest{sha256,member,content},
  sandbox_parent, sandbox_marker{path,sha256}, target, created_target_root,
  preimage{files[],directories[]},
  owned{files[{install_path,sha256,length}],directories[],created_directories[]},
  installed_top_level[], staging{path,removed}, checks[], note`。
- `rollback`：`schema_version, command, status, session_id, target, removed_files[],
  removed_directories[], failed_removals[], retained_directories[], remaining_owned_files[],
  preimage_drift[], sentinel_unchanged, postimage_files[], staging_removed, note`。

`checks[]` 是逐项检查记录，每项为 `{name, passed, detail}`。本轮 diagnose 记 10 项：
`member_path_safety`、`member_uniqueness`、`member_kind_regular_files`、
`size_limits_and_zip_bomb`、`member_declared_length`、`member_set_layout`、
`manifest_item_integrity`、`manifest_entry_set`、`tool_copy_matches_manifest`、
`usage_document_present`。

### 3.3 包内容与 manifest 合同

包成员（POSIX 相对路径，固定顺序）：

```
payload/custom_nodes/lvw_v0_bridge/<22 个 .py + web/2 个 .js>
payload/workflows/lvw/<5 个 .json>
meta/manifest.json
meta/v0_incremental_package.py     # 工具自身的版本化副本，可直接在已装 Python 环境执行
meta/使用说明.md                    # 中文使用说明
```

manifest 字段：`schema_version`、`package_format_version`、`source_commit`、`tool{name,version,sha256,
provenance,provenance_detail}`、`size_limit_bytes`、`payload_root`、`payload_item_count`、
`payload_expanded_bytes`、`items[{install_path,package_path,source_path,source_blob_id,source_mode,
length,sha256}]`、`dependencies[]`、`non_goals[]`。

- manifest **不自引用**：manifest 自身哈希记录在**外部机器收据**（build/install/rollback 收据的
  `manifest.sha256`），包内不含 manifest 哈希。
- manifest `dependencies` 只列本任务可离线证明的前提（Python 3.8+ 标准库、隔离沙箱目录、可写目标）；
  明确写明 **numpy/Pillow/ffmpeg/PyAV/Ollama 由宿主提供，本包不携带也不验证**，
  并声明只复用本机已验证宿主、不声称任意机器可用。
- `non_goals` 明确：不携带模型/权重/媒体/用户稿/凭据/真实宿主配置；不安装或修改真实宿主；
  不启动服务/调用模型/使用 GPU/联网/下载；不覆盖已有安装做升级；离线包链路不是产品 Gate0。

### 3.4 build 语义

- 从**显式 Git 候选 commit** 读字节（`git rev-parse` + `ls-tree` + `cat-file --batch`），
  **绝不打包脏工作树**；绑定完整 40 位 commit SHA。
- git 失败、或 `ls-tree` 与 `cat-file` 的对象身份（blob id）不一致 → 直接拒绝。
- 体积硬上限 `20*1024*1024` 字节，**压缩包与展开 payload 分别检查**；另有 zip bomb 比例检查
  （整包 ≤ 200，单成员 ≤ 500）。
- 确定性：固定成员顺序、固定时间戳（1980-01-01）、固定权限（100644）、固定压缩级别，
  因此同一候选重复构建产出**字节相同**的包（已实测）。
- 先写临时包 → 全量自校验 → `os.replace` 原子发布；**不覆盖已存在输出**（CONFLICT）。
- 工具自身身份：优先取 commit 中的 `tools/v0_incremental_package.py` 字节
  （`provenance:"git_commit"`）；若该 commit 没有该文件，退回工作树字节并显式标注
  `provenance:"working_tree_uncommitted"`，**不声称脏脚本来自 commit**。

### 3.5 diagnose 语义

- 在写安装目标之前完成全量校验：归档可读性、成员名安全、重复/大小写冲突、成员种类、成员声明长度、
  体积上限与 zip bomb、manifest schema、逐项长度与 SHA256、条目集合双向相等、
  manifest 自报计数与展开字节数一致、工具副本与 manifest 身份一致、中文说明含来源 commit。
- 拒绝项：路径穿越、绝对路径、UNC、盘符、反斜杠绕过、空组件、`.`/`..`、重复成员、
  Windows 大小写冲突、symlink/目录成员、zip bomb。
- **不使用 `extractall`**；不写 target；可选只读检查 target 的可写性与隔离 marker；
  不调用任何外部服务。

### 3.6 install 语义

- 目标必须位于**显式给出的 sandbox parent** 之内（且不等于 parent），且该 parent 必须带
  本工具沙箱 marker：文件名 `.lvw_v0_incremental_sandbox.json`，内容
  `{"magic":"lvw.v0-incremental-sandbox/1","tool":"v0_incremental_package.py"}`。
- 生产宿主路径**硬拒绝**：路径组件（大小写不敏感）命中
  `comfyui` / `comfyui-aki-v2` / `comfyui_windows_portable` / `comfyui-aki` 即 `PATH_REJECTED`。
- 安装布局（相对 install root）：`custom_nodes/lvw_v0_bridge/` + `workflows/lvw/`。
- 已有非 owned 冲突（owned 顶层路径已存在）→ 默认拒绝且 **0 写入**。
- 顺序：完整校验（0 写入）→ 冲突检查 → preimage 快照 → 沙箱内暂存目录逐成员严格落盘并复算哈希 →
  原子 `os.rename` 提交 → 安装后逐项哈希复验。
- 记录：目标 preimage、manifest、session ID、全部 owned 文件与目录、staging 路径与清理结果、
  包与 manifest 哈希、来源 commit。
- 失败时回退**已 commit 的 owned 项**与本轮创建的父目录，保留原始失败与实测清理数据；
  暂存目录始终被清理。**不把沙箱安装当真宿主验收**（收据 `note` 显式声明）。

### 3.7 rollback 语义

- 按安装收据绑定 session 与 installed hashes **逐项**复算；任一项被用户改写或缺失 →
  `ROLLBACK_CONFLICT`，**保留用户字节**，报告 drifted/missing 清单，**不删任何东西**。
- 全量预检通过后才做变更：只删本轮 owned 文件；owned 目录用 `os.rmdir`（非空即失败），
  因此**绝不递归删除非 owned 文件**；含非 owned 内容的目录被保留并在 `retained_directories` 中报告。
- 成功证明：原有哨兵/preimage 字节未变（`sentinel_unchanged`、`preimage_drift`）、
  owned 文件全部移除（`remaining_owned_files` 为空）、staging 已清理（`staging_removed`）。
- 支持含中文与空格的路径（端到端已实测）。
- 工具**不含**任何任意 shell 执行接口（`os.system` / `os.popen` / `shell=True` 均不存在，已由测试断言）。

---

## 4. 定向测试

命令：

```
python3 -m pytest tools/test_v0_incremental_package.py -q
```

结果：**38 passed**，exit 0。

真实链路（真实固定 commit `2db2fa81e34479e08ea33df7c90a179d1fd99936`，非合成）：

1. `test_build_binds_full_commit_sha_and_expected_hash_set` — 绑定完整 40 位 SHA；
   payload hash 集合与**独立用 `git ls-tree`/`git cat-file` 计算的集合逐项相等**（29/29）。
2. `test_build_reads_git_objects_not_dirty_worktree` — 包内字节逐个等于 Git 对象字节。
3. `test_build_is_reproducible_for_same_candidate` — 同一候选两次构建包字节完全相同，manifest 与包哈希相同。
4. `test_build_refuses_to_overwrite_existing_output` — CONFLICT，已存在输出字节不变。
5. `test_real_chain_install_diagnose_rollback_in_chinese_space_path` — 构建 → 诊断 → 中文/空格隔离
   target 安装 → 目录布局与 hash 集合校验 → 回滚 → 只剩哨兵且哨兵字节未变。
6. `test_install_receipt_records_preimage_manifest_and_owned_writes` — 收据含 preimage、manifest、
   session id、全部 owned 写入。

错误分支（合成包，只用于错误分支，不替代上面的真正常链）：

篡改包、manifest 篡改、路径穿越、`..`、绝对路径、盘符、反斜杠、空组件、重复成员、
大小写冲突、symlink 成员、exact/one-over 体积边界、zip bomb、缺 meta 成员、
已有 owned 冲突 0 写入、安装中途故障回退已 commit owned 项、用户改写后回滚拒绝且保留字节、
owned 文件缺失、目标越出沙箱、生产宿主路径、缺沙箱 marker、校验失败不留空安装目录、
diagnose 不写 target、CLI `--help`/`--version`、stdout JSON + stderr 诊断、失败非零退出、
错误码-退出码表冻结、工具无 shell 接口、工具仅标准库、脱敏（2 项，含中文空格路径）。

---

## 5. 一次真实离线包链路（绑定候选 `1c09cd6`）

执行器：`reports/v0-s3/preparation-04/implementation/run_offline_chain.py`。
包与临时副本建在自有临时目录，**不进入 Git**；证据写入 `reports/v0-s3/preparation-04/implementation/`。

| 项 | 值 |
|---|---|
| 候选 commit | `1c09cd651478beeb4c1bca026505364051a72892`（解析后一致） |
| 工具 SHA256 | `f96e3c064d0e0dee2cbaeeb63b1df39738c3d560020c27f7890e97d820f5eab9` |
| 工具与候选 commit 字节一致 | **true**（执行器强制校验，不一致即中止） |
| payload 条目数 | 29（22 个 `.py` + 2 个 `web/*.js` + 5 个工作流 `.json`） |
| 展开 payload 字节 | 183 540（上限 20 971 520） |
| 包 SHA256 | `381089ebbe72b3e3810dad12cfe8c138ddb1bcd6451b8a0a5006b9d5ef9e4478` |
| 包大小 | 90 461 字节（上限 20 971 520） |
| 包成员数 | 32（29 payload + 3 meta） |
| manifest SHA256 | `cec7c45d4227e10ccfa184d9ad9f6c943fd42310f6ae6aa641f7070e66f328e1` |
| 固定集合 fingerprint | `c37d797e27bdfd6e559ac5ddffa30ed39c52dfc24e29db2a95eb93b562db3509` |

| 步骤 | 退出码 | 结果 |
|---|---|---|
| build | 0 | 绑定候选 commit，包自校验 10 项通过 |
| diagnose | 0 | 归档/manifest/体积/路径/成员集合全量校验通过；未写 target |
| install | 0 | 隔离沙箱（`隔离 沙箱根/隔离 目标 目录`）安装 29 个 payload 文件 + 哨兵 = 30 文件 |
| rollback | 0 | owned 文件全部移除，回滚后只剩 `哨兵 文件.txt` |

哨兵与清理测量：

| 项 | 值 |
|---|---|
| 哨兵安装前 SHA256 | `403252aaeacc926cc64bddc9ddce43085c8a1d88e114758e2297760f1d0f239a` |
| 哨兵安装后 SHA256 | 同上（未变） |
| 哨兵回滚后 SHA256 | 同上（未变） |
| 回滚后哨兵字节与原始一致 | **true** |
| 回滚后剩余文件 | `["哨兵 文件.txt"]`（30 → 1） |
| 暂存目录残留 | **[]** |
| 工作目录 | `removed_by_runner`（自建临时目录，已删除并实测） |
| 产品 runtime 调用 | **0** |

包成员清单与逐项 SHA256 见 `package-manifest.json`；每步的原始命令、stdout、stderr、exit
见 `raw/01-*` 至 `raw/04-*`；汇总见 `raw/chain-summary.json`。

---

## 6. 仓库既有离线门禁（未回退，未改动）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python3 -B tools/verify_pack.py --schema` | 0 | passed 7957 / failed 0 |
| `python3 -B tools/verify_governance.py` | 0 | stage R1，errors [] |

说明：冻结基准 `2db2fa8` 上同一命令为 passed 7950 / failed 0（已用 `git archive` 只读复核），
本轮 +7 来自新增的 7 个证据 JSON（build/diagnose/install/rollback 收据、package-manifest、
chain-summary、implementation-receipt）参与校验，两次均 failed 0。
`reports/v0-s3/preparation-04/root-validation-01.json` 里记录的 8007 是在**合并前**的审阅分支树上
测得的数字，与合并后本分支的 7950 不同源；这是**既有差异，不是本轮引入**，
未据此改写任何门限或结论，也未去修改那个既有收据（它对本任务只读）。

---

## 7. 风险与限制

1. **不是产品验收**：本链路是离线准备证据。真实宿主未安装、未启动、未调用模型、未用 GPU，
   产品 runtime 调用预算为 0。V0.2 / V1 的门禁完全未触碰。
2. **沙箱不等于宿主**：安装只发生在带 marker 的隔离沙箱；真实 ComfyUI 宿主路径被硬拒绝，
   因此本轮**不能**声称宿主可安装或宿主已验证。
3. **宿主依赖未验证**：numpy、Pillow、ffmpeg/PyAV、Ollama 端点由宿主提供，本包不携带也不验证；
   工具只声明“复用本机已验证宿主”，不声称任意机器可用。
4. **包体积与压缩比的相互作用**：展开 payload 恰好等于 20 MiB 时，压缩包必须仍小于 20 MiB，
   而 zip bomb 比例阈值（整包 200 / 单成员 500）又会拒绝过度可压缩的合成数据。
   真实 payload（183 540 字节，源码，压缩比约 4）不触发该交互；该交互已在
   `test_size_limit_exact_boundary_passes_and_one_over_fails` 中以受控填充数据分别证明
   “恰好上限通过 / 超 1 字节拒绝”。
5. **跨环境字节复算**：包的可复算性在**同一 Python/zlib 环境**内实测为字节相同。
   换 zlib 版本后压缩字节可能不同；因此跨环境的可复算基准是
   **payload 固定集合 fingerprint**（`c37d797e…`）与 manifest 哈希，而不是压缩包字节。
6. **不支持覆盖升级**：已有 owned 安装路径一律 CONFLICT（0 写入）；合同明确本轮不实现覆盖升级。
7. **沙箱 marker 由沙箱拥有者提供**：工具只校验 marker，不代为签发，避免 install 自签沙箱。
   marker 被写错或丢失时报 BAD_INPUT，不会退化为“自动放行”。
8. **脱敏收据不可直接驱动回滚**：脱敏后的 install 收据不含真实绝对路径，回滚必须显式给 `--target`，
   工具对此给出明确 BAD_INPUT 而不是拿占位符当相对路径。
9. **脱敏根覆盖范围**：只对 `--redact-root` 给出的目录做替换；根之外的绝对路径在结构化 JSON 中
   变成 `<abs-path-redacted>`，在 stderr 文本中不做通用正则替换（本轮证据已实测 0 泄漏）。
10. **未覆盖的边界**：Windows 真实文件系统语义（大小写冲突、reparse point）只在 POSIX 上以等价
    语义验证，**未在真实 Windows 上跑过**；真实宿主上的 ComfyUI 节点注册、路由与前端加载
    未做任何验证。
11. **独立审查未做**：本收据是实现者自检，按合同不得宣布 Stage PASS；需另一隔离实例复核。

---

## 8. 证据路径

```
reports/v0-s3/preparation-04/implementation/
├── implementation-receipt.md            # 本收据
├── implementation-receipt.json          # 机器可读收据
├── package-manifest.json                # 本轮包的文本 manifest（外部副本）
├── build-receipt.json                   # build 机器收据（脱敏）
├── diagnose-receipt.json                # diagnose 机器收据（脱敏）
├── install-receipt.json                 # install 机器收据（脱敏，含 preimage/owned/session）
├── rollback-receipt.json                # rollback 机器收据（脱敏，含哨兵证明与清理）
├── run_offline_chain.py                 # 真实链路执行器
└── raw/
    ├── chain-summary.json               # 链路汇总（候选 SHA、工具 SHA、包/manifest 哈希、
    │                                    #   fingerprint、哨兵前后哈希、清理测量）
    ├── 01-build.{command,stdout,stderr,exit}.log
    ├── 02-diagnose.{command,stdout,stderr,exit}.log
    ├── 03-install.{command,stdout,stderr,exit}.log
    └── 04-rollback.{command,stdout,stderr,exit}.log
```

实现者结论：**READY_FOR_REVIEW**。未授予 Stage PASS，未授予产品 Gate0，未请求重复人签。
