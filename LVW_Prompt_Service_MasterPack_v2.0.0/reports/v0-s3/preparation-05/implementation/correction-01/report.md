# S3-PREP-C correction-01 — READY_FOR_REVIEW

代码候选 `eef2fe8fc4afc8fc737643185fcd2789f1103195`，基准 `bee7b345eafb2327b77520664949169d31e055c3`；开工工作树干净，fast-forward 合并无冲突。仅修改两个允许工具，证据全部追加本目录。

实现者自检：71/71通过（原45项文件完整字节前缀未变），3项原反例的纯合成适配复验退出0且均观察到预期拒绝；真实owned CPU及decoder超时已停止/reap。首次43通过/2失败及修复说明保留commands.json，不隐去历史失败。

|缺陷|修复与可复算依据|
|---|---|
|MAJ-01|大小/内容/消失/读取身份漂移全局SOURCE_CHANGED；第二源resolve/stat/hash/decode均禁止进入；报告不再重新resolve源。|
|MAJ-02|统一单调deadline进入probe、每帧、Pillow子进程、sheet、index、终态；timeout取cap与remaining较小值；实际owned超时退出-15并reap，精确边界与one-over分别验证。|
|MAJ-03|临时与保留累计、部分写入入账、黏性失败；Pillow单新文件受RLIMIT_FSIZE约束，decoder用有界pipe接收后受控写入；清理不消除失败。|
|L01|started_at独立UTC墙钟；wall单调差值。|

raw/pytest-final.stdout.log 为集中71项；raw/counterexamples.stdout.json 为原三项反例合成适配与清理；raw/owned-proof.stdout.log 为真实超时PID/exit/reap；raw/cleanup.json 为本轮临时根实测删除；raw/oracle-preservation.json 证明旧45项未降断言。commands.json列精确命令及退出码。

预算口径：output_bytes_retained为预览与index，output_bytes_staging累计临时帧，output_bytes_cumulative为二者之和；operational_metadata_bytes单独列日志与运行receipt，二进制帧不写入日志。超限失败不因清理恢复。CPU子进程清理最多terminate/join 1秒+kill/join 1秒；staging cleanup独立最多4秒，均保存实测退出。decoder沿用原owned runner的有限收尾，未修改借用runner。

限制：Linux/WSL fork+RLIMIT_FSIZE实现，没有原生Windows移植证明；未进行完整OS/syscall/网络审计，保留独审L02–L07范围限制。旧真实源和旧preview访问0，模型/GPU/网络/服务/下载/真实checkpoint均0；旧child未续期/重跑。正式10+6不变；原成功run仍绑定e1798f33和335a8b97原身份，绝不重绑本候选。独审及产品Gate0仍待；没有Stage PASS或人签。

|阶段|已完成/总数|
|---|---|
|V0 / V0-S0 基线探索|1/2|
|V0-Min / V0-S1 图片与独立人工|5/5|
|V1前置 / R0 独立服务复核|1/2|
|V1早期切片 / R1a 单图React/FastAPI|5/5|
|V0.1 / V0-S2 视频与资源控制|7/8|
|V0.2 / V0-S3 离线质量与增量包|0/6|
|V1 / R1 人工业务骨架|0/4|
|V1 / V1-M1 多镜头拆分与逐镜头人物场景动作|0/3|
|V1 / R2 任务与正式运行包|0/4|
|V2 / R3 镜头资产与检索|0/4|
|V2 / R4 MCP与恢复|0/4|
|V3 / R5a 证据与建议合同|0/4|
|V3 / R5b 受控生成交接|0/4|
|V3 / R5c 集成与完整交付|0/4|

当前坐标：R1 / WP-R1-U3 / S3_PREP_C_CONSOLIDATED_CONTROL_FLOW_CORRECTION；本批只完成工具纠偏。统一切片3/3已按原范围人签，旧S2仍7/8，完整R1/M1/R2与后续V2/V3未因本批增加完成项。十字段交接与实现/机器/独审/人签分层状态见receipt.json。
