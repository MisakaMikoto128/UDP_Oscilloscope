@echo off
echo RTT-T 监控工具打包脚本 (PyInstaller版)
echo =====================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python，请确保Python已安装并添加到系统环境变量
    pause
    exit /b 1
)

REM 检查PyInstaller是否安装
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo 安装PyInstaller失败，请检查网络连接或手动安装
        pause
        exit /b 1
    )
)

REM 创建构建目录
if not exist dist mkdir dist

REM 设置打包参数
@REM set PYTHONOPTIMIZE=2

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist build\Jlink-tools rmdir /s /q build\Jlink-tools
if exist dist\Jlink-tools rmdir /s /q dist\Jlink-tools

REM 开始打包
echo 开始打包...
pyinstaller ^
    --name="Jlink-tools" ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --upx-dir=upx-tools ^
    --add-data="src/firmware;firmware" ^
    --add-data="src/templates;templates" ^
    --add-data="src/*.html;." ^
    --add-data="src/*.css;." ^
    --add-data="src/*.js;." ^
    --icon=image/apple.ico ^
    --log-level=INFO ^
    --paths=src ^
    src/app.py

REM 检查打包结果
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

REM 创建版本信息文件
echo 创建版本信息...
(
echo 版本：1.0.0
echo 构建时间：%date% %time%
echo 构建环境：Windows
echo 作者：刘沅林
echo GitHub：https://github.com/MisakaMikoto128
) > "dist\Jlink-tools\version.txt"

echo 打包完成！可执行文件位于 dist\Jlink-tools\Jlink-tools.exe
echo 请确保将整个 Jlink-tools 文件夹一起分发，其中包含所有必要的依赖项

REM 打开输出目录
explorer "dist\Jlink-tools"

pause
