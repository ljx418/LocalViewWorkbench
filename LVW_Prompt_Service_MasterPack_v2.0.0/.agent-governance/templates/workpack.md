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
