# R1a Risk And Authorization Register

| ID | 风险/动作 | 状态 | 处置 |
|---|---|---|---|
| AUTH-R1A-01 | 离线代码、测试、构建 | AUTHORIZED | 限冻结路径与 offline cache |
| AUTH-R1A-02 | 本地 Ollama、testSource、headless Chromium | WAIT_AUTH | 绑定候选、Harness、样本、端口、一次调用和清理 |
| R-R1A-01 | 浏览器直连/云回退 | Fatal | 同源 API、pre-dispatch 阻断与静态扫描 |
| R-R1A-02 | 建议覆盖人工稿 | Fatal | 显式采纳与 dirty-draft 负例 |
| R-R1A-03 | 自定义指导覆盖系统边界 | Major | 有界枚举、800 字、低优先级模板与合同负例 |
| R-R1A-04 | 终止非自有 Ollama | Fatal | `external` 状态、禁用控制、仅持有本轮子进程句柄 |
| R-R1A-05 | 旧证据绑定新候选 | Major | SHA 绑定、新鲜运行、隔离复算 |

不授权下载、云/付费服务、可见浏览器、私有媒体、永久配置、远端推送或发布。
