# OPT-B R07 最小差异独审

**OPT-R07-OWNER-01：CLOSED_STATIC；本轮新增 Fatal 0 / Major 0 / Minor 0。** 对 root 另行封存受控 R07 复验没有发现静态阻断；本结论不是运行 ACK、动态闭合或 Stage PASS。

唯一候选 `62e0d429dd78418220235359d068ae28d7b37e6e`，基准 `1a34fbbe318fbe240823a2bf2f09517a98294744`。T10 SHA256 独立核对为 `2a8e951b357068e835f6c7d276062395d83dc691ad5e51afde5c9e1da6cb64ac`。按主控 opt-b-01/scope.json、ADR16 实质义务检查全部 **139+/8-，147 行变化**及相邻依赖；实现注释仅作导航，结论来自精确 Git blob 与实际断言控制流。

T10:4008–4035 在 public admission 等待到真实 pump 已进入 read 后，将实际 `session._pump` 保存到独立 holder，随后才收紧原 context deadline。4087–4113 在 public start 返回后从 holder 读取对象；生产后台表经 `_session_owners` 返回真正 thread，observer 的 observed_threads/start_provenance 返回原对象和真实 start 返回状态，不按名字或模拟结果核身份。相关 API 与 producer 均逐段核对。

4127–4190 的 finished/alive/error/frames/context/broker 均来自 held pump；4225–4310 的调用者要求实际非空、finished=true、alive=false、error=None、同 context/原 broker、与生产 background 表及 observer 原对象一致、provenance=STARTED。session 槽只能仍指向该对象或 None；None 分支还拒绝 NOT_STOPPED/NOT_STARTED。**None 本身绝不构成完成。** 未变 custody:1585–1664 的具体清空路径为成功 bounded join 后清空；未启动清空路径由已观察的真实启动和显式失败码排除，仍 alive/未知路径保留引用并记失败。

原有15秒观察边界未放宽，观测和硬断言在既有 finally salvage 前执行，新增代码不改变、join 或伪造 pump 状态。未知/缺 holder/仍 alive/实际 error/异 context或broker/背景或observer身份不匹配/替换 session 槽均不能 PASS。新增查询若抛错会离开 body 并进入未变 finally，不能被静默消费成成功；相关故障注入尚未运行。

原瞬时槽 equality 断言是唯一删除的 assert predicate，已用上述真实对象身份及生命周期组合替代。实际公开 default launcher/start、event/queue exact0、admission noEOF/error-None、超时原因、返回 UNKNOWN_RETAINED、broker_retained=true、PARENT_ORIGINAL_HANDLE/PID/原 broker、returned pump_error、轨迹顺序及 finally stop/drain/清理断言全部保持。展示字段 ABSENT_AFTER_CONFIRMED_JOIN 在 facts 构造时只是槽状态标签，不能单独作清理证明；它不被用于跳过上述任何硬断言，故不将其命名扩大为新发现或框架需求。

源代码变化只在 T10 的 R07 和 attempt01→attempt02 路由；模块其他顶层 AST 与基准一致。117+16+24+18+14=189 的名字/顺序/签名/decorators 均保持，其他四测试模块 bytes 不变。生产 broker/custody 完全不变，SHA256 仍为 `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` / `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581`。这是静态数据核对，不是 collection 或189执行。

旧独审提交 **cfee57a** 原样保留；其绑定的19份 attempt01 原始产物在候选中逐份哈希一致，原13PASS/1FAIL不被改写。M2/M3 静态结论只引用旧报告，不重新扩大审查。原9项原生未知 N03-R16、N05-R06/R07/R08/R24、N07-R08、N10-R12/R13/R14 继续未证实。

**本轮 NOT_RUN。** 没有读取或轮询 attempt02；没有候选 import/compile/pytest/native/model/GPU/service/DB，没有修改候选。真实 held pump error/frames、R07 是否通过、后续 controlled 子场景能否到达均未验证；writer失败/重试、早期body失败/secondary publication、interrupted-start 查询失败负例继续未验证，常规通过不能代替负例。14不等于189或产品29，无 Minor 降级。

下一步由 root 封存新候选、依赖、guard、命令/nodeids、输出根和有限预算并 ACK，再作受控 R07 复验并独立核对原始失败/清理收据；本审查不启动或新增运行。仅提交本目录三个新文件，绑定及完整 disposition 字段见 source-binding.json / findings.json。

十字段：坐标 V1/R1/WP-R1-U3/S3_P4；本批差异独审完成；最后通过 UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前门槛 root 受控 R07 复验封存；路线 OPT-B→OPT-C；剩余真实复验/未证故障分支/正式checkpoint；下一 owner root；授权 静态只读、无运行ACK；证据 本目录及cfee57a引用；停止 CLOSED_STATIC / RUNTIME_NOT_RUN。实现候选已封存、机器本轮未运行、独审静态完成、无新增人签，分别记录。

完整V0–V3大纲（execution-control 完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
