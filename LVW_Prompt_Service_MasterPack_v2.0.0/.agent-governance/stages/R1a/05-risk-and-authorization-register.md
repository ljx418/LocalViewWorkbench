# R1a Risk And Authorization Register

| ID | 风险/动作 | 分类 | 默认状态 | 处置 |
|---|---|---|---|---|
| PRE-R1A-01 | V0-Min 未通过 | Stage 依赖 | SATISFIED | 绑定现有签署与候选 |
| AUTH-R1A-01 | 仓库代码、测试、构建 | 离线仓库 | AUTHORIZED | 限 frozen allowed paths；npm 仅 offline cache |
| AUTH-R1A-02 | 本地 Ollama 与 testSource 图片 | 外部/私有 | WAIT_AUTH | 固定模型、端点、样本和一次有效运行 |
| AUTH-R1A-03 | 浏览器体验验收 | 高干扰 | WAIT_AUTH | 单独记录进程/端口/清理；人工签署 |
| R-R1A-01 | 临时前端成为第二套系统 | Major | 禁止出门 | 最终 React/FastAPI 目录和合同 |
| R-R1A-02 | 浏览器直连 Ollama | Fatal | 禁止出门 | 同源 API 与静态扫描 |
| R-R1A-03 | 建议自动覆盖人工稿 | Fatal | 禁止出门 | 显式采纳、draft dirty 与负例 |
| R-R1A-04 | 上传路径/解码炸弹 | Fatal | 禁止出门 | 流式字节限额、解码前后像素检查、run-owned 存储 |
| R-R1A-05 | 假 React/旧证据 | Major | 禁止出门 | 真实 build、候选 SHA、fresh run 和独立复算 |

不授权下载、云服务、可见浏览器、付费 Provider、目标软件升级、永久配置写入或远端推送。
