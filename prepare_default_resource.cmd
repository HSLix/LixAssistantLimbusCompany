@echo off
setlocal
pushd "%~dp0" || exit /b 1
uv run --locked python scripts\prepare_default_resource.py
set "prepare_exit=%errorlevel%"
popd
exit /b %prepare_exit%
