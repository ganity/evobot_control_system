"""
轨迹规划器

功能：
- 点到点轨迹规划
- 多点路径规划
- 多种插值算法支持
- 速度和加速度约束
- 平滑轨迹生成
"""

import numpy as np
from scipy import interpolate
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import time

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager

logger = get_logger(__name__)


class InterpolationType(Enum):
    """插值类型"""
    LINEAR = "linear"
    CUBIC_SPLINE = "cubic_spline"
    QUINTIC = "quintic"
    TRAPEZOIDAL = "trapezoidal"
    S_CURVE = "s_curve"
    BEZIER = "bezier"


class VelocityProfile(Enum):
    """速度曲线类型"""
    TRAPEZOIDAL = "trapezoidal"
    TRIANGULAR = "triangular"
    S_CURVE = "s_curve"


@dataclass
class TrajectoryPoint:
    """轨迹点"""
    timestamp: float
    positions: List[float]
    velocities: Optional[List[float]] = None
    accelerations: Optional[List[float]] = None
    
    def __post_init__(self):
        if self.velocities is None:
            self.velocities = [0.0] * len(self.positions)
        if self.accelerations is None:
            self.accelerations = [0.0] * len(self.positions)


@dataclass
class TrajectoryConstraints:
    """轨迹约束"""
    max_velocity: List[float]
    max_acceleration: List[float]
    max_jerk: Optional[List[float]] = None
    
    def __post_init__(self):
        if self.max_jerk is None:
            self.max_jerk = [j * 5 for j in self.max_acceleration]


@dataclass
class Trajectory:
    """轨迹对象"""
    points: List[TrajectoryPoint]
    duration: float
    interpolation_type: InterpolationType
    constraints: TrajectoryConstraints
    metadata: Optional[Dict[str, Any]] = None
    
    def get_point_at_time(self, t: float) -> Optional[TrajectoryPoint]:
        """获取指定时间的轨迹点"""
        if not self.points or t < 0 or t > self.duration:
            return None
        
        # 线性插值查找
        for i in range(len(self.points) - 1):
            if self.points[i].timestamp <= t <= self.points[i + 1].timestamp:
                # 线性插值
                t1, t2 = self.points[i].timestamp, self.points[i + 1].timestamp
                alpha = (t - t1) / (t2 - t1) if t2 != t1 else 0
                
                positions = []
                velocities = []
                accelerations = []
                
                for j in range(len(self.points[i].positions)):
                    pos = self.points[i].positions[j] + alpha * (self.points[i + 1].positions[j] - self.points[i].positions[j])
                    vel = self.points[i].velocities[j] + alpha * (self.points[i + 1].velocities[j] - self.points[i].velocities[j])
                    acc = self.points[i].accelerations[j] + alpha * (self.points[i + 1].accelerations[j] - self.points[i].accelerations[j])
                    
                    positions.append(pos)
                    velocities.append(vel)
                    accelerations.append(acc)
                
                return TrajectoryPoint(t, positions, velocities, accelerations)
        
        # 返回最后一个点
        return self.points[-1] if self.points else None


class TrajectoryPlanner:
    """轨迹规划器"""
    
    def __init__(self):
        """初始化轨迹规划器"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        
        # 默认约束
        self.default_constraints = TrajectoryConstraints(
            max_velocity=[500.0] * 10,
            max_acceleration=[1000.0] * 10,
            max_jerk=[5000.0] * 10
        )
        
        # 从配置加载约束
        self._load_constraints_from_config()
        
    def _load_constraints_from_config(self):
        """从配置文件加载约束参数"""
        try:
            joints_config = self.config.get('joints', [])
            if joints_config:
                max_vel = []
                max_acc = []
                max_jerk = []
                
                for joint_config in joints_config:
                    limits = joint_config.get('limits', {})
                    max_vel.append(limits.get('max_velocity', 500.0))
                    max_acc.append(limits.get('max_acceleration', 1000.0))
                    max_jerk.append(limits.get('max_acceleration', 1000.0) * 5)
                
                self.default_constraints = TrajectoryConstraints(
                    max_velocity=max_vel,
                    max_acceleration=max_acc,
                    max_jerk=max_jerk
                )
                
        except Exception as e:
            logger.warning(f"加载约束配置失败，使用默认值: {e}")
    
    @log_performance
    def plan_point_to_point(self, 
                           start_positions: List[float],
                           end_positions: List[float],
                           duration: Optional[float] = None,
                           interpolation_type: InterpolationType = InterpolationType.TRAPEZOIDAL,
                           constraints: Optional[TrajectoryConstraints] = None) -> Trajectory:
        """
        点到点轨迹规划
        
        Args:
            start_positions: 起始位置
            end_positions: 目标位置
            duration: 运动时间（可选，自动计算）
            interpolation_type: 插值类型
            constraints: 约束条件
            
        Returns:
            轨迹对象
        """
        if len(start_positions) != len(end_positions):
            raise ValueError("起始位置和目标位置维度不匹配")
        
        constraints = constraints or self.default_constraints
        
        # 计算位移
        displacements = [end - start for start, end in zip(start_positions, end_positions)]
        
        # 自动计算时间
        if duration is None:
            duration = self._calculate_optimal_duration(displacements, constraints)
        
        # 根据插值类型生成轨迹
        if interpolation_type == InterpolationType.LINEAR:
            points = self._generate_linear_trajectory(start_positions, end_positions, duration)
        elif interpolation_type == InterpolationType.CUBIC_SPLINE:
            points = self._generate_cubic_spline_trajectory(start_positions, end_positions, duration)
        elif interpolation_type == InterpolationType.QUINTIC:
            points = self._generate_quintic_trajectory(start_positions, end_positions, duration)
        elif interpolation_type == InterpolationType.TRAPEZOIDAL:
            points = self._generate_trapezoidal_trajectory(start_positions, end_positions, duration, constraints)
        elif interpolation_type == InterpolationType.S_CURVE:
            points = self._generate_s_curve_trajectory(start_positions, end_positions, duration, constraints)
        else:
            raise ValueError(f"不支持的插值类型: {interpolation_type}")
        
        trajectory = Trajectory(
            points=points,
            duration=duration,
            interpolation_type=interpolation_type,
            constraints=constraints,
            metadata={
                'start_positions': start_positions,
                'end_positions': end_positions,
                'displacements': displacements,
                'created_at': time.time()
            }
        )
        
        logger.info(f"生成点到点轨迹: {interpolation_type.value}, 时长={duration:.3f}s, 点数={len(points)}")
        return trajectory
    
    @log_performance
    def plan_multi_point(self,
                        waypoints: List[List[float]],
                        durations: Optional[List[float]] = None,
                        interpolation_type: InterpolationType = InterpolationType.CUBIC_SPLINE,
                        constraints: Optional[TrajectoryConstraints] = None) -> Trajectory:
        """
        多点轨迹规划
        
        Args:
            waypoints: 路径点列表
            durations: 各段时间（可选）
            interpolation_type: 插值类型
            constraints: 约束条件
            
        Returns:
            轨迹对象
        """
        if len(waypoints) < 2:
            raise ValueError("至少需要2个路径点")
        
        constraints = constraints or self.default_constraints
        
        # 自动计算各段时间
        if durations is None:
            durations = []
            for i in range(len(waypoints) - 1):
                displacements = [end - start for start, end in zip(waypoints[i], waypoints[i + 1])]
                duration = self._calculate_optimal_duration(displacements, constraints)
                durations.append(duration)
        
        # 生成连续轨迹
        all_points = []
        current_time = 0.0
        
        for i in range(len(waypoints) - 1):
            segment_duration = durations[i]
            
            # 生成段轨迹
            segment_trajectory = self.plan_point_to_point(
                waypoints[i], waypoints[i + 1], segment_duration, interpolation_type, constraints
            )
            
            # 调整时间戳
            for point in segment_trajectory.points:
                point.timestamp += current_time
                all_points.append(point)
            
            current_time += segment_duration
        
        total_duration = current_time
        
        trajectory = Trajectory(
            points=all_points,
            duration=total_duration,
            interpolation_type=interpolation_type,
            constraints=constraints,
            metadata={
                'waypoints': waypoints,
                'durations': durations,
                'segments': len(waypoints) - 1,
                'created_at': time.time()
            }
        )
        
        logger.info(f"生成多点轨迹: {len(waypoints)}个点, 总时长={total_duration:.3f}s")
        return trajectory
    
    def _calculate_optimal_duration(self, displacements: List[float], constraints: TrajectoryConstraints) -> float:
        """计算最优运动时间"""
        max_duration = 0.0
        
        for i, displacement in enumerate(displacements):
            if abs(displacement) < 1e-6:  # 忽略很小的位移
                continue
            
            max_vel = constraints.max_velocity[i]
            max_acc = constraints.max_acceleration[i]
            
            # 梯形速度曲线的最小时间
            # 如果能达到最大速度
            t_acc = max_vel / max_acc
            s_acc = 0.5 * max_acc * t_acc * t_acc
            
            if 2 * s_acc <= abs(displacement):
                # 有匀速段
                s_const = abs(displacement) - 2 * s_acc
                t_const = s_const / max_vel
                duration = 2 * t_acc + t_const
            else:
                # 三角形速度曲线
                duration = 2 * np.sqrt(abs(displacement) / max_acc)
            
            max_duration = max(max_duration, duration)
        
        return max(max_duration, 0.1)  # 最小时间0.1秒
    
    def _generate_linear_trajectory(self, start: List[float], end: List[float], duration: float) -> List[TrajectoryPoint]:
        """生成线性插值轨迹"""
        control_frequency = self.config.get('control', {}).get('frequency', 200)
        dt = 1.0 / control_frequency
        num_points = int(duration / dt) + 1
        
        points = []
        for i in range(num_points):
            t = i * dt
            alpha = t / duration if duration > 0 else 1.0
            alpha = min(alpha, 1.0)
            
            positions = [s + alpha * (e - s) for s, e in zip(start, end)]
            
            # 计算速度（常数）
            velocities = [(e - s) / duration if duration > 0 else 0.0 for s, e in zip(start, end)]
            
            # 加速度为0
            accelerations = [0.0] * len(positions)
            
            points.append(TrajectoryPoint(t, positions, velocities, accelerations))
        
        return points
    
    def _generate_cubic_spline_trajectory(self, start: List[float], end: List[float], duration: float) -> List[TrajectoryPoint]:
        """生成三次样条插值轨迹"""
        control_frequency = self.config.get('control', {}).get('frequency', 200)
        dt = 1.0 / control_frequency
        num_points = int(duration / dt) + 1
        
        # 时间节点
        t_nodes = np.array([0.0, duration])
        
        points = []
        for joint_idx in range(len(start)):
            # 位置节点
            pos_nodes = np.array([start[joint_idx], end[joint_idx]])
            
            # 创建三次样条插值
            cs = interpolate.CubicSpline(t_nodes, pos_nodes, bc_type='natural')
            
            # 生成轨迹点
            for i in range(num_points):
                t = i * dt
                t = min(t, duration)
                
                if joint_idx == 0:  # 第一个关节时创建点
                    points.append(TrajectoryPoint(t, [], [], []))
                
                # 计算位置、速度、加速度
                pos = float(cs(t))
                vel = float(cs(t, 1))  # 一阶导数
                acc = float(cs(t, 2))  # 二阶导数
                
                points[i].positions.append(pos)
                points[i].velocities.append(vel)
                points[i].accelerations.append(acc)
        
        return points
    
    def _generate_quintic_trajectory(self, start: List[float], end: List[float], duration: float) -> List[TrajectoryPoint]:
        """生成五次多项式轨迹"""
        control_frequency = self.config.get('control', {}).get('frequency', 200)
        dt = 1.0 / control_frequency
        num_points = int(duration / dt) + 1
        
        points = []
        
        for i in range(num_points):
            t = i * dt
            tau = t / duration if duration > 0 else 1.0
            tau = min(tau, 1.0)
            
            # 五次多项式系数 (边界条件：起始和结束速度、加速度为0)
            s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
            s_dot = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / duration if duration > 0 else 0
            s_ddot = (60 * tau - 180 * tau**2 + 120 * tau**3) / (duration**2) if duration > 0 else 0
            
            positions = [start_pos + s * (end_pos - start_pos) 
                        for start_pos, end_pos in zip(start, end)]
            velocities = [s_dot * (end_pos - start_pos) 
                         for start_pos, end_pos in zip(start, end)]
            accelerations = [s_ddot * (end_pos - start_pos) 
                           for start_pos, end_pos in zip(start, end)]
            
            points.append(TrajectoryPoint(t, positions, velocities, accelerations))
        
        return points
    
    def _generate_trapezoidal_trajectory(self, start: List[float], end: List[float], 
                                       duration: float, constraints: TrajectoryConstraints) -> List[TrajectoryPoint]:
        """生成梯形速度曲线轨迹"""
        control_frequency = self.config.get('control', {}).get('frequency', 200)
        dt = 1.0 / control_frequency
        num_points = int(duration / dt) + 1
        
        points = []
        
        # 为每个关节计算梯形速度曲线
        joint_profiles = []
        for joint_idx in range(len(start)):
            displacement = end[joint_idx] - start[joint_idx]
            max_vel = constraints.max_velocity[joint_idx]
            max_acc = constraints.max_acceleration[joint_idx]
            
            profile = self._calculate_trapezoidal_profile(displacement, max_vel, max_acc, duration)
            joint_profiles.append(profile)
        
        # 生成轨迹点
        for i in range(num_points):
            t = i * dt
            t = min(t, duration)
            
            positions = []
            velocities = []
            accelerations = []
            
            for joint_idx in range(len(start)):
                pos, vel, acc = self._evaluate_trapezoidal_profile(joint_profiles[joint_idx], t)
                positions.append(start[joint_idx] + pos)
                velocities.append(vel)
                accelerations.append(acc)
            
            points.append(TrajectoryPoint(t, positions, velocities, accelerations))
        
        return points
    
    def _calculate_trapezoidal_profile(self, displacement: float, max_vel: float, 
                                     max_acc: float, duration: float) -> Dict[str, float]:
        """计算梯形速度曲线参数"""
        abs_disp = abs(displacement)
        sign = 1 if displacement >= 0 else -1
        
        # 计算加速时间
        t_acc = max_vel / max_acc
        s_acc = 0.5 * max_acc * t_acc * t_acc
        
        if 2 * s_acc <= abs_disp:
            # 有匀速段
            s_const = abs_disp - 2 * s_acc
            t_const = s_const / max_vel
            t_total = 2 * t_acc + t_const
            
            # 如果计算时间小于给定时间，调整速度
            if t_total < duration:
                t_acc = (duration - abs_disp / max_vel) / 2
                if t_acc > 0:
                    max_vel = abs_disp / (duration - t_acc)
                    max_acc = max_vel / t_acc
                    t_const = duration - 2 * t_acc
                else:
                    # 三角形曲线
                    t_acc = duration / 2
                    max_vel = abs_disp / duration * 2
                    max_acc = max_vel / t_acc
                    t_const = 0
            else:
                t_const = duration - 2 * t_acc
        else:
            # 三角形速度曲线
            t_acc = np.sqrt(abs_disp / max_acc)
            max_vel = max_acc * t_acc
            t_const = 0
            
            # 调整到给定时间
            if 2 * t_acc < duration:
                t_acc = duration / 2
                max_vel = abs_disp / duration * 2
                max_acc = max_vel / t_acc
        
        return {
            'displacement': displacement,
            'max_velocity': max_vel * sign,
            'max_acceleration': max_acc,
            't_acc': t_acc,
            't_const': t_const,
            't_dec': t_acc,
            'sign': sign
        }
    
    def _evaluate_trapezoidal_profile(self, profile: Dict[str, float], t: float) -> Tuple[float, float, float]:
        """计算梯形速度曲线在时间t的值"""
        t_acc = profile['t_acc']
        t_const = profile['t_const']
        t_dec = profile['t_dec']
        max_vel = profile['max_velocity']
        max_acc = profile['max_acceleration']
        sign = profile['sign']
        
        if t <= t_acc:
            # 加速段
            pos = 0.5 * max_acc * t * t * sign
            vel = max_acc * t * sign
            acc = max_acc * sign
        elif t <= t_acc + t_const:
            # 匀速段
            pos = (0.5 * max_acc * t_acc * t_acc + max_vel * (t - t_acc)) * sign
            vel = max_vel
            acc = 0.0
        elif t <= t_acc + t_const + t_dec:
            # 减速段
            t_rel = t - t_acc - t_const
            pos = (0.5 * max_acc * t_acc * t_acc + max_vel * t_const + 
                   max_vel * t_rel - 0.5 * max_acc * t_rel * t_rel) * sign
            vel = (max_vel - max_acc * t_rel)
            acc = -max_acc * sign
        else:
            # 结束
            total_disp = abs(profile['displacement'])
            pos = total_disp * sign
            vel = 0.0
            acc = 0.0
        
        return pos, vel, acc
    
    def _generate_s_curve_trajectory(self, start: List[float], end: List[float], 
                                   duration: float, constraints: TrajectoryConstraints) -> List[TrajectoryPoint]:
        """生成S曲线轨迹"""
        control_frequency = self.config.get('control', {}).get('frequency', 200)
        dt = 1.0 / control_frequency
        num_points = int(duration / dt) + 1
        
        points = []
        
        # 为每个关节计算S曲线
        joint_profiles = []
        for joint_idx in range(len(start)):
            displacement = end[joint_idx] - start[joint_idx]
            max_vel = constraints.max_velocity[joint_idx]
            max_acc = constraints.max_acceleration[joint_idx]
            max_jerk = constraints.max_jerk[joint_idx]
            
            profile = self._calculate_s_curve_profile(displacement, max_vel, max_acc, max_jerk, duration)
            joint_profiles.append(profile)
        
        # 生成轨迹点
        for i in range(num_points):
            t = i * dt
            t = min(t, duration)
            
            positions = []
            velocities = []
            accelerations = []
            
            for joint_idx in range(len(start)):
                pos, vel, acc = self._evaluate_s_curve_profile(joint_profiles[joint_idx], t)
                positions.append(start[joint_idx] + pos)
                velocities.append(vel)
                accelerations.append(acc)
            
            points.append(TrajectoryPoint(t, positions, velocities, accelerations))
        
        return points
    
    def _calculate_s_curve_profile(self, displacement: float, max_vel: float, 
                                 max_acc: float, max_jerk: float, duration: float) -> Dict[str, float]:
        """计算S曲线参数"""
        abs_disp = abs(displacement)
        sign = 1 if displacement >= 0 else -1
        
        # 简化的S曲线：7段式
        t_jerk = max_acc / max_jerk
        t_acc = max_vel / max_acc
        
        # 如果加速时间太短，调整
        if t_acc < 2 * t_jerk:
            t_jerk = t_acc / 2
        
        # 计算各段时间
        t1 = t_jerk  # 加加速
        t2 = t_acc - t_jerk  # 匀加速
        t3 = t_jerk  # 减加速
        # t4 = 匀速段（待计算）
        t5 = t_jerk  # 加减速
        t6 = t_acc - t_jerk  # 匀减速
        t7 = t_jerk  # 减减速
        
        # 计算加速段位移
        s_acc = 0.5 * max_acc * t_acc * t_acc
        
        if 2 * s_acc <= abs_disp:
            # 有匀速段
            s_const = abs_disp - 2 * s_acc
            t4 = s_const / max_vel
        else:
            # 没有匀速段，重新计算
            t4 = 0
            # 简化处理：调整最大速度
            max_vel = np.sqrt(abs_disp * max_acc)
            t_acc = max_vel / max_acc
            if t_acc < 2 * t_jerk:
                t_jerk = t_acc / 2
            t2 = t_acc - t_jerk
            t6 = t2
        
        return {
            'displacement': displacement,
            'max_velocity': max_vel * sign,
            'max_acceleration': max_acc,
            'max_jerk': max_jerk,
            't1': t1, 't2': t2, 't3': t3, 't4': t4,
            't5': t5, 't6': t6, 't7': t7,
            'sign': sign
        }
    
    def _evaluate_s_curve_profile(self, profile: Dict[str, float], t: float) -> Tuple[float, float, float]:
        """计算S曲线在时间t的值 - 完整7段实现"""
        t1, t2, t3, t4, t5, t6, t7 = (
            profile['t1'], profile['t2'], profile['t3'], profile['t4'],
            profile['t5'], profile['t6'], profile['t7']
        )
        max_vel = abs(profile['max_velocity'])
        max_acc = profile['max_acceleration']
        max_jerk = profile['max_jerk']
        sign = profile['sign']
        
        # 累积时间点
        T1 = t1
        T2 = T1 + t2
        T3 = T2 + t3
        T4 = T3 + t4
        T5 = T4 + t5
        T6 = T5 + t6
        T7 = T6 + t7
        
        if t <= T1:
            # 第1段：加加速
            j = max_jerk
            a = j * t
            v = 0.5 * j * t * t
            s = (1/6) * j * t * t * t
        elif t <= T2:
            # 第2段：匀加速
            t_rel = t - T1
            j = 0
            a = max_acc
            v = 0.5 * max_jerk * t1 * t1 + max_acc * t_rel
            s = (1/6) * max_jerk * t1 * t1 * t1 + 0.5 * max_jerk * t1 * t1 * t_rel + 0.5 * max_acc * t_rel * t_rel
        elif t <= T3:
            # 第3段：减加速
            t_rel = t - T2
            j = -max_jerk
            a = max_acc - max_jerk * t_rel
            v_2 = 0.5 * max_jerk * t1 * t1 + max_acc * t2
            s_2 = (1/6) * max_jerk * t1 * t1 * t1 + 0.5 * max_jerk * t1 * t1 * t2 + 0.5 * max_acc * t2 * t2
            v = v_2 + max_acc * t_rel - 0.5 * max_jerk * t_rel * t_rel
            s = s_2 + v_2 * t_rel + 0.5 * max_acc * t_rel * t_rel - (1/6) * max_jerk * t_rel * t_rel * t_rel
        elif t <= T4:
            # 第4段：匀速
            t_rel = t - T3
            j = 0
            a = 0
            v = max_vel
            s_3 = self._calculate_s_curve_position_at_t3(profile)
            s = s_3 + max_vel * t_rel
        elif t <= T5:
            # 第5段：加减速
            t_rel = t - T4
            j = -max_jerk
            a = -max_jerk * t_rel
            s_4 = self._calculate_s_curve_position_at_t4(profile)
            v = max_vel - 0.5 * max_jerk * t_rel * t_rel
            s = s_4 + max_vel * t_rel - (1/6) * max_jerk * t_rel * t_rel * t_rel
        elif t <= T6:
            # 第6段：匀减速
            t_rel = t - T5
            j = 0
            a = -max_acc
            s_5 = self._calculate_s_curve_position_at_t5(profile)
            v_5 = max_vel - 0.5 * max_jerk * t5 * t5
            v = v_5 - max_acc * t_rel
            s = s_5 + v_5 * t_rel - 0.5 * max_acc * t_rel * t_rel
        elif t <= T7:
            # 第7段：减减速
            t_rel = t - T6
            j = max_jerk
            s_6 = self._calculate_s_curve_position_at_t6(profile)
            v_6 = max_vel - 0.5 * max_jerk * t5 * t5 - max_acc * t6
            a = -max_acc + max_jerk * t_rel
            v = v_6 - max_acc * t_rel + 0.5 * max_jerk * t_rel * t_rel
            s = s_6 + v_6 * t_rel - 0.5 * max_acc * t_rel * t_rel + (1/6) * max_jerk * t_rel * t_rel * t_rel
        else:
            # 结束
            s = abs(profile['displacement'])
            v = 0
            a = 0
        
        return s * sign, v * sign, a * sign
    
    def _calculate_s_curve_position_at_t3(self, profile: Dict[str, float]) -> float:
        """计算S曲线在T3时刻的位置"""
        t1, t2, t3 = profile['t1'], profile['t2'], profile['t3']
        max_jerk = profile['max_jerk']
        max_acc = profile['max_acceleration']
        
        s1 = (1/6) * max_jerk * t1 * t1 * t1
        s2 = 0.5 * max_jerk * t1 * t1 * t2 + 0.5 * max_acc * t2 * t2
        s3 = (0.5 * max_jerk * t1 * t1 + max_acc * t2) * t3 + 0.5 * max_acc * t3 * t3 - (1/6) * max_jerk * t3 * t3 * t3
        
        return s1 + s2 + s3
    
    def _calculate_s_curve_position_at_t4(self, profile: Dict[str, float]) -> float:
        """计算S曲线在T4时刻的位置"""
        s3 = self._calculate_s_curve_position_at_t3(profile)
        max_vel = abs(profile['max_velocity'])
        t4 = profile['t4']
        return s3 + max_vel * t4
    
    def _calculate_s_curve_position_at_t5(self, profile: Dict[str, float]) -> float:
        """计算S曲线在T5时刻的位置"""
        s4 = self._calculate_s_curve_position_at_t4(profile)
        max_vel = abs(profile['max_velocity'])
        max_jerk = profile['max_jerk']
        t5 = profile['t5']
        return s4 + max_vel * t5 - (1/6) * max_jerk * t5 * t5 * t5
    
    def _calculate_s_curve_position_at_t6(self, profile: Dict[str, float]) -> float:
        """计算S曲线在T6时刻的位置"""
        s5 = self._calculate_s_curve_position_at_t5(profile)
        max_vel = abs(profile['max_velocity'])
        max_jerk = profile['max_jerk']
        max_acc = profile['max_acceleration']
        t5, t6 = profile['t5'], profile['t6']
        v5 = max_vel - 0.5 * max_jerk * t5 * t5
        return s5 + v5 * t6 - 0.5 * max_acc * t6 * t6


# 全局轨迹规划器实例
_trajectory_planner = None


def get_trajectory_planner() -> TrajectoryPlanner:
    """获取全局轨迹规划器实例"""
    global _trajectory_planner
    if _trajectory_planner is None:
        _trajectory_planner = TrajectoryPlanner()
    return _trajectory_planner