# S2 浏览器真实链定向验证纠偏

候选：由下一次候选绑定离线检查收据确定。正式 S2 仍为 5/8，未产生 Stage PASS。

full-v0-auto-06 在公开矩阵15/15后，真实浏览器上传响应因 DevTools 缓存驱逐而无法取证。原失败保留，不改写为产品通过。修复通过页面内原生 fetch 的 Response.clone 观察真实请求和响应，不重放请求，不替换应用结果；原始字节、状态、SHA及子运行nonce逐一比对。

manual-page-diagnostic-08 使用原固定tracking样本，真实上传201；54241字节/SHA匹配，页面错误0，模型调用0。原终态SHA ba0a1f6a6401b7c0b92761aacbbeba4654db2c1131931ace722f424114607be2，受控原始归档12文件170640字节，服务、浏览器、临时根均清理。独立只读复算无Fatal/Major；这不是视频分析或Stage验收。

新增有限 browser-component-NN 调用原 StageRuntimeFactory、run_browser_phase、Supervisor 和全部九项浏览器局部 Oracle，实际模型/取消/故障路径保持。仅依赖封存范围缩为关键工具、Comfy/browser/frontend/codec；明确不封存完整Python/Ollama目录，不能冒充完整Stage，九项产品用例保持NOT_RUN。正式验收仍需同一新鲜运行的完整安装依赖、公开矩阵、浏览器、warm20及累计九项。

初次隔离审查发现3个Major，尚未真实执行：lease关闭不能等同资源清理、准备失败的保留归档权限不足、组件封存未核对冻结seed。集中纠正为：独立runtime-clearance绑定原claimed-child和terminal SHA并重算资源/归档清理；reserved归档清理在撤销/prepare失败时保留而不能启动新工作；显式绑定79原生seed文件、SDK/frontend seed及实际执行元数据工具身份，复用原冻结校验。修复后的CPU测试35项通过；复审与集中离线检查另存真实结果。

母授权AUTH-PROGRAM-V0-LOCAL-VERIFICATION-01保持ACTIVE；自动唯一子运行、有限预算、终态过期、原PID/birth清理。合同、固定分母、资源/延迟门限、人工签署均无变化。
