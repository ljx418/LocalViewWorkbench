# 两轮未出门后的范围与Oracle复核

按ADR16“连续两轮门禁无推进先复核范围/架构/Oracle”。首轮14组13PASS/1FAIL暴露返回后重读已退役槽位的取证缺陷；第二轮修复后的R07-only验证证明真实pump身份/结束，但zero清理仍遗留pipe-read线程，批次实际清理FAIL。因此不启动第三轮盲修/重试，不因前一Oracle已修正或CPU解释器最终退出而放行。

保持边界：生产broker/custody和原时限未变；固定189/产品29未完成；测试最终清理与产品返回时清理分开；实际alive或未知清理继续硬阻断。没有符合Minor条件的辅助详情问题。复用已有registry/drain，不新增通用诊断框架。

隔离审查须从原始zero-public-chain、zero-salvage、guard/runner和具体Api/read-worker生命周期证明：谁创建该实际线程、在哪个读/等待点受阻、哪些gate/cancel/close动作确实执行、为何原有release和有界drain未结束它，以及缺陷属于测试原语还是生产owner。必须给出最小owner/文件范围与成功/失败Oracle；未证明根因前保留unknown，不默认扩大生产改动。

下一次实现必须有新冻结范围和候选；下一次运行必须有独立精确计划及root ACK，不复用本轮终态许可。当前只允许完成原运行归档及只读根因调查。N2文档准备可保留，依赖实现不准入。
