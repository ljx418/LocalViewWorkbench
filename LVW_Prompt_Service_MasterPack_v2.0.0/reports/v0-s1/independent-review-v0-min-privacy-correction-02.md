# V0-Min Privacy Major Correction 02 独立复审

- 审查模式：全新隔离、离线只读；无 ComfyUI、Ollama、GPU、端口、网络或真实媒体动作
- Correction candidate：`6fcd114f6e781d143f713e82996720180a94434b`
- 基线独立报告：`6df5995e41a7b50ac4d7c416e4c92dde071e3197`
- Historical raw evidence：`c89667da32dde26425cf64a73ccca84dfea5d18d`

## 结论

**Fatal 0 / Major 0 / Minor 0**

**建议：READY_FOR_V0_MIN_GATE_DECISION。** 上轮唯一 Major 已在 reducer、execute terminal gate、verifier 和 aggregate 防篡改四层闭合。该建议只表示 root 可以进入 V0-Min 门禁裁决；不是 V0-Min PASS、Stage PASS、release approval 或新 live 授权。

默认**不需要且不得重新 live**。现有 checkpoint-01 的原始 NO_GO 保持不变，非泄漏结构机器事实仍只作为 candidate evidence 进入后续 gate。

## Findings

无 Fatal、Major 或 Minor finding。

## 上轮 Major 的独立闭合

### Reducer aggregate

`service_log_facts` 现在把以下六项精确求和为 `rejected_diagnostic_count`：

- traceback count
- current-input diagnostic count
- secret-assignment count
- long-Base64 count
- Windows absolute-path count
- WSL absolute-path count

独立合成 fixture 的结果为：

| Fixture 类别 | Windows count | WSL count | Traceback count | Aggregate | 结果 |
|---|---:|---:|---:|---:|---|
| HTTP/HTTPS URL | 0 | 0 | 0 | 0 | 可继续 |
| Windows path shape | 1 | 0 | 0 | 1 | 必须拒绝 |
| WSL path shape | 0 | 1 | 0 | 1 | 必须拒绝 |
| Traceback | 0 | 0 | 1 | 1 | 必须拒绝 |

每个 fixture 的 persisted aggregate 都与独立重算值一致。URL scheme 不再产生盘符假阳性；真实 Windows/WSL 路径均进入 aggregate。

### Execute terminal gate

`execute_live` 不直接信任 persisted aggregate：它从六个 component 独立求和，任一 component 非零，或 persisted aggregate 与 derived sum 不一致，都会把 READY 降级为 `NO_GO / SERVICE_LOG_FORBIDDEN_DIAGNOSTIC`；已有 primary failure 时记录 secondary privacy stop。

离线 fake-driver 穿透测试验证：URL fixture 返回 READY/exit 0；Windows、WSL 和 traceback fixture 均返回 NO_GO/exit 2。测试只使用合成文本与 fake driver，没有服务、GPU、端口、网络或媒体动作。

### Verifier zero-set 与 aggregate 防篡改

`verify_machine_facts` 对六个 component 执行以下独立约束：

1. 每项必须是非 bool 的非负整数；
2. 独立计算 derived sum；
3. derived sum 必须为 0；
4. persisted aggregate 必须等于 derived sum；
5. raw `service_logs` 字段仍被显式拒绝。

因此以下两类 aggregate 篡改都 fail-closed：component 非零但 aggregate 被改成 0；components 全零但 aggregate 被改成非零。Windows/WSL/traceback 非零 summary 均返回 `SERVICE_LOG_FACTS_INVALID`，URL 零值 summary 可通过。

### Raw log 不落盘

未来执行只把两个 service log 暂存在 run-owned temp，读入内存后立即缩减为不可逆计数，并随 temp 清理；raw 文本不进入封存 evidence，result/summary 不包含 raw `service_logs`。traceback fixture 的序列化结果不含原始 traceback 或诊断载荷。Verifier 另行拒绝任何重新加入 raw `service_logs` 的证据包。

## 历史证据不可变

从 `c89667d...` 到 correction candidate，`reports/v0-s1/stage-checkpoint-live-01/` 无文件差异。当前文件与历史 Git blob SHA-256 完全一致：

- `run-summary.json`：`2e77a854668ce083408c7b6d8eca1b3b6b7a973f2484a51a2c8dacd92bffeffe`
- `implementation-receipt.json`：`4258b23ba6bd54037b7165ddcff89400cb099ffbcc77ab6c58abbc8f8b3b4ca9`
- `artifact-manifest.json`：`40295b2862b8e1ca876ed2fc878fb69e359e9d36a573db97adca8ba9a9d60487`

Correction 没有把 checkpoint-01 的 `NO_GO / CASE_PRIVACY_VIOLATION` 追认为 PASS，也没有清除历史 raw diagnostic。

## Candidate identity 与测试

- Current/candidate harness SHA-256：`5832865dab2a0a24c86759a01e7eb946f24c63a02579393f464c646886c6f48d`。
- Current/candidate checkpoint test SHA-256：`1e94d61a331e0ce96435500da28cd084d4113d9f12f0bd1f0fe10d9d91e2a8e0`。
- Candidate 相对基线只改 checkpoint harness、对应测试并新增 correction receipt，未修改产品 owner、合同或历史 evidence。
- 完整离线回归：**101/101 PASS**。
- Governance：17/17；governance self-test：20/20；pack/schema：1188/1188。

新增负例覆盖 URL、Windows path、WSL path、traceback 的 reducer → execute → verifier 全链路，以及 component/aggregate mismatch 和 raw-log persistence。测试通过与静态条件、独立 fixture 结果相互一致，不依赖 receipt 的 PASS 标签。

## V0-Min scope 与 release checker 回归

- V0-Min 仍精确为 A01/A03/A04/A05/A08，acceptance hash 为 `4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5`。
- V0.1 仍为 V0-Min 累计加 A02/A07/A09/A10，共 9 项。
- V0.2 仍为 V0.1 累计加 A06/A11/A12，共 12 项。
- 旧 V0 与 V0.2 required cases 完全相同，并保留 `legacy_alias_for: V0.2`。
- Release checker 仍要求所有固定 case 为正式 PASS、同 candidate/run、存在 hash-bound observation evidence、独立 review PASS 且角色隔离、以及同 candidate/scope 的 human signoff。
- 缺任一 case、独立 review 或 human signoff 都返回非零并拒绝；`PASS_CANDIDATE_FOR_REVIEW` 仍不能通过 release gate。

Rebaseline 文档、tasks、release gates、execution-control 和 V0-S1 治理坐标未被本 correction 改动，packet/root manifest 与治理校验通过。

## Gate 使用限制

Root 可以把 checkpoint-01 中已独立复算的 24 个 public trace、五项 Oracle、模型 ledger、GPU/no-cloud/loopback、target integrity 和 owned cleanup 作为 V0-Min candidate evidence。仍不可称为：

- checkpoint-01 PASS；
- 五项正式 product PASS；
- V0-S1 Stage PASS；
- V0-Min ACCEPTED；
- 隐私合规的新鲜 live run。

进入正式 V0-Min 结论仍需 root gate decision、五项正式状态与 candidate/run/evidence 绑定，以及项目负责人 human signoff。本报告只清除隐私纠偏的独立审查阻断。

## 离线复现摘要

```text
git show / git diff / sha256sum：candidate 与历史证据 identity
service_log_facts：URL、合成 Windows/WSL path、traceback 只输出计数
fake-driver execute：URL exit 0；三类 forbidden diagnostics exit 2
verify_machine_facts：六项 zero-set、derived aggregate、tamper 和 raw-log 负例
python3 -B -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py'
tools/verify_governance.py；tools/verify_governance.py --self-test
tools/verify_pack.py --schema
```

所有操作均为离线只读检查；未把测试或治理通过提升为产品 PASS。
