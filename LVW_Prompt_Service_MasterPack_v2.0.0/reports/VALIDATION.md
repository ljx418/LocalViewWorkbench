# 本次文档与原型校验

产品验收状态：**全部 NOT_RUN**。

Agent治理状态：`V0-S0 / GATE0_READY / WAIT_AUTH`。已增加角色隔离、Stage Packet、候选/证据绑定、预算等待、跨项目队列接口和反假绿校验；`tools/verify_governance.py --self-test`的27项制度检查通过。该结果不表示目标运行时、GPU或产品用例通过。

已执行：JSON/Schema/正反例、需求任务与旧ID映射、38个HTTP操作引用、SQLite建表/不可变触发器/错误边界、Markdown链接、本地HTML无远程运行资源、发布报告缺证据拒绝测试。

浏览器：62项DOM渲染与交互检查，360/768/1440/1920视口；四版本、22篇内嵌文档、六模式/四目标、失败不覆盖稿、JSON导出Schema、资产检索、对端离线/提交未知。截图为本包实际HTML渲染。

限制：运行环境阻止file://与loopback URL导航，使用Chromium `set_content`载入本地HTML进行DOM测试，因此**未验证页面导航/真实离线部署**。200%检查为CSS zoom smoke，非原生缩放产品验收。没有访问用户Windows、运行Gemma4或4090，也没有真实Navia/Narralens/Comfy E2E。

`tools/verify_pack.py --schema`可复核合同；`tools/browser_smoke.py`是可选开发测试，需要已安装Playwright/Chromium，不自动拉取依赖。文档包不包含生产程序或可导入的真实Comfy工作流。

`tools/verify_governance.py --self-test`还会用突变负例确认：缩小固定分母、实现/审查角色碰撞、未授权外部运行、SKIPPED冒充PASS和旧候选证据均被拒绝。正式运行态收据仍应写入项目外受控存储。
