# P2B correction-01：唯一消费、可靠终态与最小跨OS补证（Codex冻结）

依据independent-p2-binding/review.md：原34de7b5工具F0/M2，原实机PARTIAL/NO_GO。原child S3-P2B-01过期不复活、原worker failed/UNKNOWN/FAILED_RETAINED不改写，不读旧PID当前状态替代当时证据。新增child S3-P2B-CORRECTION-01由COMPLETE03派生，非新人工许可，仍0真实model/ledger/GPU/媒体/服务/network/checkpoint。P1已验证的echo/事务规则不改，质量16与所有旧证据不变。

## 1. 唯一消费owner（M01）

每个child_id唯一的claim路径由新child精确固定在原live15权威ledger父目录下cpu-verification-claims，而不是ROOT/checkout/output。它是CPU执行许可消费收据，不是model预算ledger；不得读写program02.sqlite或修改预算规则。实际路径必须与已封存live15 budget_ledger.parent及child给定路径相符；不从worker路径派生，不允许另选目录。claim使用原子O_EXCL，禁止symlink/覆盖，内容绑定child_id/hash/candidate/preflight/output_root/claimer PID-birth/时间。所有checkout/大小写别名都争用同一个文件；输出只是claim属性，不是容量authority。已有claim无论RUNNING/EXPIRED/FAILED一律拒绝重用，换output/checkout/candidate不能重置。旧ID在新工具永久拒绝，不能用新工具把旧授权当可执行。

合成测试中使用同一已封存临时claim owner、两个不同checkout/root，验证仅一claim、另一0hostaccess；并发claim也仅一胜出。测试registry可在marker临时root内，不能动实际CPU registry。新真实batch才创建新固定owner一次，永不unlink退容量。日志保留与tombstone属于登记的持久产物，不是假称零残留。

## 2. 终态不依赖成功观察/预算检查（M02）

finally里所有owner观测、meter.check、清理、序列化均捕获为有限错误集合；预算超限或观测失败仍尽力原子写BLOCKED/UNKNOWN terminal和claim EXPIRED，包含已观察值/未知值/保留根/超预算原因。终态之前不能再有一个可抛异常的meter.check绕过持久化。统一输出预留64KiB终态容量；终态不把失败洗成功、不退款、不settle0。若底层存储本身完全不可写则保留最初exclusive claim、有限stderr并非零返回、明确terminal unproven，不能声称已成功落盘，也不让新路径取新容量。

统一meter覆盖所有本批stdout/stderr、fixture复制与小JSON/日志/输出（不能把169MB的metadata输入hash读取当输出）。每命令capture cap不超过剩余总量/固定上限，pipe/reader error与exit均需成功才能接纳数据；线程join未完成是失败，不因process exit0漏掉。超限为sticky失败，清理不洗掉；旧批次可用的保守预算证明仅作为历史，不冒充旧meter实际强制。新batch过程计数及最终保守复算两者都列，避免要求整台机器隐式服务普查。

## 3. 最小实际补证，不新增kill接口

先提交修复候选和合成测试，再生成新child预检，候选/合同/child/固定claim/preflight及输出根全部绑定。新batch一次，normal/hash拒绝或missing-child/真实坏回执helper/timeout在同一批次，固定真实Windows Python→wsl.exe→Ubuntu-24.04路径。已正确证明的平台正常/拒绝可作为历史参考，新批次必须核对自身候选和tools，不借旧run拼成新通过。

Windows driver启动即通过真实os.getpid及GetProcessTimes或现有process_birth记录Windows Python native PID/birth；不得把Linux interop PID当Windows本体。固定三个工具（Windows Python/wsl.exe/WSL Python）最多3文件64MiB重新hash与旧seal比对，复用其余旧metadata并明确未重验；不再扫其它工具/模型/Comfy。

Linux独立observer与Windows请求并发，限定已校验fixture root/request UUID journal，记录对应shim PID/start ticks，从ENTERED开始有界采样，覆盖超时wrapper前/后至remote同birth缺席，单调时间/次数/最大间隔/最终状态真实列明。observer最长30s、间隔<=0.25s且最多160次（受本批wall共同约束）；记录状态转换和关键时间点即可，不生成无界日志。确认连续两次同birth不存活才把remote观察终态认定已退出；不强求独立数字exit code，也不宣称自然退出或因果未证的kill。禁止重用旧run PID和记录当前旧PID。

超时可用本次合成SQLite有界锁：明确何时上锁/释放，不能用20s timer.join后单点缺席冒充超时边界链。若remote在观察截止仍活着/identity缺失，则非零BLOCKED，保留fixture reservation与根，不kill、不refund、不settle0、不扩大清理协议；后续由root依据真证据裁决。不存在给任意PID发信号/remote command平台。受限journal可以准确区分ENTERED/AUTHORITY_RETURNED_ERROR/OK，状态不代替OS存在检查。

真实坏回执用仅marker fixture可用的明确故障helper（不能说是生产已扣额shim），真实跨OS进程exit0输出错request_id/坏JSON后native客户端0send且记录错误，不能mock Windows os.name/_exchange或fake returncode。normal仍走候选真实shim与fixture authority/SQLite。已扣后丢ack必须保留扣额/未知reservation，0send；此拒绝行为是预期负例通过，不要求把未知成功请求改说成功。若remote退出与资源清理已证、UNKNOWN_ACK在fixture账本仍保留且登记保留产物，可以作为正确failclosed负例；UNKNOWN_CLEANUP则不能作为batch通过。可保留必要fixture/ledger/journal用于审计并明确区别临时垃圾，不能删除旧FAILED_RETAINED。

## 范围与测试交付

允许改tools/v0_s3_runtime_binding.py、tools/test_v0_s3_runtime_binding.py、bridge/program_budget.py、tools/v0_s3_budget_authority.py（后两仅必要journal/fixture身份/有界观察支持，不改P1预算/回执业务）。如需P1既有测试新增针对性case，可只追加其两测试文件，不改旧oracle。新证据限reports/v0-s3/product-gate0/implementation-p2-binding-correction-01/。不改任何其它合同/packet/计划/manifest/业务/质量集，原证据一字不改。

原83/P1关键回归保留，补M01跨root/并发、M02 finally预算或owner异常仍终态、统一output cap、pipe error/join失败+exit0拒绝、observer身份和超时边界及原字段不能假作nativePID。全部先合成，不访问原registry/原失败fixture/原PID/服务。一次组合自检后提交候选，唯一真实batch用新child，严格process64/wall1200/单命令30s/output16MiB/syntheticdebit16；不另开同child补试。预检尚未进入batch失败可修正后重预检，但exclusive claim成功后即已消费，不能因为0debit自动退容量。

新batch物理资源清理只本轮已确认owned wrapper/临时root/线程；remote只观察无kill能力。真实母账本/模型/媒体/GPU/网络/下载/服务/完整checkpoint动作全0。最后receipt区分测试通过/工具待审/实机已证或BLOCKED，保留所有raw失败、counter与未知；不签产品Gate0/Stage/质量/人签/发布。Git作者ljx418 <1173696783@qq.com>。两次同路线无进展即交接，不无限重试。
