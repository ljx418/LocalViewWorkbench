生产组合纠偏04独立审查：M08 CLOSED（本次离线组合范围），Fatal 0 / Major 0 / Minor 0。候选 b95de076f37e64d321629c065e5531eba8a5250a，delivery 13e77492361648dc90a414f7fd37f0bb8b8c3634，源码 baseline 6885f7a62b223f5e2c7904a9f929e760396fd88b；不签 Stage PASS。

已读 AGENTS、governance README、execution-control、执行索引、root correction04 contract/root-decision/received-review review，以及实际 M08-finish、disk-observer、close-observer JSON。根因裁决以候选源码和独立 Oracle 为依据，作者20PASS与root intake仅是待核证据。24个received文件均逐字节匹配delivery Git blob；作者ACK的20唯一节点、精确argv/cwd、root runner哈希、source pins均独立匹配（received-blob-verification.json、author-evidence-checks.json）。没有重跑作者20/35或旧独审27/37整套。

自身HEAD 204e585f81837d9743869b94030ae941b2d52be4始终未变，index原字节保存在initial-index.bin，起始status和91个源码hash见initial-state.json。物化前91源逐Git blob等于6885f7a，未把自身HEAD当源码候选；仅写入指定controller和composition测试两个候选blob，全部91源等于b95de076，批末仍匹配pins、index字节不变（materialization.json、final-integrity.json）。未checkout整树/reset/clean/add/commit，未改CMD，既存修改和未跟踪工件均保留。源码baseline到delivery多出的旧correction03/candidate-delivery.json是前一交付6ea33bc引入的原样记录，在本次delivery逐字节未变；相对6ea33bc，本次仅两源及NEW implementation-correction04证据。

本轮计划plan.json SHA256 7990b25c867f9f5df2ea481baca60b00fa3987f8126ec184fdaade07297be049；占位请求无效，root仅对更正请求msg_6620cb6bc81e给出唯一ACK msg_70d29314f689。ACK后只执行一次冻结15case，无pytest.main/collection，无追加或补跑。精确绝对argv/cwd/起止见exit.json，命令为/usr/bin/python3 -I -B NEW/guard.py NEW/runner.py NEW/guard.json，cwd为review包根。exit0，18.853245秒，未超时；15断言PASS、0FAIL、0有效缺陷、0本轮已观察探针限制，不能换算为产品通过数。

前置audit guard在任何候选/pytest导入前安装，6项审计事件自检拒绝，runtime denials为空。guard后核91源码、5工具/解释器pins和223个已封存命名依赖，显式append已装目录，没有site.main/.pth/下载/插件collection。仅本进程threads/pipe和NEW合成文件，无业务子进程/模型/GPU/native/网络/服务/browser/用户媒体。原counter仅guard外前后各一次只读，sha256均acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98，inactive/28/240/12.362未变；无写/退款/清零/新counter/复活grant。

M08关闭依据集中列于findings.json、oracle-summary.json和以下原始JSON，三处原有效失败均用独立探针重新触发：

- run终态约2730起、_release_owned_resources约2511及_finish约2830：_finish入口RuntimeError时，预期诊断失败不阻止owner清理且返回UNKNOWN。实际exit4/UNKNOWN_RETAINED，FINISH:RuntimeError，完整fd_cleanup为UNKNOWN且fd_leaked=null；后续POST_RELEASE正常仍不追认PRE_RELEASE。spawn时真实自有stdin FD10为dev15/inode6408832/mode4480，stdout/stderr也记录真实FIFO身份；产品返回、测试清理前无新增FD，仅MainThread，外来FD身份未变，自有anchors已释放（M08-finish.json）。_finish没有承担唯一清理入口。
- 第二次_fd_snapshot RuntimeError：实际exit4/UNKNOWN_RETAINED、PRE_RELEASE status UNKNOWN/fd_after与fd_leaked均null，POST_RELEASE fd_leaked=[]；真实owner已关闭pipe、线程结束，状态仍UNKNOWN，未被后观察追认（M08-close-observer.json）。
- _record_disk_actions入口RuntimeError：实际exit4、非空结构化stdout，UNKNOWN_RETAINED/CONTROLLER_DISK_ACTION_RECORD_FAILED:RuntimeError；已写summary与reservation保留，fallback summary_written=true，终态receipt成功写入且也是UNKNOWN；未逃逸到main exit5/空stdout。fallback直接使用本轮单调事实，不重试失败observer（M08-disk-observer.json）。
- _record_disk_actions/_observe_summary_visibility约2250起：在已写summary后对stat注入EIO，以及把summary移动到同合成目录另一名字。两者仍保留summary_written=true、原path和原hash，当前visibility分别UNKNOWN/EIO与UNKNOWN/ENOENT；前者内容独立读hash与动作hash相符，后者只声明路径不可见，不谎称未写或回滚。资格字段summary_persisted与disk_actions动作事实保持区分（history-stat.json、history-move.json）。
- seam.close注入OSError：实际exit4/UNKNOWN，owned_resource_release.status=FAILED，close_failed=true，错误明确且线程已结束；返回时确有未关闭的自有FIFO FD10 dev15/inode6426650/mode4480。先保存真实FD/线程/receipt，再由探针明确持有的原seam.close清理；这不是产品返回已清理的证明，也不算被允许的故障下假成功。外来FD3身份不变；没有关闭未知FD、GC或依赖进程退出清理（close-failure.json）。
- 单persist RuntimeError保留真实summary_written=true、receipt_written=false并返回UNKNOWN；双异常保留primary ValueError和secondary RuntimeError。receipt是否写出来自_persist_receipt实际成功返回，未用exists自证。持久化KeyboardInterrupt/SystemExit继续传播，事先owner释放及finally anchors释放有效；真实FD映射和线程在测试清理前已保存（M08-single/double/keyboard/system.json）。
- POST_RELEASE observer RuntimeError：返回UNKNOWN/fd_leaked=null，而已落盘PRE_RELEASE receipt仍为SUMMARY_PERSISTED且无POST_RELEASE字段；返回显式persisted_receipt_state=SUMMARY_PERSISTED。既存收据未重写，未把后来观察塞进旧产物（M08-observer.json）。

必要直接兼容：positive通过真实16行QualityPhase、真实pipe/parent reader、canonical/manifest/provenance主链，原件hash逐项匹配；正式output_contract/no_overwrite/resource_budget仍BLOCKED、summary.pass_count=0，composition facts不替代正式收据（positive.json、positive-oracle.json）。两项取消兼容按ACK直调必要函数，无collection，包装在函数测试finally前保存产品返回FD/线程/receipt：合作取消结束；非合作线程产品返回时仍活着、retained=true、late_write_after_return_is_possible=true，状态UNKNOWN，线程不可kill。随后由测试释放自身阻塞事件并有界join，这只证明测试收尾，不能冒充产品返回时线程已结束（cancel-*-before-probe-cleanup.json）。独立owner释放不新增cancel/spawn/kill，源码和运行事实均相符；owned_resource_release的RELEASED必须结合明确worker_thread_alive/retained事实解读，不代表非合作线程已消失。native默认REFUSED_BEFORE_START留下空temp/s3-production-controller目录，零spawn/summary/receipt，保留已接受语义（native.json）。

每例末FD身份与起始相同；整批起末均仅FD0/1/2且dev/inode/mode完全一致，仅MainThread（results.json、cleanup.json）。close故障/非合作场景另有清理前观测，不能用批末零遗留抹除受控产品返回状态。无新增有效F/M/m；M04/M06/meta01/m03/M05/M07/FDsnapshot/P01与更早关闭项未发现确切直接回归，不机械重开。旧FD8身份仍UNKNOWN，本轮有真实FD8也不认领旧身份。

归档独立核对见archive-reconciliation.json：对原作者03 ZIP只读逐成员hash及metadata，不解压、不执行链接；对保留pytest-temp树逐名lstat递归，不跟随symlink，仅regular读内容，symlink只readlink元数据，FIFO从未打开。实测3504=2878regular+596dir+29symlink+1fifo，ZIP恰为2878 regular成员；regular名字集合双向差为空，逐成员内容hash全部匹配。报告列出完整逐名类型/模式/大小/身份和regular hash证据，不仅复述作者数字。596目录/29symlink/1fifo没有封存进原ZIP，不能从regular全齐声称所有文件类型全打包。原ZIP hash b73e653ca04570cdaad8ff77c0b0a12fe59a3e585899f22155f67a84717bbf44未改；此证明当前保留树与封存ZIP的regular对应，不独立证明3504项历史树的不可变封存身份。链接内容不被执行或跟随。

固定I24、产品12、真实native、Windows/A06、原ledger、质量及人工签署仍未证。结论只关闭M08离线组合纠偏，不签StagePASS、不推进control、不降低阈值。

停止十字段：当前坐标R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION；本批完成一次15case与独立M08裁决；最后通过门禁仍control既有统一切片；当前阻塞为固定产品/真实运行/质量/人签未证；全局路线S3离线生产组合纠偏；剩余固定产品验证与签署；下一责任人root；所需授权本批唯一ACK已执行，无新增人批请求；证据本NEW目录；精确停止原因独审完成F0/M0/m0、M08关闭，禁止自动补跑。

V0–V3完整大纲（control完成子项/总子项）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
