# Resource-resume授权传输

项目负责人明确批准AUTH-REQUEST-V1-S2-RESOURCE-RESUME-01；仅恢复原未认领full-oracle-correction-01的一次上限，额外完整运行0、额外完整复验0。旧准入NO_GO和旧EXPIRED_NO_GO grant保持原字节，不复活或删除。

复用现有有限准入profile和完整运行协调器，仅新增一次resource-admission-oracle-resume-01并提供prepare-resume/probe-resume入口。新批准绑定请求hash、旧grant hash、原NO_GO子授权/receipt/原始terminal/关闭标志、最终候选后代和冻结Stage义务。原完整目录或终态已存在即拒绝；完整prepare仍必须有同候选新准入成功。新scope到期/撤销/失败/完整终态自动过期，全部原始预算/门限/样本/模型保持。

定向测试首轮发现17个子场景因fixture先切换临时cp.ROOT再读取模板而失败；已改为切换前读取，并避免导入TestCase导致重复计数。最终25项定向实际通过，原始成功日志与hash见resource-resume-directed-01/receipt.json。真实Git/自有文件检查可复算，原生输出明确为合成，不能据此宣称目标机或产品PASS。

下一步封存最终候选并运行offline-checkpoint-27；通过后生成新准入child并执行一次有限探测，成功才恢复原完整child，不增加新完整槽。真实运行期间不改执行字节，不重复启动、不替换样本、不跨运行拼接；docs/25未实施。
