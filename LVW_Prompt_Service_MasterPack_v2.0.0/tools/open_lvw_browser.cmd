@echo off
for /l %%I in (1,1,60) do (
  curl.exe -fsS "%~1/health" >nul 2>&1 && (
    start "" "%~1"
    exit /b 0
  )
  timeout /t 1 /nobreak >nul
)
exit /b 1
