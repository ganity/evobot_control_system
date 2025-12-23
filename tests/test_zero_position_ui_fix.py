#!/usr/bin/env python3
"""
测试零位录制UI修复
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """测试零位录制UI修复"""
    print("🧪 测试零位录制UI修复...")
    
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
    panel.resize(800, 600)
    
    # 模拟当前位置
    test_positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    panel.update_current_positions(test_positions)
    
    print("✅ 零位录制面板已显示")
    print("🧪 测试步骤:")
    print("1. 输入新的零位名称（如 'test_new'）")
    print("2. 点击'录制为零位'按钮")
    print("3. 检查下拉框是否自动选中新录制的零位")
    print("4. 选择其他零位集合，点击'加载'")
    print("5. 检查下拉框是否保持选中的零位集合")
    
    # 运行应用程序
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())