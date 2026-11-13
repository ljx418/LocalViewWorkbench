import json,pathlib
O=pathlib.Path('LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/independent-fixture-result-05')
items=[
('I01','S3InstalledRuntimeFactory → StageRuntimeFactory._write_profile_binding → NativeRuntime.write_native_binding','沿用已有首次profile合成测试/静态hook证据；本轮无新增。','真实default首次绑定/原ledger准入仍缺。','runtime/profile owner'),
('I02','同hook → NativeRuntime.write_warm_binding','沿用warm首次profile测试；本轮无新增。','真实warm关闭/生命周期仍缺。','runtime/profile owner'),
('I03','S3BudgetBindingProvider._load/_check_identity','旧missing/wrong run/candidate/child拒绝保留。','实际生产上下文组合未运行。','binding owner'),
('I04','S3BudgetBindingProvider._check_identity → accepted loader','旧authority/ledger身份拒绝保留。','原ledger/debit/expiry实际准入缺证。','binding/ledger owner'),
('I05','StageRuntimeFactory默认空profile hook','旧S2默认保持证据保留，未复跑。','目标平台默认S2集成回归未证。','S2 runtime owner'),
('I06','S3InstalledRuntimeFactory继承InstalledPackageRuntimeFactory','继承静态证据保留。','真实安装前/安装后/回滚基线缺证。','installer owner'),
('I07','quality_worker.run_worker → QualityPhase.run → ProtocolWriter → ParentSupervisor','旧实际QualityPhase/fake-driver16行与66帧证据保留；本轮clean_terminal仅synthetic fixture与手写1行canonical，不是QualityPhase。','16行真实worker进程/生产driver/parent验证/终态组合及依赖闭包未闭合。','quality worker + supervisor owner'),
('I08','ParentSupervisor.run → _terminate_owned_worker → executor原handle','本轮blocking_callback真实进程phase拒绝、stop、root_retained/resend=false断言通过，counter16 exit=-15。','真实native callback/service后代有界退出未证。','supervisor owner'),
('I09','ParentSupervisor读partial JSONL → deadline → 原handle stop','本轮blocking_persistence真实未闭合帧、stop/root_retained断言通过，counter17 exit=-15。','没有真实持久化后端阻塞/原ledger I/O组合证明；既有Oracle未增强也未缩弱。','supervisor + persistence owner'),
('I10','ProtocolState/history首次截止；ParentSupervisor._fix/_close_history_deadline','本轮history_replay准确MESSAGE_HISTORY_STARTED_REPEATED，counter18；旧H独审关闭保留。','多行生产等待/重发不延长的组合仍缺，真实replay不等于所有history边界。','supervisor owner'),
('I11','ParentSupervisor.start与earliest phase/child/shared drain','本轮实际phase timeout仅1秒；旧exact/oneover与共享drain证据保留。','10800/21600生产配置组合与所有实际child deadline路径未证；无需等待全时长可用受控时钟。','supervisor owner'),
('I12','fixture wire → ParentSupervisor._consume_stdout → decode_message → ProtocolState.accept','本轮9协议负例含early_exit；NaN/count准确原码通过，重放/错序/重复/超长/假身份/未知字段均真实管道拒绝。','不代替所有生产事件/完整16行组合；新caps未放宽。','protocol/supervisor owner'),
('I13','ParentSupervisor.poll/drain/worker exit','本轮early_exit exit0仍准确WORKER_EXITED_WITHOUT_TERMINAL，counter25；blocking partial停止补有限进程证据。','异常非零退出/父失联/真实未决I/O所有组合及保留语义未全证。','supervisor/recovery owner'),
('I14','ParentSupervisor.evidence根预约/归档/退款/重发/下一phase','本轮拒绝场景root_retained与既有C/M1关闭保留；外层fixture-owned-root清除是不同层。','真实cleanup失败保留根预约路径未执行，不能由外层删除推定产品root清理。','cleanup owner'),
('I15','RecoveryEntry.recover','旧不重发、不信文件PID的零动作测试保留。','真实父崩溃恢复/持久归属组合未证。','recovery owner'),
('I16','ParentOriginalEvidence.seal* → verify_selected_root → manifest','原O1/O2独审关闭（最新组件F0M0m1）保留；本轮bad_terminal_reference仅parent canonical边界。','manifest实际被生产controller消费、交付aggregate的调用串接缺证；Windows/reparse独立缺口。','parent originals + coordinator owner'),
('I17','NativeRuntime.bind_video_snapshot_root/video_snapshot_residue','旧空/存在/缺根/读取失败的局部测试索引保留。','真实生产phase残留观察组合、目标平台运行未证。','runtime residue owner'),
('I18','同residue accessor 512/256/nofollow边界','旧exact/oneover/替换/symlink证据保留。','Windows junction/reparse与目标平台真实残留收据未证。','runtime residue owner'),
('I19','aggregate_twelve_keys','旧C关闭与缺cleanup/旧9拒绝保留；本轮没有调用aggregator。','父manifest→实际收据→十二键最终汇总生产入口缺证；不能合成全绿receipts代替。','coordinator/aggregation owner'),
('I20','aggregate_twelve_keys independent_score/a06_isolation要求','旧缺独立评分/隔离拒绝保留；本轮无质量评分。','真实16行质量集合、独立评分原始分值、A06真实隔离均缺。','quality independent scorer + A06 owner'),
('I21','QualityPhase可选progress sink、S2 profile私有hook','旧实际phase66帧/必要回归保留；本轮parent协议进程回归补充。','生产worker组合进程级hook回归未证；不机械复跑257。','quality/profile owner'),
('I22','runner pre-import guard / fixture __main__ boundary','原guard/源hash/有限计划一致；本审0候选import、0fixture、0网络模型GPU服务下载原ledger。','只证明本次离线边界；非真实平台运行许可或A06证明。','offline harness owner'),
('I23','sealed binding/executor source+tool+plan+counter准入','本轮精确argv/11pins/python/binding、13准入28总、session60及持久settled闭合。','并非所有拒绝分支重跑；历史零动作拒绝独审保留，grant已过期额度满。','finite executor owner'),
('I24','原Popen handle birth/poll/wait → persistent counter.finish → finalizer','本轮13 obtained/proven、15..27匹配、未知0、raw13passed/exit0、ownedroot删除闭合。','仅fixture组件运行终态闭合，不能代替native descendant/GPU释放或固定24完整通过。','executor + cleanup owner')]
records=[dict(id=i,production_path=p,delta=d,remaining=g,owner=w,full_fixed_item_status='NOT_PROVEN',stage_pass_claim=False) for i,p,d,g,w in items]
(O/'i01-i24-coverage-delta.json').write_text(json.dumps({'fixed_denominator':24,'product_denominator':12,'new_denominator':False,'fixture_component_verified':True,'full24_pass_claim':False,'items':records},ensure_ascii=False,indent=2)+'\n')
lines=['固定 I01–I24 coverage delta（只读规划，固定24不替换产品12）','', '各完整义务保持 NOT_PROVEN；下表“补证”只指局部生产组件路径。既有独审结论按精确源兼容保留，不把旧测试重记为本轮执行。','', '| ID | 生产owner/路径 | 现有证据与本轮delta | 剩余缺口 |','|---|---|---|---|']
for x in records:lines.append(f"| {x['id']} | {x['owner']}；{x['production_path']} | {x['delta']} | {x['remaining']} |")
(O/'i01-i24-coverage-delta.md').write_text('\n'.join(lines)+'\n')
