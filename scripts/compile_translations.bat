@echo off
REM Compile all .ts translation files into .qm files using pyside6-lrelease

set TS_DIR=.\src\translations
set QM_DIR=.\src\translations

REM Ensure the .ts directory exists
if not exist %TS_DIR% (
    echo Translations folder not found!
    exit /b 1
)

REM Ensure the output directory exists
if not exist %QM_DIR% (
    mkdir %QM_DIR%
)

echo Compiling .ts files to .qm...

for %%f in (%TS_DIR%\*.ts) do (
    echo Compiling %%~nxf...
    pyside6-lrelease "%%f" -qm "%QM_DIR%\%%~nf.qm"
)

echo Done compiling translations.
pause
