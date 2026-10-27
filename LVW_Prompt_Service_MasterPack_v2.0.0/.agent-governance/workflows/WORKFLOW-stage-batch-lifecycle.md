# WORKFLOW: Stage Batch Lifecycle

版本：1.0.0  
日期：2026-10-27  
状态：Review

## Actors and prerequisites

门禁负责人冻结 Stage；实现负责人实现；可信执行器运行确定性检查；隔离审查者复算；人类授权高风险动作并签署体验。开始前必须存在基准候选、产品权威、固定分母、Stage Packet manifest 和单 owner Workpack。

## Workflow tree

1. **Freeze**：校验 packet、owner、范围、合同、分母、Oracle、预算和授权。
   - 缺字段或 hash 漂移：`NO_GO`，无实现副作用。
   - 需要高风险动作：`WAIT_AUTH`，不得启动该动作。
2. **Dispatch**：只把依赖满足、资源隔离、预算可用的 Workpack 置为 `READY`。
   - worktree/端口/数据库冲突：保持 `BLOCKED`，释放已取得的锁。
3. **Implement**：owner 在隔离候选中修改，定向自检，生成 `READY_FOR_REVIEW` 收据。
   - 两次同路线无新证据：停止并交接。
   - 合同、分母或授权变化：立即停止，返回 Freeze。
4. **Automated acceptance**：可信执行器绑定候选、规格和验收 hash，运行固定集合。
   - 任一 fail/blocked/skipped/not-run：不进入 PASS，普通缺陷返回 Implement。
   - 预算耗尽：`WAIT_BUDGET`，不改变分母。
5. **Independent review**：隔离审查者从公共入口复算生产路径、负例、终态和清理。
   - Fatal/Major：`CHANGES_REQUIRED`，一次性纠偏包返回 Implement。
   - 审查环境无效：`BLOCKED`，保留原始诊断。
6. **Gate decision**：门禁负责人核对候选、CI、独立审查、风险和必要签署。
   - 全满足：Stage `PASS`。
   - 已证实阻断缺陷：`NO_GO`。
   - 外部前置缺失：`BLOCKED`。
   - 缺预算/授权：`WAIT_BUDGET/WAIT_AUTH`。
7. **Closeout**：封存不可变收据、更新当前坐标和指标；只释放下一 Stage 的规划或已授权动作。

## Handoff contract

输入：冻结 packet manifest、candidate SHA、acceptance hash、gate version。成功输出：结构化收据和裁决。失败输出必须含稳定状态、可复现证据、retryable、下一 owner 和精确停止原因。任何超时都视为未验证，不计 PASS。

## Cleanup inventory

| Resource | Owner | Failure cleanup |
|---|---|---|
| worktree | dispatcher | 保留有价值差异；明确归档后再回收 |
| port/process | Workpack owner | 只清理由本轮 PID/owner marker 证明的资源 |
| test DB/temp/profile | Workpack owner | finally 清理并生成证明 |
| external/private run | human-authorized owner | 按授权预算停止、脱敏、撤销临时凭据 |
| evidence | trusted executor | 保留失败原始记录，不改写为正例 |

## Test cases

| Case | Expected |
|---|---|
| 完整冻结 packet | verifier PASS，仅代表治理就绪 |
| 删除一个固定验收 ID | verifier FAIL |
| implementer 与 reviewer 同会话 | verifier FAIL |
| skipped 被计为 PASS | verifier FAIL |
| 缺预算 | WAIT_BUDGET，不降低分母 |
| 缺外部授权 | WAIT_AUTH，不启动外部动作 |
| 候选改变而沿用旧 evidence SHA | verifier FAIL |

## Assumptions and reality status

- 当前仓库没有产品实现和首个 Git commit；并行 worktree 只定义规则，尚不可执行。
- 当前只验证治理 packet 与负例拒绝能力，未连接 Windows/Comfy/Ollama/GPU。
- 独立审查尚未发生，因此状态保持 Review，不能升级为 Approved。
