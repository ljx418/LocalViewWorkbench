# 原生桌面启动器交付

用户明确要求：制作启动图标、封装本项目启动命令，避免用户手动输入命令。该增量只增加根目录LVW.exe/启动LVW.lnk与launcher源码、图标、构建说明；复用既有图片启动器和已验证的视频临时环境方案，不修改冻结S2产品路径、合同或验收分母。

Windows原生WinForms窗口提供图片、视频、指南、工作流定位和会话目录入口。图片复用START_LVW.cmd；视频由原生ProcessStartInfo设置本轮环境并启动既有Python，不使用EncodedCommand、ExecutionPolicy Bypass或脚本执行策略修改。仅loopback，缺依赖不下载，端口占用不杀未知进程，原有Comfy安装不写入，视频导出目录保留。关闭服务使用原有服务窗口Ctrl+C，不为封装引入不可靠的全局杀进程逻辑。

明确的边界：视频仍使用原生Comfy页面；导入JSON和上传视频是正常界面操作。图片与视频入口仍分开，不宣称已交付独立视频React前端。视频模型通过图片服务面板启动。关闭启动窗口不会停止服务，窗口有提示。移动项目后旧.lnk绝对路径可能失效，可直接运行同目录LVW.exe。

验证01：本机原生csc编译、COM快捷方式、WinForms实例与路径/哈希自检通过；实际启动隔离Comfy、确认LVWVideoPromptOwner注册、终止本轮原进程句柄并删除本轮临时根通过。无媒体、模型或可见浏览器。最初离屏预览因隐藏父窗体未绘制子控件，图像空白；不将其视作视觉通过，原图和源/执行器/二进制留存为initial文件。

修正仅涉及离屏自检绘制子控件方式；验证02重新编译并重跑自检与有限原生启动。当前有效结果见02/receipt.json与原始日志，02/launcher-preview.png已人工查看；实际没有显示窗口或自动操作可见浏览器。两个有限子授权均在终态自动过期，失败/旧结果不覆盖。

本交付只是READY_FOR_REVIEW的启动辅助增量，不构成Stage PASS或人工签署。原产品机器路径身份仍需source_gate核对；Stage仍S2 7/8，人工体验及签署后Git同步待完成。本轮仅本地提交，不推送或发布。

文档验收首次发现4份原生.NET JSON输出带UTF-8 BOM，包校验器严格UTF-8读取拒绝。保留所有原生字节为*.native-utf8-bom.txt，由normalize_receipts.py生成只去BOM及缩进的JSON，解析值完全不变；映射与双向SHA见json-normalization.json。此兼容整理未改启动器或重启产品服务，原验证结果不重写。
