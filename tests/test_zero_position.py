#!/usr/bin/env python3
"""
零位录制功能测试

测试零位管理器和零位录制面板的功能
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def test_zero_position_manager():
    """测试零位管理器"""
    print("🧪 测试零位管理器...")
    
    from core.zero_position_manager import get_zero_position_manager
    
    # 获取零位管理器
    zero_manager = get_zero_position_manager()
    
    # 测试默认零位
    default_positions = zero_manager.get_zero_positions()
    print(f"默认零位: {default_positions}")
    
    # 测试录制零位
    test_positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    success = zero_manager.record_current_positions(
        test_positions, "test_zero", "测试零位"
    )
    print(f"录制零位: {'成功' if success else '失败'}")
    
    # 测试获取录制的零位
    recorded_positions = zero_manager.get_zero_positions()
    print(f"录制的零位: {recorded_positions}")
    
    # 测试微调
    success = zero_manager.adjust_zero_position(0, 50)
    print(f"微调关节0: {'成功' if success else '失败'}")
    
    adjusted_positions = zero_manager.get_zero_positions()
    print(f"微调后零位: {adjusted_positions}")
    
    # 测试零位集合
    zero_sets = zero_manager.get_zero_position_sets()
    print(f"零位集合: {list(zero_sets.keys())}")
    
    print("✅ 零位管理器测试完成")

def test_zero_position_ui():
    """测试零位录制UI"""
    print("🎨 测试零位录制UI...")
    
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
    
    # 模拟当前位置更新
    test_positions = [150, 250, 350, 450, 550, 650, 750, 850, 950, 1050]
    panel.update_current_positions(test_positions)
    
    print("✅ 零位录制UI创建成功")
    print("💡 请在UI中测试零位录制功能")
    
    # 运行应用程序
    return app.exec_()

def main():
    """主函数"""
    print("🚀 零位录制功能测试")
    print("=" * 50)
    
    # 测试零位管理器
    test_zero_position_manager()
    
    print()
    
    # 测试UI（可选）
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--ui":
        return test_zero_position_ui()
    else:
        print("💡 使用 --ui 参数测试UI界面")
        return 0

if __name__ == "__main__":
    sys.exit(main())