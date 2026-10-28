# V0-S1 checkpoint-01 独立复审

- 审查角色：隔离独立审查者
- 审查模式：仅离线读取 Git 对象与封存证据；未启动、探测或连接 ComfyUI、Ollama、GPU、端口、网络或真实媒体
- Product candidate：`1d48142b95466954ca4da264fa06762abf1522f2`
- Harness candidate：`14bb63b83b74f6604698a08ecc2e17557dd4031c`
- Authorization commit：`b0cbb073e62f23adcdfa6d84f58f66053b38b043`
- Raw evidence commit：`c89667da32dde26425cf64a73ccca84dfea5d18d`
- Root terminal seal：`a4eba33cf890e6271d6fb2e479dd9c021f7fbf63`

## 结论

**Fatal 0 / Major 2 / Minor 0**

**原 checkpoint-01 建议：NO_GO。** 五项产品 Oracle 的非隐私机器事实均可独立复算为 `PASS_CANDIDATE_FOR_REVIEW`，但封存证据不满足授权中的隐私最小化条件，且隐私扫描器把合法 URL 误判为盘符路径。两者必须分开看待：产品行为证据可信，不等于这次 checkpoint 的证据包合规。

本报告不把 `PASS_CANDIDATE_FOR_REVIEW` 升为 `PASS`，不宣布 V0-S1 Stage PASS，也不授权复跑。原授权已经 `EXPIRED_NO_GO`，历史 `CASE_PRIVACY_VIOLATION` 必须保留。

## Findings

### M-01 — Major — 封存的 Comfy 日志包含授权禁止的 traceback 过采集

- **位置：** `reports/v0-s1/stage-checkpoint-live-01/run-summary.json` 的 Comfy service-log 字段；对应生成逻辑位于 checkpoint harness 的 service-log 收集与 `_privacy_scan`。
- **触发：** 对封存 summary 做结构性隐私扫描。
- **预期：** 授权只允许最小化证据，并明确禁止 traceback、私有绝对路径、秘密、原始命令行和无关诊断。
- **实际：** Comfy 日志包含 5 个 traceback 标记。路径内容已经被占位符脱敏；未检出真实 Windows/WSL 私有绝对路径、秘密赋值、长 Base64 token、原始命令行或 `current_inputs`。因此这是**真实的证据过采集**，但未发现真实私有信息泄漏。
- **影响：** 原 checkpoint 的隐私门禁不合格；即使产品 Oracle 全部成立，也不能把本次终态改成 READY 或 PASS。严重度为 Major 而非 Fatal，因为封存内容未发现可识别私有路径、秘密或可逆凭据。
- **证据：** 边界感知的路径形态扫描为 0；Comfy 日志有 57 个 Windows 路径脱敏占位符和 5 个 traceback 标记。完整离线 verifier 在未改动证据时 fail-closed。
- **复现：** 递归遍历 summary 字符串叶子，只统计 `traceback` 标记、脱敏占位符、边界感知路径形态与秘密形态；禁止输出字符串值或解码任何 token。

### M-02 — Major — 隐私扫描器将 URL scheme 尾部误判为 Windows 盘符路径

- **位置：** `reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py` 的 `_privacy_scan` Windows-path 条件。
- **触发：** 对含合法 loopback URL 的 Ollama service-log 调用 `_privacy_scan`。
- **预期：** 盘符路径扫描应要求盘符前存在词法边界，且不能把 `scheme://` 的单字母尾部识别为盘符根形态。
- **实际：** scanner 使用无左边界的单字母加冒号/斜杠模式。Ollama 日志的 21 个命中全部来自 URL scheme 尾部，真正的盘符路径形态为 0；Comfy 日志另有 1 个同类 URL 假命中。生产终态记录的首个 `CASE_PRIVACY_VIOLATION` 因而是扫描器假阳性，而不是 Ollama 日志泄漏了私有路径。
- **影响：** 错误分类消耗了一次性终态并使 verifier 在检查产品事实前退出。它是 fail-closed，不构成假绿，但会把可信产品事实错误归类为隐私路径泄漏，且不能掩盖 M-01 的真实过采集。
- **证据：** 原 scanner 命中计数与加入左边界后的盘符形态计数分别为 Ollama `21/0`、Comfy `1/0`；原始日志仍只显示 loopback 网络事实。
- **复现：** 比较原条件与带“不允许前一字符为字母”的盘符路径条件，只输出两类命中数量，不输出任何匹配文本。

## 独立复算事实

### 权限、候选与生命周期绑定

- Product candidate 是 harness candidate 的祖先。提交链为 request `516673c...` → authorization `b0cbb07...` → raw evidence `c89667d...` → terminal seal `a4eba33...`。
- Request blob SHA-256 独立复算为 `c6fac63998b123071f3ac956cc7f6d42e64932b56a3dc094289284b9256e4605`；authorization commit 中的授权 blob为 `cdbfb656b4eb346df2e3a4a833e47bae7b2408e5507d08cfe8169503d2b6ee93`，均与 summary authority 绑定一致。
- Request 与授权逐项一致绑定 product candidate、harness candidate、harness/lifecycle SHA、run ID、evidence slot、样本 SHA、模型 digest、固定分母、target aliases 和完整预算。
- 八个生产 artifact 均从 product candidate Git blob 独立取回；blob SHA、当前文件字节与 summary 的八个 SHA 全部一致。Harness blob/当前文件 SHA 为 `9b1b4ec4d585fabd3b041b992aeccd59a064f26a9cf93c08cf97ea62b90cdb41`；lifecycle blob/当前文件 SHA 为 `94953202138267ca988818a5ba75704d845c15e288fb406d8f7af21d1af4af52`。
- Root seal 未改写 `stage-checkpoint-live-01` 的任何字节；授权被封存为终态过期且 evidence commit 指向 raw evidence。

### Manifest 与固定分母

- `run-summary.json` SHA-256 为 `2e77a854668ce083408c7b6d8eca1b3b6b7a973f2484a51a2c8dacd92bffeffe`；`implementation-receipt.json` 为 `4258b23ba6bd54037b7165ddcff89400cb099ffbcc77ab6c58abbc8f8b3b4ca9`。两者与 artifact manifest 完全一致；manifest 自身 SHA-256 为 `40295b2862b8e1ca876ed2fc878fb69e359e9d36a573db97adca8ba9a9d60487`。
- V0-A01/A03/A04/A05/A08 排序、换行后的 SHA-256 仍为 `4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5`，分母未缩小。
- Packet payload manifest 和根 `MANIFEST.sha256` 均通过。五项状态只可称为 `PASS_CANDIDATE_FOR_REVIEW`；receipt 因整体隐私 NO_GO 将五项 gate 计为 blocked，不得改写为 PASS。

### 24 个 public `/prompt` / `/history` trace 与五项 Oracle

- 独立遍历共得到 24 个非空且互异的 prompt ID；submission sequence 精确为 1..24。Comfy 日志也有 24 个 `got prompt` 事件。图 SHA 均由封存输入重新构造并匹配，不依赖 summary 的状态标签。
- **V0-A01：** public graph 绑定 `LVWControlledImageInput` → `LVWImagePromptBridge`，raw 与 `lvw.prompt/1` suggestion 均通过语义 Oracle。metadata 的 source hash 等于授权样本 SHA，输出尺寸不超过 1024，且受控预处理事实可复算。
- **V0-A03：** 三个 public trace 覆盖 preview、JSON export、TXT export；四个输出字段 hash、JSON schema、TXT 头、磁盘回读 hash 全部匹配，模型调用计数前后均为 1，source raw hash 连接 A01。
- **V0-A04：** 在 owned Ollama 已停止且 listener 终态缺席后，五个成功 trace 覆盖 20,000 字 draft 的 preview、两种 clipboard copy 和两种 export。JSON/TXT 回读 hash 匹配；确定性写失败返回 `DISK_FULL`，失败目标保持目录，owned 临时文件计数为 0。生产 owner 使用真实系统 clipboard adapter，clipboard 不可用时会 fail-closed；本次两次 public copy 均成功。
- **V0-A05：** 三步 setup 为 start/success/adopt，baseline draft epoch 为 1。非法 JSON、明确拒绝、timeout、OOM、stale token 五组负向路径都保持 draft hash 与 epoch，`retry_count=0` 且自动重试总数为 0；对应失败状态或 error code 均匹配 Oracle。
- **V0-A08：** public empty export 通过 schema，contract tuple 为 manual / null run / not requested / null suggestion；输入键只含七个 manual draft 字段，不含 approval 或 content-note 权限字段，模型调用前后均为 1。
- 将 `service_logs` 在内存中排除后（不改磁盘证据）执行同一 `verify_machine_facts`，全部 identity、authority、预算、24 trace、五项 Oracle 和 cleanup 复算通过。这一诊断只隔离隐私字段，用于证明产品事实与隐私失败相互独立。

### 模型、网络、GPU 与预算

- Observed：image `1/1`、model `1/1`、Comfy start `1/1`、Ollama start `1/1`、public submissions `24/26`；browser、download、cloud 和 external cost 均为 0。
- Preflight GPU 为 3,816 MiB（阈值 4,096），目标进程和 listener 均为 0；image/runtime 峰值分别为 4,207/4,169 MiB，均低于 23,552 MiB。
- No-cloud 为 true，5 个不少于 10 秒窗口的样本全部为 0 nonloopback，两个 runtime guard 也为 0。日志保留 loopback 事实，未发现非 loopback 连接。
- 精确本地模型为 `gemma4:26b`，匹配数 1，digest 与授权一致。模型 ledger 仅 1 次 chat；raw 日志与结构化 ledger 均为 chat 200 一次、generate 200 两次、ps 200 一次。每次 cleanup HTTP 200，terminal `/api/ps` 模型数为 0。

### Target integrity 与清理

- 六个 target alias 的完整 pre/post map 相等，包含 prompt-assistant tree 的存在性、文件计数与 tree hash。
- 两个 owned listener 都具备初始 lineage、终态 lineage re-proven、stop requested 和 terminal absent；两个 wrapper 均 `exited=true`。
- Cleanup failures 为空、最终 listener 为 0、run temp 已移除、target integrity PASS，独立 derived cleanup 为 true。运行内 post-cleanup snapshot 同时记录 listener 0、目标进程 0、run temp absent。

## 产品行为与证据隐私的分别结论

- **产品行为：** 五项机器事实可独立复算为 `PASS_CANDIDATE_FOR_REVIEW`，未发现 product candidate 的功能性 Major/Fatal，也未发现预算、网络、GPU、模型、target integrity 或 owned cleanup 假绿。
- **证据隐私：** 未发现真实私有绝对路径、秘密或可逆 token 泄漏；但 traceback 的封存违反最小化合同，且 URL/path scanner 存在严重假阳性。因此原 checkpoint 仍为 NO_GO。
- **是否需要重新 live：** 默认**不需要且当前禁止**。修正 scanner、将日志转换为最小化计数/结构事实、补充离线测试和重新独立审查可以离线完成；不得改写历史 raw evidence。只有未来门禁明确要求“同一新运行必须生成完全合规的原始隐私证据”时，才需要新的逐次授权和新 evidence slot，不能复用本授权。
- **V0-Min 使用边界：** 在项目负责人已经明确授权目标收缩的前提下，root 可以把本报告中经独立复算的、非泄漏结构化机器事实作为 V0-Min 的输入依据；必须排除 raw service-log 内容、保留 checkpoint-01 的历史 NO_GO、说明这些事实仍只是 candidate evidence，并由新冻结的 V0-Min 分母/合同和正式 gate decision 决定是否足够。不能据此追认原五项为 V0-S1 PASS。

## 离线复现与测试

以下均为只读、无外部动作的离线检查：

```text
git show / git diff-tree / git merge-base：提交父子、blob identity、历史未改写
sha256sum：request/auth/artifact/manifest/candidate blob 复算
checkpoint.py --verify-evidence reports/v0-s1/stage-checkpoint-live-01
内存排除 service_logs 后调用 verify_machine_facts：隔离产品事实与隐私失败
python3 -B -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py'
packet PAYLOAD_MANIFEST.sha256 与根 MANIFEST.sha256 校验
结构性隐私扫描：只输出类别与计数，不输出或解码匹配值
```

结果：完整离线测试 **97/97 PASS**；原 evidence verifier 如实返回 `CASE_PRIVACY_VIOLATION`；隔离 service-log 字段后的机器事实复算通过五项 candidate Oracle。测试通过不覆盖上述两项 Major，也不改变授权或 Stage 状态。
