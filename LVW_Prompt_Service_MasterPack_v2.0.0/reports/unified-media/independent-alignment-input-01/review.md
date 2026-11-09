# Independent alignment input review 01

结论：独立代码/纯CPU合成像素/mockHTTP审查通过，Fatal 0 / Major 0 / Minor 0。仅认可内部输入测量与生产消息接线；不认可任何真实模型语义、资源释放、Stage或产品验收通过。最终候选d3b4ddde5311299083e398dfe08c1ab9c4e38ea8的provider/test Git blob、当前文件与独审封存逐字节一致。

授权与角色：已读AGENTS第11条、治理README、执行坐标/索引、R1 stage-control及范围/验收/检查包、COMPLETE03 request/approval。本实例只读实现，新增本独审目录；未启动服务/模型/GPU/浏览器、未下载、未probe/decode视频、未读写真实执行账本。进程/网络调用在独立oracle内被失败断言拦截。使用现有Python/Pillow/httpx，仅合成PNG/内存事件收集；model_action为隔离假模块，不接触执行器。

## 数学与边界

在灰度分析图上固定 W=[r,w-r)×[r,h-r)，r=min(10,floor((min(w,h)-1)/4))。穷举整数偏移 d=(dx,dy)，代价 E(d)=Σ_W |P(x,y)-N(x-dx,y-dy)|。因此下一帧实际右移a/下移b时，返回对齐偏移(-a,-b)，独立不环绕粘贴的五组平移包含±10极值证明符号一致。所有候选使用相同参考像素及相同分母；最极端坐标仍位于源图[0,w)×[0,h)，无越界黑填充污染。不是随位移缩小窗口的偏置比较。

零偏移属于候选，所以最优误差不大于零偏移误差，改善率位于[0,1]；零误差除零分支返回0。整数灰度绝对误差求和精确，最大128×128×255远低于浮点精确整数上限。相同误差按偏移范数、dy、dx稳定破平，并分别输出所有相等误差最优数；静态纹理选零，不伪报平移。窄图r<1/参考窗全同灰度明确不可用；原始尺寸不等在缩放前拒绝。

23个独立用例以Python list/int逐像素重算所有候选，不调用实现的crop/ImageStat/ImageChops。覆盖符号/极值、静态、6种小/窄尺寸、7组无关随机图、固定窗外变化、多解条纹、无纹理、等亮异色结构。另验空/单帧、尺寸不等、输入SHA不可变。原始结果见raw.json；独立执行入口oracle.py，不继承父级测试结论。

## 生产接线、合同与边界

通过实际OllamaProvider.analyze_video→_analyze_images，仅httpx.MockTransport，验证一次POST、一次先于POST的mock预算扣记。4个源帧及三个残差仍在一个768×768 PNG；注册测量和RGB差异同时进入实际user消息与provider_call_started内存事件；源SHA、输入sheet SHA、4个实际时间元数据匹配。manifest含独立frame_id/pts，调用前后原样；模型raw字符串逐字保持，解析camera/subject字段仍来自mock模型内容，模板1.3.0。源测量不改写输出事实，不插入样本动作答案。输入派生版本、VIDEO_TASK、VIDEO_SCHEMA均进入VIDEO_TEMPLATE_SHA256，service.py仍将该值记入视频ModelRun。

与fd9044e比较IMAGE_SCHEMA/VIDEO_SCHEMA AST完全不变；公共models、contracts、验收/需求/资源及共享解码限制文件无diff。未增加Provider请求、模型重试或绕过预算；单PNG与原FrameRef/PTS/raw、资源/质量硬门槛保持。工作树provider.py/test_provider.py与reviewed-source封存相同，hash见source-check.json。

搜索本身每对最多441×108×108≈514万像素绝对差比较，四帧最多三对；每对scores≤441项，分析图≤4×128²灰度像素。生产上游已限制≤4帧且每边≤768；helper会先全帧convert再thumbnail，因此不能声称对任意未受限输入都只用128²内存。当前生产边界内增量有界。一次四张768方形合成图新增注册实测约0.043秒，仅本机单次CPU观察，不是资源/性能门禁证明。

## 必须保留的限制（非阻断）

- 仅灰度、缩至128：等亮异色运动可能完全消失；高频/细小结构缩放后混叠。独立等亮异色例得到reference_has_no_texture，同时RGB派生差异仍可保留颜色变化。零偏移/不可用不能推出原帧恒定。
- 固定中心窗口不看边界，独立“仅窗外改变”例零误差；主物体、背景可以分别移动。纯全局平移不覆盖旋转/变焦/透视/遮挡/景深/光照/切换，超过搜索半径无法恢复真实位移。
- equally_best_offsets只标示所选灰度目标上的精确等误差最优，不能衡量近似多解、不确定度或重复纹理真实运动。周期条纹多解已复算；偏移以缩小分析图像素计，不是原始像素/速度/物理相机方向。
- 指令已明确registration不是physical camera motion，重复图案可alias、主物体可固定。测量是附加证据，仍须独立核验真实模型是否理解与避免恒定网格误判；此次不执行真实模型，不使live10历史失败失效。

## 停止坐标与完整路线

- V0-S0：1/2，历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS
- V0-S1：5/5，已签仅V0-Min
- R0：1/2，仅R1a前置单图子集可确认；不把完整视频/Q01算通过
- R1a：5/5，已签仅单图切片；完整V1未完成
- V0-S2：7/8，Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain.
- V0-S3：0/6，已有设计，未完成正式交付；存在代码需进入时复用审计
- R1：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R2：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R3：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R4：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R5a：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R5b：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计
- R5c：0/4，已有设计，未完成正式交付；存在代码需进入时复用审计

当前坐标：R1/WP-R1-U3；本批完成：独立输入代码审查与23合成oracle/1 mockHTTP；最后通过门禁：本次仅CPU测量接线，历史按execution-control；当前阻塞：真实语义新候选未验证；全局路线：V0-Min已签，统一切片仍非完整R1；剩余工作：实际受控真实/独审及人工前置；下一责任人：codex_gate_owner/local_ci；所需授权：范围内COMPLETE03已批准；证据目录：本目录；精确停止原因：只读CPU独审完成且最终候选绑定闭合；真实语义不在本次范围。
