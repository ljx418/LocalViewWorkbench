# V0-S1 Coordinate

```text
Project: lvw-prompt-service
Design: 2.0.0
Target version: V0
Prepared stage: V0-S1 / 图片与独立人工路径
Packet version: 1.0.0
State: WAIT_AUTH / OFFLINE_REPOSITORY_ONLY
Active coordinate: V0-S1 / WP-S1-02 / GATE2_WORKPACK_RECEIPT
Last passed gate: WP_S1_02_IMAGE_STATE_OWNERS_SEALED
Exact stop reason: WAIT_AUTH_WP_S1_03_NEW_ONE_SHOT_SCOPE_REQUIRED
Product cases: NOT_RUN
Prepared-against commit: dfb00ad462d94628f1aa22045061f66a7629ec01
Product bridge candidate: 138b4486fdaeb8d207ef6b5efb63a09865f174b9
Accepted S1 baseline: dfb00ad462d94628f1aa22045061f66a7629ec01
```

本目录是已冻结的 V0-S1 Stage packet。冻结提交完成前，它不改变 `plans/execution-control.json` 的唯一当前坐标；激活后只授权 packet 允许路径内的离线仓库工作，不能继承 S0 的 live 授权。

V0-S0 已以 `dfb00ad...` 正式闭合：public `/prompt`/`history` 可达 `LVWImagePromptBridge` / `LVWVideoFramesPromptBridge`，correction-16 独立复审 Fatal/Major/Minor 均为 0。S1 可执行 WP-S1-00/01/02 的离线实现；WP-S1-03 的目标 Comfy 安装、Ollama 调用和真实图片运行仍须新的逐次授权。产品固定验收仍为 `NOT_RUN`。

WP-S1-00 已以候选 `457b2e8...` 封存：合同/绑定/固定分母、合法与非法结果、20,000 字、图片 exact/one-over 以及晚到回调夹具通过 8/8 离线测试。当前进入 WP-S1-01；这不是产品用例 PASS。

WP-S1-01 最终候选 `a9c816e...` 已封存：公共 `LVWManualPromptOwner`、纯 CPU 七输出、复制、原子 TXT/JSON 导出及路径边界通过 45/45 离线回归；外部动作均为 0。目标 Comfy 导入和系统剪贴板仍为 `NOT_RUN/WAIT_AUTH`，五项产品验收未提升。当前进入 WP-S1-02。

WP-S1-02 最终候选 `2776a0c...` 已封存：公共 `LVWControlledImageInput` 与 `LVWDraftStateOwner`、解码前像素门禁、EXIF/RGBA/缩放记录、run-token 与 draft 隔离通过 59/59 离线回归。当前停在 `AUTH-REQUEST-V0-S1-WP-S1-03-01`：在项目负责人批准并形成正式授权记录前，不准备 WP-S1-03 候选，也不执行目标安装、GPU/端口探测、Ollama 或真实图片运行。
