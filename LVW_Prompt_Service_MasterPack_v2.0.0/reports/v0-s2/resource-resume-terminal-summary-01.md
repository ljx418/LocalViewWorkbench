# RESOURCE-RESUME-01终态与未认领完整槽

最终候选e064961b16ff7a8c8a5901449f9dac5a5db8f600，通过offline-checkpoint-27的470项测试、五项检查和前后源码封存。新增恢复路由的25项定向测试也通过；docs/25优化未实施。

批准的一次resource-admission-oracle-resume-01探测终态NO_GO。首组Windows GPU4520MiB、WSL4308MiB，均大于冻结4096MiB；差值212MiB亦大于128MiB一致性容差，执行器先报RESOURCE_NOT_READY: native/WSL GPU disagreement。可用RAM8913MiB，目标端口/进程均0。不能仅忽略一致性检查，因为两个读数都不满足启动门限。

实际2个原生命令上界（PowerShell及其NVIDIA）和1个WSL查询均exit0，执行约2.91秒；model_calls/service_starts/media_reads/browser_starts均0。已复核原始terminal hash、child EXPIRED_NO_GO、lease.closed=1，以及完整槽目录和完整child文件都不存在。新grant已自动EXPIRED_NO_GO；旧失败和旧scope字节保持，未启动或终止任何外来任务。

没有足够证据判断外部占用来源，也不把两次不同时刻读数的变化归因于特定程序。没有授权额外GPU/外来进程查询，所以不继续诊断或重试。完整full-oracle-correction-01仍未认领，无新增完整运行次数。

待项目负责人将GPU稳定释放到现行门限，再处理authorization-s2-resource-resume-02.request.json：只请求1次新有限准入和恢复原未使用完整槽，完整增量0、额外完整复验0。若希望改变启动上限或采样一致性方法，需要另外批准具体合同差异；本次不实施该变化。
