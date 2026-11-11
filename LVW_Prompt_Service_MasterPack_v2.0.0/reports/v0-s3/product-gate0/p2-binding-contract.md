# S3-P2B 实际Windows/WSL绑定与生命周期（Codex冻结）

P1离线接线已独审F0/M0/m0；本P2B只验证实际已安装Windows/WSL工具身份与CPU合成跨OS通道，不是完整S3产品Gate0、模型/Comfy运行或质量验收。仍属COMPLETE03既有本机代码验证授权。正式10+6/预标/旧成功素材run、旧S2 7/8均不变。真实runtime协调器/断外联/原workflow实际执行仍待后续准确合同，不在本任务抢做。

## 有限一次实机batch

按runtime-binding-child-01.json，在代码候选提交且preflight封存候选/工具/child/hash/输出根之后执行一次。首先只做固定路径/版本/包metadata读取：已知C:/ComfyUI-aki-v2/ComfyUI/main.py、nodes.py（如注册EmptyImage等，原图只选实际源码有的class，不猜class_type）、python/python.exe、C:/Windows/System32/wsl.exe、已封存Ollama exe、WSL /usr/bin/python3、ffmpeg/ffprobe、Node；不扫模型目录或全site-packages，不load模型/torch/CUDA，不跑nvidia-smi/GPU探测，不查询/启动服务，不接网络。候选路径最多24文件/256MiB hash，缺项如实报告，不自动搜索整盘/下载。固定Ubuntu-24.04发行版，有限命令返回版本/路径/package importlib.metadata即可，Pillow/numpy/av只metadata，不import Torch或初始化GPU。保留是否存在/实际realpath/hash/版本的区别。

实际transport必须经Windows Python加载候选program_budget生产客户端，调用固定wsl.exe→既有WSL Python→候选authority shim，验证真实大小写/中文空格/UNC client_binding与Linux child路径映射，不用mock Windows os.name或替换_exchange/runner冒充实机。全部扣额仅属于带marker的TemporaryDirectory合成authority/approval/SQLite，不使用真实母账本；fixture调用记录为synthetic debit，不计或冒充真实model action，也无模型HTTP。P1 model_action政策和生产原库samefile约束不改。

当前local-fixture模式限定Linux，允许最小增加精确wsl-fixture transport，仅在Windows客户端、WSL tempfile根的marker合成authority、ledger在该fixture根内通过；其固定命令与hash/echo/期限和P1规则完全相同。真实S3配置禁止该fixture模式；production wsl原库身份约束不能因加测试分支放宽。保留已有local-fixture/生产wsl/local-wsl分支，不能加入任意argv/通用shell或新HTTP服务。新增内部mode完整schema/规则记收据，不能把fixture成功称真实原库已扣额。

生命周期用真实owned短命shim与超时/异常场景验证：成功准确回执且fixture calls先增加；错配置/缺child/坏回执0send；Windows wrapper超时后分别观察其PID/birth及WSL shim PID/birth/pipe/thread是否确实退出，不能只看wsl.exe已reap就宣布远端退出。可为shim添加由已校验binding根+request UUID派生的受限owner记录，记录LinuxPID/start_ticks及请求身份；不得接受任意journal path或任意kill PID。真实故障可用合成SQLite有界锁或测试专用helper，不能修改production预算policy、fake实际returncode或把测试helper当真实已扣额的生产shim。

如果wrapper终止并未终止remote：不发模型请求、不退款、不settle0；将fixture reservation保留并保存实际远端身份。仅可在PID/birth/request/fixture root精确重核后清理这一次owned进程；不得pkill/wsl --shutdown或终止发行版/未知进程。需要实现有限request所有权清理协议时先给出证据和最小方案由root定夺，不在未知情况下扩大进程控制能力；本batch可如实BLOCKED此前置而保留新证据，不盲重试同一路线。只有预检未进入实机batch的失败可以修正后重新preflight；一旦开始batch，终态即消费，不能换run路径补第二轮或使用旧child。

输出installed-bindings.json与cross-os-lifecycle.json，列实际工具/封存candidate/child/harness/hash、固定命令、OS/remote身份/真实退出/error/扣额与0模型send、成功及失败清理、未证明项。跨OSfixture及native元数据总进程<=64，单命令<=30s，wall<=1200s，输出<=16MiB；stdout/stderr有界且不含媒体/凭据。不要将版本metadata当完整依赖锁；不宣称网络全隔离或实际Comfy可运行。

## 实现/验证范围

新增tools/v0_s3_runtime_binding.py与tools/test_v0_s3_runtime_binding.py。可最小修改bridge/program_budget.py、tools/v0_s3_budget_authority.py及其两份P1测试文件，以支持严格wsl-fixture与上述受限own-request身份记录；不能改core/transport业务、local_program_authority、其它runtime/预算政策、旧packet/manifest/质量集。新证据仅reports/v0-s3/product-gate0/implementation-p2-binding/。媒体/模型/真实ledger/配置不碰。

先合成测试child绑定、路径映射、预算exact/one-over、生产fixture拒绝、错身份/重复终态、owned清理；已有P1两组关键回归不可降标准。提交实现候选后，实际batch只一次，工具与child/hash绑定。运行产物根用现有runtime/receipts忽略目录，合成SQLite和脚本副本用owned tmp删除或明确failed retained；不提交二进制包/数据库/源码副本。所有JSON合法、raw失败保留、绝对路径脱敏。若实机成功也只READY_FOR_REVIEW，由另一窗口独审文本/合成负例，不重复实机child。最多两次同路线无进展交接；Git作者ljx418 <1173696783@qq.com>。
