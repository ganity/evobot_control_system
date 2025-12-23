#!/usr/bin/env python3
"""
快速启动测试

测试启动优化效果
"""

import time
import sys
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def test_startup():
    """测试启动时间"""
    print("🚀 开始启动测试...")
    start_time = time.time()
    
    # 导入启动优化器
    from startup_optimizer import setup_fast_startup
    setup_time = time.time()
    print(f"⏱️  启动优化器加载时间: {setup_time - start_time:.2f}秒")
    
    # 应用优化
    setup_fast_startup()
    optimize_time = time.time()
    print(f"⏱️  优化应用时间: {optimize_time - setup_time:.2f}秒")
    
    # 导入PyQt5
    from PyQt5.QtWidgets import QApplication
    qt_time = time.time()
    print(f"⏱️  PyQt5导入时间: {qt_time - optimize_time:.2f}秒")
    
    # 导入配置管理器
    from utils.config_manager import ConfigManager
    config_time = time.time()
    print(f"⏱️  配置管理器导入时间: {config_time - qt_time:.2f}秒")
    
    # 导入运动学求解器（延迟加载）
    from core.kinematics_solver import KinematicsSolver
    kinematics_time = time.time()
    print(f"⏱️  运动学求解器导入时间: {kinematics_time - config_time:.2f}秒")
    
    # 创建运动学求解器实例（不会加载重型库）
    solver = KinematicsSolver()
    solver_time = time.time()
    print(f"⏱️  运动学求解器创建时间: {solver_time - kinematics_time:.2f}秒")
    
    total_time = solver_time - start_time
    print(f"✅ 总启动时间: {total_time:.2f}秒")
    
    return total_time

if __name__ == "__main__":
    test_startup()