"""
启动优化器 - 用于加速应用程序启动
"""

import os
import sys


def setup_fast_startup():
    """设置快速启动优化"""
    # 设置环境变量以优化启动
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # 不生成.pyc文件
    os.environ['PYTHONUNBUFFERED'] = '1'  # 不缓冲输出
    
    # 对于打包后的应用，设置资源路径
    if getattr(sys, 'frozen', False):
        # 运行在PyInstaller打包的环境中
        application_path = sys._MEIPASS
        os.chdir(application_path)
    else:
        # 开发环境
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    # 添加到系统路径
    if application_path not in sys.path:
        sys.path.insert(0, application_path)