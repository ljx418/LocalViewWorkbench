# V0-S1 Draft Risk And Authorization Register

| ID | 风险/动作 | 分类 | 默认状态 | 停止/处置 |
|---|---|---|---|---|
| PRE-01 | V0-S0 尚未正式出门 | Stage 依赖 | BLOCKED | 禁止冻结/执行 S1；只允许文档准备 |
| PRE-02 | S1 accepted baseline 尚未由 S0 出口提交确定 | 证据绑定 | BLOCKED | 草案可更新；不产生正式实现或验收收据 |
| AUTH-S1-01 | 在隔离 worktree 写产品代码 | 离线仓库 | 待 Stage 冻结 | 仅允许范围；一个 Workpack 一个 owner |
| AUTH-S1-02 | 读取目标 Comfy 节点 registry/安装测试包 | 外部/私有 | WAIT_AUTH | 限定根、备份、hash、可逆卸载 |
| AUTH-S1-03 | 调用本地 Ollama 与授权图片 | 私有/外部运行 | WAIT_AUTH | 限定样本、端点、模型、两次有效重试和清理 |
| AUTH-S1-04 | 可见浏览器验收 | 高干扰 | WAIT_AUTH | 单独授权、静音、owned PID、结束清理 |
| R-S1-01 | 模型回调覆盖人工稿 | Fatal | 禁止出门 | run token + draft epoch + 负例证明 |
| R-S1-02 | JSON/TXT 导出路径越界 | Fatal | 禁止出门 | 受控选择/文件名；exact/one-over 与路径负例 |
| R-S1-03 | Mock 或内部调用替代生产入口 | Major | 禁止出门 | 真实 workflow/API 接线和原始执行证据 |
| R-S1-04 | 为通过测试修改固定分母/阈值 | Fatal | 禁止出门 | acceptance hash、packet manifest 和候选外门禁 |
| R-S1-05 | 目标 Comfy dirty 基线被覆盖 | Major | 禁止写入 | 先备份/hash；只安装 owned 增量包；不 reset 上游 |

下载、升级、写 Prompt Assistant 配置、使用私有媒体、调用付费 Provider 和推送远端均不包含在默认 S1 权限内。
