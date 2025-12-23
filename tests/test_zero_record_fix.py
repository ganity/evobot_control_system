#!/usr/bin/env python3
"""
测试零位录制修复
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """测试零位录制修复"""
    print("🧪 测试零位录制修复...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.zero_position_panel import ZeroPositionPanel
    from utils.config_manager import ConfigManager
    
    # 创建应用程序
    app = QApplication([])
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load_config()
    joints_config = config.get('joints', [])
    
    # 创建零位录制面板
    panel = ZeroPositionPanel(joints_config)
    panel.show()
    panel.resize(900, 700)
    
    # 模拟当前位置
    test_positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    panel.update_current_positions(test_positions)
    
    print("✅ 零位录制面板已显示")
    print("🧪 测试说明:")
    print("1. 现在有两个录制按钮:")
    print("   - '📍 录制机器人位置': 录制机器人当前实际位置")
    print("   - '💾 保存零位设置': 保存当前零位设置（包含微调）")
    print("2. 微调零位后，使用'💾 保存零位设置'按钮保存微调结果")
    print("3. 如果要录制机器人实际位置，使用'📍 录制机器人位置'按钮")
    
    # 运行应用程序
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())