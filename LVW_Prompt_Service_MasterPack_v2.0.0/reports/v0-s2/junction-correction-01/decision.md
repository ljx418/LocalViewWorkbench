# S2 Junction 身份与失败恢复纠偏 01

日期：2026-11-04。状态：APPROVED_FOR_OFFLINE_IMPLEMENTATION，codex_gate_owner。
本决定只允许已授权的离线修复，不增加完整真实运行预算，不激活 S3，不签署产品通过。

## 原运行事实

full-recheck-01 / 候选 9cfb17e92b5e918282af6e7c5b4030a92a2ecdfa 已 NO_GO，子授权 EXPIRED_NO_GO，lease.closed=1，原会话98629退出1。
两次完整依赖封存及启动前复核均通过：97078 文件／15810055916 字节，manifest 982e18638044d2b06b15f5808c31242adf5d9f484b7147ef7ef718ff1330748c。它们不证明任何产品用例通过。

真实顺序在测试 Junction 创建后的原生身份查询停止：StopProbe:REPARSE_NATIVE_IDENTITY_MISMATCH。两个原生查询均记录 path 为 outside-input、属性16、无 LinkType／Target。没有 Ollama／Comfy／模型／浏览器启动或调用；九项固定用例均 NOT_RUN。完整服务清理收据为0个拥有进程／0个目标监听／0个 HTTP 待处理。

原始报告 reports/v0-s2/full-recheck-01/receipt.json 与受控原始 terminal 均保留。raw terminal SHA256 为 9a77cbbc343192d28c245a112dcc2a7d6b3715baf158f1b1e076ca21874f91ed。不得改写历史公共收据来补新字段。

## 三项纠偏

1. Junction 身份核验和非递归移除改用已核实的普通父目录 Windows 路径，再字面追加固定 redirect 叶子名；不将已有 Junction 叶子传给可能解析到目标的 wslpath。Get-Item -LiteralPath 和 Directory.Delete(false) 都必须指向链接本身，仍严格要求 Junction／0x400／唯一允许目标／精确路径，拒绝外部目标。
2. OwnedArchive.register 在空根填充前以只创建、fsync 的文件持久保存原始 root／device／inode／candidate／authorization／run。device和inode用十进制字符串，禁止覆盖旧租约。新的恢复逻辑不能把历史路径的当前 inode 冒充原始身份。
3. StageSequence 的失败码向顶层终态和脱敏公共收据传播；此前失败仅位于受控 sequence 中，顶层打印 null。旧证据仍保留，未来执行不再丢失该原因。

## 残留目录与授权边界

原临时目录 STATE/full-recheck-01/lvw-s2-default-ccmmyy5d 因 Junction 核验错误而未能归档删除。此前根身份只在内存，没有创建原始 durable lease；进程退出后无法从已有证据独立复原原 inode。
retained-root-observation.json 仅记录当前身份与原清理失败，并明确不授权自动删除，不伪装成原身份收据。目录继续保留；尚未执行额外原生探测、清理或根接管。对该目录的显式接管、校验、归档和清理必须进入后续有限授权范围。

母授权规定每Stage最多一次完整 checkpoint＋一次完整纠正复验，现均消耗。修复和离线测试可继续，第三次真实运行不得自动启动。后续如确需补充运行，先提供完整离线新候选和明确请求，由项目负责人单独批准其预算例外与残留根接管。旧槽位不可重置、改名或复用。

## 验证范围

定向 driver17项、archive9项、parent11项测试通过。其中新增用实际临时符号链接及会解析叶子的转换器来复现原有测试遗漏，检查原生查询／删除命令保留链接叶子；其 PowerShell 结果为明确的合成夹具，不能当作本机 Junction 验收。新增租约持久化／不可覆盖与公共失败码传递测试。旧测试中同根重复注册的夹具改为一次注册后依次验证拒绝条件，没有放松生产拒绝规则。

提交新候选后执行完整 offline-checkpoint-20；只有实际命令和收据全通过才能报告新的离线门禁通过。完整 V1、V0.1、独立审查和人工签署均仍未完成。
