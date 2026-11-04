# S2 resource-ready 运行终态与验收器纠偏

当前真实候选 b9fcff30cecec2cd1fdc8152cb406b0aad13f123，运行 full-resource-ready-01，终态 NO_GO。原始收据、原始归档、关闭标志与过期授权保留，不改写为通过。

事实复算见 `resource-ready-failure-facts-01.json`；原始证据由其中 terminal/manifest SHA 绑定，仅在受控状态目录保存。29 个归档文件逐个复核长度和 SHA，运行根已删除，拥有的服务/采样器/查询进程清理证明完整。此次未启动浏览器、未执行视频或热性能矩阵。

## 同批根因与修复

1. 累计 A03 将 Provider 整个日志快照相等当成“没有额外视觉调用”。实际 image-after 与 online-after 的 chat_calls 都是 1，后者保留完整旧前缀，仅新增卸载 `/api/generate` 和库存 `/api/ps` 日志。修复为校验两份原始前缀的哈希/长度/独立计数、不可改写旧前缀及视觉调用增量为零；离线 A08 同根因一并修复。保留额外 chat、日志改写、计数伪造的拒绝。
2. 提前在线失败时仅启动了第一个采样器，清理验证却固定要求默认运行的两个采样器，误报为资源采样失败。真实 63 条采样和 worker 终态没有失败。修复为所有已注册 worker 必须有完整成功终态；提前终止允许登记的 1 个，完整默认路径仍必须有 2 个，warm 必须有 1 个。资源 abort 锁存、缺失 worker 收据或失败仍拒绝。

产品实现、公共合同、验收分母、GPU/RAM 门限、重试预算保持冻结。新增回归驱动实际累计 owner、CPU 公共节点与序列关闭逻辑；服务/模型/GPU 均为明确标记的合成测试，不能替代真实运行。

## 后续门限

先封存修复候选并完成 offline-checkpoint-25。真实完整运行、独立审查、人工体验和 S2 签署尚未通过。AUTH-V1-S2-RESOURCE-READY-01 已 EXPIRED_NO_GO，完整运行余量为 0；不得重放 readiness、复活旧授权或将旧部分结果拼接成完整通过。只有新的明确预算批准才能重跑。S2 未经人工验收，不推送远端。

离线 checkpoint24：461 项测试、前端、合同与 whitespace 通过，治理检查拒绝当前坐标中的 CHANGES_REQUIRED（此项目坐标枚举未包含该值）。改为既有 FROZEN_READY_OFFLINE；不修改治理校验器或增加可通过状态。历史失败完整保留，最终复核使用 checkpoint25。
