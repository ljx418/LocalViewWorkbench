# 资源清理 correction05 结果（待独审）

候选 `1f55a4687a392c002538e135863ad71ec87b3376`。141项定向检查及295项后端回归通过，前端相同字节12项及构建复用。22/22实机检查通过，实际2模型动作、2代原生Job、52.123秒。清理GPU 21393 → 3279 MiB；最终3279MiB。

[22项原始收据](runs/real01/receipt.json) · [结算前完整证据](runs/real01/receipt.prepared.json) · [模型结果](runs/real01/model-run.json) · [最终Job证明](runs/real01/native-final.json) · [私有目录实查](runs/real01/private-root-audit.json) · [Windows ACL原生探测](runs/windows-acl-probe01/controller/stdout.log) · [桌面截图](runs/real01/analysis-desktop.png) · [移动截图](runs/real01/analysis-mobile.png)。

资源序列分开记录：外层监测峰值GPU21453、最低RAM11677 MiB；Provider序列峰值GPU21453、最低RAM11723 MiB；最终三次RAM最低12100 MiB。均满足原硬门限；不以某个序列冒称整轮连续极值。

五项Major及一个Minor对应修正见[decision](decision.md)。旧失败及预算保留不回改；历史real02外层RAM11515与Provider11497明确分开，本轮非旧证据拼接。

体验方式：重新启动本项目以加载新后端，在“本地后端服务”点击“资源清理”；清理仅针对本轮LVW服务及其后代，保留稿件/素材/模型。继续分析前点“启动模型服务”。不清理未知进程或承诺释放整机全部内存。

仍待独立复核，不宣布Stage/完整V1/人工签署；主干持久化23bd8da保持暂停。
