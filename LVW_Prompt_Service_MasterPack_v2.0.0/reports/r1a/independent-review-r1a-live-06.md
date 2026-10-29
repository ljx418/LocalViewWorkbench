# R1a LIVE-06 Independent Review

结论：**Fatal 0 / Major 0 / Minor 3**。建议允许进入 R1a 人工体验门槛；这只表示 WP-R1A-04 工程出门条件满足，不代表 R1a Stage PASS、V1 PASS 或发布批准。

本审查为隔离、只读、离线复算；未修改候选，未启动服务、Ollama 或浏览器，未访问网络。

## 身份与预算

- 候选 `d1d30480...` 及 live、browser、runtime guard、Ollama wrapper 四个 harness 与授权哈希一致。
- request、offline checkpoint、固定分母、样本、模型、端口和预算全部匹配。
- attempts/provider/browser 为 `1/1/1`，没有第二次模型调用、云调用或非 loopback 请求证据。
- LIVE-06 授权已正确过期并反向绑定 terminal receipt，不得重跑。

## 七项分母复算

- `R1A-M01 PASS`：候选绑定媒体边界检查通过，真实页面显示授权图片、尺寸、文件名和原始哈希前缀。
- `R1A-M02 PASS`：同一 call-id 仅一组 provider started/completed(success)，Ollama 同期仅一次 `/api/chat` 200。
- `R1A-M03 PASS`：manual export 在分析提交前完成，四字段和 Unicode tags 精确保留，当时 provider 调用为 0。
- `R1A-M04 PASS`：dirty draft 未被模型覆盖；确认后才显式采纳；四输出非空；clipboard、JSON、TXT 逐字段一致；raw 默认折叠。
- `R1A-M05 PASS`：真实 React/FastAPI 同源页面；Enter 启动分析；reduced-motion 存在；360/1280/1920 无水平溢出，截图无明显裁切、重叠或不可操作布局。
- `R1A-M06 PASS`：图像主体、发髻、眼镜、红唇、蓝白插画衬衫和绿色图标与输出基本一致；观察、推断和未知项分离，结果可用。
- `R1A-M07 PASS`：非 loopback 请求预阻断且实际列表为空；服务 owned；模型卸载、双域端口为空、runtime 删除、cleanup error 为 0；未发现隐私泄漏。

## Minor

1. `unknowns` 称人物性别未知，但提示词使用“年轻女性/young woman”，存在轻微语义不一致，人工体验时应重点确认。
2. provider ledger 保存预处理 PNG 哈希；尚未直接持久化 original → normalized 哈希映射。
3. wrapper 已证明 child exited、wrapper exit 0 和端口清空，但 child `exit_code` 为 null。

## 精确停止原因

```text
READY_FOR_R1A_HUMAN_EXPERIENCE_GATE:
R1A_M01_THROUGH_M07_INDEPENDENTLY_VERIFIED
+ REAL_PROVIDER_CALL_EXACTLY_ONE
+ FOUR_OUTPUT_EXPORT_CLIPBOARD_LAYOUT_NETWORK_ORACLES_PASS
+ OWNED_CLEANUP_AND_PRIVACY_PASS
+ FATAL_0_MAJOR_0
; STOP_BEFORE_HUMAN_SIGNOFF
; DOES_NOT_AUTHORIZE_R1A_STAGE_PASS_OR_V1_PASS
```
