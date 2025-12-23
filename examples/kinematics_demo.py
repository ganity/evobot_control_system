#!/usr/bin/env python3
"""
运动学求解器演示脚本

演示内容：
1. 正运动学求解
2. 逆运动学求解
3. 工作空间分析
4. 路径规划
5. 实时控制
"""

import sys
import os
import numpy as np
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.kinematics_solver import get_kinematics_solver, Pose6D
from core.advanced_planner import get_advanced_planner, Obstacle, PlanningAlgorithm
from core.motion_controller import get_motion_controller
from utils.logger import get_logger

logger = get_logger(__name__)


def demo_forward_kinematics():
    """演示正运动学求解"""
    print("\n=== 正运动学求解演示 ===")
    
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用，请安装roboticstoolbox-python")
        return
    
    # 测试多个关节配置
    test_configs = [
        [0.0] * 10,  # 零位
        [0.1] * 10,  # 小角度
        [0.0, 0.1, 0.2, 0.0, -0.1, 0.0, 0.1, -0.2, 0.0, 0.1],  # 混合角度
    ]
    
    for i, joint_angles in enumerate(test_configs):
        print(f"\n配置 {i+1}: {[f'{np.rad2deg(a):.1f}°' for a in joint_angles]}")
        
        result = solver.forward_kinematics(joint_angles)
        
        if result.success:
            pose = result.end_effector_pose
            print(f"  位置: ({pose.x*1000:.1f}, {pose.y*1000:.1f}, {pose.z*1000:.1f}) mm")
            print(f"  姿态: ({np.rad2deg(pose.roll):.1f}, {np.rad2deg(pose.pitch):.1f}, {np.rad2deg(pose.yaw):.1f})°")
            print(f"  计算时间: {result.computation_time*1000:.2f} ms")
            
            # 计算可操作性
            manipulability = solver.manipulability(joint_angles)
            print(f"  可操作性: {manipulability:.6f}")
            
            # 检测奇异点
            is_singular = solver.is_singular(joint_angles)
            print(f"  奇异点: {'是' if is_singular else '否'}")
        else:
            print(f"  求解失败: {result.error_message}")


def demo_inverse_kinematics():
    """演示逆运动学求解"""
    print("\n=== 逆运动学求解演示 ===")
    
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用")
        return
    
    # 测试多个目标位姿
    test_poses = [
        Pose6D(x=0.2, y=0.0, z=0.3, roll=0.0, pitch=0.0, yaw=0.0),
        Pose6D(x=0.1, y=0.2, z=0.4, roll=0.1, pitch=0.0, yaw=0.1),
        Pose6D(x=0.3, y=-0.1, z=0.2, roll=0.0, pitch=0.1, yaw=0.0),
    ]
    
    for i, target_pose in enumerate(test_poses):
        print(f"\n目标位姿 {i+1}:")
        print(f"  位置: ({target_pose.x*1000:.1f}, {target_pose.y*1000:.1f}, {target_pose.z*1000:.1f}) mm")
        print(f"  姿态: ({np.rad2deg(target_pose.roll):.1f}, {np.rad2deg(target_pose.pitch):.1f}, {np.rad2deg(target_pose.yaw):.1f})°")
        
        result = solver.inverse_kinematics(target_pose)
        
        if result.success:
            print(f"  求解成功:")
            joint_angles_deg = [np.rad2deg(angle) for angle in result.joint_angles]
            print(f"  关节角度: {[f'{angle:.1f}°' for angle in joint_angles_deg]}")
            print(f"  计算时间: {result.computation_time*1000:.2f} ms")
            print(f"  迭代次数: {result.iterations}")
            
            # 验证正运动学
            fk_result = solver.forward_kinematics(result.joint_angles)
            if fk_result.success:
                pose_error = np.sqrt(
                    (target_pose.x - fk_result.end_effector_pose.x)**2 +
                    (target_pose.y - fk_result.end_effector_pose.y)**2 +
                    (target_pose.z - fk_result.end_effector_pose.z)**2
                )
                print(f"  位置误差: {pose_error*1000:.3f} mm")
        else:
            print(f"  求解失败: {result.error_message}")


def demo_workspace_analysis():
    """演示工作空间分析"""
    print("\n=== 工作空间分析演示 ===")
    
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用")
        return
    
    print("开始工作空间分析（这可能需要几秒钟）...")
    start_time = time.time()
    
    workspace_data = solver.workspace_analysis(num_samples=500)  # 减少采样数以加快演示
    
    analysis_time = time.time() - start_time
    
    if workspace_data:
        print(f"分析完成，耗时: {analysis_time:.2f} 秒")
        print(f"采样点数: {workspace_data['num_valid_configs']}")
        print(f"可达性比例: {workspace_data['reachability_ratio']:.1%}")
        
        min_bounds = workspace_data['min_bounds']
        max_bounds = workspace_data['max_bounds']
        print(f"工作空间边界:")
        print(f"  X: {min_bounds[0]*1000:.1f} ~ {max_bounds[0]*1000:.1f} mm")
        print(f"  Y: {min_bounds[1]*1000:.1f} ~ {max_bounds[1]*1000:.1f} mm")
        print(f"  Z: {min_bounds[2]*1000:.1f} ~ {max_bounds[2]*1000:.1f} mm")
        
        volume = workspace_data['workspace_volume']
        print(f"工作空间体积: {volume*1e9:.1f} cm³")
    else:
        print("工作空间分析失败")


def demo_path_planning():
    """演示路径规划"""
    print("\n=== 路径规划演示 ===")
    
    planner = get_advanced_planner()
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用")
        return
    
    # 定义起始和目标位姿
    start_pose = Pose6D(x=0.2, y=0.1, z=0.3, roll=0.0, pitch=0.0, yaw=0.0)
    goal_pose = Pose6D(x=0.3, y=0.2, z=0.4, roll=0.1, pitch=0.0, yaw=0.1)
    
    print(f"起始位姿: ({start_pose.x*1000:.1f}, {start_pose.y*1000:.1f}, {start_pose.z*1000:.1f}) mm")
    print(f"目标位姿: ({goal_pose.x*1000:.1f}, {goal_pose.y*1000:.1f}, {goal_pose.z*1000:.1f}) mm")
    
    # 添加障碍物
    obstacle = Obstacle(
        center=[0.25, 0.15, 0.35],
        size=[0.05, 0.05, 0.05],
        type="box"
    )
    planner.set_obstacles([obstacle])
    print(f"添加障碍物: {obstacle.type} at {obstacle.center}")
    
    # 路径规划
    print("开始路径规划...")
    start_time = time.time()
    
    planning_result = planner.plan_cartesian_path(
        start_pose,
        goal_pose,
        algorithm=PlanningAlgorithm.RRT
    )
    
    planning_time = time.time() - start_time
    
    if planning_result.success:
        print(f"路径规划成功!")
        print(f"规划时间: {planning_time:.3f} 秒")
        print(f"路径长度: {len(planning_result.path)} 个配置点")
        print(f"路径代价: {planning_result.cost:.6f}")
        print(f"迭代次数: {planning_result.iterations}")
        
        # 路径优化
        print("开始路径优化...")
        optimized_path = planner.optimize_path(planning_result.path)
        print(f"优化后路径长度: {len(optimized_path)} 个配置点")
        
        # 转换为轨迹
        trajectory = planner.path_to_trajectory(optimized_path, total_duration=3.0)
        if trajectory:
            print(f"轨迹生成成功: {len(trajectory.points)} 个轨迹点")
        else:
            print("轨迹生成失败")
    else:
        print(f"路径规划失败: {planning_result.error_message}")


def demo_real_time_control():
    """演示实时控制"""
    print("\n=== 实时控制演示 ===")
    
    controller = get_motion_controller()
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用")
        return
    
    print("注意: 这是一个模拟演示，实际使用需要连接硬件")
    
    # 模拟当前位置
    current_positions = [1500] * 10  # 中位
    controller.set_current_positions(current_positions)
    
    # 获取当前位姿
    current_pose = controller.get_current_pose()
    if current_pose:
        print(f"当前位姿: ({current_pose.x*1000:.1f}, {current_pose.y*1000:.1f}, {current_pose.z*1000:.1f}) mm")
        
        # 计算状态指标
        manipulability = controller.get_manipulability()
        is_singular = controller.check_singularity()
        
        print(f"可操作性指标: {manipulability:.6f}")
        print(f"奇异点状态: {'接近奇异点' if is_singular else '正常'}")
        
        # 模拟笛卡尔空间运动
        target_pose = Pose6D(
            x=current_pose.x + 0.05,  # 向前移动50mm
            y=current_pose.y,
            z=current_pose.z + 0.02,  # 向上移动20mm
            roll=current_pose.roll,
            pitch=current_pose.pitch,
            yaw=current_pose.yaw
        )
        
        print(f"目标位姿: ({target_pose.x*1000:.1f}, {target_pose.y*1000:.1f}, {target_pose.z*1000:.1f}) mm")
        
        # 逆运动学求解
        ik_result = solver.inverse_kinematics(target_pose)
        if ik_result.success:
            print("逆运动学求解成功，可以执行运动")
            print(f"目标关节角度: {[f'{np.rad2deg(a):.1f}°' for a in ik_result.joint_angles]}")
        else:
            print(f"逆运动学求解失败: {ik_result.error_message}")
    else:
        print("无法获取当前位姿")


def demo_jacobian_analysis():
    """演示雅可比矩阵分析"""
    print("\n=== 雅可比矩阵分析演示 ===")
    
    solver = get_kinematics_solver()
    
    if not solver.is_enabled():
        print("运动学求解器不可用")
        return
    
    # 测试配置
    joint_angles = [0.1, 0.2, 0.0, -0.1, 0.3, 0.0, 0.1, -0.2, 0.0, 0.1]
    
    print(f"关节配置: {[f'{np.rad2deg(a):.1f}°' for a in joint_angles]}")
    
    # 计算雅可比矩阵
    jacobian = solver.jacobian(joint_angles)
    
    if jacobian is not None:
        print(f"雅可比矩阵形状: {jacobian.shape}")
        print("雅可比矩阵 (前3行为线速度，后3行为角速度):")
        print(jacobian)
        
        # 分析雅可比矩阵性质
        # 计算条件数
        try:
            condition_number = np.linalg.cond(jacobian)
            print(f"条件数: {condition_number:.2e}")
            
            if condition_number > 1e6:
                print("警告: 条件数很大，接近奇异点")
            elif condition_number > 1e3:
                print("注意: 条件数较大，可能影响控制精度")
            else:
                print("条件数正常")
        except:
            print("无法计算条件数")
        
        # 计算奇异值
        try:
            U, s, Vt = np.linalg.svd(jacobian)
            print(f"奇异值: {s}")
            print(f"最小奇异值: {s[-1]:.6f}")
            print(f"最大奇异值: {s[0]:.6f}")
            
            # 可操作性椭球
            manipulability = np.sqrt(np.linalg.det(jacobian @ jacobian.T))
            print(f"可操作性 (det(JJ^T)^0.5): {manipulability:.6f}")
        except:
            print("奇异值分解失败")
    else:
        print("雅可比矩阵计算失败")


def main():
    """主函数"""
    print("EvoBot运动学求解器演示")
    print("=" * 50)
    
    try:
        # 检查依赖
        solver = get_kinematics_solver()
        if not solver.is_enabled():
            print("错误: 运动学求解器不可用")
            print("请安装依赖: pip install roboticstoolbox-python spatialmath-python")
            return
        
        print("运动学求解器可用，开始演示...")
        
        # 运行各个演示
        demo_forward_kinematics()
        demo_inverse_kinematics()
        demo_jacobian_analysis()
        demo_workspace_analysis()
        demo_path_planning()
        demo_real_time_control()
        
        print("\n演示完成!")
        
    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()