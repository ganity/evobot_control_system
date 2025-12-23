#!/usr/bin/env python3
"""
EvoBot启动脚本

优化版本的启动脚本，包含详细的启动信息
"""

import sys
import time
from pathlib import Path

def main():
    """优化的主程序启动"""
    print("🤖 EvoBot控制系统启动中...")
    print("=" * 50)
    
    start_time = time.time()
    
    # 添加src目录到Python路径
    current_dir = Path(__file__).parent
    src_dir = current_dir / "src"
    sys.path.insert(0, str(src_dir))
    
    try:
        # 1. 应用启动优化
        print("🚀 应用启动优化...")
        from startup_optimizer import setup_fast_startup
        setup_fast_startup()
        opt_time = time.time()
        print(f"   ✅ 启动优化完成 ({opt_time - start_time:.2f}s)")
        
        # 2. 导入PyQt5
        print("🎨 初始化Qt环境...")
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        
        from utils.qt_compat import setup_qt_environment, check_qt_version
        
        # 检查Qt版本并设置环境
        check_qt_version()
        setup_qt_environment()
        qt_time = time.time()
        print(f"   ✅ Qt环境初始化完成 ({qt_time - opt_time:.2f}s)")
        
        # 3. 创建应用程序
        print("📱 创建应用程序...")
        app = QApplication(sys.argv)
        app.setApplicationName("EvoBot控制系统")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("EvoBot Team")
        app_time = time.time()
        print(f"   ✅ 应用程序创建完成 ({app_time - qt_time:.2f}s)")
        
        # 4. 初始化配置和日志
        print("⚙️  初始化配置系统...")
        from utils.config_manager import ConfigManager
        from utils.logger import setup_logger, get_logger
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        setup_logger(config.get('logging', {}))
        logger = get_logger(__name__)
        config_time = time.time()
        print(f"   ✅ 配置系统初始化完成 ({config_time - app_time:.2f}s)")
        
        # 5. 设置字体和样式
        print("🎨 设置界面样式...")
        screen = app.primaryScreen()
        logical_dpi = screen.logicalDotsPerInch()
        scaling_factor = logical_dpi / 96.0
        font = QFont()
        font_size = int(10 * scaling_factor)
        font.setPointSize(font_size)
        app.setFont(font)
        style_time = time.time()
        print(f"   ✅ 界面样式设置完成 ({style_time - config_time:.2f}s)")
        
        # 6. 创建主窗口
        print("🏠 创建主界面...")
        from ui.main_window import MainWindow
        main_window = MainWindow(config_manager)
        main_window.show()
        ui_time = time.time()
        print(f"   ✅ 主界面创建完成 ({ui_time - style_time:.2f}s)")
        
        total_time = ui_time - start_time
        print("=" * 50)
        print(f"🎉 EvoBot控制系统启动成功！")
        print(f"⏱️  总启动时间: {total_time:.2f}秒")
        print(f"💡 运动学库采用延迟加载，首次使用时才会加载")
        print("=" * 50)
        
        logger.info(f"EvoBot控制系统启动成功，启动时间: {total_time:.2f}秒")
        
        # 运行应用程序
        exit_code = app.exec_()
        logger.info(f"EvoBot控制系统退出，退出代码: {exit_code}")
        return exit_code
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("💡 请确保已安装所需依赖: uv sync")
        return 1
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())