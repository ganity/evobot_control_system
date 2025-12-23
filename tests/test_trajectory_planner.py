"""
轨迹规划器测试
"""

import pytest
import sys
from pathlib import Path
import numpy as np

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.trajectory_planner import (
    TrajectoryPlanner, InterpolationType, TrajectoryConstraints,
    TrajectoryPoint, Trajectory
)


class TestTrajectoryPlanner:
    """轨迹规划器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.planner = TrajectoryPlanner()
        self.start_positions = [1000, 1200, 1500, 1800, 2000, 1500, 1000, 1200, 1800, 2000]
        self.end_positions = [2000, 1800, 1000, 1200, 1500, 2000, 1800, 1500, 1000, 1200]
    
    def test_linear_trajectory(self):
        """测试线性轨迹规划"""
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            duration=2.0,
            interpolation_type=InterpolationType.LINEAR
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.duration == 2.0
        assert trajectory.interpolation_type == InterpolationType.LINEAR
        
        # 检查起始和结束位置
        first_point = trajectory.points[0]
        last_point = trajectory.points[-1]
        
        assert first_point.positions == self.start_positions
        assert last_point.positions == self.end_positions
    
    def test_trapezoidal_trajectory(self):
        """测试梯形速度轨迹规划"""
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            duration=3.0,
            interpolation_type=InterpolationType.TRAPEZOIDAL
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.interpolation_type == InterpolationType.TRAPEZOIDAL
        
        # 检查速度连续性
        for i in range(len(trajectory.points) - 1):
            current_point = trajectory.points[i]
            next_point = trajectory.points[i + 1]
            
            # 速度应该是连续的（允许小的数值误差）
            for j in range(len(current_point.velocities)):
                vel_diff = abs(next_point.velocities[j] - current_point.velocities[j])
                assert vel_diff < 100  # 允许的速度变化
    
    def test_cubic_spline_trajectory(self):
        """测试三次样条轨迹规划"""
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            duration=2.5,
            interpolation_type=InterpolationType.CUBIC_SPLINE
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.interpolation_type == InterpolationType.CUBIC_SPLINE
        
        # 检查平滑性（加速度连续性）
        for i in range(1, len(trajectory.points) - 1):
            prev_point = trajectory.points[i - 1]
            current_point = trajectory.points[i]
            next_point = trajectory.points[i + 1]
            
            # 加速度应该相对平滑
            for j in range(len(current_point.accelerations)):
                acc_change = abs(next_point.accelerations[j] - prev_point.accelerations[j])
                assert acc_change < 1000  # 允许的加速度变化
    
    def test_multi_point_trajectory(self):
        """测试多点轨迹规划"""
        waypoints = [
            [1500] * 10,  # 起始点
            [2000] * 10,  # 中间点1
            [1000] * 10,  # 中间点2
            [1500] * 10   # 结束点
        ]
        
        trajectory = self.planner.plan_multi_point(
            waypoints,
            interpolation_type=InterpolationType.CUBIC_SPLINE
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.metadata['segments'] == 3
        
        # 检查路径点
        first_point = trajectory.points[0]
        last_point = trajectory.points[-1]
        
        assert first_point.positions == waypoints[0]
        assert last_point.positions == waypoints[-1]
    
    def test_trajectory_constraints(self):
        """测试轨迹约束"""
        constraints = TrajectoryConstraints(
            max_velocity=[500] * 10,
            max_acceleration=[1000] * 10,
            max_jerk=[5000] * 10
        )
        
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            interpolation_type=InterpolationType.LINEAR,  # 使用线性插值，更可预测
            constraints=constraints
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.constraints == constraints
        
        # 验证轨迹基本属性
        first_point = trajectory.points[0]
        last_point = trajectory.points[-1]
        
        # 检查起始和结束位置
        assert first_point.positions == self.start_positions
        assert last_point.positions == self.end_positions
    
    def test_trajectory_point_interpolation(self):
        """测试轨迹点插值"""
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            duration=2.0,
            interpolation_type=InterpolationType.LINEAR
        )
        
        # 测试中间时刻的插值
        mid_time = trajectory.duration / 2
        mid_point = trajectory.get_point_at_time(mid_time)
        
        assert mid_point is not None
        assert mid_point.timestamp == mid_time
        
        # 线性插值的中点应该是起始和结束位置的平均值
        for i in range(len(mid_point.positions)):
            expected_pos = (self.start_positions[i] + self.end_positions[i]) / 2
            assert abs(mid_point.positions[i] - expected_pos) < 1  # 允许小误差
    
    def test_optimal_duration_calculation(self):
        """测试最优时间计算"""
        # 大位移应该需要更长时间
        large_displacement = [3000] * 10
        small_displacement = [1600] * 10
        
        large_trajectory = self.planner.plan_point_to_point(
            [0] * 10,
            large_displacement,
            interpolation_type=InterpolationType.TRAPEZOIDAL
        )
        
        small_trajectory = self.planner.plan_point_to_point(
            [1500] * 10,
            small_displacement,
            interpolation_type=InterpolationType.TRAPEZOIDAL
        )
        
        assert large_trajectory.duration > small_trajectory.duration
    
    def test_s_curve_trajectory(self):
        """测试S曲线轨迹"""
        trajectory = self.planner.plan_point_to_point(
            self.start_positions,
            self.end_positions,
            duration=3.0,
            interpolation_type=InterpolationType.S_CURVE
        )
        
        assert trajectory is not None
        assert len(trajectory.points) > 0
        assert trajectory.interpolation_type == InterpolationType.S_CURVE
        
        # S曲线应该有平滑的加速度变化
        accelerations = [point.accelerations[0] for point in trajectory.points]
        
        # 检查加速度的平滑性
        for i in range(1, len(accelerations) - 1):
            acc_change = abs(accelerations[i + 1] - accelerations[i - 1])
            assert acc_change < 2000  # S曲线的加速度变化应该相对平滑


if __name__ == "__main__":
    pytest.main([__file__, "-v"])