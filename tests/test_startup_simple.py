#!/usr/bin/env python3
"""
简单启动测试
"""

import time
import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def main():
    print("🚀 测试启动优化...")
    start_time = time.time()
    
    # 导入启动优化器并应用
    from startup_optimizer import setup_fast_startup
    setup_fast_startup()
    
    # 导入主要模块
    from PyQt5.QtWidgets import QApplication
    from utils.config_manager import ConfigManager
    from core.kinematics_solver import KinematicsSolver
    
    # 创建应用程序（不显示界面）
    app = QApplication([])
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建运动学求解器（延迟加载）
    solver = KinematicsSolver()
    
    end_time = time.time()
    print(f"✅ 启动完成，总时间: {end_time - start_time:.2f}秒")
    print(f"📊 运动学库状态: {'已加载' if solver._initialized else '未加载（延迟模式）'}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())