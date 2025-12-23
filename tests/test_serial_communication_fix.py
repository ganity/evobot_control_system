#!/usr/bin/env python3
"""
测试串口通信修复

验证：
1. 方法名错误修复
2. 状态回调错误修复
3. 数据接收处理
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def test_method_name_fix():
    """测试方法名修复"""
    from core.motion_controller import get_motion_controller
    
    controller = get_motion_controller()
    
    # 验证move_joint方法存在
    assert hasattr(controller, 'move_joint'), "move_joint方法不存在"
    
    # 验证方法签名
    import inspect
    sig = inspect.signature(controller.move_joint)
    params = list(sig.parameters.keys())
    
    expected_params = ['joint_id', 'position', 'duration']
    for param in expected_params:
        assert param in params, f"缺少参数: {param}"
    
    print("✅ 方法名修复验证通过")


def test_status_callback_fix():
    """测试状态回调修复"""
    from ui.main_window import MainWindow
    from utils.config_manager import ConfigManager
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 验证on_status_updated方法签名
    import inspect
    sig = inspect.signature(MainWindow.on_status_updated)
    params = list(sig.parameters.keys())
    
    # 应该有self和status参数
    assert 'self' in params, "缺少self参数"
    assert 'status' in params, "缺少status参数"
    
    # 检查参数类型注解
    annotations = sig.parameters['status'].annotation
    assert 'Dict' in str(annotations), f"status参数类型应为Dict，实际为: {annotations}"
    
    print("✅ 状态回调修复验证通过")


def test_data_processing():
    """测试数据处理功能"""
    from hardware.protocol_handler import get_protocol_handler
    
    protocol_handler = get_protocol_handler()
    
    # 验证parse_received_data方法存在
    assert hasattr(protocol_handler, 'parse_received_data'), "parse_received_data方法不存在"
    
    # 测试空数据
    result = protocol_handler.parse_received_data(b'')
    assert isinstance(result, list), "返回值应为列表"
    assert len(result) == 0, "空数据应返回空列表"
    
    # 测试无效数据
    result = protocol_handler.parse_received_data(b'\x01\x02\x03')
    assert isinstance(result, list), "返回值应为列表"
    
    print("✅ 数据处理功能验证通过")


def test_device_monitor_message_handling():
    """测试设备监控器消息处理"""
    from hardware.device_monitor import DeviceMonitor
    from hardware.serial_manager import SerialManager
    from hardware.protocol_handler import get_protocol_handler
    from utils.message_bus import Message, MessagePriority
    
    # 创建组件
    serial_manager = SerialManager()
    protocol_handler = get_protocol_handler()
    monitor = DeviceMonitor(serial_manager, protocol_handler)
    
    # 验证_on_robot_state方法存在
    assert hasattr(monitor, '_on_robot_state'), "_on_robot_state方法不存在"
    
    # 测试消息处理（不会抛出异常）
    test_message = Message(
        topic="robot_state",
        data={'type': 'status', 'data': None, 'timestamp': 0},
        priority=MessagePriority.NORMAL,
        timestamp=0
    )
    
    try:
        monitor._on_robot_state(test_message)
        print("✅ 设备监控器消息处理验证通过")
    except Exception as e:
        print(f"❌ 设备监控器消息处理失败: {e}")
        raise


if __name__ == "__main__":
    print("开始串口通信修复验证...")
    
    try:
        test_method_name_fix()
        test_status_callback_fix()
        test_data_processing()
        test_device_monitor_message_handling()
        
        print("\n🎉 所有测试通过！串口通信修复成功")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)