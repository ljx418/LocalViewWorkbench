# R1a LIVE-05 Independent Review

结论：**NO_GO；Fatal 0 / Major 4 / Minor 2；不得进入人工体验门槛。**

本审查为隔离、只读、离线审查；未修改候选，未启动服务、Ollama 或浏览器，未访问网络。

## 身份与执行事实

- packet 1.1 manifest 9/9 匹配，固定分母哈希 `82a3736a...` 正确。
- 候选 `f901c492...`、四个 live harness、offline checkpoint、固定样本、模型、端口和预算与 LIVE-05 子授权一致。
- LIVE-04 在任何外部动作前被授权枚举门禁拒绝，未消耗 Stage checkpoint；LIVE-05 的 corrected full recheck 启动合法。
- 浏览器提交、provider `started/completed(success)` 和 Ollama `POST /api/chat` 均恰为 1；真实本地 provider 调用成立。
- LIVE-05 terminal receipt 已使授权自动过期；R1a program corrected-recheck 额度已耗尽。

## Major

1. 浏览器产品路径在 English copy oracle 超时，clipboard、采纳后 JSON/TXT、三档布局截图和 `browser-result.json` 均未完成；七项分母正确保持 `PENDING`，R1A-M04/M05/M06 未满足。
2. 产品 DOM 把 copy button 与 textarea 同时包在同一个 `label` 内，控件关联和 accessible name 含糊；应使用独立 `id/htmlFor` 并给 copy button 唯一稳定的 accessible name，不能继续只换脆弱 selector。
3. M04 存在潜在假绿：冻结矩阵要求覆盖缺中文/负向负例，但 provider 当前可生成空 `text_zh`、`negative`，harness 只要求 English 非空和 image prompt 等于 English。
4. 控制面候选曾不统一：Stage、授权、checkpoint、receipt 绑定 `f901c492...`，execution-control 仍记录祖先 `36f42ebb...` 且 independent-review 指向 live-02；裁决前必须统一。

## Minor

1. provider ledger 的输入哈希是预处理 PNG，证据未显式记录 original sample → normalized provider input 映射，也未把 call_id 与 job/model-run ID 直接关联。
2. wrapper 已证明 child exited、wrapper exit 0 和端口清空，但 child `exit_code` 为 null；建议补齐终态字段。

## 分母与清理

- R1A-M01：候选绑定离线边界证据存在。
- R1A-M02：一次真实 provider 成功成立，完整语义/raw 同 run 独立复核材料不足。
- R1A-M03：分析前 manual export、四字段和 Unicode 产物存在。
- R1A-M04/M05：FAIL/INCOMPLETE。
- R1A-M06：NOT_RUN。
- R1A-M07：清理与隐私部分通过，完整浏览器网络 oracle 未生成。

backend、Ollama 均停止，model 已卸载，Windows/WSL 端口为空，隔离 runtime 已删除，cleanup error 为 0。未发现源媒体、base64、私有路径、Cookie、秘密、非 loopback 地址或误杀非 owned 进程的证据。

## 精确停止原因

```text
NO_GO:
BROWSER_SCOPED_ENGLISH_COPY_LOCATOR_TIMEOUT
+ ADOPTED_CLIPBOARD_AND_EXPORT_ORACLES_NOT_COMPLETED
+ RESPONSIVE_SCREENSHOTS_AND_BROWSER_RESULT_NOT_GENERATED
+ R1A-M04_R1A-M05_R1A-M06_UNSATISFIED
+ M04_MISSING_ZH_NEGATIVE_FALSE_GREEN_RISK
+ CONTROL_PLANE_CANDIDATE_IDENTITY_AMBIGUITY
+ AUTH_LIVE_05_EXPIRED
+ R1A_CORRECTED_FULL_RECHECK_BUDGET_EXHAUSTED
+ MAJOR_INDEPENDENT_FINDINGS_PRESENT
```

最小纠偏：修复 label/button/textarea 可访问性结构和稳定 locator；增加中文/负向非空 oracle；统一候选 SHA；重新执行离线 checkpoint。任何后续真实运行都需要项目负责人签发新的显式授权，不得复用 LIVE-05。
