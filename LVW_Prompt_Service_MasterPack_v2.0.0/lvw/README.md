# LVW R1a 本地单图工作台

当前是 V1 的提前体验切片，不是完整 V1，也不是生产发布包。它提供单图上传、本地 Ollama 分析、观察/推断/未知分层、显式采纳、人工编辑以及 TXT/JSON 导出。

分析前可以选择视觉表达方式和内容处理预设，并填写最多 800 字的附加分析要求。预设包括标准分析、忠实描述、艺术裸体／成人内容、医学与人体结构。附加要求只作为本地模型的分析偏好，不能改变固定 JSON 结构或事实／推断／未知边界；模型自身仍可能拒绝个别输入，此时界面会明确显示 `MODEL_REFUSAL`。

## 开发环境启动

前置：Python 3.12、已安装本项目 `pyproject.toml` 中依赖，以及本机 Ollama `gemma4:26b`。正式运行只监听 `127.0.0.1`，前端不直接连接 Ollama。

```bash
python3 lvw/run_local.py
```

随后打开 `http://127.0.0.1:8765`。停止时在终端按 `Ctrl+C`。

## Windows 双击启动

直接双击项目根目录的 `START_LVW.cmd`。这是纯 ASCII、Windows CRLF 批处理文件，不调用 PowerShell 或绕过执行策略。它会使用本机 `Ubuntu-24.04` WSL，检查 Python，将已安装的 `ollama.exe` 位置交给 LVW，然后在 `http://127.0.0.1:18765` 启动服务并自动打开浏览器。Ollama 或 `gemma4:26b` 暂时不可用时仍会打开工作台；页面的“本地后端服务”面板会显示 API、Ollama、模型可用性和模型装载状态，并提供启动、重置和关闭按钮。

启动器只复用运行时协议为 `lvw.runtime/1` 的兼容实例。若 18765 被旧版 LVW 或其他程序占用，它会依次选择 18766–18775 中的空闲端口，并打开实际选中的地址，避免新版页面连接旧版后端。

页面顶部的“本地后端服务”面板显示 LVW API、Ollama、`gemma4:26b`可用性、模型装载和进程归属。“启动模型服务”只会执行启动器绑定的 `ollama.exe serve`；“重置”和“关闭”仅对本轮 LVW 启动的 Ollama 可用。已由其他程序启动的 Ollama 只显示为“外部服务”，LVW 不会终止它。所有控制均限于 `127.0.0.1`，不下载模型、不访问云服务、不接受前端传入的命令或路径。

页面只允许启动固定的本机 loopback Ollama，不接受用户提供的命令或程序路径，也不会下载模型、访问云服务或修改永久配置。重置和关闭只对本轮由 LVW 启动的 Ollama 生效；若检测到用户自行启动的外部 Ollama，页面只观察其状态，不会终止它。使用完毕后可先在页面关闭本轮 Ollama，再在启动窗口按 `Ctrl+C` 并关闭；启动器随后删除本轮临时媒体。

## 自动体验门禁

离线回归执行 `python3 -m pytest -q lvw/tests`；前端合同执行 `cd lvw/frontend && npm test && npm run typecheck && npm run build`。本机 Ollama 与 LVW 均已启动后，执行 `python3 tools/verify_lvw_experience.py`，它会使用哈希锁定的 `testSource/图片-4.jpg` 驱动公开上传、分析、轮询和结果接口。只有 readiness 精确匹配 `gemma4:26b`、任务成功且观察/中英文/负向词/标签分母完整时才返回 PASS；跳过、模型未就绪或终态失败都返回非零退出码。

需要验证真实页面和服务控制时，在已启动 LVW 的隔离端口执行 `python3 tools/verify_lvw_ui_experience.py --base-url http://127.0.0.1:<端口>`。该门禁通过 headless Chromium 点击页面启动服务、选择固定样本、完成识别、采纳全部结果，再从页面关闭本轮服务；任一页面状态、输出分母或清理动作不成立都会返回非零退出码。

前端依赖只在构建时需要；生产页面已经位于 `frontend/dist/`。重新构建：

```bash
cd lvw/frontend
npm ci --offline --ignore-scripts --no-audit --no-fund
npm run test
npm run typecheck
npm run build
```

## 当前边界

- 图片：JPEG/PNG/WebP，最大 20 MiB、4000 万像素；分析副本最长边 1024。
- 模型端点固定为 `http://127.0.0.1:11434/api/chat`，无云回退。
- 工作稿只保存在当前页面会话；请主动导出。
- 不包含视频、完整修订历史、CLI、便携 Python、安装器或正式 V1 门禁。
