#!/usr/bin/env python3
"""
测试简化版零位录制面板
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """测试简化版零位录制面板"""
    print("🧪 测试简化版零位录制面板...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.simple_zero_panel import SimpleZeroPositionPanel
    from utils.config_manager import ConfigManager
    
    # 创建应用程序
    app = QApplication([])
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load_config()
    joints_config = config.get('joints', [])
    
    # 创建简化版零位录制面板
    panel = SimpleZeroPositionPanel(joints_config)
    panel.show()
    panel.resize(400, 600)
    
    # 模拟当前位置
    test_positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    panel.update_current_positions(test_positions)
    
    print("✅ 简化版零位录制面板已显示")
    print("🎯 简化设计特点:")
    print("1. 清晰的操作流程提示")
    print("2. 三个主要按钮：读取位置 → 微调 → 保存零位")
    print("3. 统一的工作流程，避免混淆")
    print("4. 简洁的界面布局")
    
    print("\n📋 使用流程:")
    print("1. 手动调整机器人到理想零位")
    print("2. 点击'📖 读取位置'获取当前位置")
    print("3. 可选：点击'🛠 微调'进行精细调整")
    print("4. 点击'💾 保存零位'保存设置")
    print("5. 保存后自动成为当前零位，'全部回零'将使用此零位")
    
    # 运行应用程序
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())