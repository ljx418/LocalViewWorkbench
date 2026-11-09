# AUTH-PROGRAM-V1-LOCAL-02 独立权限实现审查

候选：`0cc125f9ba8a66972cf19176a61d52a4b2742bb7`。结论：**Fatal 0 / Major 0 / Minor 1**。权限实现可进入下一次有限 live05 子授权派生；是否发出仍由实际累计账本 reserve 原子裁决。本结论不是 Stage PASS、真实模型验收、人工体验或发布签署。

本审查实例未修改产品、测试或授权文件；仅向本证据目录写入脚本、源码快照与结果。实际运行仅 Python CPU/私有临时 SQLite。未启动服务、浏览器、媒体探测、GPU 或模型，未读取私有媒体。实现者的测试 PASS 数字不作为本结论依据。

## 独立证据

- `final_probe.py` / `final-results.json`：真实 SQLite 私有数据库；16 个并发竞争 2 个动作，恰好 2 个获准；跨四 Stage 预留512，513拒绝；第5个生产零模型启动拒绝；完整子授权零动作终态不消耗有效完整槽；已终态不可重放；样本/生产源码漂移先拒绝、calls不增；工具绑定缺失/漂移拒绝，恢复正确工具后只有1次实际扣额。
- `provider_probe.py` / `provider-results.json`：生产 `OllamaProvider` 方法保持真实，替换外部 HTTP 原语，未发送网络。require-budget且缺child时零send；无效mode零扣额；连接失败调用顺序为 record→debit→send-attempt；证据磁盘写失败零debit、零send。`initial-provider-results.json` 保留此前发现的失败结果，现已修复。
- `terminal_probe.py` / `terminal-results.json`：清理未证明仍写 EXPIRED_NO_GO，并令 active=2；继续发送被拒绝，预算预留保留。
- `routing_probe.py` / `routing-results.json`：control指向Program02而approval不存在时，仍选择Program02验证；缺授权实际拒绝，未回退旧授权。
- `candidate-binding.json`：九个最终审查文件与提交内容逐项SHA核对。START_LVW.cmd工作树CRLF/Git LF仅行尾差异另行明确，规范化逐字节相同；其实际执行文件SHA仍单独保留，子授权按实际文件冻结。

## 审查范围与生产边界

已只读复核 AGENTS11、治理README/roles/anti-false-green、execution-control、执行索引和已批准request/approval。预算采用新母授权，保留历史终态，不拼旧预算。reserve使用BEGIN IMMEDIATE；模型动作在生产payload与HTTP client准备完成后、实际post尝试前扣额并认领完整槽。终态发送权限与保守预留分离。

本轮Harness在任何真实动作前先派生child；固定8动作/1800秒/1次完整槽与冻结packet；按tracked生产路径、prompt/模板、共享视频kernel、harness、Stage Packet以及新增权限工具建立文件SHA；样本每动作重核。START_LVW显式传入child与require-budget，Harness核对nonce匹配API进程环境、PID/birth、独立临时根和监听端口；现有清理流程仍限制原进程所有权。工具发现只读、封存一次，模型发送前逐工具核SHA；browser在推理前保存实际gemma4 tags digest。上述真实进程、工具执行与模型质量仍须后续真实child原始收据证明，CPU审查不代替它们。

正常用户产品路径在未设置开发验证guard时保留原有行为；本轮受控路径必须双变量及owned_env实核。结论仅覆盖本轮统一媒体Harness及权限实现，不声称其他未来Stage/Harness已接入。

## Minor M01：预发送拒绝可保守占用预留

位置：`lvw/backend/app/provider.py` 的 provider_call_started 记录发生在 model_action 之前；`reports/unified-media/authority.py:terminal` 按该event数与SQLite calls对账。

复现条件：首次调用先成功写入started，随后的model_action因样本、源码或工具漂移拒绝。HTTP post不发生、SQLite calls仍0，但原始started计数为1。清理成功时settle(1)与calls0不符，写NO_GO并active=2，完整槽的保守预留继续占用。可通过在provider_probe相同CPU原语环境将model_action替换为抛出ValueError，随后用相同raw event调用terminal复现。

影响：可能过早WAIT_BUDGET；**不会增加可用预算、发送越权推理或伪造PASS**。这是保守额度占用与事件命名精度问题，不阻止下一次有限验证。后续可区分prepared与实际send-attempt并保留防不确定退款原则；不得回写历史失败或直接返还不明额度。

## 已闭环发现

早先发现的样本未重核、零模型生产启动误归CPU类、缺guard静默旁路、终态清理失败仍可发送、live06身份被旧枚举阻断、证据写失败在零send时先认领完整槽，均在最终候选中修复并复核对应边界。原始失败未替换成PASS。
