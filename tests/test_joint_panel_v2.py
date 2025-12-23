#!/usr/bin/env python3
"""
测试关节控制面板v2的零位录制功能
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """测试关节控制面板v2"""
    print("🧪 测试关节控制面板v2的零位录制功能...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.joint_control_panel_v2 import OptimizedJointControlPanel
    from utils.config_manager import ConfigManager
    
    # 创建应用程序
    app = QApplication([])
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load_config()
    joints_config = config.get('joints', [])
    
    # 创建关节控制面板
    panel = OptimizedJointControlPanel(joints_config)
    panel.show()
    
    print("✅ 关节控制面板v2创建成功")
    print("💡 请检查是否有'📍 零位录制'按钮")
    print("💡 点击按钮测试零位录制面板的显示/隐藏")
    
    # 运行应用程序
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())