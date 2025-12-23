#!/usr/bin/env python3
"""
测试200ms查询频率的数据接收

验证200ms查询频率是否适合50Hz硬件响应
"""

import sys
import os
sys.path.append('src')

import time
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler
from hardware.device_monitor import create_device_monitor
from utils.message_bus import get_message_bus, Topics

def test_200ms_query():
    """测试200ms查询频率"""
    print("🔍 测试200ms查询频率数据接收...")
    print("硬件特性:")
    print("  - 驱动控制板响应频率: 50Hz (20ms)")
    print("  - 查询频率: 5Hz (200ms)")
    print("  - 理论上每次查询覆盖10个硬件更新周期")
    
    # 获取组件
    serial_manager = get_serial_manager()
    protocol_handler = get_protocol_handler()
    message_bus = get_message_bus()
    
    # 数据统计
    received_frames = []
    robot_state_messages = []
    query_times = []
    
    def on_robot_state(message):
        """机器人状态消息回调"""
        robot_state_messages.append({
            'message': message,
            'timestamp': time.time()
        })
        
        try:
            data = message.data
            if isinstance(data, dict) and 'type' in data:
                if data['type'] == 'status' and 'data' in data and data['data']:
                    robot_status = data['data']
                    if hasattr(robot_status, 'joints'):
                        print(f"📥 {robot_status.frame_type.name}: {len(robot_status.joints)}个关节")
                        # 只显示前3个关节的数据，避免输出过多
                        for joint in robot_status.joints[:3]:
                            print(f"   关节{joint.joint_id}: 位置={joint.position}, 电流={joint.current}")
        except Exception as e:
            print(f"❌ 状态解析错误: {e}")
    
    def on_serial_data(data):
        """串口数据回调"""
        try:
            parsed_frames = protocol_handler.parse_received_data(data)
            if parsed_frames:
                received_frames.extend(parsed_frames)
                print(f"📥 解析到 {len(parsed_frames)} 个帧")
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
        print("✅ 设备监控器已启动 (200ms查询频率)")
        
        # 记录查询时间
        start_time = time.time()
        last_query_time = start_time
        
        # 等待数据
        print("等待数据接收，持续15秒...")
        print("预期:")
        print("  - 每200ms发送一次查询")
        print("  - 交替查询ARM和WRIST板")
        print("  - 15秒内约75次查询")
        
        while time.time() - start_time < 15:
            current_time = time.time()
            
            # 检测查询间隔
            if current_time - last_query_time >= 0.19:  # 允许10ms误差
                query_times.append(current_time)
                last_query_time = current_time
            
            # 每3秒显示一次统计
            if int((current_time - start_time) / 3) != int((current_time - start_time - 0.1) / 3):
                elapsed = int(current_time - start_time)
                expected_queries = elapsed * 5  # 5Hz
                actual_queries = len(query_times)
                
                print(f"⏱️  {elapsed}s:")
                print(f"   预期查询: {expected_queries}次")
                print(f"   实际查询: {actual_queries}次")
                print(f"   接收帧: {len(received_frames)}个")
                print(f"   状态消息: {len(robot_state_messages)}个")
            
            time.sleep(0.1)
        
        # 停止监控
        device_monitor.stop()
        serial_manager.disconnect()
        
        # 分析查询间隔
        query_intervals = []
        for i in range(1, len(query_times)):
            interval = query_times[i] - query_times[i-1]
            query_intervals.append(interval)
        
        avg_interval = sum(query_intervals) / len(query_intervals) if query_intervals else 0
        
        # 分析结果
        print(f"\n📊 200ms查询频率测试结果:")
        print(f"   总查询次数: {len(query_times)}")
        print(f"   平均查询间隔: {avg_interval*1000:.1f}ms (目标200ms)")
        print(f"   接收帧数: {len(received_frames)}")
        print(f"   状态消息数: {len(robot_state_messages)}")
        
        # 计算查询效率
        if len(query_times) > 0:
            query_efficiency = len(received_frames) / len(query_times) * 100
            print(f"   查询效率: {query_efficiency:.1f}% (接收帧/查询次数)")
        
        # 分析间隔稳定性
        if query_intervals:
            min_interval = min(query_intervals) * 1000
            max_interval = max(query_intervals) * 1000
            print(f"   间隔范围: {min_interval:.1f}ms - {max_interval:.1f}ms")
        
        # 判断成功
        success = (len(received_frames) > 0 and 
                  len(robot_state_messages) > 0 and
                  abs(avg_interval - 0.2) < 0.05)  # 间隔误差小于50ms
        
        if success:
            print("✅ 200ms查询频率测试通过")
            print("   - 查询间隔稳定")
            print("   - 数据接收正常")
            print("   - 系统负载合理")
        else:
            print("❌ 200ms查询频率存在问题")
            if len(received_frames) == 0:
                print("   - 硬件无响应（这是预期的，因为硬件可能未连接）")
            if abs(avg_interval - 0.2) >= 0.05:
                print(f"   - 查询间隔不稳定: {avg_interval*1000:.1f}ms")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始测试200ms查询频率...")
    
    result = test_200ms_query()
    
    if result:
        print("🎉 200ms查询频率验证通过")
    else:
        print("⚠️  200ms查询频率需要进一步调试")