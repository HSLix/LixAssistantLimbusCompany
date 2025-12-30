@echo off
setlocal enabledelayedexpansion
@REM :: 1. Clean/Rebuild doc 
echo [1/8] Preparing doc resources ...
if exist "doc\README.md" del "doc\README.md"
if exist "doc\img"         rmdir /s /q "doc\img"
if exist "README.md"       copy "README.md" "doc" >nul
if exist "img"             xcopy "img" "doc\img" /s /e /i /y >nul
@REM :: 2. Clean frontend
echo [2/8] Cleaning frontend assets ...
for %%D in (doc ego_gifts theme_packs) do (
if exist "lalc_frontend\assets%%D" rmdir /s /q "lalc_frontend\assets%%D"
)
xcopy "doc"                         "lalc_frontend\assets\doc"         /s /e /i /y >nul
xcopy "lalc_backend\img\ego_gifts"   "lalc_frontend\assets\ego_gifts"   /s /e /i /y >nul
xcopy "lalc_backend\img\theme_packs" "lalc_frontend\assets\theme_packs" /s /e /i /y >nul
@REM :: 3. Clean Release
echo [3/8] Cleaning output folder ...
cd /d "%~dp0"
if exist "lalc" rmdir /s /q "lalc"
mkdir "lalc"

@REM :: 4. Build backend
echo [4/8] Packaging backend ...
cd /d "lalc_backend"
call deploy_to_pystand.bat
if %errorlevel% neq 0 (
echo Backend deploy failed!
cd /d "%~dp0"
exit /b %errorlevel%
)
@REM :: 5. Copy and rename backend
echo [5/8] Finalizing backend ...
cd /d "%~dp0"
set "BACK_SRC=lalc_backend\pystand"
set "BACK_DST=lalc"

@REM :: Copy backend files directly to lalc folder
xcopy "%BACK_SRC%" "%BACK_DST%" /s /e /i /y >nul

@REM :: Rename backend executable files
if exist "%BACK_DST%\lalc_backend.exe" (
    move "%BACK_DST%\lalc_backend.exe" "%BACK_DST%\LixAssistantLimbusCompany.exe" >nul
)
if exist "%BACK_DST%\lalc_backend.int" (
    move "%BACK_DST%\lalc_backend.int" "%BACK_DST%\LixAssistantLimbusCompany.int" >nul
)

@REM :: 6. Build Flutter
echo [6/8] Building Flutter ...
cd /d "lalc_frontend"

@REM :: Check if windows folder exists, if not create it
if not exist "windows" (
    echo Windows folder not found, creating with flutter create...
    cmd /c "flutter create --platforms windows ."
    if %errorlevel% neq 0 (
        echo Failed to create windows platform files!
        cd /d "%~dp0"
        exit /b %errorlevel%
    )
)

@REM :: Copy icon file to replace app_icon.ico
if exist "..\MagicAndWonder.ico" (
    if exist "windows\runner\resources\app_icon.ico" (
        copy /Y "..\MagicAndWonder.ico" "windows\runner\resources\app_icon.ico" >nul
        echo Icon file replaced successfully.
    ) else (
        echo Warning: windows\runner\resources\app_icon.ico not found.
    )
) else (
    echo Warning: MagicAndWonder.ico not found in root directory.
)

@REM :: Read version from version.txt
for /f "usebackq" %%i in ("../version.txt") do set VERSION=%%i
cmd /c "flutter build windows --dart-define=CURRENT_VERSION=v!VERSION!"
if %errorlevel% neq 0 (
echo Flutter build failed!
cd /d "%~dp0"
exit /b %errorlevel%
)
@REM :: 7. Copy frontend
echo [7/8] Packaging frontend ...
cd /d "%~dp0"
set "FRONT_SRC=lalc_frontend\build\windows\x64\runner\Release"
set "FRONT_DST=lalc\lalc_frontend"
if exist "%FRONT_DST%" rmdir /s /q "%FRONT_DST%"
xcopy "%FRONT_SRC%" "%FRONT_DST%" /s /e /i /y >nul
if %errorlevel% neq 0 (
echo Failed to copy frontend files!
exit /b %errorlevel%
)

@REM :: 7.5 Copy root files (LICENSE, README.md, update_to.bat)
echo [7.5/8] Copying root files ...
cd /d "%~dp0"
if exist "LICENSE" copy "LICENSE" "lalc" /y >nul
if exist "README.md" copy "README.md" "lalc" /y >nul
if exist "update_to.bat" copy "update_to.bat" "lalc" /y >nul

@REM :: 8. Compress lalc folder to lalc.zip
echo [8/8] Compressing lalc folder ...
cd /d "%~dp0"
if exist "lalc.zip" del "lalc.zip"
powershell Compress-Archive -Path "lalc" -DestinationPath "lalc.zip" -Force
if %errorlevel% neq 0 (
echo Failed to compress lalc folder!
exit /b %errorlevel%
)

echo Packup lalc process completed successfully. 
pause