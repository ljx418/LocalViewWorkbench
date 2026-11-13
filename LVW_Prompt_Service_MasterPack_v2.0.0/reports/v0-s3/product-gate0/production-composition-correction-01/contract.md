# 生产组合纠偏01：一次集中修复M01–M09/m01–m02

基准7c27a11；根依据独审F0M9m2，全部采纳，不以顶层BLOCKED遮掩内部错误。此文件澄清内部接线实现与文件范围，不改公共API/Schema、产品分母或质量门限。原固定I01–I24/产品12不变，旧13仅072组件证据，旧grant过期。

## 架构裁决与唯一owner

真实native可信准入后端当前未实现，必须显式硬拒绝NATIVE_EXECUTION_BACKEND_NOT_READY，controller和worker默认CLI均在spawn/native-driver构造前拒绝。不能以JSON status/布尔/自算hash或修正is为==后放行；旧native proof链只可诊断，不授权。保留未来接口范围但本批不虚构签名/授权平台，不用--force、env开关或context seam旁路。进程内typed offline seam只证明组合，保持offline标识。

只允许controller、composition测试、quality_worker及其必要兼容测试；supervisor只允许build_production_command固定命令构造函数增加明确worker context hash交接和必要相关测试，其余监督/协议/caps不改。可新增小型controller私有I/O helper tools/v0_s3_controller_io.py供controller/worker复用，禁止另建通用文件平台。coordinator既有安全原件owner逻辑不改；原QualityPhase/runtime/authority/executor/runner/fixture/public contracts/阈值/旧报告/control/MANIFEST/V2禁止改。NEW报告implementation-production-composition-correction-01。

## 逐项实现与验收义务

M01：字符串类型和值正确比较（==），bool身份严格；JSON解码字符串与Python字面量一致。修复比较不能放开真实native；必须同时落实M02硬拒绝。
M02：controller/worker默认native直接返回明确未实现拒绝且0spawn/0driver构造/0模型；缺可信后端绝不接受自写PROVEN链。不要声称S3BudgetBindingProvider.sealed已验证余额、有限授权或native custody。诊断可核binding形状，但仍非执行许可。typed Python offline driver注入不可由CLI/序列化字段开启，不调用真实NativeRuntime。
M03：CLI入口强制精确controller context hash；固定生产command把worker context hash传到底；每次worker重新加载均校验预先封存的同一hash，不能由子方自行重算替代期望。新增内部CLI参数只用于hash，无任意argv/module。provenance controller_context记录真正controller bytes/hash，worker_context另列；context换driver_arguments/source/projection在二次load前变更必须拒绝，不能旧hash+新内容成功。默认CLI无seal拒绝，不执行native。
M04：所有新context/reference/dependency读取有实际limit+1有界读、regular/no-follow/nonblock，不能read_bytes后查大小。安全句柄/受控锚点读取及内容hash同源；FIFO/设备/祖先重定向稳定拒绝，必要共享小helper，不绕过已接受owner/读取任意未知私有路径。exact/oneover证明实际读取上限，FD失败清理。root/controller context作为显式入口可由可信本地调用传路径，引用边界须逐项明确，不能以任意路径当已有读授权。
M05：最后消费者从绑定原件owner取得已重核数据；不在_provenance里另外unsafe read。在最终消费/写入准备边界重新验证root/manifest/原件，raw/canonical/root在ORIGINALS_VERIFIED后受控变化必须拒绝UNKNOWN保留，不输出矛盾hash。尽量使用已验证bytes/metadata缓存，明确最后实际观察边界，不承诺之后文件永不变或多文件原子快照，不新增无限重开/校验循环。
M06：summary与reservation落盘以绑定root dirfd、逐层no-follow目录身份、O_EXCL叶写入，mkdir/open不能跟随祖先；root/temp/summary目录换链接或对象时拒绝、不写根外。只本轮根内创建，未知外部内容不删除；错误保留partial证据。
M07：收据严格按完整义务生成，原件存在/计数非None不是output/resource/no_overwrite PASS。没有对应全义务机器证据就BLOCKED/NOT_RUN；任一实际失败须FAIL或不明，不能无条件PASS。最后16行15PASS1FAIL与首行失败/释放残留未证均负例；顶层产品12 BLOCKED不掩盖内部状态。清理/预约root_retained等以真实产品cleanup证据决定，worker退出只证明worker，不能把缺服务清理写false。合成原件执行事实与产品义务分列，原始raw/用户稿不改写。
M08：run/main所有普通异常统一进入持久UNKNOWN/保留收据（若安全落盘失败则显式报告未持久化，不能伪造成功），finally有界关本轮FD/pipe/worker seam；不吞KeyboardInterrupt/SystemExit取消；FileNotFound/OSError/写失败/异常类型均有稳定诊断与原始失败证据。不能捕异常后成功退出或删partial。
M09：预检通过后、任何worker发送前，以受控根内排他reservation/已有终态检查取得同run唯一执行权；已存在summary/reservation时拒绝/只读协调，不再跑16行。不能只到最终O_EXCL才识别重入。保留历史失败/预约，不自动删锁重试，不换runid绕过；并发争抢最多一方运行。
m01：离线线程seam增加协作取消、准确join/未决状态，不能daemon/poll假退出；非合作callback无法安全kill时明确UNKNOWN_RETAINED并保留所有权，别宣称无晚到/无残留。可收窄typed synthetic driver取消协议，在允许下一submit之前检查取消，报告不可强停边界；测试控制方自行释放/join的恢复不算产品清理证明。无需新增真实OS进程或假装可kill Python线程。
m02：worker错误输出适配text/binary stream，保留准确WorkerError code，不被TypeError覆盖，默认CLI也明确原拒绝码。

## 定向闭环与范围

独审所有11项探针一次回归，优先复用原集中脚本但Oracle不能抄PASS自述；正例精确候选身份驱动正式controller main→worker main→QualityPhase16→pipe→parent→canonical→manifest→真实收据适配→safe summary。负例覆盖每项生产入口、触发、准确Oracle、持久终态和FD/线程清理；固定24只列实际离线范围/仍缺native，不能签StagePASS。测试用例数/调用次数/interim重复分开，保留每次原始日志，不机械123/84/13/41/186/257。失败不覆盖、不伪恢复早期遗失流。

pre-importguard禁subprocess/socket/fork/exec/system/sqlite3.connect/原ledger，零fixture/网络/GPU/模型/服务/下载/用户原件；只本进程thread/pipe/合成文件。原counter inactive28/240/12.362，仅外层只读hash acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98；不退款/清零/新counter/复活旧grant。首次Claude429停WAIT_BUDGET禁止retry/换模型账号providerHarness/Codex接手；首次审批拒绝/超时停askroot不绕过。独审和人签不代替。
