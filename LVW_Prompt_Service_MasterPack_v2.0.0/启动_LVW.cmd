@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title LVW 本地图像提示词工作台
cd /d "%~dp0"

set "WSL_DISTRO=Ubuntu-24.04"
set "APP_PORT=18765"
set "APP_URL=http://127.0.0.1:%APP_PORT%"
set "OLLAMA_URL=http://127.0.0.1:11434"
set "RUN_ROOT=%TEMP%\lvw-user-%RANDOM%-%RANDOM%"

echo LVW 本地图像提示词工作台
echo 项目目录：%CD%
echo.

curl.exe -fsS --max-time 2 "%APP_URL%/health" 2>nul | findstr /c:"R1a" >nul
if not errorlevel 1 (
  echo 工作台已经运行，正在打开浏览器……
  start "" "%APP_URL%"
  exit /b 0
)

where wsl.exe >nul 2>&1 || goto :no_wsl
wsl.exe -d "%WSL_DISTRO%" -e true >nul 2>&1 || goto :no_distro
wsl.exe -d "%WSL_DISTRO%" -e python3 -c "import fastapi,uvicorn,PIL,httpx" >nul 2>&1 || goto :no_python_deps

curl.exe -sS --max-time 2 "%APP_URL%/" >nul 2>&1
if not errorlevel 1 goto :port_in_use

curl.exe -fsS "%OLLAMA_URL%/api/version" >nul 2>&1
if errorlevel 1 goto :ollama_unavailable

:ollama_ready
curl.exe -fsS "%OLLAMA_URL%/api/tags" 2>nul | findstr /c:"gemma4:26b" >nul || goto :model_unavailable

:start_lvw
mkdir "%RUN_ROOT%" >nul 2>&1
for /f "delims=" %%I in ('wsl.exe -d "%WSL_DISTRO%" -e wslpath -a -u "%CD%"') do set "WSL_ROOT=%%I"
for /f "delims=" %%I in ('wsl.exe -d "%WSL_DISTRO%" -e wslpath -a -u "%RUN_ROOT%"') do set "WSL_RUN_ROOT=%%I"
if not defined WSL_ROOT goto :path_error
if not defined WSL_RUN_ROOT goto :path_error

echo 正在启动服务，浏览器会自动打开……
echo 如果浏览器没有自动打开，请访问 %APP_URL%
start "" /b "%~dp0tools\open_lvw_browser.cmd" "%APP_URL%"
wsl.exe -d "%WSL_DISTRO%" --cd "%WSL_ROOT%" -e env "LVW_PORT=%APP_PORT%" "LVW_DATA_ROOT=%WSL_RUN_ROOT%" "PYTHONDONTWRITEBYTECODE=1" python3 lvw/run_local.py
set "LVW_EXIT=%ERRORLEVEL%"

rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
echo LVW 服务已停止，本轮临时图片已清理。
if not "%LVW_EXIT%"=="0" echo 错误：LVW 服务异常退出，代码 %LVW_EXIT%。
pause
exit /b %LVW_EXIT%

:no_wsl
echo 错误：未找到 WSL，请先确认 wsl.exe 可用。
goto :failed
:no_distro
echo 错误：未找到可用的 WSL 发行版 %WSL_DISTRO%。
goto :failed
:no_python_deps
echo 错误：%WSL_DISTRO% 的 Python 缺少 fastapi、uvicorn、Pillow 或 httpx。
goto :failed
:ollama_unavailable
echo 警告：Ollama 未运行，将以无模型模式打开 LVW。
goto :start_lvw
:model_unavailable
echo 警告：当前 Ollama 不可见 gemma4:26b，将以无模型模式打开 LVW。
goto :start_lvw
:path_error
echo 错误：无法转换项目或临时目录的 WSL 路径。
goto :failed
:port_in_use
echo 错误：端口 %APP_PORT% 已被其他程序占用，LVW 未启动。
:failed
if exist "%RUN_ROOT%" rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
pause
exit /b 1
