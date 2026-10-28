# V0-Min rebaseline + 隐私纠偏独立审查

- 审查模式：全新隔离、离线只读；未启动或探测 ComfyUI、Ollama、GPU、端口、网络或真实媒体
- 历史 raw NO_GO：`c89667da32dde26425cf64a73ccca84dfea5d18d`
- 历史独立报告：`b1c03f8b5a7df7d0dda018430358e23878611249`
- 隐私纠偏 candidate：`c713313e966f99355d582a9c40d0a710e526cd00`
- 纠偏 harness SHA-256：`aae3582b90853ed37f5915ce116113d8f239c6191594c06c3751973d12dfe800`
- V0-Min rebaseline：`a2f97ccf130f896bed068d7b3a61cdce30eb2beb`

## 结论

**Fatal 0 / Major 1 / Minor 0**

**门禁建议：NO_GO。** V0-Min rebaseline 的分母、累计版本关系、文档和 release checker 均一致；历史 checkpoint-01 三文件也保持字节不变。隐私纠偏已解决 raw service log 未来落盘、traceback 计数 fail-closed 和 URL scheme 假阳性，但真实 Windows/WSL 路径的结构计数没有进入拒绝条件，仍存在隐私假绿路径。因此当前候选不满足 `READY_FOR_V0_MIN_GATE_DECISION` 所需的 Major=0。

默认**不需要且不得进行新 live**。该 Major 可通过纯离线纠偏、负例和重新独立审查闭合；历史 NO_GO 不得重写。

## Finding

### M-01 — Major — service-log 中真实路径计数未参与 fail-closed 判定

- **位置：** `reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py` 的 `service_log_facts`、`execute_live` 终态降级条件和 `verify_machine_facts` 的 minimal-ledger 校验。
- **触发：** 给未来 run-owned service log 注入一个合成 Windows drive-root 形态或 WSL mount-root 形态，再只持久化 `service_log_facts`。
- **预期：** 任一 `private_windows_path_count` 或 `private_wsl_path_count` 非零都必须 NO_GO；verifier 也必须拒绝。raw 文本仍不得落盘。
- **实际：** 两个计数能正确变为 1，但 `rejected_diagnostic_count` 仍为 0。`execute_live` 只依据该 aggregate 降级，verifier 的零值集合也未包含两个 path count。因此真实路径 raw 文本虽不会泄漏到 summary，却可能被结构化为非零计数后仍产生 READY 候选。
- **影响：** 这是纠偏门禁的 Major 假绿：M-02 的 URL 误报已消除，但“真实盘符仍拒绝”只在 `_privacy_scan` 直接输入测试中成立，不适用于未来实际 service-log reduction 路径。
- **证据：** 离线合成 fixture 得到 URL `path_count=0/rejected=0`、Windows `path_count=1/rejected=0`、WSL `path_count=1/rejected=0`、traceback `count=1/rejected=1`。现有 100 个测试没有覆盖“service_log_facts 的真实路径计数必须导致 execute/verifier 拒绝”。
- **复现：** 调用 `service_log_facts` 分别输入 URL、合成 drive-root、合成 mount-root 和 traceback，仅输出各计数与 aggregate；不得输出任何匹配文本。随后把非零 path count 放入 otherwise-valid summary，验证当前 verifier 未将其纳入零值约束。
- **修复边界：** 将两个 path count 纳入 aggregate 和 verifier 的显式零值集合；增加 Windows/WSL 两类 reducer、execute terminal 和 verifier 负例。无需外部动作或新 live。

## 已独立确认的通过项

### 1. 历史 raw evidence 不可变

从 raw evidence commit 到 rebaseline commit，`reports/v0-s1/stage-checkpoint-live-01/` 无文件差异。当前文件与 raw Git blob 的 SHA-256 分别一致：

- `run-summary.json`：`2e77a854668ce083408c7b6d8eca1b3b6b7a973f2484a51a2c8dacd92bffeffe`
- `implementation-receipt.json`：`4258b23ba6bd54037b7165ddcff89400cb099ffbcc77ab6c58abbc8f8b3b4ca9`
- `artifact-manifest.json`：`40295b2862b8e1ca876ed2fc878fb69e359e9d36a573db97adca8ba9a9d60487`

历史 `NO_GO / CASE_PRIVACY_VIOLATION` 和独立报告的 Major 结论均未被追认或改写。

### 2. 隐私纠偏中已闭合的部分

- Future `execute_live` 不再把 `service_logs` raw text 写入 summary；只在内存读取后生成不可逆计数，并显式删除本地文本引用。
- Verifier 明确拒绝任何含 raw `service_logs` 字段的 summary。
- Traceback、`current_inputs`、secret assignment 和长 Base64 都进入 aggregate；非零时 READY 会降级为 NO_GO，已有 primary failure 时记录 secondary privacy stop。
- Traceback fixture 的封存结果不包含 traceback 文本或其诊断载荷，结构计数为 1，终态为 `SERVICE_LOG_FORBIDDEN_DIAGNOSTIC`。
- 新的左词法边界使 HTTP/HTTPS URL 不再误报；直接 `_privacy_scan` 仍拒绝真实 drive-root 形态。M-02 的 URL 假阳性已闭合，但完整真实路径 fail-closed 仍被 M-01 阻断。
- Candidate blob 与当前 harness SHA 均为 `aae3582b...`；测试文件 blob/当前 SHA 为 `9a956812...`，与纠偏 receipt 一致。

### 3. 离线测试与负例

- 完整测试：**100/100 PASS**。
- Packet manifest、根 manifest、治理校验 `17/17`、治理 self-test `20/20`、pack/schema `1187/1187` 全部通过。
- 已有负例覆盖 raw log persistence、traceback fail-closed、URL preservation、直接 drive-path rejection、candidate/authority/trace/cleanup 等；但未覆盖本报告 M-01 的 service reducer path-count 消费断点。因此 100/100 不能消除该 Major。

### 4. V0-Min / V0.1 / V0.2 分母关系

- **V0-Min：** 精确为 A01/A03/A04/A05/A08，共 5 项。
- **V0.1：** 累计 V0-Min，再加 A02/A07/A09/A10，共 9 项。
- **V0.2：** 累计 V0.1，再加 A06/A11/A12，共 12 项。
- **旧 V0：** required cases 与 V0.2 字节序列等价，并显式标记 `legacy_alias_for: V0.2`。
- `docs/01_PRD.md`、`docs/04_ROADMAP.md`、`docs/06_ACCEPTANCE.md`、`docs/13_V0_IMPLEMENTATION.md`、`docs/22_V0_MIN_REBASELINE.md`、`plans/tasks.json`、`plans/release_gates.json`、README、execution-control 和 V0-S1 治理坐标对上述范围表述一致。后续版本不会反向阻断 V0-Min，但累计发布必须回归前序分母。

### 5. Release checker 的强制拒绝路径

独立构造 otherwise-valid V0-Min fixture 后逐项删除：

- 缺任一固定 case：return code 1，拒绝；
- 缺 independent review：return code 1，拒绝；
- 缺 human signoff：return code 1，拒绝。

Checker 还要求五项逐项 `status=PASS`、同一 application commit/run、实际 observation、hash-bound evidence、独立 reviewer 与 implementation owner 分离、review candidate 一致，以及 human signoff 的 scope/candidate 绑定。`PASS_CANDIDATE_FOR_REVIEW` 不会通过 release gate。

## checkpoint-01 结构机器事实的 V0-Min 使用边界

历史 checkpoint-01 中经 `b1c03f8...` 独立复算的非泄漏结构事实，可以继续作为同一 product candidate 的**五项 candidate evidence**输入，包括：24 个 public prompt/history 的唯一顺序、五项 Oracle、单次模型 ledger、GPU/no-cloud/loopback、target pre/post、owned cleanup 与 post-cleanup snapshot。

它们仍不能称为：

- checkpoint-01 PASS；
- V0-A01/A03/A04/A05/A08 的正式 PASS；
- V0-S1 Stage PASS；
- V0-Min ACCEPTED 或 release approval；
- 新鲜、隐私完全合规的 live evidence。

转为正式 V0-Min gate 输入至少仍需：M-01 离线闭合并重新取得 Fatal=0/Major=0 的独立结论、root 明确形成 V0-Min gate decision、五项正式状态与 candidate/run/evidence 绑定，以及项目负责人对 V0-Min 产品体验的人类签署。目标收缩不自动完成这些步骤。

## Root 可执行建议

1. 当前对 `c713313...` / `a2f97cc...` 组合记录 **NO_GO**，不要进入 V0-Min gate decision。
2. 仅离线修补两个 path count 的 aggregate/verifier 消费，并增加 reducer + execute + verifier 三层 Windows/WSL 负例；不修改历史 evidence。
3. 对新纠偏 commit 做一次隔离离线复审。若 Fatal=0/Major=0，再由 root 进入 `READY_FOR_V0_MIN_GATE_DECISION`。
4. 不申请新 live；只有新的冻结门禁明确要求新鲜目标运行时，才建立新授权和新 evidence slot。

## 离线复现命令摘要

```text
git diff / git show / sha256sum：历史三文件与候选 blob identity
python3 -B -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py'
tools/verify_governance.py；tools/verify_governance.py --self-test
tools/verify_pack.py --schema
release checker：otherwise-valid V0-Min fixture 分别删除 case/review/signoff
service_log_facts：URL/合成路径/traceback 只比较计数，不输出原值
```

所有复现均为离线只读；本审查没有把文档或治理通过当作产品 PASS。
