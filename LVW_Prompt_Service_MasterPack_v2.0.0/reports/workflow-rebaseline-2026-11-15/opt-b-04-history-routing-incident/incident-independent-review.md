# 历史证据写路径事故独立评估

**本事故 Fatal 0 / Major 1 / Minor 0，RUNTIME_HOLD。** 原94cdd82的五项Major及189PASS/supp3PASS2FAIL数值原样保留；追加的限制是：本次运行发生越界历史证据写入，**不能作为输出隔离合格的正式退出checkpoint**。CPU FD/线程清理与文件/证据隔离是不同义务，无Stage或N2放行。

## 捕获与归属核验

事故包incident.json、disposition.md、combined-execution-receipt.snapshot.json已读，候选固定为d645bd559af89921cd0359612cce7b78c4892fe8。对十个精确路径逐一比较，结果全部成立：观察副本=实现区当前dirty文件；原件副本=候选Git blob=当时pre-run HEAD blob=当前实现index；两组SHA256分别等于incident清单，且观察值与原件不同。当前均为regular file、link count1，无symlink；仍仅这十历史文件与无关integration report列为tracked dirty，未读取或处理无关report内容。逐文件blob/hash/当前metadata保存在source-binding.json，未递归复制历史报告。

**收据本身不能证明运行前干净。** 它只验证source/dependency/tool pins和fresh combined01，十份历史输出不在61个source pins里。额外只读调查找到了原始执行会话425850b4-055a-47b8-9dba-d311b90b2440的tool记录：

- `call_01a1de5511f774afa8f3e349`，命令08:31:19.678Z，从实现包cwd执行HEAD/empty-root检查及`git status --short | grep -v '^??'`；08:31:26.954Z真实结果为HEAD **57a0fb0abf529e7865ae2265f8c5c7771c0d21a9**、combined01空、仅` M reports/v0-s3/product-gate0/implementation-integration-01/report.md`。过滤只排除untracked，没有排除tracked历史路径。
- 这提供了**运行前十路径tracked-clean的实际Git状态观察**；独立git show确认57a0的十个blob均与d645原件相同。后续before为08:31:57、guard于08:32:48–08:33:42运行，与原始执行收据对应。所需窄范围command/result片段及各record哈希已绑定，没有复制整个会话或读取不相关私人材料。

Orca当前terminal read只有重开后的任务screen，不能当旧运行记录；经orca-cli索引定位到上述既有原始tool记录。索引为degraded，因此没有把搜索不到的材料当不存在证明。当前index flags均H、fsmonitor/ignorestat未配置，只是当前补充信息，不倒推历史flag状态。

**仍缺失**：十文件的即时pre-write字节哈希、status到实际写入期间的独占writer证明；mtime、当前index及事后收据不能补造这些历史事实。不能绝对声称未观测到的并发/隐藏改动不可能存在。现有原始tracked status、匹配的preHEAD、固定N05写路径及保留输出，足以支持狭窄的canonical Git基线修复判断，而非宣称已重建每个写前瞬间。

## 精确恢复建议（审查者未恢复）

**建议由root执行仅这十路径的精确Git基线恢复，前提是封存事故及重新确认归属。** 这不是批量reset，也不是回滚数值结果。执行前取得这十路径的单一写入所有权，复核每个当前SHA仍等于observed capture，文件/父目录身份和link状态未变；任何漂移或新工作即停止，不覆盖新owner内容。然后使用清单中的精确d645 blob字节逐文件恢复，核对结果SHA等于原件；无关dirty report、源码、index、原始combined01和事故两套副本均不动。保存实际compare/write/posthash收据和精确路径清单，不复用“未恢复”标记，也不自称这是pre-write原状的密码学证明。

恢复不会抹去运行输出：真实覆盖字节已在observed-run-output完整封存并绑定，Git原件也已保留。事故报告、原运行FAIL与旧独审均不得改写；恢复只是清理工作区历史证据路径，不能将事故运行重新标为clean/PASS。若root要求“绝对证明恢复的是即时pre-write每个字节”，现证据不满足该更强主张，应保持capture并标unknown，不能以推测填补。

## Major HISTORY-WRITE-ROOT-01 与最小边界设计

根因是同一输出隔离链：精确N05源码91–104把EVIDENCE_DIR硬编码为correction-14/evidence，write_phase执行mkdir+write_text；R10的first/recovery/empty-owner/converge真实调用产生这十个名字。冻结runner只传T10/F5输出env，N05不消费它们。旧guard（实际pin为opt-b-02/targeted-plan-03/guard.py）对open只做counter/DB等子串deny-list，不读写flags、不验证目标是否在fresh root；这十个普通JSON写因此被放行。runner的FD/thread库存与fresh combined目录都不检测历史内容截断，runtime_denials=[]仅代表旧deny-list没有命中。原snapshot中十个raw摘要哈希也仍与实现区原收据逐份匹配，说明保留了真实结果，但不能证明不存在额外文件写入。

最小trusted executor应在现有单批root harness内完成，不另建服务或通用诊断平台：

1. **root先封存写能力与路由。** 固定candidate/工具/环境/cwd及唯一fresh输出，给N05等实际writer显式run路径；预flight静态审计所有本轮writer。候选仅可写本轮evidence、F5、pytest-temp等明确子根，source/history/dependency/治理根只读；日志、guard/runner/control收据由trusted executor单独持有，不能把整个仓库或控制收据目录放入候选可写allowlist。创建fresh根并记录device/inode、无symlink/旧内容，再装边界后才import/plugin/pytest。spent root/child不可重放。

2. **按实际mutation判断，不按后缀/字符串。** 至少覆盖open的write/append/create/truncate/RDWR（包括os.open数值flags）、mkdir、truncate/ftruncate、unlink/remove/rmdir、rename/replace及link/symlink等会创建/改变对象的形式；无匹配许可或参数不可判定则failclosed。历史JSON的此次O_TRUNC open必须在打开/截断前被拒绝。rename/replace须检查源与目的及其父根，不能只检查目标；root内部原子写仍须双方均在许可子根。不能把“写后git diff发现”说成预防。

3. **dir_fd/descriptor及链接不可略过。** 相对路径按真实cwd或对应dir_fd锚定，不能把dir_fd相对路径误拼cwd；审计事件未携足dir_fd信息时，须由trusted wrapper提供完整语义，或拒绝该形式，不能猜。整型fd/fdopen、已有可写fd、ftruncate/os.write等须有可信fd来源约束，不能靠open路径检查声称都已覆盖。symlink父组件、leaf替换和跨根hardlink须阻断/精确控制；pytest需要的内部链接单独冻结，不能泛化放行。rename不能把任意外部对象搬入可写根后改写历史inode。

4. **明确race与能力边界。** 纯realpath/resolve后再open有TOCTOU；chmod只读、无并发声明或Python monkeypatch不是完整OS写隔离。若要声称对并发链接/dir_fd/native写也不可越界，需在同一trusted启动边界采用OS强制的只读源/历史与仅fresh-root可写隔离，且候选不能解除它，或真正的目录能力/不跟随链接的原子打开机制；实现与负例未验证前不作强保证。仅增强Python audit allowlist也能拒绝**本次普通Path.write_text回归**，但须如实限定为已验证的Python调用表面，不能冒充任意C扩展/裸syscall/恶意同UID程序安全沙箱。此处只是设计，未新增或执行native权限。

5. **有限可信负例和双重收据。** 新root ACK之前，先给trusted边界做有限自检：此次历史路径、相对`..`、write/truncate flags、非默认dir_fd、symlink逃逸及rename两端；合法fresh写为正例。拒绝事件即使被测试catch仍令批次失败，不允许清空/覆盖deny收据。随后每次新批次记录受保护tracked基线的before/after精确差异和run输出清单；这是逃逸检测补层，不替代预防。保留真实命令/异常/原始结果及FD/thread证明，不能由pytest exit0或文件存在单独证明隔离。

必要的runtime hold条件：N05路由与旧五项纠偏的新候选冻结；trusted executor写根边界设计/实现独审和有限自检证据；事故封存及root若恢复则有精确恢复收据；全套source/output route审计、fresh根/工具依赖pins/argv/env/nodeids/预算及**新**root ACK。COMPLETE-03母授权不因旧child终态失效，但spend child不能复用；此incident correction不授产品/model/GPU运行。任何仍未知的写边界或实际越界都继续阻断。

本事故是历史必要证据隔离Major，非辅助展示Minor；没有新增产品数据/原件破坏证据，故未列Fatal。原189数值、supp3/2和CPU资源事实仅作真实受控反馈；产品29及原9项原生未知不变。旧94cdd82保留，本附加报告给它补充输出隔离限制，不回写旧结论。

仅写NEW本目录review.md/findings.json/source-binding.json，精确stage这三文件并一次提交；无candidate import/compile/collect/pytest、无194重跑、无恢复/候选修改、无counter内容/服务/GPU/media/network访问、无子agent。采用只读orca-cli技能定位明确执行会话tool片段，未向实现终端发送指令；技能见`/home/administrator/.agents/skills/orca-cli/SKILL.md`，协调结算用既有orchestration技能。

十字段：坐标V1/R1/WP-R1-U3/S3_P4；本批incident独审完成；最后通过UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW；当前阻断历史写隔离Major及旧五项；路线OPT-B→OPT-C；剩余精确恢复记录/路由与trusted边界修正/新有限证据；下一owner root harness与Claude test owner；授权本轮只读、无新runtime ACK；证据本目录及事故包/窄原始tool记录；停止RUNTIME_HOLD F0/M1/m0（旧5项另存）。实现正在独立纠偏、机器原结果保留但无clean退出、独审事故阻断、无新增人签分别记录。

完整V0–V3大纲（execution-control完成/总数）：V0-S0 1/2；V0-S1 5/5；R0 1/2；R1a 5/5；V0-S2 7/8；V0-S3 0/6；R1 0/4（当前Stage）；V1-M1 0/3；R2 0/4；R3 0/4；R4 0/4；R5a 0/4；R5b 0/4；R5c 0/4。
