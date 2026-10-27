# LVW Agent Governance

版本：1.0.0（2026-10-27）

本目录把多项目、多 Agent 协作规则接入现有 MasterPack。它只管理“谁可以做什么、候选如何绑定、证据如何生成、Stage 如何裁决”，不复制或改写产品权威。

## 权威顺序

1. 用户当前明确授权。
2. `docs/00_POSITION_AND_ADR.md` 与批准的 ADR。
3. `contracts/`、`plans/requirements.json`、`plans/acceptance_cases.json`、`plans/release_gates.json`。
4. 当前冻结的 `.agent-governance/stages/<stage-id>/`。
5. 本目录的通用治理规则与模板。
6. `legacy/`，只读历史。

冲突不得静默覆盖。公共合同、固定分母、阈值或角色权限变化必须新建变更记录，由门禁负责人裁决并重新冻结 Stage Packet。

## 文件关系

- `roles.md`：角色、权限和四权分离。
- `routing-policy.md`：任务路由、预算和升级。
- `stage-gates.md`：Stage、Workpack、候选和门禁状态机。
- `parallel-execution.md`：跨项目队列、worktree 与资源隔离。
- `anti-false-green.md`：生产路径、证据和反假绿规则。
- `workflows/`：阶段生命周期的可测试工作流规范。
- `templates/`：可复用交接、收据、审查和裁决模板。
- `stages/V0-S0/`：首个真实 Stage Packet；当前只冻结流程，未执行目标机验收。
- `runtime/`：可变队列、收据和指标的接口说明；实际运行数据默认不提交源码仓库。
- `project-registry.json`：跨项目调度的项目入口；这里只登记LVW，不扫描或接管其他项目。
- `plans/execution-control.json`：唯一当前坐标。
- `tools/verify_governance.py`：确定性制度校验和反假绿负例自测。

## 固定状态边界

产品用例继续只使用 `NOT_RUN/PASS/FAIL/BLOCKED`。执行调度使用 `DRAFT/READY/RUNNING/READY_FOR_REVIEW/CHANGES_REQUIRED/VERIFIED`。Stage 裁决使用 `PASS/NO_GO/BLOCKED/WAIT_BUDGET/WAIT_AUTH`。三类状态不得互相冒充。

## 最小闭环

```text
冻结 Stage Packet
-> 派生 Workpack
-> 隔离实现
-> 实现收据
-> 受控自动验收
-> 隔离独立复算
-> Codex 门禁裁决
-> 必要的人类签署
```

运行：

```bash
python3 tools/verify_governance.py
python3 tools/verify_governance.py --self-test
```

两条命令只验证制度结构和负例拒绝能力，不是 LVW 产品验收。
