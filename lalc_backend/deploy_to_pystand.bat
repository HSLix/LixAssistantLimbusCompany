@echo off
echo \__pycache__> exclude_temp.txt
echo *.pyc>> exclude_temp.txt

echo Cleaning pystand/script directory...
if exist "pystand\script" (
    rd /s /q "pystand\script"
)
echo Creating new script directory...
mkdir "pystand\script"

echo Cleaning pystand/site-packages directory...
if exist "pystand\site-packages" (
    rd /s /q "pystand\site-packages"
)
echo Creating new site-packages directory...
mkdir "pystand\site-packages"

echo Copying files and directories to pystand/script...
xcopy "config" "pystand\script\config\" /E /I /Y /EXCLUDE:exclude_temp.txt /Q
xcopy "doc" "pystand\script\doc\" /E /I /Y /Q
xcopy "img" "pystand\script\img\" /E /I /Y /Q
xcopy "input" "pystand\script\input\" /E /I /Y /EXCLUDE:exclude_temp.txt /Q
copy "main.py" "pystand\script\"
copy "server.py" "pystand\script\"
xcopy "utils" "pystand\script\utils\" /E /I /Y /EXCLUDE:exclude_temp.txt /Q
xcopy "workflow" "pystand\script\workflow\" /E /I /Y /EXCLUDE:exclude_temp.txt /Q
xcopy "recognize" "pystand\script\recognize\" /E /I /Y /EXCLUDE:exclude_temp.txt /Q

echo Copying site-packages to pystand/site-packages...
xcopy ".venv\Lib\site-packages\*" "pystand\site-packages\" /E /I /Y /Q

echo Pystand Deployment completed!
del exclude_temp.txt