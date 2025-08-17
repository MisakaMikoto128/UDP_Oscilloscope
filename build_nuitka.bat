@echo off
echo RTT-T Monitor Build Script
echo ====================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python，请确保Python已安装并添加到系统环境变量
    pause
    exit /b 1
)

REM 检查Nuitka是否安装
python -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo 正在安装Nuitka...
    pip install nuitka
    if errorlevel 1 (
        echo 安装Nuitka失败，请检查网络连接或手动安装
        pause
        exit /b 1
    )
)

REM 创建构建目录
if not exist dist mkdir dist

REM 设置编译优化参数
set CFLAGS=/Ox /GL /Ob2 /Oy /GF /Gy
set CXXFLAGS=/Ox /GL /Ob2 /Oy /GF /Gy

echo CFLAGS is set to %CFLAGS%
echo CXXFLAGS is set to %CXXFLAGS%

REM 设置打包参数
set PYTHON_OPTIMIZE=2
set PYTHONUNBUFFERED=1

REM 开始打包
echo 开始打包...
python -m nuitka ^
    --msvc=latest ^
    --standalone ^
    --assume-yes-for-downloads ^
    --follow-imports ^
    --include-package=pylink ^
    --include-package=pandas ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=pandas.tests ^
    --lto=auto ^
    --include-data-dir=src/firmware=firmware ^
    --include-data-dir=src/templates=templates ^
    --include-data-dir=src/firmware_dumps=firmware_dumps ^
    --include-data-dir=src/excel_files=excel_files ^
    --include-data-files=src/*.html=./ ^
    --include-data-files=src/*.css=./ ^
    --include-data-files=src/*.js=./ ^
    --include-data-files="./JLinkARM.dll"="JLinkARM.dll" ^
    --windows-icon-from-ico=image/apple.ico ^
    --windows-company-name="LIU YUANLIN" ^
    --windows-product-name="卡方工程烧录测试工具" ^
    --windows-file-version=1.0.0 ^
    --windows-product-version=1.0.0 ^
    --windows-file-description="卡方工程烧录测试工具" ^
    --output-dir=dist ^
    --windows-console-mode=disable ^
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
) > "dist\app.dist\version.txt"

REM 重命名可执行文件
echo 重命名可执行文件...
ren "dist\app.dist\app.exe" "RTT-T.exe"

echo "打包完成！可执行文件位于 dist\app.dist\RTT-T.exe"
echo "请确保将整个 app.dist 文件夹一起分发，其中包含所有必要的依赖项"
pause
