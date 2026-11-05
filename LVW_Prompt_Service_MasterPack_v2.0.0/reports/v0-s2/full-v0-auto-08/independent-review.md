# V0-S2 full08 独立 Stage 审查

隔离审查者：/root/s2_full08_stage_review。候选719c74559393a6489b2f630a1e0d3bc3303eb655；只读复算，未修改候选、未启动原生服务/模型/GPU/媒体解码/浏览器/网络，未拼接旧full或组件。

结论：本轮机器证据可采信，Fatal=0/Major=0/Minor=0，建议进入人工体验签署。不是S2人工签署、V0.1接受或发布。

## 独立检查

- python3 -B -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py' -q：541 tests /50.934s /OK。
- offline44：10日志SHA一致；310离线artifact中309不变，唯一变化为运行坐标plans/execution-control.json。独立source_gate复算269执行文件，payload71bb598052454a714896d1bd3d3dac320d3134375fc5f41beec234bebe6b0554；CPU测试后源码仍与候选一致。
- 公开15项逐项重算，含10负例/4视频/decoder。视频来源/PTS/时基/Provider计数一致；native-decoder与category-vfr四帧PTS及PPM SHA完全一致，固定fixture字节身份一致。
- 累计24份public trace：A01=1、A03=3、A04=6、A05=13、A08=1；prompt唯一、人工稿/实际导出字节、20,000字符与精确失败转换逐值复算一致。
- 取消/故障/浏览器九项原Oracle重算与保存值一致。准备/推理取消反馈0.05677/0.07539s，推理取消释放4.406s；浏览器取消反馈0.06623s；故障停止至释放5.844s。
- warm20由interval/history/events与637条资源采样重建hot_record/performance_oracle；20条逐值一致。10图+10视频，50真Provider调用，20预加载；图片P95=9.422s，视频P95=24.5s，GPU峰21470MiB，RAM最低7443MiB。
- default归档262文件21036697字节；warm归档103文件16272141字节；全集逐项SHA无缺失/额外/不一致。
- 五次完整依赖封存一致：97078文件15810055916字节，manifest982e18638044d2b06b15f5808c31242adf5d9f484b7147ef7ef718ff1330748c；另独立读取9个实际工具文件重哈希符合绑定。
- 原PID/birth、监听/HTTP worker/采样器/browser/group/profile/tmp清理闭合；原default/warm根均实际消失。lease.closed=1；授权EXPIRED_MACHINE_CHECKPOINT_COMPLETE；九项PASS，无FAIL/BLOCKED/NOT_RUN；公开receipt由原terminal重新构造脱敏投影逐值一致。

## SHA绑定

terminal：ea8fee340c63928e125c1b559276bf5591617c4ecee2e23bc6fc631f77acc0b1

reverification05：6bad75f65a03a4d181c539482d12d08ec2c2908b78bfe4989e3fa47f572fcb6e

public receipt：53c267a19a60b34b8aa7abc065f696ac8eb46b1549cd66a24135d7b67fb61f96

default manifest：4e10efad9c3034a784690989efa8443a5a39f5e257008f8b52cadec5396354e4

warm manifest：799ac65cdd75d6e56d7452302c1fedbf7898f0c967928c8fb3551b1d9583d53c

## 覆盖边界

未重新解码像素；核对既有真实FFmpeg结构/时间线、本次原生decoder、public history与来源/帧SHA，不把YUV framehash和缩放PPM混比，不新增门限。未执行第六次15.81GB安装树全量重哈希。人工体验、语义质量与后续S3质量集不能由机器代签。
