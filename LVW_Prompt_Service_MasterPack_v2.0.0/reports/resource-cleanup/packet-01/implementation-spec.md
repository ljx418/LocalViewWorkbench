# WP-R1-RESOURCE-CLEANUP-01 — 用户优先插入的资源清理

日期：2026-11-19。授权依据：用户明确暂停主干，要求控制面板增加资源清理按钮、完整验证并报告主干进展。本包为兼容辅助增量；不修改原 R1/多镜头固定合同、分母或历史结论，不恢复持久化任务，不代表产品 Stage PASS。

## 源码与权限边界

从主控当前 main（本包创建前 HEAD fe3d1418）派生独立 Orca 工作区。禁止从未验证的持久化候选 23bd8da 合入；其原工作树与未提交改动全部保留。实现负责人为新的可见 ClaudeCode 实例，仅处理本包，与被 429 中止的持久化任务不同。首次 429 立即停止，不重试、不换模型/Harness、不转交 Codex。

允许修改 lvw/backend/app/runtime.py、provider.py、service.py、main.py、resources.py，lvw/frontend/src 下相关控制面板/API/类型/样式，以及对应单测/端到端测试、说明与本包实现收据。允许新增薄的 resource_cleanup owner/helper；禁止泛化成进程管理平台、清空用户媒体/数据库、修改模型准入阈值、修改持久化 owner 或已有公共 Job/Schema。新接口采用兼容增量，不改旧接口语义。

## 冻结行为与接口

- 控制面板新增明确的“资源清理”按钮、进行中状态、结果与失败原因、清理后再次检查入口；人工稿不变。说明下一次分析可能重新装载模型，以及仅清理 LVW 可确认拥有的资源。
- POST `/api/v1/runtime/resources/cleanup`，无用户可控 shell、路径、PID 或模型名参数。复用现有 loopback Host/Origin、X-LVW-Control: local-ui 检查，以及 AnalysisService.runtime_control 串行互斥。禁止有分析/排队任务时清理；并发重复请求明确 RESOURCE_BUSY，结束后可再次点击。
- 同一个资源 owner 负责动作与确认。优先复用已有 provider lease/release：有 LVW lease 时仅释放该 lease；release 返回 false 必须保持 unknown/pending，不能据 HTTP200 或 readiness.loaded=false 判成功。readiness 当前吞掉 /api/ps 错误，不能拿它单独证明资源已释放。
- 没有 lease 时：仅在服务确由 LVW 管理且 native 身份证据有效、模型清单可核实时，允许卸载配置中的精确模型；不同模型/外部服务不操作。若无已加载目标且清单可证，返回 no-op；外部服务/未知归属明确说明未清理，不能伪报成功。不得停止外部 Ollama/Comfy/训练/GUI，不作 kill-all、驱动重置、系统内存清空或文件清理。
- 使用已有 loopback Ollama unload 协议，不执行推理、不拉取权重。清理期限有界（总计不超过 45 秒），用真实 /api/ps 多次核对目标消失。没有可验证终态、原服务失联或采样失败则报告 failed/unknown；不得直接清除 lease 或把未确认资源标为 released。
- 返回独立清理结果：operation_id、status（released/noop/blocked/unknown）、采取的动作、before/after GPU/RAM 数值或 null+采样失败原因、核对状态与当前运行时状态。采样数值是整机观察，不保证下降、不声称释放全部系统内存。UI区分卸载成功与整机仍有外部占用。
- 不删除或重置人工稿、历史 raw、媒体、数据库、模型权重；不自动重启推理。普通 start/reset/stop 与分析仍可继续使用。

## RC01–RC12 固定增量验证义务（不替代原门禁）

1. RC01：通过公开 POST 入口触发生产 cleanup owner，精确目标卸载并确认，before/after 不伪造。
2. RC02：无目标时 noop；未知/损坏/不可用清单不能计成功。
3. RC03：外部服务/其他模型不卸载、不杀进程；没有归属证据时拒绝。
4. RC04：active/queued 分析和并发清理拒绝，控制锁失败后仍可恢复。
5. RC05：lease 释放成功/失败/超时，失败不清 lease、不伪报 released。
6. RC06：Host/Origin/缺控制头/非固定参数负例；无任意 Shell/PID/路径入口。
7. RC07：卸载失败、失联、轮询到期和资源采样失败可解释且有界；采样失败与模型终态分别报告。
8. RC08：UI 实际点击→公开 API→结果展示；禁用/等待/失败/重试状态，保留人工稿。
9. RC09：原 start/reset/stop、媒体上传/分析/显式采纳/导出相关回归，无旧功能门限缩水。
10. RC10：前端 typecheck、前端测试、build，后端相关子树测试真实退出码与日志。
11. RC11：候选封存后有限本机验证：隔离服务/端口/数据根，实际 UI 清理与真实本地 Ollama 资源核对；无有效目标则只能证明 noop，不能冒充真实释放。必要模型装载/图片分析必须另派生母授权范围内精确子收据后执行，最多一次非私有固定图片分析，不预先启动。不得读取私人媒体。
12. RC12：独立工作区复核候选/证据/清理证明；root 审查后才能交付。真实资源未知必须如实阻断，不以 CPU mock 代替。

## 本次派发边界与收据

先只实现源码和测试、审阅已有运行工具；**本次 source dispatch 不运行 Python 产品导入/pytest/Node 构建、模型/GPU/网络/原生程序**。候选提交后返回文件列表、合同变化、拟执行的精确验证命令、环境/隔离/预算和风险，标为 READY_FOR_VALIDATION，不写 PASS。root 收到后绑定候选、适用执行器/guard 和子授权，连续推进测试、真实验证与独审。这样不会把旧 N1 的 SQLite/网络禁用 guard 错用到 FastAPI/UI 测试。

实现代码与定向测试合并为一个小批次，不为每个按钮状态新建纠偏 Stage。若安全边界不足，用一个清晰问题报告升级，避免循环猜测。
