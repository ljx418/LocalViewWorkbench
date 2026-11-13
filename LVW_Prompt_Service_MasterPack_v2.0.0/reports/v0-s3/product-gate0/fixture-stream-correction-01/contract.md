# S3-P4 流/fixture纠偏内部附约01

基准01453ee；继承原冻结合同，I01–I24不改，13场景不缩减，max_message32KiB、count1024、每stream256KiB、所有期限不放宽。不是产品公共API/schema变更。

1. 非有限数负例必须提供完整JSONL frame（末尾换行），解析器实际拒绝NaN。write_raw保留原始字节语义，阻塞持久化场景的故意不完整帧不能被修好。
2. 消息数负例应发恰好MAX_MESSAGES+1条合法闭合身份消息，含STARTED；空payload合法PROGRESS、固定短合成run_id允许在该负例中使用，必须由父context和子消息一致绑定、候选sourcepin封存。候选/授权hash长度仍40/64，不伪造或放松身份校验。生成前确定完整wire bytes<=原256KiB且每条<=32KiB，避免字节上限遮蔽消息数；不得换Oracle为phase timeout或提高任一上限。
3. 生产ParentSupervisor必须及时察觉stdout/stderr reader.overflow和reader.error，撤销后续动作，终止自己持有worker并保留稳定拒绝和证据，不等待10800s phase兜底。内部稳定码固定STDOUT_STREAM_LIMIT_EXCEEDED、STDERR_STREAM_LIMIT_EXCEEDED、STDOUT_STREAM_READ_FAILED、STDERR_STREAM_READ_FAILED。原正常、协议及deadline行为保持。发现资源/读错误不能因同一批已有TERMINAL而发布假成功。
4. 并发读与消费不丢已接收的有界字节/帧；短临界区不包含os.read或外部回调，不使父循环同步等待输入。总bytes、保留bytes、已解析消息与overflow标志语义明确，不把消费后的空缓冲称原流为空。
5. 本轮仅零进程代码/定向测试，可用受控os.pipe和线程或fake reader/handle驱动生产owner，不能启动fixture/网络/模型/服务/原counter。真实复验须候选独审后另行有限机器预算决策，旧180预留不返还。
