# V0-S2 Risk And Authorization Register

| ID | 风险/动作 | 初始状态 | 处置 |
|---|---|---|---|
| DEP-S2-01 | R1a 当前候选尚未完成 | WAIT_DEPENDENCY | 不激活 V0-S2，不并发写 owner |
| AUTH-S2-01 | 离线实现与测试 | PREPARED | 激活 packet 后授权 |
| AUTH-S2-02 | testSource/FFmpeg/Comfy/Ollama/GPU/headless | PROGRAM_SCOPED | 每次运行先生成候选绑定子授权收据 |
| R-S2-01 | 全片解码/OOM | Fatal | ffprobe 先验、CPU 有界采样、4 帧/768px/自有临时配额 |
| R-S2-02 | 路径或 reparse 越界 | Fatal | 允许根、realpath/handle 校验、fail-closed |
| R-S2-03 | 取消后晚到覆盖 | Fatal | run token + cancel epoch + terminal CAS |
| R-S2-04 | 清理误杀外部进程 | Fatal | 仅自有句柄；外部占用只报告 BUSY |
| R-S2-05 | 资源统计假绿 | Major | 固定 10+10 分母、逐次原始记录、P95 独立复算 |
| R-S2-06 | 用帧数组单测替代视频文件 | Major | 真实 MP4/MOV 公共入口与 frame manifest |

禁止下载、云/付费服务、非 loopback、私有媒体、Cookie、现有浏览器 profile、可见浏览器自动化、永久配置、远端推送和发布。
