# live03 视频语义纠偏

原运行a8a431d的图片、公开输入拒绝、采样来源、人工稿保护、导出、运行中取消、资源释放与原生进程退出保留真实证据。独审发现UM04 Major：跟拍结构样本存在网格位移，但模型原文声称three identical images/no changes/static，导出还带none/none。HTTP成功和严格JSON不能证明时序语义正确。原始结果不改写。

离线修复：把1–4个实际采样帧按时间顺序排成最多768×768的一张时序图，保留完整画面，等比缩放、留边、不裁切、不复制帧；用F编号和真实秒数标注，分隔标签与场景。只改变内部视觉呈现，不新增帧读取API，不改变公开Schema、源视频SHA/源PTS或模型输入来源。时序任务替换之前单图任务句，避免单图/多帧指令混合；要求比较每一实际格、分开主体/背景/取景变化，无法判断时明确unknown，而非强称静止。不向模型输入跟拍样本的答案。

模板身份包含temporal-sheet/1。Provider账本分开记录source frame_count与payload_image_count、source_frame_hashes及实际发送PNG指纹，不能把一张拼图伪称发送四张图片。num_ctx4096/num_predict768、GPU/RAM/释放门限不变。图片分析路径不改。

定向测试从实际Provider序列化的HTTP payload解码PNG，核对4个不同颜色源帧按时间进入4格、尺寸上限、1–3帧不补重复帧、0/5与元数据不匹配fail-closed；不把mock响应的运镜文字当作真实模型效果。

另补真实AnalysisService准备阶段取消组合：真实公开上传/取消owner + 受控解码线程屏障，取消传到decoder并清理后才终态cancelled/released，Provider调用0，无发布。这是离线故障驱动证据，非额外模型运行。

现有完整槽已2/2使用；准备中的live04必须有新人工批准且绑定完整请求hash，默认锁定。修复是否改善模型语义，必须新一次真实运行及独立复算，不能由离线测试宣布解决。
