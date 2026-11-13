# Workpack Template

```yaml
project_id:
stage_id:
workpack_id:
objective:
depends_on: []
implementation_owner:
allowed_paths: []
forbidden_paths: []
public_contract_change: none
acceptance_ids: []
commands: []
oracles: []
negative_cases: []
resource_locks: []
budget:
  currency:
  max_amount:
  max_retries: 2
evidence_required: []
stop_conditions: []
completion_state: READY_FOR_REVIEW
```

实现者只能修改冻结范围。需要改变公共合同、验收分母、阈值或所有权时立即停止并提交变更请求。

ClaudeCode任务必须附带的停止条件：首次HTTP 429立即停止并报告WAIT_BUDGET，保存真实错误和候选状态；禁止自动重试、改路由或由Codex接手。只有用户针对本次中断明确授权Codex接手后，才可在新记录的有限范围内恢复实现。完整规则见[模型路由与预算政策](../routing-policy.md)。

## Agent 生命周期（派生前与收尾必填）

- 精确工作区/dispatch/终端：
- 派生前容量检查命令、退出码与快照（单空间1、项目3，未知占槽）：
- 当前唯一实现/审查责任人：
- 前任归档及物理退出证明（替换时）：
- 本子阶段完成后的输出归档、worker-release/close收据：
- 未回收窗口及原因/下一动作：

默认不keep-open，当前执行窗口可见；不能用改名/新任务绕过容量。FIRST429立即停止规则见routing-policy.md。

## 验证命令与边界（执行前冻结）

- 精确argv/选中nodeids、候选/guard源码hash、预算与日志位置：
- guard先于候选/pytest插件导入的证明与禁止的子进程/网络/SQLite行为：
- 额外兼容回归是否允许及对应主控ACK（缺失即禁止）：
- 真实动作计数与被拒尝试分开；counter之外辅助动作单列，不以旧counter不变宣称零动作。
