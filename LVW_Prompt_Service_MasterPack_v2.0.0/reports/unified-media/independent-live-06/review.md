# live06 独立审查

**NO_GO，固定UM 9/10；Fatal 0 / Major 2 / Minor 0。** UM04真实时序语义失败，独审已完成，不能签人工入口、完整R1或V1。候选`8d43c1dcb79cedd16ce5143c8f68887de38e6572`，R1 packet1.0.3。候选、live06原始产物保持只读。

本次仅纯CPU重哈希、Git blob与机器产物复算、候选代码/测试静态审查及合成像素数学检查。零新增模型/服务/浏览器/媒体探测/媒体解码。未读取或依赖实现者结论。`recompute.py`以隔离Python运行，源绑定107个候选Git冻结文件及4个固定样本；CMD的LF→CRLF checkout差异显式复现。`pixel_math.py`仅从候选AST抽取统计函数，在独立假的像素原语上执行；不导入产品模块或PIL，不读取实际frame像素。

## 完整缺陷

**Major 1：背景/构图真实变化继续误判为恒定、静止。** 位置：`live-06/video-model-run.json`原始`message.content`与parsed_spec、`video-adopted.json`及后续导出的video_prompt。触发：固定tracking.mov，四源帧PTS1/3/5/7秒，四个源SHA逐项匹配既存原始decoder manifest，Provider确有一次temporal-sheet请求。实际文本说红框相对网格位置identical、camera framing/background alignment constant，推断背景visually identical/no structural changes；英文prompt直接写static，negative列motion/camera movement。预期：区别固定红框和变化的网格背景，描述可见相对位移/构图变化；无法判定物理镜头时保留unknown，不能断言背景恒定或把观察到的变化排除。

固定`tools/v0_s2_fixtures.py:28` recipe先画40px周期网格，再crop x=20+2*n，最后画固定红框(135,65,50,60)。12fps下四采样x=44/92/140/188，相位4/12/20/28各不同。既有同源SHA/PTS的`independent-live-03/four-frames.png`提供这一相对变化的视觉证据。本轮未重新解码。旧PNG为RGB另存，文件SHA不同于源frame payload；`recomputed.json`分别记录原始manifest源SHA和可视PNG SHA，未混称。旧运行只用于同hash输入的视觉事实，不借旧成功输出拼接本次模型结果。

**Major 2：统计fraction误读成percent，进一步以错误数量级支撑静止结论。** 位置：同一raw response的最后一条observation、第二条inference；对应原始证据`live-06/runtime-evidence/provider.jsonl`两次video的`pixel_measurements`。实际账本相邻different_pixel_fraction为0.343871/0.341304/0.333726，意味着34.3871%/34.1304%/33.3726%像素变化，而模型写approximately0.34%（约小100倍），并说likely compression artifacts/minor noise、no structural changes。预期：fraction按0..1读取、乘100才是百分比；变化比例本身不证明物理相机方向，不能以错误比例消除肉眼可见背景变化。未知原因的unknown字段不能抵消同时存在的恒定/静止断言。

## 新统计路径审查

冻结provider.py的`analyze_video`直接把实际`decoded.frames`传入`temporal_pixel_measurements`，源payload SHA也在同一函数由decoded.frames计算。统计函数转RGB，逐channel绝对差、三channel取max判不同像素，changed/(width*height)为fraction，三channel均值平均为mean_absolute_rgb_delta。结果同一对象传入用户message的Measured adjacent-frame... JSON，并写provider_call_started账本；没有样本答案/运动类别/方向硬编码。真实两次video测量完全一致；image统计null。原始数据链与source SHA/PTS绑定有效。

`pixel_math.py`对完全相同、1/4单channel255变化、1/3全channel255变化、全像素255变化四个独立合成oracle分别验证fraction0/.25/.333333/1和mean0/21.25/85/255，全部通过。没有发现统计数值单位算法错误。真实mean19.948187/19.711854/19.509985与fraction被作为原始账本保存，本轮没有从实际media再生成这些数值，因此不声称新增像素级独立解码证明；这不影响fraction到percent的确定性复算或同hash背景变化事实。

本次浏览器UM04明确BLOCKED等待独审，分工正确；没有沿用live05局部假绿oracle缺陷。独审完成后该项裁为FAIL。整体机器receipt一直INDEPENDENT_REVIEW_PENDING且stage_pass_claim=false，未称完整Stage已PASS。

## 固定10项

依据已批准且program02吸收的RUNTIME-01 scope，真实duration/corrupt与完整真实image/video/adopt/cancel/offline序列，加候选绑定CPU受控负例/race共同判断。没有增加模型负例、改变分母或阈值。候选共享decoder、media/service与准备/排队/晚到测试相对live05未改变；候选测试源码已另存`candidate-tests/`并审查生产owner/oracle/cleanup。program02-offline-02旧CPU日志只证明未改受控路径的已批准复用，未冒称新候选重新运行122项。新增provider统计由本次独立数学检查与真实调用数据验证。

| 项目 | 判定 | 证据/边界 |
|---|---|---|
| UM-01 | PASS | 原始图片响应、公共请求日志及人工稿采纳前保护；image-model-run、image-draft与before-video-adopt来源一致。 |
| UM-02 | PASS | 批准RUNTIME-01 scope的真实+CPU分工：live06真实422 duration/corrupt；候选公共ASGI负例在Provider前拒绝并清空media/video-temp；共享生产validate_probe/stage_video覆盖bytes/pixels/container/empty边界，未把模拟称真实模型。 |
| UM-03 | PASS | live06四实际PTS=1/3/5/7秒、四独立源hash、source SHA绑定；候选shared decoder sparse/eof测试驱动生产owner，验证1/2/3帧、无重复补帧、bounded调用和cleanup；单帧warning与统一Provider采样局限保留。 |
| UM-04 | FAIL | 真实四源帧一次请求，但继续将相对网格/红框背景变化判恒定与static，并将0.343871 fraction误读为0.34%；真实语义FAIL。浏览器正确BLOCKED等待独审。 |
| UM-05 | PASS | 真实running cancel终态cancelled/released且result_ref null、人工稿与已采纳source不变；已批准CPU分工中公共ASGI队列取消幂等/准备decoder barrier清理后终态/晚到不发布均有实际生产service oracle。 |
| UM-06 | PASS | image→video采纳前仍归属image、显式对话接受后video来源改变；编辑后/取消后/离线JSON/TXT导出保持已采纳video来源及手工内容。 |
| UM-07 | PASS | 真实native model stopped/unreachable后人工编辑和TXT/JSON导出；受控失败支路与无模型人工路径由候选测试覆盖。 |
| UM-08 | PASS | 独立重算3调用/3lease释放，每lease至少3次inventory_empty且GPU≤baseline+1024；采样GPU峰21910<23552、最低RAM9724≥2048；原生NO_CLOUD/loopback日志与PID+birth+nonce exited witness。 |
| UM-09 | PASS | 实际START_LVW→Windows curl健康→同build正式React/FastAPI/headless入口；日志三次POST分析及页面静态资产；page errors/external requests空，Comfy零启动。 |
| UM-10 | PASS | 候选git blob绑定107 frozen项+4样本、packet1.0.3、工具身份/build复算；原进程exit/owned temp removal/终态授权及只读program02 settlement闭合；本隔离独审完成。 |

## 授权、资源和终态

request/approval/child hash、packet hash、全部工具bindings、候选build均复算一致；build为`57326589f2fb0ca615819f44ae0111e7e12ed3609887f156df727749de03984f`。独立Provider计数3次send尝试（2成功+1取消），3租约均至少连续三次inventory_empty且GPU在baseline+1024内，峰21910MiB<23552，最低RAM9724MiB≥2048。native NO_CLOUD=true与127.0.0.1 host配置原始日志存在；owner nonce7e9b775814024b6dad954810d6bc6b89、PID32156、birth_ticks639297889990889953为exited/listener_owned=false。API原PID2293936日志Finished，原启动器报告owned temp removal，stop记录不可达；清理收据listener absent。浏览器外联/错误数组为空。网络结论限于本轮配置和捕获范围，不声称全系统网络审计。

SQLite账本只读查询：live06 calls3/checkpoint1/active0/elapsed54秒，cap8/1800秒，child与bindings SHA匹配；live05保留3/1/0/61，累计actions6、effective checkpoints2、elapsed115，不重置、不退款、无旧slot复活。母授权仍有效，人工体验与11个人工留样未执行。

可在同范围后续候选一次纠偏：清楚表达统计单位/量级，改善全时序背景对照与输出可靠性，保持真实局限；不能只把technical字段改unknown而留下observations/prompt/negative中的相互矛盾内容。新候选须重新有限实测并独审；本报告不签人工、完整R1/V1或发布。
