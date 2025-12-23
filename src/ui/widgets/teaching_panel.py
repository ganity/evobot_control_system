"""
示教模式面板

功能：
- 示教录制控制
- 关键帧管理
- 序列回放
- 序列管理
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QTextEdit,
    QGroupBox, QProgressBar, QComboBox, QSpinBox, QMessageBox,
    QFileDialog, QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
from typing import List, Optional, Dict, Any
import time

from utils.logger import get_logger
from application.teaching_mode import get_teaching_mode, TeachingState, TeachingSequence
from core.trajectory_planner import InterpolationType

logger = get_logger(__name__)


class SequenceInfoDialog(QDialog):
    """序列信息对话框"""
    
    def __init__(self, parent=None, sequence: Optional[TeachingSequence] = None):
        super().__init__(parent)
        self.sequence = sequence
        self.setup_ui()
        
        if sequence:
            self.load_sequence_info()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("序列信息")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入序列名称")
        form_layout.addRow("名称:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("输入序列描述")
        self.description_edit.setMaximumHeight(100)
        form_layout.addRow("描述:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_sequence_info(self):
        """加载序列信息"""
        if self.sequence:
            self.name_edit.setText(self.sequence.name)
            self.description_edit.setPlainText(self.sequence.description)
    
    def get_sequence_info(self) -> tuple[str, str]:
        """获取序列信息"""
        return self.name_edit.text().strip(), self.description_edit.toPlainText().strip()


class KeyFrameWidget(QWidget):
    """关键帧控件"""
    
    # 信号
    delete_requested = pyqtSignal(int)  # 删除请求
    
    def __init__(self, index: int, keyframe_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.index = index
        self.keyframe_data = keyframe_data
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 关键帧信息
        info_layout = QVBoxLayout()
        
        # 名称和时间
        name_label = QLabel(self.keyframe_data.get('name', f'关键帧{self.index}'))
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)
        
        time_label = QLabel(f"时间: {self.keyframe_data.get('timestamp', 0):.2f}s")
        info_layout.addWidget(time_label)
        
        # 位置信息（显示前3个关节）
        positions = self.keyframe_data.get('positions', [])
        if positions:
            pos_text = f"位置: {positions[0]}, {positions[1]}, {positions[2]}..."
            pos_label = QLabel(pos_text)
            pos_label.setStyleSheet("color: #666;")
            info_layout.addWidget(pos_label)
        
        layout.addLayout(info_layout)
        
        # 删除按钮
        delete_button = QPushButton("删除")
        delete_button.setMaximumWidth(60)
        delete_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        delete_button.clicked.connect(lambda: self.delete_requested.emit(self.index))
        layout.addWidget(delete_button)


class TeachingPanel(QWidget):
    """示教模式面板"""
    
    # 信号
    sequence_selected = pyqtSignal(str)  # 序列选择
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.teaching_mode = get_teaching_mode()
        self.current_sequence: Optional[TeachingSequence] = None
        
        self.setup_ui()
        self.connect_signals()
        
        # 状态更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(100)  # 100ms更新
        
        # 刷新序列列表
        self.refresh_sequence_list()
    
    def setup_ui(self):
        """设置UI"""
        # 主布局使用垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        from PyQt5.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # 内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("示教模式")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 录制控制区域
        record_group = QGroupBox("录制控制")
        record_layout = QVBoxLayout(record_group)
        
        # 录制按钮行
        record_button_layout = QHBoxLayout()
        
        self.start_record_button = QPushButton("开始录制")
        self.start_record_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        record_button_layout.addWidget(self.start_record_button)
        
        self.stop_record_button = QPushButton("停止录制")
        self.stop_record_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_record_button.setEnabled(False)
        record_button_layout.addWidget(self.stop_record_button)
        
        self.add_keyframe_button = QPushButton("添加关键帧")
        self.add_keyframe_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        self.add_keyframe_button.setEnabled(False)
        record_button_layout.addWidget(self.add_keyframe_button)
        
        record_layout.addLayout(record_button_layout)
        
        # 录制状态
        self.record_status_label = QLabel("状态: 空闲")
        record_layout.addWidget(self.record_status_label)
        
        # 录制进度
        self.record_progress = QProgressBar()
        self.record_progress.setVisible(False)
        record_layout.addWidget(self.record_progress)
        
        layout.addWidget(record_group)
        
        # 关键帧列表
        keyframes_group = QGroupBox("关键帧列表")
        keyframes_layout = QVBoxLayout(keyframes_group)
        
        self.keyframes_list = QListWidget()
        self.keyframes_list.setMaximumHeight(200)
        keyframes_layout.addWidget(self.keyframes_list)
        
        layout.addWidget(keyframes_group)
        
        # 回放控制区域
        playback_group = QGroupBox("回放控制")
        playback_layout = QVBoxLayout(playback_group)
        
        # 插值算法选择
        algorithm_layout = QHBoxLayout()
        algorithm_layout.addWidget(QLabel("插值算法:"))
        
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "线性插值", "三次样条", "五次多项式", "梯形速度", "S曲线"
        ])
        self.algorithm_combo.setCurrentText("三次样条")
        algorithm_layout.addWidget(self.algorithm_combo)
        
        algorithm_layout.addStretch()
        playback_layout.addLayout(algorithm_layout)
        
        # 回放按钮
        playback_button_layout = QHBoxLayout()
        
        self.play_button = QPushButton("回放序列")
        self.play_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.play_button.setEnabled(False)
        playback_button_layout.addWidget(self.play_button)
        
        self.stop_playback_button = QPushButton("停止回放")
        self.stop_playback_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_playback_button.setEnabled(False)
        playback_button_layout.addWidget(self.stop_playback_button)
        
        playback_layout.addLayout(playback_button_layout)
        
        layout.addWidget(playback_group)
        
        # 序列管理区域
        sequence_group = QGroupBox("序列管理")
        sequence_layout = QVBoxLayout(sequence_group)
        
        # 序列列表
        self.sequence_list = QListWidget()
        self.sequence_list.setMaximumHeight(150)
        sequence_layout.addWidget(self.sequence_list)
        
        # 序列操作按钮
        sequence_button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存序列")
        self.save_button.setEnabled(False)
        sequence_button_layout.addWidget(self.save_button)
        
        self.load_button = QPushButton("加载序列")
        sequence_button_layout.addWidget(self.load_button)
        
        self.delete_sequence_button = QPushButton("删除序列")
        sequence_button_layout.addWidget(self.delete_sequence_button)
        
        self.refresh_button = QPushButton("刷新列表")
        sequence_button_layout.addWidget(self.refresh_button)
        
        sequence_layout.addLayout(sequence_button_layout)
        
        layout.addWidget(sequence_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置滚动区域的部件
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
    
    def connect_signals(self):
        """连接信号"""
        self.start_record_button.clicked.connect(self.start_recording)
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.add_keyframe_button.clicked.connect(self.add_keyframe)
        
        self.play_button.clicked.connect(self.play_sequence)
        self.stop_playback_button.clicked.connect(self.stop_playback)
        
        self.save_button.clicked.connect(self.save_sequence)
        self.load_button.clicked.connect(self.load_sequence)
        self.delete_sequence_button.clicked.connect(self.delete_sequence)
        self.refresh_button.clicked.connect(self.refresh_sequence_list)
        
        self.sequence_list.itemClicked.connect(self.on_sequence_selected)
    
    def start_recording(self):
        """开始录制"""
        dialog = SequenceInfoDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, description = dialog.get_sequence_info()
            if name:
                if self.teaching_mode.start_recording(name, description):
                    self.start_record_button.setEnabled(False)
                    self.stop_record_button.setEnabled(True)
                    self.add_keyframe_button.setEnabled(True)
                    self.record_progress.setVisible(True)
                else:
                    QMessageBox.warning(self, "错误", "开始录制失败")
            else:
                QMessageBox.warning(self, "错误", "请输入序列名称")
    
    def stop_recording(self):
        """停止录制"""
        if self.teaching_mode.stop_recording():
            self.start_record_button.setEnabled(True)
            self.stop_record_button.setEnabled(False)
            self.add_keyframe_button.setEnabled(False)
            self.record_progress.setVisible(False)
            self.save_button.setEnabled(True)
            
            # 更新关键帧列表
            self.update_keyframes_list()
        else:
            QMessageBox.warning(self, "错误", "停止录制失败")
    
    def add_keyframe(self):
        """添加关键帧"""
        name, ok = QLineEdit().getText(self, "添加关键帧", "关键帧名称:")
        if ok and name:
            if self.teaching_mode.add_keyframe_manually(name):
                self.update_keyframes_list()
            else:
                QMessageBox.warning(self, "错误", "添加关键帧失败")
    
    def play_sequence(self):
        """回放序列"""
        if not self.current_sequence:
            QMessageBox.warning(self, "错误", "请先选择一个序列")
            return
        
        # 获取插值算法
        algorithm_map = {
            "线性插值": InterpolationType.LINEAR,
            "三次样条": InterpolationType.CUBIC_SPLINE,
            "五次多项式": InterpolationType.QUINTIC,
            "梯形速度": InterpolationType.TRAPEZOIDAL,
            "S曲线": InterpolationType.S_CURVE
        }
        
        algorithm = algorithm_map.get(self.algorithm_combo.currentText(), InterpolationType.CUBIC_SPLINE)
        
        if self.teaching_mode.play_sequence(self.current_sequence, algorithm):
            self.play_button.setEnabled(False)
            self.stop_playback_button.setEnabled(True)
        else:
            QMessageBox.warning(self, "错误", "回放序列失败")
    
    def stop_playback(self):
        """停止回放"""
        self.teaching_mode.stop_playback()
        self.play_button.setEnabled(True)
        self.stop_playback_button.setEnabled(False)
    
    def save_sequence(self):
        """保存序列"""
        current_seq = self.teaching_mode.get_current_sequence()
        if current_seq:
            if self.teaching_mode.save_sequence(current_seq):
                QMessageBox.information(self, "成功", "序列保存成功")
                self.refresh_sequence_list()
                self.save_button.setEnabled(False)
            else:
                QMessageBox.warning(self, "错误", "保存序列失败")
        else:
            QMessageBox.warning(self, "错误", "没有可保存的序列")
    
    def load_sequence(self):
        """加载序列"""
        item = self.sequence_list.currentItem()
        if not item:
            QMessageBox.warning(self, "错误", "请选择一个序列")
            return
        
        filename = item.data(Qt.UserRole)
        filepath = f"data/sequences/{filename}"
        
        sequence = self.teaching_mode.load_sequence(filepath)
        if sequence:
            self.current_sequence = sequence
            self.update_keyframes_list()
            self.play_button.setEnabled(True)
            QMessageBox.information(self, "成功", f"序列 '{sequence.name}' 加载成功")
        else:
            QMessageBox.warning(self, "错误", "加载序列失败")
    
    def delete_sequence(self):
        """删除序列"""
        item = self.sequence_list.currentItem()
        if not item:
            QMessageBox.warning(self, "错误", "请选择一个序列")
            return
        
        filename = item.data(Qt.UserRole)
        sequence_name = item.text().split(' - ')[0]
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除序列 '{sequence_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                import os
                filepath = f"data/sequences/{filename}"
                os.remove(filepath)
                self.refresh_sequence_list()
                QMessageBox.information(self, "成功", "序列删除成功")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除序列失败: {e}")
    
    def refresh_sequence_list(self):
        """刷新序列列表"""
        self.sequence_list.clear()
        
        sequences = self.teaching_mode.list_sequences()
        for seq_info in sequences:
            item_text = f"{seq_info['name']} - {seq_info['keyframes_count']}帧"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, seq_info['filename'])
            
            # 添加工具提示
            tooltip = f"名称: {seq_info['name']}\n"
            tooltip += f"描述: {seq_info['description']}\n"
            tooltip += f"关键帧数: {seq_info['keyframes_count']}\n"
            tooltip += f"创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(seq_info['created_at']))}"
            item.setToolTip(tooltip)
            
            self.sequence_list.addItem(item)
    
    def on_sequence_selected(self, item: QListWidgetItem):
        """序列选择事件"""
        filename = item.data(Qt.UserRole)
        self.sequence_selected.emit(filename)
    
    def update_keyframes_list(self):
        """更新关键帧列表"""
        self.keyframes_list.clear()
        
        current_seq = self.current_sequence or self.teaching_mode.get_current_sequence()
        if current_seq:
            for i, keyframe in enumerate(current_seq.keyframes):
                keyframe_data = keyframe.to_dict()
                
                # 创建自定义控件
                keyframe_widget = KeyFrameWidget(i, keyframe_data)
                keyframe_widget.delete_requested.connect(self.delete_keyframe)
                
                # 添加到列表
                item = QListWidgetItem()
                item.setSizeHint(keyframe_widget.sizeHint())
                self.keyframes_list.addItem(item)
                self.keyframes_list.setItemWidget(item, keyframe_widget)
    
    def delete_keyframe(self, index: int):
        """删除关键帧"""
        current_seq = self.current_sequence or self.teaching_mode.get_current_sequence()
        if current_seq and current_seq.remove_keyframe(index):
            self.update_keyframes_list()
    
    def update_status(self):
        """更新状态显示"""
        state = self.teaching_mode.get_state()
        
        if state == TeachingState.IDLE:
            self.record_status_label.setText("状态: 空闲")
            self.record_status_label.setStyleSheet("color: #666;")
        elif state == TeachingState.RECORDING:
            self.record_status_label.setText("状态: 录制中...")
            self.record_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # 更新关键帧列表
            self.update_keyframes_list()
        elif state == TeachingState.PLAYING:
            self.record_status_label.setText("状态: 回放中...")
            self.record_status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        
        # 更新按钮状态
        if state == TeachingState.PLAYING:
            self.play_button.setEnabled(False)
            self.stop_playback_button.setEnabled(True)
        elif state == TeachingState.IDLE:
            self.play_button.setEnabled(self.current_sequence is not None)
            self.stop_playback_button.setEnabled(False)