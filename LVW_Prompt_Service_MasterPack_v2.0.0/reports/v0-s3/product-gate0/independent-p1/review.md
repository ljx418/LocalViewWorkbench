# S3-P1 独立审查：离线生产扣额接线可接受

结论：**OFFLINE_P1_VERIFIED_ONLY；Fatal 0 / Major 0 / Minor 0**。本实例未实现或修改候选；只新增本目录。不能据此签完整产品 Gate0、Stage、质量、人工体验或发布。实际 Windows/WSL 绑定与生命周期仍是 P2 前置，未在本轮验证。

候选 `c3c6bcb6a96576d9ed542acb4eb25c55d6b204d0`；证据 tip `edb81e91292220225a23cef56fcdbcd73a33d082`；root 基准 `28cf4211674fb89d2661474109e6f2d8ef42a0a1`。起始 `git status --porcelain` 无输出，随后指定 merge 从 84264c7 快进至证据 tip，exit 0，无冲突。先读 AGENTS、治理 README、execution-control、执行索引、完整 production-integration packet、P1 合同及 ledger-compatibility；报告不修改这些权威。

## 集中证据与结论

| 核查 | 实际证据与判断 |
|---|---|
| 候选/白名单/封存 | `fingerprints.json`：基准至候选仅九个白名单文件；逐个 SHA256、Git blob、当前字节与 candidate/tip 一致。packet 十项与 spec 五项全部复算相符；预算 authority、MANIFEST、execution-control、quality16 与 root 基准相同。tip 额外仅实现收据目录。 |
| 默认图、四帧、preload | 独立运行 packet 测试，真实 `BridgeOwner.analyze_image/analyze_video` 分别通过默认和 interruptible transport，最终网络被替身拦截，拦截时真实 fixture SQLite 的 calls 已逐次为 1/2/3/4。`NativeRuntime.preload` 独立一扣且发送字节 hash 相符。不是 helper 常量计数，不存在 submit 统一扣一次或两入口双扣。 |
| 非模型动作 | 新接线仅默认 chat URL、interruptible chat body、runtime preload 三处；控制 GET、unload、人工编译路径不经过扣额。独立 probe 实际调用默认 cleanup：keep_alive=0 控制发送一次，SQLite delta=0。空图拒绝测试 delta=0；旧 owner/control 回归通过。人工编译与状态的零扣额结论为静态调用图及既有回归，不冒充真实产品 checkpoint。 |
| 同库/权限/事务 | shim 验证 authority_root 固定模块位置及 pinned authority 源码 hash，在该 root 导入，未重写 ROOT/LEDGER；生产分支要求 ledger 与历史 live15 指针 samefile 且已存在。fixture 分支只在带 marker 的临时 root 内使用合成库。实际调用原 `model_action` 事务；exact8/one-over、并发12抢8及独立6抢2均守上界。原库缺失不新建，源码/child/tool/execution/approval/candidate/root/expiry 漂移均拒绝。未访问任何真实库。 |
| profile 与旧护栏 | COMPLETE03/S3 新分支与精确 child/path/hash、candidate、model digest、run、PID/birth、binding hash 相等；期限落在 row/child 有限范围及21600s内。旧 LOCAL01/S2 7200s 语义保留；native max64、每视频最多4、warm20及10+10未变。缺绑定的活动 S3 profile、required env 和坏 hash 拒绝；无 S3 的普通 owner 回归通过，无新增授权 UI。 |
| stdio 与媒体隔离 | Windows 固定 wsl.exe/-d/--exec/Python/-I/-B/shim 角色，Linux 固定 Python/-I/-B/shim；Popen 默认 shell=False，无任意 argv 公共接口/新HTTP平台。binding/approval/candidate/源码/tool/expiry 验证，request_id/action/payload hash/model/run/child/authority 全量字典回显比较。stdin只发摘要与身份；日志不输出图像或 base64。 |
| 反假绿/未知结果 | packet 覆盖错nonce、坏JSON、实际exit7、超时、超限、丢回执、取消；补充七种回显篡改均0send且每次已扣1保留 active1。独立真实 shim 返回有效DEBITED且真实exit0后，注入真实 reader EOF异常，实际 `_exchange` 产出PIPE_ERROR/reaped/joined，默认生产chat拒绝，0send，扣额不退。最终网络失败仍1扣，无自动重试。合成未知清理 close_retaining_reservation 留active2/calls9/cap32，没有settle0。 |
| 清理与边界 | 真正子进程为 owned 合成 shim/短命失败探针；packet timeout检查 kill/wait、线程join与pipe关闭。所有实验/pytest basetemp在 TemporaryDirectory，`checks.json`/`probes.json`记录退出后目录不存在。未安装、下载、探测模型/GPU、访问源媒体/preview、网络、原ledger；0真实child、0产品完整checkpoint。 |

## 命令与原始结果

`run_checks.py` 只运行两组定向测试，各一次。完整 argv、owned basetemp、exit、耗时和清理见 `checks.json`；原始 stdout/stderr 分别在 `check-1.*`、`check-2.*`。

- 冻结 packet 四文件组合：**66 passed，exit 0**（7.86s）。
- 实际变更影响的旧 bridge/video transport/native evidence/warm benchmark/runtime 五文件组合：**77 passed，exit 0**（0.79s）。这是旧 owner 回归，不重跑全仓或 verify_pack。
- `python3 -B reports/v0-s3/product-gate0/independent-p1/probes.py`：**exit 0，13条事实记录**；其中12条行为/事务记录和1条临时根清理。`probes.stdout/stderr/exit`、`probes.json`保留逐项Oracle实测值。沿用候选 Fixture 只生成合成授权树，独立断言与故障注入由 reviewer 编写，不替换真实 authority/model_action/SQLite。

首次独立 probe 因 reviewer 错用 `BridgeError.subcode` 而退出1（实际属性为 `details['subcode']`），当时产品已正确拒绝第一条坏回显。保留 `probes-initial.*`，只修本目录探针后运行一次完成；未改候选、未重复 packet/旧 owner 回归。首轮 TemporaryDirectory 在异常退出时按上下文清理，首轮没有独立路径删除断言，故不把它算作额外清理证明。

## P2 必须保持的前置

本轮只证明 Linux 合成 root 下的离线生产扣额接线。真实 Windows/WSL 的 wsl.exe/Python/发行版/两套可读路径、authority root 与原累计库身份、installed source/model/PID birth seals，需在 P2 有限 binding 中实际发现并封存。Windows wrapper 超时后的 WSL shim/管道/线程回收与未知结果保留 reservation 仍须实际生命周期证据；当前本地 reap 不能替代跨 OS 证明。

root 接下来可冻结 P2 薄协调器与实际绑定验证：同原账本、精确候选、有限子预算；不按日志推算扣额，不对丢回执补发或退款；清理未知不得 settle0。包 factory、断外联尝试记录、原 workflow/质量 raw driver 与真实累计十二项均未由本轮签署。P1离线接受不把 S3六项分母更新为完成。

## 十字段交接与完整路线

1. 当前坐标：execution-control 的 R1/WP-R1-U3，gate=S3_P1_FROZEN_NATIVE_BUDGET_INTEGRATION；本次审查工作包 V0-S3/S3-P1。
2. 目标：独立核实生产发送前同权威扣额。
3. 完成：白名单/指纹、静态调用图、66+77定向检查、聚焦反例与清理。
4. 修改：仅 independent-p1 新证据与探针。
5. 合同/分母变化：无。
6. 验证：本报告表格、原始输出与机器收据。
7. 缺陷：本轮可复现 Fatal0/Major0/Minor0；无风格扩围项。
8. 风险/未跑：实际跨OS生命周期与完整产品验收，保留P2前置。
9. 授权/资源：全部离线合成，真实ledger/media/model/GPU/network/child/checkpoint均0。
10. 下一动作/责任：root审阅本提交并冻结P2，实施者不得据此签完整Gate0或Stage。

从唯一 execution-control 提取的完整状态保存在 `outline-snapshot.json`：V0-S0 1/2（历史NO_GO）、V0-S1 5/5、R0 1/2、R1a 5/5、V0-S2 7/8、**当前离线P1对应 V0-S3 0/6**；V1 R1 0/4、V1-M1 0/3、R2 0/4；V2 R3 0/4、R4 0/4；V3 R5a/R5b/R5c各0/4。V1-D0准备2/2及统一早期切片3/3的原机器/独审/有限人签保持；本报告不增加任何产品人工签署。

独立签署：Codex dispatched reviewer task_05738c5edb16，2026-11-12；Git作者 ljx418 <1173696783@qq.com>。签署范围仅本候选的S3-P1离线审查。
