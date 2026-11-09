# 当前门禁：WAIT_RESOURCE；图像注册新候选已离线完成，未取得真实语义结果

当前实现候选d3b4ddde5311299083e398dfe08c1ab9c4e38ea8。资源释放后live10完成真实图片/视频/取消/采纳/导出，3模型动作/53秒、GPU峰22595MiB、RAM最低10131MiB，三次租约释放和原始进程清理闭合；独审9/10 NO_GO、UM04 Major1：原始模型仍称网格与红框空间恒定，并猜测显著差异为压缩/噪声。

因此改用另一技术路线：保留完整F源帧＋明确D派生残差，在同一次模型消息/账本追加有界图像注册测量。仅Pillow、灰度≤128²、共同窗口、±10穷举、next-to-prev偏移/误差/精确多解，非物理相机分类。所有源SHA/PTS/FrameRef/raw/一次Provider/公共DTO/UM10/资源质量门槛不变。新内部template1.3.0；134CPU组合回归、23独立整数oracle及mock生产接线通过，代码独审Fatal0/Major0/Minor0，不代表模型语义通过。

新候选live11在Provider.acquire内部、lease_acquired之前因GPUfree1329<19047被拒绝，0模型/0有效完整轮，完整清理。其独审只判WAIT_RESOURCE，alignment真实语义NOT_RUN，不能把live10 FAIL或合成结果当新候选结论。

后续有界资源接力子运行最多60次/660秒，达标才签发一个新live12；实际60次都未达标、末次free1133/used23006MiB，未签发live12。该等待已终态，不在后台无限轮询。只读核查live10原native父进程的直接子进程，无遗留，没有终止任何外部进程。

COMPLETE03持续ACTIVE，无阶段/候选授权硬配额。全局累计12/1024动作、4/24有效完整轮、1102/172800秒生产运行，包含旧消耗，全部子记录闭合。当前只等实际GPU空闲（≥19047MiB，RAM≥2048MiB），保留约2分钟即可立即新建live12；无需人批GPU/预算/候选/Stage，也不降低资源门槛。尚未到统一人工核签、完整R1/V1通过或发布。

证据：live10/11、independent-live-10/11、alignment-input-offline-01、independent-alignment-input-01、complete03-resource-handoff-01、owned-descendant-audit-01、complete03-budget-after-live11.json。以下保留历史。

---

# 历史：COMPLETE03启用后的live08资源门禁

执行器候选dccdd1b7e06d3bb71d2baf86dc440dee8a6b3f99。AUTH-PROGRAM-V1-COMPLETE-03已明确批准并hash绑定；133项CPU组合回归及执行器隔离独审Fatal0/Major0/Minor0。实际账本仍为原program02.sqlite，全局累计1024模型动作/24有效完整轮/48小时，不再使用阶段/启动/CPU次数授权硬配额。旧单次live08增量请求已被覆盖，无需另批。

live08原始Windows启动→真实React/FastAPI→本轮原生Ollama服务已运行，固定两个损坏/超时长负例拒绝。但首个图片分析在Provider.acquire内部资源guard、lease_acquired前拒绝，baseline GPU free18839MiB<冻结19047，RAM9824MiB。未启动视觉推理，model/provider send=0、有效完整槽=0。模型服务/API/browser正常退出、原始native身份和临时根清理闭合。残差输入真实语义NOT_RUN，不能把live07或合成图当新通过。

18次有界只读资源等待均未达到19047MiB；没有终止外部进程或降低资源/质量门槛。见complete03-resource-wait-01与后续有限检查。资源释放后自动派生新唯一live09，不复活旧child，不请求重复GPU或阶段授权。

独审independent-live-08按本轮实际证据完整义务1PASS/9BLOCKED，UM10冻结/清理闭合；UM02两个真实负例仅局部成功，不借历史组合结果补齐。历史9模型动作/3有效完整轮/178秒保留，后续零模型时间另记，母授权仍ACTIVE。

当前不是人工体验签署入口或整个R1/V1通过；只在资源就绪后完成真实语义检查及独审，再请求人类实际核签。下一S3仅准备文档preparation-02，不跳过前置人签。以下保留先前门禁历史。

---

# 历史：可视残差输入离线完成，曾等待预算

新候选96e77ea3691cf68422ccd159c85985b4d9a118ec：124项子树回归及最终34项定向通过，源输入独立158断言、权限独立28检查通过，Fatal0/Major0/Minor0。无真实模型、服务或媒体探测，不能把此离线结论当UM04通过。

原始源帧全幅缩略图保留，添加明确D标签的absRGB派生证据，单PNG≤768、一次Provider、source SHA/PTS/raw/显式采纳与全部固定分母/阈值不变。详情见residual-input-correction-01.md。

已准备精确单次预算请求AUTH-BUDGET-V1-R1-RESIDUAL-01（authorization-residual-recheck-01.request.json），仅R1/live08、stage3→4、单轮8动作/1800秒、母授权总512/8轮/24h不变。正式approval不存在，live08不存在，当前并未获增量授权。普通“继续”只使离线工作继续，不增加次数。批准后才允许新有限子运行，终态过期、不自动再试。

上一次真实候选仍为d9759de/live07、独审9/10 NO_GO，原始失败保留如下；当前未到人工核签。

---

# 历史live07门禁：NO_GO；当时R1真实验收预算已用尽

候选d9759decaa760eb81479db5434ff9206b18b3327，live07独审9PASS/1FAIL，Fatal0/Major1。UM04真实视频时序内容仍错误断言背景恒定。当前不是人工体验签署入口，不是整个R1/V1通过。

AUTH-PROGRAM-V1-LOCAL-02已批准并生效，RUNTIME-01已被覆盖，无需再次确认GPU/代码/SHA。本机执行器已原子预留/扣额、绑定真实候选/输入/模板/共享核/工具和单次原始进程，独审通过。母授权仍ACTIVE；当前R1的有效完整验收上限3轮已用完，不能用总模型额度剩余或旧授权叠加启动live08。

| 运行 | 候选 | 模型动作/时长 | 独审 |
|---|---|---|---|
| live05 | 0cc125f | 3 / 61s | 9/10，时序误判及局部schema-only oracle过度PASS |
| live06 | 8d43c1d | 3 / 54s | 9/10，时序误判及fraction到百分比量级错误 |
| live07 | d9759de | 3 / 63s | 9/10，比例已正确，时序误判仍在 |

总计9动作/178秒生产运行/3轮完整槽。三轮都证明图片/视频公开链路、运行中取消与3次实际lease释放、显式采纳/导出、模型离线人工编辑、原生退出/no-cloud/监听和临时根清理。GPU峰值分别22096/21910/22133MiB，均低于23552；本轮最小RAM9365MiB，资源并非阻塞根因。11个人工留样仍未提交模型。

机器原始结果、离线结果、独审结论分别保留，旧失败不重写：最近完整子树123CPU对应8d43输入版本，最终计量单位修正由19Provider定向与独立精确数学oracle覆盖，未变路径有明确复用边界。浏览器UM04现只标BLOCKED等待独审，不再把Schema视为内容通过。

停止真实运行，先改变技术路线，见temporal-route-reassessment-01.md。任何额外完整运行需明确增量预算裁决，不是重新请求GPU基本权限。历史门禁原文见gate-decision-before-program02.md及Git历史。
