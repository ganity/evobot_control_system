#!/usr/bin/env python3
"""
测试录制功能修复

这个脚本用于测试录制和回放功能是否正常工作
"""

import sys
import os
import time
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, qRegisterMetaType

# 注册Qt元类型
qRegisterMetaType("QVector<int>")

def test_data_recorder():
    """测试数据录制器"""
    print("测试数据录制器...")
    
    try:
        from application.data_recorder import get_data_recorder, RecordingFormat
        
        recorder = get_data_recorder()
        
        # 配置录制
        success = recorder.configure_recording(
            sample_rate=10.0,  # 低采样率用于测试
            format=RecordingFormat.JSON,
            auto_save=True
        )
        
        if success:
            print("✅ 录制器配置成功")
        else:
            print("❌ 录制器配置失败")
            return False
        
        # 开始录制
        success = recorder.start_recording("测试录制", "这是一个测试录制")
        
        if success:
            print("✅ 录制开始成功")
        else:
            print("❌ 录制开始失败")
            return False
        
        # 等待一段时间
        print("录制中...")
        time.sleep(2)
        
        # 停止录制
        success = recorder.stop_recording()
        
        if success:
            print("✅ 录制停止成功")
        else:
            print("❌ 录制停止失败")
            return False
        
        # 列出录制文件
        recordings = recorder.list_recordings()
        print(f"✅ 找到 {len(recordings)} 个录制文件")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据录制器测试失败: {e}")
        return False

def test_data_player():
    """测试数据回放器"""
    print("\n测试数据回放器...")
    
    try:
        from application.data_player import get_data_player, PlaybackConfig, PlaybackMode
        from application.data_recorder import get_data_recorder
        
        recorder = get_data_recorder()
        player = get_data_player()
        
        # 获取最新的录制文件
        recordings = recorder.list_recordings()
        if not recordings:
            print("❌ 没有找到录制文件")
            return False
        
        latest_recording = recordings[0]
        session = recorder.load_session(latest_recording['filepath'])
        
        if not session:
            print("❌ 加载录制会话失败")
            return False
        
        print(f"✅ 加载会话成功: {session.name}")
        
        # 配置回放
        config = PlaybackConfig(
            mode=PlaybackMode.POSITION_ONLY,
            speed_factor=2.0,  # 2倍速回放
            sync_to_realtime=False
        )
        
        success = player.configure_playback(config)
        if success:
            print("✅ 回放器配置成功")
        else:
            print("❌ 回放器配置失败")
            return False
        
        # 加载会话
        success = player.load_session_for_playback(session)
        if success:
            print("✅ 会话加载成功")
        else:
            print("❌ 会话加载失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 数据回放器测试失败: {e}")
        return False

def test_ui_components():
    """测试UI组件"""
    print("\n测试UI组件...")
    
    try:
        app = QApplication(sys.argv)
        
        from ui.widgets.recording_panel import RecordingPanel
        
        # 创建录制面板
        panel = RecordingPanel()
        
        print("✅ 录制面板创建成功")
        
        # 测试刷新文件列表
        panel.refresh_file_list()
        print("✅ 文件列表刷新成功")
        
        app.quit()
        return True
        
    except Exception as e:
        print(f"❌ UI组件测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🔧 开始测试录制功能修复...")
    
    # 确保数据目录存在
    Path("data/recordings").mkdir(parents=True, exist_ok=True)
    
    # 测试数据录制器
    if not test_data_recorder():
        print("❌ 数据录制器测试失败")
        return 1
    
    # 测试数据回放器
    if not test_data_player():
        print("❌ 数据回放器测试失败")
        return 1
    
    # 测试UI组件
    if not test_ui_components():
        print("❌ UI组件测试失败")
        return 1
    
    print("\n🎉 所有测试通过！录制功能修复成功！")
    return 0

if __name__ == "__main__":
    sys.exit(main())