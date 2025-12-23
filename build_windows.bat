@echo off
echo 开始打包EvoBot控制系统...

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

REM 使用PyInstaller打包
echo 开始打包...
pyinstaller evobot.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo 错误: 打包失败
    pause
    exit /b 1
)

echo 打包完成！
echo 可执行文件位于: dist\EvoBot控制系统\
echo 运行 dist\EvoBot控制系统\EvoBot控制系统.exe 启动程序

pause