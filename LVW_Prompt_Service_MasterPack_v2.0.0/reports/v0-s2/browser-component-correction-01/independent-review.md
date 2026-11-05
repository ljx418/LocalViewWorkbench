# 隔离只读修复复审

审查实例：/root/s2_browser_component_review；与实现上下文隔离；2026-11-06。输入为冻结规范、当前候选源码及原始机器记录；禁止改候选和真实服务运行。

结论：剩余 Fatal=0、Major=0。此前三个Major闭合；仅同意继续封存/离线门禁，不签Stage PASS。

1. component_clearance独立复算原claimed-child/terminal身份、清理及归档；原全局准入锁内检查，closed标记不能单独放行。
2. reserved archive/cleanup在撤销及Factory prepare失败时保留；不能授予新服务工作。
3. seed映射复用原verify_observations，核对codec/SDK/frontend/browser及实际metadata工具hash/终态/退出码。

独立命令：PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest LVW_V0_RuntimePatch.tests.test_s2_browser_component LVW_V0_RuntimePatch.tests.test_s2_component_seeds LVW_V0_RuntimePatch.tests.test_s2_stage_runtime；22/22通过。另基于真实冻结seed纯数据复算79个codec文件逐项改hash，79/79拒绝；84个SDK映射正常。

临时目录复算：有效服务启动前失败归档可准入；mutable active-child修改不改变claimed身份；伪造正向clearance并更新terminal hash仍因清理复算失败拒绝。

限制：仅CPU及合成证据，未执行真实服务/模型/媒体/GPU/浏览器，不保证实际启动后的清理；正式九项仍NOT_RUN。定向证据不可替代完整Stage。
