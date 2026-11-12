# S3 协调器接线清单 01

架构设计记录，非新 Stage Packet、非运行授权、非验收结论。当前 P3B 独审处理中；本清单不修改其候选或冻结合同。接线实现由后续可见 ClaudeCode 工作包承担，不启动额外并行实现。

| 复用 owner | 已核实调用点 | 必须补齐的接线与 Oracle |
|---|---|---|
| InstalledPackageRuntimeFactory | tools/v0_s3_stage_runtime.py；继承 StageRuntimeFactory._prepare | 复用受保护安装、目录/归档生命周期，不能退回复制源码的旧工厂；原 S2 默认行为保持 |
| NativeRuntime.write_native_binding / write_warm_binding | tools/v0_s2_runtime.py，均已有可选 s3_budget_binding | 父工厂 _prepare 现未传入此参数，默认生成 LOCAL01/S2 身份。新 S3 专用接线必须在首次模型动作前传递已接受 P1 的 COMPLETE03 有限绑定，不得先写旧 profile 再覆盖文件。默认/暖阶段都须生产路径负例证明缺绑定零发送 |
| StageSequence | tools/v0_s2_stage_sequence.py | 只复用各 phase/上下文校验/清理与归档 owner；旧 sequence 固定九项、45+20 submissions，不能直接当 S3 十二项总账。新总账按原 A01–A12 保留全部项，Quality 16 行与格式补项各自保留身份 |
| QualityPhase（候选 cea5bf3，独审未决） | tools/v0_s3_quality_phase.py | 不把 FakeNative 边界测试称生产组合通过。真实 NativeRuntime 尚无 video_snapshot_residue；需单一受管 run root 下的有界只读 accessor，未知/越界/读取失败不得返回假空列表，不能清理后再伪称从无残留 |
| NativeRuntime.release_preload / cleanup | tools/v0_s2_runtime.py | 使用真实 release API 与既有 sampler/PID birth、监听归属、pending HTTP 终态；原实例仅 cleanup 返回 exit0 不构成全链清理证明。归档前绑定所有注册 worker 和未决回调 |
| 原生模型扣账 | tools/v0_s3_budget_authority.py + bridge/program_budget.py | 使用原始 COMPLETE03 账本位置、已验固定 WSL shim 与实际 native send。禁止工作区默认账本、消费前先发送、未知 ACK 自动重试/退款 |

## 同候选父批次与预算

沿用 remaining-integration-budget-02：A 原生矩阵 cap103；B 已知40模型动作仍非最终 cap。B 包含固定16质量行34调用、冷图/片至少5调用和独立 WebP 格式1调用；格式样本不替代质量样本。所有故障、加载、控制、清理成本在冻结执行包时逐项补齐。两 child 顺序执行，各 full=True 如实计两完整槽，候选/源码/依赖/父批次一致，不能用跨候选成功补行。当前未预约或触碰真实账本。

## 必须在产品 Gate0 前解决的运行约束

A06 仍缺可执行网络隔离后端：实机只确认当前 token 非管理员，不足以假设 WFP/防火墙可配置。必须限制本轮进程、保留 loopback、阻断非 loopback 并观测尝试；代理变量/空连接列表/模型 no-cloud 标记都不替代此义务。机制未验证前不能签 Gate0，也不先发起提升或修改系统配置。

安装前/回滚后的同一目标基线必须由实际注册 Schema 驱动原图 CPU 工作流并检查新鲜输出。LoadImage/SaveImage 目前仅源码静态候选，不写虚构 class_type/schema；该基线须与真实安装/回滚目标生命周期绑定。两个 child 间保留受控且不可拼接的父批次证据，不能复用旧 S2 成功。

## 交付边界

下一实现包应把上述接线、十二项汇总和有界中断清理作为一批交付，定向/组合测试后集中审查；不把每个 getter 拆成新产品阶段。不重复已经接受的 P1/P2B/P3A 全套测试，除非接线实际修改其行为或发现新回归。A06 技术方案、最终预算与真实节点 Schema 尚未闭合，本清单不宣称实现包已经可以冻结。

## 本次只读来源绑定

- `tools/v0_s3_stage_runtime.py` SHA256 `c4815fdc2140961171af938ba5396763260314de2e938a1087ab6b21038b1aad`
- `tools/v0_s2_stage_runtime.py` SHA256 `a051ff3da90a62292b541d93a835dfec8f90cf1b80d114ee6d9d51be9685388c`
- `tools/v0_s2_stage_sequence.py` SHA256 `0b6be81e1cf9d0db88e7f5fe581f23686418d3a15634bd53f88ccb56f8718e20`
- `tools/v0_s2_runtime.py` SHA256 `3d38dfd37faaa5434c24818ca366208318678a51b7a0b3339aa0b5ac10aaf2c8`
- `tools/v0_s3_budget_authority.py` SHA256 `80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7`
