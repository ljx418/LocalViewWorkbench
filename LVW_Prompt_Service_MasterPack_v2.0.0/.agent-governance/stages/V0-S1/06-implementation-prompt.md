# V0-S1 Implementation Prompt

```text
本文件已冻结。激活提交后只允许 WP-S1-00/01/02 的离线仓库实现；S0 live 授权已经过期，不得继承。WP-S1-03 的目标 Comfy 安装、Ollama 调用、真实图片或可见浏览器动作必须等待新的逐次授权。

正式执行时先读 AGENTS.md、S1 全 packet、docs/13_V0_IMPLEMENTATION.md、contracts/v0-result.schema.json、contracts/errors.json、config/runtime.defaults.json、plans/acceptance_cases.json。

实现顺序固定：纯 CPU 人工编辑/导出 → 图片预处理与状态隔离 → 真实图片公共入口/工作流。不得改变公共合同、固定分母、阈值或 owner。不得把 suggestion 自动写入 draft；不得手写未验证 class_type；不得调用云回退；不得删除/跳过失败测试。

每个 Workpack 输出变更文件、合同变化或 none、测试命令/退出码、生产路径、负例、候选 SHA、原始证据、风险和停止原因。自检只能标 READY_FOR_REVIEW，不能宣布 Stage PASS。
```
