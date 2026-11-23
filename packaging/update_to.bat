@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-update.ps1" -Source "%~1" -Target "%~2" -Legacy
exit /b %errorlevel%
