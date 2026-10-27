# Runtime State Interface

本目录只定义运行态布局，不保存真实秘密或私有证据。

- `task-queue/`：跨项目队列快照；生产部署应迁移到项目外受控状态存储。
- `receipts/`：结构化收据引用；大型原始日志和私有数据只保存外部 URI/hash。
- `metrics/`：成本、耗时、首次通过率、返工和审查积压。

提交仓库前必须脱敏。Cookie、token、原始私有媒体、浏览器 profile、模型密钥和绝对私有路径禁止进入这些目录。
