#!/usr/bin/env python3
"""
测试零位录制工作流程
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """测试零位录制工作流程"""
    print("🧪 测试零位录制工作流程...")
    
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    from core.zero_position_manager import get_zero_position_manager
    
    # 获取零位管理器
    zero_manager = get_zero_position_manager()
    
    print("📊 测试流程:")
    
    # 1. 录制新零位
    print("\n1️⃣ 录制新零位...")
    test_positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    success = zero_manager.record_current_positions(
        test_positions, "workflow_test", "工作流程测试零位"
    )
    print(f"   录制结果: {'成功' if success else '失败'}")
    
    # 2. 检查当前零位
    current_zero = zero_manager.get_zero_positions()
    print(f"   当前零位: {current_zero}")
    
    # 3. 测试微调
    print("\n2️⃣ 测试微调...")
    original_pos_0 = current_zero[0]
    success = zero_manager.adjust_zero_position(0, 50)  # 关节0增加50
    print(f"   微调结果: {'成功' if success else '失败'}")
    
    adjusted_zero = zero_manager.get_zero_positions()
    print(f"   微调前关节0: {original_pos_0}")
    print(f"   微调后关节0: {adjusted_zero[0]}")
    print(f"   微调是否生效: {adjusted_zero[0] == original_pos_0 + 50}")
    
    # 4. 测试加载其他零位集合
    print("\n3️⃣ 测试加载零位集合...")
    zero_sets = zero_manager.get_zero_position_sets()
    print(f"   可用零位集合: {list(zero_sets.keys())}")
    
    if len(zero_sets) > 1:
        # 加载第一个不同的零位集合
        other_set = None
        for set_name in zero_sets.keys():
            if set_name != "workflow_test":
                other_set = set_name
                break
        
        if other_set:
            print(f"   加载零位集合: {other_set}")
            success = zero_manager.load_zero_position_set(other_set)
            print(f"   加载结果: {'成功' if success else '失败'}")
            
            loaded_zero = zero_manager.get_zero_positions()
            print(f"   加载后零位: {loaded_zero}")
            
            # 再次加载回测试零位
            print(f"   重新加载测试零位: workflow_test")
            success = zero_manager.load_zero_position_set("workflow_test")
            print(f"   重新加载结果: {'成功' if success else '失败'}")
            
            final_zero = zero_manager.get_zero_positions()
            print(f"   最终零位: {final_zero}")
    
    print("\n✅ 工作流程测试完成")
    
    print("\n📋 使用说明:")
    print("1. 录制新零位后，该零位自动成为当前零位")
    print("2. 微调零位后，调整会保存到当前零位")
    print("3. 要使用其他零位集合，需要点击'应用为当前零位'按钮")
    print("4. '全部回零'始终使用当前零位")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())