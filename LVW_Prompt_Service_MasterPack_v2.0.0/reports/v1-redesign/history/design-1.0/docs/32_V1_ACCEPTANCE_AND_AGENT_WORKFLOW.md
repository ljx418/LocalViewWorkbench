# 32｜V1验收设计与Orca协作制度

版本1.0，DESIGN_REVIEW。旧UM10和历史V0/V1证据不改；新V1固定29组=原21+MS01–08。产品范围批准不是新接口Gate0或当前切片人签。源：[release gates](../plans/release_gates.json)、[cases](../plans/acceptance_cases.json)、[角色批准](../reports/v1-redesign/product-change-approval.json)。

## 固定验收与独立样本

原Q01独立12图+6片、图>=10/12/片>=5/6、五维总>=8且关键幻觉0完全保留。新多镜头另设12个非私有视频，开发/独立样本分开；既有11个人工留样不得静默用来调优。独立标注先于模型运行冻结，目录必须有source/license/hash、PTS、切点、镜头清单、人物/场景/动作及unknown预期。无标签或样本hash未冻结时不能Gate0。

建议固定组合：6个明显硬切片，各含5/5/5/4/4/4镜头（合计21个标注切点）；2个无切片覆盖摇镜/闪光；2个渐变/叠化片（疑似需可校订）；1个VFR四镜头；1个短/快切八镜头。合计47个计划镜头，实际不同帧时间必须标注。18段内容质量子集在这47段内预选，不能结果出来后挑：12个简单动作、3个含糊动作、3个静态；人物多人/遮挡/换场景覆盖。样本实际取得与哈希尚未完成，以上是待独立标注冻结的设计，不伪装已有47段真实输入。

MS01切点一对一匹配、P/R>=.90、容差±2实际源帧；无切负例不能因人物移动/闪光误切。渐变不强求逐帧精确但必须标疑似并能人工修订。MS04五维：人物、场景、动作、证据一致性、未知/局限，各0–2，总>=8可用；总>=15/18，动作子集>=10/12，含糊/静态六段不得虚构动作、关键幻觉0。分母/阈值经Gate0冻结后不能由实现者更改。

| ID | 生产路径与oracle | 必要负例/证据 |
|---|---|---|
| MS01 | public detect→PTS owner→候选列表，与独立切点匹配 | 无切/闪光/摇镜、VFR；所有检测/未匹配切点保留 |
| MS02 | public边界编辑→版本事务→stale结果/旧稿 | 零长、越界、旧etag412、合并/拆分影响范围、旧revision不变 |
| MS03 | segment owner→实际解码帧→ModelRun绑定 | 帧边界exact/oneover、短段少帧、跨切点/重复帧拒绝 |
| MS04 | 同镜头真模型→人物/场景/动作证据→独立评分 | 错误动作/串人物/串镜头、空答/拒答算不可用；raw不改 |
| MS05 | 固定父子清单→worker CAS→public取消/重试 | 真实queued/preparing/running、重启interrupted、late结果不写、实际释放 |
| MS06 | 真实React→逐镜头采纳→人工版本→导出 | 切换不串稿，失败不覆盖，全部计划行有状态，格式切换0调用 |
| MS07 | public上传/计数/lease→资源/清理 | 12/13、视频边界、root逃逸、GPU/RAM/OOM、清理未证实保留预算 |
| MS08 | migration/repository→重启恢复→旧合同回归 | 部分迁移/磁盘满/rollback、旧revisionhash不变，原单图/整片路径保留 |

每个义务需要公开owner/驱动/oracle/负例/持久终态/清理链。HTTP200、退出0、schema存在和模型自述都不单独算通过。缺失、BLOCKED、SKIPPED不得PASS。raw语义评分与程序结构证据分开，不用数字替代识别能力。

## 检查点与人类门槛

- Gate0：Codex设计+独立设计审查、准确DTO/OpenAPI overlay/DDL迁移、样本标签/hash、oracle/预算/commands、owner/file范围全部冻结；D0工具通过仅证明规划结构，不能替代产品Gate0。
- Workpack：Claude定向合同负例/单元/类型，提交candidate、files、production path、commands/exit/loghash、risks，状态READY_FOR_REVIEW。无需每文件完整E2E。
- Stage结束：受控执行器先集中CPU/合同/前端/治理与包检查；全部必要离线命令在真运行之前完成。再一条代表性三镜头生产链，诊断不拼接完整验收；继而一次新鲜固定分母真实checkpoint。
- 隔离审查：独立上下文/副本只读候选和原始证据，复算样本、质量、生产接线、预算及真实取消/清理；不自行修复后自签。Fatal0/Major0才能由Codex裁决机器就绪。
- 人类门槛：现有621b1bf统一切片体验签署仍待；R1、M1分别交付其新增体验后实际签署；R2最终29项完成后V1体验及发布签署按原政策办理。机器与独审不能替代人签；可在同一已冻结Stage批量验收，不要求每Workpack人批。

父任务最多12子项，单次分析420s，父总1800s；完整checkpoint预算必须按固定全样本清单计算，不误用整片四帧的8动作预算。设计估计47镜头+原18质量+UI/故障<=80次模型/10800秒一个完整轮，低于父授权单次上限时才可冻结；实际样本/动作账本高于预算须先调整执行包并核对父授权，不能截断分母。资源硬阈值不变。原全局1024/24/48h含历史；每次有限子运行绑定候选/模板/模型/样本/工具/端口/进程/清理。

## Orca任务与分工

Codex在主工作区维护PRD、总体/详细架构、合同、质量阈值、Stage packet与唯一当前坐标；不再默认批量写产品。ClaudeCode实现窗口在Orca可见独立子工作区，有明确owner/允许路径。每次分发附spec manifest与基准commit；代码与审核不抢同文件。

初始只开两个窗口：`LVW-D0-Implement`实现规划校验器/测试；`LVW-D0-Review`独立审核新设计/边界/验收/可实施性。两者无产品GPU/服务/媒体权限，报告返回Codex后协调者统一处理合同问题，不让实现者改规则。D0审查通过后再冻结产品Stage并派发实现；当前产品前置签署不被D0绕过。

Codex通过Orca Dispatch mailbox协调，读取真实worker_done/commands/files/risks，不能把窗口启动回执当已开发。Orca保持窗口供用户查看；额度/登录/启动错误必须报告实际状态，不秘密购买、更换供应商或冒充另一个Agent。一个Workpack唯一实现负责人；审查队列增长时先验收/修复，不不断增加实现窗口。

实现收据必须含project/stage/workpack/candidate/spec_hash/acceptance_hash/run_id/provider_model（可验证时，未知如实写）/commands/exit/原始日志hash/调用链/风险/清理。失败保留；跨会话由Orca Task+仓库收据恢复，不能依赖整段聊天。Codex审核有效发现并裁决；实际人签后立即记录、普通Git推送；没有发布签署不发布。


授权账本映射：现有COMPLETE03的stages不含新显示名V1-M1，因此M1作为已批准的V1/R2提前子阶段执行，有限收据同时绑定design_stage=V1-M1、authority_stage=R2、此次范围批准hash与新packet；仍计同一全局账本，不修改旧授权hash、不新增预算、不把V2/R3改名混入。此映射必须在M1 harness负例中验证，不能把任意未授权stage映射R2。
