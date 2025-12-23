"""
数据录制回放面板

功能：
- 数据录制控制
- 录制格式选择
- 数据回放控制
- 回放配置管理
- 录制文件管理
"""

import sys
import os
from typing import List, Optional, Dict, Any
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QProgressBar, QSlider, QTabWidget, QTextEdit, QLineEdit,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

import pyqtgraph as pg
import numpy as np

from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics, MessagePriority
from application.data_recorder import (
    get_data_recorder, RecordingFormat, RecordingState, RecordingSession
)
from application.data_player import (
    get_data_player, PlaybackMode, PlaybackState, PlaybackConfig
)

logger = get_logger(__name__)


class RecordingConfigDialog(QDialog):
    """录制配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("录制配置")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 会话名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入录制会话名称")
        form_layout.addRow("会话名称:", self.name_edit)
        
        # 描述
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("输入录制描述")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("描述:", self.description_edit)
        
        # 采样率
        self.sample_rate_spinbox = QDoubleSpinBox()
        self.sample_rate_spinbox.setRange(1.0, 1000.0)
        self.sample_rate_spinbox.setValue(100.0)
        self.sample_rate_spinbox.setSuffix(" Hz")
        form_layout.addRow("采样率:", self.sample_rate_spinbox)
        
        # 录制格式
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "HDF5", "Binary"])
        form_layout.addRow("格式:", self.format_combo)
        
        # 自动保存
        self.auto_save_checkbox = QCheckBox("自动保存")
        self.auto_save_checkbox.setChecked(True)
        form_layout.addRow("选项:", self.auto_save_checkbox)
        
        # 压缩
        self.compression_checkbox = QCheckBox("启用压缩")
        self.compression_checkbox.setChecked(True)
        form_layout.addRow("", self.compression_checkbox)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        format_map = {
            "JSON": RecordingFormat.JSON,
            "CSV": RecordingFormat.CSV,
            "HDF5": RecordingFormat.HDF5,
            "Binary": RecordingFormat.BINARY
        }
        
        return {
            'name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'sample_rate': self.sample_rate_spinbox.value(),
            'format': format_map[self.format_combo.currentText()],
            'auto_save': self.auto_save_checkbox.isChecked(),
            'compression': self.compression_checkbox.isChecked()
        }


class PlaybackConfigDialog(QDialog):
    """回放配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("回放配置")
        self.setModal(True)
        self.resize(400, 350)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 回放模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "仅位置回放", "完整回放", "速度曲线回放", "力反馈回放"
        ])
        form_layout.addRow("回放模式:", self.mode_combo)
        
        # 速度因子
        self.speed_factor_spinbox = QDoubleSpinBox()
        self.speed_factor_spinbox.setRange(0.1, 10.0)
        self.speed_factor_spinbox.setValue(1.0)
        self.speed_factor_spinbox.setSingleStep(0.1)
        form_layout.addRow("速度因子:", self.speed_factor_spinbox)
        
        # 循环播放
        self.loop_checkbox = QCheckBox("循环播放")
        form_layout.addRow("选项:", self.loop_checkbox)
        
        # 实时同步
        self.sync_checkbox = QCheckBox("同步到实时")
        self.sync_checkbox.setChecked(True)
        form_layout.addRow("", self.sync_checkbox)
        
        # 启用插值
        self.interpolation_checkbox = QCheckBox("启用插值")
        self.interpolation_checkbox.setChecked(True)
        form_layout.addRow("", self.interpolation_checkbox)
        
        # 时间范围
        time_group = QGroupBox("时间范围")
        time_layout = QGridLayout(time_group)
        
        self.start_time_spinbox = QDoubleSpinBox()
        self.start_time_spinbox.setRange(0.0, 3600.0)
        self.start_time_spinbox.setSuffix(" s")
        time_layout.addWidget(QLabel("开始时间:"), 0, 0)
        time_layout.addWidget(self.start_time_spinbox, 0, 1)
        
        self.end_time_spinbox = QDoubleSpinBox()
        self.end_time_spinbox.setRange(0.0, 3600.0)
        self.end_time_spinbox.setValue(3600.0)
        self.end_time_spinbox.setSuffix(" s")
        time_layout.addWidget(QLabel("结束时间:"), 1, 0)
        time_layout.addWidget(self.end_time_spinbox, 1, 1)
        
        self.use_full_range_checkbox = QCheckBox("使用完整范围")
        self.use_full_range_checkbox.setChecked(True)
        time_layout.addWidget(self.use_full_range_checkbox, 2, 0, 1, 2)
        
        layout.addLayout(form_layout)
        layout.addWidget(time_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 连接信号
        self.use_full_range_checkbox.toggled.connect(self._on_full_range_toggled)
        
        # 初始状态
        self._on_full_range_toggled(True)
    
    def _on_full_range_toggled(self, checked: bool):
        """完整范围切换"""
        self.start_time_spinbox.setEnabled(not checked)
        self.end_time_spinbox.setEnabled(not checked)
    
    def get_config(self) -> PlaybackConfig:
        """获取配置"""
        mode_map = {
            "仅位置回放": PlaybackMode.POSITION_ONLY,
            "完整回放": PlaybackMode.FULL_REPLAY,
            "速度曲线回放": PlaybackMode.VELOCITY_PROFILE,
            "力反馈回放": PlaybackMode.FORCE_FEEDBACK
        }
        
        config = PlaybackConfig(
            mode=mode_map[self.mode_combo.currentText()],
            speed_factor=self.speed_factor_spinbox.value(),
            loop_enabled=self.loop_checkbox.isChecked(),
            sync_to_realtime=self.sync_checkbox.isChecked(),
            interpolation_enabled=self.interpolation_checkbox.isChecked()
        )
        
        if not self.use_full_range_checkbox.isChecked():
            config.start_time = self.start_time_spinbox.value()
            config.end_time = self.end_time_spinbox.value()
        
        return config


class DataVisualizationWidget(QWidget):
    """数据可视化组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # 数据
        self.time_data = np.array([0])
        self.position_data = np.zeros((1, 10))
        self.velocity_data = np.zeros((1, 10))
        self.current_data = np.zeros((1, 10))
        
        # 显示的关节
        self.visible_joints = set(range(10))
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("显示关节:"))
        
        self.joint_checkboxes = []
        for i in range(10):
            checkbox = QCheckBox(f"J{i}")
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda checked, joint=i: self._on_joint_visibility_changed(joint, checked))
            self.joint_checkboxes.append(checkbox)
            control_layout.addWidget(checkbox)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 图形窗口
        self.graphics_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_widget)
        
        # 位置图
        self.position_plot = self.graphics_widget.addPlot(title="关节位置")
        self.position_plot.setLabel('left', '位置', units='单位')
        self.position_plot.setLabel('bottom', '时间', units='秒')
        self.position_plot.showGrid(x=True, y=True)
        
        # 换行
        self.graphics_widget.nextRow()
        
        # 速度图
        self.velocity_plot = self.graphics_widget.addPlot(title="关节速度")
        self.velocity_plot.setLabel('left', '速度', units='单位/秒')
        self.velocity_plot.setLabel('bottom', '时间', units='秒')
        self.velocity_plot.showGrid(x=True, y=True)
        
        # 换行
        self.graphics_widget.nextRow()
        
        # 电流图
        self.current_plot = self.graphics_widget.addPlot(title="关节电流")
        self.current_plot.setLabel('left', '电流', units='mA')
        self.current_plot.setLabel('bottom', '时间', units='秒')
        self.current_plot.showGrid(x=True, y=True)
        
        # 链接X轴
        self.velocity_plot.setXLink(self.position_plot)
        self.current_plot.setXLink(self.position_plot)
        
        # 曲线
        self.position_curves = []
        self.velocity_curves = []
        self.current_curves = []
        
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange', 'pink', 'gray']
        
        for i in range(10):
            pos_curve = self.position_plot.plot(pen=colors[i], name=f'Joint {i}')
            vel_curve = self.velocity_plot.plot(pen=colors[i], name=f'Joint {i}')
            cur_curve = self.current_plot.plot(pen=colors[i], name=f'Joint {i}')
            
            self.position_curves.append(pos_curve)
            self.velocity_curves.append(vel_curve)
            self.current_curves.append(cur_curve)
    
    def _on_joint_visibility_changed(self, joint_id: int, visible: bool):
        """关节可见性改变"""
        if visible:
            self.visible_joints.add(joint_id)
        else:
            self.visible_joints.discard(joint_id)
        
        self.update_curves()
    
    def update_data(self, session: RecordingSession):
        """更新数据"""
        if not session.data_points:
            return
        
        # 提取数据
        self.time_data = np.array([dp.timestamp for dp in session.data_points])
        self.position_data = np.array([dp.positions for dp in session.data_points])
        self.velocity_data = np.array([dp.velocities for dp in session.data_points])
        self.current_data = np.array([dp.currents for dp in session.data_points])
        
        self.update_curves()
    
    def update_curves(self):
        """更新曲线"""
        for i in range(10):
            if i in self.visible_joints and len(self.time_data) > 0:
                self.position_curves[i].setData(self.time_data, self.position_data[:, i])
                self.velocity_curves[i].setData(self.time_data, self.velocity_data[:, i])
                self.current_curves[i].setData(self.time_data, self.current_data[:, i])
            else:
                self.position_curves[i].clear()
                self.velocity_curves[i].clear()
                self.current_curves[i].clear()
    
    def clear_curves(self):
        """清空曲线"""
        for i in range(10):
            self.position_curves[i].clear()
            self.velocity_curves[i].clear()
            self.current_curves[i].clear()


class RecordingPanel(QWidget):
    """数据录制回放面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_recorder = get_data_recorder()
        self.data_player = get_data_player()
        self.message_bus = get_message_bus()
        
        self.current_session: Optional[RecordingSession] = None
        
        self.setup_ui()
        self.connect_signals()
        self.setup_timer()
        
        # 刷新文件列表
        self.refresh_file_list()
        
        logger.info("数据录制回放面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 录制标签页
        self.setup_recording_tab()
        
        # 回放标签页
        self.setup_playback_tab()
        
        # 文件管理标签页
        self.setup_file_management_tab()
        
        # 数据可视化标签页
        self.setup_visualization_tab()
    
    def setup_recording_tab(self):
        """设置录制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 录制控制组
        record_group = QGroupBox("录制控制")
        record_layout = QVBoxLayout(record_group)
        
        # 录制按钮行
        button_layout = QHBoxLayout()
        
        self.start_record_button = QPushButton("开始录制")
        self.start_record_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.start_record_button.setMinimumHeight(40)
        button_layout.addWidget(self.start_record_button)
        
        self.pause_record_button = QPushButton("暂停录制")
        self.pause_record_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        self.pause_record_button.setMinimumHeight(40)
        self.pause_record_button.setEnabled(False)
        button_layout.addWidget(self.pause_record_button)
        
        self.stop_record_button = QPushButton("停止录制")
        self.stop_record_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_record_button.setMinimumHeight(40)
        self.stop_record_button.setEnabled(False)
        button_layout.addWidget(self.stop_record_button)
        
        record_layout.addLayout(button_layout)
        
        # 录制状态
        status_layout = QGridLayout()
        
        status_layout.addWidget(QLabel("状态:"), 0, 0)
        self.record_status_label = QLabel("空闲")
        status_layout.addWidget(self.record_status_label, 0, 1)
        
        status_layout.addWidget(QLabel("时长:"), 1, 0)
        self.record_duration_label = QLabel("00:00:00")
        status_layout.addWidget(self.record_duration_label, 1, 1)
        
        status_layout.addWidget(QLabel("数据点:"), 2, 0)
        self.record_points_label = QLabel("0")
        status_layout.addWidget(self.record_points_label, 2, 1)
        
        status_layout.addWidget(QLabel("采样率:"), 3, 0)
        self.record_rate_label = QLabel("100 Hz")
        status_layout.addWidget(self.record_rate_label, 3, 1)
        
        record_layout.addLayout(status_layout)
        
        layout.addWidget(record_group)
        
        # 录制配置组
        config_group = QGroupBox("录制配置")
        config_layout = QHBoxLayout(config_group)
        
        self.config_record_button = QPushButton("配置录制")
        config_layout.addWidget(self.config_record_button)
        
        config_layout.addStretch()
        
        layout.addWidget(config_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "数据录制")
    
    def setup_playback_tab(self):
        """设置回放标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 回放控制组
        playback_group = QGroupBox("回放控制")
        playback_layout = QVBoxLayout(playback_group)
        
        # 回放按钮行
        button_layout = QHBoxLayout()
        
        self.start_playback_button = QPushButton("开始回放")
        self.start_playback_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.start_playback_button.setMinimumHeight(40)
        self.start_playback_button.setEnabled(False)
        button_layout.addWidget(self.start_playback_button)
        
        self.pause_playback_button = QPushButton("暂停回放")
        self.pause_playback_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        self.pause_playback_button.setMinimumHeight(40)
        self.pause_playback_button.setEnabled(False)
        button_layout.addWidget(self.pause_playback_button)
        
        self.stop_playback_button = QPushButton("停止回放")
        self.stop_playback_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_playback_button.setMinimumHeight(40)
        self.stop_playback_button.setEnabled(False)
        button_layout.addWidget(self.stop_playback_button)
        
        playback_layout.addLayout(button_layout)
        
        # 进度控制
        progress_layout = QVBoxLayout()
        
        progress_layout.addWidget(QLabel("回放进度:"))
        
        self.playback_progress_slider = QSlider(Qt.Horizontal)
        self.playback_progress_slider.setRange(0, 1000)
        self.playback_progress_slider.setValue(0)
        progress_layout.addWidget(self.playback_progress_slider)
        
        progress_info_layout = QHBoxLayout()
        self.playback_time_label = QLabel("00:00 / 00:00")
        progress_info_layout.addWidget(self.playback_time_label)
        progress_info_layout.addStretch()
        
        self.playback_speed_label = QLabel("速度: 1.0x")
        progress_info_layout.addWidget(self.playback_speed_label)
        
        progress_layout.addLayout(progress_info_layout)
        
        playback_layout.addLayout(progress_layout)
        
        # 回放状态
        status_layout = QGridLayout()
        
        status_layout.addWidget(QLabel("状态:"), 0, 0)
        self.playback_status_label = QLabel("空闲")
        status_layout.addWidget(self.playback_status_label, 0, 1)
        
        status_layout.addWidget(QLabel("模式:"), 1, 0)
        self.playback_mode_label = QLabel("仅位置回放")
        status_layout.addWidget(self.playback_mode_label, 1, 1)
        
        playback_layout.addLayout(status_layout)
        
        layout.addWidget(playback_group)
        
        # 回放配置组
        config_group = QGroupBox("回放配置")
        config_layout = QHBoxLayout(config_group)
        
        self.config_playback_button = QPushButton("配置回放")
        config_layout.addWidget(self.config_playback_button)
        
        config_layout.addStretch()
        
        layout.addWidget(config_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "数据回放")
    
    def setup_file_management_tab(self):
        """设置文件管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 文件列表
        file_group = QGroupBox("录制文件")
        file_layout = QVBoxLayout(file_group)
        
        # 文件表格
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(["文件名", "格式", "大小", "修改时间", "操作"])
        
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        file_layout.addWidget(self.file_table)
        
        # 文件操作按钮
        file_button_layout = QHBoxLayout()
        
        self.refresh_files_button = QPushButton("刷新")
        file_button_layout.addWidget(self.refresh_files_button)
        
        self.import_file_button = QPushButton("导入文件")
        file_button_layout.addWidget(self.import_file_button)
        
        self.export_file_button = QPushButton("导出文件")
        file_button_layout.addWidget(self.export_file_button)
        
        self.delete_file_button = QPushButton("删除文件")
        file_button_layout.addWidget(self.delete_file_button)
        
        file_button_layout.addStretch()
        
        file_layout.addLayout(file_button_layout)
        
        layout.addWidget(file_group)
        
        self.tab_widget.addTab(tab, "文件管理")
    
    def setup_visualization_tab(self):
        """设置数据可视化标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 数据可视化组件
        self.visualization_widget = DataVisualizationWidget()
        layout.addWidget(self.visualization_widget)
        
        self.tab_widget.addTab(tab, "数据可视化")
    
    def connect_signals(self):
        """连接信号"""
        # 录制控制
        self.start_record_button.clicked.connect(self.start_recording)
        self.pause_record_button.clicked.connect(self.pause_recording)
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.config_record_button.clicked.connect(self.configure_recording)
        
        # 回放控制
        self.start_playback_button.clicked.connect(self.start_playback)
        self.pause_playback_button.clicked.connect(self.pause_playback)
        self.stop_playback_button.clicked.connect(self.stop_playback)
        self.config_playback_button.clicked.connect(self.configure_playback)
        
        # 进度控制
        self.playback_progress_slider.sliderPressed.connect(self._on_progress_slider_pressed)
        self.playback_progress_slider.sliderReleased.connect(self._on_progress_slider_released)
        
        # 文件管理
        self.refresh_files_button.clicked.connect(self.refresh_file_list)
        self.import_file_button.clicked.connect(self.import_file)
        self.export_file_button.clicked.connect(self.export_file)
        self.delete_file_button.clicked.connect(self.delete_file)
        
        self.file_table.itemSelectionChanged.connect(self.on_file_selected)
        
        # 订阅消息
        self.message_bus.subscribe(Topics.RECORDING_STARTED, self.on_recording_started)
        self.message_bus.subscribe(Topics.RECORDING_STOPPED, self.on_recording_stopped)
        self.message_bus.subscribe(Topics.PLAYBACK_STARTED, self.on_playback_started)
        self.message_bus.subscribe(Topics.PLAYBACK_STOPPED, self.on_playback_stopped)
    
    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(100)  # 100ms更新
    
    def start_recording(self):
        """开始录制"""
        dialog = RecordingConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            
            if not config['name']:
                QMessageBox.warning(self, "错误", "请输入会话名称")
                return
            
            # 配置录制器
            self.data_recorder.configure_recording(
                sample_rate=config['sample_rate'],
                format=config['format'],
                auto_save=config['auto_save'],
                compression=config['compression']
            )
            
            # 开始录制
            if self.data_recorder.start_recording(config['name'], config['description']):
                self.start_record_button.setEnabled(False)
                self.pause_record_button.setEnabled(True)
                self.stop_record_button.setEnabled(True)
            else:
                QMessageBox.warning(self, "错误", "开始录制失败")
    
    def pause_recording(self):
        """暂停录制"""
        if self.data_recorder.get_state() == RecordingState.RECORDING:
            if self.data_recorder.pause_recording():
                self.pause_record_button.setText("恢复录制")
            else:
                QMessageBox.warning(self, "错误", "暂停录制失败")
        else:
            if self.data_recorder.resume_recording():
                self.pause_record_button.setText("暂停录制")
            else:
                QMessageBox.warning(self, "错误", "恢复录制失败")
    
    def stop_recording(self):
        """停止录制"""
        if self.data_recorder.stop_recording():
            self.start_record_button.setEnabled(True)
            self.pause_record_button.setEnabled(False)
            self.pause_record_button.setText("暂停录制")
            self.stop_record_button.setEnabled(False)
            
            # 刷新文件列表
            self.refresh_file_list()
        else:
            QMessageBox.warning(self, "错误", "停止录制失败")
    
    def configure_recording(self):
        """配置录制"""
        dialog = RecordingConfigDialog(self)
        dialog.exec_()
    
    def start_playback(self):
        """开始回放"""
        if not self.current_session:
            QMessageBox.warning(self, "错误", "请先选择一个录制文件")
            return
        
        # 加载会话到回放器
        if not self.data_player.load_session_for_playback(self.current_session):
            QMessageBox.warning(self, "错误", "加载回放会话失败")
            return
        
        # 开始回放
        if self.data_player.start_playback():
            self.start_playback_button.setEnabled(False)
            self.pause_playback_button.setEnabled(True)
            self.stop_playback_button.setEnabled(True)
        else:
            QMessageBox.warning(self, "错误", "开始回放失败")
    
    def pause_playback(self):
        """暂停回放"""
        if self.data_player.get_state() == PlaybackState.PLAYING:
            if self.data_player.pause_playback():
                self.pause_playback_button.setText("恢复回放")
            else:
                QMessageBox.warning(self, "错误", "暂停回放失败")
        else:
            if self.data_player.resume_playback():
                self.pause_playback_button.setText("暂停回放")
            else:
                QMessageBox.warning(self, "错误", "恢复回放失败")
    
    def stop_playback(self):
        """停止回放"""
        if self.data_player.stop_playback():
            self.start_playback_button.setEnabled(True)
            self.pause_playback_button.setEnabled(False)
            self.pause_playback_button.setText("暂停回放")
            self.stop_playback_button.setEnabled(False)
        else:
            QMessageBox.warning(self, "错误", "停止回放失败")
    
    def configure_playback(self):
        """配置回放"""
        dialog = PlaybackConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            self.data_player.configure_playback(config)
            
            # 更新显示
            mode_text = {
                PlaybackMode.POSITION_ONLY: "仅位置回放",
                PlaybackMode.FULL_REPLAY: "完整回放",
                PlaybackMode.VELOCITY_PROFILE: "速度曲线回放",
                PlaybackMode.FORCE_FEEDBACK: "力反馈回放"
            }
            self.playback_mode_label.setText(mode_text[config.mode])
    
    def _on_progress_slider_pressed(self):
        """进度滑块按下"""
        pass
    
    def _on_progress_slider_released(self):
        """进度滑块释放"""
        if self.data_player.get_state() in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
            progress = self.playback_progress_slider.value() / 1000.0
            self.data_player.seek_to_progress(progress)
    
    def refresh_file_list(self):
        """刷新文件列表"""
        try:
            recordings = self.data_recorder.list_recordings()
            
            self.file_table.setRowCount(len(recordings))
            
            for row, recording in enumerate(recordings):
                # 文件名
                name_item = QTableWidgetItem(recording['filename'])
                self.file_table.setItem(row, 0, name_item)
                
                # 格式
                format_item = QTableWidgetItem(recording['format'].upper())
                self.file_table.setItem(row, 1, format_item)
                
                # 大小
                size_mb = recording['size'] / (1024 * 1024)
                size_item = QTableWidgetItem(f"{size_mb:.2f} MB")
                self.file_table.setItem(row, 2, size_item)
                
                # 修改时间
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(recording['modified_at']))
                time_item = QTableWidgetItem(time_str)
                self.file_table.setItem(row, 3, time_item)
                
                # 操作按钮 - 使用文本而不是按钮组件避免线程问题
                action_item = QTableWidgetItem("点击加载")
                action_item.setData(Qt.UserRole, recording['filepath'])
                self.file_table.setItem(row, 4, action_item)
                
        except Exception as e:
            logger.error(f"刷新文件列表失败: {e}")
    
    def load_file(self, filepath: str):
        """加载文件"""
        try:
            session = self.data_recorder.load_session(filepath)
            if session:
                self.current_session = session
                self.start_playback_button.setEnabled(True)
                
                # 更新可视化
                self.visualization_widget.update_data(session)
                
                QMessageBox.information(self, "成功", f"文件加载成功: {session.name}")
            else:
                QMessageBox.warning(self, "错误", "加载文件失败")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载文件失败: {e}")
    
    def import_file(self):
        """导入文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入录制文件", "", 
            "All Supported (*.json *.csv *.hdf5 *.h5 *.binary *.pkl);;JSON Files (*.json);;CSV Files (*.csv);;HDF5 Files (*.hdf5 *.h5);;Binary Files (*.binary *.pkl)"
        )
        
        if filepath:
            self.load_file(filepath)
            self.refresh_file_list()
    
    def export_file(self):
        """导出文件"""
        if not self.current_session:
            QMessageBox.warning(self, "错误", "请先选择一个录制文件")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出录制文件", f"{self.current_session.name}.csv",
            "CSV Files (*.csv);;JSON Files (*.json);;All Files (*)"
        )
        
        if filepath:
            try:
                if filepath.endswith('.csv'):
                    # 导出为CSV
                    from application.teaching_mode import get_teaching_mode
                    teaching_mode = get_teaching_mode()
                    
                    # 转换为示教序列格式并导出
                    # 这里需要实现数据格式转换
                    QMessageBox.information(self, "成功", "文件导出成功")
                else:
                    # 保存为原格式
                    if self.data_recorder.save_session(self.current_session, os.path.basename(filepath)):
                        QMessageBox.information(self, "成功", "文件导出成功")
                    else:
                        QMessageBox.warning(self, "错误", "文件导出失败")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"文件导出失败: {e}")
    
    def delete_file(self):
        """删除文件"""
        current_row = self.file_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "错误", "请选择要删除的文件")
            return
        
        filename = self.file_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除文件 '{filename}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                recordings = self.data_recorder.list_recordings()
                if current_row < len(recordings):
                    filepath = recordings[current_row]['filepath']
                    os.remove(filepath)
                    self.refresh_file_list()
                    QMessageBox.information(self, "成功", "文件删除成功")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除文件失败: {e}")
    
    def on_file_selected(self):
        """文件选择事件"""
        try:
            current_row = self.file_table.currentRow()
            if current_row >= 0:
                action_item = self.file_table.item(current_row, 4)
                if action_item:
                    filepath = action_item.data(Qt.UserRole)
                    if filepath:
                        self.load_file(filepath)
        except Exception as e:
            logger.error(f"文件选择处理失败: {e}")
    
    def update_status(self):
        """更新状态显示"""
        # 更新录制状态
        record_state = self.data_recorder.get_state()
        record_stats = self.data_recorder.get_recording_statistics()
        
        if record_state == RecordingState.IDLE:
            self.record_status_label.setText("空闲")
            self.record_status_label.setStyleSheet("color: #666;")
        elif record_state == RecordingState.RECORDING:
            self.record_status_label.setText("录制中...")
            self.record_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif record_state == RecordingState.PAUSED:
            self.record_status_label.setText("已暂停")
            self.record_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        
        # 更新录制统计
        duration = record_stats.get('current_duration', 0)
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        self.record_duration_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        self.record_points_label.setText(str(record_stats.get('total_points_recorded', 0)))
        self.record_rate_label.setText(f"{record_stats.get('sample_rate', 100):.1f} Hz")
        
        # 更新回放状态
        playback_state = self.data_player.get_state()
        playback_stats = self.data_player.get_playback_statistics()
        
        if playback_state == PlaybackState.IDLE:
            self.playback_status_label.setText("空闲")
            self.playback_status_label.setStyleSheet("color: #666;")
        elif playback_state == PlaybackState.PLAYING:
            self.playback_status_label.setText("回放中...")
            self.playback_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif playback_state == PlaybackState.PAUSED:
            self.playback_status_label.setText("已暂停")
            self.playback_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        elif playback_state == PlaybackState.COMPLETED:
            self.playback_status_label.setText("已完成")
            self.playback_status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        
        # 更新回放进度
        if playback_state in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
            progress = playback_stats.get('progress', 0.0)
            self.playback_progress_slider.setValue(int(progress * 1000))
            
            current_time = playback_stats.get('current_time', 0.0)
            total_time = 0.0
            if self.current_session and self.current_session.data_points:
                total_time = self.current_session.duration
            
            current_min = int(current_time // 60)
            current_sec = int(current_time % 60)
            total_min = int(total_time // 60)
            total_sec = int(total_time % 60)
            
            self.playback_time_label.setText(f"{current_min:02d}:{current_sec:02d} / {total_min:02d}:{total_sec:02d}")
            
            speed_factor = playback_stats.get('speed_factor', 1.0)
            self.playback_speed_label.setText(f"速度: {speed_factor:.1f}x")
    
    def on_recording_started(self, message):
        """录制开始事件"""
        pass
    
    def on_recording_stopped(self, message):
        """录制停止事件"""
        self.refresh_file_list()
    
    def on_playback_started(self, message):
        """回放开始事件"""
        pass
    
    def on_playback_stopped(self, message):
        """回放停止事件"""
        pass


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = RecordingPanel()
    panel.show()
    
    sys.exit(app.exec_())