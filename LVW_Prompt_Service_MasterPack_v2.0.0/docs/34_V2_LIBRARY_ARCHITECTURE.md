# 34｜V2 素材库与命名整理详细架构

CHANGE-V2-LIBRARY-01 / ADR-15，设计候选0.2（独审集中纠偏）。部署不变；仅设计已落盘，下面文件名与迁移序号必须按最终V1真实布局重新绑定。候选Schema、HTTP overlay、DDL分别见 contracts/candidates/v2-library，均不能自动执行到用户库。

## 唯一owner与生产调用路径

React素材库/命名/操作记录 → 同源FastAPI应用服务 → SourceRegistry / AssetDescriptor / NamingCompiler / RenamePlanner / FileOperationService → 同一SQLite与受管小工件。CLI、本地启动器与MCP共享应用服务，Node仅构建；无Redis、向量DB、微服务、多Agent运行时。

| Owner / 建议模块 | 唯一职责与边界 |
|---|---|
| SourceRegistry / source_registry.py | 本地可信根登记/撤销、权限epoch、root/file稳定ID、卷/文件身份、位置和重绑定；API不接受任意绝对根 |
| AssetDescriptor / asset_descriptions.py | 独立不可变AssetDescriptionRevision、字段来源/确认、unknown、人工锁定；不修改Prompt raw或人工稿 |
| LibrarySampling / library_sampling.py | 只读原片句柄、受控probe/seek/抽帧与覆盖说明；原有短视频上传owner不改 |
| NamingCompiler / naming.py | CPU纯函数，字段白名单/无eval、模板修订、合法名、冻结序号、目录规则；无Provider引用 |
| RenamePlanner / rename_plans.py | 冻结清单/源身份/模板描述版本/目标/排序，冲突图和plan_hash；编辑append-only，旧确认失效 |
| FileOperationService/Journal / file_operations.py | 唯一原片写owner，预检、intent、native no-replace、协调/撤销；模型、API路由、MCP不直接改文件 |
| AssetRepository/FTS、最终V1 JobOwner | 稳定业务引用、当前位置/旧名搜索；通用batch/attempt/lease与单GPU调度，不能借shot_batch12限制承载1000项 |

## 源目录、身份与权限

可信本地CLI `lvw source register` 或现有启动器原生目录选择，通过受限本机IPC提交绝对位置；IPC校验本机用户/启动器会话，仅返回root_id。该命令为计划，不是已实现入口。浏览器/API/MCP只接root/asset/file/plan ID及相对展示位置，错误/导出不泄漏绝对根或凭据。登记默认read/list，analyze和rename_archive分别显式授予；撤销递增permission_epoch，所有旧确认失效。绑定不等于写授权。

首版只支持经验证的本地Windows NTFS、普通文件及同卷登记根；拒绝UNC/映射网络卷、symlink/junction/任一reparse祖先、ADS、跨卷、身份未知、大小写敏感目录未验证配置。硬链接多名称共享同一物理对象时，业务记录仍分开；第一版标aliased只读，拒绝写入，不能自动合并/删重。content hash相同但不同file ID的普通副本分别登记。

三种身份分离：source_file_id业务引用；volume_serial+file_id_128物理身份；sha256内容身份。额外记录root身份/epoch、原始相对路径、size、creation/write/change时间和校验版本。路径变化不改变业务ID，内容变化产生新binding/分析修订，旧hash/Prompt/Scene不改写。缺失标missing，权限撤销permission_revoked，歧义needs_attention；重绑定必须用户选择登记根、逐项重验hash/身份，不能按basename自动找同名替代。

本机会话由可信启动器/CLI通过一次性受限IPC引导，秘密不放URL查询、日志、CSV或MCP结果。API保留loopback、Host、精确Origin校验；写请求额外校验会话、CSRF随机头、root scope/epoch、plan确认。Cookie采用HttpOnly/SameSite=Strict；loopback HTTP的安全边界须本机威胁模型和实测，不宣称TLS保护。跨站同host不同port仍须严格Origin拒绝。浏览器会话绝不自行授予root。

## 分页扫描与大视频profile

扫描有持久scan_id、固定root/epoch、cursor、发现/已核验/unsupported/missing计数，分页keyset默认100/上限200；续扫cursor绑定scan及root版本。逐目录有界队列与检查点，不一次列出全部库；取消在枚举/4MiB hash块间检查并保留已登记项。扫描期不推理，size/mtime仅快速线索，首次完整hash必须单独完成后才允许分析复用或写操作。暂不支持的后缀记录unsupported，不因质量失败换素材。

候选library-sampling/0.1：保留PRD现有长片<=2h/20GiB设计范围，原片受控引用；图片仍JPEG/PNG/WebP，视频首批MP4/MOV及经probe白名单的codec，MKV/AVI不隐式放开。大小超过256MiB走新入口，绝不上传/复制整片。probe<=15s/256KiB输出；hash单流4MiB块/单文件候选1200s；默认4、最多8个稀疏窗口，每窗口seek/decode候选<=10s，总抽帧<=80s、索引<=16MiB、原帧<=8294400像素、送模型长边<=768。超限/seek失败/无索引显式失败或人工选择区间，不降级整片无限扫描；不对每镜头重扫全片。

读取期使用可证明稳定的只读原片句柄并校验读前后身份/size/hash一致；记录实际PTS、time_base、有无索引、实际观察区间及未观察区间。稀疏采样不证明整场事件或连续动作。GPU仍一个槽，沿用最终V1硬限制（GPU<23552MiB/RAM>=2048MiB、取消/释放及分析420s/释放30s）；profile预算为设计候选，pilot前不对外宣称可用。不足帧不复制填满；逐实际帧Provider动作计量，上限8，自动重试0，不能在模型失败后改用其他素材。

## 可复用事实与修订

analysis_key覆盖原片sha、实际帧hash/PTS、sampling_profile版本、model_digest、analysis_profile/schema/analysis_template版本和配置hash。复用必须精确匹配；旧分析缺字段显示insufficient，可显式补充产生新raw/description修订。Naming template版本仅参与plan_hash，不改变analysis_key；模板渲染变化不重发模型。创作模板升级与分析模板升级分开。

Description头用If-Match CAS；机器候选与人工修订分离，显式采纳，锁字段不能被后台重分析覆盖。FieldFact={field,value,source_kind,source_ref,source_revision,confirmation,coverage}；source_kind只允许observed/trusted_metadata/user_confirmed/candidate/inference。后两者不能作为确定身份/日期，creative_intent禁止进入事实结构。人工不必填满未知；unknowns为结构化field/reason。

## 命名编译、冻结计划和确认

字段白名单为DJ/Event/Date/VisualSummary/Subject/Scene/Action/Width/Height/Seq；自由表达式、函数、路径插值、Shell与URL不支持。Date只来自已确认事实；技术Width/Height来自probe。模板输出stem，不允许用户改扩展名；原扩展名原样保留，输出不借扩展名转换格式。对无英文事实明确缺值，不伪翻译。

目标stem采用NFC、控制字符与Windows非法字符拒绝；设备名含扩展名、尾点空格、点路径、分隔符、ADS全部拒绝。路径每组件候选<=240 UTF-16单位，完整路径候选<=240单位（含服务端根）作为保守第一版规则，超出明确PATH_TOO_LONG，不截断扩展名/UTF-16代理对。最终支持范围由native pilot冻结，不能改永久long-path配置。

冲突key采用volume+目标parent file ID+NFC/casefold保守键，再加native文件系统大小写核验；这是额外拒绝等价名策略，不声称NTFS自动Unicode归一化。原始路径字节/大小写完整保留。中文/英文受控词表版本固定。序号按冻结原始相对路径的NFC/casefold、source_file_id稳定排序分配；选中子集保留原Seq，不按执行先后重编号。截短时保留固定hash后缀并再次全量碰撞检查；默认冲突阻止，可显式选择确定性后缀后生成新修订。

plan包含全部有序item、旧/目标root与相对路径、源身份与hash、root epoch、description/template修订hash、词表/编译器版本、缺值/长度/冲突策略、依赖图和临时名计划；编辑创建新revision。canonical JSON采用UTF-8、sort_keys、整数与规范UTC、禁止NaN/重复key；hash不包含自身hash、会话秘密或缩略图blob。选中项hash由plan_hash和按plan顺序的唯一item_ids组成。最大1000项/计划，超出显式分批，不能静默截前1000。CreatePlan的target_root_id=null表示保留各自原root/父目录；指定target_root_id且target_relative_directory=null表示该登记根本身，其他目录必须非空安全相对路径。

UI展示original/proposed/thumbnail/evidence/unknown/conflicts，csv/json导出同一plan_hash并转义CSV公式前缀，附第三方剪辑工程路径可能失效提示和旧新映射。导出无秘密/绝对根。确认生成短时一次性服务端record，绑定会话、plan revision/hash、选中项hash、root epochs和到期（候选10分钟）；编辑、选择变更、撤权、源变化使其失效。apply要求If-Match、Idempotency-Key、plan_hash、精确选中项和确认token，不能以可猜ID作为授权。相同幂等键+完全相同请求重返原operation，不能再消费确认；不同payload返回409。恢复/重试是新的受审核计划，不自动复活旧token。

## Windows不覆盖协议与并发边界

候选native adapter使用源DELETE访问句柄、FILE_ID_INFO核对身份，目标parent句柄固定，SetFileInformationByHandle(FileRenameInfo, ReplaceIfExists=FALSE)处理目标同名争抢；禁止os.replace、ReplaceIfExists=TRUE、跨卷copy fallback。每个祖先需原生reparse/卷/身份检查和防替换句柄策略。原生共享模式拒绝其他写/删除句柄以稳定内容；不满足时FILE_BUSY，不偷偷降权。**这些是需要目标Windows试验证实的方案；WSL路径检查或SQLite测试不证明该原语/祖先防替换/flush已有效。**

写owner对root/file ID持有进程级及数据库lease/fencing，实际文件动作保持单写槽。lease过期不自动启动第二writer：必须确认旧执行进程已退出并协调未决步；DB token不能阻止仍持native句柄的旧worker改磁盘。无法证明custody时needs_attention。启动恢复必须先排空未决操作再允许新apply。

预览前、确认前、每个实际磁盘步骤前都核对root/epoch、source物理身份/内容、权限和目标父；持稳定句柄完成本次hash与rename，异步文件编辑不能穿过检查后继续。exists仅用于预览，不是不覆盖保证。动作后核对目标file ID与content SHA，不符停止该依赖组件并记录needs_attention；不自动删任何对象。

冲突图按目标占用依赖排序。只改大小写、交换/环形必须先将该强连通组件所有源以native no-replace转到**原同目录**唯一临时名，再逐个转目标；所有原件的每一步intent先落盘。选中项必须包含依赖闭包，否则SELECTION_DEPENDENCY_CONFLICT；不移动未确认项。临时名冻结在计划并在DB保留，磁盘不预建占位文件，以no-replace直接移入；争抢则拒绝/重规划，不随机更名绕过确认。普通链按空位逆序。失败时保留可定位临时件，不承诺整组件原子。目录本身不改名、不递归删除；归档只往已存在且已登记/核验的同卷目标目录，首版不自动创建目录树。

## 操作日志、崩溃协调、取消与撤销

计划revision不可变；operation状态：queued→running→succeeded/partial/failed/cancelled/needs_attention；崩溃进入reconciling，不把文件动作不明标failed可直接重试。item状态：planned→intent_durable→staged→moved→committed；任一步可进入conflict/needs_attention，未开始项cancelled。每一步记录单调event_seq、step_id/attempt/fencing、旧/临时/目标位置、预期身份/hash/实际观察及错误。终结计数和成功计数分开。

| 崩溃点 | 磁盘/DB核验Oracle | 恢复决定 |
|---|---|---|
| intent提交前 | 无持久intent且未授权执行该步 | 不运行磁盘动作 |
| intent提交后、rename前 | 仅旧位置含预期身份/hash | 记录可继续建议，须现有效授权；不默认恢复推理/自动重放 |
| 临时rename后、event提交前 | 仅冻结临时位置含预期身份/hash | 补记录已发生stage，继续需有效执行范围；否则保留待确认 |
| 最终rename后、DB提交前 | 仅目标含预期身份/hash | 短事务补记位置/索引/commit，绝不再次rename |
| DB声称完成、文件后来变化 | 目标缺失/被改写/多处同ID | needs_attention，保留全日志与对象 |
| parent退出但child未证实停止 | 句柄/进程归属或未决I/O未知 | 阻断新writer，不抢租约、不清理未知进程 |

SQLite短事务先持久化intent（WAL及synchronous策略在pilot验证），事务外磁盘动作，动作后短事务提交event/source_file当前位置/旧名历史/FTS；stage成功同样先登记临时位置，再推进组件后续项，防止环形改名时DB仍占用旧路径唯一键。系统不把SQLite与文件系统说成一个事务；断电耐久超出已验Windows/文件系统flush范围时明确UNPROVEN。

部分成功保留；取消阻止新的组件/步骤，当前已发生动作必须完成身份核验、journal收尾和临时位置登记，不标“无变化”。不保证取消能回滚整批；取消处理中展示真实状态。显式重试只选择未成功且状态可唯一判定的项，成功项不重复；新attempt/plan/确认绑定原操作链。

undo是新反向plan，引用原operation/item/event，逐项验证当前目标仍原物理对象/同内容、原位置空闲、权限及卷；预览/确认/执行使用同一协议。占位、改写、丢失、权限撤销逐项拒绝。反向操作同样可取消/恢复/部分成功；原日志从不删除。内容hash、asset/media/Prompt/Scene IDs和历史revision不因位置变动而改变。第三方工程路径不自动修复，提供映射并清楚提示影响。

## 数据迁移与备份

[candidate DDL](../contracts/candidates/v2-library/storage-additions.sql) 是在原storage.sql上可编译的增量设计，不是已部署数据库；版本号写NEXT_VERIFIED_SCHEMA而非写死2/3。新增source_root/source_file/asset_source_binding、description/template heads+append-only revisions、rename plan/item、operation/event、name_history。唯一约束/FK/check保护引用和命令幂等，复杂事实/计划hash/路径/状态机由同一service校验，不能声称DDL单独证明。

R3-L1前重新审计最终V1schema，映射真实表/迁移版本与Job/Attempt；一致性backup API快照+manifest+integrity/FK验证，事务迁移失败回原库/旧代码，拒绝旧代码写新schema。不得对用户库试跑候选SQL。R4-L3前版本兼容fixture覆盖每个supported V1 snapshot。

恢复DB前停止全部file writers并确证退出；保留不随旧DB回滚的受控journal旁证（candidate设计为每步append-only有界镜像、绑定operation/event hash）。若镜像和DB不同、manifest记录未决操作或已有后续文件动作，先全量协调相关ID，标needs_attention，不覆盖唯一新journal；恢复旧DB本身不回滚磁盘。如何证明旁证flush/保留/容量由L3 native pilot冻结，未证明前禁止自动恢复后写操作。

## 稳定错误、API与MCP

400 INVALID_REQUEST；401 LOCAL_SESSION_REQUIRED；403 ROOT_SCOPE_DENIED/ORIGIN_FORBIDDEN；404 SOURCE_MISSING；409 TARGET_EXISTS/PLAN_STALE/IDEMPOTENCY_CONFLICT/SELECTION_DEPENDENCY_CONFLICT；412 ETAG_MISMATCH；428 IF_MATCH_REQUIRED；422 INVALID_NAME/PATH_TOO_LONG/FORMAT_UNSUPPORTED/SOURCE_IDENTITY_CHANGED/CONTENT_CHANGED/CROSS_VOLUME/REPARSE_FORBIDDEN/FILE_ID_ALIASED；423 FILE_BUSY；507 DISK_FULL；503 MODEL_UNAVAILABLE/RESOURCE_BUSY/NATIVE_CAPABILITY_UNPROVEN；operation项出现JOURNAL_UNPROVEN/RECOVERY_AMBIGUOUS时needs_attention。对原生未知错误保留脱敏native code+UNKNOWN，不伪装重试成功。权限/路径失败在模型/磁盘动作前拒绝。

HTTP增量放在/api/v2/library、asset-description-batches、naming-templates、rename-plans、file-operations，独立LibraryTask DTO，不改旧strict Job枚举/字段与/jobs/batch body。HTTP overlay只添加不相交路径与Library_前缀components，冲突即拒绝合并；旧接口回归逐字段比对。列表opaque cursor绑定筛选/排序/快照，默认100上限200，稳定tie-break为ID；写head必须If-Match；命令幂等绑定会话/route/key与payload_hash。

MCP先增加受控describe_assets（需analyze scope）、preview_rename（独立naming_preview scope，CPU并可保存预览计划，绝无文件写权）、get_rename_plan/get_file_operation（read）。旧analyze绝不包含rename/apply/undo权限；本期MCP无文件写工具。只接受ID及相对结果，不接任意路径/SQL/Shell。实际MCP客户端真调用属于R4-L4，设计Schema不代表已验。

## 参考及未验证边界

Windows官方说明：ReplaceIfExists=FALSE在目标已存在时返回错误，目标RootDirectory可采用目录句柄；这是候选原语选择依据，不是本机race/flush验收。[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)。物理身份由卷号与文件ID组成，需本机API能力试验：[FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)。名称边界另见[Windows命名规范](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)。数据库备份采用[SQLite backup API](https://www.sqlite.org/backup.html)，其数据库事务不涵盖媒体文件动作；[atomic commit](https://www.sqlite.org/atomiccommit.html)不构成跨文件系统事务承诺。

缩略图由受控CPU派生或复用已抽取帧，key为source hash/PTS/renderer版本，候选单图<=1MiB、全局LRU<=256MiB，仅清理LVW自有缓存；分页不重新扫描/解码全视频。缓存与采样预算均需pilot冻结。

## 设计0.2｜独审集中纠偏后的线协议

### 描述/模板头的强ETag

GET /api/v2/assets/{id}/description、GET /api/v2/naming-templates/{id}及其revision/create成功响应在HTTP **ETag header** 返回当前可变head的强值，body仍是该head指向的不可变revision，禁止临时给strict revision加未声明etag字段。ETag为带引号的 `lh:` + SHA256(canonical JSON {version,store_epoch,aggregate_kind,aggregate_id,head_revision_id,head_content_sha256,head_sequence})；客户端视为opaque并原样传If-Match。Header必须与同次读出的body revision一致。

成功新修订在同一短事务递增head_sequence并CAS更新head；revision POST返回新head的ETag，后续写用该值。无If-Match返回428，单个精确旧值返回412且不追加revision/不移head，弱值W/、通配*、列表值返回400。新模板只允许If-None-Match:*创建不存在ID，已存在412；返回ETag供第一次编辑。store_epoch在迁移时生成，DB恢复后先更换epoch并废弃旧会话/确认，再协调未决文件；旧etag不能跨恢复复活。头表/epoch的候选载体见DDL，语义与wire例子见semantic-rules.json；尚不是HTTP运行证明。

### 冲突预览与可执行目标保留分离

rename_plan_item不对target_path_key做唯一约束；重复目标的所有源条目都必须持久化，并在预览/分页/完整CSVJSON保留冲突。预览保存成功不表示可apply。确认时按精确选中项重新核对依赖闭包及目标：未选中的潜在重名可通过取消选择排除，但所选目标之间仍冲突、或未选中源实际占位则阻止确认/应用；不得偷偷丢项或改号。

file_target_reservation独立承载可执行目标的唯一(volume,parent_file_id,target_key)，stage/final两类都登记；在一个短事务中查幂等键、验证确认、建立operation并领取全部所需目标保留。第二个重复目标返回409 DUPLICATE_TARGET并回滚事务，完整预览不变，磁盘动作0。保留成功只是协调约束，不能替代native no-replace。未决原writer未确证退出/步骤未协调时不得清空保留，租约到期不构成释放证明；释放留journal事件。

### LibraryIntent与旧Job兼容投影

LibraryIntent是内部版本化载体，经library_job_intent关联**同一个持久job.id**；scan/describe/file_operation父任务均映射旧kind=batch，描述子任务仍analyze。完整映射见job-compatibility.json，旧Job schema和/jobs/batch请求不改。LibraryTask允许reconciling/needs_attention，但旧Job分别投影preparing/interrupted（后者error_code=RECOVERY_AMBIGUOUS），绝不泄漏新枚举。canonical progress_done=terminal_count、progress_total=固定总项；扫描枚举尚未封存时为0/0，不用动态发现数冒充完整目录总数。

旧GET /jobs及/jobs/{id}保留同ID的canonical batch表示、权限过滤和所有旧字段；library父任务result_ref=null，结果经新领域接口读取，不能让旧UI把operation当ModelRun。纯CPU任务不申请GPU，resource_state=released；describe父投影实际active child状态，未知仍unknown。旧cancel按内部intent派发同一领域owner，file_operation不继承旧analyze权限，须发起会话或明确操作控制权限；取消只停后续并收尾已授权副作用。旧retry对library父返回409 LIBRARY_RETRY_REQUIRES_REVIEW，不盲推理/重放磁盘；旧/jobs/batch无法提交任意LibraryIntent。

### 显式重试关系

新增POST /api/v2/file-operations/{id}/retry-plans，If-Match绑定当前operation，body指定失败/未开始项和last_event_seq。仅原writer已确证退出、operation终态且位置已唯一协调时可生成；成功项禁止加入，needs_attention必须先解决歧义。staged项从journal证明的当前临时位置作为新source_relative_path，不假装还在原名，UI显示该位置及原目标。

新plan的retry_of_operation_id、retry_base_event_seq及每项retry_of_item_id/retry_from_event_seq都进入plan_hash；目标/模板/描述版本保留可审阅，后续编辑仍新revision，需全新确认。原operation/events不更新为成功，不重复成功项。普通重试不借undo_of字段；重试一个失败undo时direction仍undo，undo_of仍指原正向操作，retry_of指这次失败的反向操作，两条关系分开。所有依赖闭包和目标保留仍重新核对，不能复用旧token或legacy Job retry。

### 真实调用与耗时的公开投影

LibraryTask.accounting_ref指向同任务的GET /api/v2/library/tasks/{id}/accounting及/accounting/items（默认100/最大200，opaque cursor与snapshot一致）。汇总区分planned/discovered/reused/model_attempted/failed/not_attempted资产数，Provider尝试数与实际观察调用数分开；逐资产关联source_file/child_job/attempt/model_run/analysis_key和动作ID、复用/未尝试/失败状态。多个显式重试是独立task/attempt，累计费用可沿retry关系查询，禁止重复合并成功调用。

统计来自真实attempt/Provider账本与观察记录，未知实际调用数/未测时间为null，accounting_complete=false；不能把缺证据写0。分别报告scan/hash/probe/decode/inference/preview/file_operation/cleanup耗时；扫描发现数不是完整目录覆盖，未封存只展示阶段计数。CPU模板/预览/apply/undo的0模型调用须真实账本证明，非UI推断。只读统计不返回凭据/绝对根；新DTO不改变旧Job字段。

描述修订显式携带typed tags（TagFact：label/language/source_kind/source_ref/source_revision/confirmation/coverage），facts按(field,language)唯一，标签按规范label/language及来源合并展示但保留证据，不用无来源字符串覆盖人工标签。facts_json与tags_json分别保存；整个tags路径可锁定。NamingCompiler按模板语言选择同语言事实或语言无关技术元数据；bilingual缺任一所需语言仍按缺值策略处理，绝不隐式翻译。标签候选/推断显示其域，不自动升级已确认事实或进入命名确定字段。
