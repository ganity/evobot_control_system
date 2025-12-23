#!/usr/bin/env python3
"""
调试零位录制功能
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """调试零位录制功能"""
    print("🔍 调试零位录制功能...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from core.zero_position_manager import get_zero_position_manager
    
    # 获取零位管理器
    zero_manager = get_zero_position_manager()
    
    print("📊 当前零位管理器状态:")
    print(f"   当前零位数量: {len(zero_manager.current_zero_positions)}")
    print(f"   零位集合数量: {len(zero_manager.zero_position_sets)}")
    
    # 显示所有零位集合
    zero_sets = zero_manager.get_zero_position_sets()
    print(f"   零位集合列表: {list(zero_sets.keys())}")
    
    # 测试录制新零位
    print("\n🧪 测试录制新零位...")
    test_positions = [111, 222, 333, 444, 555, 666, 777, 888, 999, 1111]
    success = zero_manager.record_current_positions(
        test_positions, "debug_test", "调试测试零位"
    )
    print(f"   录制结果: {'成功' if success else '失败'}")
    
    # 检查录制后的状态
    zero_sets_after = zero_manager.get_zero_position_sets()
    print(f"   录制后零位集合: {list(zero_sets_after.keys())}")
    
    # 测试加载不同的零位集合
    if len(zero_sets_after) > 1:
        set_names = list(zero_sets_after.keys())
        first_set = set_names[0]
        second_set = set_names[1]
        
        print(f"\n🧪 测试加载零位集合...")
        print(f"   当前零位: {zero_manager.get_zero_positions()}")
        
        # 加载第一个集合
        success1 = zero_manager.load_zero_position_set(first_set)
        print(f"   加载 '{first_set}': {'成功' if success1 else '失败'}")
        print(f"   加载后零位: {zero_manager.get_zero_positions()}")
        
        # 加载第二个集合
        success2 = zero_manager.load_zero_position_set(second_set)
        print(f"   加载 '{second_set}': {'成功' if success2 else '失败'}")
        print(f"   加载后零位: {zero_manager.get_zero_positions()}")
    
    print("\n✅ 调试完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())