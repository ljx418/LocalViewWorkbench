# V0-S1 Draft Acceptance Matrix

拟冻结分母：`V0-A01,V0-A03,V0-A04,V0-A05,V0-A08`

```text
sha256(sorted IDs joined by LF with trailing LF)
4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5
```

| 义务 | 生产路径 | 明确 Oracle | 必须负例/边界 | 持久终态/清理证明 |
|---|---|---|---|---|
| V0-A01 图片真实输入 | 真实 workflow/API → 受控预处理 → 已绑定视觉 owner | 原图 hash 不变；预处理尺寸/策略可追；非 demo raw 与 suggestion | JPG/PNG/WebP；损坏、超字节、exact pixels、one-over pixels、RGBA/EXIF | 一次 run 的状态、error code、证据和 owned 临时文件清理 |
| V0-A03 四输出与合同 | 单次结果 → CPU compile → 视图切换/JSON/TXT | 切换产生 0 次额外推理；JSON 通过 `lvw.v0.result/1`；模型/来源可追 | 英文字段缺失不伪翻译；负向词允许空；额外字段拒绝 | 导出 hash 与候选绑定；不修改 raw |
| V0-A04 独立人工编辑导出 | Ollama 停止 → manual editor → copy/export | 20,000 字可编辑导出；不入 GPU 队列；刷新行为有明确提示 | 空稿、Unicode、中文路径、剪贴板失败、磁盘写失败 | 成功/失败明确；失败不清空草稿；只清理 owned 临时文件 |
| V0-A05 异常不覆盖草稿 | 已有 draft → 分析失败/晚到结果 | draft bytes 与 epoch 保持；raw/错误仍可查看；无无限重试 | 非法 JSON、明确未答、超时、OOM、旧 run token、exact/one-over retry | `failed/partial/cancelled` 不伪装 succeeded；模型清理由 S2 最终验收 |
| V0-A08 无审批前置 | 未分析/空人工字段/无内容备注 → manual export | 导出合法 `lvw.v0.result/1`：`source_type=manual`、`run_id=null`、`analysis_status=not_requested`、`suggestion=null`；无 NSFW 节点、云回退或审批状态前置 | 直接导出、伪造 approval/content-note 状态、通过公开按钮与等价公共入口；审批字段不得改变权限 | 成功导出可回读且无模型/外联；写失败不清空草稿、不留下半文件；错误码可复现 |

S1 的 `PASS` 需要五项全部在同一候选上通过；`SKIPPED/BLOCKED/NOT_RUN` 不能计入 PASS。S1 PASS 不是 V0 发布批准。
