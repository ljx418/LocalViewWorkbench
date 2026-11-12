# S3 父进程监督设计 01

root 架构设计；承接 p3b-correction-02.adjudication.json 的 NM02。不是已实现能力、执行授权或 Gate0，不改600s历史等待/10800s质量阶段/21600s单child硬上限。

## 复用与缺口

- v0_s2_http.LoopbackClient 的 socket/请求绝对截止、pending 请求跟踪保留；同步 observer 可能阻塞，不能推导完整父阶段硬截止。
- v0_s2_browser_supervisor.Supervisor 的有界协议/非阻塞管道/失败留痕可作为模式参考；observe、日志fsync和回调线程排空仍可能阻塞，不能直接套一层线程声称强制终止。
- local_program_authority 负责既有原始账本预约/真实动作计数/settle 或 close_retaining_reservation；它不是进程守护器，不把预算到期等同工作已退出。
- StageSequence.close 与 NativeRuntime.cleanup 继续负责实际服务、sampler、HTTP及归档证据；不因终止Python worker就假定Windows Comfy/Ollama退出。源与目标仍按既有P3A原始所有权校验。

## 唯一新增组合职责

薄 S3 协调器作为外部父进程，质量phase及其可能阻塞的观察/持久化放在本轮可终止worker进程中。父监督循环不执行worker传来的Python回调，不经过同一可能卡死的observer；只接收有界、身份绑定的进度与原始终态。不能仅靠worker自报PID/出生时间授予终止权。

执行前，父方持有原始worker进程句柄及本轮服务启动/出生身份凭据，绑定run/candidate/child/工具/端口，完整服务清理路径独立于被监督worker。若身份与外部清理不能建立，不准进入真实发送。进度协议单源有序、消息大小/数量有上限，开始历史等待时一次性固定600s截止，父方不接受重发延时；全phase截止固定10800s，且受child剩余期限更早值约束。原生请求的内部截止继续保留。

超过截止、协议失联或进程异常：撤销新动作许可；请求本轮协作取消；在冻结宽限后只终止已绑定worker；用父方独立核验本轮Windows服务/后代出生身份并清理。尚在运行、未决网络worker、回调、目录身份或GPU释放不明均记UNPROVEN、保留预约及原根，禁止归档删除或继续下一phase。执行停止与后续有限清理时间分别计量，均受同一child最终截止；不延长或叠加授权。动态网络规则必须与该清理顺序组合，不能假设监督进程退出自动安全。

父方持久化完整16行计划及开始状态，不依赖worker在卡死后补写终态。失联项明确失败/未知，未开始项BLOCKED，计数不缩水。已有raw文件只登记实际可读取身份与hash，不伪造丢失输出或拼接别轮。父方故障恢复只做清理/恢复证据，不自动重放推理。父监督崩溃场景仍需真实所有权和看护机制证明；此设计不保证尚未实现的崩溃顺序。

## 最小验证与封包条件

下一集成实现包内完成：正常退出、受控阻塞回调/写入、600s与10800s缩尺等价截止、进度伪造/重放、清理失败/未决HTTP、父故障恢复；每条验证deadline实际停止而非函数返回后才报超时。先用有限新Python fixture进程验证组合，任何新增进程测试须在新执行包明确白名单/数量/时长/清理，而不是沿用P3B零进程守卫偷偷执行。Native Windows服务和GPU清理另在同源有限子运行验证，不以fixture替代。

这是当前S3协调器的一项组合义务，不新建通用Worker平台。新真实执行包还须补齐A06进程隔离/尝试观测、安装前后同源基线、真实父capacity提供者、视频残留适配及最终A/B预算。以上未闭合仍阻止产品Gate0；当前P3B纠偏只修改其自身局部校验，不实现或宣称本设计。

## 只读来源身份

- `tools/v0_s2_http.py` SHA256 `3c02c3d69d5141883ee62e4543c6ff61c7d5f5e5c0c894083e556e3499e1e9b9`
- `tools/v0_s2_browser_supervisor.py` SHA256 `54203f5cc355d9ad2083debc4d1af99b56cfab303fb6ec96cd66b59e7ee2074d`
- `tools/local_program_authority.py` SHA256 `677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787`
- `tools/v0_s2_stage_sequence.py` SHA256 `0b6be81e1cf9d0db88e7f5fe581f23686418d3a15634bd53f88ccb56f8718e20`
- `tools/v0_s2_runtime.py` SHA256 `3d38dfd37faaa5434c24818ca366208318678a51b7a0b3339aa0b5ac10aaf2c8`
