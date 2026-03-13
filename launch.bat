@echo off
title MusicOtheque
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Create venv if needed
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install deps only once (re-install if requirements.txt changes)
set "MARKER=venv\.deps_installed"
if exist "%MARKER%" (
    fc /b requirements.txt "%MARKER%" >nul 2>&1 && goto :launch
)
echo Installing dependencies...
pip install -q -r requirements.txt
copy /y requirements.txt "%MARKER%" >nul 2>&1

:launch
python musicotheque.py %*
