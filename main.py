#!/usr/bin/env python3
"""
EvoBot控制系统主程序入口

功能：
- 初始化系统组件
- 启动主界面
- 处理系统退出
"""

import sys
import os
from pathlib import Path

# 启动优化 - 必须在其他导入之前
from startup_optimizer import setup_fast_startup
setup_fast_startup()

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    """主程序入口"""
    try:
        # 导入PyQt5相关模块
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        
        # 使用兼容性Qt环境初始化
        from utils.qt_compat import setup_qt_environment, check_qt_version
        
        # 检查Qt版本并设置环境
        check_qt_version()
        setup_qt_environment()
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 设置应用程序信息
        app.setApplicationName("EvoBot控制系统")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("EvoBot Team")
        
        # 初始化配置管理器
        from utils.config_manager import ConfigManager
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # 初始化日志系统
        from utils.logger import setup_logger, get_logger
        setup_logger(config.get('logging', {}))
        logger = get_logger(__name__)
        logger.info("EvoBot控制系统启动")
        
        # 设置字体缩放
        screen = app.primaryScreen()
        logical_dpi = screen.logicalDotsPerInch()
        scaling_factor = logical_dpi / 96.0
        font = QFont()
        font_size = int(10 * scaling_factor)
        font.setPointSize(font_size)
        app.setFont(font)
        
        # 创建并显示主窗口
        from ui.main_window import MainWindow
        main_window = MainWindow(config_manager)
        main_window.show()
        
        logger.info("主界面已启动")
        
        # 运行应用程序
        exit_code = app.exec_()
        
        logger.info(f"EvoBot控制系统退出，退出代码: {exit_code}")
        return exit_code
        
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装所需依赖: uv sync")
        return 1
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
