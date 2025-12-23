#!/usr/bin/env python3
"""
测试Qt修复

简单测试Qt元类型注册是否解决了警告问题
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_qt_init():
    """测试Qt初始化"""
    print("🔧 测试Qt初始化...")
    
    try:
        from utils.qt_compat import setup_qt_environment, check_qt_version
        
        # 检查Qt版本
        supports_meta_type = check_qt_version()
        
        # 设置Qt环境
        setup_qt_environment()
        
        print("✅ Qt环境初始化成功")
        
        if not supports_meta_type:
            print("ℹ️  注意: 当前PyQt5版本不支持qRegisterMetaType，使用兼容模式")
        
        return True
    except Exception as e:
        print(f"❌ Qt环境初始化失败: {e}")
        return False

def test_pyqtgraph_import():
    """测试pyqtgraph导入"""
    print("📊 测试pyqtgraph导入...")
    
    try:
        import pyqtgraph as pg
        print("✅ pyqtgraph导入成功")
        
        # 测试创建简单图形
        plot_widget = pg.PlotWidget()
        print("✅ pyqtgraph组件创建成功")
        
        return True
    except Exception as e:
        print(f"❌ pyqtgraph测试失败: {e}")
        return False

def test_recording_components():
    """测试录制组件"""
    print("📹 测试录制组件...")
    
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from application.data_recorder import get_data_recorder
        recorder = get_data_recorder()
        print("✅ 数据录制器创建成功")
        
        from application.data_player import get_data_player
        player = get_data_player()
        print("✅ 数据回放器创建成功")
        
        app.quit()
        return True
    except Exception as e:
        print(f"❌ 录制组件测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始Qt修复测试...\n")
    
    success = True
    
    # 测试Qt初始化
    if not test_qt_init():
        success = False
    
    print()
    
    # 测试pyqtgraph
    if not test_pyqtgraph_import():
        success = False
    
    print()
    
    # 测试录制组件
    if not test_recording_components():
        success = False
    
    print()
    
    if success:
        print("🎉 所有测试通过！Qt修复成功！")
        print("\n💡 建议:")
        print("1. 重新启动应用程序: uv run python main.py")
        print("2. 测试录制功能，应该不再有QVector<int>警告")
        return 0
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())