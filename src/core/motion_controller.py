"""
运动控制器

功能：
- 统一的运动控制接口
- 多种控制模式支持
- 实时位置控制
- 安全检查和限位
- 与硬件层集成
"""

import time
import threading
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.trajectory_planner import (
    TrajectoryPlanner, Trajectory, InterpolationType, 
    TrajectoryConstraints, get_trajectory_planner
)
from core.interpolator import Interpolator, InterpolatorState, get_interpolator
from core.kinematics_solver import get_kinematics_solver, Pose6D, KinematicsResult
from core.advanced_planner import get_advanced_planner, Obstacle, PlanningAlgorithm
from core.calibration_manager import get_calibration_manager
from core.velocity_controller import get_velocity_controller, VelocityParameters
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler

logger = get_logger(__name__)


class ControlMode(Enum):
    """控制模式"""
    MANUAL = "manual"           # 手动控制
    TRAJECTORY = "trajectory"   # 轨迹控制
    TEACHING = "teaching"       # 示教模式
    SCRIPT = "script"          # 脚本模式


class SafetyLevel(Enum):
    """安全级别"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MotionStatus:
    """运动状态"""
    mode: ControlMode
    is_moving: bool
    current_positions: List[int]
    target_positions: List[int]
    velocities: List[float]
    currents: List[int]
    safety_level: SafetyLevel
    error_message: Optional[str] = None


class SafetyChecker:
    """安全检查器"""
    
    def __init__(self, config: Dict):
        """初始化安全检查器"""
        self.config = config
        self.joints_config = config.get('joints', [])
        self.safety_config = config.get('safety', {})
        
        self.enable_soft_limits = self.safety_config.get('enable_soft_limits', True)
        self.enable_velocity_limits = self.safety_config.get('enable_velocity_limits', True)
        self.enable_current_limits = self.safety_config.get('enable_current_limits', True)
        
        logger.info("安全检查器初始化完成")
    
    def check_position_limits(self, positions: List[int]) -> tuple[bool, Optional[str]]:
        """检查位置限位"""
        if not self.enable_soft_limits:
            return True, None
        
        for i, pos in enumerate(positions):
            if i >= len(self.joints_config):
                continue
            
            joint_config = self.joints_config[i]
            limits = joint_config.get('limits', {})
            min_pos = limits.get('min_position', 0)
            max_pos = limits.get('max_position', 3000)
            
            if pos < min_pos or pos > max_pos:
                joint_name = joint_config.get('name', f'joint_{i}')
                return False, f"关节{joint_name}位置超限: {pos} (范围: {min_pos}-{max_pos})"
        
        return True, None
    
    def check_velocity_limits(self, velocities: List[float]) -> tuple[bool, Optional[str]]:
        """检查速度限制"""
        if not self.enable_velocity_limits:
            return True, None
        
        for i, vel in enumerate(velocities):
            if i >= len(self.joints_config):
                continue
            
            joint_config = self.joints_config[i]
            limits = joint_config.get('limits', {})
            max_vel = limits.get('max_velocity', 1000)
            
            if abs(vel) > max_vel:
                joint_name = joint_config.get('name', f'joint_{i}')
                return False, f"关节{joint_name}速度超限: {abs(vel):.1f} > {max_vel}"
        
        return True, None
    
    def check_current_limits(self, currents: List[int]) -> tuple[bool, Optional[str]]:
        """检查电流限制"""
        if not self.enable_current_limits:
            return True, None
        
        for i, current in enumerate(currents):
            if i >= len(self.joints_config):
                continue
            
            joint_config = self.joints_config[i]
            limits = joint_config.get('limits', {})
            max_current = limits.get('max_current', 2000)
            
            if current > max_current:
                joint_name = joint_config.get('name', f'joint_{i}')
                return False, f"关节{joint_name}电流超限: {current}mA > {max_current}mA"
        
        return True, None
    
    def limit_positions(self, positions: List[int]) -> List[int]:
        """限制位置到安全范围"""
        limited = []
        for i, pos in enumerate(positions):
            if i >= len(self.joints_config):
                limited.append(pos)
                continue
            
            joint_config = self.joints_config[i]
            limits = joint_config.get('limits', {})
            min_pos = limits.get('min_position', 0)
            max_pos = limits.get('max_position', 3000)
            
            limited_pos = max(min_pos, min(max_pos, pos))
            if limited_pos != pos:
                joint_name = joint_config.get('name', f'joint_{i}')
                logger.warning(f"关节{joint_name}位置被限制: {pos} -> {limited_pos}")
            
            limited.append(limited_pos)
        
        return limited


class MotionController:
    """运动控制器"""
    
    def __init__(self):
        """初始化运动控制器"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        
        # 核心组件
        self.trajectory_planner = get_trajectory_planner()
        self.interpolator = get_interpolator()
        self.kinematics_solver = get_kinematics_solver()
        self.advanced_planner = get_advanced_planner()
        self.calibration_manager = get_calibration_manager()
        self.velocity_controller = get_velocity_controller()
        self.serial_manager = get_serial_manager()
        self.protocol_handler = get_protocol_handler()
        
        # 安全检查器
        self.safety_checker = SafetyChecker(self.config)
        
        # 状态管理
        self.mode = ControlMode.MANUAL
        self.current_positions = [1500] * 10  # 默认中位
        self.target_positions = [1500] * 10
        self.velocities = [0.0] * 10
        self.currents = [0] * 10
        self.safety_level = SafetyLevel.NORMAL
        
        self.state_lock = threading.RLock()
        
        # 设置插值器回调
        self.interpolator.set_position_callback(self._on_interpolator_position)
        self.interpolator.set_status_callback(self._on_interpolator_status)
        
        # 订阅机器人状态更新
        self.message_bus.subscribe(Topics.ROBOT_STATE, self._on_robot_state_update)
        
        logger.info("运动控制器初始化完成")
    
    def set_mode(self, mode: ControlMode) -> bool:
        """设置控制模式"""
        with self.state_lock:
            if self.interpolator.is_running():
                logger.warning("轨迹正在执行，无法切换模式")
                return False
            
            old_mode = self.mode
            self.mode = mode
            
            logger.info(f"控制模式切换: {old_mode.value} -> {mode.value}")
            
            self.message_bus.publish(
                Topics.CONTROL_MODE_CHANGED,
                {'old_mode': old_mode.value, 'new_mode': mode.value},
                MessagePriority.NORMAL
            )
            
            return True
    
    def get_mode(self) -> ControlMode:
        """获取当前控制模式"""
        return self.mode
    
    @log_performance
    def move_to_position(self, positions: List[int], duration: Optional[float] = None,
                        interpolation_type: InterpolationType = InterpolationType.TRAPEZOIDAL) -> bool:
        """
        移动到目标位置
        
        Args:
            positions: 目标位置
            duration: 运动时间（可选）
            interpolation_type: 插值类型
            
        Returns:
            是否成功启动
        """
        with self.state_lock:
            try:
                # 检查连接
                if not self.serial_manager.is_connected():
                    logger.error("串口未连接")
                    return False
                
                # 安全检查
                safe, error_msg = self.safety_checker.check_position_limits(positions)
                if not safe:
                    logger.error(f"位置安全检查失败: {error_msg}")
                    return False
                
                # 限制位置
                safe_positions = self.safety_checker.limit_positions(positions)
                
                # 应用标定转换
                hardware_positions = self.calibration_manager.apply_calibration(safe_positions)
                
                # 获取当前速度参数
                velocity_params = self.velocity_controller.get_current_parameters()
                
                # 创建轨迹约束
                constraints = TrajectoryConstraints(
                    max_velocity=velocity_params.velocity,
                    max_acceleration=velocity_params.acceleration,
                    max_jerk=velocity_params.jerk
                )
                
                # 规划轨迹
                trajectory = self.trajectory_planner.plan_point_to_point(
                    self.current_positions,
                    hardware_positions,  # 使用标定后的硬件位置
                    duration,
                    velocity_params.interpolation,  # 使用速度控制器的插值类型
                    constraints
                )
                
                # 执行轨迹
                self.target_positions = safe_positions  # 保存用户空间的目标位置
                return self.interpolator.start_trajectory(trajectory)
                
            except Exception as e:
                logger.error(f"移动到位置失败: {e}")
                return False
    
    @log_performance
    def move_trajectory(self, trajectory: Trajectory) -> bool:
        """
        执行轨迹运动
        
        Args:
            trajectory: 轨迹对象
            
        Returns:
            是否成功启动
        """
        with self.state_lock:
            try:
                # 检查连接
                if not self.serial_manager.is_connected():
                    logger.error("串口未连接")
                    return False
                
                # 检查模式
                if self.mode != ControlMode.TRAJECTORY:
                    logger.warning(f"当前模式不是轨迹模式: {self.mode.value}")
                
                # 执行轨迹
                return self.interpolator.start_trajectory(trajectory)
                
            except Exception as e:
                logger.error(f"执行轨迹失败: {e}")
                return False
    
    @log_performance
    def move_to_pose(self, target_pose: Pose6D, duration: Optional[float] = None,
                    interpolation_type: InterpolationType = InterpolationType.TRAPEZOIDAL) -> bool:
        """
        移动到目标位姿（笛卡尔空间）
        
        Args:
            target_pose: 目标位姿
            duration: 运动时间（可选）
            interpolation_type: 插值类型
            
        Returns:
            是否成功启动
        """
        with self.state_lock:
            try:
                # 检查连接
                if not self.serial_manager.is_connected():
                    logger.error("串口未连接")
                    return False
                
                # 检查运动学求解器
                if not self.kinematics_solver.is_enabled():
                    logger.error("运动学求解器不可用")
                    return False
                
                # 逆运动学求解
                ik_result = self.kinematics_solver.inverse_kinematics(target_pose)
                if not ik_result.success:
                    logger.error(f"逆运动学求解失败: {ik_result.error_message}")
                    return False
                
                # 转换为整数位置（假设需要转换）
                target_positions = [int(round(angle * 3000 / (2 * 3.14159))) for angle in ik_result.joint_angles]
                
                # 调用位置控制
                return self.move_to_position(target_positions, duration, interpolation_type)
                
            except Exception as e:
                logger.error(f"移动到位姿失败: {e}")
                return False
    
    @log_performance
    def move_with_path_planning(self, target_pose: Pose6D, 
                               obstacles: Optional[List[Obstacle]] = None,
                               algorithm: PlanningAlgorithm = PlanningAlgorithm.RRT) -> bool:
        """
        使用路径规划移动到目标位姿
        
        Args:
            target_pose: 目标位姿
            obstacles: 障碍物列表
            algorithm: 规划算法
            
        Returns:
            是否成功启动
        """
        with self.state_lock:
            try:
                # 检查连接
                if not self.serial_manager.is_connected():
                    logger.error("串口未连接")
                    return False
                
                # 获取当前位姿
                current_angles = [pos * 2 * 3.14159 / 3000 for pos in self.current_positions]  # 转换为弧度
                fk_result = self.kinematics_solver.forward_kinematics(current_angles)
                if not fk_result.success:
                    logger.error("无法获取当前位姿")
                    return False
                
                current_pose = fk_result.end_effector_pose
                
                # 设置障碍物
                if obstacles:
                    self.advanced_planner.set_obstacles(obstacles)
                
                # 路径规划
                planning_result = self.advanced_planner.plan_cartesian_path(
                    current_pose, target_pose, algorithm
                )
                
                if not planning_result.success:
                    logger.error(f"路径规划失败: {planning_result.error_message}")
                    return False
                
                # 路径优化
                optimized_path = self.advanced_planner.optimize_path(planning_result.path)
                
                # 转换为轨迹
                trajectory = self.advanced_planner.path_to_trajectory(
                    optimized_path, 
                    total_duration=5.0  # 默认5秒
                )
                
                if trajectory is None:
                    logger.error("路径转轨迹失败")
                    return False
                
                # 执行轨迹
                return self.interpolator.start_trajectory(trajectory)
                
            except Exception as e:
                logger.error(f"路径规划运动失败: {e}")
                return False
    def move_joint(self, joint_id: int, position: int, duration: Optional[float] = None) -> bool:
        """
        移动单个关节
        
        Args:
            joint_id: 关节ID
            position: 目标位置
            duration: 运动时间
            
        Returns:
            是否成功
        """
        if joint_id < 0 or joint_id >= 10:
            logger.error(f"无效的关节ID: {joint_id}")
            return False
        
        target_positions = self.current_positions.copy()
        target_positions[joint_id] = position
        
        return self.move_to_position(target_positions, duration)
    
    def set_velocity_parameters(self, parameters: VelocityParameters) -> bool:
        """
        设置速度参数
        
        Args:
            parameters: 速度参数
            
        Returns:
            是否设置成功
        """
        return self.velocity_controller.set_velocity_parameters(parameters)
    
    def get_velocity_parameters(self) -> VelocityParameters:
        """获取当前速度参数"""
        return self.velocity_controller.get_current_parameters()
    
    def apply_velocity_preset(self, preset_name: str) -> bool:
        """
        应用速度预设
        
        Args:
            preset_name: 预设名称
            
        Returns:
            是否应用成功
        """
        try:
            from core.velocity_controller import VelocityPreset
            preset = VelocityPreset(preset_name)
            return self.velocity_controller.apply_preset(preset)
        except ValueError:
            logger.error(f"未知的速度预设: {preset_name}")
            return False
    
    def get_current_pose(self) -> Optional[Pose6D]:
        """
        获取当前末端执行器位姿
        
        Returns:
            当前位姿
        """
        if not self.kinematics_solver.is_enabled():
            return None
        
        try:
            # 转换当前位置为弧度
            current_angles = [pos * 2 * 3.14159 / 3000 for pos in self.current_positions]
            
            # 正运动学求解
            fk_result = self.kinematics_solver.forward_kinematics(current_angles)
            if fk_result.success:
                return fk_result.end_effector_pose
            else:
                logger.error(f"正运动学求解失败: {fk_result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"获取当前位姿失败: {e}")
            return None
    
    def get_manipulability(self) -> float:
        """
        获取当前配置的可操作性指标
        
        Returns:
            可操作性指标
        """
        if not self.kinematics_solver.is_enabled():
            return 0.0
        
        try:
            current_angles = [pos * 2 * 3.14159 / 3000 for pos in self.current_positions]
            return self.kinematics_solver.manipulability(current_angles)
        except Exception as e:
            logger.error(f"计算可操作性失败: {e}")
            return 0.0
    
    def check_singularity(self) -> bool:
        """
        检查当前配置是否接近奇异点
        
        Returns:
            是否接近奇异点
        """
        if not self.kinematics_solver.is_enabled():
            return False
        
        try:
            current_angles = [pos * 2 * 3.14159 / 3000 for pos in self.current_positions]
            return self.kinematics_solver.is_singular(current_angles)
        except Exception as e:
            logger.error(f"奇异点检测失败: {e}")
            return False
    
    def stop(self):
        """停止运动"""
        logger.info("停止运动")
        self.interpolator.stop()
    
    def emergency_stop(self):
        """紧急停止"""
        logger.warning("紧急停止")
        self.interpolator.emergency_stop()
        self.safety_level = SafetyLevel.EMERGENCY
    
    def pause(self):
        """暂停运动"""
        self.interpolator.pause()
    
    def resume(self):
        """恢复运动"""
        self.interpolator.resume()
    
    def get_status(self) -> MotionStatus:
        """获取运动状态"""
        with self.state_lock:
            return MotionStatus(
                mode=self.mode,
                is_moving=self.interpolator.is_running(),
                current_positions=self.current_positions.copy(),
                target_positions=self.target_positions.copy(),
                velocities=self.velocities.copy(),
                currents=self.currents.copy(),
                safety_level=self.safety_level
            )
    
    def get_current_positions(self) -> List[int]:
        """获取当前位置（用户空间）"""
        # 将硬件位置转换为用户空间位置
        hardware_positions = self.current_positions.copy()
        user_positions = self.calibration_manager.reverse_calibration(hardware_positions)
        return user_positions
    
    def get_current_hardware_positions(self) -> List[int]:
        """获取当前硬件位置"""
        return self.current_positions.copy()
    
    def set_current_positions(self, positions: List[int], is_hardware_space: bool = True):
        """
        设置当前位置
        
        Args:
            positions: 位置数组
            is_hardware_space: 是否为硬件空间位置
        """
        with self.state_lock:
            if is_hardware_space:
                self.current_positions = positions.copy()
            else:
                # 用户空间位置，需要转换为硬件空间
                hardware_positions = self.calibration_manager.apply_calibration(positions)
                self.current_positions = hardware_positions
    
    def _on_interpolator_position(self, positions: List[int]):
        """插值器位置输出回调"""
        try:
            # 发送位置指令到硬件
            command = self.protocol_handler.encode_position_command(positions)
            self.serial_manager.send_data(command)
            
            # 更新当前位置
            with self.state_lock:
                self.current_positions = positions
            
        except Exception as e:
            logger.error(f"发送位置指令失败: {e}")
    
    def _on_interpolator_status(self, status):
        """插值器状态更新回调"""
        # 可以在这里添加状态监控逻辑
        pass
    
    def _on_robot_state_update(self, message):
        """机器人状态更新回调"""
        try:
            data = message.data
            
            # 处理不同的数据格式
            joints = []
            
            if isinstance(data, dict):
                if 'joints' in data:
                    # 直接包含joints字段的格式 (来自protocol_handler内部发布)
                    joints = data.get('joints', [])
                elif 'data' in data and hasattr(data['data'], 'joints'):
                    # 包装格式 (来自main_window发布)
                    robot_status = data['data']
                    joints = [
                        {
                            'id': joint.joint_id,
                            'position': joint.position,
                            'velocity': joint.velocity,
                            'current': joint.current
                        } for joint in robot_status.joints
                    ]
                else:
                    logger.warning(f"未识别的机器人状态数据格式: {data}")
                    return
            else:
                logger.warning(f"机器人状态数据不是字典格式: {type(data)}")
                return
            
            # 更新位置和电流
            for joint_data in joints:
                joint_id = joint_data.get('id')
                if 0 <= joint_id < 10:
                    self.current_positions[joint_id] = joint_data.get('position', 0)
                    self.velocities[joint_id] = joint_data.get('velocity', 0)
                    self.currents[joint_id] = joint_data.get('current', 0)
            
            # 安全检查
            self._check_safety()
            
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")
    
    def _check_safety(self):
        """检查安全状态"""
        # 检查电流
        safe, error_msg = self.safety_checker.check_current_limits(self.currents)
        if not safe:
            logger.warning(f"电流安全警告: {error_msg}")
            self.safety_level = SafetyLevel.WARNING
        else:
            self.safety_level = SafetyLevel.NORMAL


# 全局运动控制器实例
_motion_controller = None


def get_motion_controller() -> MotionController:
    """获取全局运动控制器实例"""
    global _motion_controller
    if _motion_controller is None:
        _motion_controller = MotionController()
    return _motion_controller
