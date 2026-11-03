# V0-S2 Risk And Authorization Register

| ID | 风险/动作 | 初始状态 | 处置 |
|---|---|---|---|
| DEP-S2-01 | R1a 当前候选尚未完成 | WAIT_DEPENDENCY | 不激活 V0-S2，不并发写 owner |
| AUTH-S2-01 | 离线实现与测试 | PREPARED | 激活 packet 后授权 |
| AUTH-S2-02 | testSource/FFmpeg/Comfy/Ollama/GPU/headless | PROGRAM_SCOPED | 每次运行先生成候选绑定子授权收据 |
| R-S2-01 | 全片解码/OOM | Fatal | ffprobe 先验、CPU 有界采样、4 帧/768px/自有临时配额 |
| R-S2-02 | 路径或 reparse 越界 | Fatal | 允许根、realpath/handle 校验、fail-closed |
| R-S2-03 | 取消后晚到覆盖 | Fatal | run token + cancel epoch + terminal CAS |
| R-S2-04 | 清理误杀外部进程 | Fatal | 仅自有句柄；外部占用只报告 BUSY |
| R-S2-05 | 资源统计假绿 | Major | 固定 10+10 分母、逐次原始记录、P95 独立复算 |
| R-S2-06 | 用帧数组单测替代视频文件 | Major | 真实 MP4/MOV 公共入口与 frame manifest |
| R-S2-07 | 现成 PyAV/FFmpeg 包存在但原生兼容性未知 | Major / OPEN | 封存安装字节；Windows Comfy 公开节点先做无模型组件验证，再执行完整真实分母；不把库元数据当功能 PASS |
| R-S2-08 | 原生视频 UI 的 raw/建议/人工稿与忙时导出尚未验证 | Major / OPEN | 真实浏览器验证显式采纳、草稿不覆盖和无需 GPU 队列的人工导出；不能仅用 API 返回 text 列表代替体验 |

禁止下载、云/付费服务、非 loopback、私有媒体、Cookie、现有浏览器 profile、可见浏览器自动化、永久配置和发布。远端推送仅在 Stage 完成人工验收后按 AGENTS.md 第16条立即执行；不允许提前推送、强推或覆盖历史。

当前处置追加记录：DEP-S2-01 已由 `reports/r1a/human-signoff-r1a-live-08.json` 关闭，表中保留最初依赖状态。R-S2-08 的 raw/建议、显式采纳、CPU 人工编辑/复制/导出已进入离线验证，真实浏览器与完整 Stage 验收仍为 NOT_RUN，不能关闭 Major 风险。原生组件 01 因启动前 GPU 超限停止，未启动服务或调用模型，终态见 `reports/v0-s2/native-component-01/receipt.json`；不得终止外部占用或自行追加尝试预算。

R-S2-09：Major / OPEN。默认逐帧卸载不能当作热基准；需临时且有归属证明的热配置、逐调用驻留证据、结束恢复与真实延迟。裁决依据见 reports/v0-s2/warm-benchmark-evidence-gap-01.md；不得用 hot 标签、减去加载时间或缩分母制造通过。

1.0.28 授权状态澄清：项目负责人已通过 AUTH-PROGRAM-V1-LOCAL-01 授予 S2 完整固定分母及纠正复验范围。PROGRAM_CHILD_REQUIRED 表示可在范围内派生一次性子收据，不能跳过整包离线门禁、绑定、预算或清理。执行状态只读 plans/execution-control.json；冻结 packet 不因每个运行状态变化而改写。完整命令见 reports/v0-s2/full-parent-executor-decision-01.md。原生组件/前端绑定/样本准备各自两槽均已消耗，不得另加准备尝试。
