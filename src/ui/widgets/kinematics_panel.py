"""
运动学控制面板

功能：
- 笛卡尔空间位置控制
- 正逆运动学求解
- 工作空间可视化
- 奇异点检测
- 可操作性显示
"""

import sys
from typing import List, Optional, Dict, Any
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QPushButton, QGroupBox,
    QProgressBar, QTextEdit, QTabWidget, QCheckBox,
    QSlider, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

import pyqtgraph as pg
import pyqtgraph.opengl as gl

from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics
from core.motion_controller import get_motion_controller
from core.kinematics_solver import get_kinematics_solver, Pose6D
from core.advanced_planner import get_advanced_planner, Obstacle, PlanningAlgorithm

logger = get_logger(__name__)


class Pose6DWidget(QWidget):
    """6自由度位姿控制组件"""
    
    pose_changed = pyqtSignal(object)  # Pose6D
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI"""
        layout = QGridLayout(self)
        
        # 位置控制
        layout.addWidget(QLabel("X (mm):"), 0, 0)
        self.x_spinbox = QDoubleSpinBox()
        self.x_spinbox.setRange(-1000, 1000)
        self.x_spinbox.setDecimals(1)
        self.x_spinbox.setSuffix(" mm")
        layout.addWidget(self.x_spinbox, 0, 1)
        
        layout.addWidget(QLabel("Y (mm):"), 1, 0)
        self.y_spinbox = QDoubleSpinBox()
        self.y_spinbox.setRange(-1000, 1000)
        self.y_spinbox.setDecimals(1)
        self.y_spinbox.setSuffix(" mm")
        layout.addWidget(self.y_spinbox, 1, 1)
        
        layout.addWidget(QLabel("Z (mm):"), 2, 0)
        self.z_spinbox = QDoubleSpinBox()
        self.z_spinbox.setRange(-1000, 1000)
        self.z_spinbox.setDecimals(1)
        self.z_spinbox.setSuffix(" mm")
        layout.addWidget(self.z_spinbox, 2, 1)
        
        # 姿态控制
        layout.addWidget(QLabel("Roll (°):"), 0, 2)
        self.roll_spinbox = QDoubleSpinBox()
        self.roll_spinbox.setRange(-180, 180)
        self.roll_spinbox.setDecimals(1)
        self.roll_spinbox.setSuffix("°")
        layout.addWidget(self.roll_spinbox, 0, 3)
        
        layout.addWidget(QLabel("Pitch (°):"), 1, 2)
        self.pitch_spinbox = QDoubleSpinBox()
        self.pitch_spinbox.setRange(-180, 180)
        self.pitch_spinbox.setDecimals(1)
        self.pitch_spinbox.setSuffix("°")
        layout.addWidget(self.pitch_spinbox, 1, 3)
        
        layout.addWidget(QLabel("Yaw (°):"), 2, 2)
        self.yaw_spinbox = QDoubleSpinBox()
        self.yaw_spinbox.setRange(-180, 180)
        self.yaw_spinbox.setDecimals(1)
        self.yaw_spinbox.setSuffix("°")
        layout.addWidget(self.yaw_spinbox, 2, 3)
    
    def connect_signals(self):
        """连接信号"""
        self.x_spinbox.valueChanged.connect(self.on_pose_changed)
        self.y_spinbox.valueChanged.connect(self.on_pose_changed)
        self.z_spinbox.valueChanged.connect(self.on_pose_changed)
        self.roll_spinbox.valueChanged.connect(self.on_pose_changed)
        self.pitch_spinbox.valueChanged.connect(self.on_pose_changed)
        self.yaw_spinbox.valueChanged.connect(self.on_pose_changed)
    
    def on_pose_changed(self):
        """位姿改变回调"""
        pose = self.get_pose()
        self.pose_changed.emit(pose)
    
    def get_pose(self) -> Pose6D:
        """获取当前位姿"""
        return Pose6D(
            x=self.x_spinbox.value() / 1000.0,  # 转换为米
            y=self.y_spinbox.value() / 1000.0,
            z=self.z_spinbox.value() / 1000.0,
            roll=np.deg2rad(self.roll_spinbox.value()),
            pitch=np.deg2rad(self.pitch_spinbox.value()),
            yaw=np.deg2rad(self.yaw_spinbox.value())
        )
    
    def set_pose(self, pose: Pose6D):
        """设置位姿"""
        # 暂时断开信号避免循环触发
        self.x_spinbox.blockSignals(True)
        self.y_spinbox.blockSignals(True)
        self.z_spinbox.blockSignals(True)
        self.roll_spinbox.blockSignals(True)
        self.pitch_spinbox.blockSignals(True)
        self.yaw_spinbox.blockSignals(True)
        
        self.x_spinbox.setValue(pose.x * 1000)  # 转换为毫米
        self.y_spinbox.setValue(pose.y * 1000)
        self.z_spinbox.setValue(pose.z * 1000)
        self.roll_spinbox.setValue(np.rad2deg(pose.roll))
        self.pitch_spinbox.setValue(np.rad2deg(pose.pitch))
        self.yaw_spinbox.setValue(np.rad2deg(pose.yaw))
        
        # 重新连接信号
        self.x_spinbox.blockSignals(False)
        self.y_spinbox.blockSignals(False)
        self.z_spinbox.blockSignals(False)
        self.roll_spinbox.blockSignals(False)
        self.pitch_spinbox.blockSignals(False)
        self.yaw_spinbox.blockSignals(False)


class WorkspaceVisualizationWidget(QWidget):
    """工作空间可视化组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.workspace_points = []
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 3D可视化
        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.setMinimumSize(400, 300)
        layout.addWidget(self.gl_widget)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.analyze_button = QPushButton("分析工作空间")
        self.analyze_button.clicked.connect(self.analyze_workspace)
        button_layout.addWidget(self.analyze_button)
        
        self.clear_button = QPushButton("清除")
        self.clear_button.clicked.connect(self.clear_workspace)
        button_layout.addWidget(self.clear_button)
        
        layout.addLayout(button_layout)
        
        # 设置3D场景
        self.setup_3d_scene()
    
    def setup_3d_scene(self):
        """设置3D场景"""
        # 添加坐标轴
        axis = gl.GLAxisItem()
        axis.setSize(0.2, 0.2, 0.2)
        self.gl_widget.addItem(axis)
        
        # 添加网格
        grid = gl.GLGridItem()
        grid.scale(0.1, 0.1, 0.1)
        self.gl_widget.addItem(grid)
        
        # 设置相机
        self.gl_widget.setCameraPosition(distance=1.0)
    
    def analyze_workspace(self):
        """分析工作空间"""
        try:
            kinematics_solver = get_kinematics_solver()
            if not kinematics_solver.is_enabled():
                logger.warning("运动学求解器不可用")
                return
            
            # 分析工作空间
            workspace_data = kinematics_solver.workspace_analysis(num_samples=1000)
            
            if not workspace_data:
                logger.warning("工作空间分析失败")
                return
            
            # 获取工作空间点
            self.workspace_points = np.array(workspace_data['workspace_points'])
            
            # 清除旧的点云
            self.clear_workspace()
            
            # 添加点云
            scatter = gl.GLScatterPlotItem(
                pos=self.workspace_points,
                color=(1, 0, 0, 0.3),
                size=2
            )
            self.gl_widget.addItem(scatter)
            
            logger.info(f"工作空间分析完成: {len(self.workspace_points)}个点")
            
        except Exception as e:
            logger.error(f"工作空间分析失败: {e}")
    
    def clear_workspace(self):
        """清除工作空间显示"""
        # 移除所有散点图
        items_to_remove = []
        for item in self.gl_widget.items:
            if isinstance(item, gl.GLScatterPlotItem):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.gl_widget.removeItem(item)


class KinematicsPanel(QWidget):
    """运动学控制面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.motion_controller = get_motion_controller()
        self.kinematics_solver = get_kinematics_solver()
        self.advanced_planner = get_advanced_planner()
        self.message_bus = get_message_bus()
        
        self.setup_ui()
        self.connect_signals()
        self.setup_timer()
        
        logger.info("运动学控制面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 位姿控制标签页
        self.setup_pose_control_tab()
        
        # 工作空间标签页
        self.setup_workspace_tab()
        
        # 路径规划标签页
        self.setup_path_planning_tab()
        
        # 状态显示
        self.setup_status_display()
        layout.addWidget(self.status_group)
    
    def setup_pose_control_tab(self):
        """设置位姿控制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 当前位姿显示
        current_group = QGroupBox("当前位姿")
        current_layout = QVBoxLayout(current_group)
        
        self.current_pose_widget = Pose6DWidget()
        self.current_pose_widget.setEnabled(False)  # 只读
        current_layout.addWidget(self.current_pose_widget)
        
        layout.addWidget(current_group)
        
        # 目标位姿设置
        target_group = QGroupBox("目标位姿")
        target_layout = QVBoxLayout(target_group)
        
        self.target_pose_widget = Pose6DWidget()
        target_layout.addWidget(self.target_pose_widget)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.move_to_pose_button = QPushButton("移动到位姿")
        self.move_to_pose_button.clicked.connect(self.move_to_pose)
        button_layout.addWidget(self.move_to_pose_button)
        
        self.get_current_pose_button = QPushButton("获取当前位姿")
        self.get_current_pose_button.clicked.connect(self.get_current_pose)
        button_layout.addWidget(self.get_current_pose_button)
        
        target_layout.addLayout(button_layout)
        layout.addWidget(target_group)
        
        # 运动学求解
        ik_group = QGroupBox("运动学求解")
        ik_layout = QVBoxLayout(ik_group)
        
        solve_layout = QHBoxLayout()
        
        self.solve_ik_button = QPushButton("逆运动学求解")
        self.solve_ik_button.clicked.connect(self.solve_inverse_kinematics)
        solve_layout.addWidget(self.solve_ik_button)
        
        self.solve_fk_button = QPushButton("正运动学求解")
        self.solve_fk_button.clicked.connect(self.solve_forward_kinematics)
        solve_layout.addWidget(self.solve_fk_button)
        
        ik_layout.addLayout(solve_layout)
        
        # 求解结果显示
        self.ik_result_text = QTextEdit()
        self.ik_result_text.setMaximumHeight(100)
        self.ik_result_text.setReadOnly(True)
        ik_layout.addWidget(self.ik_result_text)
        
        layout.addWidget(ik_group)
        
        self.tab_widget.addTab(tab, "位姿控制")
    
    def setup_workspace_tab(self):
        """设置工作空间标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 工作空间可视化
        self.workspace_widget = WorkspaceVisualizationWidget()
        layout.addWidget(self.workspace_widget)
        
        self.tab_widget.addTab(tab, "工作空间")
    
    def setup_path_planning_tab(self):
        """设置路径规划标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 规划算法选择
        algorithm_group = QGroupBox("规划算法")
        algorithm_layout = QHBoxLayout(algorithm_group)
        
        algorithm_layout.addWidget(QLabel("算法:"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["RRT", "RRT*", "A*"])
        algorithm_layout.addWidget(self.algorithm_combo)
        
        layout.addWidget(algorithm_group)
        
        # 障碍物设置
        obstacle_group = QGroupBox("障碍物")
        obstacle_layout = QVBoxLayout(obstacle_group)
        
        obstacle_button_layout = QHBoxLayout()
        
        self.add_obstacle_button = QPushButton("添加障碍物")
        self.add_obstacle_button.clicked.connect(self.add_obstacle)
        obstacle_button_layout.addWidget(self.add_obstacle_button)
        
        self.clear_obstacles_button = QPushButton("清除障碍物")
        self.clear_obstacles_button.clicked.connect(self.clear_obstacles)
        obstacle_button_layout.addWidget(self.clear_obstacles_button)
        
        obstacle_layout.addLayout(obstacle_button_layout)
        
        self.obstacle_list_text = QTextEdit()
        self.obstacle_list_text.setMaximumHeight(80)
        self.obstacle_list_text.setReadOnly(True)
        obstacle_layout.addWidget(self.obstacle_list_text)
        
        layout.addWidget(obstacle_group)
        
        # 路径规划控制
        planning_group = QGroupBox("路径规划")
        planning_layout = QVBoxLayout(planning_group)
        
        self.plan_path_button = QPushButton("规划路径并执行")
        self.plan_path_button.clicked.connect(self.plan_and_execute_path)
        planning_layout.addWidget(self.plan_path_button)
        
        # 规划结果显示
        self.planning_result_text = QTextEdit()
        self.planning_result_text.setMaximumHeight(100)
        self.planning_result_text.setReadOnly(True)
        planning_layout.addWidget(self.planning_result_text)
        
        layout.addWidget(planning_group)
        
        self.tab_widget.addTab(tab, "路径规划")
    
    def setup_status_display(self):
        """设置状态显示"""
        self.status_group = QGroupBox("运动学状态")
        layout = QGridLayout(self.status_group)
        
        # 可操作性指标
        layout.addWidget(QLabel("可操作性:"), 0, 0)
        self.manipulability_label = QLabel("0.000")
        layout.addWidget(self.manipulability_label, 0, 1)
        
        self.manipulability_bar = QProgressBar()
        self.manipulability_bar.setRange(0, 100)
        layout.addWidget(self.manipulability_bar, 0, 2)
        
        # 奇异点检测
        layout.addWidget(QLabel("奇异点:"), 1, 0)
        self.singularity_label = QLabel("正常")
        layout.addWidget(self.singularity_label, 1, 1)
        
        # 运动学求解器状态
        layout.addWidget(QLabel("求解器:"), 2, 0)
        self.solver_status_label = QLabel("未知")
        layout.addWidget(self.solver_status_label, 2, 1)
    
    def connect_signals(self):
        """连接信号"""
        # 订阅机器人状态更新
        self.message_bus.subscribe(Topics.ROBOT_STATE, self.on_robot_state_update)
    
    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(200)  # 5Hz更新
    
    def move_to_pose(self):
        """移动到目标位姿"""
        try:
            target_pose = self.target_pose_widget.get_pose()
            
            success = self.motion_controller.move_to_pose(target_pose)
            
            if success:
                self.ik_result_text.append(f"开始移动到位姿: {target_pose}")
            else:
                self.ik_result_text.append("移动失败")
                
        except Exception as e:
            logger.error(f"移动到位姿失败: {e}")
            self.ik_result_text.append(f"错误: {e}")
    
    def get_current_pose(self):
        """获取当前位姿"""
        try:
            current_pose = self.motion_controller.get_current_pose()
            
            if current_pose:
                self.current_pose_widget.set_pose(current_pose)
                self.target_pose_widget.set_pose(current_pose)  # 同时设置为目标位姿
                self.ik_result_text.append(f"当前位姿: {current_pose}")
            else:
                self.ik_result_text.append("无法获取当前位姿")
                
        except Exception as e:
            logger.error(f"获取当前位姿失败: {e}")
            self.ik_result_text.append(f"错误: {e}")
    
    def solve_inverse_kinematics(self):
        """求解逆运动学"""
        try:
            target_pose = self.target_pose_widget.get_pose()
            
            ik_result = self.kinematics_solver.inverse_kinematics(target_pose)
            
            if ik_result.success:
                joint_angles_deg = [np.rad2deg(angle) for angle in ik_result.joint_angles]
                self.ik_result_text.append(f"逆运动学求解成功:")
                self.ik_result_text.append(f"关节角度(度): {[f'{angle:.1f}' for angle in joint_angles_deg]}")
                self.ik_result_text.append(f"计算时间: {ik_result.computation_time*1000:.1f}ms")
            else:
                self.ik_result_text.append(f"逆运动学求解失败: {ik_result.error_message}")
                
        except Exception as e:
            logger.error(f"逆运动学求解失败: {e}")
            self.ik_result_text.append(f"错误: {e}")
    
    def solve_forward_kinematics(self):
        """求解正运动学"""
        try:
            # 获取当前关节角度
            current_positions = self.motion_controller.get_current_positions()
            current_angles = [pos * 2 * 3.14159 / 3000 for pos in current_positions]
            
            fk_result = self.kinematics_solver.forward_kinematics(current_angles)
            
            if fk_result.success:
                pose = fk_result.end_effector_pose
                self.current_pose_widget.set_pose(pose)
                self.ik_result_text.append(f"正运动学求解成功:")
                self.ik_result_text.append(f"位置: ({pose.x*1000:.1f}, {pose.y*1000:.1f}, {pose.z*1000:.1f}) mm")
                self.ik_result_text.append(f"姿态: ({np.rad2deg(pose.roll):.1f}, {np.rad2deg(pose.pitch):.1f}, {np.rad2deg(pose.yaw):.1f})°")
                self.ik_result_text.append(f"计算时间: {fk_result.computation_time*1000:.1f}ms")
            else:
                self.ik_result_text.append(f"正运动学求解失败: {fk_result.error_message}")
                
        except Exception as e:
            logger.error(f"正运动学求解失败: {e}")
            self.ik_result_text.append(f"错误: {e}")
    
    def add_obstacle(self):
        """添加障碍物"""
        # 简单示例：添加一个固定的盒子障碍物
        obstacle = Obstacle(
            center=[0.2, 0.2, 0.2],
            size=[0.1, 0.1, 0.1],
            type="box"
        )
        
        self.advanced_planner.collision_checker.add_obstacle(obstacle)
        self.update_obstacle_list()
        
        self.planning_result_text.append(f"添加障碍物: {obstacle.type} at {obstacle.center}")
    
    def clear_obstacles(self):
        """清除障碍物"""
        self.advanced_planner.collision_checker.remove_all_obstacles()
        self.update_obstacle_list()
        self.planning_result_text.append("已清除所有障碍物")
    
    def update_obstacle_list(self):
        """更新障碍物列表显示"""
        obstacles = self.advanced_planner.collision_checker.obstacles
        text = f"障碍物数量: {len(obstacles)}\n"
        
        for i, obstacle in enumerate(obstacles):
            text += f"{i+1}. {obstacle.type} at {obstacle.center}\n"
        
        self.obstacle_list_text.setPlainText(text)
    
    def plan_and_execute_path(self):
        """规划路径并执行"""
        try:
            target_pose = self.target_pose_widget.get_pose()
            
            # 获取选择的算法
            algorithm_name = self.algorithm_combo.currentText()
            algorithm_map = {
                "RRT": PlanningAlgorithm.RRT,
                "RRT*": PlanningAlgorithm.RRT_STAR,
                "A*": PlanningAlgorithm.A_STAR
            }
            algorithm = algorithm_map.get(algorithm_name, PlanningAlgorithm.RRT)
            
            # 执行路径规划运动
            success = self.motion_controller.move_with_path_planning(
                target_pose, 
                obstacles=None,  # 使用已设置的障碍物
                algorithm=algorithm
            )
            
            if success:
                self.planning_result_text.append(f"路径规划成功，开始执行运动")
            else:
                self.planning_result_text.append("路径规划失败")
                
        except Exception as e:
            logger.error(f"路径规划执行失败: {e}")
            self.planning_result_text.append(f"错误: {e}")
    
    def update_status(self):
        """更新状态显示"""
        try:
            # 更新运动学求解器状态
            if self.kinematics_solver.is_enabled():
                self.solver_status_label.setText("可用")
                self.solver_status_label.setStyleSheet("color: green")
                
                # 更新可操作性
                manipulability = self.motion_controller.get_manipulability()
                self.manipulability_label.setText(f"{manipulability:.3f}")
                self.manipulability_bar.setValue(int(manipulability * 100))
                
                # 更新奇异点状态
                is_singular = self.motion_controller.check_singularity()
                if is_singular:
                    self.singularity_label.setText("奇异点")
                    self.singularity_label.setStyleSheet("color: red")
                else:
                    self.singularity_label.setText("正常")
                    self.singularity_label.setStyleSheet("color: green")
            else:
                self.solver_status_label.setText("不可用")
                self.solver_status_label.setStyleSheet("color: red")
                self.manipulability_label.setText("N/A")
                self.manipulability_bar.setValue(0)
                self.singularity_label.setText("N/A")
                self.singularity_label.setStyleSheet("color: gray")
                
        except Exception as e:
            logger.error(f"更新状态失败: {e}")
    
    def on_robot_state_update(self, data: Dict):
        """机器人状态更新回调"""
        try:
            # 可以在这里添加实时状态更新逻辑
            pass
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = KinematicsPanel()
    panel.show()
    
    sys.exit(app.exec_())