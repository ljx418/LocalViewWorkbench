# V1-D0 / D0-B-IMPL 实现收据（第2版，修复 Codex 评审 Major D0-CODE-M01）

状态：**READY_FOR_REVIEW**。这不是Stage PASS，不是产品验收，不是人工签署，也不解除任何既有前置（当前产品坐标仍为 R1 / WP-R1-U3 / WAIT_HUMAN）。

机器可读版本：[implementation-receipt.json](./implementation-receipt.json)。原始日志：[logs/](./logs)。

| 项 | 值 |
|---|---|
| stage / workpack | V1-D0 / D0-B-IMPL |
| 实现者 | ClaudeCode-D0-Implement（Orca可见子工作区） |
| 独立审查 | ClaudeCode-D0-Review（另一窗口，本worker未启动） |
| 门禁所有者 | Codex |
| 分支 | `ljx418/lvw-v1-d0-implement`（父checkout未改，未merge，未push） |
| 本次候选 | `b621297fe97a4c33209c3dd55bafa6260b25f180`（checker + tests，修复后） |
| 被取代候选 | `372575b1a38c322449aece03bdf5670cfb962856`（首次候选，Codex 评审提出 Major D0-CODE-M01） |
| 生产入口 | `python3 -B tools/verify_v1_plan.py`（只读；根目录默认为本包根，所有输入路径可覆盖） |
| 新增文件 | `tools/verify_v1_plan.py`、`tools/test_verify_v1_plan.py`、`reports/v1-redesign/d0-worker/` |

未改动：contracts、plans、docs、lvw/、LVW_V0_RuntimePatch/、`.agent-governance/`（含D0 packet与其PAYLOAD_MANIFEST）、AGENTS.md、MANIFEST.sha256、权威 spec-manifest。无安装、无网络、无GPU/媒体/服务/模型调用、无凭据读取、无付费、无推送、无merge。

## 评审发现 Major D0-CODE-M01：复现与修复

**复现（候选 372575b，真实父级 spec 布局的临时副本，只改 D0 stage-control，不刷新任何围栏）**

| 注入 | 观察 | 证据 |
|---|---|---|
| `D0-B-IMPL.allowed_files=[]` | `RESULT: PASS`，退出码 **0** | `logs/repro-major-D0-CODE-M01/allowed_files_empty.stdout.log` |
| `D0-B-IMPL.commands=[]` | `RESULT: PASS`，退出码 **0** | `logs/repro-major-D0-CODE-M01/commands_empty.stdout.log` |

根因有两处：其一，`check_ownership` 写成 `if allowed and allowed != expected`，空列表为假值，绕过冻结清单比较；其二，权威 spec-manifest 未列出 D0 stage-control（实测 `stage-control in spec-manifest = False`、`D0 payload manifest in spec-manifest = False`），且 checker 完全不校验 D0 的 `PAYLOAD_MANIFEST.sha256`，因此 D0 控制面没有任何围栏。

**修复**

1. 新增 `require_exact_list`：无条件比较冻结清单，空列表、缺键、长度错、顺序错全部是发现项（`E_OWNERSHIP_ALLOWED_FILES`、`E_OWNERSHIP_COMMANDS`、`E_OWNERSHIP_REVIEW_FILES`、`E_OWNERSHIP_FORBIDDEN_PATHS`）。
2. 归属面补充：`outputs` 非空、D0-B-IMPL 与 D0-B-REVIEW 不得声明同一路径（`E_OWNERSHIP_OVERLAP`）、D0 模型/检查点预算必须为 0（`E_OWNERSHIP_BUDGET`）、被校验的 stage-control 必须就是 packet 内那一个文件（`E_OWNERSHIP_CONTROL_PATH`）。
3. 新增 `check_d0_packet_integrity`，用 D0 自身的 payload manifest 围住控制面：manifest 必须存在；其 sha256 由 checker 以源码管控（source-control pin）固定；清单必须恰好是冻结的 10 个 packet 文件（`E_D0_PACKET_MANIFEST_MISSING_ENTRY` / `E_D0_PACKET_MANIFEST_EXTRA_ENTRY`）；每个被列文件的哈希必须不变（`E_D0_PACKET_DRIFT`）；目录内不得有未登记文件（`E_D0_PACKET_UNLISTED_FILE`）；必须同时绑定 `stage-control.json` 与 `spec-manifest.json`（`E_D0_CONTROL_UNBOUND`）。
4. 攻击者改了控制面又重新签署 manifest，仍被 pin 拦住（`E_D0_PACKET_MANIFEST_PINNED`）。

**修复后同一副本复验（候选 b621297）**

| 注入 | 退出码 | 发现项 |
|---|---|---|
| `allowed_files=[]` | 1 | `E_OWNERSHIP_ALLOWED_FILES` + `E_D0_PACKET_DRIFT` |
| `commands=[]` | 1 | `E_OWNERSHIP_COMMANDS` + `E_D0_PACKET_DRIFT` |
| 改控制面并重新签署 manifest | 1 | `E_D0_PACKET_MANIFEST_PINNED` + 两条归属发现 |

## 命令、退出码与日志哈希（候选 b621297）

| 命令 | 退出码 | 观察 | stdout 日志 sha256 | stderr 日志 sha256 |
|---|---|---|---|---|
| `python3 -B tools/verify_v1_plan.py` | 0 | `RESULT: PASS (V1=29 V2=38 V3=47; MS01-MS08 once; legacy prefix intact; DAG acyclic; no human signature claimed)` | `ebb4dfc8b804a4fe064fdb7362c68c3c7e717caf38c99e9d1739ad79c1e0a57b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0 | `50 passed` | `6a2b4b6e3a0ef266a1c0a1a13e97c8d0449fd34648d05047c22bf5f411965c52` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空） |

退出码含义：0 = 根计划有效；1 = 确定性失败，每条一行 `E_CODE: detail`，按代码排序；2 = 输入不可读/不可解析，不出结论。首次候选 372575b 的原始日志保留在 `logs/candidate-372575b/`，本次候选日志在 `logs/candidate-b621297/`，复现证据在 `logs/repro-major-D0-CODE-M01/`。

## 校验了什么（不变部分）

分母 29/38/47 与 21/30/39 有序前缀；MS01–MS08 各恰好一次；R22 覆盖与 V1-M1 八项；无环 DAG（M1→R1、R2→M1，且与 tasks.json 一致）；无伪造完成/无伪造人签；12 项资源门槛方向比较 + Q01/MS01/MS04/MS05/MS07 固定质量阈值不漂移；候选 DTO Schema 结构闭合且与候选合同实体一致（`jsonschema` 可导入时做 metaschema 校验，不可导入时只跑结构检查并出 NOTE）；旧 R1 packet 与三份 canonical 合同按冻结哈希比对；权威 spec-manifest 围栏成立；预算不清零、全局授权不变、只有 V1-M1 可记在 R2 名下且 scope 哈希绑定围栏。

## 负例（50项，全部在 tmp_path 合成包上运行，绝不改动真实计划/packet/清单）

新增覆盖 Major D0-CODE-M01 的故障类：空 allowed_files / 空 commands / 空 forbidden_write_paths / 空 D0-B-REVIEW allowed_files / 缺 workpack / D0 预算非零 / 真实父级布局下 stage-control 无 spec 围栏仍需检出漂移 / packet 控制面漂移 / manifest 缺条目 / manifest 多条目 / manifest 列出的文件缺失 / manifest 本身缺失 / manifest 重新签署以掩盖漂移 / packet 目录有未登记文件 / manifest 未绑定 spec-manifest / stage-control 非 packet 内文件。其余维持：缩分母、删除原21项前缀、重复 MS（门禁/用例定义/根计划）、DAG 环、缺 M1→R1、缺 R2→M1、资源上限放宽、RAM 下限下调、门槛缺项、质量阈值漂移、写路径越权、角色未分离、伪造人签/伪人验收/伪完成/伪发布结论、预算清零、未授权 stage 别名与权威别名、scope 哈希漂移、spec 围栏漂移、canonical 合同漂移、旧 R1 包漂移、合同/Schema 不一致、Schema 未闭合、输入缺失不出结论；另有 3 项正向/只读控制（含对真实包跑一次并断言被监视文件哈希未变）。

## 风险与未做事项

1. 冻结期望表（29/38/47、21/30/39、12 项资源门槛、质量阈值 token、D0 控制清单、D0 packet 文件清单）都在 `tools/verify_v1_plan.py` 内；权威若改分母、门槛、控制清单或 D0 packet，须由所有者在同一提交内重新冻结，本worker未改任何一项。
2. D0 packet manifest 以自身 sha256 固定在 checker 内，构成 spec-manifest 未覆盖处的源码绑定；重新冻结 D0 packet 必须同步更新 checker，这是刻意的耦合。
3. 质量阈值检查读取用例断言中的中文 token；Codex 若只改措辞不改数字，会报 E_QUALITY_DRIFT，需协同重新冻结。
4. spec-manifest 围栏在权威文件先于清单更新时 fail-closed（预期的 spec drift 硬停）。
5. 本环境恰好可导入 `jsonschema`，metaschema 路径被实际执行；无该依赖的主机只跑结构检查并输出 NOTE，不会假装通过。
6. provider/model 仅为本worker自述，未获外部 harness 元数据核实；pytest tmp_path 的清理未被独立观察，故此处不作断言。
7. 自检不是独立终审；D0-B-REVIEW 与 Codex 门禁裁决仍待进行，本worker只报 READY_FOR_REVIEW。checker 只验证计划结构与冻结哈希，不能替代真实样本、标注哈希、实机质量与人工体验签署。
