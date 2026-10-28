# V0-S1 Workpack Plan

## WP-S1-00：基线与合同夹具

Owner：可信执行器。依赖 V0-S0 正式出口和候选 commit。锁定 `v0-result.schema.json`、`errors.json`、runtime defaults、节点绑定和 S1 固定分母。建立有效/无效结果、20,000 字草稿、非法 JSON、超限图片及晚到回调夹具。只做离线确定性检查。

## WP-S1-01：独立人工编辑与导出

Owner：`codex_isolated_implementer`（V0 临时代行）。实现纯 CPU 草稿状态、四输出视图、标签、复制、TXT/JSON 导出和显式来源标识。Ollama 停止时必须工作；未分析、空人工字段或没有内容备注仍可导出合法的 `manual/not_requested` 结果，不伪造分析成功，也不引入审批状态。

## WP-S1-02：图片预处理与状态隔离

Owner：`codex_isolated_implementer`。实现单图字节/像素/格式限制、EXIF、RGBA 策略、源 hash 与预处理记录；实现 run token、raw/suggestion/draft 隔离、draft epoch 和异常不覆盖。只运行单元、Schema、负例和静态检查。

## WP-S1-03：真实图片公共入口与工作流

Owner：`codex_isolated_implementer`。依赖 S0 的正式 live binding 和逐次本地运行授权。连接已验证的 `LVWImagePromptBridge` public `/prompt`/`history` 与本地 Ollama；生成同一真实图导出的 `.ui.json` 和 `.api.json`，以及人工 workflow/等价面板。不得手写不存在的 class type。

## WP-S1-04：Stage Checkpoint

Owner：可信执行器运行冻结测试；`codex_isolated_reviewer` 复算；root Codex 裁决。统一执行 V0-A01/A03/A04/A05/A08、子树回归、生产接线、失败/恢复、秘密和路径扫描。修改候选后关键证据必须对新 SHA 重跑。

同一冻结 Stage 内 WP-S1-01 至 WP-S1-03 可按依赖连续实现；每个 Workpack 保留局部收据，但只在 WP-S1-04 进行一次 Stage 集中验收。
