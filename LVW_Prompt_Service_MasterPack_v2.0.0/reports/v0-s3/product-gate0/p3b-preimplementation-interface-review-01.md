# P3B实现中架构接线核查01（不是独立验收）

对象为恢复前中断的未提交稿tools/v0_s3_quality_phase.py，58886字节，SHA25662a6b51594ec838d309bd14a4a2584a6a66c06cdb0db18cf7ac2df9b8be8d186。当前Claude任务仍在实现，以下不是对未交付候选作Stage NO-GO；仅提前汇总原冻结合同义务，禁止逐条开启新Workpack/全回归。root未编辑实现文件或执行候选。若实现者已在修复，以最终源码和定向证据为准。

1. **实际公开路径**：稿第58行COMFY_URL=8188，而现有live_probe/base与S2SystemDriver.submit走8191。所有history/库存请求必须沿同一原驱动及有限loopback端点，不能提交A查询B；来源为现有base.COMFY_URL，不另造默认。
2. **可执行控制流**：第534行传deadline未定义；第567行HALT_ERROR_CODES未定义。正常完整16行正例及失败路径应都驱动到终态，不能由宽泛except把内部NameError当允许继续的样本失败。
3. **真实驱动协议**：构造器要求release_resources，但现有NativeRuntime唯一对应释放owner为release_preload(binding,worker)，其结果字段也不是model_inventory_empty/residual_snapshots。对接真实owner或模块内显式薄适配，组合实际库存/snapshot/物理释放证明；不能只给测试FakeDriver补一个生产不存在的方法。无需扩大既有源码白名单。binding/有效baseline不能缺失后跳过检查。
4. **raw先保存**：第548行之后先做after日志计数/监听身份检查才保存raw；_persist_row又先解析image metadata/video raw数组后写raw.txt。凡已收到的模型原字符串应在后续结构/计数/metadata解析失败前保存，不得因坏metadata、坏raw JSON或provider后快照异常丢失它。raw被保存不等于通过。
5. **持久化失败关闭**：_write_receipt第914行吞掉OSError/ValueError并返回完整成功对象，且配额不满足时静默不写。必须明确UNPROVEN、不可对外完整可评分，并将artifact写失败作为停止后续提交条件；首次目录重放不得向旧目录补写“新终态”。原错误、已保存证据和真实保留状态要可见。
6. **失败动作与调用计数**：提交数在submit返回后才加；provider计数在精确期望匹配后才加。失败/未知发送不能变成0或腾出预算；提前有限预留本行最坏1/4动作，观测数量不符或未知时记录真实已知/UNKNOWN、停止后续并保留34上限。禁止自动重试或旧日志补数。正式母账本扣额仍沿原生产owner，不由phase伪造。
7. **来源/路径/有界读取**：原preflight只在全批开始读一次源；受控authorize返回后、提交前以及终态需核对同一原对象/文件hash，source流读取有明确累计字节/时间限制，不能靠读到EOF处理不断增长的文件。artifact根/父目录也须防受控回调替换，不向replacement或旧目录继续写。按已批准有限callback威胁边界处理，不新建通用安全框架。
8. **保留原产品边界**：草稿VIDEO_EXTENSIONS还接受mkv/webm，当前公开产品只MP4/MOV；图metadata校验须包含长边<=1024等既有预处理事实。正式projection精确字段及固定16来源不应允许附带prelabels；评分收据也应核对实际10/6行与session、raw证据绑定，布尔不可当整数。

以上集中纳入QD/QS原批定向正负例，不要求额外真实运行、广泛回归或新权限。保持原src与失败历史、同一任务/工作区/候选责任人；代码只由Claude修改。发生429立即停止，root不接手。最终实现者交付后另窗独审，当前架构核查不给任何验收PASS。
