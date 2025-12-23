#!/usr/bin/env python3
"""
测试原始串口数据接收

直接测试串口是否能接收到任何数据
"""

import sys
import os
sys.path.append('src')

import time
import serial
import serial.tools.list_ports

def test_raw_serial_reception():
    """测试原始串口数据接收"""
    print("🔍 测试原始串口数据接收...")
    
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
        print("等待接收数据，持续10秒...")
        
        # 发送一些查询命令（参考实现格式）
        query_arm = bytes([0xFD, 0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x01, 0x7B, 0xF8])
        query_wrist = bytes([0xFD, 0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x02, 0x7C, 0xF8])
        
        start_time = time.time()
        received_data = []
        
        while time.time() - start_time < 10:
            # 发送查询命令
            if int((time.time() - start_time) * 200) % 4 == 2:  # 每5ms，每4个周期发送一次
                ser.write(query_arm)
                print("发送手臂查询")
            elif int((time.time() - start_time) * 200) % 4 == 3:
                ser.write(query_wrist)
                print("发送手腕查询")
            
            # 检查接收数据
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                received_data.append(data)
                print(f"📥 接收到 {len(data)} 字节: {data.hex()}")
            
            time.sleep(0.005)  # 5ms
        
        ser.close()
        
        # 分析结果
        total_bytes = sum(len(data) for data in received_data)
        print(f"\n📊 原始串口测试结果:")
        print(f"   接收数据包数: {len(received_data)}")
        print(f"   总接收字节数: {total_bytes}")
        
        if received_data:
            print("✅ 串口能够接收数据")
            print("   接收到的数据:")
            for i, data in enumerate(received_data[:5]):  # 显示前5包
                print(f"     包{i+1}: {data.hex()}")
            if len(received_data) > 5:
                print(f"     ... 还有 {len(received_data) - 5} 包数据")
        else:
            print("❌ 串口未接收到任何数据")
            print("   可能原因:")
            print("   1. 硬件未连接或未上电")
            print("   2. 硬件不响应查询命令")
            print("   3. 波特率不匹配")
            print("   4. 硬件需要特殊初始化")
        
        return len(received_data) > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始测试原始串口数据接收...")
    
    result = test_raw_serial_reception()
    
    if result:
        print("🎉 原始串口接收测试通过")
    else:
        print("⚠️  原始串口接收存在问题")