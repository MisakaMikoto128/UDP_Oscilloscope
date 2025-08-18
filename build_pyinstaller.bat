@echo off
chcp 65001 > nul
echo ========================================
echo        UDP示波器 PyInstaller 打包工具
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

REM 检查PyInstaller
python -c "import PyInstaller" > nul 2>&1
if errorlevel 1 (
    echo 错误：未找到PyInstaller！
    echo 正在安装PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo PyInstaller安装失败！
        pause
        exit /b 1
    )
)

REM 创建构建目录
if not exist dist mkdir dist

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist build\UDP_Oscilloscope rmdir /s /q build\UDP_Oscilloscope
if exist dist\UDP_Oscilloscope rmdir /s /q dist\UDP_Oscilloscope

REM 开始打包
echo 开始打包...
pyinstaller ^
    --name="UDP_Oscilloscope" ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data="src/config/default_config.json;config" ^
    --hidden-import=winloop ^
    --hidden-import=crcmod ^
    --hidden-import=h5py ^
    --hidden-import=pyqtgraph.opengl ^
    --hidden-import=PyQt5.sip ^
    --log-level=INFO ^
    --paths=src ^
    src/main.py

REM 检查打包结果
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
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
copy "src\config\default_config.json" "dist\UDP_Oscilloscope\config\" > nul

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
