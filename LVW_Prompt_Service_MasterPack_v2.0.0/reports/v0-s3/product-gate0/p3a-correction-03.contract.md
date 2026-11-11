# P3A 纠偏03：原目录绑定的运行根分配及相邻副作用检查

Root裁决接受3ecd45b独审M04，M03与原M01/M02/m01全部保持关闭。原合同无外部写入义务未变；本补充仅授权最小运行根分配与相邻回调交接修复，不新增产品功能/门限/权限。不重做包工具。

允许tools/v0_s2_stage_runtime.py增加最小内部root分配/准备目录seam（默认保持原S2方法及行为）；tools/v0_s3_stage_runtime.py受保护分配及生命周期；tools/test_s3_install_handoff.py和原P3A新增测试。若同类回调窗口实际存在于OwnedArchive登记收据，可最小修改tools/v0_s2_stage_archive.py的内部持久化seam（默认旧行为不变），配套相关定向测试；不得重写archive/prepare整套算法、添加通用平台或任意shell/callback产品入口。包owner原则上不改，先前17项独审只在字节/依赖有效时显式复用，不计新跑数。新证据仅implementation-p3a-correction-03/。禁止改旧独审/原raw/合同/authority/质量集/坐标/MANIFEST或删测试。

## M04 必须行为

原parent在进入prepare之前固定。verify_complete或authorize等受控回调返回后，root创建须使用这个原parent的目录描述符及单相对名、exclusive mkdir，不能tempfile.mkdtemp(dir=失效pathname)。可选择先发现漂移即拒绝（零root创建），也可在已拥有原inode内分配并保存真实保留身份；任何replacement inode创建必须0。随机名和碰撞尝试次数有限，mkdir后立即no-follow打开并核验原root身份，异常无路径删除fallback。

root分配失败或分配后尚未archive登记时也要有真实失败收据、原错误与原对象保留/UNKNOWN说明。不得为避错提前写入“已登记”或篡改OwnedArchive身份。准备input/output/temp/custom_nodes以及登记收据的实际目标也要与同一原root/parent一致，不能修完mkdtemp后下一行又经替换pathname写入。默认旧S2路径保持行为和既有回归；新protected模式只能原inode或fail closed。

## 本轮一次性相邻边界核查

在收据列出有限表：complete验证返回→root分配；authorize返回→实际登记/写入；archive.register/lease返回→准备子目录；部署返回→样本/参考写入；NativeRuntime受控准备回调返回→最终preparation证据写入；错误处理→收据/删除。逐项列生产位置、现有保护、是否有可复现替换inode副作用。对同根因的实际缺口在本白名单内一次修正并补断言；不存在的不要凭想象新增通用机制。仅事前事后guard不能冒充中间会调用可变路径操作的安全证明。不是要求防御任意恶意内存修改或任意指令级OS race；已披露的原owned inode被移动限制保持，不把它当替换inode写入的豁免。若需超白名单修改实际owner，向root一次汇总具体位置/复现/最小改动，不自行拓展。

## 固定验收

新增M04明确生产_prepare断言：在verify_complete内移动parent并返回有效proof，replacement新文件/目录0、服务0；原parent中的收据/保留状态真实、原异常保留、所有描述符闭合。再验证授权回调和登记→子目录交接同类边界，正常default/warm成功路径仍通过。保留并执行原54项及新增、旧23项S2回归、原独审5项+M04 gap断言一次（原文件不改）。若archive owner实际改动，补它的相关定向回归；不跑P2B/全项目/早期缺陷观察套件。失败日志真实保留，不以skip/改断言消除分母。

所有测试安装/归档均synthetic临时夹具、受控Git/Python，真实Windows/WSL/PS/Parser/hosthash/媒体/模型/GPU/服务/网络/ledger/完整checkpoint全部0。登记与清理自己的tmp，文本收据绑定新candidate/命令/退出码/用例数，禁止提交DB/包/源码快照。无新人工授权需求。交付READY_FOR_REVIEW，隔离审查后root裁决；本次关闭原M03属于有效进展，不错误应用无进展停止。
