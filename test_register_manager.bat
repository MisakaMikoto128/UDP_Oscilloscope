@echo off
echo 启动寄存器管理界面测试...
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python环境
    pause
    exit /b 1
)

REM 检查必要的目录
if not exist "config" mkdir config
if not exist "docs" mkdir docs
if not exist "src\ui\styles" mkdir src\ui\styles

REM 检查配置文件
if not exist "config\registers_config.json" (
    echo 配置文件不存在，复制示例配置文件...
    if exist "config\registers_config_example.json" (
        copy "config\registers_config_example.json" "config\registers_config.json"
        echo 已复制示例配置文件
    ) else (
        echo 警告: 示例配置文件不存在
    )
)

REM 运行测试
echo 启动寄存器管理界面测试...
python test\test_register_manager.py

pause
