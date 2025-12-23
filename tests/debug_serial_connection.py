#!/usr/bin/env python3
"""
调试串口连接问题

对比参考实现，检查：
1. 串口参数设置
2. 数据接收流程
3. 协议解析
"""

import sys
import os
sys.path.append('src')

import serial
import serial.tools.list_ports
import time
import threading

def test_reference_style_connection():
    """使用参考实现的方式测试串口连接"""
    print("=== 使用参考实现方式测试串口连接 ===")
    
    # 扫描端口
    ports = [port.device for port in serial.tools.list_ports.comports()]
    print(f"可用端口: {ports}")
    
    if not ports:
        print("❌ 没有找到可用端口")
        return False
    
    # 选择第一个端口进行测试
    port_name = ports[0]
    print(f"测试端口: {port_name}")
    
    try:
        # 使用参考实现的参数
        baudrate = 1000000
        timeout = 10
        
        ser = serial.Serial(
            port=port_name, 
            baudrate=baudrate, 
            bytesize=8, 
            parity='N', 
            stopbits=1, 
            timeout=timeout
        )
        
        # 设置缓冲区
        if hasattr(ser, 'set_buffer_size'):
            ser.set_buffer_size(rx_size=12000, tx_size=12000)
            print("✅ 缓冲区设置成功")
        else:
            print("⚠️  不支持缓冲区设置")
        
        print(f"✅ 串口连接成功: {port_name}")
        print(f"   波特率: {baudrate}")
        print(f"   超时: {timeout}s")
        print(f"   是否打开: {ser.is_open}")
        
        # 测试数据接收
        print("\n开始监听数据...")
        start_time = time.time()
        data_count = 0
        
        while time.time() - start_time < 5:  # 监听5秒
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_count += len(data)
                print(f"📥 接收到 {len(data)} 字节数据: {data.hex()}")
            time.sleep(0.01)
        
        print(f"\n📊 5秒内总共接收到 {data_count} 字节数据")
        
        ser.close()
        return data_count > 0
        
    except Exception as e:
        print(f"❌ 串口连接失败: {e}")
        return False

def test_our_implementation():
    """测试我们的实现"""
    print("\n=== 测试我们的实现 ===")
    
    try:
        from hardware.serial_manager import get_serial_manager, SerialConfig
        
        # 扫描端口
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if not ports:
            print("❌ 没有找到可用端口")
            return False
        
        port_name = ports[0]
        print(f"测试端口: {port_name}")
        
        # 获取串口管理器
        serial_manager = get_serial_manager()
        
        # 设置数据接收回调
        received_data = []
        def data_callback(data):
            received_data.append(data)
            print(f"📥 我们的实现接收到 {len(data)} 字节: {data.hex()}")
        
        serial_manager.set_data_received_callback(data_callback)
        
        # 连接串口
        success = serial_manager.connect(port_name, 1000000)
        if success:
            print("✅ 我们的实现连接成功")
            
            # 等待数据
            print("监听数据5秒...")
            time.sleep(5)
            
            print(f"📊 总共接收到 {len(received_data)} 个数据包")
            total_bytes = sum(len(data) for data in received_data)
            print(f"📊 总字节数: {total_bytes}")
            
            serial_manager.disconnect()
            return len(received_data) > 0
        else:
            print("❌ 我们的实现连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试我们的实现失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_protocol_parsing():
    """测试协议解析"""
    print("\n=== 测试协议解析 ===")
    
    try:
        from hardware.protocol_handler import get_protocol_handler
        
        # 模拟一个完整的帧数据（参考实现的格式）
        # 帧头(0xfd) + 数据 + 校验 + 帧尾(0xf8)
        test_frame = bytes([
            0xfd,  # 帧头
            0x00, 0x2c, 0x02, 0x01, 0x00, 0x74,  # 帧数据
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06,  # 模拟关节数据
            0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c,
            0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12,
            0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
            0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e,
            0x1f, 0x20, 0x21, 0x22, 0x23, 0x24,
            0x25, 0x26,  # 更多数据
            0x00,  # 校验和占位符
            0xf8   # 帧尾
        ])
        
        protocol_handler = get_protocol_handler()
        
        print(f"测试帧长度: {len(test_frame)} 字节")
        print(f"测试帧数据: {test_frame.hex()}")
        
        # 解析数据
        parsed_frames = protocol_handler.parse_received_data(test_frame)
        
        print(f"解析结果: {len(parsed_frames)} 个帧")
        for i, frame in enumerate(parsed_frames):
            print(f"  帧 {i+1}: {frame}")
        
        return len(parsed_frames) > 0
        
    except Exception as e:
        print(f"❌ 协议解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 开始串口连接调试...")
    
    results = []
    
    # 测试参考实现方式
    results.append(test_reference_style_connection())
    
    # 测试我们的实现
    results.append(test_our_implementation())
    
    # 测试协议解析
    results.append(test_protocol_parsing())
    
    # 总结
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if results[0] and not results[1]:
        print("🔍 分析：参考实现能接收数据，我们的实现不能")
        print("   可能原因：")
        print("   1. 数据接收线程逻辑问题")
        print("   2. 回调机制问题")
        print("   3. 缓冲区处理问题")
    elif not results[0]:
        print("🔍 分析：串口本身可能没有数据传输")
        print("   建议：")
        print("   1. 检查硬件连接")
        print("   2. 确认设备是否在发送数据")
        print("   3. 尝试其他串口工具验证")
    
    print("\n🔧 建议的修复方向：")
    print("1. 对齐串口参数（超时时间、缓冲区）")
    print("2. 优化数据接收线程逻辑")
    print("3. 添加更详细的调试日志")
    print("4. 实现帧同步机制")