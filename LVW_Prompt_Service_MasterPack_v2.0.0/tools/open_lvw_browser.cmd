@echo off
for /l %%I in (1,1,60) do (
  curl.exe -fsS "%~1/api/v1/runtime/status" 2>nul | findstr /c:"lvw.runtime/1" >nul
  if not errorlevel 1 (
    start "" "%~1"
    exit /b 0
  )
  timeout /t 1 /nobreak >nul
)
exit /b 1
