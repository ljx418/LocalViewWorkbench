# 旧D0校验器的适用范围与本次对照

verify_v1_plan.py仍绑定design112/WAIT_HUMAN及当时25文件的历史快照。本次不修改该工具、旧spec-manifest或冻结D0包。

实际运行：当前树exit1/10条；修改前Git基线的48份相关原始Git文件在临时隔离文档根按同一工具/默认pin运行，exit1/10条。对照归一化错误类别和漂移文件路径完全一致，原始stdout/stderr/argv/25+packet文件hash保存在checks/v1-plan-baseline*。当前和旧基线都不是PASS；这不是忽略错误或宣布旧D0重新通过。

三个状态类问题是已有真实切片签署/acceptance值与历史“无签署”要求、当前坐标非WAIT_HUMAN；七个漂移路径为docs17/30/31/32、execution-control、tasks、v1-revised-plan。本轮30–32与坐标确有获批修改，但这些路径在本轮前已不同于历史pin。关键canonical产品JSON/旧冻结包本轮均原字节保留。

当前新增制度以verify_delivery_workflow、既有verify_governance及FULL_SPEC检查验证。后续OPT-A需把当前生命周期设计与历史D0快照的校验责任分开；不得拿旧工具的历史限制阻断所有定向反馈，也不得改旧pin抹掉失败。新的公共接口/迁移/质量等变更仍需实际合同校验，不由本说明豁免。
