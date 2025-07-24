@echo off
REM Update all .ts translation files using pylupdate6

REM Ensure the translations directory exists
if not exist .\src\translations (
    echo Translations folder not found!
    exit /b 1
)

echo Searching for .ts files in .\src\translations...

REM For each .ts file in the translations directory
for %%f in (.\src\translations\*.ts) do (
    echo Updating translation: %%~nxf
    pylupdate6 --exclude *_rc.py .\src\ --ts "%%f" --verbose
)

echo Done updating all translations.
pause
