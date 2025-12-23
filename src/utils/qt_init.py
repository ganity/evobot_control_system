"""
Qt初始化工具

功能：
- 统一Qt元类型注册
- 解决pyqtgraph兼容性问题
- 提供Qt应用程序初始化配置
"""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

def register_qt_metatypes():
    """注册Qt元类型以避免警告"""
    try:
        from PyQt5.QtCore import qRegisterMetaType
        
        # 基础数值类型
        qRegisterMetaType("QVector<int>")
        qRegisterMetaType("QList<int>")
        qRegisterMetaType("QVector<double>")
        qRegisterMetaType("QList<double>")
        qRegisterMetaType("QVector<float>")
        qRegisterMetaType("QList<float>")
        
        # 字符串类型
        qRegisterMetaType("QVector<QString>")
        qRegisterMetaType("QList<QString>")
        
        # 其他常用类型
        qRegisterMetaType("QVector<QPointF>")
        qRegisterMetaType("QList<QPointF>")
        qRegisterMetaType("QVector<QPoint>")
        qRegisterMetaType("QList<QPoint>")
        
        print("✅ Qt元类型注册成功")
        
    except ImportError:
        # 如果qRegisterMetaType不可用，使用替代方案
        print("⚠️  qRegisterMetaType不可用，跳过元类型注册")
        pass
    except Exception as e:
        print(f"⚠️  Qt元类型注册失败: {e}")
        pass

def configure_qt_application():
    """配置Qt应用程序"""
    try:
        # 设置高DPI支持
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 设置OpenGL支持（如果可用）
        try:
            QApplication.setAttribute(Qt.AA_UseOpenGLES, False)
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
            crashWarning=False  # 禁用崩溃警告以减少噪音
        )
        
        # 设置默认背景色
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
    """设置完整的Qt环境"""
    print("🔧 初始化Qt环境...")
    
    # 配置Qt应用程序
    configure_qt_application()
    
    # 注册元类型
    register_qt_metatypes()
    
    # 初始化pyqtgraph
    init_pyqtgraph()
    
    print("✅ Qt环境初始化完成")