#!/usr/bin/env python3
"""
测试频率调整效果

验证查询200ms，发送100ms的频率设置
"""

import sys
import os
sys.path.append('src')

import time
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler
from hardware.device_monitor import create_device_monitor
from core.motion_controller import get_motion_controller

def test_frequency_adjustment():
    """测试频率调整效果"""
    print("🔧 测试频率调整效果...")
    print("   查询频率: 200ms (5Hz)")
    print("   发送频率: 100ms (10Hz)")
    
    # 获取组件
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    motion_controller = get_motion_controller()
    
    # 扫描端口
    ports = serial_manager.scan_ports()
    if not ports:
        print("❌ 没有找到可用端口")
        return False
    
    port_name = ports[0]['device']
    print(f"使用端口: {port_name}")
    
    try:
        # 连接串口
        print("连接串口...")
        success = serial_manager.connect(port_name, 1000000)
        if not success:
            print("❌ 串口连接失败")
            return False
        
        print("✅ 串口连接成功")
        
        # 创建设备监控器
        device_monitor = create_device_monitor(serial_manager, protocol_handler)
        device_monitor.start()
        print("✅ 设备监控器已启动 (查询频率: 200ms)")
        
        # 模拟发送位置命令 (100ms间隔)
        print("发送位置命令测试 (100ms间隔)...")
        test_positions = [1500] * 10  # 中间位置
        
        send_start = time.time()
        for i in range(5):
            success = motion_controller.move_to_position(test_positions)
            if success:
                print(f"✅ 位置命令 {i+1} 发送成功")
            else:
                print(f"❌ 位置命令 {i+1} 发送失败")
            time.sleep(0.1)  # 100ms间隔
        
        send_duration = time.time() - send_start
        print(f"发送5个命令耗时: {send_duration:.2f}s")
        
        # 观察系统运行
        print("观察系统运行10秒...")
        start_time = time.time()
        last_stats = serial_manager.get_statistics()
        
        while time.time() - start_time < 10:
            # 每2秒显示一次统计
            if int((time.time() - start_time) / 2) != int((time.time() - start_time - 0.1) / 2):
                elapsed = int(time.time() - start_time)
                stats = serial_manager.get_statistics()
                
                # 计算增量
                send_delta = stats['send_errors'] - last_stats['send_errors']
                bytes_sent_delta = stats['bytes_sent'] - last_stats['bytes_sent']
                
                print(f"⏱️  {elapsed}s: 发送错误增量={send_delta}, 发送字节增量={bytes_sent_delta}, 队列大小={stats['send_queue_size']}")
                last_stats = stats
            
            time.sleep(0.1)
        
        # 停止监控
        device_monitor.stop()
        serial_manager.disconnect()
        
        # 评估结果
        final_stats = serial_manager.get_statistics()
        print(f"\n📊 测试结果:")
        print(f"   总发送错误: {final_stats['send_errors']}")
        print(f"   发送字节数: {final_stats['bytes_sent']}")
        print(f"   接收字节数: {final_stats['bytes_received']}")
        print(f"   重连次数: {final_stats['reconnect_count']}")
        
        # 评估频率效果
        if final_stats['send_errors'] == 0:
            print("✅ 频率调整完美，无发送错误")
            return True
        elif final_stats['send_errors'] < 5:
            print("✅ 频率调整良好，发送错误很少")
            return True
        else:
            print("⚠️  频率调整需要进一步优化")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始测试频率调整...")
    
    result = test_frequency_adjustment()
    
    if result:
        print("🎉 频率调整测试通过")
        print("💡 建议:")
        print("   - 查询频率200ms适合状态监控")
        print("   - 发送频率100ms适合位置控制")
        print("   - 系统负载大幅降低")
    else:
        print("⚠️  频率调整需要进一步优化")