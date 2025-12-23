"""
速度控制器

功能：
- 速度参数管理
- 速度预设切换
- 实时速度控制
- 速度曲线生成
- 与轨迹规划器集成
"""

import time
import threading
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.trajectory_planner import InterpolationType

logger = get_logger(__name__)


class VelocityPreset(Enum):
    """速度预设"""
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    VERY_FAST = "very_fast"
    CUSTOM = "custom"


@dataclass
class VelocityParameters:
    """速度参数"""
    velocity: float = 500.0           # 速度 (单位/秒)
    acceleration: float = 1000.0      # 加速度 (单位/秒²)
    jerk: float = 5000.0              # 加加速度 (单位/秒³)
    interpolation: InterpolationType = InterpolationType.TRAPEZOIDAL
    description: str = ""


@dataclass
class JointVelocityLimits:
    """关节速度限制"""
    max_velocity: float = 1000.0
    max_acceleration: float = 2000.0
    max_jerk: float = 10000.0
    min_velocity: float = 10.0


class VelocityController:
    """速度控制器"""
    
    def __init__(self):
        """初始化速度控制器"""
        self.config_manager = get_config_manager()
        self.message_bus = get_message_bus()
        
        # 当前速度参数
        self.current_parameters = VelocityParameters()
        self.current_preset = VelocityPreset.MEDIUM
        
        # 关节速度限制
        self.joint_limits: List[JointVelocityLimits] = []
        
        # 速度预设
        self.velocity_presets: Dict[VelocityPreset, VelocityParameters] = {}
        
        # 状态管理
        self.velocity_lock = threading.RLock()
        
        # 加载配置
        self._load_velocity_config()
        
        logger.info("速度控制器初始化完成")
    
    def _load_velocity_config(self):
        """加载速度配置"""
        try:
            config = self.config_manager.load_config()
            velocity_config = config.get('velocity_control', {})
            
            # 加载默认参数
            defaults = velocity_config.get('defaults', {})
            self.current_parameters = VelocityParameters(
                velocity=defaults.get('velocity', 500.0),
                acceleration=defaults.get('acceleration', 1000.0),
                jerk=defaults.get('jerk', 5000.0),
                interpolation=InterpolationType(defaults.get('interpolation', 'trapezoidal')),
                description="默认速度"
            )
            
            # 加载速度预设
            presets_config = velocity_config.get('presets', {})
            self.velocity_presets = {}
            
            for preset_name, preset_data in presets_config.items():
                try:
                    preset_enum = VelocityPreset(preset_name)
                    self.velocity_presets[preset_enum] = VelocityParameters(
                        velocity=preset_data.get('velocity', 500.0),
                        acceleration=preset_data.get('acceleration', 1000.0),
                        jerk=preset_data.get('jerk', 5000.0),
                        interpolation=InterpolationType(preset_data.get('interpolation', 'trapezoidal')),
                        description=preset_data.get('description', '')
                    )
                except ValueError:
                    logger.warning(f"未知的速度预设: {preset_name}")
            
            # 加载关节限制
            joints_config = velocity_config.get('joints', [])
            self.joint_limits = []
            
            for joint_config in joints_config:
                limits = JointVelocityLimits(
                    max_velocity=joint_config.get('max_velocity', 1000.0),
                    max_acceleration=joint_config.get('max_acceleration', 2000.0),
                    max_jerk=joint_config.get('max_jerk', 10000.0),
                    min_velocity=joint_config.get('min_velocity', 10.0)
                )
                self.joint_limits.append(limits)
            
            # 确保有10个关节的限制
            while len(self.joint_limits) < 10:
                self.joint_limits.append(JointVelocityLimits())
            
            logger.info("速度配置加载完成")
            
        except Exception as e:
            logger.error(f"加载速度配置失败: {e}")
            self._load_default_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        # 默认速度预设
        self.velocity_presets = {
            VelocityPreset.VERY_SLOW: VelocityParameters(
                velocity=100.0, acceleration=200.0, jerk=1000.0,
                interpolation=InterpolationType.S_CURVE,
                description="非常慢，适合精细操作"
            ),
            VelocityPreset.SLOW: VelocityParameters(
                velocity=300.0, acceleration=500.0, jerk=2000.0,
                interpolation=InterpolationType.S_CURVE,
                description="慢速，适合调试"
            ),
            VelocityPreset.MEDIUM: VelocityParameters(
                velocity=500.0, acceleration=1000.0, jerk=5000.0,
                interpolation=InterpolationType.TRAPEZOIDAL,
                description="中速，默认速度"
            ),
            VelocityPreset.FAST: VelocityParameters(
                velocity=800.0, acceleration=1500.0, jerk=8000.0,
                interpolation=InterpolationType.TRAPEZOIDAL,
                description="快速，适合大范围运动"
            ),
            VelocityPreset.VERY_FAST: VelocityParameters(
                velocity=1000.0, acceleration=2000.0, jerk=10000.0,
                interpolation=InterpolationType.TRAPEZOIDAL,
                description="非常快，最大速度"
            )
        }
        
        # 默认关节限制
        self.joint_limits = [JointVelocityLimits() for _ in range(10)]
        
        logger.info("使用默认速度配置")
    
    def get_current_parameters(self) -> VelocityParameters:
        """获取当前速度参数"""
        with self.velocity_lock:
            return VelocityParameters(
                velocity=self.current_parameters.velocity,
                acceleration=self.current_parameters.acceleration,
                jerk=self.current_parameters.jerk,
                interpolation=self.current_parameters.interpolation,
                description=self.current_parameters.description
            )
    
    def set_velocity_parameters(self, parameters: VelocityParameters) -> bool:
        """
        设置速度参数
        
        Args:
            parameters: 速度参数
            
        Returns:
            是否设置成功
        """
        with self.velocity_lock:
            try:
                # 验证参数
                if not self._validate_parameters(parameters):
                    return False
                
                # 应用限制
                limited_params = self._apply_limits(parameters)
                
                # 更新当前参数
                old_params = self.current_parameters
                self.current_parameters = limited_params
                self.current_preset = VelocityPreset.CUSTOM
                
                logger.info(f"速度参数已更新: 速度={limited_params.velocity}, 加速度={limited_params.acceleration}")
                
                # 发布速度变更事件
                self.message_bus.publish(
                    Topics.VELOCITY_CHANGED,
                    {
                        'old_parameters': old_params,
                        'new_parameters': limited_params,
                        'preset': self.current_preset.value
                    },
                    MessagePriority.NORMAL
                )
                
                return True
                
            except Exception as e:
                logger.error(f"设置速度参数失败: {e}")
                return False
    
    def apply_preset(self, preset: VelocityPreset) -> bool:
        """
        应用速度预设
        
        Args:
            preset: 速度预设
            
        Returns:
            是否应用成功
        """
        with self.velocity_lock:
            try:
                if preset not in self.velocity_presets:
                    logger.error(f"未知的速度预设: {preset}")
                    return False
                
                preset_params = self.velocity_presets[preset]
                old_params = self.current_parameters
                
                # 应用预设参数
                self.current_parameters = VelocityParameters(
                    velocity=preset_params.velocity,
                    acceleration=preset_params.acceleration,
                    jerk=preset_params.jerk,
                    interpolation=preset_params.interpolation,
                    description=preset_params.description
                )
                self.current_preset = preset
                
                logger.info(f"应用速度预设: {preset.value} - {preset_params.description}")
                
                # 发布预设应用事件
                self.message_bus.publish(
                    Topics.VELOCITY_PRESET_APPLIED,
                    {
                        'preset': preset.value,
                        'parameters': self.current_parameters,
                        'old_parameters': old_params
                    },
                    MessagePriority.NORMAL
                )
                
                return True
                
            except Exception as e:
                logger.error(f"应用速度预设失败: {e}")
                return False
    
    def get_preset_parameters(self, preset: VelocityPreset) -> Optional[VelocityParameters]:
        """获取预设参数"""
        return self.velocity_presets.get(preset)
    
    def get_all_presets(self) -> Dict[VelocityPreset, VelocityParameters]:
        """获取所有预设"""
        return self.velocity_presets.copy()
    
    def get_current_preset(self) -> VelocityPreset:
        """获取当前预设"""
        return self.current_preset
    
    def set_joint_velocity(self, joint_id: int, velocity: float) -> bool:
        """
        设置单个关节的速度
        
        Args:
            joint_id: 关节ID
            velocity: 速度值
            
        Returns:
            是否设置成功
        """
        if joint_id < 0 or joint_id >= 10:
            logger.error(f"无效的关节ID: {joint_id}")
            return False
        
        # 应用关节限制
        limits = self.joint_limits[joint_id]
        limited_velocity = max(limits.min_velocity, min(limits.max_velocity, velocity))
        
        if limited_velocity != velocity:
            logger.warning(f"关节{joint_id}速度被限制: {velocity} -> {limited_velocity}")
        
        # 这里可以实现单关节速度控制逻辑
        # 目前暂时记录日志
        logger.info(f"设置关节{joint_id}速度: {limited_velocity}")
        
        return True
    
    def get_joint_limits(self, joint_id: int) -> Optional[JointVelocityLimits]:
        """获取关节速度限制"""
        if 0 <= joint_id < len(self.joint_limits):
            return self.joint_limits[joint_id]
        return None
    
    def _validate_parameters(self, parameters: VelocityParameters) -> bool:
        """验证速度参数"""
        if parameters.velocity <= 0:
            logger.error(f"速度必须大于0: {parameters.velocity}")
            return False
        
        if parameters.acceleration <= 0:
            logger.error(f"加速度必须大于0: {parameters.acceleration}")
            return False
        
        if parameters.jerk <= 0:
            logger.error(f"加加速度必须大于0: {parameters.jerk}")
            return False
        
        return True
    
    def _apply_limits(self, parameters: VelocityParameters) -> VelocityParameters:
        """应用全局限制"""
        # 获取所有关节的最大限制
        max_velocity = max(limits.max_velocity for limits in self.joint_limits)
        max_acceleration = max(limits.max_acceleration for limits in self.joint_limits)
        max_jerk = max(limits.max_jerk for limits in self.joint_limits)
        
        # 应用限制
        limited_velocity = min(parameters.velocity, max_velocity)
        limited_acceleration = min(parameters.acceleration, max_acceleration)
        limited_jerk = min(parameters.jerk, max_jerk)
        
        return VelocityParameters(
            velocity=limited_velocity,
            acceleration=limited_acceleration,
            jerk=limited_jerk,
            interpolation=parameters.interpolation,
            description=parameters.description
        )
    
    def generate_velocity_profile(self, start_pos: float, end_pos: float, 
                                duration: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        生成速度曲线
        
        Args:
            start_pos: 起始位置
            end_pos: 结束位置
            duration: 运动时间（可选）
            
        Returns:
            (时间数组, 位置数组, 速度数组)
        """
        displacement = end_pos - start_pos
        
        if abs(displacement) < 1e-6:
            # 无位移
            t = np.array([0.0, 0.1])
            pos = np.array([start_pos, start_pos])
            vel = np.array([0.0, 0.0])
            return t, pos, vel
        
        # 计算运动时间
        if duration is None:
            duration = abs(displacement) / self.current_parameters.velocity * 2  # 估算时间
        
        # 生成时间数组
        dt = 0.01  # 10ms采样
        t = np.arange(0, duration + dt, dt)
        
        # 根据插值类型生成曲线
        if self.current_parameters.interpolation == InterpolationType.TRAPEZOIDAL:
            pos, vel = self._generate_trapezoidal_profile(start_pos, end_pos, t)
        elif self.current_parameters.interpolation == InterpolationType.S_CURVE:
            pos, vel = self._generate_s_curve_profile(start_pos, end_pos, t)
        else:
            # 默认线性
            pos, vel = self._generate_linear_profile(start_pos, end_pos, t)
        
        return t, pos, vel
    
    def _generate_trapezoidal_profile(self, start_pos: float, end_pos: float, 
                                    t: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """生成梯形速度曲线"""
        displacement = end_pos - start_pos
        duration = t[-1]
        
        max_vel = self.current_parameters.velocity
        max_acc = self.current_parameters.acceleration
        
        # 计算加速时间
        t_acc = max_vel / max_acc
        
        # 检查是否能达到最大速度
        if 2 * t_acc >= duration:
            # 三角形曲线
            t_acc = duration / 2
            max_vel = max_acc * t_acc
        
        t_dec = t_acc
        t_const = duration - t_acc - t_dec
        
        pos = np.zeros_like(t)
        vel = np.zeros_like(t)
        
        for i, time in enumerate(t):
            if time <= t_acc:
                # 加速段
                vel[i] = max_acc * time * np.sign(displacement)
                pos[i] = start_pos + 0.5 * max_acc * time * time * np.sign(displacement)
            elif time <= t_acc + t_const:
                # 匀速段
                vel[i] = max_vel * np.sign(displacement)
                pos[i] = start_pos + (0.5 * max_acc * t_acc * t_acc + max_vel * (time - t_acc)) * np.sign(displacement)
            elif time <= duration:
                # 减速段
                t_rel = time - t_acc - t_const
                vel[i] = (max_vel - max_acc * t_rel) * np.sign(displacement)
                pos[i] = start_pos + (0.5 * max_acc * t_acc * t_acc + max_vel * t_const + 
                                    max_vel * t_rel - 0.5 * max_acc * t_rel * t_rel) * np.sign(displacement)
            else:
                # 结束
                vel[i] = 0
                pos[i] = end_pos
        
        return pos, vel
    
    def _generate_s_curve_profile(self, start_pos: float, end_pos: float, 
                                t: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """生成S曲线"""
        # 简化的S曲线实现
        displacement = end_pos - start_pos
        duration = t[-1]
        
        pos = np.zeros_like(t)
        vel = np.zeros_like(t)
        
        for i, time in enumerate(t):
            # 使用五次多项式近似S曲线
            tau = time / duration if duration > 0 else 1.0
            tau = min(tau, 1.0)
            
            # 五次多项式系数
            s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
            s_dot = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / duration if duration > 0 else 0
            
            pos[i] = start_pos + s * displacement
            vel[i] = s_dot * displacement
        
        return pos, vel
    
    def _generate_linear_profile(self, start_pos: float, end_pos: float, 
                               t: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """生成线性曲线"""
        displacement = end_pos - start_pos
        duration = t[-1]
        
        pos = start_pos + (t / duration) * displacement
        vel = np.full_like(t, displacement / duration if duration > 0 else 0)
        
        return pos, vel
    
    def save_velocity_config(self) -> bool:
        """保存速度配置"""
        try:
            config = self.config_manager.load_config()
            
            # 更新速度控制配置
            velocity_config = {
                'mode': 'trajectory_interpolation',
                'control_frequency': 200,
                'defaults': {
                    'velocity': self.current_parameters.velocity,
                    'acceleration': self.current_parameters.acceleration,
                    'jerk': self.current_parameters.jerk,
                    'interpolation': self.current_parameters.interpolation.value
                },
                'presets': {},
                'joints': []
            }
            
            # 保存预设
            for preset, params in self.velocity_presets.items():
                velocity_config['presets'][preset.value] = {
                    'velocity': params.velocity,
                    'acceleration': params.acceleration,
                    'jerk': params.jerk,
                    'interpolation': params.interpolation.value,
                    'description': params.description
                }
            
            # 保存关节限制
            for i, limits in enumerate(self.joint_limits):
                velocity_config['joints'].append({
                    'id': i,
                    'max_velocity': limits.max_velocity,
                    'max_acceleration': limits.max_acceleration,
                    'max_jerk': limits.max_jerk,
                    'min_velocity': limits.min_velocity
                })
            
            config['velocity_control'] = velocity_config
            
            # 保存配置
            success = self.config_manager.save_config(config)
            
            if success:
                logger.info("速度配置已保存")
            else:
                logger.error("保存速度配置失败")
            
            return success
            
        except Exception as e:
            logger.error(f"保存速度配置失败: {e}")
            return False


# 全局速度控制器实例
_velocity_controller = None


def get_velocity_controller() -> VelocityController:
    """获取全局速度控制器实例"""
    global _velocity_controller
    if _velocity_controller is None:
        _velocity_controller = VelocityController()
    return _velocity_controller