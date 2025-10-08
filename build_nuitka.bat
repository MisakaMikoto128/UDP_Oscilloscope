@echo off
chcp 65001 > nul
echo ========================================
echo         UDP示波器 Nuitka 打包工具
echo ========================================
echo.

REM 检查Python环境
python --version > nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python环境！
    echo 请确保Python已正确安装并添加到PATH环境变量中。
    pause
    exit /b 1
)

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 警告：未找到虚拟环境，使用系统Python环境
)

REM 检查Nuitka是否安装
python -c "import nuitka" > nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Nuitka！
    echo 正在安装Nuitka...
    pip install nuitka
    if errorlevel 1 (
        echo 安装Nuitka失败！
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

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist "main.dist" rmdir /s /q "main.dist"
if exist "main.build" rmdir /s /q "main.build"
if exist "main.onefile-build" rmdir /s /q "main.onefile-build"

REM 开始打包
echo 开始打包...
python -m nuitka ^
    --msvc=latest ^
    --standalone ^
    --assume-yes-for-downloads ^
    --follow-imports ^
    --enable-plugin=pyqt5 ^
    --include-package=pyqtgraph ^
    --include-package=numpy ^
    --include-package=h5py ^
    --include-package=crcmod ^
    --include-package=winloop ^
    --include-package=qasync ^
    --include-package=qfluentwidgets ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=matplotlib ^
    --include-module=pyqtgraph.opengl ^
    --lto=auto ^
    --include-data-dir=src/config=config ^
    --include-data-dir=src/ui/styles=ui/styles ^
    --windows-company-name="LIU YUANLIN" ^
    --windows-product-name="UDP示波器" ^
    --windows-file-version=1.0.0 ^
    --windows-product-version=1.0.0 ^
    --windows-file-description="电机控制板上位机软件" ^
    --output-dir=dist ^
    --windows-console-mode=disable ^
    main.py

REM 检查打包结果
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

REM 移动生成的文件夹到dist目录
if exist "main.dist" (
    if exist "dist\UDP_Oscilloscope" rmdir /s /q "dist\UDP_Oscilloscope"
    move "main.dist" "dist\UDP_Oscilloscope"
)

REM 重命名可执行文件
echo 重命名可执行文件...
if exist "dist\UDP_Oscilloscope\main.exe" (
    ren "dist\UDP_Oscilloscope\main.exe" "UDP_Oscilloscope.exe"
    echo 可执行文件重命名成功
) else (
    echo 警告：未找到main.exe文件！
)

REM 创建版本信息文件
echo 创建版本信息...
(
echo 应用名称：UDP示波器
echo 版本：1.0.0
echo 构建时间：%date% %time%
echo 构建环境：Windows
echo 作者：刘沅林
echo 描述：电机控制板上位机软件
echo GitHub：https://github.com/MisakaMikoto128
) > "dist\UDP_Oscilloscope\version.txt"

REM 复制配置文件
echo 复制配置文件...
if not exist "dist\UDP_Oscilloscope\config" mkdir "dist\UDP_Oscilloscope\config"
if exist "src\config\default_config.json" (
    copy "src\config\default_config.json" "dist\UDP_Oscilloscope\config\" > nul
    echo 配置文件复制成功
) else (
    echo 警告：未找到default_config.json文件！
)

REM 验证打包结果
echo 验证打包结果...
if exist "dist\UDP_Oscilloscope\UDP_Oscilloscope.exe" (
    echo ✅ 可执行文件存在
) else (
    echo ❌ 可执行文件不存在！
)

if exist "dist\UDP_Oscilloscope\config\default_config.json" (
    echo ✅ 配置文件存在
) else (
    echo ❌ 配置文件不存在！
)

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo 可执行文件位于: dist\UDP_Oscilloscope\UDP_Oscilloscope.exe
echo 请确保将整个 UDP_Oscilloscope 文件夹一起分发
echo.

REM 打开输出目录
explorer "dist\UDP_Oscilloscope"

pause
