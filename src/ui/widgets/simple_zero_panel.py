"""
简化版零位录制面板

功能：
- 读取当前位置
- 微调零位
- 保存零位
- 加载零位
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSpinBox, QGroupBox, QComboBox, QLineEdit,
    QMessageBox, QDialog, QDialogButtonBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from typing import List, Dict
import datetime

from core.zero_position_manager import get_zero_position_manager
from utils.logger import get_logger

logger = get_logger(__name__)


class SimpleZeroPositionPanel(QWidget):
    """简化版零位录制面板"""
    
    # 信号
    zero_position_changed = pyqtSignal(list)  # 零位改变
    move_to_zero_requested = pyqtSignal()     # 请求移动到零位
    read_current_positions_requested = pyqtSignal()  # 请求读取当前位置
    
    def __init__(self, joints_config: List[Dict], parent=None):
        super().__init__(parent)
        
        self.joints_config = joints_config
        self.zero_manager = get_zero_position_manager()
        
        # 当前位置数据
        self.current_positions = [1500] * 10
        self.working_positions = [1500] * 10  # 工作中的位置（可能包含微调）
        self.val_labels = []
        
        # 关节名称
        self.joint_names = []
        for joint_config in joints_config:
            self.joint_names.append(joint_config.get('name', f'Joint {joint_config.get("id", 0)}'))
        
        self.setup_ui()
        self.connect_signals()
        self.update_display()
        
        # 自动读取定时器
        self.auto_read_timer = QTimer()
        self.auto_read_timer.timeout.connect(self._request_read_positions)
        self.auto_read_timer.setInterval(1000)
        
        logger.info("简化版零位录制面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        # 极简模式样式表
        self.setStyleSheet("""
            QWidget { font-size: 11px; }
            QGroupBox {
                border: 1px solid #DDD;
                border-radius: 4px;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 5px;
                padding: 0 3px;
                color: #666;
                font-weight: bold;
            }
            QPushButton {
                padding: 3px 8px;
                border-radius: 3px;
                min-width: 50px;
            }
            QLineEdit, QComboBox {
                padding: 2px;
                border: 1px solid #CCC;
                border-radius: 2px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Row 1: 标题 + 状态 + 自动读取
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        title_label = QLabel("🛠 零位管理")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
        header_layout.addWidget(title_label)
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.status_label)
        
        header_layout.addStretch()
        
        self.auto_read_button = QPushButton("自动读取")
        self.auto_read_button.setCheckable(True)
        self.auto_read_button.setStyleSheet("""
            QPushButton { background-color: #EEE; border: 1px solid #CCC; }
            QPushButton:checked { background-color: #E3F2FD; border: 1px solid #2196F3; color: #2196F3; }
        """)
        header_layout.addWidget(self.auto_read_button)
        
        layout.addLayout(header_layout)
        
        # Row 2: 10个关节数值显示 (紧凑横向排列)
        # 使用 ScrollArea 防止窗口太窄显示不下
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(60) # 固定高度，非常紧凑
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(5)
        
        self.val_labels = []
        for i in range(10):
            frame = QFrame()
            frame.setFixedSize(60, 45) # 固定小尺寸卡片
            frame.setStyleSheet("background-color: #FFF; border: 1px solid #DDD; border-radius: 3px;")
            
            f_layout = QVBoxLayout(frame)
            f_layout.setContentsMargins(2, 2, 2, 2)
            f_layout.setSpacing(0)
            
            # 名字 (J0, J1...)
            name_text = self.joint_names[i]
            # 简化名字显示 如果太长只取前几个字符或简写
            if "Thumb" in name_text or "拇" in name_text: short_name = "拇指"
            elif "Index" in name_text or "食" in name_text: short_name = "食指"
            elif "Middle" in name_text or "中" in name_text: short_name = "中指"
            elif "Ring" in name_text or "无" in name_text: short_name = "无名"
            elif "Pinky" in name_text or "小" in name_text: short_name = "小指"
            else: short_name = f"J{i}"
            
            lbl_name = QLabel(short_name)
            lbl_name.setAlignment(Qt.AlignCenter)
            lbl_name.setStyleSheet("font-size: 9px; color: #888;")
            f_layout.addWidget(lbl_name)
            
            # 数值
            lbl_val = QLabel("1500")
            lbl_val.setAlignment(Qt.AlignCenter)
            lbl_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #0078D4;")
            self.val_labels.append(lbl_val)
            f_layout.addWidget(lbl_val)
            
            scroll_layout.addWidget(frame)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Row 3: 操作控制栏
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        
        # 左边：录制相关
        record_layout = QHBoxLayout()
        record_layout.setSpacing(5)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("零位名称")
        self.name_edit.setFixedWidth(100)
        self.name_edit.setText(f"ZP_{datetime.datetime.now().strftime('%H%M')}")
        record_layout.addWidget(self.name_edit)
        
        self.read_button = QPushButton("读")
        self.read_button.setToolTip("读取当前位置")
        self.read_button.setFixedWidth(30)
        self.read_button.setStyleSheet("background: #E3F2FD; color: #1565C0; font-weight: bold; border: 1px solid #90CAF9;")
        record_layout.addWidget(self.read_button)
        
        self.adjust_button = QPushButton("调")
        self.adjust_button.setToolTip("微调数值")
        self.adjust_button.setFixedWidth(30)
        self.adjust_button.setStyleSheet("background: #FFF3E0; color: #E65100; font-weight: bold; border: 1px solid #FFCC80;")
        record_layout.addWidget(self.adjust_button)
        
        self.save_button = QPushButton("存")
        self.save_button.setToolTip("保存为零位")
        self.save_button.setFixedWidth(30)
        self.save_button.setStyleSheet("background: #E8F5E9; color: #2E7D32; font-weight: bold; border: 1px solid #A5D6A7;")
        record_layout.addWidget(self.save_button)
        
        ctrl_layout.addLayout(record_layout)
        
        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("color: #DDD;")
        ctrl_layout.addWidget(line)
        
        # 右边：管理相关
        manage_layout = QHBoxLayout()
        manage_layout.setSpacing(5)
        
        self.zero_combo = QComboBox()
        self.zero_combo.setFixedWidth(100)
        manage_layout.addWidget(self.zero_combo)
        
        self.load_button = QPushButton("载入")
        self.load_button.setStyleSheet("background-color: #EEE;")
        manage_layout.addWidget(self.load_button)
        
        self.go_zero_button = QPushButton("回零")
        self.go_zero_button.setStyleSheet("background-color: #F3E5F5; color: #7B1FA2; border: 1px solid #E1BEE7;")
        manage_layout.addWidget(self.go_zero_button)
        
        self.delete_button = QPushButton("Del")
        self.delete_button.setFixedWidth(35)
        self.delete_button.setStyleSheet("color: red; border: none;")
        manage_layout.addWidget(self.delete_button)
        
        ctrl_layout.addLayout(manage_layout)
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)
        
        # 移除底部弹簧，保持紧凑
        # layout.addStretch()
    
    def connect_signals(self):
        """连接信号"""
        self.read_button.clicked.connect(self._on_read_clicked)
        self.adjust_button.clicked.connect(self._on_adjust_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.auto_read_button.toggled.connect(self._on_auto_read_toggled)
        self.load_button.clicked.connect(self._on_load_clicked)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.go_zero_button.clicked.connect(self._on_go_zero_clicked)
    
    def _on_read_clicked(self):
        """读取位置按钮点击"""
        self.read_current_positions_requested.emit()
        self.status_label.setText("正在读取机器人位置...")
    
    def _on_adjust_clicked(self):
        """微调按钮点击"""
        from ui.widgets.zero_position_panel import ZeroPositionAdjustDialog
        
        dialog = ZeroPositionAdjustDialog(self.working_positions, self.joint_names, self)
        if dialog.exec_() == QDialog.Accepted:
            self.working_positions = dialog.get_adjusted_positions()
            self.status_label.setText("位置已微调，请保存零位")
            logger.info(f"零位微调完成: {self.working_positions}")
    
    def _on_save_clicked(self):
        """保存按钮点击"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入零位名称")
            return
        
        # 保存工作位置为零位
        success = self.zero_manager.record_current_positions(
            self.working_positions, name, "用户录制的零位"
        )
        
        if success:
            self.update_display()
            # 选中新保存的零位
            index = self.zero_combo.findText(name)
            if index >= 0:
                self.zero_combo.setCurrentIndex(index)
            
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            self.name_edit.setText(f"零位_{datetime.datetime.now().strftime('%m%d_%H%M')}")
            self.status_label.setText(f"零位 '{name}' 保存成功")
            
            QMessageBox.information(self, "成功", f"零位 '{name}' 已保存\n现在'全部回零'将使用此零位")
        else:
            QMessageBox.critical(self, "错误", "零位保存失败")
            self.status_label.setText("零位保存失败")
    
    def _on_auto_read_toggled(self, checked: bool):
        """自动读取切换"""
        if checked:
            self.auto_read_timer.start()
            self.auto_read_button.setText("🔄 停止自动读取")
            self.status_label.setText("自动读取已开启")
        else:
            self.auto_read_timer.stop()
            self.auto_read_button.setText("🔄 自动读取")
            self.status_label.setText("自动读取已关闭")
    
    def _on_load_clicked(self):
        """加载按钮点击"""
        set_name = self.zero_combo.currentText()
        if not set_name:
            return
        
        success = self.zero_manager.load_zero_position_set(set_name)
        if success:
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            self.status_label.setText(f"已加载零位: {set_name}")
            QMessageBox.information(self, "成功", f"零位 '{set_name}' 已加载\n现在'全部回零'将使用此零位")
        else:
            QMessageBox.critical(self, "错误", f"加载零位 '{set_name}' 失败")
    
    def _on_delete_clicked(self):
        """删除按钮点击"""
        set_name = self.zero_combo.currentText()
        if not set_name:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除零位 '{set_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.zero_manager.delete_zero_position_set(set_name)
            if success:
                self.update_display()
                self.status_label.setText(f"已删除零位: {set_name}")
            else:
                QMessageBox.critical(self, "错误", f"删除零位 '{set_name}' 失败")
    
    def _on_go_zero_clicked(self):
        """移动到零位按钮点击"""
        self.move_to_zero_requested.emit()
        self.status_label.setText("正在移动到零位...")
    
    def _request_read_positions(self):
        """请求读取当前位置"""
        self.read_current_positions_requested.emit()
    
    def update_current_positions(self, positions: List[int]):
        """更新当前位置"""
        self.current_positions = positions[:10]
        self.working_positions = positions[:10]  # 同时更新工作位置
        
        # 更新网格显示
        for i, pos in enumerate(self.current_positions):
            if i < len(self.val_labels):
                self.val_labels[i].setText(str(pos))
        
        self.status_label.setText(f"位置已更新 ({datetime.datetime.now().strftime('%H:%M:%S')})")
    
    def update_display(self):
        """更新显示"""
        # 更新零位下拉框
        current_selection = self.zero_combo.currentText()
        self.zero_combo.clear()
        
        zero_sets = self.zero_manager.get_zero_position_sets()
        for set_name in zero_sets.keys():
            self.zero_combo.addItem(set_name)
        
        # 恢复选中项
        if current_selection:
            index = self.zero_combo.findText(current_selection)
            if index >= 0:
                self.zero_combo.setCurrentIndex(index)
    
    def get_zero_positions(self) -> List[int]:
        """获取当前零位"""
        return self.zero_manager.get_zero_positions()
    
    def set_enabled(self, enabled: bool):
        """设置面板启用状态"""
        self.read_button.setEnabled(enabled)
        self.adjust_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.load_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.go_zero_button.setEnabled(enabled)