# P3A 纠偏02：异常收据生命周期锚定

Root裁决：接受独审e9c910e的P3A-C01-M03；原M01/M02/m01已由独立4项断言关闭，不重复重新定义。新候选必须关闭继承异常处理对替换parent写失败文件、误报root_retained=false的问题。此为原合同无外部写入/失败证据义务的纠正，不增产品范围或授权。

## 允许修改与架构

允许tools/v0_s2_stage_runtime.py新增最小内部异常持久化扩展点（旧默认仍执行原保存逻辑，保留接口与行为）、tools/v0_s3_stage_runtime.py的受保护实现及生命周期、tools/test_s3_install_handoff.py/原P3A定向测试中的新增测试；只有该异常链确需时可最小修改包owner的受保护句柄生命周期，不重写安装器。新文本证据仅implementation-p3a-correction-02/。禁止改旧独审探针、历史测试断言/原始证据、公共合同/质量集/authority/坐标/MANIFEST。

薄seam方案：原_prepare调用一个可覆写的内部失败记录方法，默认逻辑保持旧S2；S3子类在进入继承_prepare之前固定证据父目录身份，覆盖异常处理及收据落盘的完整生命周期，最终释放描述符。不能只延长_deploy内with到返回，因为继承异常块在它外面。实际调用层次/方法名由实现者合理选择，但不复制整套_prepare。

失败文件只能通过原已登记父目录的无跟随、exclusive、单相对名句柄操作保存，不再使用失效self.directory pathname open。parent被移走而原inode仍有句柄时，允许向那个已拥有对象写真实失败证据（沿用已披露relocated-owned-inode限制）；绝不写替换inode。若确实不能安全保存，明确PERSISTENCE_UNPROVEN并保留原错误及内存诊断，禁止fallback pathname写或声称已持久化。持久化错误不能掩盖触发的原始错误，不覆盖旧文件。

root_retained等字段必须由已登记原root身份/安全句柄判断；旧pathname不存在不能推断原owned root已清理。若不能证明存在/消失，用null/UNKNOWN加实际观察说明，不填false制造清理通过。失败收据保留安装、部署、cleanup/retention原证据和本轮candidate/run身份。

在目标prepare开始前固定parent、register时固定root或等效已验证身份，覆盖早失败、部署失败、部署后准备失败；所有描述符在成功/失败/持久化失败路径有限释放。目录漂移时停止任何后续native边界动作和路径删除；保留正确原对象及证据。不能靠捕获异常后丢失所有记录来让单项测试变绿。

## 验收

新增生产_prepare驱动的明确Oracle：独审原M03注入下replacement父目录新文件0、服务启动0；原父目录安全持久化失败文件，或明确未持久化的失败终态（无假成功）；原owned root保留状态真实；原始异常不被覆盖。还覆盖早期部署失败、正常parent下失败、失败文件冲突/写失败和部署完成后准备失败，检查句柄释放及无删除未拥有对象。保留并运行原独审5项修复断言一次；其M03断言应实际通过，不修改原探针。旧四项最初观察无需重跑。

仅定向44项/新增项及旧23项S2回归；包owner未修改可复用其先前独立17项证据但不得说新候选重新执行了它们，若修改包owner则再跑相关17项。无需P2B或全面回归。严格受控Git/Python新synthetic夹具；实际Windows/WSL/PS/Parser/hosthash/媒体/模型/GPU/服务/网络/账本/完整checkpoint全部0。保存所有真实raw/exit、候选与测试绑定、fixture清理/保留、平台限制。

交付READY_FOR_REVIEW，独立窗口复核后由root裁决，不自签Stage。一次汇总修复，不增通用工具；同路线两次无新证据再停止交接，本次关闭三个原义务属于有效进展。
