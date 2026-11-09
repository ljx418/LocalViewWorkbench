# live07 独立审查

**NO_GO，固定UM 9/10；Fatal 0 / Major 1 / Minor 0。UM04仍FAIL，人工核签入口不可用。** 候选`d9759decaa760eb81479db5434ff9206b18b3327`，R1 packet1.0.3。最后预算槽不降低质量要求。本轮独审已完成，不签完整R1/V1、人工体验或发布。

仅纯CPU、候选Git blob、冻结原始证据与已有同源帧事实复算。未启动服务/GPU/模型/浏览器/媒体探测或媒体解码。未修改候选和live07原始文件。脚本隔离Python执行；候选源码按Git对象获取，CMD按原CRLF checkout复现hash。`raw-hashes.sha256`与`candidate-hashes.sha256`分别绑定原始产物和候选源；`recomputed.json`保存完整复算。

## 当前唯一Major：真实背景时序区别仍失败

位置：`live-07/video-model-run.json`的raw_response内`message.content.observations[3..4]`、`inferences[0]`、`prompt_zh`，以及`video-adopted.json`的中文/视频输出。触发：固定tracking.mov、F1/F2/F3/F4实际PTS1/3/5/7秒、一次完整temporal sheet真实Provider调用。

预期：区分固定红框与变化的网格背景，承认可见背景相对位移/构图变化；不能判定物理相机方向时保留unknown，不把场景断为背景恒定或整体静止。实际第四条observation明确说background grid与red rectangle在composition/color/placement上visually identical；下一条说无discernible movement或structural changes；推断visual content static并猜测compression、lighting或noise；中文提示保留“静态”美感。`camera_motion=unknown`和承认像素变化不能抵消这些错误的背景恒定断言。固定红框静止本身正确，本报告没有把subject_action=static单独判错。

固定生成recipe在`tools/v0_s2_fixtures.py:28`：先画40px周期网格，再crop x=20+2*n，最后画固定红框(135,65,50,60)。12fps下四采样crop x44/92/140/188、网格相位4/12/20/28各不同。源SHA为b08ea8…ff6d，live07四原始frame SHA/PTS逐项匹配既存`independent-live-03/independent-decoder-recompute.json`；既有`four-frames.png`可见竖线相对红框变化。本轮未重新解码。PNG是当时payload转RGB另存的可视化，文件hash与原始payload hash分别保留，不混称。旧证据仅用于相同hash输入视觉事实，不代替本次模型输出或运行成功。

## 已纠正项与新统计核实

前轮fraction百分比误读本次已纠正，**不计入本轮缺陷**。真实Provider账本整数为121747/354048、120838/354048、118155/354048，独立乘100并四位舍入分别得到34.3871%、34.1304%、33.3726%；模型正确说approximately33–34%。原始均值19.948187/19.711854/19.509985保留。两次video相同统计、四源SHA一致，image metadata=null。

候选`analyze_video`直接从`decoded.frames`算源SHA与统计；`temporal_pixel_measurements`对RGB绝对差合并非零像素，输出changed count、total count、percent和三channel mean；同一metadata进入message和provider ledger。没有样本答案、运动类别或方向硬编码。`pixel_math.py`仅抽取精确候选统计函数AST，用独立假的像素原语验证相同、1/4单channel变化、1/3全channel变化、全像素变化四个数学oracle，全部通过。未发现统计算法单位错误；没有重新实际frame解码，不冒称新增像素测量生成证明。

浏览器UM04仍明确BLOCKED等待独审，是正确权限分工。本次独审据真实内容将它裁为FAIL。机器整体原收据INDEPENDENT_REVIEW_PENDING、stage_pass_claim=false，未称Stage已通过。

## 固定10项

按照已批准且program02吸收的RUNTIME-01 scope，真实duration/corrupt、完整image/video/adoption/cancel/offline序列，加候选绑定CPU受控负例/race共同判断。未改media/service/shared decoder及测试的既有CPU证据可按该分工复用；新增统计另有本次独立数学和原始调用路径核实。候选定向测试源码单独另存`candidate-tests/`，审查公共ASGI、生产owner、Provider零调用、取消状态转移和cleanup oracle。旧program02-offline-02日志hash复算仅为未改受控路径的证据复用，不冒称本轮新全回归。

| 项目 | 判定 | 证据/边界 |
|---|---|---|
| UM-01 | PASS | 原始图片响应、公共请求日志及人工稿采纳前保护；image-model-run、image-draft与before-video-adopt来源一致。 |
| UM-02 | PASS | 批准RUNTIME-01 scope的真实+CPU分工：live07真实422 duration/corrupt；候选公共ASGI负例在Provider前拒绝并清空media/video-temp；共享生产validate_probe/stage_video覆盖bytes/pixels/container/empty边界，未把模拟称真实模型。 |
| UM-03 | PASS | live07四实际PTS=1/3/5/7秒、四独立源hash、source SHA绑定；候选shared decoder sparse/eof测试驱动生产owner，验证1/2/3帧、无重复补帧、bounded调用和cleanup；单帧warning与统一Provider采样局限保留。 |
| UM-04 | FAIL | 百分比33–34%量级正确；仍断言背景网格/红框composition/placement相同，以static及noise/compression猜测消解真实背景变化。严格语义FAIL。浏览器BLOCKED等待独审正确。 |
| UM-05 | PASS | 真实running cancel终态cancelled/released且result_ref null、人工稿与已采纳source不变；已批准CPU分工中公共ASGI队列取消幂等/准备decoder barrier清理后终态/晚到不发布均有实际生产service oracle。 |
| UM-06 | PASS | image→video采纳前仍归属image、显式对话接受后video来源改变；编辑后/取消后/离线JSON/TXT导出保持已采纳video来源及手工内容。 |
| UM-07 | PASS | 真实native model stopped/unreachable后人工编辑和TXT/JSON导出；受控失败支路与无模型人工路径由候选测试覆盖。 |
| UM-08 | PASS | 独立重算3调用/3lease释放，每lease至少3次inventory_empty且GPU≤baseline+1024；采样GPU峰22133<23552、最低RAM9365≥2048；原生NO_CLOUD/loopback日志与PID+birth+nonce exited witness。 |
| UM-09 | PASS | 实际START_LVW→Windows curl健康→同build正式React/FastAPI/headless入口；日志三次POST分析及页面静态资产；page errors/external requests空，Comfy零启动。 |
| UM-10 | PASS | 候选git blob绑定107 frozen项+4样本、packet1.0.3、工具身份/build复算；原进程exit/owned temp removal/终态授权及只读program02 settlement闭合；本隔离独审完成。 |

## 身份、调用、清理与预算

111项冻结文件/样本hash通过，其中107项为候选Git冻结文件；程序request/approval/child、packet、工具bindings与运行build复算一致。build=`58df5f0b10024b7e5aae6db0e1c21806d3381a5e6f22c48341dd1956c00431aa`。

独立日志计数3次send尝试（image、video、cancelled video），3lease各连续至少三次inventory_empty/GPU≤baseline+1024，峰GPU22133MiB<23552、最低RAM9365MiB≥2048。原生NO_CLOUD=true/127.0.0.1配置有原始日志；owner nonce64492c503f0941ae9ab354a643354af9、PID26020、birth_ticks639297893120183703为exited/listener_owned=false。API原PID2327292日志Finished，model stop不可达，owned temp移除日志及listener absent收据闭合；浏览器page errors/external requests为空。网络结论仅本轮配置/拦截记录，不扩为全系统网络审计。

SQLite只读复算live07 calls3/checkpoint1/active0/elapsed63秒，cap8/1800秒，child/bindings hash正确。live05=3/1/61秒、live06=3/1/54秒、live07=3/1/63秒，三者active均0；累计9次model actions、3个effective full checkpoints、178秒。program02每Stage上限3，**R1完整槽3/3已消费，剩余0；母授权ACTIVE不意味着还能运行live08**。旧槽不退款、不重置，不换Stage绕预算。

当前质量裁决NO_GO；预算状态为当前R1完整复验额度耗尽，不能据此开放人工核签或降低标准。未运行11个人工留样、未有人类签署。后续应由门禁负责人依据本缺陷和精确预算状态处理；本独审不派生新运行、不授权live08或跨Stage执行。
