# N1纠偏01：一次集中修复原54节点8失败

失败候选247519de8c1512d86921af8ed2c73f0db3982c88，原HEAD13e7749，根执行计划validation-plan-02原始54call/46PASS8FAIL/0SKIP，功能45/52、integrity1/2，exit1。所有原件/旧失败保留，不声称通过。旧controller/coordinator等owner未变。允许只改tools/v0_s3_native_custody.py、tools/test_v0_s3_native_custody.py和NEW reports/v0-s3/product-gate0/implementation-native-custody-correction-01；native_broker生产源码/现有owners/合同/质量门限/control/MANIFEST/旧报告禁止改。若新证据证明broker存在另一个实际缺陷，先askroot，不用测试放宽来掩盖。

1. 真实路径缺陷：相对log引用拒绝所有冒号、盘符绝对C:/、盘符相对C:foo、UNC/反斜杠、POSIX绝对与..穿越、ADS，保留明确合法相对日志正例。路径验证要在生产validate_launch_plan且任何创建前拒绝；不能仅测helper或改掉拒绝断言。使用宿主无关Windows路径语义，不依赖Linux Path.is_absolute；同样闭合规则在实际broker消费之前生效。源/临时根外零日志/零create用FakeWin32调用Oracle，不真的写Windows路径。
2. FakeWin32.create_job记录其真实分配的假句柄，保留失败调用与零创建语义。FakeWin32失败点按真实Windows façade已定义的稳定BrokerError码映射create_job/job_limit/create/assign/resume/terminate/query_job/close等；不可通过去掉错误码/终止权/句柄关闭断言放宽，错误映射必须逐生产源位置证明。未知failure点不能默认为成功。真实Win32仍未验证，Fake只是驱动owner分支。
3. parent start接受broker主动STATUS，本身不发额外STATUS属现有行为，不为凑2帧改生产。STOP幂等测试应核初次STOP恰1帧、再次stop无新增、sequence不重发、原broker只关一次，不能只删len断言。
4. OLD_OWNERS coordinator正确sha=14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c，逐Git blob/实文件核对后修测试末位，不改owner。报告称root此前抄错末位与原消息不符：root validation-plan-01/reply-body.txt明确已给正确末位c。NEW报告勘误这项归因，旧报告/correction-note-01保留，不倒写历史；root此前没有发现测试未按正确全文修完是静态核对的限制，不伪称故意注入。
5. root旧runner receipt尾部可能存在两个literal字符backslash+n（JSONDecoder原对象已静态读取，trailing另记），属root收据格式问题、不是产品失败，不允许改原字节。NEW报告明确原始bytes hash与该限制；下一root runner只修尾换行，不修改任何历史测试结果，也不为此复跑旧54。

先静态修正和AST，不导入候选/pytest；提交一次精确有限验证计划，8失败节点+路径新边界+fake映射直接关联cleanup/成功正例，不机械重跑全部54/旧20/35等。选定集合需完整覆盖被改Fake façade的关键成功/失败/cleanup，避免重复计数。沿用root前置硬guard、-I -B、原223命名依赖文件、精确collection顺序、真实FD身份/线程，最多1批<=300s，计划source/tool/hash/argv/logs交root ACK后执行。失败原样留存不自动补跑。

原counter只guard外前后各一次只读acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98 inactive28/240/12.362，不写/退款/清零新建或复活。无真实WindowsAPI/Job/OS业务进程/socket/SQLite/模型/GPU/native/服务/浏览器/用户媒体/下载。所有native/GPU/端口/父崩溃/WindowsEOF仍NOT_PROVEN，grant_NOT_VERIFIED、admission=false。独审在修复测试后集中进行，不把作者分类当最终关闭。FIRST429停WAIT_BUDGET不retry/切路由；FIRST审批拒绝/超时停askroot，不包装绕过。唯一ClaudeCode owner不派生Agent，只报READY_FOR_REVIEW。
