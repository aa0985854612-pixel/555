@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0runtime\python.exe" (
  "%~dp0runtime\python.exe" -X utf8 -m app.desktop
  if errorlevel 1 echo Startup failed. Keep this window open and send a screenshot without passwords.
) else (
  echo The Python runtime is missing. Extract the FULL Windows ZIP before starting.
  echo Download pigledger-windows-1.2.1.zip from the GitHub release folder.
)
echo.
echo This window may now be closed. Your saved data is kept on this laptop.
pause
endlocal
