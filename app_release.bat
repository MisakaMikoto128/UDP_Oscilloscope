@echo off
chcp 65001 > nul
title UDP示波器 - 实用优化启动

echo ========================================
echo UDP示波器实用优化启动脚本 v3.0
echo ========================================
echo.

cd /d %~dp0

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [权限] 管理员权限 - 将设置高优先级
    set ADMIN_MODE=1
) else (
    echo [权限] 普通用户权限
    set ADMIN_MODE=0
)

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 警告：未找到虚拟环境，使用系统Python环境
)

if %ADMIN_MODE% == 1 (
    echo [高优先级] 管理员模式启动
    start /HIGH /WAIT python -OO -u main.py
) else (
    python -OO -u main.py
)
