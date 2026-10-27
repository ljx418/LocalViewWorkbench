# Stage Packet Template

必须建立目录 `stages/<stage-id>/`，包含：

```text
00-coordinate.md
01-scope-and-non-goals.md
02-architecture-and-ownership.md
03-workpack-plan.md
04-acceptance-matrix.md
05-risk-and-authorization-register.md
06-implementation-prompt.md
07-checkpoint-plan.md
stage-control.json
PAYLOAD_MANIFEST.sha256
```

冻结前检查：基准候选、权威文件、合同版本、固定分母、阈值、owner、允许/禁止文件、命令、Oracle、负例、清理、预算、授权分类、停止条件、下一责任人均非空。Manifest 必须覆盖本目录除自身外的所有冻结载荷。
