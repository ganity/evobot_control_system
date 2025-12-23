#!/usr/bin/env python3
"""
调试接收到的原始数据

分析硬件返回的数据格式
"""

import sys
import os
sys.path.append('src')

import time
import serial
import serial.tools.list_ports

def debug_received_data():
    """调试接收到的原始数据"""
    print("🔍 调试接收到的原始数据...")
    
    # 扫描端口
    ports = [port.device for port in serial.tools.list_ports.comports()]
    if not ports:
        print("❌ 没有找到可用端口")
        return False
    
    port_name = ports[0]
    print(f"使用端口: {port_name}")
    
    try:
        # 直接打开串口
        ser = serial.Serial(
            port=port_name,
            baudrate=1000000,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=10.0
        )
        
        print("✅ 串口连接成功")
        print("发送查询命令并分析返回数据...")
        
        # 发送查询命令
        query_arm = bytes([0xFD, 0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x01, 0x7B, 0xF8])
        query_wrist = bytes([0xFD, 0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x02, 0x7C, 0xF8])
        
        print(f"发送ARM查询: {query_arm.hex()}")
        ser.write(query_arm)
        time.sleep(0.1)
        
        # 检查响应
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"📥 ARM查询响应 ({len(data)} 字节): {data.hex()}")
            analyze_data(data, "ARM查询响应")
        else:
            print("❌ ARM查询无响应")
        
        time.sleep(0.2)
        
        print(f"发送WRIST查询: {query_wrist.hex()}")
        ser.write(query_wrist)
        time.sleep(0.1)
        
        # 检查响应
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"📥 WRIST查询响应 ({len(data)} 字节): {data.hex()}")
            analyze_data(data, "WRIST查询响应")
        else:
            print("❌ WRIST查询无响应")
        
        # 持续监听一段时间
        print("\n持续监听5秒...")
        start_time = time.time()
        all_data = []
        
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                all_data.append(data)
                print(f"📥 接收数据 ({len(data)} 字节): {data.hex()}")
                analyze_data(data, f"数据包{len(all_data)}")
            time.sleep(0.1)
        
        ser.close()
        
        # 总结
        total_bytes = sum(len(data) for data in all_data)
        print(f"\n📊 数据接收总结:")
        print(f"   总数据包: {len(all_data)}")
        print(f"   总字节数: {total_bytes}")
        
        if all_data:
            print("✅ 硬件正在响应")
            return True
        else:
            print("❌ 硬件无响应")
            return False
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_data(data: bytes, label: str):
    """分析数据格式"""
    print(f"  📋 {label} 分析:")
    print(f"     长度: {len(data)} 字节")
    print(f"     十六进制: {data.hex()}")
    print(f"     十进制: {list(data)}")
    
    # 查找可能的帧头帧尾
    frame_headers = []
    frame_tails = []
    
    for i, byte_val in enumerate(data):
        if byte_val == 0xFD:
            frame_headers.append(i)
        elif byte_val == 0xF8:
            frame_tails.append(i)
    
    if frame_headers:
        print(f"     帧头 (0xFD) 位置: {frame_headers}")
    if frame_tails:
        print(f"     帧尾 (0xF8) 位置: {frame_tails}")
    
    # 查找可能的帧类型
    frame_types = []
    for i, byte_val in enumerate(data):
        if byte_val in [0x73, 0x74]:  # ARM_STATUS, FINGER_STATUS
            frame_types.append((i, hex(byte_val)))
    
    if frame_types:
        print(f"     可能的帧类型: {frame_types}")
    
    # 检查是否符合预期格式
    if len(data) >= 3:
        if data[0] == 0xFD and data[-1] == 0xF8:
            print(f"     ✅ 符合帧格式 (帧头0xFD, 帧尾0xF8)")
        else:
            print(f"     ⚠️  不符合标准帧格式")
    
    print()

if __name__ == "__main__":
    print("🚀 开始调试接收数据...")
    
    result = debug_received_data()
    
    if result:
        print("🎉 数据接收调试完成")
    else:
        print("⚠️  数据接收调试发现问题")