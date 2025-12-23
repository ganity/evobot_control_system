"""
运动学求解器测试

测试内容：
- 正运动学求解
- 逆运动学求解
- 雅可比矩阵计算
- 工作空间分析
- 奇异点检测
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.kinematics_solver import KinematicsSolver, Pose6D, EvoBot10DOF, KinematicsResult


class TestPose6D:
    """测试Pose6D类"""
    
    def test_pose_creation(self):
        """测试位姿创建"""
        pose = Pose6D(x=0.1, y=0.2, z=0.3, roll=0.1, pitch=0.2, yaw=0.3)
        
        assert pose.x == 0.1
        assert pose.y == 0.2
        assert pose.z == 0.3
        assert pose.roll == 0.1
        assert pose.pitch == 0.2
        assert pose.yaw == 0.3
    
    def test_default_pose(self):
        """测试默认位姿"""
        pose = Pose6D()
        
        assert pose.x == 0.0
        assert pose.y == 0.0
        assert pose.z == 0.0
        assert pose.roll == 0.0
        assert pose.pitch == 0.0
        assert pose.yaw == 0.0


class TestEvoBot10DOF:
    """测试EvoBot10DOF机器人模型"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            'joints': [
                {
                    'id': 0,
                    'name': 'joint_0',
                    'dh_params': {
                        'd': 0.05,
                        'a': 0.08,
                        'alpha': 1.57,
                        'theta': 0.0
                    },
                    'limits': {
                        'min_position': 0,
                        'max_position': 3000
                    }
                }
            ] * 10  # 10个相同的关节
        }
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_robot_creation(self, mock_config):
        """测试机器人模型创建"""
        with patch('roboticstoolbox.DHRobot'), \
             patch('roboticstoolbox.RevoluteDH'):
            
            robot = EvoBot10DOF(mock_config)
            
            assert len(robot.dh_params) == 10
            assert len(robot.joint_limits) == 10
    
    def test_dh_parameter_extraction(self, mock_config):
        """测试DH参数提取"""
        with patch('core.kinematics_solver.RTB_AVAILABLE', True), \
             patch('roboticstoolbox.DHRobot'), \
             patch('roboticstoolbox.RevoluteDH'):
            
            robot = EvoBot10DOF(mock_config)
            dh_params = robot._extract_dh_parameters()
            
            assert len(dh_params) == 10
            assert dh_params[0]['d'] == 0.05
            assert dh_params[0]['a'] == 0.08
    
    def test_joint_limits_extraction(self, mock_config):
        """测试关节限位提取"""
        with patch('core.kinematics_solver.RTB_AVAILABLE', True), \
             patch('roboticstoolbox.DHRobot'), \
             patch('roboticstoolbox.RevoluteDH'):
            
            robot = EvoBot10DOF(mock_config)
            limits = robot._extract_joint_limits()
            
            assert len(limits) == 10
            assert isinstance(limits[0], tuple)
            assert len(limits[0]) == 2


class TestKinematicsSolver:
    """测试运动学求解器"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """模拟配置管理器"""
        mock_manager = Mock()
        mock_manager.load_config.return_value = {
            'joints': [
                {
                    'id': i,
                    'name': f'joint_{i}',
                    'dh_params': {
                        'd': 0.05,
                        'a': 0.08,
                        'alpha': 0.0,
                        'theta': 0.0
                    },
                    'limits': {
                        'min_position': 0,
                        'max_position': 3000
                    }
                } for i in range(10)
            ]
        }
        return mock_manager
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', False)
    def test_solver_disabled_when_rtb_unavailable(self, mock_config_manager):
        """测试RTB不可用时求解器被禁用"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager):
            solver = KinematicsSolver()
            
            assert not solver.is_enabled()
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_solver_enabled_when_rtb_available(self, mock_config_manager):
        """测试RTB可用时求解器启用"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot:
            
            mock_robot_instance = Mock()
            mock_robot_instance.robot = Mock()
            mock_robot.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            assert solver.is_enabled()
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_forward_kinematics_success(self, mock_config_manager):
        """测试正运动学求解成功"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            # 模拟SE3变换矩阵
            mock_transform = Mock()
            mock_transform.t = np.array([0.1, 0.2, 0.3])
            mock_transform.rpy.return_value = np.array([0.1, 0.2, 0.3])
            
            mock_robot.fkine.return_value = mock_transform
            mock_robot_instance.robot = mock_robot
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试正运动学
            joint_angles = [0.1] * 10
            result = solver.forward_kinematics(joint_angles)
            
            assert result.success
            assert result.end_effector_pose is not None
            assert result.computation_time > 0
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_forward_kinematics_wrong_joint_count(self, mock_config_manager):
        """测试关节数量错误的正运动学"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF'):
            
            solver = KinematicsSolver()
            
            # 错误的关节数量
            joint_angles = [0.1] * 5  # 只有5个关节
            result = solver.forward_kinematics(joint_angles)
            
            assert not result.success
            assert "关节角度数量错误" in result.error_message
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_inverse_kinematics_success(self, mock_config_manager):
        """测试逆运动学求解成功"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            # 模拟逆运动学求解结果
            mock_solution = Mock()
            mock_solution.success = True
            mock_solution.q = np.array([0.1] * 10)
            mock_solution.iterations = 10
            
            mock_robot.ikine_LM.return_value = mock_solution
            mock_robot_instance.robot = mock_robot
            mock_robot_instance.joint_limits = [(-np.pi, np.pi)] * 10
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试逆运动学
            target_pose = Pose6D(x=0.1, y=0.2, z=0.3)
            result = solver.inverse_kinematics(target_pose)
            
            assert result.success
            assert result.joint_angles is not None
            assert len(result.joint_angles) == 10
            assert result.computation_time > 0
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_inverse_kinematics_no_solution(self, mock_config_manager):
        """测试逆运动学无解"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            # 模拟逆运动学求解失败
            mock_solution = Mock()
            mock_solution.success = False
            
            mock_robot.ikine_LM.return_value = mock_solution
            mock_robot_instance.robot = mock_robot
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试逆运动学
            target_pose = Pose6D(x=10.0, y=10.0, z=10.0)  # 不可达位置
            result = solver.inverse_kinematics(target_pose)
            
            assert not result.success
            assert "无解或不收敛" in result.error_message
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_jacobian_calculation(self, mock_config_manager):
        """测试雅可比矩阵计算"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            # 模拟雅可比矩阵
            mock_jacobian = np.random.rand(6, 10)
            mock_robot.jacob0.return_value = mock_jacobian
            
            mock_robot_instance.robot = mock_robot
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试雅可比矩阵计算
            joint_angles = [0.1] * 10
            jacobian = solver.jacobian(joint_angles)
            
            assert jacobian is not None
            assert jacobian.shape == (6, 10)
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_manipulability_calculation(self, mock_config_manager):
        """测试可操作性计算"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            # 模拟可操作性
            mock_robot.manipulability.return_value = 0.5
            
            mock_robot_instance.robot = mock_robot
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试可操作性计算
            joint_angles = [0.1] * 10
            manipulability = solver.manipulability(joint_angles)
            
            assert manipulability == 0.5
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_singularity_detection(self, mock_config_manager):
        """测试奇异点检测"""
        with patch('core.kinematics_solver.get_config_manager', return_value=mock_config_manager), \
             patch('core.kinematics_solver.EvoBot10DOF') as mock_robot_class:
            
            # 模拟机器人
            mock_robot_instance = Mock()
            mock_robot = Mock()
            
            mock_robot_instance.robot = mock_robot
            mock_robot_class.return_value = mock_robot_instance
            
            solver = KinematicsSolver()
            
            # 测试奇异点检测 - 正常情况
            mock_robot.manipulability.return_value = 0.1  # 高于阈值
            joint_angles = [0.1] * 10
            is_singular = solver.is_singular(joint_angles, threshold=0.05)
            assert not is_singular
            
            # 测试奇异点检测 - 奇异情况
            mock_robot.manipulability.return_value = 0.001  # 低于阈值
            is_singular = solver.is_singular(joint_angles, threshold=0.05)
            assert is_singular
    
    def test_solver_disabled_operations(self):
        """测试求解器禁用时的操作"""
        with patch('core.kinematics_solver.RTB_AVAILABLE', False):
            solver = KinematicsSolver()
            
            # 测试各种操作都应该返回失败或默认值
            joint_angles = [0.1] * 10
            target_pose = Pose6D()
            
            fk_result = solver.forward_kinematics(joint_angles)
            assert not fk_result.success
            assert "不可用" in fk_result.error_message
            
            ik_result = solver.inverse_kinematics(target_pose)
            assert not ik_result.success
            assert "不可用" in ik_result.error_message
            
            jacobian = solver.jacobian(joint_angles)
            assert jacobian is None
            
            manipulability = solver.manipulability(joint_angles)
            assert manipulability == 0.0
            
            is_singular = solver.is_singular(joint_angles)
            assert not is_singular


class TestKinematicsIntegration:
    """运动学集成测试"""
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True)
    def test_forward_inverse_consistency(self):
        """测试正逆运动学一致性"""
        # 这个测试需要真实的RTB环境，这里只是示例框架
        pass
    
    @patch('core.kinematics_solver.RTB_AVAILABLE', True) 
    def test_workspace_analysis_integration(self):
        """测试工作空间分析集成"""
        # 这个测试需要真实的RTB环境，这里只是示例框架
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])