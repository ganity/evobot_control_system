#!/usr/bin/env python3
"""
简单测试脚本

测试基本的PyQt5功能是否正常
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_qt():
    """测试基本Qt功能"""
    print("🔧 测试基本Qt功能...")
    
    try:
        from PyQt5.QtWidgets import QApplication, QLabel, QWidget
        from PyQt5.QtCore import Qt
        
        print("✅ PyQt5基础模块导入成功")
        
        # 创建应用程序
        app = QApplication(sys.argv)
        print("✅ QApplication创建成功")
        
        # 创建简单窗口
        widget = QWidget()
        widget.setWindowTitle("测试窗口")
        widget.resize(300, 200)
        
        label = QLabel("PyQt5测试成功！", widget)
        label.setAlignment(Qt.AlignCenter)
        
        print("✅ Qt组件创建成功")
        
        # 不显示窗口，直接退出
        app.quit()
        
        return True
        
    except Exception as e:
        print(f"❌ 基本Qt测试失败: {e}")
        return False

def test_pyqtgraph():
    """测试pyqtgraph"""
    print("📊 测试pyqtgraph...")
    
    try:
        import pyqtgraph as pg
        print("✅ pyqtgraph导入成功")
        
        # 设置配置
        pg.setConfigOptions(
            antialias=True,
            useOpenGL=False,
            crashWarning=False
        )
        print("✅ pyqtgraph配置成功")
        
        return True
        
    except Exception as e:
        print(f"❌ pyqtgraph测试失败: {e}")
        return False

def test_qt_version():
    """测试Qt版本"""
    print("ℹ️  检查Qt版本信息...")
    
    try:
        from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        print(f"Qt版本: {QT_VERSION_STR}")
        print(f"PyQt5版本: {PYQT_VERSION_STR}")
        
        # 检查qRegisterMetaType
        try:
            from PyQt5.QtCore import qRegisterMetaType
            print("✅ 支持qRegisterMetaType")
        except ImportError:
            print("⚠️  不支持qRegisterMetaType（使用兼容模式）")
        
        return True
        
    except Exception as e:
        print(f"❌ 版本检查失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始简单Qt测试...\n")
    
    success = True
    
    # 测试Qt版本
    if not test_qt_version():
        success = False
    
    print()
    
    # 测试基本Qt功能
    if not test_basic_qt():
        success = False
    
    print()
    
    # 测试pyqtgraph
    if not test_pyqtgraph():
        success = False
    
    print()
    
    if success:
        print("🎉 所有基础测试通过！")
        print("\n💡 下一步:")
        print("1. 运行完整测试: python test_qt_fix.py")
        print("2. 启动主程序: uv run python main.py")
        return 0
    else:
        print("❌ 部分测试失败")
        print("\n🔧 建议:")
        print("1. 重新安装依赖: rm -rf .venv && uv sync")
        print("2. 检查PyQt5版本: pip show PyQt5")
        return 1

if __name__ == "__main__":
    sys.exit(main())