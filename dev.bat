@echo off
echo UDP Oscilloscope Development Environment
echo ======================================

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

echo Starting PowerShell development environment...
powershell -NoExit -Command "& {. .\venv\Scripts\Activate.ps1}"
