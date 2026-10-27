# V0-S0 Risk And Authorization Register

| ID | 风险/动作 | 分类 | 默认状态 | 停止/清理 |
|---|---|---|---|---|
| AUTH-01 | 读取目标机安装目录和版本 | 外部/私有 | WAIT_AUTH | 仅批准根；日志脱敏路径 |
| AUTH-02 | 使用真实图片/视频 | 私有数据 | WAIT_AUTH | 只记录 hash；不打包原媒体 |
| AUTH-03 | 调用本地 Ollama/Comfy | 外部运行 | WAIT_AUTH | 限定端点、次数、超时；核对 owned request |
| AUTH-04 | 可见浏览器 | 高干扰 | 未申请 | S0 默认不用；若必要单独授权并静音、owned PID、finally 清理 |
| AUTH-05 | 下载/升级/写配置 | 环境变更 | 禁止 | 发现需要即停止并提变更请求 |
| R-01 | 未知 GPU 占用 | 资源 | 阻断探测 | 不 kill 他人进程；记录 RESOURCE_BUSY |
| R-02 | 节点/模型能力不匹配 | 技术 | 可产生 NO_GO/BLOCKED | 保留失败，不临时换模型降门槛 |
| R-03 | 证据泄漏路径/媒体/凭据 | 隐私 | Fatal | 停止发布，清理本轮受控副本并保留脱敏事故记录 |
| R-04 | 预算或重试耗尽 | 成本 | WAIT_BUDGET | 不降低分母；保存 checkpoint |

授权必须写明目标机器、允许根/端点、样本、Provider/网络、可见界面、最大重试/成本、证据目的地和清理。当前未取得 AUTH-01/02/03。
