# S3-PREP-B — 增量包工具冻结实施约束 v1

负责人：Codex架构/门禁；Orca可见ClaudeCode实现；另一个窗口独审。此文件是后续离线准备Workpack，不改写或续期preparation-03的媒体child，不授予产品Gate0、Stage PASS或旧V0发布。旧S2保持7/8；允许S3 toward V1衔接批准不变。

目标：交付可真实构建、校验、隔离安装和回滚的V0增量包工具，复用现有RuntimePatch代码。依据docs/13和docs/19。仅新增工具和准备输出；禁止业务代码重构、真实宿主安装、启动服务、模型/GPU、媒体读取、网络和下载。0产品完整验收槽位。本任务可在自有TemporaryDirectory或本报告目录下操作文件；不能写C:/ComfyUI-aki-v2或用户现有应用配置。

## 公共工具合同

唯一生产owner：tools/v0_incremental_package.py；测试tools/test_v0_incremental_package.py。stdlib优先，不引入依赖。CLI提供build、diagnose、install、rollback，均输出结构化JSON到stdout，诊断到stderr，nonzero为失败；稳定错误码至少BAD_INPUT、INTEGRITY_MISMATCH、PATH_REJECTED、SIZE_LIMIT、CONFLICT、INSTALL_FAILED、ROLLBACK_CONFLICT。不可把异常吞掉为成功。提供--help，具体argparse参数和JSON schema由实现收据完整记录，以上子命令与语义冻结。

build从显式Git候选commit读取字节（不打包脏工作树）并绑定完整commit SHA；git失败或对象身份不匹配即拒绝。源payload精确允许LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/下已跟踪.py与web/*.js、LVW_V0_RuntimePatch/workflows/下已跟踪.json。审计是否存在这些生产模块所需的其它静态文件，若有缺口先报告，不擅自扩大。排除tests、fixtures、__pycache__、pyc、原日志、机器绑定/绝对路径、真实配置、模型、媒体、用户稿、reports及凭据。包内另外携带生成的manifest和工具自身的版本化副本/中文使用说明，能在已装Python环境直接执行，不要求clone/pip/npm。构建manifest列schema_version、source_commit、package_format_version、每项相对安装路径/长度/SHA256、依赖前提和非目标；manifest哈希记在外部机器收据，不能自引用。模型/宿主/PyTorch不复制，明确本机已验证宿主复用，不能声称任意机器可用。ZIP成员名固定使用POSIX相对路径。

体积硬上限20*1024*1024字节（压缩包与展开payload分别检查；限制是保守执行预算，不扩大现有目标）。固定顺序/时间戳/权限使相同候选重复构建payload内容可复算；产生临时包完成自校验后原子发布，不覆盖已存在输出。构建前检查git与输入，记录真实文件hash和包hash；源码无修改。工具自身候选身份必须清楚说明，不能声称dirty脚本来自commit。可先提交工具再从该commit构建。

diagnose在写安装目标之前验证完整archive/manifest、长度/hash、条目集合及上限；拒绝路径穿越、绝对路径、盘符、反斜杠绕过、重复成员/大小写冲突（Windows语义）、symlink/reparse逃逸和zip bomb。不能extractall。检查target写权限/隔离标记但不调用外部服务；依赖只做本任务可离线证明的项目，不伪称GPU/Ollama/Comfy已验证。校验失败不能写target（包括不留下空安装目录）。

install只允许显式提供的sandbox parent内且带本工具沙箱marker的target；本轮生产host路径硬拒绝。安装是同根隔离Comfy目录布局：custom_nodes/lvw_v0_bridge + workflows/lvw/。记录目标preimage、manifest、session ID及所有owned写入；不修改其它节点、模型、输入输出和用户文件。已有非owned冲突默认拒绝且0写入；无需在本任务实现覆盖现有安装升级。全量校验再stage/原子rename提交，失败回退已提交owned项；保留原始失败和测量清理。不把沙箱安装当真宿主验收。

rollback按安装receipt绑定session及installed hashes逐项检查，无用户改写才移除本轮owned文件/目录；有改写则ROLLBACK_CONFLICT、保留用户字节和记录，不递归删除非owned文件。不修改外部原文件。全量预检再变更，成功证明原有哨兵字节未变且owned staging清理，失败保留诊断。支持在含中文和空格路径执行。工具不能包含任意shell执行接口。

## 有序Workpack与验收

1. 只读审计现有构建/安装能力（Git跟踪文件，不扫描本机），能复用就复用；差异记receipt。
2. 一人连续实现build/diagnose与install/rollback，合同不变时不逐项交接。
3. 定向测试驱动公共CLI/owner：真实固定commit构建→hash集合校验→中文空格隔离target安装→诊断→回滚→原有哨兵不变。证明被篡改包、路径穿越、重复/大小写路径、symlink、exact/one-over大小边界、已有冲突、安装中途故障、用户修改后回滚拒绝及清理。合成故障注入不能取代真正常链。不要做镜像实现细节的机械测试。
4. 提交工具候选后用同候选真实仓库payload做一次离线构建/沙箱安装/回滚；不是服务/模型/媒体验收。保留原始命令、stdout/stderr、exit、候选SHA、工具SHA、固定集合fingerprint、包hash/大小、安装前后哨兵hash和真实cleanup，raw失败不可删除。任何真实产品runtime调用预算0。
5. READY_FOR_REVIEW后停止；Codex汇总另派独审，实施者不宣布Stage PASS。最多两次同根因无进展须交接。

允许写入仅tools/v0_incremental_package.py、tools/test_v0_incremental_package.py、reports/v0-s3/preparation-04/implementation/。本任务文件/其它root文件只读；不能改旧packet、MANIFEST.sha256、plans、contracts、业务RuntimePatch、历史证据。包或临时副本不加入Git；使用自有临时目录并实测清理。可提交机器收据和文本manifest/说明，脱敏绝对路径。Git作者ljx418 <1173696783@qq.com>。任务结束报告full SHA、变更清单、公共CLI合同、测试与退出码、一次真实离线包链路结果、风险/限制和证据路径，并worker_done。基准以调度时给定root commit为准。
