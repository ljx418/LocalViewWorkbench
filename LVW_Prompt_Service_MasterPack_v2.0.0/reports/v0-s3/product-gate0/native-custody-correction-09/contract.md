# N1 correction09：无关取消负例的确定性顺序，仅测试修正

原生产候选66600a1bd692c0149fc7724b624997bf2f40dcc1不改；correction08 attempt02实际175/174PASS1FAIL0SKIP/exit1/cleanuptrue。原计划1 NOT_RUN、计划2一次失败、counter=MISSING/历史连续性UNAVAILABLE、旧grant EXPIRED_NO_REPLAY原样保留。

root确认：_ChannelCancel.set是first setter wins，锁内只在Event尚未set时登记owner；现有负例启动外部owner线程后，主线程不等它实际设置_cancel就session.stop，故实际CHANNEL_CLOSE先到。raw不证明外部取消被吞；这次分类为测试调度前置缺口，不据此声明生产完全正确，六Major仍OPEN待独审。

唯一纠正范围：tools/test_v0_s3_native_custody_correction07.py和NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-09/。可以改该模块的私有fixture/helpers和诊断输出根指向NEW correction09/f5-evidence，不能改其他测试/production broker/custody/旧owner/contract/原16+24+18义务/control/MANIFEST/旧报告。若任何其他必需变动，先askroot。

1. 外部owner helper等待实际read已阻塞的明确事件（有界且检查返回）；设置同一实际channel._cancel、不命名owner，随后才发布external_cancel_published确认事件。主线程必须等确认后，断言flag已经set且origin确为None，才执行首次公共stop。不能sleep/轮询/概率重跑或给生产代码加fake benign接口。
2. 外部owner异常也须传回测试owner并有界唤醒，不能worker thread抛断言而主线程仍执行close。finally要join该精确线程以及真实chain安全收口；不在活worker下关file，不靠daemon退出。
3. 原负例reader error非空/来源未知不当正常close、broker保持UNKNOWN、连续两次公共stop不丢首错及原deadline不变的断言全部保留。错误码若实际来源确定会不同，不自行改接受集合，先列真实来源证据与具体oracle关系给root；不能删error/close_cancellation断言。
4. 已通过正常close取消、定向原thread HANDLE故障first retained→second released、成功项不双关的场景保持。此次因提前失败未执行的负例继续真实执行：无关取消第二stop、普通读故障两stop、partial frame两stop。预计10份phase JSON、旧实际只有5份，因此缺少5份，不能把“4个子场景”当缺少文件数。逐份before assert写真实facts，未走到阶段明确NOT_RUN，不预建成功JSON。root不为计数说明另开验收轮，随本次报告一次勘误。
5. source文件只有本模块改变；原175node身份顺序不改，可在同节点内加强明确event/owner来源观测但不删弱断言。新增diagnostics文件只写NEW correction09目录，禁止覆写correction08的5份实测JSON。

先静态修改/AST，精确路径Git提交新候选，再askroot唯一175节点有限计划。生产两源及其余测试相对66600a1逐字相等必须报告。plan含实际source pins/原223依赖文件/3stdlib、NEW root correction09/validation-plan-01工具（继承correction08/validation-plan-02的硬guard及absence mode）、三条精确argv/cwd、<=300s一批、逐node/raw/退出码/FD真实身份/全部线程/10份诊断。
原临时counter与parent仅外层lstat前后必须MISSING，不读取/重建；历史连续性UNAVAILABLE_NOT_PROVEN，旧授权不复活；不能复制旧counter-read形状。hardguard先于candidate/pytest，只一次可信stdlib dlopen(None)后永久关闭，真实Win32API/Job/进程/GPU/模型/网络/socket/sqlite/媒体/下载/原ledger均拒。任何runtime denial失败，不能把guard拒绝当通过。
ACK前不import候选/collect/pytest，不跑guard/absence工具；ACK后单次，失败保留候选和证据，不自动修到绿/重跑/循环stop。FIRST429停WAIT_BUDGET不retry/切路/root接手；FIRST审批拒绝/超时停不包装绕过。ask后结束turn等待reply，不同时worker_done。原六Major仍OPEN，不StagePASS，不N2/真实运行。
