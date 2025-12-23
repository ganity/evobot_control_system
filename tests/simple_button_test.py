#!/usr/bin/env python3
"""
简单的按钮测试
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """简单测试"""
    print("🔍 简单按钮测试...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
    
    # 创建应用程序
    app = QApplication([])
    
    # 创建简单窗口
    window = QWidget()
    layout = QVBoxLayout(window)
    
    # 添加测试按钮
    test_button = QPushButton("📍 测试零位录制按钮")
    test_button.setStyleSheet("""
        QPushButton {
            background-color: #9C27B0;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #7B1FA2;
        }
    """)
    layout.addWidget(test_button)
    
    # 添加说明
    info_button = QPushButton("如果你能看到上面的紫色按钮，说明样式正常")
    layout.addWidget(info_button)
    
    window.setWindowTitle("零位录制按钮测试")
    window.resize(300, 150)
    window.show()
    
    print("✅ 测试窗口已显示")
    print("💡 如果能看到紫色的'📍 测试零位录制按钮'，说明按钮样式正常")
    
    # 运行应用程序
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())