# Stage、候选与门禁

## Stage Packet 冻结

每个 Stage 必须包含：坐标、范围/非目标、架构与 owner、有序 Workpack、验收矩阵、风险/授权、实现提示词、checkpoint 计划、`stage-control.json` 和 `PAYLOAD_MANIFEST.sha256`。

进入实现前必须满足：基准候选已解析、公共合同版本明确、所有 Workpack 单 owner、允许修改范围明确、固定验收分母及阈值冻结、命令和 Oracle 明确、外部动作分类、停止与清理规则明确。

## 状态机

```text
Stage: DRAFT -> GATE0_READY -> RUNNING -> CHECKPOINT ->
       PASS | NO_GO | BLOCKED | WAIT_BUDGET | WAIT_AUTH

Workpack: DRAFT -> READY -> RUNNING -> READY_FOR_REVIEW ->
          VERIFIED | CHANGES_REQUIRED | BLOCKED

Candidate: CREATED -> SELF_CHECKED -> CI_CHECKED -> INDEPENDENT_REVIEWED -> DECIDED
```

`WAIT_BUDGET` 和 `WAIT_AUTH` 是安全等待，不是产品用例结果。`BLOCKED` 必须指出外部前置或不可继续条件。候选任何修改都生成新 `candidate_sha`；旧证据仅在冻结复用规则证明不受影响时复用。

## 执行层次

1. 实现内循环：定向单测、合同负例、类型和必要静态检查；不产生 Stage PASS。
2. Workpack 收据：变更文件、合同变化、命令/退出码、生产路径、风险和停止原因。
3. Stage checkpoint：一次相关子树回归、生产组合、故障/恢复、隐私/资源、PRD 覆盖和集中纠偏。
4. 真实验收：离线门禁全绿后，按明确授权使用真实浏览器、网络、私有数据或 Provider。
5. 独立出门：隔离复算，Fatal=0、Major=0、固定分母完整、必要人类签署存在。

## 裁决

- `PASS`：所有必选检查和签署满足。
- `NO_GO`：存在已证实的阻断缺陷或不可接受风险。
- `BLOCKED`：明确外部前置使验收无法完成。
- `WAIT_BUDGET`：必要执行/裁决因额度不足尚未完成。
- `WAIT_AUTH`：等待一次明确的人类高风险授权。

任何 `FAIL/BLOCKED/SKIPPED/NOT_RUN` 不得计入 PASS。Codex 的 Stage PASS 不自动等于人类生产发布批准。

## 人工验收后立即同步 Git

项目负责人2026-11-03授权：每个 Stage 开发完成并通过人工验收后，立即提交阶段代码、脱敏证据和签署记录，推送到已配置远端及跟踪分支。该授权取代历史远程推送禁令，覆盖已签署 R1a 的补推。禁止强制推送和覆盖远端历史；遇到分支冲突或凭据失败应保留本地提交并报告。远端同步不构成生产发布批准。停止报告须区分本地 commit、远端推送成功与实际发布。
