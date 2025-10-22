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

REM 设置编译器优化标志
REM /O2: 最大化速度(推荐,比/Ox更全面)
REM /Oi: 启用内联函数
REM /Ot: 偏向速度而非大小
REM /GL: 全程序优化(配合--lto=yes使用)
REM /GF: 字符串池化(消除重复字符串)
REM /Gy: 函数级别链接(配合链接器优化)
set CFLAGS=/Ox /GL /Ob2 /Oy /GF /Gy
set CXXFLAGS=/Ox /GL /Ob2 /Oy /GF /Gy
REM 链接器优化标志
REM /LTCG: 链接时代码生成(配合/GL)
REM /OPT:REF: 移除未引用的代码
REM /OPT:ICF: 合并相同的COMDAT
set LDFLAGS=/LTCG /OPT:REF /OPT:ICF /INCREMENTAL:NO

echo CFLAGS is set to %CFLAGS%
echo CXXFLAGS is set to %CXXFLAGS%

REM 设置打包参数
set PYTHONUNBUFFERED=1

REM 开始打包
echo 开始打包...
python -m nuitka ^
    --msvc=latest ^
    --standalone ^
    --assume-yes-for-downloads ^
    --include-data-dir=img=img ^
    --include-data-dir=resource=resource ^
    --include-data-dir=config=config ^
    --include-data-dir=src/config=src/config ^
    --include-data-dir=src/ui/styles=ui/styles ^
    --windows-icon-from-ico=img\star.ico ^
    --windows-console-mode=force ^
    --follow-imports ^
    --enable-plugin=pyqt5 ^
    --enable-plugin=anti-bloat ^
    --python-flag=no_site ^
    --python-flag=-OO ^
    --nofollow-import-to=pyqt5-plugins,pyqt5-tools,qt5-tools ^
    --nofollow-import-to=setuptools,pip,wheel ^
    --nofollow-import-to=pytest,pydoc,docutils ^
    --nofollow-import-to=matplotlib ^
    --nofollow-import-to=numba,llvmlite ^
    --nofollow-import-to=scipy ^
    --nofollow-import-to=openpyxl ^
    --nofollow-import-to=pandas ^
    --nofollow-import-to=numpy._core.tests ^
    --nofollow-import-to=numpy.typing.tests ^
    --nofollow-import-to=numpy.tests.tests ^
    --nofollow-import-to=numpy.random.tests ^
    --nofollow-import-to=*.tests ^
    --nofollow-import-to=*.test ^
    --nofollow-import-to=*.testing ^
    --nofollow-import-to=pyqtgraph.examples ^
    --nofollow-import-to=OpenGL_accelerate ^
    --include-package=pyqtgraph ^
    --include-package=pyqtgraph.graphicsItems ^
    --include-package=pyqtgraph.opengl ^
    --include-package=pyqtgraph.exporters ^
    --include-package=pyqtgraph.widgets ^
    --include-package=OpenGL ^
    --include-package=numpy ^
    --include-package=h5py ^
    --include-package=crcmod ^
    --include-package=winloop ^
    --include-package=qasync ^
    --include-package=qfluentwidgets ^
    --include-package=qframelesswindow ^
    --include-package=qframelesswindow.titlebar ^
    --include-package-data=qfluentwidgets ^
    --include-package-data=qframelesswindow ^
    --lto=yes ^
    --windows-company-name="LIU YUANLIN" ^
    --windows-product-name="电机控制板上位机软件" ^
    --windows-file-version=1.0.0 ^
    --windows-product-version=1.0.0 ^
    --windows-file-description="电机控制板上位机软件" ^
    --output-dir=release ^
    main.py

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

pause
