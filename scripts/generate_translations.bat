@echo off
REM Check if argument is passed
if "%~1"=="" (
    echo Please provide the translation name as an argument.
    exit /b 1
)

set TS_FILE=%~1

REM Ensure the translations directory exists
if not exist .\src\translations (
    mkdir .\src\translations
)

REM Generate the translation file using pylupdate6
echo Generating translation file %TS_FILE%.ts...

pylupdate6 --exclude *_rc.py .\src\ --ts .\src\translations\%TS_FILE%.ts --verbose
