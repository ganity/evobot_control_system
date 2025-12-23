# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)
src_dir = project_root / "src"

# 分析主程序 - 使用调试版本
a = Analysis(
    ['main_debug.py'],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=[
        # 配置文件
        ('config/*.yaml', 'config'),
        ('config/*.json', 'config'),
        # 启动优化器
        ('startup_optimizer.py', '.'),
        # 源代码目录（用于调试）
        ('src', 'src'),
    ],
    hiddenimports=[
        # PyQt5核心模块
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # PyQtGraph相关
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.widgets',
        # 科学计算库
        'numpy',
        'scipy',
        'scipy.spatial',
        'scipy.optimize',
        'matplotlib',
        'matplotlib.backends.backend_qt5agg',
        # 串口通信
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        # 日志和配置
        'loguru',
        'yaml',
        'pyyaml',
        # 启动优化器
        'startup_optimizer',
        # 项目模块 - 使用具体模块名
        'utils.qt_compat',
        'utils.config_manager',
        'utils.logger',
        'utils.message_bus',
        'hardware.serial_manager',
        'hardware.protocol_handler',
        'hardware.device_monitor',
        'ui.main_window',
        'core.motion_controller',
        'core.zero_position_manager',
        # 添加更多可能缺失的模块
        'ui.widgets.joint_control_panel_v2',
        'ui.widgets.velocity_panel',
        'ui.widgets.calibration_panel',
        'ui.widgets.recording_panel',
        'ui.widgets.zero_position_panel',
        'ui.widgets.simple_zero_panel',
        'core.velocity_controller',
        'core.calibration_manager',
        'core.trajectory_planner',
        'core.interpolator',
        'application.data_recorder',
        'application.data_player',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块
        'tkinter',
        'unittest',
        'test',
        'tests',
        'pytest',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 处理Python字节码
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EvoBot控制系统_Debug',
    debug=True,  # 启用调试模式
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX压缩
    console=True,  # 启用控制台以便查看错误信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# 收集所有文件
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # 禁用UPX压缩
    upx_exclude=[],
    name='EvoBot控制系统_Debug',
)