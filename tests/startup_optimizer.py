#!/usr/bin/env python3
"""
启动优化器

功能：
- 抑制第三方库的警告
- 延迟加载重型库
- 优化启动流程
"""

import warnings
import sys
import os
from pathlib import Path

def suppress_warnings():
    """抑制各种警告"""
    # 抑制SyntaxWarning
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    
    # 抑制roboticstoolbox相关警告
    warnings.filterwarnings("ignore", module="roboticstoolbox")
    warnings.filterwarnings("ignore", module="spatialmath")
    
    # 抑制numpy警告
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")
    
    # 抑制matplotlib警告
    warnings.filterwarnings("ignore", module="matplotlib")
    
    # 设置环境变量抑制Qt警告
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
    os.environ['PYTHONWARNINGS'] = 'ignore::SyntaxWarning'
    
    # 抑制pyqtgraph警告
    os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'

def optimize_python_startup():
    """优化Python启动"""
    # 禁用字节码生成以加快导入
    sys.dont_write_bytecode = True
    
    # 设置递归限制
    sys.setrecursionlimit(3000)

def optimize_imports():
    """优化导入"""
    # 预加载常用模块
    try:
        import numpy
        import PyQt5.QtCore
        import PyQt5.QtWidgets
        print("✅ 核心模块预加载完成")
    except ImportError as e:
        print(f"⚠️  预加载失败: {e}")

def setup_fast_startup():
    """设置快速启动"""
    # 优化Python启动
    optimize_python_startup()
    
    # 抑制警告
    suppress_warnings()
    
    # 优化导入
    optimize_imports()
    
    print("🚀 启动优化已应用")

if __name__ == "__main__":
    setup_fast_startup()