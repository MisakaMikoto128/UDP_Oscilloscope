@echo off
chcp 65001 > nul
echo ========================================
echo           UDP示波器启动脚本
echo ========================================
echo.

cd /d %~dp0

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 警告：未找到虚拟环境，使用系统Python环境
)

echo 正在启动UDP示波器...
python main.py

pause