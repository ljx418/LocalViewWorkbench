# S3 P3A：实际安装产物进入原生运行根（冻结内部实现合同 1.0）

起始代码：root本合同提交（worker先合入）。架构/门禁root；可见独立实现窗口只实现并自检，随后独立审查。范围为生产安装到运行的接线，不重建包工具，不改变产品合同或旧S2运行语义。

## 唯一允许实现面

- 新tools/v0_s3_stage_runtime.py：InstalledPackageRuntimeFactory继承现有StageRuntimeFactory，复用原_prepare、启动、公开registry校验、base-directory身份检查、profile、archive与cleanup路径。
- 新LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py。
- 如继承无法保证必要的调用顺序，可最小修改tools/v0_s2_stage_runtime.py（需在收据说明原因）；禁止改变其默认复制源码行为/旧调用接口。
- 新reports/v0-s3/product-gate0/implementation-p3a/文本证据。其余文件不得修改，包工具、预算authority、P2B、质量集、固定packet与坐标不改。

## 行为与权限边界

新工厂额外接受keyword-only package_path、package_sha256、manifest_sha256；其余参数沿用基类。这些不是外部产品API。S3工厂只覆盖安装部署，不接受任意执行callback或shell；禁止回退到基类复制桥接源码。

_deploy(root)由继承_prepare在本轮新建并archive.register的root上调用：root必须是directory内本轮登记的直接运行子目录，不是外部传入的现有用户目录。directory的包工具沙箱marker必须由调用方预先提供并验证，不静默创建/覆盖marker。实际调用现有command_install把冻结包安装进这个root，而不是旁路目录；sandbox_parent为directory，target为root，保存原安装收据及所有权记录。后续Comfy --base-directory必须仍指向同一个root。包工具既有owner/路径/回滚防护全部保留。

安装前拒绝symlink/越界/非法摘要/包或manifest摘要漂移/manifest.source_commit不等于candidate。manifest.items的bridge source_path集合和SHA必须精确等于source_identity.execution_artifact_sha256中桥接源码部分；额外、缺失或不同文件都拒绝，不能仅信ZIP自报SHA。全部workflow条目也须与候选execution_artifact_sha256同源匹配；若原封存未覆盖workflow，则明确拒绝并报告所缺文件，不能隐式降低封存。使用包工具的完整archive校验，不再实现ZIP提取器。包≤20MiB/archive+expanded原门限不变，读取需有界。

安装后按manifest实际重算所有落地payload路径/大小/SHA，bridge集合精确匹配并无symlink/路径逃逸；校验目标内所有权身份和安装收据一致。evidence记录部署模式INSTALLED_PACKAGE、candidate、package/manifest哈希、target及安装/核验结果；原生启动发生在全部验证完成之后。异常必须沿原_prepare失败/cleanup/archive路径保留真实失败；禁止自动重装、自动重试、跨目标rollback或根据外部收据任意删除。实际完整回滚验收仍由后续协调器负责，本模块不把临时目录删除当回滚证明。

不得假称该组件已支持完整S3预算/profile或离线阻断。旧工厂仍为旧S2语义；此接线必须可被后续薄协调器明确选择，不能默默激活S3实机运行。

## 验收及固定义务

定向pytest驱动真实安装owner和新工厂，不只测试常量/私有验证函数。在临时Git仓库从真实tracked fixture构建真实包，调用新工厂走继承_prepare；以假的native服务边界替代Windows，断言安装target、实际Comfy base-directory、安装收据、封存及落地字节指向同一root；将源码copy路径设为抛错，仍能到达假native启动；这仅证明离线接线，不是真服务结果。修改安装产物必须在启动前失败；原始源码故意与包不同不能悄悄复制源码救绿。

负例覆盖：旧候选/错误package与manifesthash、缺失或多余桥接文件、workflow未封存、symlink/根目录或越界target、无marker/marker漂移、安装失败与安装后字节漂移。每个失败断言服务启动0、非本轮文件字节不变和持久失败/保留说明；实际包工具已有负例不全部重复，新增接线必须驱动生产owner。保留旧test_s2_stage_runtime.py与test_s2_browser_component.py回归，不删/skip旧用例。

离线操作限：仓库Python/Git及自建tmp；0 Windows/WSL子进程/Parser/主机可执行文件哈希，0模型/GPU/媒体/网络/服务/真实ledger/完整checkpoint。现有主机测试必须拦截宿主启动，不依赖异常捕获后继续。不要扫描testSource或重跑237/旧P2B。保存真实命令/退出码/raw，模型说明不替代执行证据。不得提交二进制DB/源码归档或fixture副本，只提交文本证据；fixture留临时工作区登记清理或保留原因。

交付候选commit、文件清单、合同变化none、实际命令/退出码/测试分母、生产接线说明及限制，READY_FOR_REVIEW；不能签StagePASS。若同路线两次修复无新证据停止整理，不创建新管理工具。
