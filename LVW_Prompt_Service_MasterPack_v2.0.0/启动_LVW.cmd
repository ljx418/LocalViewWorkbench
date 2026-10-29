@echo off
chcp 65001 >nul
title LVW 本地图像提示词工作台
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:8765"
set "OLLAMA_URL=http://127.0.0.1:11434"
set "RUN_ROOT=%TEMP%\lvw-user-%RANDOM%-%RANDOM%"

echo LVW 本地图像提示词工作台
echo 项目目录：%CD%
echo.

curl.exe -fsS "%APP_URL%/health" >nul 2>&1
if not errorlevel 1 (
  echo 工作台已经运行，正在打开浏览器……
  start "" "%APP_URL%"
  exit /b 0
)

where wsl.exe >nul 2>&1 || goto :no_wsl
wsl.exe -e python3 -c "import fastapi,uvicorn,PIL,httpx" >nul 2>&1 || goto :no_python_deps

curl.exe -fsS "%OLLAMA_URL%/api/version" >nul 2>&1
if errorlevel 1 (
  set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
  if not exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" goto :no_ollama
  echo 正在启动本机 Ollama……
  set "OLLAMA_NO_CLOUD=1"
  start "LVW Ollama" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
  for /l %%I in (1,1,30) do (
    curl.exe -fsS "%OLLAMA_URL%/api/version" >nul 2>&1 && goto :ollama_ready
    timeout /t 1 /nobreak >nul
  )
  goto :ollama_timeout
)

:ollama_ready
curl.exe -fsS "%OLLAMA_URL%/api/tags" 2>nul | findstr /c:"gemma4:26b" >nul || goto :no_model

mkdir "%RUN_ROOT%" >nul 2>&1
for /f "delims=" %%I in ('wsl.exe wslpath -a -u "%CD%"') do set "WSL_ROOT=%%I"
for /f "delims=" %%I in ('wsl.exe wslpath -a -u "%RUN_ROOT%"') do set "WSL_RUN_ROOT=%%I"
if not defined WSL_ROOT goto :path_error
if not defined WSL_RUN_ROOT goto :path_error

echo 正在启动服务，浏览器会自动打开……
start "" /b cmd.exe /d /c ""%~dp0tools\open_lvw_browser.cmd" "%APP_URL%""
start "LVW 服务 - 关闭此窗口即可停止" /wait wsl.exe --cd "%WSL_ROOT%" -e env "LVW_PORT=8765" "LVW_DATA_ROOT=%WSL_RUN_ROOT%" "PYTHONDONTWRITEBYTECODE=1" python3 lvw/run_local.py

rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
echo LVW 服务已停止，本轮临时图片已清理。
echo 如果本次启动器打开了 Ollama，可在系统托盘退出 Ollama。
pause
exit /b 0

:no_wsl
echo 错误：未找到 WSL，请先确认 wsl.exe 可用。
goto :failed
:no_python_deps
echo 错误：WSL Python 缺少 fastapi、uvicorn、Pillow 或 httpx。
goto :failed
:no_ollama
echo 错误：未找到本机 Ollama。
goto :failed
:ollama_timeout
echo 错误：Ollama 启动超时。
goto :failed
:no_model
echo 错误：本机没有 gemma4:26b；启动器不会自动下载模型。
goto :failed
:path_error
echo 错误：无法转换项目或临时目录的 WSL 路径。
:failed
if exist "%RUN_ROOT%" rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
pause
exit /b 1
