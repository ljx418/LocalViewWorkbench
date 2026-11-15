# Trusted harness `/dev/null` 最小兼容独审

**本次范围新增 Fatal 0 / Major 0 / Minor 0。READY_FOR_EXACT_ONE_20S_OWN_CANARY_FEEDBACK_AFTER_ROOT_ACK。** 仅表示可由root对冻结plan的一次自有canary反馈发ACK，不是实际自检PASS、candidate运行ACK或Stage PASS。旧五项Major和历史路由incident仍OPEN；当前candidate runtime仍待新证据与冻结准入。

独立读取boundary02 scope、guard、payload、launcher、plan并只比boundary01最小delta。plan SHA256核对为`a8c5d114169d094f369b7dc8838092b1a7b908511efbea01f635ee646bdbd585`；三个pins均匹配：guard `f2f97d2d1191112f60b170b9a0bf69ed5c4ab569f1bffef5903c1ec28a6d6d6c`，payload `408558a23bac55967e0d602e9a3c3e208ec700b498e21153d7198d87dd5143fd`，launcher `25b9c5af4d1e415fff8f04edfa26fdbad6207c6468b1610a40d55aaf988febb8`。新目录记录全部输入/既有raw哈希，未触碰abb/43/215旧报告。

## 触发、修复与Oracle

combined05冻结raw证实：pytest logging配置_FileHandler时对字面量`/dev/null`写open，被boundary01 `open.outside_root`拒绝，pytest_exit=3、collected=0、calls=0、reports=[]。guard preload已CLOSED且CPU FD/线程清理成立。**原189及supp5均未执行**，不能把0FAIL/cleanuptrue说成通过；Claude完成原收据/postcheck不等于获准重跑。

期望是仅放行预存的精确虚拟null sink写open。boundary02 guard:25–30先lstat要求/dev/null为字符设备并保存dev/ino/rdev；95–105只对输入恰为`/dev/null`的str/bytes写open重新lstat核身份，其他路径/fd仍调用原writable。remove/rename/chmod/link/symlink等mutation分支未改，没有泛化`/dev`、realpath alias、删除或改名例外。现有native/network等八类拒绝、单次preload源码策略、目录根/dir_fd/hardlink检查均保持。

payload:15–18增加真正`open('/dev/null','wb')`与25-byte write正例；旧owned create/write/read/rename/remove及九次实际denial不变。launcher只有expected check_count10→11变化，仍要求child exit0、outside自有canary字节不变、9 denials、旧8类拒绝、11 checks全true、negative selftest的clean ledger=false及pins复核；一次20秒、fresh_parent mkdir(exist_ok=False)、无retry、无candidate/product imports。故此次兼容机制记**CLOSED_STATIC / RUNTIME_PENDING**；我没有打开写/dev/null或执行任何代码来验证它。

必要闭合Oracle为root ACK后实际raw证明这11项成立、终态及清理可靠；identity改变/非字符设备/其他/dev或alias不得借null例外放行。当前无boundary02运行证据，不声称已经动态修复。初次只读检查fresh_parent尚不存在，不把该观察代替执行时freshness验证。

## 外层 denial veto 的源码与既有实证

boundary01 validate_feedback.py约25–32在读取runner成功声明前，先要求runtime_denials存在且为list；非空即GUARD_RUNTIME_DENIALS_NONEMPTY，缺失/非list即MISSING_OR_INVALID，异常路径保持accepted_cpu_feedback=false并exit1。empty ledger还需clean标志true、原8类拒绝、单次CLOSED preload、write-root、完整call顺序/实际outcome/cleanup等检查。这个trusted outer不能被pytest exit0替代。

已核对validator SHA与outer-denial-veto-selftest-command.json一致；实际boundary01自有canary child **exit0、passed=true、9项denial**，outer实际 **exit1、accepted=false、GUARD_RUNTIME_DENIALS_NONEMPTY**。guard raw哈希与该decision绑定一致。因此“非空ledger即使child0也拒绝”有实际原始证据；**缺失/invalid ledger只有本次源码路径证据，没有另行运行负例**。该selftest提供的runner参数是canary-result而非普通产品runner，但veto先于读取它，正好证明独立优先拒绝；不冒称曾验证普通candidate的成功路径。

## 限制与下一准入

保持cooperative/pinned Python调用表面的能力声明，不扩大为native、恶意同UID、所有fd或OS sandbox证明。已有fd0/1/2/FIFO例外、未完全介入的os.write/native操作、realpath→open的TOCTOU、unsupported relative dir_fd write和新symlink限制均未改变；literal null身份检查也不是对特权设备替换race的完整证明。无权为compat扩大通用设备写能力。原launcher partial-setup/per-object cleanup失败收据限制、canary未实测singleton preload正例仍沿用guard01报告，不作为本次新Major反复扩大框架；任何实际setup/cleanup缺结果仍不得算自检PASS。

下一步仅是精确冻结canary的root ACK与一次实际自有反馈，保留全部denial/字节/终态清理raw。下一**cooperative candidate有限反馈**另需：有效canary结果独立核验；新candidate/source/依赖及boundary02 guard和outer validator pins；N05/F5/T10所有输出与临时根明确fresh隔离；新命令/env/nodeids/有限预算/root ACK，实际外层必须对任何非空或缺失ledger拒绝，spent child不重放。历史恢复/前后受保护文件核对和未解决Major范围继续明确。ADR16 O1仍允许root在登记疑点下冻结有限反馈，不将此报告变成“所有Major先形式关闭才可任何验证”的新增前置；它们仍阻断N2依赖、正式退出与Stage PASS。

本轮仅NEW output-guard-02三文件；未修改候选/旧报告、未restore历史、未import/compile/collect/run guard/canary/candidate，无模型/GPU/network/media/service/DB/counter内容或额外agent。十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批trusted兼容源码独审完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前门槛root canary实际证据/新candidate冻结；路线OPT-B→OPT-C；剩余一次自有canary和后续有效负例/正式门槛；下一owner root executor；授权本轮只读、未发ACK；证据本目录及冻结raw；停止本范围F0/M0/m0、candidate NOT_READY。实现源码静态已审、机器本delta NOT_RUN、旧事故/五项仍OPEN、无新增人签分开。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
