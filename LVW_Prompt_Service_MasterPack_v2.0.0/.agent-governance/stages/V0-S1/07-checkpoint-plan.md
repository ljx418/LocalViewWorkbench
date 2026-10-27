# V0-S1 Draft Checkpoint Plan

## Gate 1：实现内循环

- 纯函数/状态机/Schema 单测。
- exact 与 one-over 输入限额。
- raw/suggestion/draft 隔离和旧 run token 负例。
- 类型、语法、静态秘密/绝对路径扫描。

每次编辑不运行昂贵完整 E2E，不产生 Stage PASS。

## Gate 2：Workpack 收据

每个收据绑定 packet version、acceptance hash、candidate SHA、实现会话、变更文件、真实命令/退出码和未关闭风险。合同变化必须停止并交回 Codex。

## Gate 3：Stage Checkpoint

1. 校验 packet manifest、候选 SHA、固定五项分母和工作流/扩展清单。
2. 执行子树回归与同候选的 V0-A01/A03/A04/A05/A08。
3. 从真实 ComfyUI workflow/API 驱动产品 owner；核对 class type、输入输出和模型调用次数。
4. 在 Ollama 停止时完成 20,000 字人工编辑、复制和 JSON/TXT 导出。
5. 注入非法 JSON、未答、超时、OOM、晚到结果、超限图片和导出写失败；证明 draft 未覆盖、无错误写入和无无限重试。
6. 扫描秘密、绝对私有路径、云回退、任意 URL/文件读取和候选外证据。
7. 独立审查复算 raw/建议/草稿差异和五项分母；Fatal=0、Major=0 才提交 Codex 裁决。

## 允许结论

`PASS`、`NO_GO`、`BLOCKED`、`WAIT_BUDGET`、`WAIT_AUTH`。即使 S1 PASS，V0-A02/A06/A07/A09/A10/A11/A12 仍未完成，V0 不能出门。
