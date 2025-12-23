#!/usr/bin/env python3
"""
Windows依赖修复脚本
解决PyQt5在Windows平台的兼容性问题
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令并处理错误"""
    print(f"🔧 {description}")
    print(f"执行: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description} 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败")
        print(f"错误: {e.stderr}")
        return False


def check_python():
    """检查Python环境"""
    try:
        version = sys.version_info
        if version.major == 3 and version.minor >= 10:
            print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            print(f"❌ Python版本过低: {version.major}.{version.minor}.{version.micro}")
            print("需要Python 3.10或更高版本")
            return False
    except Exception as e:
        print(f"❌ 检查Python版本失败: {e}")
        return False


def install_with_pip():
    """使用pip安装依赖"""
    print("\n📦 使用pip安装Windows兼容的依赖...")
    
    # 核心PyQt5依赖
    qt_packages = [
        "PyQt5==5.15.10",
        "PyQt5-sip==12.13.0",
    ]
    
    # 其他依赖
    other_packages = [
        "pyqtgraph>=0.13.0",
        "pyserial>=3.5",
        "numpy>=1.24.0,<2.0.0",
        "scipy>=1.10.0",
        "pyyaml>=6.0",
        "loguru>=0.7.0",
        "matplotlib>=3.7.0",
    ]
    
    # 可选依赖（可能安装失败但不影响基本功能）
    optional_packages = [
        "roboticstoolbox-python>=1.1.0",
        "spatialmath-python>=1.1.0",
    ]
    
    success = True
    
    # 安装PyQt5
    for package in qt_packages:
        if not run_command(f"pip install {package}", f"安装 {package}"):
            success = False
    
    # 安装其他核心依赖
    for package in other_packages:
        if not run_command(f"pip install {package}", f"安装 {package}"):
            success = False
    
    # 安装可选依赖
    for package in optional_packages:
        run_command(f"pip install {package}", f"安装 {package} (可选)")
    
    return success


def install_with_uv():
    """使用uv安装依赖"""
    print("\n📦 尝试使用uv安装...")
    
    # 检查uv是否可用
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("uv未安装，正在安装...")
        if not run_command("pip install uv", "安装uv"):
            return False
    
    # 尝试使用修复后的配置
    return run_command("uv sync", "使用uv同步依赖")


def create_test_script():
    """创建测试脚本"""
    test_script = """
import sys
print("🧪 测试依赖导入...")

try:
    from PyQt5.QtWidgets import QApplication
    print("✅ PyQt5.QtWidgets 导入成功")
except ImportError as e:
    print(f"❌ PyQt5.QtWidgets 导入失败: {e}")
    sys.exit(1)

try:
    import pyqtgraph
    print("✅ pyqtgraph 导入成功")
except ImportError as e:
    print(f"❌ pyqtgraph 导入失败: {e}")

try:
    import serial
    print("✅ pyserial 导入成功")
except ImportError as e:
    print(f"❌ pyserial 导入失败: {e}")

try:
    import numpy
    print("✅ numpy 导入成功")
except ImportError as e:
    print(f"❌ numpy 导入失败: {e}")

print("\\n🎉 核心依赖测试完成！")
"""
    
    with open("test_deps.py", "w", encoding="utf-8") as f:
        f.write(test_script)
    
    print("✅ 创建测试脚本: test_deps.py")


def main():
    """主函数"""
    print("🔧 EvoBot Windows依赖修复工具")
    print("=" * 50)
    
    # 检查Python环境
    if not check_python():
        return False
    
    # 尝试不同的安装方法
    success = False
    
    # 方法1: 使用修复后的uv
    if install_with_uv():
        success = True
    else:
        print("\n⚠️  uv安装失败，尝试使用pip...")
        # 方法2: 使用pip
        if install_with_pip():
            success = True
    
    if success:
        print("\n🎉 依赖安装成功！")
        
        # 创建测试脚本
        create_test_script()
        
        print("\n📋 后续步骤:")
        print("1. 运行测试: python test_deps.py")
        print("2. 启动程序: python main.py")
        
        return True
    else:
        print("\n❌ 依赖安装失败")
        print("\n🔧 手动解决方案:")
        print("1. pip install PyQt5==5.15.10")
        print("2. pip install pyqtgraph pyserial numpy scipy")
        print("3. pip install pyyaml loguru matplotlib")
        
        return False


def is_ci_environment():
    """检查是否在CI环境中运行"""
    return any(key in os.environ for key in ['CI', 'GITHUB_ACTIONS', 'CONTINUOUS_INTEGRATION'])


if __name__ == "__main__":
    success = main()
    
    # 在CI环境中不等待用户输入
    if not is_ci_environment():
        input("\n按回车键退出...")
    
    sys.exit(0 if success else 1)