"""
延迟加载运动学模块

功能：
- 延迟加载roboticstoolbox和spatialmath
- 减少启动时间
- 按需初始化重型库
"""

import warnings
from typing import Optional, Any

class LazyKinematicsLoader:
    """延迟加载运动学库"""
    
    def __init__(self):
        self._roboticstoolbox = None
        self._spatialmath = None
        self._loaded = False
    
    def _load_libraries(self):
        """加载运动学库"""
        if self._loaded:
            return
            
        print("📚 正在加载运动学库...")
        
        # 抑制警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            try:
                import roboticstoolbox as rtb
                import spatialmath as sm
                
                self._roboticstoolbox = rtb
                self._spatialmath = sm
                self._loaded = True
                
                print("✅ 运动学库加载完成")
                
            except ImportError as e:
                print(f"⚠️  运动学库加载失败: {e}")
                raise
    
    @property
    def roboticstoolbox(self):
        """获取roboticstoolbox模块"""
        if not self._loaded:
            self._load_libraries()
        return self._roboticstoolbox
    
    @property
    def spatialmath(self):
        """获取spatialmath模块"""
        if not self._loaded:
            self._load_libraries()
        return self._spatialmath
    
    def is_loaded(self) -> bool:
        """检查是否已加载"""
        return self._loaded

# 全局实例
_lazy_loader = LazyKinematicsLoader()

def get_roboticstoolbox():
    """获取roboticstoolbox模块"""
    return _lazy_loader.roboticstoolbox

def get_spatialmath():
    """获取spatialmath模块"""
    return _lazy_loader.spatialmath

def is_kinematics_loaded() -> bool:
    """检查运动学库是否已加载"""
    return _lazy_loader.is_loaded()