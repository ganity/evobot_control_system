"""
高级运动规划器

基于PythonRobotics算法实现：
- RRT路径规划
- A*路径规划  
- 轨迹优化
- 碰撞检测
- 动态窗口法
"""

import numpy as np
import math
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass
from enum import Enum
import time

from utils.logger import get_logger, log_performance
from core.kinematics_solver import get_kinematics_solver, Pose6D, KinematicsResult
from core.trajectory_planner import Trajectory, TrajectoryPoint, TrajectoryConstraints

logger = get_logger(__name__)


class PlanningAlgorithm(Enum):
    """规划算法类型"""
    RRT = "rrt"
    RRT_STAR = "rrt_star"
    A_STAR = "a_star"
    DIJKSTRA = "dijkstra"
    PRM = "prm"


@dataclass
class PlanningResult:
    """规划结果"""
    success: bool
    path: Optional[List[List[float]]] = None
    cost: float = 0.0
    computation_time: float = 0.0
    iterations: int = 0
    error_message: Optional[str] = None


@dataclass
class Obstacle:
    """障碍物定义"""
    center: List[float]  # 中心位置
    size: List[float]    # 尺寸 [长, 宽, 高]
    type: str = "box"    # 类型：box, sphere, cylinder


class CollisionChecker:
    """碰撞检测器"""
    
    def __init__(self):
        """初始化碰撞检测器"""
        self.obstacles: List[Obstacle] = []
        self.kinematics_solver = get_kinematics_solver()
        
    def add_obstacle(self, obstacle: Obstacle):
        """添加障碍物"""
        self.obstacles.append(obstacle)
        logger.info(f"添加障碍物: {obstacle.type} at {obstacle.center}")
    
    def remove_all_obstacles(self):
        """移除所有障碍物"""
        self.obstacles.clear()
        logger.info("已清除所有障碍物")
    
    def check_collision(self, joint_angles: List[float]) -> bool:
        """
        检查关节配置是否碰撞
        
        Args:
            joint_angles: 关节角度
            
        Returns:
            是否碰撞
        """
        if not self.kinematics_solver.is_enabled():
            return False  # 无法检测，假设无碰撞
        
        # 计算末端执行器位置
        fk_result = self.kinematics_solver.forward_kinematics(joint_angles)
        if not fk_result.success:
            return True  # 运动学求解失败，认为碰撞
        
        pose = fk_result.end_effector_pose
        end_effector_pos = [pose.x, pose.y, pose.z]
        
        # 检查与障碍物的碰撞
        for obstacle in self.obstacles:
            if self._check_point_obstacle_collision(end_effector_pos, obstacle):
                return True
        
        return False
    
    def _check_point_obstacle_collision(self, point: List[float], obstacle: Obstacle) -> bool:
        """检查点与障碍物的碰撞"""
        if obstacle.type == "box":
            return self._check_point_box_collision(point, obstacle)
        elif obstacle.type == "sphere":
            return self._check_point_sphere_collision(point, obstacle)
        else:
            return False
    
    def _check_point_box_collision(self, point: List[float], obstacle: Obstacle) -> bool:
        """检查点与盒子的碰撞"""
        center = obstacle.center
        size = obstacle.size
        
        for i in range(3):
            if abs(point[i] - center[i]) > size[i] / 2:
                return False
        return True
    
    def _check_point_sphere_collision(self, point: List[float], obstacle: Obstacle) -> bool:
        """检查点与球体的碰撞"""
        center = obstacle.center
        radius = obstacle.size[0] / 2  # 假设size[0]是直径
        
        distance = math.sqrt(sum((point[i] - center[i])**2 for i in range(3)))
        return distance <= radius


class RRTPlanner:
    """RRT路径规划器"""
    
    def __init__(self, collision_checker: CollisionChecker):
        """初始化RRT规划器"""
        self.collision_checker = collision_checker
        self.kinematics_solver = get_kinematics_solver()
        
        # RRT参数
        self.max_iterations = 5000
        self.step_size = 0.1  # 弧度
        self.goal_tolerance = 0.1
        self.goal_sample_rate = 0.1  # 10%概率采样目标
        
    @log_performance
    def plan(self, start_config: List[float], goal_config: List[float]) -> PlanningResult:
        """
        RRT路径规划
        
        Args:
            start_config: 起始关节配置
            goal_config: 目标关节配置
            
        Returns:
            规划结果
        """
        start_time = time.time()
        
        try:
            # 检查起始和目标配置
            if self.collision_checker.check_collision(start_config):
                return PlanningResult(
                    success=False,
                    error_message="起始配置发生碰撞",
                    computation_time=time.time() - start_time
                )
            
            if self.collision_checker.check_collision(goal_config):
                return PlanningResult(
                    success=False,
                    error_message="目标配置发生碰撞",
                    computation_time=time.time() - start_time
                )
            
            # 初始化RRT树
            tree = {0: {'config': start_config, 'parent': None, 'cost': 0.0}}
            node_count = 1
            
            for iteration in range(self.max_iterations):
                # 采样随机配置
                if np.random.random() < self.goal_sample_rate:
                    rand_config = goal_config
                else:
                    rand_config = self._sample_random_config()
                
                # 找到最近节点
                nearest_id = self._find_nearest_node(tree, rand_config)
                nearest_config = tree[nearest_id]['config']
                
                # 扩展树
                new_config = self._steer(nearest_config, rand_config)
                
                # 检查路径是否无碰撞
                if self._is_path_collision_free(nearest_config, new_config):
                    # 添加新节点
                    cost = tree[nearest_id]['cost'] + self._distance(nearest_config, new_config)
                    tree[node_count] = {
                        'config': new_config,
                        'parent': nearest_id,
                        'cost': cost
                    }
                    
                    # 检查是否到达目标
                    if self._distance(new_config, goal_config) < self.goal_tolerance:
                        # 构建路径
                        path = self._build_path(tree, node_count, goal_config)
                        
                        return PlanningResult(
                            success=True,
                            path=path,
                            cost=cost,
                            computation_time=time.time() - start_time,
                            iterations=iteration + 1
                        )
                    
                    node_count += 1
            
            # 未找到路径
            return PlanningResult(
                success=False,
                error_message="超过最大迭代次数",
                computation_time=time.time() - start_time,
                iterations=self.max_iterations
            )
            
        except Exception as e:
            logger.error(f"RRT规划失败: {e}")
            return PlanningResult(
                success=False,
                error_message=str(e),
                computation_time=time.time() - start_time
            )
    
    def _sample_random_config(self) -> List[float]:
        """采样随机关节配置"""
        config = []
        
        # 获取关节限位
        if self.kinematics_solver.is_enabled():
            robot_info = self.kinematics_solver.get_robot_info()
            joint_limits = robot_info.get('joint_limits', [])
        else:
            joint_limits = []
        
        for i in range(10):
            if i < len(joint_limits):
                min_limit, max_limit = joint_limits[i]
                angle = np.random.uniform(min_limit, max_limit)
            else:
                angle = np.random.uniform(-np.pi, np.pi)
            config.append(angle)
        
        return config
    
    def _find_nearest_node(self, tree: Dict, target_config: List[float]) -> int:
        """找到最近的树节点"""
        min_distance = float('inf')
        nearest_id = 0
        
        for node_id, node_data in tree.items():
            distance = self._distance(node_data['config'], target_config)
            if distance < min_distance:
                min_distance = distance
                nearest_id = node_id
        
        return nearest_id
    
    def _distance(self, config1: List[float], config2: List[float]) -> float:
        """计算关节配置间的距离"""
        return math.sqrt(sum((a - b)**2 for a, b in zip(config1, config2)))
    
    def _steer(self, from_config: List[float], to_config: List[float]) -> List[float]:
        """从一个配置向另一个配置扩展"""
        direction = np.array(to_config) - np.array(from_config)
        distance = np.linalg.norm(direction)
        
        if distance <= self.step_size:
            return to_config
        
        unit_direction = direction / distance
        new_config = np.array(from_config) + self.step_size * unit_direction
        
        return new_config.tolist()
    
    def _is_path_collision_free(self, config1: List[float], config2: List[float]) -> bool:
        """检查两个配置间的路径是否无碰撞"""
        # 简单的线性插值检查
        num_checks = 10
        
        for i in range(num_checks + 1):
            alpha = i / num_checks
            intermediate_config = [
                c1 + alpha * (c2 - c1) for c1, c2 in zip(config1, config2)
            ]
            
            if self.collision_checker.check_collision(intermediate_config):
                return False
        
        return True
    
    def _build_path(self, tree: Dict, goal_node_id: int, goal_config: List[float]) -> List[List[float]]:
        """构建从起点到终点的路径"""
        path = [goal_config]
        current_id = goal_node_id
        
        while current_id is not None:
            path.append(tree[current_id]['config'])
            current_id = tree[current_id]['parent']
        
        path.reverse()
        return path


class AdvancedMotionPlanner:
    """高级运动规划器"""
    
    def __init__(self):
        """初始化高级运动规划器"""
        self.collision_checker = CollisionChecker()
        self.rrt_planner = RRTPlanner(self.collision_checker)
        self.kinematics_solver = get_kinematics_solver()
        
        logger.info("高级运动规划器初始化完成")
    
    def set_obstacles(self, obstacles: List[Obstacle]):
        """设置障碍物"""
        self.collision_checker.remove_all_obstacles()
        for obstacle in obstacles:
            self.collision_checker.add_obstacle(obstacle)
    
    @log_performance
    def plan_cartesian_path(self, 
                           start_pose: Pose6D,
                           goal_pose: Pose6D,
                           algorithm: PlanningAlgorithm = PlanningAlgorithm.RRT) -> PlanningResult:
        """
        笛卡尔空间路径规划
        
        Args:
            start_pose: 起始位姿
            goal_pose: 目标位姿
            algorithm: 规划算法
            
        Returns:
            规划结果
        """
        if not self.kinematics_solver.is_enabled():
            return PlanningResult(
                success=False,
                error_message="运动学求解器不可用"
            )
        
        try:
            # 逆运动学求解起始和目标关节配置
            start_ik = self.kinematics_solver.inverse_kinematics(start_pose)
            if not start_ik.success:
                return PlanningResult(
                    success=False,
                    error_message=f"起始位姿逆运动学求解失败: {start_ik.error_message}"
                )
            
            goal_ik = self.kinematics_solver.inverse_kinematics(goal_pose)
            if not goal_ik.success:
                return PlanningResult(
                    success=False,
                    error_message=f"目标位姿逆运动学求解失败: {goal_ik.error_message}"
                )
            
            # 在关节空间进行路径规划
            return self.plan_joint_path(
                start_ik.joint_angles,
                goal_ik.joint_angles,
                algorithm
            )
            
        except Exception as e:
            logger.error(f"笛卡尔路径规划失败: {e}")
            return PlanningResult(
                success=False,
                error_message=str(e)
            )
    
    @log_performance
    def plan_joint_path(self,
                       start_config: List[float],
                       goal_config: List[float],
                       algorithm: PlanningAlgorithm = PlanningAlgorithm.RRT) -> PlanningResult:
        """
        关节空间路径规划
        
        Args:
            start_config: 起始关节配置
            goal_config: 目标关节配置
            algorithm: 规划算法
            
        Returns:
            规划结果
        """
        try:
            if algorithm == PlanningAlgorithm.RRT:
                return self.rrt_planner.plan(start_config, goal_config)
            else:
                return PlanningResult(
                    success=False,
                    error_message=f"不支持的规划算法: {algorithm.value}"
                )
                
        except Exception as e:
            logger.error(f"关节路径规划失败: {e}")
            return PlanningResult(
                success=False,
                error_message=str(e)
            )
    
    def optimize_path(self, path: List[List[float]]) -> List[List[float]]:
        """
        路径优化
        
        Args:
            path: 原始路径
            
        Returns:
            优化后的路径
        """
        if len(path) < 3:
            return path
        
        try:
            # 简单的路径平滑
            optimized_path = [path[0]]  # 起点
            
            i = 0
            while i < len(path) - 1:
                # 尝试直接连接到更远的点
                for j in range(len(path) - 1, i + 1, -1):
                    if self.collision_checker._is_path_collision_free(path[i], path[j]):
                        optimized_path.append(path[j])
                        i = j
                        break
                else:
                    # 无法跳跃，添加下一个点
                    i += 1
                    if i < len(path):
                        optimized_path.append(path[i])
            
            logger.info(f"路径优化: {len(path)} -> {len(optimized_path)} 个点")
            return optimized_path
            
        except Exception as e:
            logger.error(f"路径优化失败: {e}")
            return path
    
    def path_to_trajectory(self, 
                          path: List[List[float]], 
                          total_duration: float,
                          constraints: Optional[TrajectoryConstraints] = None) -> Optional[Trajectory]:
        """
        将路径转换为轨迹
        
        Args:
            path: 关节空间路径
            total_duration: 总时间
            constraints: 轨迹约束
            
        Returns:
            轨迹对象
        """
        if not path or len(path) < 2:
            return None
        
        try:
            from core.trajectory_planner import get_trajectory_planner, InterpolationType
            
            planner = get_trajectory_planner()
            
            # 使用多点轨迹规划
            durations = [total_duration / (len(path) - 1)] * (len(path) - 1)
            
            trajectory = planner.plan_multi_point(
                waypoints=path,
                durations=durations,
                interpolation_type=InterpolationType.CUBIC_SPLINE,
                constraints=constraints
            )
            
            return trajectory
            
        except Exception as e:
            logger.error(f"路径转轨迹失败: {e}")
            return None


# 全局高级运动规划器实例
_advanced_planner = None


def get_advanced_planner() -> AdvancedMotionPlanner:
    """获取全局高级运动规划器实例"""
    global _advanced_planner
    if _advanced_planner is None:
        _advanced_planner = AdvancedMotionPlanner()
    return _advanced_planner