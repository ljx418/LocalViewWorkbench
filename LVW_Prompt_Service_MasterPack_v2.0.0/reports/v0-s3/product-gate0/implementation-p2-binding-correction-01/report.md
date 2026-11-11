# P2B correction-01 实现交付：READY_FOR_REVIEW / 实际批次 BLOCKED

基准 b54b0a4cd315426e1884b04a764629696e55b57c 从干净工作树无冲突快进；代码候选 a57258624419377cb8247ccfd07fe30f0051328d。实现任务未全部完成，worker outcome=failed；READY_FOR_REVIEW仅表示交付可审，不是工具/批次/产品通过。

已实现固定共享 O_EXCL claim（校验 child、历史授权父目录、跨大小写 samefile、拒绝 symlink）、finally 独立捕获 owner/预算/序列化错误并尝试持久终态、输出预留、pipe/reader/join 错误优先。补 Windows GetCurrentProcess/GetProcessTimes 本体 PID/birth、受限 UUID/binding/PID-birth observer、原子 journal、明确 fixture 错回执 helper。P1 client/回执判定和真实 authority 预算业务未改，shim 只修改 journal 发布/状态。两次组合自检均94+84=178通过，第二次因原子 journal 修正而复跑；初次日志全部保留。

唯一新批次 claim 成功后消费，17.750220s 后非零 exit1，EXPIRED/BLOCKED 已落盘。正常 Windows Python PID26804/birth134389022820385865 → wsl wrapper PID41948/birth134389022822578161 → WSL shim PID1723500/start5014329，正常扣额1、0send；坏hash真实拒绝；normal observer 6次、最大间隔0.106829s、连续两次同birth缺席。不得把这些已退出身份用于新的进程操作。

第二个 Windows driver 在 load_binding 拒绝 alternate shim path，原因是既有 validate_config 只接受 tools/v0_s3_budget_authority.py；helper尚未进入真实跨OS交换，因此坏回执未实测，timeout未执行。保留完整 traceback、native-bad-receipt.json 和160次无身份观察（17.104532s，最大间隔0.121335s）；没有身份不能冒充cleanup通过。代码缺少本 helper 配置准入的合成集成回归，本批失败不能靠178绿测覆盖。修复路线需在固定 fixture角色边界内设计明确helper且先验证实际配置，但本实现没有再改候选/再起batch。

raw/cross-os-lifecycle.json 的 synthetic_debits=0 是末尾查询未执行的初始化值，原始文件不改；同文件 calls_after_normal=1 和真实 DEBITED 回执证明本轮实际1次，失败driver在load_binding先拒绝，未调用_exchange，无第二次扣额。16是预留上限不是实际值。真实模型账本读写、模型发送、服务/GPU/媒体/network/download/full-checkpoint均0，无refund、settle0或远端kill。

计数：运行meter启动预留22、直接Windows driver2、实际wrapper1、remote shim1；含预检/报告工具的owned保守上界40<64，不是全机隐式进程普查。3个固定工具初次hash共8,383,928字节，均与旧seal匹配；把fixture协议内对相同工具的重复seal读取算入，Python不超过5次、wsl不超过6次、Windows Python1次，共41,757,880字节<64MiB，保守记42,000,000。其它metadata不再盘点。最大外层命令0.421559s；单命令30s限额未触发。output meter预留7,531,419字节，包括两命令4MiB捕获、3MiB内部固定writer envelope、64KiB终态以及源复制/JSON；已登记fixture138,727字节，报告约0.2MiB，保守总输出上界10,000,000<16MiB。内部预算采用保守预留而不是逐写实时计量；stderr仅保留UTF8 replacement解码结果，不能声称原二进制stderr无损。

本轮/tmp/lvw-s3-p2b-中文 Space-kbrmm4gi登记FAILED_RETAINED，保留fixture SQLite reservation、journal、源码与结果作为审计产物，清单见receipt；不删根、不退款，原旧失败根完全未触碰。没有当前仍运行的owned外层driver/pipe/observer线程；normal remote两次缺席已证，helper远端未启动，timeout未启动。共享CPU claim是消费元数据，永不删除重置，不是program02.sqlite。已复制raw claim与原始runtime输出，原始失败终态不回填成功。

十字段：
1. 当前坐标：R1/WP-R1-U3，S3_P2B_CONSUMPTION_TERMINAL_AND_LIFECYCLE_CORRECTION。
2. 本批完成：修复候选/178合成回归/一次真实批次与失败归档；集中补证未完成。
3. 最后通过门禁：live15统一切片UM10机器、独审及人签，仅既有范围。
4. 当前阻塞门禁：P2B纠偏待审，真实helper和timeout缺证。
5. 全局路线位置：S3产品Gate0前置，非阶段验收。
6. 剩余工作：helper固定角色配置修复及完整补证由协调者裁决；此child不可重用。
7. 下一责任人：协调者与隔离独审，实施者无门禁裁决权。
8. 所需授权：不请求重复CPU人批；本child已永久消费，不自行派生新批。
9. 证据目录：本目录raw、checks、receipt、outline-snapshot及SHA256SUMS。
10. 精确停止原因：唯一真实批次PROCESS_EXIT/authority root roles，任务未全成，保留失败交接。

完整大纲（execution-control原值，未增加完成数）：V0-S0 1/2历史NO_GO；V0-S1 5/5已签；R0 1/2；R1a 5/5已签；V0-S2 7/8机器/独审通过而旧人签待；V0-S3 0/6；V1 R1 0/4、M1 0/3、R2 0/4；V2 R3/R4各0/4；V3 R5a/R5b/R5c各0/4。V1-D0准备2/2、统一早期切片3/3保持既有范围，完整R1/V1仍未验收。当前实现仅待审，完整批次BLOCKED，未独审、未新增人签、未签产品Gate0/Stage/发布。
