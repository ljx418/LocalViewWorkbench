# P2B correction-02 离线候选交接

仅 READY_FOR_REVIEW，任务 outcome=failed：代码修正可审，但本轮零原工具哈希读取约束未满足，且一次 Observer 间歇失败未得出确切根因。候选 `d339e53d0394fac172b7c984a1613faab2ec33df`；基准干净后 fast-forward 合并 `b387ce07e067709a67eb55eb4247fafb01b62c19`，无冲突。未激活 child，未执行任何 Windows/WSL batch。

生产 role validator、program_budget、authority 文件不改。normal 与 bad-receipt 使用同一个 factory 生成独立直接 /tmp marker 根；故障 vector 位于固定 shim 角色，独立 child/execution/ledger/binding 与 UNC 一致封存。Windows driver 始终取 normal 候选源，helper 只作为 binding 目标；admission 检查原 load_binding、候选源及 helper 固定源、角色、UNC、child/execution/SQLite 绑定，并报告正常/错误 hash/错误回执/timeout/旧别名各阶段。旧别名正确拒绝。Linux helper 回执仅 nonce 错、exit0、真实 journal 身份及零 debit 已观察，不冒充生产扣额。

preflight 与 run 首先拒绝 DRAFT/旧 ID；未知 debit 记 null，逐根保留 last_observed 与来源。终态登记两个根；原 M01 共享 claim 与 M02 预算/owner/serialization 失败断言保留。旧收据 synthetic_debits=0 不改，calls_after_normal=1 的旧 errata 仍适用。

## 实际验证与偏离

完整命令、cwd、exit、清理在 checks.json / rechecks.json / observer-diagnostic.json，对应 stdout/stderr 全保留。首轮 directed 3通过+13 setup errors、组合97通过+13 setup errors，oracle84通过。原因是未发现复制 authority 的 bind_execution 间接对固定 WSL exe 执行 digest，26个 setup errors 对应推定26次完整读取；无单独系统调用日志，不能声称0 host hash。未启动该 exe、未访问实际 claim/母ledger/旧失败根。

修正测试夹具：只替代复制 authority 的外部 WSL seal 为合成值，其他 digest 与真实SQLite封存保持；Path.open guard 拒绝 /mnt/c。没有手写替代 binding，也没有 mock 生产 validator/load_binding。第二轮 directed16通过，但组合109通过+1失败：Observer two_absences=False。保留该失败，补诊断打印后组合110通过；无法据此断言间歇问题已修复。原178断言未减、新16覆盖，总最终覆盖194；所有新增 TemporaryDirectory 由上下文清理，Linux helper reaped/readers joined/pipes closed。证据中的 PID 仅本轮 owned helper，不查旧 PID。

未来实机仍须独审；特别应审查重复 executable digest 的累计字节计数（authority bind_execution 与验证路径会重新读取）。本轮没有用实机进一步发现配置问题，没有修改 child/合同/计划/manifest/正式16/旧raw。

## 十字段停止报告

1. 当前坐标：{'stage_id': 'R1', 'workpack_id': 'WP-R1-U3', 'gate': 'S3_P2B_OFFLINE_CASE_PLAN_ADMISSION_CORRECTION', 'state': 'PREPARING_NEXT_STAGE'}。
2. 本批完成：限定两文件修正、候选提交、失败与复验文本证据；本轮约束违规如上，不声称成功闭环。
3. 最后通过门禁：UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW，候选 621b1bf386db71bfe08ca2f533fa8ec396b0504b，仅原范围。
4. 当前阻塞门禁：P2B_HELPER_ROLE_CONFIGURATION_AND_PRELIVE_REVIEW；另须裁决本轮 host hash 偏离及 Observer 风险。
5. 全局路线位置：R1/WP-R1-U3，S3 P2B 离线准入修正，不激活产品 Gate0。
6. 剩余工作：独立审查、处理间歇观察与重复hash计数，root 决定后续；不得使用此证据直接激活实机。
7. 下一责任人：root 协调者与独立审查者。
8. 所需授权：无新人工权限请求；新 child 保持 DRAFT_NOT_AUTHORIZED，只有 root 可在独审后激活。
9. 证据目录：本目录；receipt.json 封存代码/合同/child hash 与 Git blob。
10. 精确停止原因：交付审查候选但任务失败，零原工具hash限制违反且Observer间歇风险未闭合；不盲跑、不复活旧child。

## V0–V3 完整大纲（唯一坐标读取）

- V0-S0 基线探索: 1/2；实现=ARCHIVED，机器=NO_GO_HISTORICAL，独审=COMPLETED_WITH_BLOCKERS，人签=NOT_SIGNED
- V0-S1 图片与独立人工: 5/5；实现=DELIVERED，机器=ACCEPTED_SCOPE_ONLY，独审=COMPLETED，人签=APPROVED
- R0 独立服务复核: 1/2；实现=PARTIAL_REUSED，机器=SINGLE_IMAGE_SUBSET_ONLY，独审=NO_SEPARATE_R0_VERDICT，人签=NO_SEPARATE_R0_SIGNOFF
- R1a 单图React/FastAPI: 5/5；实现=DELIVERED，机器=ACCEPTED_SCOPE_ONLY，独审=COMPLETED，人签=APPROVED
- V0-S2 视频与资源控制: 7/8；实现=IMPLEMENTED，机器=COMPLETE_FIXED9_PASSED，独审=COMPLETE_FATAL0_MAJOR0_MINOR0，人签=PENDING
- V0-S3 离线质量与增量包: 0/6；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R1 人工业务骨架: 0/4；实现=EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING，机器=EARLY_SLICE_UM10_ONLY，独审=EARLY_SLICE_FATAL0_MAJOR0，人签=EARLY_SLICE_APPROVED_FULL_R1_PENDING
- V1-M1 多镜头拆分与逐镜头人物场景动作: 0/3；实现=DESIGN_ONLY，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R2 任务与正式运行包: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R3 镜头资产与检索: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R4 MCP与恢复: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R5a 证据与建议合同: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R5b 受控生成交接: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
- R5c 集成与完整交付: 0/4；实现=NOT_DELIVERED，机器=NOT_RUN，独审=NOT_RUN，人签=NOT_SIGNED
