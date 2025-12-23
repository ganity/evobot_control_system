#!/usr/bin/env python3
"""
EvoBot控制系统主程序入口 - 调试版本

功能：
- 初始化系统组件
- 启动主界面
- 处理系统退出
- 详细的错误日志和调试信息
"""

import sys
import os
import traceback
from pathlib import Path

def setup_debug_logging():
    """设置调试日志"""
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('evobot_debug.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def main():
    """主程序入口"""
    logger = setup_debug_logging()
    logger.info("=" * 50)
    logger.info("EvoBot控制系统启动 - 调试模式")
    logger.info("=" * 50)
    
    try:
        # 检查Python环境
        logger.info(f"Python版本: {sys.version}")
        logger.info(f"Python路径: {sys.executable}")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info(f"程序路径: {__file__}")
        
        # 检查是否在PyInstaller环境中
        if getattr(sys, 'frozen', False):
            logger.info("运行在PyInstaller打包环境中")
            logger.info(f"可执行文件路径: {sys.executable}")
            logger.info(f"临时目录: {sys._MEIPASS}")
            # 切换到临时目录
            os.chdir(sys._MEIPASS)
            logger.info(f"切换工作目录到: {os.getcwd()}")
        else:
            logger.info("运行在开发环境中")
        
        # 启动优化 - 必须在其他导入之前
        logger.info("导入启动优化器...")
        try:
            from startup_optimizer import setup_fast_startup
            setup_fast_startup()
            logger.info("启动优化器设置完成")
        except Exception as e:
            logger.error(f"启动优化器失败: {e}")
            # 继续执行，不中断
        
        # 添加src目录到Python路径
        if getattr(sys, 'frozen', False):
            # 打包环境中，模块已经包含在可执行文件中
            logger.info("打包环境，跳过路径设置")
        else:
            # 开发环境
            current_dir = Path(__file__).parent
            src_dir = current_dir / "src"
            sys.path.insert(0, str(src_dir))
            logger.info(f"添加src目录到路径: {src_dir}")
        
        logger.info(f"当前Python路径: {sys.path[:3]}...")  # 只显示前3个
        
        # 测试PyQt5导入
        logger.info("导入PyQt5模块...")
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            from PyQt5.QtCore import Qt, QT_VERSION_STR
            from PyQt5.QtGui import QFont
            logger.info(f"PyQt5导入成功，版本: {QT_VERSION_STR}")
        except ImportError as e:
            logger.error(f"PyQt5导入失败: {e}")
            raise
        
        # 使用兼容性Qt环境初始化
        logger.info("初始化Qt环境...")
        try:
            from utils.qt_compat import setup_qt_environment, check_qt_version
            
            # 检查Qt版本并设置环境
            supports_meta_type = check_qt_version()
            logger.info(f"Qt版本检查完成，支持MetaType: {supports_meta_type}")
            
            setup_qt_environment()
            logger.info("Qt环境设置完成")
        except Exception as e:
            logger.error(f"Qt环境初始化失败: {e}")
            logger.error(traceback.format_exc())
            # 尝试继续执行
        
        # 创建应用程序
        logger.info("创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("QApplication创建成功")
        
        # 设置应用程序信息
        app.setApplicationName("EvoBot控制系统")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("EvoBot Team")
        logger.info("应用程序信息设置完成")
        
        # 初始化配置管理器
        logger.info("初始化配置管理器...")
        try:
            from utils.config_manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.load_config()
            logger.info("配置管理器初始化成功")
        except Exception as e:
            logger.error(f"配置管理器初始化失败: {e}")
            logger.error(traceback.format_exc())
            # 使用默认配置
            config = {}
            config_manager = None
        
        # 初始化日志系统
        logger.info("初始化应用日志系统...")
        try:
            from utils.logger import setup_logger, get_logger
            setup_logger(config.get('logging', {}))
            app_logger = get_logger(__name__)
            app_logger.info("EvoBot控制系统启动")
            logger.info("应用日志系统初始化成功")
        except Exception as e:
            logger.error(f"应用日志系统初始化失败: {e}")
            logger.error(traceback.format_exc())
            # 继续使用调试日志
            app_logger = logger
        
        # 设置字体缩放
        logger.info("设置字体缩放...")
        try:
            screen = app.primaryScreen()
            logical_dpi = screen.logicalDotsPerInch()
            scaling_factor = logical_dpi / 96.0
            font = QFont()
            font_size = int(10 * scaling_factor)
            font.setPointSize(font_size)
            app.setFont(font)
            logger.info(f"字体缩放设置完成，DPI: {logical_dpi}, 缩放: {scaling_factor}")
        except Exception as e:
            logger.error(f"字体缩放设置失败: {e}")
            # 继续执行
        
        # 创建并显示主窗口
        logger.info("创建主窗口...")
        try:
            from ui.main_window import MainWindow
            main_window = MainWindow(config_manager)
            logger.info("主窗口创建成功")
            
            main_window.show()
            logger.info("主窗口显示成功")
            
            app_logger.info("主界面已启动")
        except Exception as e:
            logger.error(f"主窗口创建/显示失败: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # 运行应用程序
        logger.info("启动应用程序事件循环...")
        exit_code = app.exec_()
        
        logger.info(f"应用程序退出，退出代码: {exit_code}")
        app_logger.info(f"EvoBot控制系统退出，退出代码: {exit_code}")
        return exit_code
        
    except ImportError as e:
        error_msg = f"导入错误: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        print(error_msg)
        print("请确保已安装所需依赖")
        return 1
    except Exception as e:
        error_msg = f"启动失败: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        print(error_msg)
        print("详细错误信息已保存到 evobot_debug.log")
        return 1
    finally:
        logger.info("程序结束")


if __name__ == "__main__":
    sys.exit(main())