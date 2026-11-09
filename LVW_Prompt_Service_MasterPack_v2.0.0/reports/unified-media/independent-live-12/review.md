# live12 独立只读验收

**建议 NO_GO：固定10项为9 PASS / 1 FAIL；Fatal0 / Major1 / Minor0。UM-04真实时序语义失败。** 这是隔离独审建议，不是Stage裁决、人类体验签署或整个V1验收。

候选 `52736c9aabc769d49bbb9662f878d705c32e5ed2`，R1 packet1.0.3 / gate lvw-unified/1，精确raw哈希见raw-hashes.json。先读规范/候选，收到执行终态信号后才读live12。候选gitblob导出后只运行CPU原语与受控生产owner检查；未调用GPU/model/API服务/browser/媒体probe/video decode/下载，未写任何执行账本，未继承实现者或旧审查PASS。

## Major M1 — UM-04

原始模型 `observations[4]` 说红框相对网格位置“appears visually consistent across all source frames”；`inferences[1]` 以“red subject and grid appear stationary”为前提，把差异解释为lighting/compression的可能性。另一方面，`inferences[2]` 承认consistent x-offset suggests systematic spatial shift。技术字段仅复述x-offset与subject stationary，未修正错误的相对位置观察。unknown/物理相机unverified是允许的，但不能冲销已作出的错误观察与不受证据支持的优先因果解释。

本独审没有重新解码视频。直接把已有无损PNG像素序列化为PPM，四个SHA逐一精确匹配live12的FrameRef及provider ledger，故这些像素是本轮实际源帧的字节等价图像证据，不是沿用旧结论。红框bbox四帧均为 `[322,156,445,301]`；y=20网格首竖线x为 `88.5→69→50→30.5`，每段约左移19像素，网格相对红框位置显著变化。眼见四帧图与整数测量一致。这里仅裁定图像坐标中可见结构变化；不要求断言真实相机右移，也不把图像注册当物理相机分类。

独立枚举128×77灰度图、±10共同窗的441个偏移，得到每段next-to-previous `(3,0)`、唯一最优、误差降低约72.5%/77.9%/74.0%；与ledger逐字段一致。3是**降采样图像中用于把下一帧对齐到上一帧的偏移**，不是原视频精确3像素，更不是物理主体/相机运动。模型只提3 pixels而未说明坐标语义，不能据此补成正确的主体/网格关系。模型的34%左右变化比例本次正确，但语义关系仍错误。

输入保留F源完整帧+D明确派生图，一次Provider单PNG重建hash与ledger相同；没有写入样本答案、没有把CPU复算篡为原始模型结果。raw/parsed关键字段严格对应。建议修复路线须解决可见相对位置观察及因果自洽问题，不能只增加offset/unknown词。

## 其他逐项事实

固定10项生产owner→oracle→证据见coverage.json的10条items（rows为同一固定集合）。3 attempted推理含取消，2 completed；3lease各有3个稳定空inventory/GPU恢复样本；峰GPU21217MiB、RAM最低10032MiB。原生PID27672/birth639298255854124545/nonce f7f76b0011ca4d92a735b14fbfc59c44一致并exited；原API PID/birth已消失，/proc监听表无18780/11434，原launcher日志有API退出和owned temp删除。headless browser closed、0页面错误/外部请求，native NO_CLOUD/loopback有原始日志。没有重启服务补证。

真实duration/corrupt负例均422；按RUNTIME01 scope，其他边界/排队准备取消使用候选gitblob的生产owner+受控外部原语CPU检查，**未声称这些都是模型调用或真实媒体解码**。CPU10项通过（其中exact/one-over输入、空上传/无排队/无provider/无文件、少帧不复制/重复PTS拒绝、排队取消/准备清理/晚到不发布/错误资源终态）。原public采纳导出关联已逐字段复核，取消不会覆盖既有人工稿/来源，模型停止仍能编辑并导出TXT/JSON。

所有frozen/sample/tool字节哈希通过。START_LVW.cmd工作树为CRLF，Git blob为LF：二者仅行尾不同、规范化完全相等，实际执行字节与授权hash精确匹配，已在脚本明确保留这项比较。SQLite使用mode=ro；live12账本3动作/1完整/56秒、active0；全局15/1024动作、5/24完整、1163/172800秒、0 active。56秒是终态SQLite/收据记录值，未把模型17秒或provider跨度当全部运行时长。

## 十字段状态

- 当前坐标：R1 / WP-R1-U3，live12隔离独审已完成。
- 本批完成：固定10项独审、10项CPU检查、原始哈希/源/工具/样本/全局账本复算。
- 最后通过门禁：本轮身份/原始链路/资源/清理检查；不授予产品Stage PASS。
- 当前阻塞门禁：UM-04时序语义 Major1。
- 全局路线位置：V1前置最小图视频统一切片；旧V0-S2人工前置仍依坐标保留。
- 剩余工作：纠正模型真实语义后按授权有限复验与新独审；通过后实际人工体验签署。
- 下一责任人：gate owner接收NO_GO并决定技术路线。
- 所需授权：本次只读独审无新增权限；COMPLETE03仍有效，不代人类签署。
- 证据目录：reports/unified-media/independent-live-12。
- 精确停止原因：独审已完成，UM04_FAIL_VISIBLE_RELATIVE_POSITION_DENIAL_AND_UNSUPPORTED_CAUSAL_INFERENCE。

## V0–V3完整开发大纲

以下只抄唯一execution-control.development_outline的完成计数，非主观工时，非本独审重新签署既有Stage。

| Stage | 子阶段 | 完成/总数 | 机器 / 独审 / 人签 |
|---|---|---|---|
| V0-S0 | 基线探索 | 1/2 | NO_GO_HISTORICAL / COMPLETED_WITH_BLOCKERS / NOT_SIGNED |
| V0-S1 | 图片与独立人工 | 5/5 | ACCEPTED_SCOPE_ONLY / COMPLETED / APPROVED |
| R0 | 独立服务复核 | 1/2 | SINGLE_IMAGE_SUBSET_ONLY / NO_SEPARATE_R0_VERDICT / NO_SEPARATE_R0_SIGNOFF |
| R1a | 单图React/FastAPI | 5/5 | ACCEPTED_SCOPE_ONLY / COMPLETED / APPROVED |
| V0-S2 | 视频与资源控制 | 7/8 | COMPLETE_FIXED9_PASSED / COMPLETE_FATAL0_MAJOR0_MINOR0 / PENDING |
| V0-S3 | 离线质量与增量包 | 0/6 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R1 | 人工业务骨架 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R2 | 任务与正式运行包 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R3 | 镜头资产与检索 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R4 | MCP与恢复 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5a | 证据与建议合同 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5b | 受控生成交接 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5c | 集成与完整交付 | 0/4 | NOT_RUN / NOT_RUN / NOT_SIGNED |
