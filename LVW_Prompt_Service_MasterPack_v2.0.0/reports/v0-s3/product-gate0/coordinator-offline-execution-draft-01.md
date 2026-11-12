# S3 集成离线执行包草案 01

Root 架构/验收准备，未激活、未派发、不是运行授权或 Gate0。前置是 P3B 最终候选独审阻断项关闭后由 root 冻结该候选与本包；当前 correction03 仍在 ClaudeCode 实现。与 coordinator-integration-map-01.md、parent-supervision-design-01.md 配合使用，不复制产品合同或旧测试。

## 一个集成 Workpack，三个实现段，一次集中复核

| 实现段 | 实际 owner 与允许变更建议 | 明确交付与负例 |
|---|---|---|
| A：有限绑定接线 | 新 S3 coordinator/sequence；v0_s3_stage_runtime.py；v0_s2_stage_runtime.py 只增加默认不改变 S2 的可选参数钩子及其调用 | 现 _prepare 在214/216行首次写 warm/native profile，必须在这次排他写入时传入 s3_budget_binding；禁止写旧 LOCAL01 后再覆盖。两分支缺失/错 run、candidate、child、原始 authority/ledger 身份零发送；默认 S2 行为回归保持。复用 P1/P2B 既有实现，不改 program_budget/local_program_authority。 |
| B：父监督与终态 | 新薄 S3 supervisor 及定向测试；实际 QualityPhase 通过受控 worker 组合，不再复制质量实现 | 外层掌握原始 worker 句柄，内部不执行任意父回调；完整16行先封存。正常、阻塞 callback/写入、历史600/phase10800固定截止的缩尺验证、乱序/重放/超长消息、失联、未决I/O、清理失败、恢复不重发。硬截止时真实 fixture 进程必须停止，不能只检查返回的 timeout 字符串。 |
| C：资源残留和汇总 | v0_s2_runtime.NativeRuntime 增加单一受管目录下的只读 video_snapshot_residue；新 S3 汇总组合原 phase | 源 owner video_files.stage_video 实际使用 temp 下 lvw-video-* 目录。accessor 有界枚举、绑定原始根及身份，不跟随符号链接/reparse；不存在的根、I/O错误或越界均 unknown，不能返回[]。空、真残留、目录替换、枚举超限、读取失败的公共组合负例。清理后观察与从未残留明确区分。 |

基线代码定位：StageRuntimeFactory._prepare 在启动/注册验证之后、首次模型请求之前写有限 profile；继承的 InstalledPackageRuntimeFactory 继续作为真实安装工厂，禁止回退源码复制。原 sequence 的九项45+20发送不是 S3十二项总账。该草案不授权覆盖已经接受的安装/归档、扣账或所有权实现。

## 离线进程白名单：冻结前需要填入实际文件哈希

此处是后续包的预算设计，不是本轮 correction03 的执行范围。P3B 当前零 subprocess/network 守卫继续有效。

- 只允许冻结哈希的本机 Linux Python executable，argv 固定 -I -S -B 加新受控 fixture 脚本及枚举场景参数；无 shell、WSL、PowerShell、Windows exe、FFmpeg、浏览器、HTTP、GPU、服务或媒体访问。
- 所有进程由可信父创建并持有原始句柄；每次最多2个、整包最多24次启动、单次最多10秒、全包测试墙钟最多180秒，最后30秒只清理。超限停止，不自动加预算。
- 一次受控正常 fixture、callback 阻塞、持久化阻塞、历史截止、phase截止、协议错序/超长、worker异常、父故障恢复等场景使用相同监督生产入口。缩尺只改变注入 clock/deadline 参数，生产默认600/10800不改；禁止用 sleep 后再返回的伪造结果替代杀停证明。
- 探测只针对本轮 PID/出生身份及子进程句柄；不得终止未知进程。unknown/失联保留根和预约，不归档删除，不自动重试模型。
- 标准输出/错误每进程最多256KiB，单条协议消息<=32KiB，累计<=1024条；新证据目录<=8MiB。源/工具/fixture/环境与实际候选绑定；原始退出码和失败保留。
- 最终派发前须确认现有父授权覆盖离线测试、绑定真实工具与 fixture hash，并产出有限子执行收据。不得直接拿本草案启动进程；无需凭此向人类重复索要同范围许可。

## 集中验证与证据边界

编辑期只跑定向测试；交付候选一次相关新增/改动子树组合测试，审查者再独立复算关键失败路径。已有 P1/P2B/P3A/P3B 整套不机械重复，只有实际行为变更才列必要回归。A/B/C按依赖在同一个可见Claude窗口连续完成，不为每个 getter 新开产品Stage或单独完整checkpoint。

CPU fixture 只证明 supervisor 组合。真实 native 服务/后代身份、GPU释放、pending HTTP、原始账本容量提供者、A06隔离与尝试观测、安装前/回滚后实际节点基线、最终 A/B 模型预算仍需另行同源有限运行证明；不能以此草案或 fixture PASS 签产品 Gate0。A06 当前原token权限不足的问题仍未解决，不在本包中暗加提权/动态规则权限。

## 冻结前检查

1. P3B 最新候选及独审已裁决，引用其真实完整 source hash；不再写旧 cea5bf3 为当前候选。
2. A/B/C文件允许清单、实际 owner、测试命令、fixture argv/工具hash和上述有限预算落入正式 task/child；明确继承S2默认行为与回滚。
3. 协议与清理必须使用原始父 custody；不让worker自报PID授予终止权；父故障恢复与A06动态规则顺序仍未证明时保持运行阻断。
4. 独审隔离、FIRST Claude429立即WAIT_BUDGET、真实收据、固定分母与人工签署边界全部保留。
