@echo off
rem fusion-agent launcher for Windows (cmd, PowerShell or a double-click in Explorer).
rem Finds Python 3.10+, creates .venv on the first run, installs the requirements when they change,
rem then starts the app and passes every argument through.
setlocal
chcp 65001 >nul

rem A double-click (or PowerShell) runs this file as "cmd /c ...": pause on errors so the window stays readable.
set "PAUSE_ON_ERROR="
setlocal EnableDelayedExpansion
if /i not "!cmdcmdline:/c =!"=="!cmdcmdline!" set "PAUSE_ON_ERROR=1"
endlocal & set "PAUSE_ON_ERROR=%PAUSE_ON_ERROR%"

set "HERE=%~dp0"
set "VENV=%HERE%.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"

if exist "%VENV_PY%" goto :have_venv

call :find_python
if not defined BASE_PY (
    echo Python 3.10 or newer was not found.
    echo   1. Install Python 3.12 from https://www.python.org/downloads/windows/
    echo      and tick "Add python.exe to PATH" in the installer,
    echo      or run in a terminal: winget install Python.Python.3.12
    echo   2. Open a new terminal window and run fusion-agent again.
    goto :fail
)
echo First run: creating the Python environment in "%VENV%" ...
%BASE_PY% -m venv "%VENV%"
if errorlevel 1 (
    echo Could not create the Python environment in "%VENV%".
    goto :fail
)

:have_venv
"%VENV_PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo The Python environment in "%VENV%" is broken.
    echo   Delete the folder .venv and run fusion-agent again.
    goto :fail
)
fc /b "%HERE%requirements.txt" "%VENV%\installed-requirements.txt" >nul 2>&1
if errorlevel 1 (
    echo Installing the requirements ...
    "%VENV_PY%" -m pip install --disable-pip-version-check --quiet -r "%HERE%requirements.txt"
    if errorlevel 1 (
        echo pip could not install the requirements. Check the internet connection and run fusion-agent again.
        goto :fail
    )
    copy /y "%HERE%requirements.txt" "%VENV%\installed-requirements.txt" >nul
)

set "PYTHONPATH=%HERE%;%PYTHONPATH%"
"%VENV_PY%" -X utf8 -m fusion_agent %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" if not "%CODE%"=="130" if defined PAUSE_ON_ERROR pause
exit /b %CODE%

:fail
if defined PAUSE_ON_ERROR pause
exit /b 1

:find_python
set "BASE_PY="
for %%C in ("py -3" "python" "python3") do (
    %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_PY=%%~C"
        exit /b 0
    )
)
exit /b 0
