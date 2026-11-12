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
