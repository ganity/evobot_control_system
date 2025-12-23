# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)
src_dir = project_root / "src"

# 分析主程序
a = Analysis(
    ['main.py'],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=[
        # 配置文件
        ('config/*.yaml', 'config'),
        ('config/*.json', 'config'),
        # 文档（可选）
        ('README.md', '.'),
        # 其他资源文件
        ('data/.gitkeep', 'data'),
    ],
    hiddenimports=[
        # PyQt5相关
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.QtOpenGL',
        # PyQtGraph相关
        'pyqtgraph',
        'pyqtgraph.opengl',
        # 科学计算库
        'numpy',
        'scipy',
        'scipy.spatial',
        'scipy.optimize',
        'matplotlib',
        # 机器人工具箱
        'roboticstoolbox',
        'spatialmath',
        # 串口通信
        'serial',
        # 日志
        'loguru',
        # YAML
        'yaml',
        # 项目模块
        'src.core',
        'src.ui',
        'src.hardware',
        'src.application',
        'src.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小体积
        'tkinter',
        'unittest',
        'test',
        'tests',
        'pytest',
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
    name='EvoBot控制系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

# 收集所有文件
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EvoBot控制系统',
)