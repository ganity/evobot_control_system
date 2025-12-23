#!/usr/bin/env python3
"""
测试数据接收

验证我们是否真的接收到了机器人状态数据
"""

import sys
import os
sys.path.append('src')

import time
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler
from hardware.device_monitor import create_device_monitor
from utils.message_bus import get_message_bus, Topics

def test_data_reception():
    """测试数据接收"""
    print("🔍 测试数据接收...")
    
    # 获取组件
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    message_bus = get_message_bus()
    
    # 数据统计
    received_frames = []
    robot_state_messages = []
    
    def on_robot_state(message):
        """机器人状态消息回调"""
        robot_state_messages.append(message)
        print(f"📥 接收到机器人状态消息: {message.data}")
    
    def on_serial_data(data):
        """串口数据回调"""
        try:
            parsed_frames = protocol_handler.parse_received_data(data)
            received_frames.extend(parsed_frames)
            if parsed_frames:
                print(f"📥 解析到 {len(parsed_frames)} 个帧")
                for frame in parsed_frames:
                    if frame['type'] == 'status' and frame['data']:
                        robot_status = frame['data']
                        print(f"   {robot_status.frame_type.name}: {len(robot_status.joints)}个关节")
                        for joint in robot_status.joints:
                            print(f"     关节{joint.joint_id}: 位置={joint.position}, 速度={joint.velocity}, 电流={joint.current}")
        except Exception as e:
            print(f"❌ 数据解析错误: {e}")
    
    # 订阅消息
    message_bus.subscribe(Topics.ROBOT_STATE, on_robot_state)
    
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
        
        # 设置数据回调
        serial_manager.set_data_received_callback(on_serial_data)
        
        # 创建设备监控器
        device_monitor = create_device_monitor(serial_manager, protocol_handler)
        device_monitor.start()
        print("✅ 设备监控器已启动")
        
        # 等待数据
        print("等待数据接收，持续15秒...")
        start_time = time.time()
        
        while time.time() - start_time < 15:
            # 每3秒显示一次统计
            if int((time.time() - start_time) / 3) != int((time.time() - start_time - 0.1) / 3):
                elapsed = int(time.time() - start_time)
                print(f"⏱️  {elapsed}s: 原始帧={len(received_frames)}, 状态消息={len(robot_state_messages)}")
            
            time.sleep(0.1)
        
        # 停止监控
        device_monitor.stop()
        serial_manager.disconnect()
        
        # 分析结果
        print(f"\n📊 数据接收测试结果:")
        print(f"   原始帧数: {len(received_frames)}")
        print(f"   状态消息数: {len(robot_state_messages)}")
        
        # 分析帧类型
        frame_types = {}
        for frame in received_frames:
            if frame['type'] == 'status' and frame['data']:
                frame_type = frame['data'].frame_type.name
                frame_types[frame_type] = frame_types.get(frame_type, 0) + 1
        
        for frame_type, count in frame_types.items():
            print(f"   {frame_type}: {count} 帧")
        
        # 检查是否有位置数据
        has_position_data = False
        if robot_state_messages:
            last_message = robot_state_messages[-1]
            if 'data' in last_message.data and last_message.data['data']:
                robot_status = last_message.data['data']
                if robot_status.joints:
                    has_position_data = True
                    print(f"\n📍 最新位置数据:")
                    for joint in robot_status.joints:
                        print(f"   关节{joint.joint_id}: {joint.position}")
        
        # 判断成功
        success = len(received_frames) > 0 and len(robot_state_messages) > 0
        
        if success:
            print("✅ 数据接收正常")
            if has_position_data:
                print("✅ 位置数据有效")
            else:
                print("⚠️  位置数据可能无效")
        else:
            print("❌ 数据接收失败")
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

if __name__ == "__main__":
    print("🚀 开始测试数据接收...")
    
    result = test_data_reception()
    
    if result:
        print("🎉 数据接收测试通过")
    else:
        print("⚠️  数据接收存在问题")