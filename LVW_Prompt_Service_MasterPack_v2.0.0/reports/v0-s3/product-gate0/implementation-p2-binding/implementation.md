# P2B 实现交付：READY_FOR_REVIEW；实机证据缺口 BLOCKED

候选 `34de7b54a529a8947d63736c6f1bd345828cad57`。83项合成测试通过；此前一项测试错误构造重复child绑定被正确拒绝，原始失败保留。输出根纠正前的启动在预检拒绝，0实机访问；纠正后唯一实机batch已消费并EXPIRED，不允许改路径复跑。

实际Windows Python 3.12.10 → 固定wsl.exe → Ubuntu-24.04 /usr/bin/python3 3.12.3 → 候选shim → 标记/tmp fixture SQLite完成1次synthetic debit，真实模型发送0。Windows大小写保留、中文空格与UNC实际通过；大小写变体拒绝仅合成测试覆盖。错binding hash和缺child在实际Windows拒绝。Windows wrapper正常exit0、缺child exit1、超时exit1/TIMEOUT，记录native PID/creation time、pipe关闭及threads joined。Linux记录成功PID1666044/start4877478、超时PID1666148/start4877530；最终均不再同birth存活。

超时Linux owner停在ENTERED，远端实际退出码和因果未采集；约1秒时确认活着，最终观察在20秒锁释放timer join后。不能把Windows wrapper退出等同远端立即退出，也不能把raw中的“natural bounded lock release observed”解释成远端自然退出。保留UNKNOWN、1次已有扣额和整个fixture reservation，未refund/settle0，未杀远端。fixture根以FAILED_RETAINED列明；所有脚本副本与SQLite留在该owned /tmp根，不提交。

计数：21.303秒；固定逻辑启动计数13/64（7直接命令+3wsl wrapper+3shim），未做隐式interop helper全量OS进程普查；9个固定metadata文件169955221字节；stdout/stderr3880字节，完整文本产物另计于receipt；1/16合成扣额，0真实模型/完整checkpoint/GPU/服务/媒体/真实ledger操作。单命令最长9.578秒，逐命令原始argv/exit见cross-os-lifecycle。严格统一输出计数、Windows Python自身native PID birth、远端exit status和真实坏回执仍缺证据，因此不声称P2B全部验收通过。

没有扩大cleanup协议；不需要root批准新的kill能力，因为最终观测没有仍存活的owned PID。本轮不申请重跑；请先隔离独审文本与合成负例，由root裁决后续精确合同。

完整大纲（来自只读execution-control，无进度增加）：

| 阶段 | 完成/总数 | 边界 |
|---|---:|---|
| V0-S0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-S1 | 5/5 | 已签仅V0-Min |
| R0 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| R1a | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0-S2 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0-S3 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1-M1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| R2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R4 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5a | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5b | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| R5c | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

V1-D0准备2/2；统一提前切片3/3已人签，只覆盖该切片。

十字段：

- 当前坐标：R1/WP-R1-U3，S3_P2B_FINITE_WINDOWS_WSL_BINDING。
- 本批完成：严格fixture分支、owner记录、有限工具、83CPU测试与一次真实Windows/WSL批次。
- 最后通过门禁：live15 UM10及独审/统一切片人签；本次不签任何门禁。
- 当前阻塞门禁：S3_PRODUCT_GATE0_REAL_PLATFORM_BINDING_AND_EXECUTOR，P2B仍有上述证据缺口。
- 全局路线位置：S3前置；完整R1/M1/R2及V2/V3未完成。
- 剩余工作：隔离审查、精确计数/远端exit/坏回执等缺口裁决；后续完整S3仍待。
- 下一责任人：协调root与独立审查实例。
- 所需授权：不缺原有CPU验证授权；当前child已终态，不能自行复跑或扩cleanup协议。
- 证据目录：reports/v0-s3/product-gate0/implementation-p2-binding；原始本地runtime收据目录见receipt。
- 精确停止原因：唯一实机batch已过期；实现READY_FOR_REVIEW，证据完整性BLOCKED，保留全部未知与fixture reservation。
