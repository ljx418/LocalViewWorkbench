# V1-D0 / D0-B-IMPL 实现收据（实现者自检，READY_FOR_REVIEW）

状态：**READY_FOR_REVIEW**。这不是Stage PASS，不是产品验收，不是人工签署，也不解除任何既有前置（当前产品坐标仍为 R1 / WP-R1-U3 / WAIT_HUMAN）。

机器可读版本：[implementation-receipt.json](./implementation-receipt.json)。原始日志：[logs/](./logs)。

## 交付

| 项 | 值 |
|---|---|
| stage / workpack | V1-D0 / D0-B-IMPL |
| 实现者 | ClaudeCode-D0-Implement（Orca可见子工作区） |
| 独立审查 | ClaudeCode-D0-Review（另一窗口，本worker未启动） |
| 门禁所有者 | Codex |
| 分支 | `ljx418/lvw-v1-d0-implement`（父checkout未改） |
| candidate SHA | `372575b1a38c322449aece03bdf5670cfb962856`（checker + tests） |
| 生产入口 | `python3 -B tools/verify_v1_plan.py`（只读；根目录默认为本包根，所有输入路径可覆盖） |
| 新增文件 | `tools/verify_v1_plan.py`、`tools/test_verify_v1_plan.py`、`reports/v1-redesign/d0-worker/` |

未改动：contracts、plans、docs、lvw/、LVW_V0_RuntimePatch/、`.agent-governance/`、AGENTS.md、MANIFEST.sha256、权威 spec-manifest。无安装、无网络、无GPU/媒体/服务/模型调用、无凭据读取、无付费、无推送。

## 命令、退出码与日志哈希

| 命令 | 退出码 | 观察 | stdout 日志 sha256 | stderr 日志 sha256 |
|---|---|---|---|---|
| `python3 -B tools/verify_v1_plan.py` | 0 | `RESULT: PASS (V1=29 V2=38 V3=47; MS01-MS08 once; legacy prefix intact; DAG acyclic; no human signature claimed)` | `ebb4dfc8b804a4fe064fdb7362c68c3c7e717caf38c99e9d1739ad79c1e0a57b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0 | `34 passed` | `8bf47fedf2ae2ed3090199b3c4053904566b03a1aa4648f7fd9159369a9a5d62` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空） |

退出码含义：0 = 根计划有效；1 = 确定性失败，每条一行 `E_CODE: detail`，按代码排序；2 = 输入不可读/不可解析，不出结论。日志与退出码原始记录见 `logs/`。

## 校验了什么

- 分母：V1/V2/V3 恰为 29/38/47；变更前 21/30/39 以原顺序保留为前缀。
- MS01–MS08 在 release gates、根计划、用例定义、R22 接受集中各恰好出现一次。
- 覆盖：R22 存在且状态 NOT_RUN，由 V1-M1 与 R2 承担；V1-M1 恰好负责八个 MS 用例。
- DAG：plan 无环，V1-M1 依赖 R1，R2 依赖 V1-M1，plan 与 tasks.json 依赖一致。
- 无伪造完成/无伪造人签：设计期阶段 completed 必须为 0；用例/阶段状态只在 NOT_RUN/PASS/FAIL/BLOCKED 内；批准文件的人签/发布标志必须为 false；plan 内不得出现签署字段或 execution-control 的 forbidden claim。
- 无放宽固定门槛：12 项资源门槛按方向比较（上限不得变大、下限不得变小、缺项报错）；Q01/MS01/MS04/MS05/MS07 断言文本中的固定质量阈值不得漂移。
- D0 归属：D0-B-IMPL 允许文件清单、禁止写路径、角色四分离、两条冻结命令均被强制。
- 候选合同/Schema：候选 DTO Schema 结构闭合（additionalProperties=false、required ⊆ properties）、与候选合同实体 required 一致；`jsonschema` 可导入时做 metaschema 校验，不可导入时只跑结构检查并出 NOTE，绝不静默通过。
- 不可变物：旧 R1 packet manifest 及其文件、三份 canonical 合同、权威 spec-manifest 围栏全部按冻结哈希比对。
- 预算与授权：不得 `budget_reset`；全局授权仍为 `AUTH-PROGRAM-V1-COMPLETE-03`；只有 `V1-M1` 可记在 `R2` 名下；scope record 的哈希必须与 spec-manifest 一致（改写批准文件即 E_SCOPE_HASH_DRIFT）。

## 负例（34项，全部在 tmp_path 合成包上运行，绝不改动真实计划）

缩分母、删除原21项前缀、重复 MS（门禁/用例定义/根计划三处）、DAG 环、缺 M1→R1、缺 R2→M1、资源上限放宽、RAM 下限下调、门槛缺项、质量阈值漂移、写路径越权、角色未分离、伪造人签、伪造人验收、伪造完成、伪造发布结论、预算清零、未授权 stage 别名（R2/V3）、权威别名、scope 哈希漂移、spec 围栏漂移、canonical 合同漂移、旧 R1 包漂移、合同/Schema 不一致、Schema 未闭合、输入缺失不出结论；另有 3 项正向/只读控制（含对真实包跑一次且断言文件未被写动）。

## 风险与未做事项

1. 冻结期望表（29/38/47、21/30/39、12 项资源门槛、质量阈值 token）写在 `tools/verify_v1_plan.py` 内；权威若改分母或阈值，须由所有者在同一提交内重新冻结，本worker未改任何一项。
2. 质量阈值检查读取用例断言中的中文阈值 token；Codex 若只改写措辞而不改数字，会报 E_QUALITY_DRIFT，需要协同重新冻结。
3. spec-manifest 围栏使 checker 在权威文件先于清单更新时 fail-closed（这是预期的 spec drift 硬停），也意味着 checker 只对围栏一致的树有效。
4. 本环境恰好可导入 `jsonschema`，metaschema 路径被实际执行；无该依赖的主机上只跑结构检查并输出 NOTE，不会假装通过。
5. 自检不是独立终审；D0-B-REVIEW 与 Codex 门禁裁决仍待进行，本worker只报 READY_FOR_REVIEW。
6. checker 只验证计划结构与冻结哈希，不能替代真实样本、标注哈希、实机质量与人工体验签署。
