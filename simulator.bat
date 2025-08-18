@echo off
chcp 65001 > nul
echo ========================================
echo         下位机模拟器启动脚本
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

echo 正在启动下位机模拟器...
echo 目标地址: 127.0.0.1:8888
echo 发送频率: 100 Hz
echo 按 Ctrl+C 停止模拟器
echo.

python test_simulator.py

pause
