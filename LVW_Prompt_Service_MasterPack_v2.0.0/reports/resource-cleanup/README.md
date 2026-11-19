# 资源清理按钮：使用与证据

**最新：独审02剩余第1–8项已做纠偏02，75项定向、229项后端与空载服务关闭实机验证通过，等待独立复核；完整已加载模型链路仍BLOCKED。** 旧卸载方案与旧验证属于历史，不能据其升级当前候选。详见[纠偏决定及13项处置](correction-01/decision.md)。

1. 关闭旧 LVW 启动窗口，再双击原启动图标；刷新网页不会更新已运行的旧 Python 后端。
2. 在页面顶部“本地后端服务”点击“资源清理”。有分析正在运行时先取消，等待资源释放；按钮在切换期间禁用。
3. 根据实际结果继续：`released` 是已核实本轮原模型服务退出且资源范围核对完成；`noop` 是此前原服务已证退出且当前端口缺席的重复清理；`blocked` 是外部/未知归属；`unknown` 是释放尚未确认。后两者都不是清理成功。
4. “再次检查服务”重新读取后端状态。下次分析前先点击“启动模型服务”；人工稿与导出始终保留。

该动作是固定后端脚本逻辑，不执行用户输入的命令，不再向端口发送模型卸载POST，不删除文件或清空数据库，不重启驱动，不结束其他软件。没有 LVW lease 且服务由外部启动时，不会冒认占用归属。Windows 桌面、浏览器或其他软件占用不能由此按钮全部释放；WSL `/proc/meminfo` 数值仅代表运行环境可用内存。

以下为初始候选的历史记录（当前纠偏候选不能沿用旧通过结论）：

实现者：ClaudeCode 首次 429 后按用户明确授权由 Codex 接替；原主干持久化开发仍暂停。候选、派生授权、日志、截图与清理证明均按目录保留，失败不覆盖：

- [实现合同与12项增量义务](packet-01/implementation-spec.md)
- [接替授权](takeover.json)
- [后端22项定向检查](validation-01/check-01/stdout.log)
- [完整后端子树回归](validation-01/check-06/stdout.log)：176项通过；之前缺 PYTHONPATH/工作目录的失败保留在 check-02/check-05。
- [前端11项测试](validation-02/check-01/stdout.log)、[TypeScript与生产构建](validation-02/check-02/stdout.log)
- [首次页面夹具验证](ui-fixture-01/receipt.json)：真实页面/API/生产清理 owner，模型资源为夹具，不能证明真实卸载。
- [真实装载验证受阻](live-01/receipt.json)：本机模型已装，但可用显存约17598MiB，未满足原19047MiB分析准入；零模型调用，原服务已完整关闭。不得将本轮计为真实释放或图片识别通过。
- [有界归属核查](resource-diagnostic-01/receipt.json)：Ollama活动模型为空，GPU compute-app列表为空，未找到可确认为LVW拥有的占用；不推断为空闲整机、不误停未知程序。
- [最终页面夹具验证12项](ui-fixture-02/receipt.json)：包含真实HTTP409提示、失败重试、归属拒绝和人工稿保留。
- [真实Ollama空载页面验证10项](live-noop-02/receipt.json)：真实API、资源采样、页面按钮、重复清理、移动布局与关闭证明；只证明空载安全路径，不能替代已加载模型释放。
- [页面截图](live-noop-02/cleanup-desktop.png)、[移动截图](live-noop-02/cleanup-mobile.png)、[实现状态与RC01–RC12覆盖](implementation-receipt.json)。

这项增量的真实“已装载模型释放→再次图片识别”验证目前仍受资源准入阻塞。独立复核及后续真实空载页面验证另保存在同目录；只有对应实际收据才能提升状态。本记录不宣布完整V1或任何旧Stage PASS，不补签人工体验。

## 纠偏01验证（当前候选）

[实现与证据收据](correction-01/implementation-receipt.json)：43项定向、197项后端、12项前端与生产构建通过；页面夹具9项、真实空载页面7项。所有实际运行零模型调用，原服务退出由nonce/PID/birth匹配证明。临时诊断根明确保留，不递归删除或声称已删除。

[最新页面](correction-01/runs/real-zero-model-01/desktop.png)、[原句柄清理夹具](correction-01/runs/ui-fixture-01/desktop.png)。独审复核尚未完成；真实已装载模型关闭、重新启动和随后固定图片识别仍未执行，不宣布完整机器验收通过。

## 纠偏02（当前待复核）

[8项剩余发现处置](correction-02/decision.md)、[实现与机器结果](correction-02/implementation-receipt.json)。源候选679803cf的生产/验证器字节与实机候选312e3a96一致，后来只补充两项边界测试。

75项定向、229项后端通过；前端12项及构建按字节一致规则复用。夹具9项、真实空载服务关闭7项通过，原进程退出与端口连接拒绝均已证明，零模型调用。[实机截图](correction-02/runs/real-zero-model-01/desktop.png)。仍未执行真实已加载模型释放、重启与图片识别，不宣布完整机器验收或人工签署。
