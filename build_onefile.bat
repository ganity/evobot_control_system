@echo off
echo 开始单文件打包EvoBot控制系统...

REM 检查Python环境
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python环境
    pause
    exit /b 1
)

REM 安装打包依赖
echo 安装打包依赖...
pip install -r build_requirements.txt
if %errorlevel% neq 0 (
    echo 错误: 安装打包依赖失败
    pause
    exit /b 1
)

REM 清理之前的构建
echo 清理之前的构建文件...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM 单文件打包
echo 开始单文件打包...
pyinstaller --onefile ^
    --windowed ^
    --name "EvoBot控制系统" ^
    --add-data "config;config" ^
    --add-data "README.md;." ^
    --hidden-import "PyQt5.QtCore" ^
    --hidden-import "PyQt5.QtGui" ^
    --hidden-import "PyQt5.QtWidgets" ^
    --hidden-import "pyqtgraph" ^
    --hidden-import "numpy" ^
    --hidden-import "scipy" ^
    --hidden-import "roboticstoolbox" ^
    --hidden-import "spatialmath" ^
    --hidden-import "serial" ^
    --hidden-import "loguru" ^
    --hidden-import "yaml" ^
    --exclude-module "tkinter" ^
    --exclude-module "unittest" ^
    --exclude-module "test" ^
    --exclude-module "tests" ^
    --exclude-module "pytest" ^
    main.py

if %errorlevel% neq 0 (
    echo 错误: 单文件打包失败
    pause
    exit /b 1
)

echo 单文件打包完成！
echo 可执行文件: dist\EvoBot控制系统.exe

pause