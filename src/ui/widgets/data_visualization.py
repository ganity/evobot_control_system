"""
数据可视化组件

功能：
- 实时曲线显示
- 多关节数据对比
- 历史数据回放
- 数据导出功能
"""

import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QCheckBox, QGroupBox, QGridLayout, QSpinBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import numpy as np
from collections import deque
from typing import Dict, List, Optional
import time

from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics

logger = get_logger(__name__)


class RealTimePlotWidget(QWidget):
    """实时绘图控件"""
    
    def __init__(self, title: str = "实时数据", parent=None):
        super().__init__(parent)
        self.title = title
        
        # 数据缓冲区
        self.max_points = 300
        self.time_data = deque(maxlen=self.max_points)
        self.joint_data = {i: deque(maxlen=self.max_points) for i in range(10)}
        
        # 绘图曲线
        self.curves = {}
        # 优化后的高对比度颜色
        self.colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFACA4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
        ]
        
        self.setup_ui()
        
        # 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(50)  # 20Hz更新
        
        # 订阅机器人状态
        self.message_bus = get_message_bus()
        self.message_bus.subscribe(Topics.ROBOT_STATE, self.on_robot_state_update)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #CCCCCC;")
        layout.addWidget(title_label)
        
        # 控制面板
        control_group = QGroupBox("显示选项")
        control_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3E3E42;
                border-radius: 6px;
                padding-top: 10px;
                margin-top: 10px;
                color: #858585;
            }
            QCheckBox { color: #CCCCCC; }
            QLabel { color: #CCCCCC; }
        """)
        control_layout = QGridLayout(control_group)
        
        # 关节选择
        self.joint_checkboxes = {}
        for i in range(10):
            joint_names = ["拇指", "食指", "中指", "无名指", "小指", "手腕", "S1", "S2", "E1", "E2"]
            checkbox = QCheckBox(f"{joint_names[i]}")
            checkbox.setChecked(i < 3)  # 默认显示前3个关节
            checkbox.stateChanged.connect(self.on_joint_visibility_changed)
            self.joint_checkboxes[i] = checkbox
            
            row = i // 5
            col = i % 5
            control_layout.addWidget(checkbox, row, col)
        
        # 数据类型选择
        control_layout.addWidget(QLabel("数据类型:"), 2, 0)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["位置", "速度", "电流"])
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        control_layout.addWidget(self.data_type_combo, 2, 1)
        
        # 时间范围
        control_layout.addWidget(QLabel("时间范围:"), 2, 2)
        self.time_range_spinbox = QSpinBox()
        self.time_range_spinbox.setRange(10, 600)
        self.time_range_spinbox.setValue(15)
        self.time_range_spinbox.setSuffix(" s")
        self.time_range_spinbox.setStyleSheet("background-color: #1E1E1E; color: #CCCCCC;")
        self.time_range_spinbox.valueChanged.connect(self.on_time_range_changed)
        control_layout.addWidget(self.time_range_spinbox, 2, 3)
        
        # 清除按钮
        clear_button = QPushButton("清除")
        clear_button.setStyleSheet("background-color: #3E3E42; border: none; padding: 4px;")
        clear_button.clicked.connect(self.clear_data)
        control_layout.addWidget(clear_button, 2, 4)
        
        layout.addWidget(control_group)
        
        # 绘图区域 - 深色模式配置
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1E1E1E')
        
        # 设置坐标轴颜色
        styles = {'color': '#999', 'font-size': '12px'}
        self.plot_widget.setLabel('left', '数值', **styles)
        self.plot_widget.setLabel('bottom', '时间 (s)', **styles)
        self.plot_widget.getAxis('left').setPen('#555')
        self.plot_widget.getAxis('bottom').setPen('#555')
        self.plot_widget.getAxis('left').setTextPen('#999')
        self.plot_widget.getAxis('bottom').setTextPen('#999')
        
        # 网格
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        
        self.plot_widget.addLegend(offset=(10, 10))
        
        layout.addWidget(self.plot_widget)
        
        # 初始化曲线
        self.update_curves()
    
    def on_joint_visibility_changed(self):
        """关节可见性改变"""
        self.update_curves()
    
    def on_data_type_changed(self, data_type: str):
        """数据类型改变"""
        type_map = {
            "位置": "单位",
            "速度": "单位/秒", 
            "电流": "mA"
        }
        
        self.plot_widget.setLabel('left', data_type, units=type_map.get(data_type, ''))
        self.clear_data()
    
    def on_time_range_changed(self, seconds: int):
        """时间范围改变"""
        points = int(seconds * 20)  # 20Hz更新频率
        self.max_points = points
        
        # 调整缓冲区大小
        self.time_data = deque(list(self.time_data)[-points:], maxlen=points)
        for i in range(10):
            self.joint_data[i] = deque(list(self.joint_data[i])[-points:], maxlen=points)
    
    def update_curves(self):
        """更新曲线"""
        self.plot_widget.clear()
        self.curves.clear()
        
        joint_names = ["拇指", "食指", "中指", "无名指", "小指", "手腕", "J6", "J7", "J8", "J9"]
        
        for i in range(10):
            if self.joint_checkboxes[i].isChecked():
                pen = pg.mkPen(color=self.colors[i], width=2)
                curve = self.plot_widget.plot(
                    pen=pen, 
                    name=f"{joint_names[i]}"
                )
                self.curves[i] = curve
    
    def clear_data(self):
        """清除数据"""
        self.time_data.clear()
        for i in range(10):
            self.joint_data[i].clear()
    
    def on_robot_state_update(self, message):
        """机器人状态更新"""
        try:
            data = message.data
            
            # 处理不同的数据格式
            joints = []
            
            if isinstance(data, dict):
                if 'joints' in data:
                    # 直接包含joints字段的格式
                    joints = data.get('joints', [])
                elif 'data' in data and hasattr(data['data'], 'joints'):
                    # 包装格式
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
                    # 尝试直接访问joints属性
                    if hasattr(data, 'joints'):
                        joints = [
                            {
                                'id': joint.joint_id,
                                'position': joint.position,
                                'velocity': joint.velocity,
                                'current': joint.current
                            } for joint in data.joints
                        ]
            elif hasattr(data, 'joints'):
                # 直接是RobotStatus对象
                joints = [
                    {
                        'id': joint.joint_id,
                        'position': joint.position,
                        'velocity': joint.velocity,
                        'current': joint.current
                    } for joint in data.joints
                ]
            
            if not joints:
                return
            
            current_time = time.time()
            self.time_data.append(current_time)
            
            # 根据数据类型获取相应数据
            data_type = self.data_type_combo.currentText()
            
            for joint_data in joints:
                joint_id = joint_data.get('id')
                if 0 <= joint_id < 10:
                    if data_type == "位置":
                        value = joint_data.get('position', 0)
                    elif data_type == "速度":
                        value = joint_data.get('velocity', 0.0)
                    elif data_type == "电流":
                        value = joint_data.get('current', 0)
                    else:
                        value = 0
                    
                    self.joint_data[joint_id].append(value)
            
            # 填充缺失的关节数据
            for i in range(10):
                if len(self.joint_data[i]) < len(self.time_data):
                    self.joint_data[i].append(0)
                    
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")
    
    def update_plot(self):
        """更新绘图"""
        if not self.time_data:
            return
        
        try:
            # 转换为相对时间
            base_time = self.time_data[0] if self.time_data else 0
            time_array = np.array([t - base_time for t in self.time_data])
            
            # 更新每条曲线
            for joint_id, curve in self.curves.items():
                if len(self.joint_data[joint_id]) > 0:
                    data_array = np.array(list(self.joint_data[joint_id]))
                    curve.setData(time_array, data_array)
                    
        except Exception as e:
            logger.error(f"更新绘图失败: {e}")


class DataVisualizationPanel(QWidget):
    """数据可视化面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        from PyQt5.QtWidgets import QScrollArea, QFrame
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # 内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 实时数据绘图
        self.realtime_plot = RealTimePlotWidget("📈 实时关节数据监控")
        layout.addWidget(self.realtime_plot)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_button = QPushButton("导出 CSV")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #CCCCCC;
                border: 1px solid #3E3E42;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3E3E42; }
        """)
        export_button.clicked.connect(self.export_data)
        button_layout.addWidget(export_button)
        
        screenshot_button = QPushButton("保存截图")
        screenshot_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0098FF; }
        """)
        screenshot_button.clicked.connect(self.save_screenshot)
        button_layout.addWidget(screenshot_button)
        
        layout.addLayout(button_layout)
        
        # 设置滚动内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def export_data(self):
        """导出数据"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import csv
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出数据", "robot_data.csv", "CSV Files (*.csv)"
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # 写入表头
                    header = ['时间'] + [f'关节{i}' for i in range(10)]
                    writer.writerow(header)
                    
                    # 写入数据
                    time_data = list(self.realtime_plot.time_data)
                    for i, t in enumerate(time_data):
                        row = [t]
                        for j in range(10):
                            if i < len(self.realtime_plot.joint_data[j]):
                                row.append(self.realtime_plot.joint_data[j][i])
                            else:
                                row.append(0)
                        writer.writerow(row)
                
                logger.info(f"数据已导出到: {filename}")
                
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
    
    def save_screenshot(self):
        """保存截图"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import pyqtgraph.exporters
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存截图", "plot_screenshot.png", "PNG Files (*.png)"
            )
            
            if filename:
                exporter = pg.exporters.ImageExporter(self.realtime_plot.plot_widget.plotItem)
                exporter.export(filename)
                logger.info(f"截图已保存到: {filename}")
                
        except Exception as e:
            logger.error(f"保存截图失败: {e}")