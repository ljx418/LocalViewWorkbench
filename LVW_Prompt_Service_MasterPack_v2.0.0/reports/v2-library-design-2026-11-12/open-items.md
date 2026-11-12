# 已设计但仍未验证的准入项

- 本轮未运行模型/GPU/原生Windows文件操作/MCP客户端，未读取私人素材或真实产品数据库。
- V1最终SQLite/schema/持久Job/Scene/Revision仍待实际交付与复用核验；迁移序号NEXT_VERIFIED_SCHEMA，不假设设计DDL已部署。
- native no-replace、文件ID、祖先防替换/共享句柄、NTFS大小写/Unicode/长路径、进程custody与flush仅为候选方案，需隔离Windows pilot；不支持则保持写入门槛未通过。
- 原文件根/读写scope、30样本路径/许可/hash/独立标签、正式模型与动作预算均未绑定；本次需求调整不赋予这些权限。
- >=90%与P95 1s/2s、4素材pilot及8帧长片资源参数为提议目标；实测不足时保留失败并重新设计，不降旧门限/不缩固定分母。
- DB恢复外部文件协调与journal旁证耐久/容量仍需实测，不声称断电或跨DB/磁盘原子性。
- 明确会影响第三方剪辑工程路径；只提供映射，不承诺自动修复。L5监控/auto apply/跨卷/文档/更多容器等未纳核心。
- 当前V1 correction04仍WAIT_BUDGET；此次仅新V2设计任务，不构成恢复ClaudeCode或Codex接手许可。
