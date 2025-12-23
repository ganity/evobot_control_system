"""
运动学求解器

基于Robotics Toolbox实现：
- 正运动学求解
- 逆运动学求解
- 雅可比矩阵计算
- 工作空间分析
- 奇异点检测
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import time

from core.lazy_kinematics import get_roboticstoolbox, get_spatialmath, is_kinematics_loaded
from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager

logger = get_logger(__name__)


@dataclass
class Pose6D:
    """6自由度位姿"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    
    def to_se3(self) -> 'SE3':
        """转换为SE3变换矩阵"""
        if not is_kinematics_loaded():
            raise RuntimeError("Kinematics libraries not loaded")
        SE3 = get_spatialmath().SE3
        return SE3.Trans(self.x, self.y, self.z) * SE3.RPY([self.roll, self.pitch, self.yaw])
    
    @classmethod
    def from_se3(cls, T: 'SE3') -> 'Pose6D':
        """从SE3变换矩阵创建"""
        if not is_kinematics_loaded():
            raise RuntimeError("Kinematics libraries not loaded")
        
        # 提取位置
        pos = T.t
        # 提取欧拉角
        rpy = T.rpy()
        
        return cls(
            x=float(pos[0]),
            y=float(pos[1]), 
            z=float(pos[2]),
            roll=float(rpy[0]),
            pitch=float(rpy[1]),
            yaw=float(rpy[2])
        )


@dataclass
class KinematicsResult:
    """运动学求解结果"""
    success: bool
    joint_angles: Optional[List[float]] = None
    end_effector_pose: Optional[Pose6D] = None
    error_message: Optional[str] = None
    computation_time: float = 0.0
    iterations: int = 0


class EvoBot10DOF:
    """EvoBot 10自由度机器人模型"""
    
    def __init__(self, config: Dict):
        """初始化机器人模型"""
        if not is_kinematics_loaded():
            raise RuntimeError("Kinematics libraries not loaded")
        
        self.config = config
        self.joints_config = config.get('joints', [])
        
        # 构建DH参数
        self.dh_params = self._extract_dh_parameters()
        
        # 创建机器人模型
        self.robot = self._create_robot_model()
        
        # 关节限位
        self.joint_limits = self._extract_joint_limits()
        
        logger.info(f"EvoBot 10DOF模型创建完成: {len(self.dh_params)}个关节")
    
    def _extract_dh_parameters(self) -> List[Dict]:
        """从配置提取DH参数"""
        dh_params = []
        
        for joint_config in self.joints_config:
            dh = joint_config.get('dh_params', {})
            
            # 默认DH参数（如果配置中没有）
            default_dh = {
                'd': 0.0,      # 连杆偏移
                'a': 0.05,     # 连杆长度  
                'alpha': 0.0,  # 连杆扭角
                'theta': 0.0   # 关节角度偏移
            }
            
            # 合并配置
            dh_param = {**default_dh, **dh}
            dh_params.append(dh_param)
        
        # 如果配置不足10个关节，补充默认参数
        while len(dh_params) < 10:
            dh_params.append({
                'd': 0.0,
                'a': 0.05,
                'alpha': 0.0,
                'theta': 0.0
            })
        
        return dh_params
    
    def _create_robot_model(self) -> 'DHRobot':
        """创建机器人DH模型"""
        rtb = get_roboticstoolbox()
        RevoluteDH = rtb.RevoluteDH
        DHRobot = rtb.DHRobot
        
        links = []
        
        for i, dh in enumerate(self.dh_params):
            # 创建旋转关节（假设都是旋转关节）
            link = RevoluteDH(
                d=dh['d'],
                a=dh['a'], 
                alpha=dh['alpha'],
                offset=dh['theta'],
                qlim=self._get_joint_limit(i)
            )
            links.append(link)
        
        # 创建机器人
        robot = DHRobot(
            links,
            name="EvoBot10DOF",
            manufacturer="EvoBot"
        )
        
        return robot
    
    def _get_joint_limit(self, joint_id: int) -> Tuple[float, float]:
        """获取关节限位"""
        if joint_id < len(self.joints_config):
            limits = self.joints_config[joint_id].get('limits', {})
            min_pos = limits.get('min_position', 0)
            max_pos = limits.get('max_position', 3000)
            
            # 转换为弧度（假设配置中是度或编码器值）
            min_rad = np.deg2rad(min_pos * 360 / 3000)  # 假设3000对应360度
            max_rad = np.deg2rad(max_pos * 360 / 3000)
            
            return (min_rad, max_rad)
        
        return (-np.pi, np.pi)  # 默认限位
    
    def _extract_joint_limits(self) -> List[Tuple[float, float]]:
        """提取所有关节限位"""
        limits = []
        for i in range(10):
            limits.append(self._get_joint_limit(i))
        return limits


class KinematicsSolver:
    """运动学求解器"""
    
    def __init__(self):
        """初始化运动学求解器"""
        # 延迟初始化，只有在实际使用时才加载库
        self.enabled = False
        self._initialized = False
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        
        logger.info("运动学求解器创建完成（延迟加载模式）")
    
    def _ensure_initialized(self):
        """确保运动学库已初始化"""
        if self._initialized:
            return
            
        if not is_kinematics_loaded():
            logger.info("首次使用运动学功能，正在加载库...")
            try:
                # 触发库加载
                get_roboticstoolbox()
                get_spatialmath()
            except ImportError as e:
                logger.error(f"运动学库加载失败: {e}")
                return
        
        # 创建机器人模型
        try:
            self.robot_model = EvoBot10DOF(self.config)
            self.robot = self.robot_model.robot
            self.enabled = True
            self._initialized = True
            logger.info("运动学求解器初始化完成")
        except Exception as e:
            logger.error(f"创建机器人模型失败: {e}")
            return
        
        # 求解器配置
        self.ik_solver_config = {
            'method': 'LM',  # Levenberg-Marquardt
            'max_iterations': 100,
            'tolerance': 1e-6,
            'lambda_min': 1e-12,
            'lambda_max': 1e6
        }
        
        logger.info("运动学求解器初始化完成")
    
    def is_enabled(self) -> bool:
        """检查求解器是否可用"""
        return self.enabled
    
    @log_performance
    def forward_kinematics(self, joint_angles: List[float]) -> KinematicsResult:
        """
        正运动学求解
        
        Args:
            joint_angles: 关节角度（弧度）
            
        Returns:
            运动学求解结果
        """
        # 确保运动学库已初始化
        self._ensure_initialized()
        
        if not self.enabled:
            return KinematicsResult(
                success=False,
                error_message="运动学求解器不可用"
            )
        
        start_time = time.time()
        
        try:
            # 检查关节角度数量
            if len(joint_angles) != 10:
                return KinematicsResult(
                    success=False,
                    error_message=f"关节角度数量错误: {len(joint_angles)} != 10"
                )
            
            # 转换为numpy数组
            q = np.array(joint_angles)
            
            # 计算正运动学
            T = self.robot.fkine(q)
            
            # 转换为Pose6D
            pose = Pose6D.from_se3(T)
            
            computation_time = time.time() - start_time
            
            return KinematicsResult(
                success=True,
                joint_angles=joint_angles,
                end_effector_pose=pose,
                computation_time=computation_time
            )
            
        except Exception as e:
            logger.error(f"正运动学求解失败: {e}")
            return KinematicsResult(
                success=False,
                error_message=str(e),
                computation_time=time.time() - start_time
            )
    
    @log_performance
    def inverse_kinematics(self, target_pose: Pose6D, 
                          initial_guess: Optional[List[float]] = None) -> KinematicsResult:
        """
        逆运动学求解
        
        Args:
            target_pose: 目标位姿
            initial_guess: 初始猜测关节角度
            
        Returns:
            运动学求解结果
        """
        # 确保运动学库已初始化
        self._ensure_initialized()
        
        if not self.enabled:
            return KinematicsResult(
                success=False,
                error_message="运动学求解器不可用"
            )
        
        start_time = time.time()
        
        try:
            # 转换目标位姿为SE3
            T_target = target_pose.to_se3()
            
            # 初始猜测
            if initial_guess is None:
                q0 = np.zeros(10)  # 零位作为初始猜测
            else:
                if len(initial_guess) != 10:
                    return KinematicsResult(
                        success=False,
                        error_message=f"初始猜测角度数量错误: {len(initial_guess)} != 10"
                    )
                q0 = np.array(initial_guess)
            
            # 逆运动学求解
            solution = self.robot.ikine_LM(
                T_target,
                q0=q0,
                **self.ik_solver_config
            )
            
            computation_time = time.time() - start_time
            
            if solution.success:
                # 验证解的有效性
                joint_angles = solution.q.tolist()
                
                # 检查关节限位
                if self._check_joint_limits(joint_angles):
                    return KinematicsResult(
                        success=True,
                        joint_angles=joint_angles,
                        end_effector_pose=target_pose,
                        computation_time=computation_time,
                        iterations=solution.iterations if hasattr(solution, 'iterations') else 0
                    )
                else:
                    return KinematicsResult(
                        success=False,
                        error_message="求解结果超出关节限位",
                        computation_time=computation_time
                    )
            else:
                return KinematicsResult(
                    success=False,
                    error_message="逆运动学求解失败：无解或不收敛",
                    computation_time=computation_time
                )
                
        except Exception as e:
            logger.error(f"逆运动学求解失败: {e}")
            return KinematicsResult(
                success=False,
                error_message=str(e),
                computation_time=time.time() - start_time
            )
    
    def _check_joint_limits(self, joint_angles: List[float]) -> bool:
        """检查关节限位"""
        for i, angle in enumerate(joint_angles):
            if i < len(self.robot_model.joint_limits):
                min_limit, max_limit = self.robot_model.joint_limits[i]
                if angle < min_limit or angle > max_limit:
                    logger.warning(f"关节{i}超限: {angle} not in [{min_limit}, {max_limit}]")
                    return False
        return True
    
    @log_performance
    def jacobian(self, joint_angles: List[float]) -> Optional[np.ndarray]:
        """
        计算雅可比矩阵
        
        Args:
            joint_angles: 关节角度
            
        Returns:
            雅可比矩阵 (6x10)
        """
        if not self.enabled:
            return None
        
        try:
            q = np.array(joint_angles)
            J = self.robot.jacob0(q)  # 基坐标系雅可比
            return J
        except Exception as e:
            logger.error(f"雅可比矩阵计算失败: {e}")
            return None
    
    def manipulability(self, joint_angles: List[float]) -> float:
        """
        计算可操作性指标
        
        Args:
            joint_angles: 关节角度
            
        Returns:
            可操作性指标
        """
        if not self.enabled:
            return 0.0
        
        try:
            q = np.array(joint_angles)
            return float(self.robot.manipulability(q))
        except Exception as e:
            logger.error(f"可操作性计算失败: {e}")
            return 0.0
    
    def is_singular(self, joint_angles: List[float], threshold: float = 1e-3) -> bool:
        """
        检测奇异点
        
        Args:
            joint_angles: 关节角度
            threshold: 奇异性阈值
            
        Returns:
            是否为奇异点
        """
        manipulability = self.manipulability(joint_angles)
        return manipulability < threshold
    
    def workspace_analysis(self, num_samples: int = 1000) -> Dict[str, Any]:
        """
        工作空间分析
        
        Args:
            num_samples: 采样点数量
            
        Returns:
            工作空间分析结果
        """
        if not self.enabled:
            return {}
        
        try:
            # 随机采样关节空间
            workspace_points = []
            valid_configs = []
            
            for _ in range(num_samples):
                # 在关节限位内随机采样
                q = []
                for i in range(10):
                    min_limit, max_limit = self.robot_model.joint_limits[i]
                    angle = np.random.uniform(min_limit, max_limit)
                    q.append(angle)
                
                # 计算正运动学
                result = self.forward_kinematics(q)
                if result.success:
                    pose = result.end_effector_pose
                    workspace_points.append([pose.x, pose.y, pose.z])
                    valid_configs.append(q)
            
            if not workspace_points:
                return {}
            
            workspace_points = np.array(workspace_points)
            
            # 计算工作空间边界
            min_bounds = np.min(workspace_points, axis=0)
            max_bounds = np.max(workspace_points, axis=0)
            
            # 计算工作空间体积（近似）
            volume = np.prod(max_bounds - min_bounds)
            
            return {
                'num_valid_configs': len(valid_configs),
                'workspace_points': workspace_points.tolist(),
                'min_bounds': min_bounds.tolist(),
                'max_bounds': max_bounds.tolist(),
                'workspace_volume': float(volume),
                'reachability_ratio': len(valid_configs) / num_samples
            }
            
        except Exception as e:
            logger.error(f"工作空间分析失败: {e}")
            return {}
    
    def get_robot_info(self) -> Dict[str, Any]:
        """获取机器人模型信息"""
        if not self.enabled:
            return {}
        
        return {
            'name': self.robot.name,
            'num_joints': self.robot.n,
            'joint_limits': self.robot_model.joint_limits,
            'dh_parameters': self.robot_model.dh_params,
            'base_transform': self.robot.base.A.tolist() if hasattr(self.robot, 'base') else None,
            'tool_transform': self.robot.tool.A.tolist() if hasattr(self.robot, 'tool') else None
        }


# 全局运动学求解器实例
_kinematics_solver = None


def get_kinematics_solver() -> KinematicsSolver:
    """获取全局运动学求解器实例"""
    global _kinematics_solver
    if _kinematics_solver is None:
        _kinematics_solver = KinematicsSolver()
    return _kinematics_solver