@echo off
setlocal EnableExtensions
title LVW Local Prompt Workbench
cd /d "%~dp0"

set "WSL_DISTRO=Ubuntu-24.04"
set "APP_PORT="
set "APP_URL="
set "EXISTING_LVW="
set "OLLAMA_URL=http://127.0.0.1:11434"
set "RUN_ROOT=%TEMP%\lvw-user-%RANDOM%-%RANDOM%"
set "OLLAMA_EXE_WIN="
set "WSL_OLLAMA_EXE="
for /f "delims=" %%I in ('where ollama.exe 2^>nul') do if not defined OLLAMA_EXE_WIN set "OLLAMA_EXE_WIN=%%I"

echo LVW Local Prompt Workbench
echo Project directory: %CD%
echo.

for /l %%P in (18765,1,18775) do call :probe_port %%P
if not defined APP_PORT goto :no_port
set "APP_URL=http://127.0.0.1:%APP_PORT%"
if defined EXISTING_LVW goto :already_running

where wsl.exe >nul 2>&1 || goto :no_wsl
wsl.exe -d %WSL_DISTRO% -e python3 --version >nul 2>&1 || goto :no_python

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
if /i not "%LVW_NO_BROWSER%"=="1" start "" /b "%ComSpec%" /d /c call "%~dp0tools\open_lvw_browser.cmd" "%APP_URL%"
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
echo INFO: Ollama is not running yet. Start it from the LVW service panel.
goto :start_lvw
:model_unavailable
echo WARNING: gemma4:26b is unavailable. LVW will open without model analysis.
goto :start_lvw
:path_error
echo ERROR: Failed to convert the project or temporary path for WSL.
goto :failed
:already_running
echo A compatible LVW is already running on port %APP_PORT%.
echo Opening the browser...
if /i not "%LVW_NO_BROWSER%"=="1" start "" "%APP_URL%"
exit /b 0
:no_port
echo ERROR: Ports 18765 through 18775 are already in use.
echo Close an older LVW window or free one of those ports, then try again.
:failed
if exist "%RUN_ROOT%" rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo.
pause
exit /b 1

:probe_port
if defined APP_PORT exit /b 0
set "CANDIDATE_URL=http://127.0.0.1:%~1"
curl.exe -fsS --max-time 1 "%CANDIDATE_URL%/api/v1/runtime/status" 2>nul | findstr /c:"lvw.runtime/1" >nul
if not errorlevel 1 (
  set "APP_PORT=%~1"
  set "EXISTING_LVW=1"
  exit /b 0
)
curl.exe -sS --max-time 1 "%CANDIDATE_URL%/" >nul 2>&1
if errorlevel 1 set "APP_PORT=%~1"
exit /b 0
