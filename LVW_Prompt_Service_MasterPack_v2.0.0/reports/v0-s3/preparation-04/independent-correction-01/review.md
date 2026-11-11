# S3-PREP-B correction-01 — 独立闭环复验（independent-correction-01）

- 审查对象：`tools/v0_incremental_package.py` + `tools/test_v0_incremental_package.py`（correction-01 候选）
- root 纠偏裁决基准：`7d1398527236f760205053e7b886cc3bd04c1fd2`（已含于候选历史）
- 工具候选（被审代码身份）：`ef8c065346a8f7d78b28b238207e7550444d897e`
- 完整修复证据 tip：`c40c6f1769141f7ce2cf85d5b531ffe4e6d25b61`
- 本审查合并后的 HEAD：`070b9615c2f81c31d45164b2979ab401cbc64c39`
- 审查分支：`ljx418/lvw-v1-d0-review`
- 规格 hash（`stage-packet-preparation-b.md`）：`cd7076463467ae6545ac86de633a2100ad357f2d2ab5946bf490ddaba2588abd`
- 纠偏包 hash（`correction-01.task.md`）：`d0c1f8f3f59a9b1753885f7a1bd7290c5aa05e46a837e9ab6eceafa159ba3e86`
- 裁决单 hash（`codex-review-decision-01.json`）：`fd728bca47319f78c7e47d10074568563709b1f4b16d9351bbacba33a012a497`
- 工具 sha256：`b383d2e9292ada578cc8b90b9bcea8b15ce8c49cb439c0ccec6abcc65d899931`
  （= 候选 commit 中 `tools/v0_incremental_package.py` 的 blob，工作树字节与候选 commit **逐字节一致**，已用 `git diff ef8c065 -- tools/` 核对为空）
- 测试文件 sha256：`f115219661d12e9ae5dbb4ec1bfb9a3f734c6808995a03dce2a89a55739d2419`
- 运行环境：Linux 6.18.40.1-microsoft-standard-WSL2 x86_64 / Python 3.12.3 / pytest 8.4.2 / git 2.43.0
- 产品 runtime 调用：**0**；网络/下载/GPU/模型/媒体/真实宿主配置：**未使用**；产品完整 checkpoint：**0**

> 证据里的绝对路径已做确定性脱敏（`<pack-root>` / `<git-worktree-root>` / `<own-tmp-root>` / `<tmp-root>`），
> 脱敏只替换路径字符串，**所有 sha256、退出码、判定字段逐字保留**（见 `evidence-redaction.json`）。

## 0. 结论

**建议：correction-01 的 `F-01` / `F-02` / `M-01` 与三 Minor 全部闭合，本轮不建议再退回纠偏。**
（门禁结论由 root / Codex 裁决；本审查**不授予** S3 产品 Gate0、Stage PASS、人签或发布。）

- 原 **2 个 Fatal（F-01、F-02）**：**已闭合**。经**独立复现**（不是采信实现者的 17/17 摘要），
  篡改收据的 `owned.files[].install_path` 与 `staging.path` 现在都返回**非零 + 稳定错误码**，
  外部 victim 字节不变、目标整树不变。
- 原 **1 个 Major（M-01）**：**已闭合**。跨沙箱同名回滚现在被目标内所有权记录的目标身份 / 沙箱 marker /
  session 三重绑定拦下，另一沙箱整树（含其 owned 文件与非 owned 标记）零变更。
- 原 **3 个 Minor（m-01/m-02/m-03）**：**已闭合**（m-02 的历史残留按合同只披露，见第 9 节）。
- **本轮未发现新的阻断项。** 只发现 **1 个新的 Minor（表述精度，非功能缺陷）**，见第 10 节。

证据汇总：候选测试 **70 passed / exit 0**；独立负例 **22/22**；所有权记录写失败故障注入 **3/3**；
runner 清理自检 **2/2**；独立真实链路 **33/33 校验通过**；证据脱敏 **0 泄漏**。

## 1. 合并与工作树状态

```
git status --porcelain            → 合并前为空（clean）
git merge --no-edit c40c6f1769141f7ce2cf85d5b531ffe4e6d25b61
                                  → Merge made by the 'ort' strategy.  无冲突
```

- 合并结果为 `070b9615c2f81c31d45164b2979ab401cbc64c39`；**无冲突，未覆盖任何既有文件**。
- `ef8c065` 与 `7d13985` 均为 `c40c6f1` 的祖先（已用 `git merge-base --is-ancestor` 核对）。
- 合并**相对本分支旧 HEAD 的净差异**只有：`MANIFEST.sha256`（root 维护）、`plans/execution-control.json`
  （仅 5 行门禁坐标/next_action/处置单指针，**固定分母未改**，见第 8 节）、新增 `reports/v0-s3/preparation-04/`
  下的纠偏包与两个 `tools/` 文件。`contracts/` 与业务代码 `LVW_V0_RuntimePatch/` **零改动**。
- **原始失败证据保持不变**：原 `independent-01/` 的 108 个文件与 `implementation/` 的 203 个文件
  均未被本轮覆盖或改写（`git diff HEAD -- <两目录>` 为空）；本轮只新增 `independent-correction-01/` 目录。

## 2. 候选变更范围核查

```
git diff --name-status 4be5f61 ef8c065
  M  tools/test_v0_incremental_package.py   (+582 行量级)
  M  tools/v0_incremental_package.py        (+1100 行量级)

git diff --name-only 4be5f61 ef8c065 | grep -E "^(plans|contracts|LVW_V0_RuntimePatch|MANIFEST)"
  → NONE
```

- 候选**只改了两个 `tools/` 文件**，未触碰业务代码、contracts、plans、MANIFEST.sha256、既有报告。
- `ef8c065 → c40c6f1` 只新增 `reports/v0-s3/preparation-04/implementation/correction-01/`，
  **工具字节未变**（`git diff ef8c065 HEAD -- tools/` 为空）。

### 修复点的实现位置（供 root 复核）

| 原问题 | 本轮实现位置（`tools/v0_incremental_package.py`） |
|---|---|
| F-01 收据路径穿越 | `_validate_owned_relative_path`(:295) + `_validate_owned_entries`(:2308)；`command_rollback` 在交叉核对**之前**先校验收据全部路径字段(:2583-2593) |
| F-02 收据 staging 任意 rmtree | `command_rollback` 只**确认** staging 终态、从不递归删除(:2665-2707)；全仓唯一的 `rmtree` 在 `_remove_owned_staging`(:2132)，且先做「本工具前缀 + 位于沙箱内 + 非 symlink」三重身份确认 |
| M-01 同名跨沙箱 | 目标身份绑定(:2516-2532) + 沙箱父目录/marker 身份(:2534-2566) + 不可碰撞 session(:2568-2581)，**不再用 basename 认定同一目标** |
| 所有权记录 | `_build_ownership_record`(:1667) / `_write_ownership_record`(:1717，原子写且拒绝覆盖用户文件) / `_read_ownership_record`(:1755，缺失/改写/自洽性全拒) |
| m-01 Windows 尾随点/空格/保留名 | `_windows_component_key`(:268) 用 `rstrip(" .").lower()`，并新增 `_path_component_problems`(:282) 拒绝保留设备名 |
| m-03 `--manifest` 坏输入 | 外部 manifest 的读取与解析都归一到 `BAD_INPUT`(:1168-1192) |

## 3. 候选测试套件（独立执行一次）

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<pack> \
python3 -B -m pytest tools/test_v0_incremental_package.py \
  -p no:cacheprovider --basetemp=<自有临时目录> -v
```

结果：**70 passed**，exit 0，耗时 27.45 s。原始输出 `raw/00-pytest.stdout.log`，退出码 `raw/00-pytest.exit.log`。
自有 `--basetemp` 用后删除并复检（目录不存在）。

**「70 tests」属实**（`--collect-only` 也收集到 70 个用例）。

### 旧 38 功能覆盖保留的独立核对

不是采信实现者的说法，而是把**旧候选的测试文件**（`4be5f61:./tools/test_v0_incremental_package.py`）
取出来单独 `--collect-only`，再按**用例 id**（按行切分，因为有一个 id 本身含空格）做集合比较：

| 量 | 值 |
|---|---|
| 旧候选收集到的用例 | 38 |
| 新候选收集到的用例 | 70 |
| **旧用例在新候选中缺失** | **0**（旧 38 是新 70 的严格子集） |
| 新增用例 | 32（全部是 correction-01 回归） |
| 旧测试文件正文中消失的行 | 只有 2 行：`def make_sandbox(...)` 签名行与其 `target = ...` 赋值行 |

即：旧测试**没有任何断言被删除、放宽或改成恒通过**；唯一的旧改动是 `make_sandbox` helper 增加了一个
**带默认值**的 `target_name` 形参（默认行为不变）。证据：`old-test-coverage-retention.json`。

### 新 oracle 的合理性

旧正例里唯一发生终态变化的是「安装后回滚」：目标内现在会多落一份所有权记录，回滚时它自身也是本轮 owned，
因此**回滚后目标内 owned 文件数从 29 降为 29（payload 全删）且所有权记录一并被移除**——这是合同第 12 条
明确要求的「rollback 安全移除 owned 记录」，属于**合理的终态变化**，而不是把失败改成通过。
新加的 32 个用例全部是**新增的负例**（篡改收据/记录/绑定字段 → 必须非零且零副作用），
没有把任何旧正例的判据放松。

## 4. 独立负例（22 个探针，**不复用实现者的脚本**）

驱动：`probe/negative_probes_correction01.py`（本审查新写；只复用独审 independent-01 自己写过的驱动骨架，
**全部 oracle 按 correction-01 合同重新表述**）。全部在自有 `TemporaryDirectory` 内的合成树上运行。
原始 stdout/stderr/exit 逐条落在 `raw/probes/`（50 次 CLI 调用 × command/stdout/stderr/exit = 200 个原始记录文件）。

**结果：22 / 22 通过（`raw/01-probes.exit.log` = 0）**，机器收据 `negative-probes.json`。

| 探针 | 期望 | 实测（exit / error_code） | 结论 |
|---|---|---|---|
| P01 **F-01** 收据 `install_path` 穿越 | 4/PATH_REJECTED，目标整树不变，外部 victim 字节不变，哨兵不变 | **4 / PATH_REJECTED** ✓ | 通过 |
| P02 **F-02** 收据 `staging.path` 指向外部目录 | 非零，目标整树不变，victim 目录及内容原样存在 | **8 / ROLLBACK_CONFLICT** ✓ | 通过 |
| P03 **M-01** 同名不同沙箱跨目标回滚 | 非零，沙箱 B（含其 owned 文件与非 owned 标记）与沙箱 A 整树都不变 | **8 / ROLLBACK_CONFLICT**，B 前后 32 文件不变 ✓ | 通过 |
| P04 收据 `owned.directories` 穿越 | 非零，零删除，外部目录原样存在 | **4 / PATH_REJECTED** ✓ | 通过 |
| P05 收据 `owned.created_directories` 穿越 | 非零，零删除 | **4 / PATH_REJECTED** ✓ | 通过 |
| P06 收据 `preimage.files[].path` 穿越 | 非零，零删除，外部 victim 字节不变 | **4 / PATH_REJECTED** ✓ | 通过 |
| P07 收据 session 与本地记录不符 | 8/ROLLBACK_CONFLICT，零删除 | **8** ✓ | 通过 |
| P08 目标内所有权记录缺失 | 8/ROLLBACK_CONFLICT，零删除 | **8** ✓ | 通过 |
| P09 所有权记录被改写（owned 清单） | 非零，零删除，外部 victim 字节不变 | **8** ✓ | 通过 |
| P10 所有权记录被改写**且攻击者重算 install_hash** | 非零（外部收据交叉核对必须拦下重绑），零删除 | **8** ✓ | 通过 |
| P11 沙箱 marker 缺失 | 非零，零删除 | **8** ✓ | 通过 |
| P12 沙箱 marker 内容被改 | 非零，零删除 | **8** ✓ | 通过 |
| P13 收据 `target` 被改绑到另一沙箱 | 非零，两个沙箱整树都不变 | **8** ✓ | 通过 |
| P14 **晚失败**：staging 残留仍在 | 非零，零删除，**残留目录与其内容必须原样存在（不得 rmtree）** | **8**，残留目录完好 ✓ | 通过 |
| P15 **晚失败**：用户改写 29 个 owned 中的 1 个 | 8/ROLLBACK_CONFLICT，**整树不变（其余 28 项也必须零删除）** | **8**，24 个 `custom_nodes/` 文件全部仍在 ✓ | 通过 |
| P16 脱敏收据 + 显式 `--target` | 0，owned 全移除，所有权记录被移除，哨兵不变 | **0** ✓ | 通过 |
| P17 脱敏收据 + 显式 `--target` 指向别的目标 | 非零，两个沙箱整树都不变（脱敏不得成为重绑借口） | **8** ✓ | 通过 |
| P18 脱敏收据 + 不给 `--target` | 2/BAD_INPUT，零删除 | **2 / BAD_INPUT** ✓ | 通过 |
| P19 Windows 段尾随点 / 段尾随空格 / 保留设备名（`zz.py.` / `zz.py ` / `NUL` / `con.py`） | 每个案例都 4/PATH_REJECTED | **4 / PATH_REJECTED ×4** ✓ | 通过 |
| P20 外部 `--manifest` 非法 JSON / 不可读 | 两种都 2/BAD_INPUT | **2 / BAD_INPUT ×2** ✓ | 通过 |
| P21 回滚绝不 rmtree 任何收据点名的目录（含沙箱内的目录） | 非零，零删除，被点名目录原样存在 | **4 / PATH_REJECTED** ✓ | 通过 |
| P22 目标根本没装过 | 非零，零删除 | **8** ✓ | 通过 |

### 关于「不得只比较 basename 或同文件 hash」

P03/P13/P17 三个探针都把**同名**目标放在**不同沙箱**里，其中 B 沙箱还装了一份**内容完全相同**的 payload
（即「同文件 hash」情形）。三者都被拒绝且两个沙箱整树零变更——证明绑定用的是
**规范化 target 身份 + 沙箱 marker 身份 + 不可碰撞 session + 外部收据交叉核对**，不是 basename，也不是文件 hash。

### 关于「有限威胁边界」

P10 是本轮**最强**的同权限篡改尝试：攻击者直接改写目标内所有权记录的 owned 清单，并**按工具同一算法重算
`install_hash`**（因此记录自身自洽，`_read_ownership_record` 的自洽性检查放行）。结果仍被**外部收据交叉核对**
拦下（8/ROLLBACK_CONFLICT，零删除，外部 victim 字节不变）。

按纠偏合同「无需建立密钥服务/平台或对本机同权限主动篡改者作不现实承诺」，本审查**不要求**密码学防篡改；
但可以确认：**在合同声明的边界内，收据替换/重绑路径已被独立证伪。**

## 5. 所有权记录写失败（确定性故障注入，3 个变体）

驱动：`probe/ownership_write_failure.py`。该失败分支无法用黑盒 CLI 稳定触发（安装前的同名检查会先拦下），
因此把**候选 commit 的工具 blob 抽出到自有临时目录后导入本进程**，只 monkeypatch 工具模块的
`os.replace` / `_write_ownership_record`，**其余逻辑与候选字节逐字一致**。
**仓库里的 `tools/v0_incremental_package.py` 一个字节都没有被本审查改动。**

**结果：3 / 3 通过（`raw/02-ownership-write-failure.exit.log` = 0）**，机器收据 `ownership-write-failure.json`。

| 变体 | 期望 | 实测 |
|---|---|---|
| A 所有权记录的原子发布（`os.replace`）失败 | 非零(INSTALL_FAILED)、**无所有权记录（含临时文件）**、owned 全部回退、哨兵完好、staging 已清 | **7 / INSTALL_FAILED**；无记录、无临时文件残留、owned 剩余 0、哨兵完好、**沙箱内实际 staging 残留 = []**、原始失败保留 ✓ |
| B 整个 `_write_ownership_record` 抛错 | 同上 | **7 / INSTALL_FAILED**；同上全项满足 ✓ |
| C 所有权记录写成功但内容被改写（记录不可用） | 回滚必须 8/ROLLBACK_CONFLICT 且零删除 | **8**，24 个 owned 文件一个不少 ✓ |

A/B 变体证明**不存在「已安装但报 OK 且无可用 record」的无记录终态**：所有权记录落盘是安装事务的最后一步，
落盘失败会连带回退已 commit 的 owned 项。

## 6. 本轮 runner 的失败路径清理自检

驱动：`probe/runner_cleanup_selftest.py`，把独审自己的探针驱动当作被测 runner。
**结果：2 / 2 通过（`raw/03-runner-cleanup.exit.log` = 0）**，机器收据 `runner-cleanup-selftest.json`。

| 探针 | 期望 | 实测 |
|---|---|---|
| R01 正常路径 | exit 0，且自有临时根已被删除 | exit 0，临时根已不存在 ✓ |
| R02 **失败路径**（注入强制异常） | exit ≠ 0，且**自有临时根仍然已被删除** | exit 1（`RuntimeError: simulated runner failure after setup`），临时根已不存在 ✓ |

## 7. 独立四步真实离线链路（自建驱动）

驱动：`probe/chain_independent_correction01.py`（本审查新写，**不使用**实现者的链路脚本或其摘要）。
候选是**同一个精确 Git commit `ef8c065…`**，工作根含中文与空格
（`<own-tmp-root>/lvw 独立链路 correction01 <rand>/隔离 沙箱根/隔离 目标 目录`）。

| 步骤 | 命令 | 退出码 |
|---|---|---|
| 1 | `build --repo <repo> --commit ef8c065… --out <pkg> --redact-root <workroot>` | 0 |
| 1b | `build`（同候选复算到另一文件名） | 0 |
| 2 | `diagnose --package <pkg> --target <t> --sandbox-parent <sp> --redact-root <workroot>` | 0 |
| 3 | `install --package <pkg> --sandbox-parent <sp> --target <t> --receipt-out <r> --redact-root <workroot>` | 0 |
| 4 | `rollback --receipt <r> --target <t>`（脱敏收据 + 显式 target） | 0 |

**结果：33 / 33 校验通过（`raw/04-chain.exit.log` = 0）**，机器收据 `chain-summary.json`。

### 绑定链核对

| 量 | 值 |
|---|---|
| 候选工具 blob sha256 | `b383d2e9292ada578cc8b90b9bcea8b15ce8c49cb439c0ccec6abcc65d899931` |
| **包内工具副本** `meta/v0_incremental_package.py` sha256 | **等于**候选 blob ✓ |
| manifest `tool.sha256` / `provenance` | 等于候选 blob / **`git_commit`** ✓ |
| manifest `source_commit` | `ef8c065346a8f7d78b28b238207e7550444d897e` ✓ |
| 包 sha256 | `2c74a8d0c91cb078bd3e5f8f258359e0f0352914aa8966f40f88ad97a33cf898`（98983 字节） |
| **同候选重复构建字节相同** | **是**（两次 sha256 完全一致）✓ |
| manifest sha256（build/diagnose/install 三份收据一致） | `173568308385c260ab01c0c2287c632414dee7154b0706a1d9271b67b2efb589` ✓ |
| 固定 payload fingerprint（build 收据 / 所有权记录 / 由 manifest items 独立重算） | 三者**完全一致** = `c37d797e27bdfd6e559ac5ddffa30ed39c52dfc24e29db2a95eb93b562db3509` ✓ |
| 包成员数 / payload 条目数 / 展开字节 | 32 / 29 / 183540 |
| 所有权记录 sha256（与 install 收据 `ownership.sha256` 一致） | 见 `chain-summary.json`（每次安装含随机 session_id，该值逐次不同） ✓ |
| 所有权记录绑定 | source_commit / package_sha256 / manifest_sha256 / target_identity_sha256 / sandbox_marker.sha256 **全部对上** ✓ |

> 注：payload fingerprint `c37d797e…` 与独审 **independent-01** 当时记录的 fingerprint **完全相同**——
> 说明本轮修复只动了工具与所有权机制，**生产 payload 集合逐字节未变**（独立复核，非实现者自述）。

### 哨兵 / 非 owned / 外部 victim 前后一致

| 对象 | 安装前 | 安装后 | 回滚后 | 结论 |
|---|---|---|---|---|
| 哨兵 `哨兵 文件.txt` | `403252aaeacc926cc64bddc9ddce43085c8a1d88e114758e2297760f1d0f239a` | 同左 | 同左 | **三次相同** ✓ |
| 外部 victim（**沙箱之外**）`victim.txt` | `f33ec5ef2a27f08188b09a080e402f1c4f52c820b6d0c2fd4b83c3aa3a3960a6` | 同左 | 同左 | **三次相同** ✓ |
| 用户在安装**之后**新增的 `用户 新增 文件.txt` | （安装后创建）`4d40d51a5d76914cf4cabf2278213c1ee0179c4405c3a4b7284ad9ebef5b68c7` | — | 同左 | **原样保留** ✓ |

### 本地所有权记录生命周期与 staging

| 项 | 结果 |
|---|---|
| 安装后目标内所有权记录 | **存在** ✓ |
| 回滚后所有权记录 | **已移除**（回滚收据 `ownership_record.removed = true`） ✓ |
| 安装后 staging 残留 | `[]` ✓ |
| 回滚后 staging 残留 | `[]` ✓ |
| 回滚移除的 owned 文件 / 目录 | **29 个文件 / 5 个目录** |
| 回滚后目标内剩余文件 | 仅 `哨兵 文件.txt` 与 `用户 新增 文件.txt`；剩余目录 `[]` ✓ |
| 回滚收据 `staging_deleted_by_rollback` | **`false`**（回滚本身**未**做任何递归删除） ✓ |
| 回滚收据 `sentinel_unchanged` | `true` ✓ |
| 自有工作根 | **实测已删除** ✓ |
| 包 ZIP（含复算副本） | **用后删除**，**未提交任何 ZIP 或源码副本** ✓ |
| 提交的 install 收据绝对路径泄漏 | **0**（`<redacted-root>` 已生效） ✓ |

## 8. 原 F-01 / F-02 / M-01 与三 Minor 的逐条判定

| 编号 | 原判 | 本轮判定 | 依据 |
|---|---|---|---|
| **F-01** | Fatal | **已闭合** | P01（exit 4，外部 victim 字节不变，目标整树不变）+ P21（不 rmtree 任何收据点名的目录）+ 候选测试 `test_F01_*` |
| **F-02** | Fatal | **已闭合** | P02（exit 8，外部 victim 目录及内容原样存在）+ P14（残留 staging 不得 rmtree）+ 实现位置：回滚只确认 staging 终态 |
| **M-01** | Major | **已闭合** | P03 / P13 / P17（跨沙箱、同名、同内容均被拒，两个沙箱零变更） |
| **m-01** | Minor | **已闭合** | P19（`zz.py.` / `zz.py ` / `NUL` / `con.py` 全部 4/PATH_REJECTED） |
| **m-02** | Minor | **已闭合（就本轮实现而言）** | R01/R02（新的 runner 失败路径也清理自有临时根）；**历史残留按合同只披露**，见第 9 节 |
| **m-03** | Minor | **已闭合** | P20（非法 JSON 与不可读都是 2/BAD_INPUT） |

**闭合方式小结（不是靠加密，而是靠"授权来源"的重构）**：
回滚现在**只信任目标内的所有权记录**作为删除授权来源；外部收据**降级为交叉核对材料**，
其任何路径字段都不再授予删除权；目标身份改用**规范化绝对路径 + sha256** 而非 basename；
所有路径在**第一次写入/删除之前**完成全量校验（类型/集合/唯一性/相对规范/前缀归属/symlink 逃逸/Windows 归一化）。

## 9. `/tmp` 历史残留（**仅披露，未删除，未阻断候选**）

按 correction-01 合同「仅核实由本实现者此前创建且能以记录证明的精确临时根，才清理；不扫删 `/tmp` 前缀或未知目录」，
本轮**没有删除任何宿主目录**。实现者此前链路执行器遗留的 5 个目录仍然在原处，已逐个记录
（文件名、文件数、字节数、每个文件的 sha256、mtime、mode）于 `tmp-residue-disclosure.json`：

| 目录 | 文件数 | 字节 | 性质 |
|---|---|---|---|
| `<tmp-root>/lvw smoke 沙箱.McucN0` | 14 | 174518 | 含 `pkg.zip`（89156 字节）与各步收据 |
| `<tmp-root>/lvw smoke 沙箱.tj7KZA` | 4 | 714 | 含哨兵与 build 收据 |
| `<tmp-root>/lvw 离线包链路 15ar1jkf` | 0 | 0 | 空目录 |
| `<tmp-root>/lvw 离线包链路 iupsl92p` | 0 | 0 | 空目录 |
| `<tmp-root>/lvw 离线包链路 qcjychxp` | 0 | 0 | 空目录 |

这与独审 independent-01 的 m-02 是**同一根因**（清理是执行器 `execute()` 的最后一句，异常路径跳过）。
独审**无法以记录证明**这 5 个目录的完整所有权链，因此**只披露、不擅删**，并**不因此阻断本候选**。
（本轮自己的 runner 不再产生同类残留，见第 6 节。）

## 10. 本轮新发现（**无阻断项**，1 个 Minor）

### NEW-m-01（Minor，表述精度，非功能缺陷）安装失败回退收据里的 `cleanup.staging_removed` 字段**低报**

- **位置**：`tools/v0_incremental_package.py` 的 `_rollback_committed`（约 :2202-2204）。
  该字段只在 `staging.exists()` 为真时才置 `True`。
- **现象**：当失败发生在**所有权记录写入**阶段时，staging 目录**早已**被同一事务里前一步的
  `_remove_owned_staging` 成功删除，因此回退收据里 `cleanup.staging_removed` 是 `false`。
- **实测**：本审查**实测**沙箱内实际 staging 残留为 `[]`（变体 A/B），即**没有真实泄漏**；
  字段只是**低报**（false negative），并非合同禁止的「伪造 staging_removed」。
- **影响**：仅可能让读失败收据的人误以为 staging 泄漏。**不构成破坏性风险，不阻断候选。**
- **建议（准备工具层面，非本轮阻断）**：把该字段改成「staging 终态」语义（例如
  `staging_absent: true` + `staging_removed_by_this_cleanup: false`），或直接报告实测的终态，
  以免与「是否由本次回退删除」混为一谈。

### 留给 root 的开放项（非候选缺陷）

- `tools/v0_incremental_package.py` 与 `tools/test_v0_incremental_package.py` **目前仍不在
  `MANIFEST.sha256` 里**（该清单当前只登记了 `reports/v0-s3/preparation-04/**` 的 117 条）。
  冻结 workpack 明令候选不得改 `MANIFEST.sha256`，且根 manifest 由 root 维护，因此
  **这不是产品失败**；本候选工具的完整性目前只由 **Git blob + 本审查记录的 sha256** 绑定。
  （这正是 independent-01 第 11 节第 5 条的可选建议，仍未由 root 落地。）
- 本审查新增的 `independent-correction-01/` 目录同样需要 root 登记进根 manifest。

## 11. 不变项与历史合规

- 体积硬上限 `20*1024*1024` 未变（常量 `SIZE_LIMIT_BYTES`）；包 98983 字节、展开 183540 字节，均远低于上限。
- **产品 12 项 / 质量 10 图 6 视频 / 旧 S2 7/8 全部不变**：本候选只动两个 `tools/` 文件；
  `contracts/` 与 `LVW_V0_RuntimePatch/` 在合并前后**零改动**；
  `plans/execution-control.json` 相对合并前只改了 5 行（gate 坐标、`current_blocking_gate`、
  `next_action`、`exact_stop_reason`、`latest_preparation_disposition` 指针），**`development_outline`
  条目数 14 → 14 不变，固定分母未被改动**。
- 旧 hash review 历史按原判**保持不合规**，本审查**未重开、未补跑媒体**。
- 本审查**未修改候选实现后自签**；未修改任何 `tools/`、业务、合同、计划、原始日志、manifest 文件。
  仓库内唯一新增/修改就是 `reports/v0-s3/preparation-04/independent-correction-01/`。
- **按任务要求未重复全项目 `verify_pack`**（根 manifest 由 root 维护）。

## 12. 限制（不得被扩大解读）

- 仅 **POSIX（WSL2）** 沙箱：**没有**真实 Windows 宿主、ComfyUI 启动、Ollama、GPU、模型、媒体、网络或下载。
  因此本审查**不能**、也**没有**声称真实 Windows 宿主产品安装已被证明；
  Windows 路径语义只作为 **ZIP 内容问题在 POSIX 上探测**（段尾随点/空格/保留设备名）。
- POSIX 沙箱的成功链路**不等于** Comfy 真实安装通过。
- 本轮把所有权记录的 `install_hash` 当作**自洽性校验**（防误改），**不主张**它能抵抗同权限的主动重算攻击；
  P10 之所以仍被拦下，靠的是**外部收据交叉核对**，不是密码学。
- 未消耗任何产品完整 checkpoint；产品 runtime 调用 = 0。
- 本审查**不授予** S3 产品 Gate0、Stage PASS、人签或发布；门禁结论由 root 作。

## 13. 清理实测

| 项 | 结果 |
|---|---|
| 自有 pytest `--basetemp` | 用后删除并复检（目录不存在） |
| 独审自有 pytest / 探针 / 故障注入 / 链路的临时根 | 全部由 `TemporaryDirectory` 覆盖，**成功与失败路径都实测已删除**（R01/R02） |
| 链路工作根 `<own-tmp-root>/lvw 独立链路 correction01 …` | **实测已删除** |
| 包 ZIP（含复算副本） | **用后删除**，**未提交 ZIP 或源码副本** |
| 宿主 `/tmp` 历史 5 个残留 | **未删除**（无所有权证明），已披露（第 9 节） |
| 仓库副作用 | 仅新增 `reports/v0-s3/preparation-04/independent-correction-01/`；仓库内无残留 `__pycache__` / `.pytest_cache` |
| 证据脱敏 | 256 个文件扫描、122 个文件含脱敏占位符；**复扫 `/home` `/mnt` `/root` `/Users` 盘符路径命中 0**；所有 JSON 仍可解析；**所有 sha256 串逐个不变**（`evidence-redaction.json`） |

## 14. 给 root 的建议（仅为准备工具层面）

1. **correction-01 可以收口**：F-01 / F-02 / M-01 与三 Minor 全部闭合，独立复现下**零越界删除**。
2. 建议 root 把两个 `tools/` 文件与本审查目录登记进根 `MANIFEST.sha256`，让 `verify_pack` 能覆盖它们。
3. 建议把 NEW-m-01 的 `cleanup.staging_removed` 字段语义改成「staging 终态」，避免误读；**不阻断**。
4. 建议由 root 处置（而非本审查）那 5 个 `/tmp` 历史残留。
5. **不要**把本轮的 POSIX 沙箱结论扩大为 Windows 宿主或 Comfy 真实安装结论。

---

证据索引：`review.md`（本文）、`independent-review.json`（机器收据）、`chain-summary.json`、
`negative-probes.json`、`ownership-write-failure.json`、`runner-cleanup-selftest.json`、
`old-test-coverage-retention.json`、`tmp-residue-disclosure.json`、`evidence-redaction.json`、
`raw/`（原始命令/stdout/stderr/exit）、`probe/`（本审查自建的 8 个最小复现/校验脚本）。
