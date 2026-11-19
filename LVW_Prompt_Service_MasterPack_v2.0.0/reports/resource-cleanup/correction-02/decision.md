# 资源清理纠偏02：采用独审02剩余8项，不改写历史

本次仍是用户明确授权Codex接替的资源清理增量；主干保持暂停。不扩大到未知进程关闭、阈值放松、模型下载、私人媒体、付费服务或真实完整产品PASS。

1. 独立的loopback TCP观察区分连接拒绝（absent）、连接建立（responding）和超时/其他错误（indeterminate）。清理后必须原生退出、资源范围和最终端口absent均可证；HTTP500/坏JSON/超时不再充当端口退出证明。真实状态返回包括listener_observation；未观察/失败/跳过有各自原因。
2. Provider.acquire同步保存当前原生nonce/PID/birth代次；外部服务可正常按既有分析授权运行，但其lease没有可接管的原生代次，清理拒绝收养。当前句柄不同或代次缺失都不允许停当前服务或清除lease。所有start/reset/stop及service.runtime_control在遗留lease时先拒绝，不再默认调用旧provider.release尾处理。
3. inventory强制model字段存在并等于name，其余非空白、digest、size_vram和重复检查保持。
4. pending与遗留lease阻止新任务提交，pending也在队列执行/获取lease前阻断。readiness/model_ready/控制按钮状态同步显示待核对，不冒充已就绪。正在正常运行的当前job允许维持既有队列行为。
5. v3在产品导入前校验独占data目录真实身份与新鲜性，拒绝子目录symlink/hardlink；写证据使用相对目录FD、O_NOFOLLOW和普通单链接文件校验。比对实际Python、Chromium、Ollama、PowerShell与PATH选定nvidia-smi，封存授权执行器及CPU/native helper依赖。临时数据只保留，不递归删除。
6. runtime在准备原生启动时保留history，启动失败后也能定位本次nonce记录，不能把丢失身份当作从未启动。原生证明归档异常独立捕获，预算和主终态收据继续执行；未知或多代次均保留预算。
7. 计数默认unknown；非零、账本失败、settle失败或保留预算失败都不能返回成功。保留预算后也核对账本active=2；不得把失败的保留当成功。原始异常通过结构化收据及外层执行器保留。
8. 外部服务即使inventory为空也明确blocked。本轮自己管理的服务即使无已加载模型，点击清理仍关闭原始句柄并完整核对；只有此前已证原退出且当前端口absent的重复点击才可noop。这避免用另一个空监听者的清单证明原服务已空。

独审02第9–13项已在其指定范围确认关闭；不因新纠偏改写旧结论。v1/v2 harness保留历史源码但CLI退役，当前只使用v3。前端源码/编译产物与已验收字节一致，复用其12项测试与build证据；新后端/验证器执行定向和完整相关子树回归，并用新有限子授权重新跑页面夹具与真实零模型维护观察。真实已装载模型释放、重新启动与图片识别仍单独BLOCKED，零模型维护不替代。
