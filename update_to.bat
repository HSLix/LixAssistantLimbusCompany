@echo off
rem update_to.bat  ——  Self-update helper for LixAssistantLimbusCompany
rem Author: <you>
rem Usage:  update_to.bat  <path-to-source-directory> <path-to-target-directory>

setlocal enabledelayedexpansion
set "LOG=update_log.txt"
set "SOURCE_DIR=%~1"
set "TARGET_DIR=%~2"

rem ------------------------------------------------------------------
rem 0. Basic validation
rem ------------------------------------------------------------------
echo === Update started at %DATE% %TIME% === > "%LOG%"
echo [INFO] Source directory: "%SOURCE_DIR%" >> "%LOG%"
echo [INFO] Target directory: "%TARGET_DIR%" >> "%LOG%"
if "%SOURCE_DIR%"=="" (
    echo [ERROR] No source directory provided. >> "%LOG%"
    echo 未提供源目录参数 >> "%LOG%"
    exit /b 1
)
if "%TARGET_DIR%"=="" (
    echo [ERROR] No target directory provided. >> "%LOG%"
    echo 未提供目标目录参数 >> "%LOG%"
    exit /b 1
)

rem Check if source directory exists
if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory does not exist: "%SOURCE_DIR%" >> "%LOG%"
    echo 源目录不存在 >> "%LOG%"
    exit /b 1
)

rem Create target directory if it doesn't exist
if not exist "%TARGET_DIR%" (
    echo [INFO] Creating target directory: "%TARGET_DIR%" >> "%LOG%"
    mkdir "%TARGET_DIR%" >> "%LOG%"
)

rem ------------------------------------------------------------------
rem 1. Terminate running processes
rem ------------------------------------------------------------------
echo [INFO] Terminating lalc_frontend and LixAssistantLimbusCompany ... >> "%LOG%"
echo "正在关闭 lalc_frontend 和 LixAssistantLimbusCompany 进程" >> "%LOG%"
taskkill /F /IM lalc_frontend.exe 2>nul >> "%LOG%"
echo "等待 LixAssistantLimbusCompany 进程关闭中" >> "%LOG%"
timeout /t 12 /nobreak >nul
@REM taskkill /F /IM LixAssistantLimbusCompany.exe 2>nul >> "%LOG%"
echo [INFO] Processes terminated. >> "%LOG%"


rem ------------------------------------------------------------------
rem 2. Clean target directory (keep update_to.bat if it exists there)
rem ------------------------------------------------------------------
echo [INFO] Cleaning target directory ... >> "%LOG%"
echo 正在清理目标目录 >> "%LOG%"
pushd "%TARGET_DIR%"

rem Process files first
for /f "delims=" %%i in ('dir /b /a-d 2^>nul') do (
    if /i not "%%i"=="update_to.bat" (
        echo [DELETE] file %%i >> "%LOG%"
        echo Deleting file: %%i
        del /f /q "%%i" >> "%LOG%" 2>&1
        if errorlevel 1 (
            echo [ERROR] Could not delete file %%i, will copy over it later >> "%LOG%"
            echo Error deleting file: %%i
        )
    )
)

rem Process directories
for /f "delims=" %%d in ('dir /b /ad 2^>nul') do (
    if /i not "%%d"=="%~nx0" (
        echo [DELETE] folder %%d >> "%LOG%"
        echo Deleting folder: %%d
        rd /s /q "%%d" >> "%LOG%" 2>&1
        if errorlevel 1 (
            echo [ERROR] Could not delete folder %%d, will copy over it later >> "%LOG%"
            echo Error deleting folder: %%d
        )
    )
)
popd

rem ------------------------------------------------------------------
rem 3. Copy from source directory to target directory (except this script)
rem ------------------------------------------------------------------
echo [INFO] Copying from source directory to target ... >> "%LOG%"
echo 正在从源目录复制文件到目标目录 >> "%LOG%"
echo Starting robocopy from "%SOURCE_DIR%" to "%TARGET_DIR%"

rem Use robocopy with detailed logging and exclude this script file, showing output directly
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /COPY:DAT /R:3 /W:2 /XD "%TARGET_DIR%" /XF "update_to.bat" /V /NP

set "ROBOCOPY_EXIT_CODE=%errorlevel%"

rem Log robocopy result
echo [INFO] Robocopy completed with exit code %ROBOCOPY_EXIT_CODE% >> "%LOG%"
echo Robocopy completed with exit code %ROBOCOPY_EXIT_CODE%

if %ROBOCOPY_EXIT_CODE% gtr 7 (
    echo [ERROR] Robocopy failed with code %ROBOCOPY_EXIT_CODE% >> "%LOG%"
    echo 复制失败，请查看日志 >> "%LOG%"
    echo Robocopy failed with code %ROBOCOPY_EXIT_CODE%
    exit /b %ROBOCOPY_EXIT_CODE%
)

rem ------------------------------------------------------------------
rem 4. Done
rem ------------------------------------------------------------------
echo [INFO] Update finished successfully at %DATE% %TIME% >> "%LOG%"
echo 更新完成 >> "%LOG%"
echo Update completed successfully!

rem ------------------------------------------------------------------
rem 5. Start the application as administrator
rem ------------------------------------------------------------------
echo [INFO] Attempting to start LixAssistantLimbusCompany.exe as Administrator >> "%LOG%"
echo 正在尝试以管理员身份启动 LixAssistantLimbusCompany.exe >> "%LOG%"

set "APP_PATH=%TARGET_DIR%\LixAssistantLimbusCompany.exe"

if exist "!APP_PATH!" (
    echo [INFO] Found application at "!APP_PATH!" >> "%LOG%"
    echo 找到应用程序 >> "%LOG%"
    
    rem Try to start as administrator using PowerShell
    PowerShell -Command "Start-Process -FilePath '!APP_PATH!' -Verb RunAs -WorkingDirectory '%TARGET_DIR%'" 2>> "%LOG%"
    
    if !errorlevel! equ 0 (
        echo [INFO] Successfully started application as Administrator >> "%LOG%"
        echo 成功以管理员身份启动应用程序 >> "%LOG%"
    ) else (
        echo [ERROR] Failed to start application as Administrator >> "%LOG%"
        echo 以管理员身份启动应用程序失败 >> "%LOG%"
        echo 请手动以管理员身份运行 LixAssistantLimbusCompany.exe
    )
) else (
    echo [ERROR] Application not found at "!APP_PATH!" >> "%LOG%"
    echo 应用程序未找到 >> "%LOG%"
)

pause
exit /b 0