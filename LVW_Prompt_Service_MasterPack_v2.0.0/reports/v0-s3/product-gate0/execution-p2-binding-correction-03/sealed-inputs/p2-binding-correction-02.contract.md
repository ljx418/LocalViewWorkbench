# P2B correction-02 离线配置闭环合同（Codex冻结）

原correction-01 batch已EXPIRED/BLOCKED，保持worker failed、1次正常合成扣额、helper未启动/timeout未跑等全部事实。178绿测不替代场景配置正确性；原两项M01/M02实现仍待独审。此合同不准许任何新Windows/WSL实际批次，不访问固定CPU claim原owner、真实账本或原/tmp失败根。先离线闭环并独审，root随后才可激活DRAFT新child。

根因已精确查证：bad_helper把shim角色替换成tools/bad_receipt_fixture.py，而validate_config要求authority_root/tools/v0_s3_budget_authority.py；load_binding在启动_exchange前正确拒绝。禁止放宽role/path/production guard来让辅助程序通过。

## 最小修复

1. 故障helper使用第二个独立WSL tempfile fixture根（仍必须直接位于/tmp、lvw-s3-p2b-前缀及marker），保持全部固定角色位置：tools/local_program_authority.py、tools/v0_s3_budget_authority.py。第二个fixture的shim角色文件仅放明确的fault-helper测试vector，不冒充生产已扣额shim。所有authority_root、child/ledger/execution/binding路径及UNC必须在该第二根内部一致重新生成与封存。不得用泛化任意argv/role override接口；内部case enum足够。normal/timeout仍使用候选真实shim及原fixture，P1业务/预算模块不改。
2. 独立helper fixture必须在全套fixture/运行目录登记中出现；Observer读取helper实际根与新binding/request UUID，不监视错误的normal根。helper在正确的UUID/binding/PID-birth journal下运行，返回形状与DEBITED成功回执相同但只改request_id的受控错回显，真实exit0、无模型send、无authority debit。客户端必须在已启动helper且收到错误echo后拒绝，不能把load_binding早拒绝充该场景。
3. 新增有限case-plan admission函数，在任何实机启动前对所有normal/negative/helper/timeout计划验证生产validate_config、角色位置、UNC、marker/根归属、candidate/source/blob引用、期望正例或拒绝的具体阶段。root只允许这个固定case集合，不建设通用运行平台。合成回归必须真实构造与batch相同factory产物，而不是手写一个碰巧通过的假binding。演示旧bad_helper配置必拒绝，新完整helper配置可经原validator/load_binding（Linux等价路径）接受。用真实owned Linux Python执行helper测试vector，确认其JSON确实只有request_id与expected receipt不同、exit0/journal身份正确、未调用authority；这不是Windows实机证明。
4. 借由测试把normal/timeout和所有root登记清理联起来：合成stub driver不取代生产client/validator的配置读取，至少覆盖正负计划来源/阶段/观察根。复核M01两个checkout同child共享claim与M02预算/owner异常终态仍落盘；保留原178测试功能/断言不减。
5. 修未来收据计数：每次成功查询fixture calls后立即更新actual/last-observed synthetic debit；失败中断没有末尾查询时不能留下初始化0并冒充已知实际0，未知用null+来源说明/已知下界。所有fixture/owner/留存原因逐根记录，不遗漏helper根。旧raw synthetic_debits=0与calls_after_normal=1矛盾保留并用新errata解释，不改写旧收据。

## 实机准入闩

新runtime-binding-correction-02.child.json当前DRAFT_NOT_AUTHORIZED。新工具只能支持该新ID并严格检查status，DRAFT预检拒绝且Windows启动/host metadata/claim创建均0；旧两个child ID必须拒绝，无checkout/output重放。根源消费与角色规则不改。root以后只更新授权data状态和对应hash/候选seal，未经独审不能激活；实现者不能改child/合同/计划/manifest。若新child数据更新但工具源码无变，后续执行前由root比对独审blob再封存。

仅允许修改tools/v0_s3_runtime_binding.py、tools/test_v0_s3_runtime_binding.py；不修改program_budget/authority来绕role验证。新增证据reports/v0-s3/product-gate0/implementation-p2-binding-correction-02/。实现只离线合成，无Windows/WSL实机调用、无原metadata/tool重新hash、原/tmp retained读取/清理、实际CPU registry/真实ledger、模型/GPU/媒体/服务/网络/下载/完整checkpoint。Linux owned helper/SQLite仅新TemporaryDirectory与marker，P1真实SQLite策略可复用既有fixture但不能写原账本。

一次新增定向测试+受影响P2B/P1关键组合回归，命令/raw stdout stderr/exit、候选/source hashes、case plan接受/拒绝、journal/owned清理和旧失败保留都交付。旧失败root只是引用，不接触。Git作者ljx418 <1173696783@qq.com>。只READY_FOR_REVIEW，worker_done完整SHA/覆盖与风险；不签Stage/Gate0/质量/人签。两次同路线无新证据或进展停止交接，不能盲开新实机。
