# 当前门禁：WAIT_BUDGET；可视残差输入离线完成，未真实验证

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
