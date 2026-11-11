# D0-B-IMPL｜V1 多镜头设计 1.1.2 集中纠偏实施收据（NM-1..NM-8）

- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-IMPL`
- 设计权威：`3af446302f6237b41dc500ee290caf2b5075ab80`（合并进本 checkout，`36cfe62`，clean merge 无冲突）
- 状态：`READY_FOR_REVIEW`｜产品动作 0｜人工签署 无｜产品 PASS 否｜Stage PASS 否
- 编排身份：coordinator `term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0`｜worker `term_6e344f4f-8bc9-4fda-84c0-77f8af72a014`｜task `task_47741957bae4`｜dispatch `ctx_269da7001d7b`（provider 元数据自报、未独立验证）
- 本包是**一个集中纠偏包**，不是新的产品 Stage；产品仍为 `R1 / WAIT_HUMAN`，无样本冻结，无运行时授权

## 1. 强制命令（原始日志在 `logs/`，数字均由脚本从日志提取）

| 命令 | exit | 结果 | stdout sha256 |
|---|---|---|---|
| `python3 -B tools/verify_v1_plan.py` | 0 | `RESULT: PASS (V1=29 V2=38 V3=47; MS01-MS08 once and NOT_RUN; legacy prefix intact; DAG acyclic; parent deadline 450*n+90<=5490; checkpoint 65+ 7=72 actions / 21600 s; no human signature claimed)` | `4a6b877a46b65e05aa78d263bbf7cf844052eff94c62e7ddd72fa0aa96ecc7c9` |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0 | 233 passed, 0 failed, 0 skipped | `ba0ed5305595227cd40f86514487e6c3720f024451f29160d423715a15698a1d` |

补充只读校验：

| 命令 | exit | 结果 | stdout sha256 |
|---|---|---|---|
| `python3 -B tools/verify_pack.py` | 0 | passed 7530, failed 0 | `b01b4ec90da6d543ac67b40e3326f3988118d03345b63c625a698ceb9b082335` |
| `python3 -B tools/verify_governance.py` | 0 | errors [], failed 0 | `e8927ccbca17c63e6ca696c254e5e232add8617ec564f840df4907579089d7cf` |
| owner `verify-design112.py`（临时副本） | 0 | {"checks": 72, "failed": 0} | `9bda961ee8a6dc1aa7fa111e868d88f592b70891853f773f86d58836ae7584f9` |
| 独审探针 P01/P02/P05/P22/P23/P24 + P00 | 0 | 六个负例均 exit 1 并给出确定性 finding；P00 正例 exit 0 | `e774821f2166788a0bcb24b3f640585fc779e7469a3cf080f625c10cd732673a` |

## 2. NM-7：旧 1.1.1 收据的更正（追加式，旧字节全部保留）

- 旧收据：`reports/v1-redesign/d0-worker/design111/implementation-receipt-1.1.1.json`（sha256 `bc2ed1fba46ff57abe6721014efb8f79c6b4bb81458a0d8cc4f3b3547edacf8d`）
- 旧收据正文写的是 **passed 7408**；它按 sha256 绑定的日志 `reports/v1-redesign/d0-worker/design111/logs/verify_pack.stdout.log`（sha256 `c0d2ebec64a86d1f2de344d347cc96ba4c3ee8c2e0bc7a569444ebcb6885e4e9`）写的是 **passed 7475**
- 结论：正文数字陈旧（沿用 1.1 收据），日志本身正确且在册；**旧收据、旧 markdown、旧日志一字未改**
- 本树 `verify_pack` 的 **passed 7530** 是新树计数，与历史 7475 不可直接等同（多数检查按 MANIFEST.sha256 逐行一项）

## 3. 计数核对（NM-7 附带）

- `findings.json` 的实际 finding 数组：**3 Major + 5 Minor（Fatal 0，共 8 条 NM-1..NM-8）**
- 独审报告 summary 写的是 **6 Minor**；该报告原文保留未改，差异在此收据核对说明，未凭空制造第九条问题

## 4. 允许写入清单（与 stage-control 一致）

- `tools/verify_v1_plan.py`
- `tools/test_verify_v1_plan.py`
- `reports/v1-redesign/d0-worker/design112/implementation-receipt-1.1.2.json`
- `reports/v1-redesign/d0-worker/design112/implementation-receipt-1.1.2.md`
- `reports/v1-redesign/d0-worker/design112/make_receipt.py`
- `reports/v1-redesign/d0-worker/design112/reviewer-probe-rerun.py`
- `reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.exit.log`
- `reports/v1-redesign/d0-worker/design112/logs/pytest.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/pytest.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/pytest.exit.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_pack.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_pack.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_pack.exit.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_governance.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_governance.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify_governance.exit.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify-design112.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify-design112.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/verify-design112.exit.log`
- `reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.stdout.log`
- `reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.stderr.log`
- `reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.exit.log`

## 5. 限制

- This is an offline plan and schema correction. It is not product acceptance, not a product Gate0, not a Stage PASS and not a human signature.
- The product coordinate stays R1 / WAIT_HUMAN; the 621b1bf experience signature is still absent and the samples stay NOT_MATERIALIZED_NOT_FROZEN.
- The candidate migration is only read as text; it is never executed and no production database is opened.
- The N5 domain engine is an offline plan/schema rule guard. There is no runtime adapter yet, so the conformance fixtures prove that the declared rule is implementable and unambiguous; they do not verify product output.
- The scene hash can only be validated against the declared prose rule, because the DDL that defines lvw_scene_hash is not part of the frozen package.
- The probe suite is a bounded independent selection, not an exhaustive enumeration of the checker's inputs.
- The provider and model identity are self reported by the worker session and were not independently verified.

