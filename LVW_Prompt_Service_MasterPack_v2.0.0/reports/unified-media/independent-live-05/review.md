# live05 独立审查

结论 **NO_GO，UM 9/10**。独审已完成；UM04真实时序语义失败阻断人工签署入口。候选 `0cc125f9ba8a66972cf19176a61d52a4b2742bb7`，冻结R1 packet **1.0.3**。完整R1/V1与人工体验均未签署。未改候选及live05原始证据。

审查仅用隔离 `python3 -I` 标准库脚本重算、Git对象与原始机器产物，并查看既有图像。未启动服务/GPU/模型/浏览器/媒体探测或额外解码。`recomputed.json`、`candidate-hashes.sha256`与`raw-hashes.sha256`保存数据及身份。开发者在独审期间开始另一纠偏，因此候选源读取Git blob；CMD按既有CRLF checkout复现字节，未把新实现拼接到本轮。

## 两项Major

1. **UM04真实时序错判**。位置：`live-05/video-model-run.json` 的 `raw_response.message.content`、`parsed_spec.domains.observation/inference`，以及 `video-adopted.json` 的 `outputs.video_prompt`。触发：固定tracking.mov，F1/F2/F3/F4实际PTS为1/3/5/7秒，全部源帧进入一次`temporal-sheet/1`请求。预期：识别背景网格与红框的相对位移/构图变化，无法判定物理镜头运动时保留不确定性。实际：明确称四帧grid alignment/background恒定、无subject或camera movement、static，并导出静态视频提示词。红框固定本身正确，但不能推出整个场景静止。

`tools/v0_s2_fixtures.py:28` 的固定recipe先`drawgrid`，再`crop x=20+2*n`，最后固定红框(135,65,50,60)。12fps下四采样裁切x为44/92/140/188，40像素网格相位为4/12/20/28，均不同。live05源SHA为b08ea8…ff6d，四帧源SHA逐项等于既存`independent-live-03/independent-decoder-recompute.json`中的原始manifest；既存`four-frames.png`可见背景竖线相对红框变化。该PNG由当时frame payload转RGB另存，PNG文件hash**不是**源帧payload hash；两者分别记录，未混淆。旧证据只用于相同源hash/PTS的视觉事实，不借用旧运行正向验收。

2. **局部UM04 oracle过度声称PASS**。位置：冻结候选`reports/unified-media/live_browser.cjs:15`。断言仅为frames.length=4、双语文本非空与raw存在，即写UM04 PASS；没有检验背景/构图时序区别。`live-05/browser-result.json`因此对真实静止错判仍标PASS。预期应将真实调用/Schema完整与语义独审分开，语义未判定前不得写UM04 PASS。整体receipt原本明确`INDEPENDENT_REVIEW_PENDING`、`stage_pass_claim=false`，本项不指称整个Stage已被正式误签。根代理已通知在后续独立候选纠偏；本审查不将未验证的新改动计入本轮。

## 固定10项

依据program02吸收的已批准`authorization-runtime-transition-01.request.json` scope，真实duration/corrupt与真实图片/视频/取消/导出，与候选绑定CPU受控负例及race覆盖共同判断。没有要求每个负例额外调用模型，也不把CPU测试称真实模型成功。已静态审查保存于`candidate-tests/`的最终候选生产owner定向测试、公共ASGI路径、负例Provider零调用断言、状态转移与cleanup oracle。程序最终离线日志122 passed的三个日志hash已复算；本轮未重跑包含decoder的测试，以遵守禁止额外解码。

| 项目 | 判定 | 证据/边界 |
|---|---|---|
| UM-01 | PASS | 原始图片响应、公共请求日志及人工稿采纳前保护；image-model-run、image-draft与before-video-adopt来源一致。 |
| UM-02 | PASS | 批准RUNTIME-01 scope的真实+CPU分工：live05真实422 duration/corrupt；候选公共ASGI负例在Provider前拒绝并清空media/video-temp；共享生产validate_probe/stage_video覆盖bytes/pixels/container/empty边界，未把模拟称真实模型。 |
| UM-03 | PASS | live05四实际PTS=1/3/5/7秒、四独立源hash、source SHA绑定；候选shared decoder sparse/eof测试驱动生产owner，验证1/2/3帧、无重复补帧、bounded调用和cleanup；单帧warning与统一Provider采样局限保留。 |
| UM-04 | FAIL | 真实Provider确有四源帧一次temporal sheet请求及原始输出，但错误断言grid alignment constant/scene static；固定tracking背景网格有时序相位变化。 |
| UM-05 | PASS | 真实running cancel终态cancelled/released且result_ref null、人工稿与已采纳source不变；已批准CPU分工中公共ASGI队列取消幂等/准备decoder barrier清理后终态/晚到不发布均有实际生产service oracle。 |
| UM-06 | PASS | image→video采纳前仍归属image、显式对话接受后video来源改变；编辑后/取消后/离线JSON/TXT导出保持已采纳video来源及手工内容。 |
| UM-07 | PASS | 真实native model stopped/unreachable后人工编辑和TXT/JSON导出；受控失败支路与无模型人工路径由候选测试覆盖。 |
| UM-08 | PASS | 独立重算3调用/3lease释放，每lease至少3次inventory_empty且GPU≤baseline+1024；采样GPU峰22096<23552、最低RAM9280≥2048；原生NO_CLOUD/loopback日志与PID+birth+nonce exited witness。 |
| UM-09 | PASS | 实际START_LVW→Windows curl健康→同build正式React/FastAPI/headless入口；日志三次POST分析及页面静态资产；page errors/external requests空，Comfy零启动。 |
| UM-10 | PASS | 候选git blob绑定107 frozen项+4样本、packet1.0.3、工具身份/build复算；原进程exit/owned temp removal/终态授权及只读program02 settlement闭合；本隔离独审完成。 |

## 授权、资源与清理复算

批准request SHA `212b89a987dba5ad478a2f7cac6be35aa0520d7461c919003b500174fe49d108`与approval/child一致。111项冻结/样本hash校验通过，其中107冻结文件在候选Git中绑定；实际运行build `1b62171d…430d19`重算一致，工具bindings逐项重哈希。账本以SQLite只读连接查询，live05 calls=3、checkpoint=1、active=0、elapsed=61秒，cap8/1800秒、child/bindings hash一致；没有退款或复活旧slot。

Provider日志为3次send尝试（image、video、cancelled video），不是只数2次成功响应；第三次已计费而无发布结果。三租约各连续至少三次inventory_empty/GPU baseline+1024内，峰GPU22096MiB、最低运行RAM9280MiB符合硬限。原生配置明确NO_CLOUD=true与127.0.0.1:11434；后台日志原PID30304/birth_ticks639297884902758317/nonce5fe0…为exited且listener_owned=false。API日志原PID2273198正常Finished，模型stop不可达，owned temp已移除，原收据listener absent。断网结论限于本轮loopback/no-cloud及browser外联拦截记录，不声称全系统网络审计。

人类留样/人工体验未执行。下一步修复时序语义与局部oracle，封存新候选，按仍有效母授权派生有限子运行并独审；本报告不授权追加运行、不签完整R1/V1或人工体验。
