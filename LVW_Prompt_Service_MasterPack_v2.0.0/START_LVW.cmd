@echo off
setlocal EnableExtensions
title LVW Unified Local Workbench
cd /d "%~dp0"
set "WSL_DISTRO=Ubuntu-24.04"
set "APP_PORT="
set "EXISTING_LVW="
set "EXPECTED_BUILD="
set "OLLAMA_EXE_WIN="
set "WSL_OLLAMA_EXE="
set "RUN_ROOT=%TEMP%\lvw-user-%RANDOM%-%RANDOM%"
where wsl.exe >nul 2>&1 || goto :no_wsl
for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u "%CD%"') do set "WSL_ROOT=%%I"
if not defined WSL_ROOT goto :path_error
for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% --cd "%WSL_ROOT%" -e python3 -B lvw/print_build_id.py') do set "EXPECTED_BUILD=%%I"
if not defined EXPECTED_BUILD goto :no_python
if defined LVW_PORT_OVERRIDE goto :override
for /l %%P in (18765,1,18775) do call :probe_port %%P
goto :selected
:override
for /l %%P in (18765,1,18785) do if "%LVW_PORT_OVERRIDE%"=="%%P" call :probe_port %%P
:selected
if not defined APP_PORT goto :no_port
set "APP_URL=http://127.0.0.1:%APP_PORT%"
if defined EXISTING_LVW goto :already_running
for /f "delims=" %%I in ('where ollama.exe 2^>nul') do if not defined OLLAMA_EXE_WIN set "OLLAMA_EXE_WIN=%%I"
mkdir "%RUN_ROOT%" >nul 2>&1
for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u "%RUN_ROOT%"') do set "WSL_RUN_ROOT=%%I"
if not defined WSL_RUN_ROOT goto :path_error
if defined OLLAMA_EXE_WIN for /f "delims=" %%I in ('wsl.exe -d %WSL_DISTRO% -e wslpath -a -u "%OLLAMA_EXE_WIN%"') do set "WSL_OLLAMA_EXE=%%I"
echo LVW Unified Local Workbench
echo Project directory: %CD%
echo Opening %APP_URL%
echo Start the model from the service panel. Keep this window open.
if /i not "%LVW_NO_BROWSER%"=="1" start "" /b "%ComSpec%" /d /c call "%~dp0tools\open_lvw_browser.cmd" "%APP_URL%"
wsl.exe -d %WSL_DISTRO% --cd "%WSL_ROOT%" -e env LVW_PORT=%APP_PORT% "LVW_DATA_ROOT=%WSL_RUN_ROOT%" "LVW_OLLAMA_EXE=%WSL_OLLAMA_EXE%" "LVW_LAUNCH_TOKEN=%LVW_LAUNCH_TOKEN%" "LVW_PROVIDER_LEDGER=%WSL_RUN_ROOT%/provider.jsonl" "LVW_AUTHORIZATION_CHILD=%LVW_AUTHORIZATION_CHILD%" "LVW_REQUIRE_BUDGET=%LVW_REQUIRE_BUDGET%" PYTHONDONTWRITEBYTECODE=1 python3 -B lvw/run_local.py
set "LVW_EXIT=%ERRORLEVEL%"
rmdir /s /q "%RUN_ROOT%" >nul 2>&1
echo LVW stopped. Run-owned temporary files were removed.
if /i not "%LVW_NO_PAUSE%"=="1" pause
exit /b %LVW_EXIT%
:already_running
if /i not "%LVW_NO_BROWSER%"=="1" start "" "%APP_URL%"
exit /b 0
:no_wsl
echo ERROR: wsl.exe was not found.
goto :failed
:no_python
echo ERROR: Python or the local project build is unavailable.
goto :failed
:path_error
echo ERROR: Failed to convert the local project path.
goto :failed
:no_port
echo ERROR: No free port. An older or incompatible LVW will not be reused.
:failed
if /i not "%LVW_NO_PAUSE%"=="1" pause
exit /b 1
:probe_port
if defined APP_PORT exit /b 0
curl.exe -fsS --max-time 1 "http://127.0.0.1:%~1/api/v1/capabilities" 2>nul | findstr /c:"%EXPECTED_BUILD%" >nul
if not errorlevel 1 (
 set "APP_PORT=%~1"
 set "EXISTING_LVW=1"
 exit /b 0
)
powershell.exe -NoProfile -NonInteractive -Command "$p=%~1; if (@([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object {$_.Port -eq $p}).Count) {exit 1} else {exit 0}" >nul 2>&1
if errorlevel 1 exit /b 0
wsl.exe -d %WSL_DISTRO% -e python3 -B -c "import socket,sys; s=socket.socket(); s.settimeout(0.3); r=s.connect_ex(('127.0.0.1',%~1)); s.close(); sys.exit(0 if r==111 else 1)" >nul 2>&1
if not errorlevel 1 set "APP_PORT=%~1"
exit /b 0
