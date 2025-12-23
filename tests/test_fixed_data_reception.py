#!/usr/bin/env python3
"""
测试修复后的数据接收

验证修复后是否能正常接收机器人状态数据
"""

import sys
import os
sys.path.append('src')

import time
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler
from hardware.device_monitor import create_device_monitor
from utils.message_bus import get_message_bus, Topics

def test_fixed_data_reception():
    """测试修复后的数据接收"""
    print("🔍 测试修复后的数据接收...")
    print("修复内容:")
    print("  1. 串口超时从0.1s增加到10s")
    print("  2. 查询频率从200ms改为5ms")
    print("  3. 查询模式匹配参考实现")
    
    # 获取组件
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    message_bus = get_message_bus()
    
    # 数据统计
    received_frames = []
    robot_state_messages = []
    position_updates = {}
    
    def on_robot_state(message):
        """机器人状态消息回调"""
        robot_state_messages.append(message)
        
        # 提取位置信息
        try:
            data = message.data
            if isinstance(data, dict) and 'type' in data:
                if data['type'] == 'status' and 'data' in data and data['data']:
                    robot_status = data['data']
                    if hasattr(robot_status, 'joints'):
                        for joint in robot_status.joints:
                            joint_id = joint.joint_id
                            position_updates[joint_id] = {
                                'position': joint.position,
                                'velocity': joint.velocity,
                                'current': joint.current,
                                'timestamp': time.time()
                            }
                        
                        print(f"📥 {robot_status.frame_type.name}: {len(robot_status.joints)}个关节")
                        for joint in robot_status.joints:
                            print(f"   关节{joint.joint_id}: 位置={joint.position}, 速度={joint.velocity}, 电流={joint.current}")
        except Exception as e:
            print(f"❌ 状态解析错误: {e}")
    
    def on_serial_data(data):
        """串口数据回调"""
        try:
            parsed_frames = protocol_handler.parse_received_data(data)
            received_frames.extend(parsed_frames)
            if parsed_frames:
                print(f"📥 解析到 {len(parsed_frames)} 个帧，原始数据长度: {len(data)}")
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
        print("✅ 设备监控器已启动 (5ms查询频率)")
        
        # 等待数据
        print("等待数据接收，持续20秒...")
        start_time = time.time()
        last_report_time = start_time
        
        while time.time() - start_time < 20:
            current_time = time.time()
            
            # 每3秒显示一次统计
            if current_time - last_report_time >= 3:
                elapsed = int(current_time - start_time)
                print(f"⏱️  {elapsed}s: 原始帧={len(received_frames)}, 状态消息={len(robot_state_messages)}, 位置更新={len(position_updates)}")
                
                # 显示最新位置
                if position_updates:
                    print("   最新位置:")
                    for joint_id in sorted(position_updates.keys()):
                        pos_data = position_updates[joint_id]
                        age = current_time - pos_data['timestamp']
                        print(f"     关节{joint_id}: {pos_data['position']} (更新于{age:.1f}s前)")
                
                last_report_time = current_time
            
            time.sleep(0.1)
        
        # 停止监控
        device_monitor.stop()
        serial_manager.disconnect()
        
        # 分析结果
        print(f"\n📊 修复后数据接收测试结果:")
        print(f"   原始帧数: {len(received_frames)}")
        print(f"   状态消息数: {len(robot_state_messages)}")
        print(f"   位置更新关节数: {len(position_updates)}")
        
        # 分析帧类型
        frame_types = {}
        for frame in received_frames:
            if frame['type'] == 'status' and frame['data']:
                frame_type = frame['data'].frame_type.name
                frame_types[frame_type] = frame_types.get(frame_type, 0) + 1
        
        for frame_type, count in frame_types.items():
            print(f"   {frame_type}: {count} 帧")
        
        # 检查位置数据有效性
        valid_positions = 0
        for joint_id, pos_data in position_updates.items():
            if 0 <= pos_data['position'] <= 3000:  # 合理范围
                valid_positions += 1
        
        print(f"   有效位置数据: {valid_positions}/{len(position_updates)}")
        
        # 判断成功
        success = (len(received_frames) > 0 and 
                  len(robot_state_messages) > 0 and 
                  len(position_updates) >= 5)  # 至少5个关节有数据
        
        if success:
            print("✅ 修复成功！数据接收正常")
            if valid_positions >= len(position_updates) * 0.8:
                print("✅ 位置数据有效")
            else:
                print("⚠️  部分位置数据可能无效")
        else:
            print("❌ 修复后仍有问题")
            print("   可能原因:")
            print("   1. 硬件未连接或未上电")
            print("   2. 硬件不响应查询命令")
            print("   3. 协议解析仍有问题")
            print("   4. 需要进一步调试")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始测试修复后的数据接收...")
    
    result = test_fixed_data_reception()
    
    if result:
        print("🎉 修复验证通过")
    else:
        print("⚠️  修复后仍需进一步调试")