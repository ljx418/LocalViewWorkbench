# 20｜可靠性、故障恢复与运维

## 状态机

job: queued→preparing→running→succeeded/partial/failed；取消经cancelling→cancelled；重启残留→interrupted；显式retry新attempt。resource: unknown/busy/releasing/released。job终止不等于resource released；新的GPU任务需二者条件满足。UI显示当前attempt和可重试原因，不无限轮询。

V0会话内run_id/draft_epoch；V1持久attempt+cancel_epoch；V2lease/fencing+batch；V3外部receipt/outbox。对相同Idempotency-Key不同payload拒绝；晚到attempt不允许写shot head/revision。

## 提交和副作用

纯分析可重试但保留旧run；不可变修订用唯一业务键防重复。工件先临时目录、完成哈希、原子rename、事务登记；失败清理只针对本attempt。外部Comfy响应未知不自动重试，先reconcile。不存在任意跨系统恰好一次保证。

## 取消

UI≤1s反馈；停止/卸载单独观测。V0 Comfy全局interrupt不能误伤其他工作流；V3确认所有权后才能用。HTTP断连不是GPU已停，查询/api/ps及显存。取消60s未停止标资源仍占用，人工操作不锁；记录诊断，不kill用户进程。

## 资源与重试

单GPU任务；超限输入在预处理前拒绝，CPU预处理流式。可恢复网络断连最多一次**显式或受控**重试，仅在确认无外部副作用时；OOM不自动提高ctx/无限换模型，推荐降低配置由用户确认。驱动异常/磁盘满错误可读，数据事务回滚。

## 观测

每请求request_id，业务job/attempt/asset/revision/external_id；日志默认元数据不含私密正文。指标load/preprocess/infer/compile/queue/release时长、GPU/AvailableRAM、错误码、取消终态；诊断包显式导出脱敏。记录stage_report与证据hash，不用日志“success”自证结果正确。

## 运维命令目标

`diagnose`只读；`backup`一致性snapshot；`restore --dry-run`先校验；`migrate --plan`展示版本；`rollback`切软件+匹配数据；`clean-temp`仅LVW临时根且不碰活动lease；`export-project`显式范围。这些是实施命令合同，不是本包已提供生产命令。
