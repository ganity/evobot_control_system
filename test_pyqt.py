#!/usr/bin/env python3
"""
PyQt5测试脚本 - 验证PyQt5是否正常工作
"""

import sys
import traceback

def test_pyqt5():
    """测试PyQt5基本功能"""
    print("=" * 50)
    print("PyQt5测试开始")
    print("=" * 50)
    
    try:
        print("1. 导入PyQt5模块...")
        from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
        from PyQt5.QtCore import Qt, QT_VERSION_STR
        from PyQt5.QtGui import QFont
        print(f"   ✅ PyQt5导入成功，版本: {QT_VERSION_STR}")
        
        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("   ✅ QApplication创建成功")
        
        print("3. 创建测试窗口...")
        window = QWidget()
        window.setWindowTitle("PyQt5测试窗口")
        window.setGeometry(100, 100, 300, 200)
        
        layout = QVBoxLayout()
        
        label = QLabel("PyQt5测试成功！")
        label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        label.setFont(font)
        
        button = QPushButton("关闭")
        button.clicked.connect(window.close)
        
        layout.addWidget(label)
        layout.addWidget(button)
        window.setLayout(layout)
        
        print("   ✅ 测试窗口创建成功")
        
        print("4. 显示窗口...")
        window.show()
        print("   ✅ 窗口显示成功")
        
        print("5. 启动事件循环...")
        print("   提示: 请关闭弹出的窗口以完成测试")
        
        exit_code = app.exec_()
        print(f"   ✅ 应用程序正常退出，退出代码: {exit_code}")
        
        print("=" * 50)
        print("PyQt5测试完成 - 所有功能正常")
        print("=" * 50)
        return True
        
    except ImportError as e:
        print(f"   ❌ 导入错误: {e}")
        print("   请检查PyQt5是否正确安装")
        return False
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        print("   详细错误信息:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pyqt5()
    sys.exit(0 if success else 1)