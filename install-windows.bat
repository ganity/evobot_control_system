@echo off
echo 正在为Windows平台安装EvoBot控制系统依赖...

REM 检查Python环境
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python环境
    echo 请先安装Python 3.10或更高版本
    pause
    exit /b 1
)

REM 检查uv是否安装
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装uv包管理器...
    pip install uv
    if %errorlevel% neq 0 (
        echo 错误: uv安装失败
        pause
        exit /b 1
    )
)

echo 正在使用Windows专用依赖文件安装...

REM 方法1: 使用Windows专用requirements文件
pip install -r requirements-windows.txt
if %errorlevel% equ 0 (
    echo ✅ 依赖安装成功！
    goto :success
)

echo 方法1失败，尝试方法2...

REM 方法2: 逐个安装核心依赖
echo 正在安装PyQt5...
pip install PyQt5==5.15.10
if %errorlevel% neq 0 (
    echo 错误: PyQt5安装失败
    pause
    exit /b 1
)

echo 正在安装其他依赖...
pip install pyqtgraph pyserial numpy scipy pyyaml loguru matplotlib
if %errorlevel% neq 0 (
    echo 错误: 其他依赖安装失败
    pause
    exit /b 1
)

echo 正在安装机器人工具箱...
pip install roboticstoolbox-python spatialmath-python
if %errorlevel% neq 0 (
    echo 警告: 机器人工具箱安装失败，但不影响基本功能
)

:success
echo.
echo ✅ 安装完成！
echo.
echo 现在可以运行程序了:
echo   python main.py
echo.
pause