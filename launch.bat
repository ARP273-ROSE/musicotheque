@echo off
title MusicOtheque
cd /d "%~dp0"

REM === Find Python (try multiple methods) ===
set "PYTHON="

REM 1. Windows Python Launcher (most reliable)
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if defined PYTHON goto :found_python

REM 2. python in PATH
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON=python"
if defined PYTHON goto :found_python

REM 3. python3 in PATH
python3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=python3"
if defined PYTHON goto :found_python

echo.
echo  Python not found. Please install Python 3.10+ from python.org
echo  Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found_python

REM === Check if venv is valid for THIS machine ===
if not exist "venv\Scripts\python.exe" goto :create_venv
"venv\Scripts\python.exe" -c "print('ok')" >nul 2>&1
if not errorlevel 1 goto :venv_ok

:create_venv
if exist "venv" (
    echo Recreating virtual environment...
    rmdir /s /q venv
)
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON% -m venv venv
)

:venv_ok
REM === Activate venv ===
call venv\Scripts\activate.bat

REM === Install deps (re-install if requirements.txt changes) ===
set "MARKER=venv\.deps_installed"
if exist "%MARKER%" (
    fc /b requirements.txt "%MARKER%" >nul 2>&1 && goto :launch
)
echo Installing dependencies...
pip install -q -r requirements.txt
copy /y requirements.txt "%MARKER%" >nul 2>&1

:launch
REM Use pythonw (no console) if available
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" musicotheque.py %*
) else (
    python musicotheque.py %*
)
