# Gate Decision Template

```text
Project / Stage:
Candidate SHA:
Stage Packet manifest:
Spec version / acceptance hash / gate version:
CI receipt:
Independent review:
Human signoff, if required:
Open Fatal / Major / Minor:
Decision: PASS | NO_GO | BLOCKED | WAIT_BUDGET | WAIT_AUTH
Allowed claim:
Forbidden claim:
Next owner:
Required authorization:
Evidence root:
Exact stop reason:
```

`PASS` 仅在全部必要条件满足时使用。Codex Stage PASS 不替代人类生产发布签署。

停止报告在上表前增加完整开发大纲：Stage / 子阶段已完成数与总数 / 实现状态 / 机器验收 / 独审与人工签署 / 当前Stage标记。由 `plans/execution-control.json` 的 development_outline 填写，不能复制旧报告主观更新百分比。再给原十字段，细则见 docs/24。
