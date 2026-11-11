# S3-PREP-B correction-01：安装所有权与回滚信任边界纠偏

Codex门禁裁决：原候选1c09cd651478beeb4c1bca026505364051a72892为CHANGES_REQUIRED；独审bcae94562786e71fd903566547f417bc5cebe90c的F-01、F-02、M-01阻断。原始失败必须保留。此次为原冻结包合同的安全修复，不扩产品范围、预算、Stage分母或旧人签。仍为0媒体/模型/GPU/服务/网络/真实宿主操作，0产品完整checkpoint。

基准：先从root给定的纠偏协调commit干净merge；代码与原实测仍以1c09cd6/0c96999为历史身份。允许只修改tools/v0_incremental_package.py、tools/test_v0_incremental_package.py，新增reports/v0-s3/preparation-04/implementation/correction-01/。原始implementation和independent日志/收据/执行器保持不变，不能在原路径覆盖失败。root manifest/业务代码/合同/计划均只读。

## 必修原则与架构约束

1. 回滚是全量预检后才发生第一项修改。来自外部收据的owned files/directories、created directories、preimage、staging、target、sandbox、session等字段都不是删除授权。严格类型/集合/唯一性校验；路径须规范相对路径、在原owned安装前缀内，拒绝..、绝对/盘符/反斜杠绕过、大小写冲突和symlink/reparse逃逸。任何一项拒绝时证明整个目标、外部victim和哨兵零写入零删除，不能先删29项再报错。
2. 安装成功时形成目标内的本轮所有权记录，绑定规范化target身份、sandbox marker身份、不可碰撞session、源candidate/manifest/payload集合与安装hash。此记录不是外部输入receipt的重复自述；rollback必须读取目标内真实安装记录并交叉核对外部receipt与沙箱marker，不得只用basename或同样的文件hash认定所有权。无需建立密钥服务/平台或对本机同权限主动篡改者作不现实承诺；局部持久记录足以防外部收据替换/重绑。内置记录自身路径/内容需校验，用户改写时拒绝，不能覆盖用户文件。同名不同target/sandbox、session不符、缺/错marker、缺失/冲突所有权记录、被改owned清单都应非零。外部receipt脱敏后仍须可使用显式--target，实际target从本地记录绑定，不能为脱敏便利放宽身份。说明本轮内部receipt/ownership schema版本；不修改产品公共API/schema。
3. 不再以外部receipt.staging.path对目录rmtree。成功安装应已清理自有staging，rollback只需确认本轮绑定的staging终态；可校验其字段与原本地所有权记录一致，但不能以路径字符串授予递归删除权。出现残留/不符则稳定失败并保留诊断，不清理未知目录。安装失败的staging清理也必须只指向本次函数实际创建且身份已确认的目录；失败回退不能移除非owned内容。
4. 所有权记录的创建/提交/错误回退须与安装同一事务边界；不可留下已安装但无法安全回滚的无记录终态并报OK。rollback安全移除owned记录，用户新增非owned内容保留。结构化终态只记录实际成功删除和实际剩余，失败非零、稳定错误码，不伪造staging_removed或sentinel_unchanged。

## 同根因和低风险纠偏

复用路径解析时顺带拒绝Windows段尾随点/空格及非法路径别名；不能只lower()防冲突。外部--manifest不可读/非法JSON按BAD_INPUT稳定拒绝。这两项是原合同路径/输入错误约束，勿扩大重构。独审m-02指出旧执行器故障路径残留，原脚本保留历史；新增本轮runner必须try/finally/TemporaryDirectory覆盖所有失败。仅核实由本实现者此前创建且能以记录证明的精确临时根，才清理；不扫删/tmp前缀或未知目录，不能删除审查失败证据。无法证明所有权的遗留目录记限制即可，不阻止本轮代码安全修复。

## 一次集中交付

先查看独审review.md、独立probe与原始失败记录。添加针对F-01/F-02/M-01及所有权记录缺失/篡改、不同session/target、receipt全部路径字段、用户改写/新增文件的公共CLI回归；必须覆盖预检失败全树不变。保留原38测试功能覆盖，不能删测试/跳过或改恒通过；旧正例若因新增所有权记录有合理终态变化，要记录新oracle，不能失去哨兵和实际删除证明。再跑新候选单文件定向测试和代表性独立负例（可在correction新目录复制适配旧probe，不改历史），无效恶意收据应非零拒绝且victim不变。已知成功链路仍可正常回滚，脱敏receipt显式target也要验证。

提交修复工具候选之后，从该精确Git候选重新跑一次真实仓库payload build→diagnose→中文空格sandbox install→rollback。包工具副本/hash必须属于新候选，旧证据不可改绑定新SHA。给出命令/raw stdout/stderr/exit、候选/工具/包/manifest/fingerprint、预先固定原文件/外部victim/非owned内容hash、本轮本地所有权生命周期、临时清理实测。真实包/临时副本不提交Git。最多两次同路线无新进展须停止交接；仅READY_FOR_REVIEW，不Stage PASS。Git作者ljx418 <1173696783@qq.com>。完成提交full SHA并worker_done，列变更/测试/失败保留/清理/风险。
