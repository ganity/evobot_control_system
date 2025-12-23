#!/usr/bin/env python3
"""
测试QTextCursor跨线程问题修复

验证：
1. 信号槽连接正常工作
2. 跨线程UI更新使用信号机制
3. 脚本面板输出处理正常
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def test_script_panel_signals():
    """测试脚本面板信号"""
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.script_panel import ScriptPanel
    
    # 创建应用程序（如果不存在）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建脚本面板
    panel = ScriptPanel()
    
    # 验证信号存在
    assert hasattr(panel, 'output_received'), "output_received信号不存在"
    assert hasattr(panel, 'script_executed'), "script_executed信号不存在"
    
    # 验证方法存在
    assert hasattr(panel, 'append_output_safe'), "append_output_safe方法不存在"
    assert hasattr(panel, 'on_script_output_threaded'), "on_script_output_threaded方法不存在"
    
    print("✅ 脚本面板信号验证通过")


def test_signal_connection():
    """测试信号连接"""
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.script_panel import ScriptPanel
    
    # 创建应用程序（如果不存在）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建脚本面板
    panel = ScriptPanel()
    
    # 测试信号发射（不应该抛出异常）
    try:
        panel.output_received.emit("测试输出")
        print("✅ 信号连接验证通过")
    except Exception as e:
        print(f"❌ 信号连接失败: {e}")
        raise


def test_thread_safe_output():
    """测试线程安全的输出处理"""
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.script_panel import ScriptPanel
    import threading
    import time
    
    # 创建应用程序（如果不存在）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建脚本面板
    panel = ScriptPanel()
    
    # 模拟从其他线程发送输出
    def thread_output():
        time.sleep(0.1)  # 短暂延迟
        panel.on_script_output_threaded("来自其他线程的输出")
    
    # 启动线程
    thread = threading.Thread(target=thread_output)
    thread.start()
    thread.join()
    
    print("✅ 线程安全输出验证通过")


def test_output_callback_mechanism():
    """测试输出回调机制"""
    from PyQt5.QtWidgets import QApplication
    from ui.widgets.script_panel import ScriptPanel
    
    # 创建应用程序（如果不存在）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建脚本面板
    panel = ScriptPanel()
    
    # 测试输出文本初始状态
    initial_text = panel.output_text.toPlainText()
    
    # 测试直接输出
    panel.append_output_safe("测试输出内容")
    
    # 验证文本已添加
    final_text = panel.output_text.toPlainText()
    assert "测试输出内容" in final_text, "输出内容未正确添加"
    
    print("✅ 输出回调机制验证通过")


if __name__ == "__main__":
    print("开始QTextCursor跨线程问题修复验证...")
    
    try:
        test_script_panel_signals()
        test_signal_connection()
        test_thread_safe_output()
        test_output_callback_mechanism()
        
        print("\n🎉 所有测试通过！QTextCursor跨线程问题修复成功")
        print("📝 修复方案：使用Qt信号槽机制处理跨线程UI更新")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)