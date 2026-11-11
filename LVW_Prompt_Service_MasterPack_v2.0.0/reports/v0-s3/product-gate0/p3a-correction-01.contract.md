# P3A 纠偏合同 01：安装交接的路径身份与收据一致性

root架构/门禁裁决：接受bdbe43c独审的P3A-M01/M02/m01，旧候选CHANGES_REQUIRED。不是新增产品需求、门限或授权请求；原P3A合同不改写，本补充记录实现白名单扩展。

允许修改：tools/v0_s3_stage_runtime.py、tools/v0_incremental_package.py（仅解决此次安全交接的内部可选受控接口/路径及错误清理，不改变默认CLI/旧回滚契约）、LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py；如需要新增包工具定向测试，使用原有包测试所在目录的新test_s3_install_handoff.py。新文本收据仅reports/v0-s3/product-gate0/implementation-p3a-correction-01/。禁止修改已交付审查探针、旧测试、原始收据、任何权威/预算政策、质量集/固定分母或治理坐标；无需新增通用管理工具。

## 必须关闭的三个义务

1. M01：检查与使用不能分处两个可变路径事务。真实安装commit必须锚定已登记root及目标父目录身份，拒绝替换/链接；不能只在返回后验证，也不能仅在同一处多做一次is_symlink便宣称解决。优先复用现有包安装owner和已验证contents，增加有限内部受控安装模式，使实际写入/rename、owner写入与失败清理使用锚定目录句柄/无跟随相对操作（若适用平台不支持，须在任何目标写入前明确fail closed，不能退回未经保护路径）。不得为了测试绕过真实installer。WSL Python实际负责本项目文件操作；无需建设跨平台安全框架。需说明OS支持边界，不能凭Linux夹具宣称Windows原生已验证。
2. M02：包输入在验证与安装交接中保持已验证对象身份和有界内容；不得再次经可变pathname读取未绑定档案。可将已绑定输入以无跟随句柄/私有封存内容交给现有验证/安装owner。原包路径若在交接中变成链接或身份漂移（即便字节相同），必须拒绝进入服务启动。新模式不得给任意调用方提供跳过包校验的入口；摘要/candidate/manifest/contents约束仍完整。验证后的路径/句柄与归档来源证据必须可复算。
3. m01：真实返回receipt.session_id必须与已验证目标owner.session_id一致，其他身份交叉校验保留。错误时服务启动0且记录原失败。

目录身份漂移后，不调用基于失效路径的删除/rollback去修复外部树。以安全锚定清理或明确保留并记录未知；不得无证据声明完整清理。预防写入未登记目录是M01的Oracle，事后拒绝启动或删除误写不能替代。目录在打开句柄后被移动时的支持/威胁边界须明示，不制造对任意恶意并发rename的万能保证。

## 测试与交付

保留原30+23检查；新增修复断言并运行原独审4项观察探针一次。原观察探针可能只记录缺陷而不按修复预期断言，因此必须另外建立明确Oracle：晚替换custom_nodes时外部目录写入0、服务启动0；晚替换包路径时服务启动0；session错配时服务启动0；正常真实build/install/inherited prepare仍通过。至少覆盖验证后/提交前、提交过程和错误清理三处身份变化；证明非本轮sentinel不变、错误持久化，无重试或副作用掩盖。不得改审查探针以消除复现。

只做定向测试、所改包owner的相关回归及原两文件回归。保留所有失败原始日志，受控Git/Python synthetic fixture外禁止任何子进程/网络，宿主Windows/WSL/Parser/可执行hash/真实媒体/模型/GPU/服务/账本/完整checkpoint为0。沿用原离线有限范围，临时包不超过原20MiB限制，fixture登记与清理。候选改变后新SHA，报告READY_FOR_REVIEW，交隔离独审复验，不自签PASS。连续两次同路线无新证据停止交接。
