#!/usr/bin/env python3
"""
测试查询系统

验证我们的实现是否能正确发送查询命令并接收数据
"""

import sys
import os
sys.path.append('src')

import time
import threading
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler
from hardware.device_monitor import create_device_monitor

def test_query_system():
    """测试查询系统"""
    print("🔍 测试查询系统...")
    
    # 获取组件
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    
    # 扫描端口
    ports = serial_manager.scan_ports()
    if not ports:
        print("❌ 没有找到可用端口")
        return False
    
    print(f"可用端口: {[p['device'] for p in ports]}")
    port_name = ports[0]['device']
    print(f"使用端口: {port_name}")
    
    # 数据统计
    received_frames = []
    query_count = 0
    
    def on_data_received(data):
        """数据接收回调"""
        nonlocal received_frames
        try:
            parsed_frames = protocol_handler.parse_received_data(data)
            received_frames.extend(parsed_frames)
            if parsed_frames:
                print(f"📥 接收到 {len(parsed_frames)} 个帧")
                for frame in parsed_frames:
                    if frame['type'] == 'status' and frame['data']:
                        robot_status = frame['data']
                        print(f"   {robot_status.frame_type.name}: {len(robot_status.joints)}个关节")
        except Exception as e:
            print(f"❌ 数据解析错误: {e}")
    
    # 设置回调
    serial_manager.set_data_received_callback(on_data_received)
    
    try:
        # 连接串口
        print("连接串口...")
        success = serial_manager.connect(port_name, 1000000)
        if not success:
            print("❌ 串口连接失败")
            return False
        
        print("✅ 串口连接成功")
        
        # 创建设备监控器（会自动开始查询）
        device_monitor = create_device_monitor(serial_manager, protocol_handler)
        device_monitor.start()
        
        print("✅ 设备监控器已启动")
        print("开始查询测试，持续10秒...")
        
        # 等待10秒，观察数据接收情况
        start_time = time.time()
        while time.time() - start_time < 10:
            time.sleep(0.1)
            
            # 每秒显示一次统计
            if int(time.time() - start_time) != int(time.time() - start_time - 0.1):
                elapsed = int(time.time() - start_time)
                print(f"⏱️  {elapsed}s: 已接收 {len(received_frames)} 个帧")
        
        # 停止监控
        device_monitor.stop()
        serial_manager.disconnect()
        
        # 统计结果
        print(f"\n📊 测试结果:")
        print(f"   总接收帧数: {len(received_frames)}")
        
        # 按帧类型统计
        frame_types = {}
        for frame in received_frames:
            if frame['type'] == 'status' and frame['data']:
                frame_type = frame['data'].frame_type.name
                frame_types[frame_type] = frame_types.get(frame_type, 0) + 1
        
        for frame_type, count in frame_types.items():
            print(f"   {frame_type}: {count} 帧")
        
        # 判断成功
        success = len(received_frames) > 0
        if success:
            print("✅ 查询系统工作正常")
        else:
            print("❌ 查询系统未接收到数据")
            print("   可能原因:")
            print("   1. 硬件未连接或未上电")
            print("   2. 硬件不响应查询命令")
            print("   3. 协议解析问题")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_manual_query():
    """手动发送查询命令测试"""
    print("\n🔍 手动查询测试...")
    
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    
    # 扫描端口
    ports = serial_manager.scan_ports()
    if not ports:
        print("❌ 没有找到可用端口")
        return False
    
    port_name = ports[0]['device']
    
    received_data = []
    
    def on_data_received(data):
        received_data.append(data)
        print(f"📥 接收原始数据: {len(data)} 字节 - {data.hex()}")
    
    serial_manager.set_data_received_callback(on_data_received)
    
    try:
        # 连接串口
        success = serial_manager.connect(port_name, 1000000)
        if not success:
            print("❌ 串口连接失败")
            return False
        
        print("✅ 串口连接成功")
        
        # 手动发送查询命令
        from hardware.protocol_handler import BoardID
        
        print("发送手臂状态查询...")
        arm_query = protocol_handler.encode_query_command(BoardID.ARM_BOARD)
        print(f"查询命令: {arm_query.hex()}")
        serial_manager.send_data(arm_query)
        
        time.sleep(0.1)
        
        print("发送手腕状态查询...")
        wrist_query = protocol_handler.encode_query_command(BoardID.WRIST_BOARD)
        print(f"查询命令: {wrist_query.hex()}")
        serial_manager.send_data(wrist_query)
        
        # 等待响应
        print("等待响应...")
        time.sleep(2)
        
        serial_manager.disconnect()
        
        print(f"📊 接收到 {len(received_data)} 个数据包")
        total_bytes = sum(len(data) for data in received_data)
        print(f"📊 总字节数: {total_bytes}")
        
        return len(received_data) > 0
        
    except Exception as e:
        print(f"❌ 手动查询测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试查询系统...")
    
    # 测试自动查询系统
    result1 = test_query_system()
    
    # 测试手动查询
    result2 = test_manual_query()
    
    print(f"\n📊 测试总结:")
    print(f"   自动查询系统: {'✅ 通过' if result1 else '❌ 失败'}")
    print(f"   手动查询测试: {'✅ 通过' if result2 else '❌ 失败'}")
    
    if result1 or result2:
        print("🎉 查询系统基本工作正常")
    else:
        print("⚠️  查询系统可能存在问题，建议检查硬件连接")