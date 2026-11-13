你是隔离Codex独审者，复验S3-P4纠偏候选7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0相对74ff021，未参与实现。不继承实现者通过结论，不派生Agent，不修改候选。root包 /mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0。
先读root AGENTS/parallel-execution/当前控制和s3-integration-offline-contract-01.md；复验依据是root reports/v0-s3/product-gate0/audit-correction-review-01/received/review.md、negative_probes.py、rawlogs，以及root-decision.json中的3Major1Minor。实现者总结仅可在独立判断后对照，不拿CONVERTED_ORACLES_OK当结论。
在现有review工作区先保存git状态，干净则checkout --detach候选7ed2116（对象共享无需fetch），禁止root/实现工作区改动，不清理/重置任何工件。只能NEW reports/v0-s3/product-gate0/independent-audit-correction-02/ 写独审报告/诊断脚本/日志；可提交仅新报告，候选源/合同/门限/24分母/全局MANIFEST/坐标不得改。
严格零fixture子进程/零网络/零模型GPU/服务/原ledger，不执行任何带binding runner。共享counter /tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json 仅只读，active=false、2PENDING、admit2、reserved120/180、spent2.896；记录前后hash相同，不写/退款/清零，不消费最后60秒。
全面审查变化3份源码 executor.py/run_guarded_checks.py（均implementation-integration-01目录）、tools/test_v0_s3_supervisor.py。逐项复验：
M1 本次真实guard事件关联executor/charge/thread/action且一次性；copiedmarker+gateerror、复制整个凭据/外层类、旧真实拒绝重放不能释放当前占位；真实guard正例须走生产链，不伪造异常自证。检查独审原负例触发条件未被弱化；不把任意恶意进程内存篡改上升成本轮不存在的威胁模型。
M2 finish抛错/返回false在有句柄和无句柄两条路径均不能提前假写终态/假cleanup；持久化不明仍open/UNKNOWN、非零并保留根。检查一次性凭据消费与finish失败的组合，别用新本地字段掩盖counter的PENDING；实际计数不减少。
M3 显式安装异常、真实CPython静默拒绝、已有旧hook/alias、当前注册instance握手应failclosed且在pytest/候选导入前；无法用旧hook应答新握手。正常安装与幂等工作不能被新防护误阻断。
m1 完整有效argv/command与orig_argv/programmatic/UNKNOWN语义真实，modules/select/binding/hash/role/candidate不丢；旧证据不改。
只执行一次受影响focused10及一次guard4，保存真实外层退出/原始stdoutstderr：候选生产runner无binding，--mode focused --label independent-audit02-focused --modules tools/test_v0_s3_supervisor.py --select "refused_start or machine_accounting or real_guard_refusal or copied_marker or replayed_real_guard or settlement_failed or proof_of_a_child or guard_installation or complete_effective_command" --outdir reports/v0-s3/product-gate0/independent-audit-correction-02；guard用--mode guard --label independent-audit02-guard。不机械重跑57/100/92/71/257。根据原独审脚本自主构造必要零进程负例，不能照抄作者反转结果当独立反证。候选import前必须外层硬守卫禁进程/网络；runner安装若不可靠不能无守卫导入。记录skip具体原因，不计PASS。
报告一次汇总全部可复现F/M/m（位置/触发/预期实际/证据/命令），F0M0也需实证。输出4项状态及回归影响、源码hash、日志/收据hash、原counter前后不变。原历史2PENDING裁决建议仍可引用上次原始traceback，不对账写counter。真实13fixture/完整24集成/WindowsGPU原ledger等仍NOTPROVEN，不能签StagePASS。
完成worker_done后root归档回收窗口，默认不keep-open。
