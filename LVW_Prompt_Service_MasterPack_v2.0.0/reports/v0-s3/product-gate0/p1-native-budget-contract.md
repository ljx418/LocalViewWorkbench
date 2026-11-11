# S3 原生生产扣额接线合同 1.0（Codex冻结，仅离线P1）

产品目标、V0-A01..12及正式quality-set.frozen.json不变。此合同只准入S3-P1离线实现，不授予完整产品Gate0或任何真实运行。事实依据fact-audit-01/source-index.json、ledger-compatibility.md及budget-proposal.json。旧S2仍7/8，批准handoff允许本S3 toward V1，旧已签功能不重构。

## 总体架构裁决

一个S3父运行内按固定顺序分原生累计子运行与质量/安装子运行，同一候选、样本/环境seal、父ID；首段失败不启动后段，候选修改必须新父运行，不拼接旧正例。现有ledger没有共享parent full计数API，不修改预算政策：两段如均为完整子运行，均full=True，各在首动作消耗一轮，明确共2轮有效完整账本额度；Stage集中验收仍是一轮父流程。103原生上限与34质量+5冷启动+尚待绑定rollback/格式/故障成本不能塞单child128。最终第二child有限cap及时间待后续实际绑定，不在本P1虚报已预留。保留母授权1024/24/172800s、每child128/21600s；原账面29/8/1506只是快照，正式reserve时原子复核。

账本唯一权威是原live15已绑定的program02.sqlite，不从worktree ROOT猜新库，不复制/重建/清零。local_program_authority.py的预算/事务/扣额/结算政策不改。S3原生chat和preload均在实际发送之前由同一authority扣额；图一次、默认视频4帧4次、每次warm preload另扣一次。cleanup/unload/status无模型扣额但受有限请求/时间控制。不能在submit一次扣额替代逐帧，也不能从HTTP200或日志事件数推算实际扣额。

## 跨OS内部协议与所有权

新增bridge program_budget.py作有限客户端；新增tools/v0_s3_budget_authority.py为WSL权威shim。冻结内部函数authorize_model_action(action_kind,payload,*,binding=None)；action_kind仅chat/preload，payload摘要为实际发送体字节SHA256（不要在收据存明文图像或完整base64）。客户端有明确S3模式要求：活动S3 profile或LVW_S3_BUDGET_REQUIRED=1时缺配置/过期/错绑定必须拒绝发送；普通无S3运行保留原使用行为，不给日常用户加授权UI。

Windows通过固定受控wsl.exe -d <冻结发行版> --exec <冻结WSL Python> -I -B <冻结shim绝对路径>传输，不使用Shell、拼接命令或任意可执行argv接口。不新增HTTP控制服务或云回退。Linux离线测试/已声明WSL harness可用同一shim的直接函数或固定local-subprocess分支；所有分支调用同一authority，不复制预算规则。实际wsl.exe/Python/发行版/路径和hash在后续有限运行binding才发现封存，本P1不读取宿主或启动探测。

binding配置由运行协调器生成在owned临时根，不写永久配置；客户端通过LVW_S3_BUDGET_BINDING及LVW_S3_BUDGET_BINDING_SHA256读取并复算。schema必须列program/approval hash、run_id/stage_id、candidate SHA、child真实路径/hash、原权威ledger路径、execution bindings路径/hash、authority root/shim/Python/wsl executable角色和digest、expires、固定transport mode/distribution。跨OS Windows可读binding路径与WSL child路径需明确不同字段并相互封存，不能假设Linux字符串能被Windows pathlib读取。缺失/未知字段或替代路径拒绝，不允许由模型/媒体输入决定这些字段。执行配置是内部受控能力，不对产品API暴露任意命令或任意文件读取。

权威shim只接受有界JSON stdin：request_id(UUID)、action_kind、payload_sha256、model及binding身份；核对child/approval/candidate/ledger/执行bindings和期限，再调用同一local_program_authority.model_action(child_path)。当从worktree导入authority时必须显式解决其ROOT及默认LEDGER派生：加载正确authority_root的模块并验证代码hash，不临时改写全局预算规则、默认库或复制库。允许测试fixture root的同合同分支但不能出现在真实S3配置。路径/根身份必须与父运行seal一致。

成功回执DEBITED包含request_id、action_kind、payload_sha256、run_id/child hash及权威身份，stdout只一份有界JSON，stderr诊断。native客户端必须核对成功/echo/hash和进程真实成功退出后才发送。拒绝、超时、输出超限、坏JSON、错nonce/echo、桥接异常均fail-closed，0模型send，不自动重试/重连/换child；扣额后回执丢失也不能refund或补发，保留已扣/未知发送证据与reservation，由明确终态处置。每调用新request_id；禁止自动重放，避免重复费用。该stdio协议信任冻结owned进程/工具，不宣称抵御本机同权限主动篡改者，不建密钥/通用调度平台。

客户端stdout/stderr/时间均有界，只停自己的Popen及读线程，证明reap；绑定后使用固定超时且受child剩余wall约束。不要因已读DEBITED但进程报错而发送，保留真实exit/error。签名和schema在实现收据详细列明，不改变以上语义。

## 精确修改面与发送接线

新增：tools/v0_s3_budget_authority.py、bridge/program_budget.py；测试tools/test_v0_s3_budget_authority.py、RuntimePatch/tests/test_s3_program_budget.py。
可最小修改：bridge/core.py默认chat发送边界、bridge/video_transport.py interruptible chat发送边界；tools/v0_s2_runtime.py preload发送边界及S3 profile生成；bridge/benchmark.py、bridge/video_evidence.py仅新增精确COMPLETE03/S3 scope绑定验证分支。其它业务提示词、输出schema、前端、decoder、预算policy、旧S2 stage_checkpoint、manifest/合同/计划/准备工具不改。

新profile scope为V0_S3_NATIVE_CHECKPOINT、V0_S3_WARM_BENCHMARK，program_authorization_id=AUTH-PROGRAM-V1-COMPLETE-03，保留旧LOCAL01/S2分支原语义；新分支必须绑定child/hash/candidate/model digest/owner PID birth/实际expiry<=child及母授权per-child21600s，不能只比较program字符串。max_runs<=64、每视频最多4attempt、warm20请求与10+10分母不扩大。新增runtime参数用显式keyword/可选受控context，不全局放松7200s旧分支。原profile旧用例保持。

送前扣额不可双扣：一个实际chat只走一个适配入口；若core默认与interruptible共享下层，明确唯一owner以避免2次；在新S3模式里preload也同权威。取消/故障发生在发送后仍保留已扣动作；文件负例/人工编译/格式切换不扣，不新增视觉调用。测试驱动实际生产owner/发送边界，不能只测helper或常量。

## 离线验收固定义务

合成authority root/approval/SQLite，不访问或写原真实ledger。并发/exact/one-over cap、过期/错child/错源码/错tool binding拒绝，永不新建替代库绕上限，母授权无效failclosed。真实同fixture sqlite事务调用model_action，模拟native→shim正例与拒绝，证明发送前计数已增加；默认图1次、四帧4次、preload1次，不双扣。新scope缺/坏配置/桥接返回错/超时/失去回执均0send，真实owned子进程超时和reap；stdout错误链须同时核exit和error，避免刚修过的exit0假绿。

旧S2 profile与生产边界回归保持，预算/候选/调用日志脱敏且不存图像base64。mock仅代替最终网络及Windows执行环境，不代替事务真实性或把offline测试说成已跨Windows接线运行。没有真实工具/GPU/服务/网络/媒体/原preview动作，不reserve真实child、不消耗完整验收。一次定向组合自检后READY_FOR_REVIEW，独立实例审查；禁止本P1宣布完整Gate0/Stage PASS。

root后续P2再冻结薄协调器、包target-host factory、断外联与尝试记录、exact原workflow/质量raw driver及有限动作时间。未补齐这些前不执行真实S3，也不因本P1通过虚报六正式子项完成。实现收据与风险新写reports/v0-s3/product-gate0/implementation-p1/，旧证据只读。两次同路线无进展交接，不无限尝试。Git作者ljx418 <1173696783@qq.com>。
