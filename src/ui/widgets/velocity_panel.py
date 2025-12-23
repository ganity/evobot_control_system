"""
速度控制面板

功能：
- 全局速度控制
- 速度预设切换
- 单关节速度设置
- 实时速度曲线显示
- 插值算法选择
"""

import sys
from typing import List, Optional, Dict, Any
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSlider, QDoubleSpinBox,
    QComboBox, QRadioButton, QButtonGroup, QTabWidget,
    QFrame, QSplitter, QCheckBox, QSpinBox, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor

import pyqtgraph as pg

from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.velocity_controller import (
    get_velocity_controller, VelocityPreset, VelocityParameters
)
from core.trajectory_planner import InterpolationType

logger = get_logger(__name__)


class VelocitySliderWidget(QWidget):
    """速度滑块组件"""
    
    value_changed = pyqtSignal(float)
    
    def __init__(self, label: str, min_val: float = 10, max_val: float = 1000, 
                 default_val: float = 500, unit: str = "单位/秒", parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        
        self.setup_ui(label, default_val)
        self.connect_signals()
    
    def setup_ui(self, label: str, default_val: float):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标签
        self.label = QLabel(label)
        self.label.setMinimumWidth(80)
        layout.addWidget(self.label)
        
        # 滑块
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(self.min_val))
        self.slider.setMaximum(int(self.max_val))
        self.slider.setValue(int(default_val))
        layout.addWidget(self.slider)
        
        # 数值输入框
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setMinimum(self.min_val)
        self.spinbox.setMaximum(self.max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setSuffix(f" {self.unit}")
        self.spinbox.setMinimumWidth(120)
        layout.addWidget(self.spinbox)
    
    def connect_signals(self):
        """连接信号"""
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.spinbox.valueChanged.connect(self.on_spinbox_changed)
    
    def on_slider_changed(self, value: int):
        """滑块值改变"""
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(float(value))
        self.spinbox.blockSignals(False)
        self.value_changed.emit(float(value))
    
    def on_spinbox_changed(self, value: float):
        """输入框值改变"""
        self.slider.blockSignals(True)
        self.slider.setValue(int(value))
        self.slider.blockSignals(False)
        self.value_changed.emit(value)
    
    def get_value(self) -> float:
        """获取当前值"""
        return self.spinbox.value()
    
    def set_value(self, value: float):
        """设置值"""
        self.slider.blockSignals(True)
        self.spinbox.blockSignals(True)
        
        self.slider.setValue(int(value))
        self.spinbox.setValue(value)
        
        self.slider.blockSignals(False)
        self.spinbox.blockSignals(False)


class VelocityCurveWidget(QWidget):
    """速度曲线显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # 曲线数据
        self.time_data = np.array([0, 1])
        self.position_data = np.array([0, 100])
        self.velocity_data = np.array([0, 0])
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建图形窗口
        self.graphics_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_widget)
        
        # 位置曲线
        self.position_plot = self.graphics_widget.addPlot(title="位置曲线")
        self.position_plot.setLabel('left', '位置', units='单位')
        self.position_plot.setLabel('bottom', '时间', units='秒')
        self.position_curve = self.position_plot.plot(pen='b', name='位置')
        
        # 换行
        self.graphics_widget.nextRow()
        
        # 速度曲线
        self.velocity_plot = self.graphics_widget.addPlot(title="速度曲线")
        self.velocity_plot.setLabel('left', '速度', units='单位/秒')
        self.velocity_plot.setLabel('bottom', '时间', units='秒')
        self.velocity_curve = self.velocity_plot.plot(pen='r', name='速度')
        
        # 设置图形属性
        self.position_plot.showGrid(x=True, y=True)
        self.velocity_plot.showGrid(x=True, y=True)
        
        # 链接X轴
        self.velocity_plot.setXLink(self.position_plot)
    
    def update_curves(self, time_data: np.ndarray, position_data: np.ndarray, velocity_data: np.ndarray):
        """更新曲线数据"""
        self.time_data = time_data
        self.position_data = position_data
        self.velocity_data = velocity_data
        
        # 更新曲线
        self.position_curve.setData(time_data, position_data)
        self.velocity_curve.setData(time_data, velocity_data)
    
    def clear_curves(self):
        """清空曲线"""
        self.position_curve.clear()
        self.velocity_curve.clear()


class VelocityPanel(QWidget):
    """速度控制面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.velocity_controller = get_velocity_controller()
        self.message_bus = get_message_bus()
        
        self.setup_ui()
        self.connect_signals()
        self.setup_timer()
        
        # 初始化显示
        self.update_display()
        
        logger.info("速度控制面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 全局速度控制标签页
        self.setup_global_control_tab()
        
        # 单关节速度控制标签页
        self.setup_joint_control_tab()
        
        # 速度曲线显示标签页
        self.setup_curve_display_tab()
    
    def setup_global_control_tab(self):
        """设置全局速度控制标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")
        
        # 内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 速度预设组
        preset_group = QGroupBox("速度预设")
        preset_layout = QGridLayout(preset_group)
        
        # 预设按钮
        self.preset_button_group = QButtonGroup()
        self.preset_buttons = {}
        
        presets = [
            (VelocityPreset.VERY_SLOW, "很慢", 0, 0),
            (VelocityPreset.SLOW, "慢", 0, 1),
            (VelocityPreset.MEDIUM, "中", 0, 2),
            (VelocityPreset.FAST, "快", 1, 0),
            (VelocityPreset.VERY_FAST, "很快", 1, 1),
            (VelocityPreset.CUSTOM, "自定义", 1, 2)
        ]
        
        for preset, text, row, col in presets:
            button = QRadioButton(text)
            self.preset_buttons[preset] = button
            self.preset_button_group.addButton(button)
            preset_layout.addWidget(button, row, col)
        
        # 默认选中中速
        self.preset_buttons[VelocityPreset.MEDIUM].setChecked(True)
        
        layout.addWidget(preset_group)
        
        # 全局速度参数组
        params_group = QGroupBox("全局速度参数")
        params_layout = QVBoxLayout(params_group)
        
        # 速度滑块
        self.velocity_slider = VelocitySliderWidget(
            "速度:", 10, 1000, 500, "单位/秒"
        )
        params_layout.addWidget(self.velocity_slider)
        
        # 加速度滑块
        self.acceleration_slider = VelocitySliderWidget(
            "加速度:", 100, 2000, 1000, "单位/秒²"
        )
        params_layout.addWidget(self.acceleration_slider)
        
        # 加加速度滑块
        self.jerk_slider = VelocitySliderWidget(
            "加加速度:", 1000, 10000, 5000, "单位/秒³"
        )
        params_layout.addWidget(self.jerk_slider)
        
        layout.addWidget(params_group)
        
        # 插值算法组
        algorithm_group = QGroupBox("插值算法")
        algorithm_layout = QHBoxLayout(algorithm_group)
        
        algorithm_layout.addWidget(QLabel("算法:"))
        
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "梯形速度曲线", "S曲线", "三次样条", "五次多项式", "线性插值"
        ])
        algorithm_layout.addWidget(self.algorithm_combo)
        
        algorithm_layout.addStretch()
        
        layout.addWidget(algorithm_group)
        
        # 操作按钮组
        button_group = QGroupBox("操作")
        button_layout = QHBoxLayout(button_group)
        
        self.apply_all_button = QPushButton("应用到所有关节")
        self.apply_all_button.setMinimumHeight(35)
        button_layout.addWidget(self.apply_all_button)
        
        self.save_default_button = QPushButton("保存为默认")
        self.save_default_button.setMinimumHeight(35)
        button_layout.addWidget(self.save_default_button)
        
        self.reset_button = QPushButton("重置")
        self.reset_button.setMinimumHeight(35)
        button_layout.addWidget(self.reset_button)
        
        layout.addWidget(button_group)
        
        layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(tab, "全局控制")
    
    def setup_joint_control_tab(self):
        """设置单关节速度控制标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")
        
        # 内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 关节选择
        joint_select_layout = QHBoxLayout()
        joint_select_layout.addWidget(QLabel("选择关节:"))
        
        self.joint_combo = QComboBox()
        joint_names = ["拇指", "食指", "中指", "无名指", "小指", "手腕", "肩部1", "肩部2", "肘部1", "肘部2"]
        for i, name in enumerate(joint_names):
            self.joint_combo.addItem(f"{i}: {name}")
        joint_select_layout.addWidget(self.joint_combo)
        
        joint_select_layout.addStretch()
        layout.addLayout(joint_select_layout)
        
        # 单关节速度参数
        joint_params_group = QGroupBox("关节速度参数")
        joint_params_layout = QVBoxLayout(joint_params_group)
        
        # 关节速度滑块
        self.joint_velocity_slider = VelocitySliderWidget(
            "速度:", 10, 1000, 500, "单位/秒"
        )
        joint_params_layout.addWidget(self.joint_velocity_slider)
        
        # 关节限制显示
        limits_layout = QGridLayout()
        
        limits_layout.addWidget(QLabel("最大速度:"), 0, 0)
        self.max_velocity_label = QLabel("1000 单位/秒")
        limits_layout.addWidget(self.max_velocity_label, 0, 1)
        
        limits_layout.addWidget(QLabel("最大加速度:"), 1, 0)
        self.max_acceleration_label = QLabel("2000 单位/秒²")
        limits_layout.addWidget(self.max_acceleration_label, 1, 1)
        
        limits_layout.addWidget(QLabel("最小速度:"), 2, 0)
        self.min_velocity_label = QLabel("10 单位/秒")
        limits_layout.addWidget(self.min_velocity_label, 2, 1)
        
        joint_params_layout.addLayout(limits_layout)
        
        layout.addWidget(joint_params_group)
        
        # 关节操作按钮
        joint_button_layout = QHBoxLayout()
        
        self.apply_joint_button = QPushButton("应用到当前关节")
        self.apply_joint_button.setMinimumHeight(35)
        joint_button_layout.addWidget(self.apply_joint_button)
        
        self.copy_from_global_button = QPushButton("复制全局设置")
        self.copy_from_global_button.setMinimumHeight(35)
        joint_button_layout.addWidget(self.copy_from_global_button)
        
        layout.addLayout(joint_button_layout)
        
        layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(tab, "单关节控制")
    
    def setup_curve_display_tab(self):
        """设置速度曲线显示标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")
        
        # 内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 曲线参数设置
        params_group = QGroupBox("曲线参数")
        params_layout = QGridLayout(params_group)
        
        params_layout.addWidget(QLabel("起始位置:"), 0, 0)
        self.start_pos_spinbox = QSpinBox()
        self.start_pos_spinbox.setRange(0, 3000)
        self.start_pos_spinbox.setValue(0)
        params_layout.addWidget(self.start_pos_spinbox, 0, 1)
        
        params_layout.addWidget(QLabel("结束位置:"), 0, 2)
        self.end_pos_spinbox = QSpinBox()
        self.end_pos_spinbox.setRange(0, 3000)
        self.end_pos_spinbox.setValue(1500)
        params_layout.addWidget(self.end_pos_spinbox, 0, 3)
        
        params_layout.addWidget(QLabel("运动时间:"), 1, 0)
        self.duration_spinbox = QDoubleSpinBox()
        self.duration_spinbox.setRange(0.1, 10.0)
        self.duration_spinbox.setValue(2.0)
        self.duration_spinbox.setSuffix(" 秒")
        params_layout.addWidget(self.duration_spinbox, 1, 1)
        
        self.generate_curve_button = QPushButton("生成曲线")
        params_layout.addWidget(self.generate_curve_button, 1, 2, 1, 2)
        
        layout.addWidget(params_group)
        
        # 速度曲线显示
        self.curve_widget = VelocityCurveWidget()
        layout.addWidget(self.curve_widget)
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(tab, "速度曲线")
    
    def connect_signals(self):
        """连接信号"""
        # 预设按钮
        self.preset_button_group.buttonClicked.connect(self.on_preset_changed)
        
        # 速度参数滑块
        self.velocity_slider.value_changed.connect(self.on_velocity_changed)
        self.acceleration_slider.value_changed.connect(self.on_acceleration_changed)
        self.jerk_slider.value_changed.connect(self.on_jerk_changed)
        
        # 插值算法
        self.algorithm_combo.currentTextChanged.connect(self.on_algorithm_changed)
        
        # 操作按钮
        self.apply_all_button.clicked.connect(self.apply_to_all_joints)
        self.save_default_button.clicked.connect(self.save_as_default)
        self.reset_button.clicked.connect(self.reset_parameters)
        
        # 单关节控制
        self.joint_combo.currentIndexChanged.connect(self.on_joint_selected)
        self.joint_velocity_slider.value_changed.connect(self.on_joint_velocity_changed)
        self.apply_joint_button.clicked.connect(self.apply_to_current_joint)
        self.copy_from_global_button.clicked.connect(self.copy_from_global)
        
        # 曲线生成
        self.generate_curve_button.clicked.connect(self.generate_velocity_curve)
        
        # 订阅速度变更事件
        self.message_bus.subscribe(Topics.VELOCITY_CHANGED, self.on_velocity_updated)
        self.message_bus.subscribe(Topics.VELOCITY_PRESET_APPLIED, self.on_preset_applied)
    
    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_joint_limits_display)
        self.update_timer.start(1000)  # 1秒更新一次
    
    def on_preset_changed(self, button):
        """预设改变"""
        for preset, preset_button in self.preset_buttons.items():
            if preset_button == button:
                success = self.velocity_controller.apply_preset(preset)
                if success:
                    self.update_display()
                break
    
    def on_velocity_changed(self, value: float):
        """速度改变"""
        self.update_custom_parameters()
    
    def on_acceleration_changed(self, value: float):
        """加速度改变"""
        self.update_custom_parameters()
    
    def on_jerk_changed(self, value: float):
        """加加速度改变"""
        self.update_custom_parameters()
    
    def on_algorithm_changed(self, text: str):
        """插值算法改变"""
        self.update_custom_parameters()
    
    def update_custom_parameters(self):
        """更新自定义参数"""
        # 获取插值类型
        algorithm_map = {
            "梯形速度曲线": InterpolationType.TRAPEZOIDAL,
            "S曲线": InterpolationType.S_CURVE,
            "三次样条": InterpolationType.CUBIC_SPLINE,
            "五次多项式": InterpolationType.QUINTIC,
            "线性插值": InterpolationType.LINEAR
        }
        
        interpolation = algorithm_map.get(self.algorithm_combo.currentText(), InterpolationType.TRAPEZOIDAL)
        
        # 创建新参数
        parameters = VelocityParameters(
            velocity=self.velocity_slider.get_value(),
            acceleration=self.acceleration_slider.get_value(),
            jerk=self.jerk_slider.get_value(),
            interpolation=interpolation,
            description="自定义速度参数"
        )
        
        # 应用参数
        success = self.velocity_controller.set_velocity_parameters(parameters)
        if success:
            # 选中自定义预设
            self.preset_buttons[VelocityPreset.CUSTOM].setChecked(True)
    
    def apply_to_all_joints(self):
        """应用到所有关节"""
        # 这里可以实现应用到所有关节的逻辑
        logger.info("应用速度参数到所有关节")
    
    def save_as_default(self):
        """保存为默认"""
        success = self.velocity_controller.save_velocity_config()
        if success:
            logger.info("速度配置已保存为默认")
    
    def reset_parameters(self):
        """重置参数"""
        self.velocity_controller.apply_preset(VelocityPreset.MEDIUM)
        self.update_display()
    
    def on_joint_selected(self, index: int):
        """关节选择改变"""
        self.update_joint_limits_display()
    
    def on_joint_velocity_changed(self, value: float):
        """单关节速度改变"""
        pass  # 可以实现单关节速度设置逻辑
    
    def apply_to_current_joint(self):
        """应用到当前关节"""
        joint_id = self.joint_combo.currentIndex()
        velocity = self.joint_velocity_slider.get_value()
        
        success = self.velocity_controller.set_joint_velocity(joint_id, velocity)
        if success:
            logger.info(f"关节{joint_id}速度已设置为{velocity}")
    
    def copy_from_global(self):
        """复制全局设置"""
        params = self.velocity_controller.get_current_parameters()
        self.joint_velocity_slider.set_value(params.velocity)
    
    def generate_velocity_curve(self):
        """生成速度曲线"""
        start_pos = self.start_pos_spinbox.value()
        end_pos = self.end_pos_spinbox.value()
        duration = self.duration_spinbox.value()
        
        # 生成曲线数据
        t, pos, vel = self.velocity_controller.generate_velocity_profile(
            start_pos, end_pos, duration
        )
        
        # 更新显示
        self.curve_widget.update_curves(t, pos, vel)
    
    def update_display(self):
        """更新显示"""
        try:
            # 获取当前参数
            params = self.velocity_controller.get_current_parameters()
            current_preset = self.velocity_controller.get_current_preset()
            
            # 更新预设选择
            if current_preset in self.preset_buttons:
                self.preset_buttons[current_preset].setChecked(True)
            
            # 更新参数滑块
            self.velocity_slider.set_value(params.velocity)
            self.acceleration_slider.set_value(params.acceleration)
            self.jerk_slider.set_value(params.jerk)
            
            # 更新插值算法
            algorithm_map = {
                InterpolationType.TRAPEZOIDAL: "梯形速度曲线",
                InterpolationType.S_CURVE: "S曲线",
                InterpolationType.CUBIC_SPLINE: "三次样条",
                InterpolationType.QUINTIC: "五次多项式",
                InterpolationType.LINEAR: "线性插值"
            }
            
            algorithm_text = algorithm_map.get(params.interpolation, "梯形速度曲线")
            self.algorithm_combo.setCurrentText(algorithm_text)
            
        except Exception as e:
            logger.error(f"更新速度显示失败: {e}")
    
    def update_joint_limits_display(self):
        """更新关节限制显示"""
        try:
            joint_id = self.joint_combo.currentIndex()
            limits = self.velocity_controller.get_joint_limits(joint_id)
            
            if limits:
                self.max_velocity_label.setText(f"{limits.max_velocity:.0f} 单位/秒")
                self.max_acceleration_label.setText(f"{limits.max_acceleration:.0f} 单位/秒²")
                self.min_velocity_label.setText(f"{limits.min_velocity:.0f} 单位/秒")
                
                # 更新滑块范围
                self.joint_velocity_slider.slider.setMaximum(int(limits.max_velocity))
                self.joint_velocity_slider.slider.setMinimum(int(limits.min_velocity))
                self.joint_velocity_slider.spinbox.setMaximum(limits.max_velocity)
                self.joint_velocity_slider.spinbox.setMinimum(limits.min_velocity)
            
        except Exception as e:
            logger.error(f"更新关节限制显示失败: {e}")
    
    def on_velocity_updated(self, message):
        """速度更新事件回调"""
        self.update_display()
    
    def on_preset_applied(self, message):
        """预设应用事件回调"""
        self.update_display()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = VelocityPanel()
    panel.show()
    
    sys.exit(app.exec_())