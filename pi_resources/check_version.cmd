@echo off
uv run --no-project --python 3.12 python "%~dp0check_version.py" %*
set "check_exit=%errorlevel%"
pause
exit /b %check_exit%
