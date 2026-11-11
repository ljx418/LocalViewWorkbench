S3-P2B独立审查已失败/部分完成的真实批次，不能把worker outcome=failed改写为已通过。候选34de7b54a529a8947d63736c6f1bd345828cad57，证据tip210fb1e130ac749e9537bda895472b7a3b5101f9，root7e33e6112d9df330ef4385773e41072a7c2f5469。你未实现此候选。先确认worktree干净，再git merge --no-edit 210fb1e130ac749e9537bda895472b7a3b5101f9，冲突停止不覆盖。读AGENTS、execution-control、完整p2-binding-contract.md、runtime-binding-child-01.json、implementation-p2-binding/所有原始证据和P1已验证边界。
唯一新增reports/v0-s3/product-gate0/independent-p2-binding/；不改工具/业务/packet/计划/旧证据。旧P2B child已实际使用并过期，禁止新Windows/WSL实机批次、metadata发现/安装工具hash、真实ledger、源媒体/preview、服务/GPU/模型/网络/下载/完整checkpoint操作。不终止任何旧PID、不删除FAILED_RETAINED目录、不退款/settle0。可以只读已经登记的fixture文本/标记/SQLite（如确有必要，只URI mode=ro，不调用authority/transaction）以核对证据，但不能借此继续批次或发新合成debit。测试仅新建owned合成fixture，执行P2B新测试及P1相关回归一次（实现者83，核对具体命令/范围）；不要重跑完整仓库或verify_pack。

集中审查两个层次：
A代码：wsl-fixture限Windows+WSL tempfile marker root及同fixture ledger，不能进入production branch或放宽真实同库政策；source/hash/child/nonce/stdio/出口失败优先不回退，有限runtime-binding owner是否真实执行preflight→一次batch→终态消费、不按改路径伪造新容量。路径发现固定不扫模型/私有数据，计数/timeout/stdout/stderr有界，journal只落正确已封存root/request UUID，无任意journal path/kill API。旧P1及LOCAL01/S2/普通产品行为不变。对实际可复现代码Fatal/Major一次性汇总。
B现有实机证据：正常真实Windows Python→固定wsl.exe→Ubuntu shim→合成SQLite扣1、0模型send、缺child/hash拒绝、超时真实wrapper exit与管道线程、远端PID/birth的观察时点和最终消失事实。准确区分已证明/未证明/只mock；不能把exit0或最终不存活说成即时远端清理/已取退出码，也不能把ENTERED说成功或自然退出。保留fixture reservation未知及/tmp FAILED_RETAINED，不重新收集当前进程状态代替当时证据。

root需要你依据原冻结合同给出最小真实缺口和证据充分性判断：哪些必须修代码/补证才允许生产运行，哪些属于额外的完整OS审计/原合同未要求的退出码细节。原文要求owned身份和退出证明，并不要求整台机器所有系统服务进程普查；若能从固定脚本/Popen/命令记录给出可信实际owned count或保守上界<=64，可计算并说明推导，而不能假称已捕捉所有OS进程。对统一16MiB输出可由现存文件树/日志数量/有界buffer和保守上界核算则直接核算，不另跑实机；区别metadata源读取169MB与输出，不把两者混同。缺真实坏回执场景必须说明P1原有echo验证代码是否字节不变/跨OS是否已验证同路径，以及是否已有预先允许的合成回归可支持其平台无关部分；不能凭猜测宣称坏回执实机已跑。

如果确需下一次实机，给出确切未证明义务、一次集中纠偏方案和需要的新有限child，而不是让人类再批同范围CPU动作。对remote生命周期的缺口优先提出最小owned request/PID-birth证据/有界回收方案，防止扩成进程平台；未经root合同新freeze不要实施新cleanup能力。若原批次实际budget无法证实如实标UNKNOWN/NO_GO，不补写过去测量。

输出review.md、machine receipt、实际命令/stdout/stderr/exit、源码与证据hash、聚焦probe和owned清理。分开工具可接受性与实际P2B readiness，不能一份测试全绿替代实机缺口。精确保留0真实母ledger/模型/媒体等边界，Git作者ljx418 <1173696783@qq.com>，只提交新独审目录，worker_done完整SHA、Fatal/Major/实际已证/未证及建议。保持窗口可见，不签完整产品Gate0/Stage PASS/质量/人签/发布。
