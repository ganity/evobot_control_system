"""
Qt兼容性工具

功能：
- 处理不同PyQt5版本的兼容性问题
- 提供统一的Qt初始化接口
- 解决常见的Qt警告问题
"""

import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

def suppress_qt_warnings():
    """抑制Qt警告"""
    # 设置环境变量来抑制Qt警告
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
    
    # 抑制pyqtgraph的警告
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="pyqtgraph")

def configure_qt_application():
    """配置Qt应用程序"""
    try:
        # 设置高DPI支持
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 设置其他属性
        try:
            QApplication.setAttribute(Qt.AA_UseDesktopOpenGL, True)
        except:
            pass
            
        print("✅ Qt应用程序配置成功")
        
    except Exception as e:
        print(f"⚠️  Qt应用程序配置失败: {e}")

def init_pyqtgraph():
    """初始化pyqtgraph配置"""
    try:
        import pyqtgraph as pg
        
        # 设置pyqtgraph配置
        pg.setConfigOptions(
            antialias=True,
            useOpenGL=False,  # 禁用OpenGL以避免兼容性问题
            enableExperimental=False,
            crashWarning=False  # 禁用崩溃警告
        )
        
        # 设置默认样式
        pg.setConfigOption('background', 'w')  # 白色背景
        pg.setConfigOption('foreground', 'k')  # 黑色前景
        
        print("✅ pyqtgraph配置成功")
        return True
        
    except ImportError:
        print("⚠️  pyqtgraph不可用")
        return False
    except Exception as e:
        print(f"⚠️  pyqtgraph配置失败: {e}")
        return False

def setup_qt_environment():
    """设置Qt环境（兼容版本）"""
    print("🔧 初始化Qt环境（兼容模式）...")
    
    # 抑制Qt警告
    suppress_qt_warnings()
    
    # 配置Qt应用程序
    configure_qt_application()
    
    # 初始化pyqtgraph
    init_pyqtgraph()
    
    print("✅ Qt环境初始化完成（兼容模式）")

def check_qt_version():
    """检查Qt版本信息"""
    try:
        from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        print(f"Qt版本: {QT_VERSION_STR}")
        print(f"PyQt5版本: {PYQT_VERSION_STR}")
        
        # 检查是否支持qRegisterMetaType
        try:
            from PyQt5.QtCore import qRegisterMetaType
            print("✅ 支持qRegisterMetaType")
            return True
        except ImportError:
            print("⚠️  不支持qRegisterMetaType")
            return False
            
    except Exception as e:
        print(f"⚠️  无法获取Qt版本信息: {e}")
        return False