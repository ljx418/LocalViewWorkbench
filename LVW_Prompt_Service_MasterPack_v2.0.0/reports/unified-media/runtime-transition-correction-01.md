# live04启动竞态纠偏

本轮按已批准request SHA ddb4fa72…精确激活packet1.0.3，以9f4a659为文档后代候选运行一次live04。准入free20950MiB/RAM10560MiB、目标端口空闲，资源条件正常。失败原因不是GPU不足：生产日志记录readiness200→media201→jobs/analyze409→runtime/start200。服务的controller锁尚未释放，前端却只按model_ready启用分析；原analyze handler也未检查runtimeAction。这是实现遗漏。无Job、无Provider账本、无ModelRun，原生日志无chat/generate，独审确认实际推理0。

原浏览器waitDone还要求出现.job-status，所以无Job的409失败等待420秒才结束（独审Minor）。本轮NO_GO原始数据不改；原生exited/停止响应/API正常退出/监听消失/临时根删除证明齐全。原一次性授权随终态过期，不能因零模型调用自动退款或重跑。

## 修复

- App按钮与analyze入口均加runtimeAction门禁；服务启动/重置/关闭未完成时等待，不受提前出现的model_ready误导。
- 操作期间显示“等待服务切换完成”，人工编辑与导出不锁定。
- 浏览器验收等待器同时识别“有Job终态”和“无Job但已明确报错”；后者立即进入失败断言，不凭错误提示计成功。
- 后端对controller忙时409保持不变，无新增API、Schema、阈值或产品分母变更。

## 验证

runtime-transition-cpu02的真实生产React/default_app/AnalysisService，注入可控Runtime/Provider边界：故意让ready轮询显示可用、但控制请求保持未完成。start/reset/stop三种情况按钮均禁用，直接负例各409且不增Job；人工编辑/JSON导出保留。释放start/reset后各一次UI分析202，FakeProvider2次、真实推理0次。5项均通过，原始服务日志/下载及清理可复算。CPU01的405是测试控制路由被产品静态mount遮挡，已仅调整fixture路由顺序，失败留存，不修改产品入口以适配夹具。

9项前端单测、typecheck、build均通过；108项后端/共享核/静态集成在新候选上重新通过。以上不证明时序图真实视频识别改善。

## 下一门限

最终候选57aa9de6052effa4b1043ac0920e54d083204be4（生产代码与已测1d1db相同，另补全模板/共享核冻结）不属于原批准998的纯文档后代（前端/Harness已变化）。AUTH-REQUEST-V1-R1-U3-RUNTIME-01仅待批准：新live05一次完整运行，原未使用8次模型调用上限不增加，另加API/Ollama/headless各一次启动；不自动复活旧授权、不退款旧完整尝试。仍需真实图视频、取消/导出/释放组合及独立时序语义复算后才进入人工核签。11留样未提交模型。
