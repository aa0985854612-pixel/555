@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0runtime\python.exe" (
  "%~dp0runtime\python.exe" -X utf8 -m app.phone
  if errorlevel 1 echo Phone connection failed. Your records are kept. Check Internet and retry.
) else (
  echo Extract the FULL pigledger-windows-1.2.0.zip before starting.
)
echo.
echo This window may now be closed. Your saved data is kept on this laptop.
pause
endlocal
