@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The C-LARA Windows Python environment was not found beside this launcher.
  pause
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -E "platform_server\manage.py" community_google_tts_connect
set "CLARA_CONNECT_RESULT=%ERRORLEVEL%"
echo.
pause
popd
exit /b %CLARA_CONNECT_RESULT%
