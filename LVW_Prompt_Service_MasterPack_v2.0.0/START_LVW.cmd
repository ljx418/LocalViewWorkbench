@echo off
setlocal EnableExtensions
title LVW Local Prompt Workbench
cd /d "%~dp0"

set "WSL_DISTRO=Ubuntu-24.04"
set "APP_PORT=18765"
set "APP_URL=http://127.0.0.1:%APP_PORT%"
set "OLLAMA_URL=http://127.0.0.1:11434"
set "RUN_ROOT=%TEMP%\lvw-user-%RANDOM%-%RANDOM%"
set "OLLAMA_EXE_WIN="
set "WSL_OLLAMA_EXE="
for /f "delims=" %%I in ('where ollama.exe 2^>nul') do if not defined OLLAMA_EXE_WIN set "OLLAMA_EXE_WIN=%%I"

echo LVW Local Prompt Workbench
echo Project directory: %CD%
echo.

curl.exe -fsS --max-time 2 "%APP_URL%/health" 2>nul | findstr /c:"R1a" >nul
if not errorlevel 1 (
  echo LVW is already running. Opening the browser...
  start "" "%APP_URL%"
  exit /b 0
)

where wsl.exe >nul 2>&1 || goto :no_wsl
wsl.exe -d %WSL_DISTRO% -e python3 --version >nul 2>&1 || goto :no_python

curl.exe -sS --max-time 2 "%APP_URL%/" >nul 2>&1
if not errorlevel 1 goto :port_in_use

curl.exe -fsS --max-time 2 "%OLLAMA_URL%/api/version" >nul 2>&1
if errorlevel 1 goto :ollama_unavailable

:ollama_ready
curl.exe -fsS --max-time 2 "%OLLAMA_URL%/api/tags" 2>nul | findstr /c:"gemma4:26b" >nul || goto :model_unavailable

:start_lvw
mkdir "%RUN_ROOT%" >nul 2>&1
for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u %CD%') do set "WSL_ROOT=%%I"
for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u %RUN_ROOT%') do set "WSL_RUN_ROOT=%%I"
if defined OLLAMA_EXE_WIN for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u %OLLAMA_EXE_WIN%') do set "WSL_OLLAMA_EXE=%%I"
if not defined WSL_ROOT goto :path_error
if not defined WSL_RUN_ROOT goto :path_error

echo Starting LVW. The browser will open automatically.
echo If it does not open, visit %APP_URL%
start "" /b "%ComSpec%" /d /c call "%~dp0tools\open_lvw_browser.cmd" "%APP_URL%"
wsl.exe -d %WSL_DISTRO% --cd %WSL_ROOT% -e env LVW_PORT=%APP_PORT% LVW_DATA_ROOT=%WSL_RUN_ROOT% LVW_OLLAMA_EXE=%WSL_OLLAMA_EXE% PYTHONDONTWRITEBYTECODE=1 python3 lvw/run_local.py
set "LVW_EXIT=%ERRORLEVEL%"

rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
echo LVW stopped. Temporary images from this run were removed.
if not "%LVW_EXIT%"=="0" echo ERROR: LVW exited with code %LVW_EXIT%.
pause
exit /b %LVW_EXIT%

:no_wsl
echo ERROR: wsl.exe was not found.
goto :failed
:no_python
echo ERROR: Python in %WSL_DISTRO% is unavailable.
goto :failed
:ollama_unavailable
echo WARNING: Ollama is not running. LVW will open without model analysis.
goto :start_lvw
:model_unavailable
echo WARNING: gemma4:26b is unavailable. LVW will open without model analysis.
goto :start_lvw
:path_error
echo ERROR: Failed to convert the project or temporary path for WSL.
goto :failed
:port_in_use
echo ERROR: Port %APP_PORT% is already used by another application.
:failed
if exist "%RUN_ROOT%" rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
pause
exit /b 1
