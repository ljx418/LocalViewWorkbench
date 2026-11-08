# 独立审查一次集中纠偏

独审e420eb5发现3个Major：无效JSON envelope丢失raw；WSL->Win32环境未传递；420秒分析/30秒释放预算未包围全部等待。原报告及复现日志保留。

修复：所有invalid envelope保留原文并允许失败ModelRun查询；原生Windows PowerShell持有本轮Ollama原Process.Handle，显式设置loopback/no-cloud，nonce停止文件只请求该原句柄退出，保留PID/birth/监听归属与终态JSON，无ExecutionPolicy绕过、无EncodedCommand、无全局杀进程；WSLENV /w也明确转发保护参数，仅作用于子进程；420秒单调绝对预算覆盖acquire/prepare/infer，取消获取时关闭其等待；CPU解码线程由事件中断并等待清理；30秒清理预算覆盖解码收尾与模型释放，释放函数另有总超时与await后deadline复查，不证明则unknown且禁止发布有效建议。

增加无效JSON保留、获取阶段总时限、释放过期后不继续采样的回归。未经批准改变公共合同=none。真实验收仍未执行。微软官方WSLENV方向说明：https://learn.microsoft.com/en-us/windows/wsl/filesystems （/w为WSL启动Win32时传递，未改永久环境）。
