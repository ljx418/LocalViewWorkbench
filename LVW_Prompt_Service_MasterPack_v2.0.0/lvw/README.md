# LVW R1a 本地单图工作台

当前是 V1 的提前体验切片，不是完整 V1，也不是生产发布包。它提供单图上传、本地 Ollama 分析、观察/推断/未知分层、显式采纳、人工编辑以及 TXT/JSON 导出。

## 开发环境启动

前置：Python 3.12、已安装本项目 `pyproject.toml` 中依赖，以及本机 Ollama `gemma4:26b`。正式运行只监听 `127.0.0.1`，前端不直接连接 Ollama。

```bash
python3 lvw/run_local.py
```

随后打开 `http://127.0.0.1:8765`。停止时在终端按 `Ctrl+C`。

## Windows 双击启动

直接双击项目根目录的 `启动_LVW.cmd`。这是普通批处理文件，不调用 PowerShell 或绕过执行策略。它会使用本机 `Ubuntu-24.04` WSL，检查 Python 依赖，复用已运行的本机 Ollama，然后在 `http://127.0.0.1:18765` 启动服务并自动打开浏览器。Ollama 或 `gemma4:26b` 暂时不可用时仍会打开工作台，但只能使用人工编辑与导出，不能执行图片分析。

使用完毕后在启动窗口按 `Ctrl+C`并关闭；启动器随后删除本轮临时媒体。它不会自动启动 Ollama、下载模型或修改永久配置。

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
