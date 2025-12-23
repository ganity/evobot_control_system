#!/usr/bin/env python3
"""
验证零位录制按钮是否正确添加
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """验证零位录制按钮"""
    print("🔍 验证零位录制按钮...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from PyQt5.QtWidgets import QApplication, QPushButton
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
    
    # 显示面板以便查看
    panel.show()
    panel.resize(800, 600)
    
    print("💡 面板已显示，请查看是否有零位录制按钮")
    
    # 检查零位录制按钮是否存在
    if hasattr(panel, 'zero_record_button'):
        button = panel.zero_record_button
        print(f"✅ 找到零位录制按钮: {button.text()}")
        print(f"   按钮类型: {type(button)}")
        print(f"   按钮可见: {button.isVisible()}")
        print(f"   按钮启用: {button.isEnabled()}")
        print(f"   按钮大小: {button.size()}")
        print(f"   按钮位置: {button.pos()}")
        
        # 强制显示按钮
        button.setVisible(True)
        button.show()
        
        # 检查零位面板是否存在
        if hasattr(panel, 'zero_position_panel'):
            zero_panel = panel.zero_position_panel
            print(f"✅ 找到零位录制面板: {type(zero_panel)}")
            print(f"   面板可见: {zero_panel.isVisible()}")
            
            print("🧪 测试按钮功能...")
            print("💡 请手动点击'📍 零位录制'按钮测试功能")
            
            # 运行应用程序让用户测试
            return app.exec_()
        else:
            print("❌ 未找到零位录制面板")
    else:
        print("❌ 未找到零位录制按钮")
        
        # 列出面板中的所有按钮
        buttons = panel.findChildren(QPushButton)
        print(f"面板中的所有按钮 ({len(buttons)}个):")
        for i, btn in enumerate(buttons):
            print(f"  {i+1}. {btn.text()} ({type(btn).__name__})")
            print(f"      可见: {btn.isVisible()}, 启用: {btn.isEnabled()}")
    
    print("🏁 验证完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())