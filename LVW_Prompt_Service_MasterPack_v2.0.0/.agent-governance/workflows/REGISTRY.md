# Workflow Registry

## By workflow

| Workflow | Spec | Status | Trigger | Primary actor | Last reviewed |
|---|---|---|---|---|---|
| Stage batch lifecycle | `WORKFLOW-stage-batch-lifecycle.md` | Review | Frozen Stage Packet | Gate owner | 2026-10-27 |
| LVW V0 product runtime | `workflow_specs/*.spec.json` and `docs/13_V0_IMPLEMENTATION.md` | Draft | User media/manual input | LVW/Comfy/Ollama | 2026-10-27 |

## By component

| Component | Files | Workflows |
|---|---|---|
| Product authority | `docs/`, `contracts/`, `plans/` | LVW V0–V3 product lifecycle |
| Governance control | `.agent-governance/`, `plans/execution-control.json` | Stage batch lifecycle |
| Deterministic verifier | `tools/verify_governance.py` | Freeze, handoff and false-green checks |
| Product verifier | `tools/verify_pack.py`, `tools/check_release.py` | Document validation and release evidence |

## By journey

| Actor experience | Workflow | Entry |
|---|---|---|
| Gate owner freezes and dispatches a Stage | Stage batch lifecycle | Stage Packet |
| Implementer delivers one candidate | Stage batch lifecycle | Workpack + isolated worktree |
| Reviewer independently disproves/recomputes | Stage batch lifecycle | Frozen packet + candidate + raw evidence |
| Human authorizes high-risk action | Stage batch lifecycle | `WAIT_AUTH` decision |

## By state

| State | Entered by | Exited by |
|---|---|---|
| GATE0_READY | complete frozen packet | authorized dispatch or NO_GO |
| RUNNING | owner starts eligible Workpack | receipt/checkpoint/mandatory stop |
| READY_FOR_REVIEW | implementer self-check | CI and independent review |
| WAIT_BUDGET | required budget unavailable | replenished budget and same frozen denominator |
| WAIT_AUTH | high-risk action pending | explicit run-specific human authorization |
| PASS | gate owner after complete evidence | next Stage planning only |

未实现产品代码不存在可扫描的生产路由；因此 V0 产品工作流保持 `Draft`，不能标记 `Approved`。
