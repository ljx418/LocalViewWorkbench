# V0-S1 Draft Implementation Prompt

```text
本文件是草案，当前禁止执行。唯一当前坐标仍为 V0-S0 / WAIT_AUTH。

只有在以下条件全部满足后，Codex 才能冻结并签发正式 S1 prompt：
1. V0-S0 已得到 STAGE_BASELINE_COMPLETE；
2. 有真实 live registry/node binding 和复用裁决；
3. 将 S0 正式出口 commit 写为 S1 accepted baseline；
4. S1 packet 已改为正式版本并重新生成 manifest；
5. 隔离 worktree、owner、预算和外部授权已记录。

正式执行时先读 AGENTS.md、S1 全 packet、docs/13_V0_IMPLEMENTATION.md、contracts/v0-result.schema.json、contracts/errors.json、config/runtime.defaults.json、plans/acceptance_cases.json。

实现顺序固定：纯 CPU 人工编辑/导出 → 图片预处理与状态隔离 → 真实图片公共入口/工作流。不得改变公共合同、固定分母、阈值或 owner。不得把 suggestion 自动写入 draft；不得手写未验证 class_type；不得调用云回退；不得删除/跳过失败测试。

每个 Workpack 输出变更文件、合同变化或 none、测试命令/退出码、生产路径、负例、候选 SHA、原始证据、风险和停止原因。自检只能标 READY_FOR_REVIEW，不能宣布 Stage PASS。
```
