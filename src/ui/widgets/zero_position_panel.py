"""
零位录制面板

功能：
- 读取当前位置
- 录制零位
- 零位微调
- 零位管理
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSpinBox, QGroupBox, QComboBox, QLineEdit,
    QTextEdit, QMessageBox, QDialog, QDialogButtonBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

from typing import List, Dict, Optional
import datetime

from core.zero_position_manager import get_zero_position_manager, ZeroPositionSet
from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics, MessagePriority

logger = get_logger(__name__)


class ZeroPositionAdjustDialog(QDialog):
    """零位微调对话框"""
    
    def __init__(self, joint_positions: List[int], joint_names: List[str], parent=None):
        super().__init__(parent)
        
        self.joint_positions = joint_positions.copy()
        self.joint_names = joint_names
        self.adjustment_spinboxes = []
        
        self.setup_ui()
        self.setWindowTitle("零位微调")
        self.setModal(True)
        self.resize(400, 500)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 说明
        info_label = QLabel("对各关节零位进行微调（单位：编码器值）")
        info_label.setStyleSheet("QLabel { color: #666; font-size: 12px; }")
        layout.addWidget(info_label)
        
        # 微调区域
        adjust_group = QGroupBox("零位微调")
        adjust_layout = QGridLayout(adjust_group)
        
        for i, (position, name) in enumerate(zip(self.joint_positions, self.joint_names)):
            # 关节名称
            name_label = QLabel(f"{name}:")
            adjust_layout.addWidget(name_label, i, 0)
            
            # 当前位置
            pos_label = QLabel(f"{position}")
            pos_label.setStyleSheet("QLabel { font-weight: bold; color: #2196F3; }")
            adjust_layout.addWidget(pos_label, i, 1)
            
            # 微调输入
            adjust_spinbox = QSpinBox()
            adjust_spinbox.setRange(-500, 500)
            adjust_spinbox.setValue(0)
            adjust_spinbox.setSuffix(" 单位")
            adjust_spinbox.valueChanged.connect(lambda v, idx=i: self._on_adjustment_changed(idx, v))
            self.adjustment_spinboxes.append(adjust_spinbox)
            adjust_layout.addWidget(adjust_spinbox, i, 2)
            
            # 调整后位置
            result_label = QLabel(f"{position}")
            result_label.setStyleSheet("QLabel { font-weight: bold; color: #4CAF50; }")
            adjust_layout.addWidget(result_label, i, 3)
        
        layout.addWidget(adjust_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _on_adjustment_changed(self, joint_idx: int, adjustment: int):
        """微调值改变"""
        original_pos = self.joint_positions[joint_idx]
        new_pos = original_pos + adjustment
        
        # 更新显示
        result_label = self.layout().itemAt(1).widget().layout().itemAtPosition(joint_idx, 3).widget()
        result_label.setText(f"{new_pos}")
    
    def get_adjusted_positions(self) -> List[int]:
        """获取调整后的位置"""
        adjusted_positions = []
        for i, spinbox in enumerate(self.adjustment_spinboxes):
            original_pos = self.joint_positions[i]
            adjustment = spinbox.value()
            adjusted_positions.append(original_pos + adjustment)
        
        return adjusted_positions


class ZeroPositionPanel(QWidget):
    """零位录制面板"""
    
    # 信号
    zero_position_changed = pyqtSignal(list)  # 零位改变
    move_to_zero_requested = pyqtSignal()     # 请求移动到零位
    read_current_positions_requested = pyqtSignal()  # 请求读取当前位置
    
    def __init__(self, joints_config: List[Dict], parent=None):
        super().__init__(parent)
        
        self.joints_config = joints_config
        self.zero_manager = get_zero_position_manager()
        self.message_bus = get_message_bus()
        
        # 当前位置数据
        self.current_positions = [1500] * 10
        self.joint_names = []
        
        # UI引用
        self.current_val_labels = []
        self.zero_val_labels = []
        self.diff_labels = []
        
        # 提取关节名称
        for joint_config in joints_config:
            self.joint_names.append(joint_config.get('name', f'Joint {joint_config.get("id", 0)}'))
        
        self.setup_ui()
        self.connect_signals()
        self.update_display()
        
        logger.info("零位录制面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        # 设置面板样式
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 12px;
                font-weight: bold;
                background-color: #FAFAFA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #555555;
            }
            QLabel { color: #333333; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 顶部标题栏 + 基础操作
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📍 零位管理配置")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.read_button = QPushButton("读取当前位置")
        self.read_button.setCursor(Qt.PointingHandCursor)
        self.read_button.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        header_layout.addWidget(self.read_button)
        
        self.auto_read_button = QPushButton("自动读取")
        self.auto_read_button.setCheckable(True)
        self.auto_read_button.setCursor(Qt.PointingHandCursor)
        self.auto_read_button.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:checked { background-color: #E65100; }
        """)
        header_layout.addWidget(self.auto_read_button)
        
        layout.addLayout(header_layout)
        
        # --- 状态概览区域 (Grid) ---
        status_group = QGroupBox("关节零位状态监控")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(10)
        
        # 5列 x 2行布局
        for i in range(10):
            row = i // 5
            col = i % 5
            
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #EEEEEE;
                    border-radius: 4px;
                }
            """)
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 8, 8, 8)
            frame_layout.setSpacing(4)
            
            # 关节名
            name_label = QLabel(self.joint_names[i] if i < len(self.joint_names) else f"Joint {i}")
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("font-weight: bold; color: #0078D4; font-size: 11px;")
            frame_layout.addWidget(name_label)
            
            # 分割线
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("color: #EEEEEE;")
            frame_layout.addWidget(line)
            
            # GRID 用于显示数值
            val_grid = QGridLayout()
            val_grid.setContentsMargins(0, 0, 0, 0)
            val_grid.setSpacing(4)
            
            val_grid.addWidget(QLabel("当前:"), 0, 0)
            curr_val = QLabel("1500")
            curr_val.setStyleSheet("font-family: monospace; color: #333;")
            val_grid.addWidget(curr_val, 0, 1)
            self.current_val_labels.append(curr_val)
            
            val_grid.addWidget(QLabel("零位:"), 1, 0)
            zero_val = QLabel("1500")
            zero_val.setStyleSheet("font-family: monospace; color: #666;")
            val_grid.addWidget(zero_val, 1, 1)
            self.zero_val_labels.append(zero_val)
            
            frame_layout.addLayout(val_grid)
            status_layout.addWidget(frame, row, col)
            
        layout.addWidget(status_group)
        
        # --- 操作控制区域 ---
        ops_layout = QHBoxLayout()
        
        # 左侧：录制控制
        record_group = QGroupBox("录制新零位")
        record_layout_inner = QVBoxLayout(record_group)
        
        input_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("零位配置名称")
        self.name_edit.setText(f"零位_{datetime.datetime.now().strftime('%m%d_%H%M')}")
        input_layout.addWidget(self.name_edit)
        
        # 录制按钮区域
        record_buttons_layout = QHBoxLayout()
        
        self.record_current_button = QPushButton("📍 录制机器人位置")
        self.record_current_button.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; padding: 5px 8px; border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.record_current_button.setToolTip("录制机器人当前实际位置为零位")
        record_buttons_layout.addWidget(self.record_current_button)
        
        self.record_zero_button = QPushButton("💾 保存零位设置")
        self.record_zero_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 5px 8px; border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.record_zero_button.setToolTip("保存当前零位设置（包含微调）")
        record_buttons_layout.addWidget(self.record_zero_button)
        
        input_layout.addLayout(record_buttons_layout)
        record_layout_inner.addLayout(input_layout)
        
        self.adjust_button = QPushButton("🛠 微调当前零位数值")
        self.adjust_button.setStyleSheet("color: #555; background: transparent; border: 1px solid #CCC; border-radius: 3px; padding: 4px;")
        record_layout_inner.addWidget(self.adjust_button)
        
        ops_layout.addWidget(record_group, 2) # Stretch factor 2
        
        # 右侧：管理控制
        manage_group = QGroupBox("配置管理")
        manage_layout_inner = QVBoxLayout(manage_group)
        
        set_layout = QHBoxLayout()
        self.zero_set_combo = QComboBox()
        set_layout.addWidget(self.zero_set_combo, 1)
        
        self.load_set_button = QPushButton("加载")
        set_layout.addWidget(self.load_set_button)
        
        self.apply_as_current_button = QPushButton("应用为当前零位")
        self.apply_as_current_button.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.apply_as_current_button.setToolTip("将选中的零位集合应用为当前零位，'全部回零'将使用此零位")
        set_layout.addWidget(self.apply_as_current_button)
        
        self.delete_set_button = QPushButton("删除")
        self.delete_set_button.setStyleSheet("color: #F44336;")
        set_layout.addWidget(self.delete_set_button)
        
        manage_layout_inner.addLayout(set_layout)
        
        self.move_to_zero_button = QPushButton("⏩ 所有关节移动到零位")
        self.move_to_zero_button.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; padding: 6px; border-radius: 3px; font-weight: bold; }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        manage_layout_inner.addWidget(self.move_to_zero_button)
        
        ops_layout.addWidget(manage_group, 3) # Stretch factor 3
        
        layout.addLayout(ops_layout)
        
        # 自动读取定时器
        self.auto_read_timer = QTimer()
        self.auto_read_timer.timeout.connect(self._request_read_positions)
        self.auto_read_timer.setInterval(1000)
    
    def connect_signals(self):
        """连接信号"""
        self.read_button.clicked.connect(self._request_read_positions)
        self.auto_read_button.toggled.connect(self._on_auto_read_toggled)
        self.record_current_button.clicked.connect(self._on_record_current_clicked)
        self.record_zero_button.clicked.connect(self._on_record_zero_clicked)
        self.adjust_button.clicked.connect(self._on_adjust_clicked)
        self.load_set_button.clicked.connect(self._on_load_set_clicked)
        self.apply_as_current_button.clicked.connect(self._on_apply_as_current_clicked)
        self.delete_set_button.clicked.connect(self._on_delete_set_clicked)
        self.move_to_zero_button.clicked.connect(self._on_move_to_zero_clicked)
    
    def _request_read_positions(self):
        """请求读取当前位置"""
        self.read_current_positions_requested.emit()
    
    def _on_auto_read_toggled(self, checked: bool):
        """自动读取切换"""
        if checked:
            self.auto_read_timer.start()
            self.auto_read_button.setText("停止读取")
        else:
            self.auto_read_timer.stop()
            self.auto_read_button.setText("自动读取")
    
    def _on_record_current_clicked(self):
        """录制机器人当前位置按钮点击"""
        name = self.name_edit.text().strip()
        description = "录制机器人当前位置"
        
        if not name:
            QMessageBox.warning(self, "警告", "请输入零位名称")
            return
        
        # 录制机器人当前实际位置
        success = self.zero_manager.record_current_positions(
            self.current_positions, name, description
        )
        
        if success:
            # 更新显示
            self.update_display()
            # 选中新录制的零位集合
            index = self.zero_set_combo.findText(name)
            if index >= 0:
                self.zero_set_combo.setCurrentIndex(index)
            
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            
            # 更新名称
            self.name_edit.setText(f"零位_{datetime.datetime.now().strftime('%m%d_%H%M')}")
            
            QMessageBox.information(
                self, "录制完成", 
                f"已录制机器人当前位置为零位 '{name}'\n"
                f"现在点击'全部回零'将使用此零位"
            )
        else:
            QMessageBox.critical(self, "错误", "零位录制失败")
    
    def _on_record_zero_clicked(self):
        """保存当前零位设置按钮点击"""
        name = self.name_edit.text().strip()
        description = "保存当前零位设置"
        
        if not name:
            QMessageBox.warning(self, "警告", "请输入零位名称")
            return
        
        # 获取当前零位设置（包含微调）
        current_zero_positions = self.zero_manager.get_zero_positions()
        
        # 录制当前零位设置
        success = self.zero_manager.record_current_positions(
            current_zero_positions, name, description
        )
        
        if success:
            # 更新显示
            self.update_display()
            # 选中新录制的零位集合
            index = self.zero_set_combo.findText(name)
            if index >= 0:
                self.zero_set_combo.setCurrentIndex(index)
            
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            
            # 更新名称
            self.name_edit.setText(f"零位_{datetime.datetime.now().strftime('%m%d_%H%M')}")
            
            QMessageBox.information(
                self, "保存完成", 
                f"已保存当前零位设置为 '{name}'\n"
                f"包含所有微调修改\n"
                f"现在点击'全部回零'将使用此零位"
            )
        else:
            QMessageBox.critical(self, "错误", "零位保存失败")
    
    def _on_adjust_clicked(self):
        """微调按钮点击"""
        zero_positions = self.zero_manager.get_zero_positions()
        dialog = ZeroPositionAdjustDialog(zero_positions, self.joint_names, self)
        if dialog.exec_() == QDialog.Accepted:
            adjusted_positions = dialog.get_adjusted_positions()
            
            # 更新每个关节的零位
            for i, position in enumerate(adjusted_positions):
                self.zero_manager.set_zero_position(i, position)
            
            # 重要：如果当前有选中的零位集合，也要更新该集合
            current_set_name = self.zero_set_combo.currentText()
            if current_set_name:
                # 创建新的零位集合来替换当前的
                import datetime
                success = self.zero_manager.record_current_positions(
                    adjusted_positions, 
                    current_set_name, 
                    f"微调后的{current_set_name}"
                )
                if success:
                    logger.info(f"微调后更新零位集合: {current_set_name}")
            
            self.update_display()
            self.zero_position_changed.emit(adjusted_positions)
            QMessageBox.information(self, "成功", "零位微调完成\n新的零位已保存并应用")
        else:
            logger.debug("用户取消了零位微调")
    
    def _on_load_set_clicked(self):
        """加载零位集合"""
        set_name = self.zero_set_combo.currentText()
        if not set_name: 
            return
        
        success = self.zero_manager.load_zero_position_set(set_name)
        if success:
            # 更新显示，但保持当前选中的集合
            self.update_display()
            # 确保下拉框显示正确的选中项
            index = self.zero_set_combo.findText(set_name)
            if index >= 0:
                self.zero_set_combo.setCurrentIndex(index)
            
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            QMessageBox.information(self, "成功", f"零位集合 '{set_name}' 加载成功")
        else:
            QMessageBox.critical(self, "错误", f"零位集合 '{set_name}' 加载失败")
    
    def _on_apply_as_current_clicked(self):
        """应用为当前零位"""
        set_name = self.zero_set_combo.currentText()
        if not set_name:
            QMessageBox.warning(self, "警告", "请先选择一个零位集合")
            return
        
        # 加载选中的零位集合作为当前零位
        success = self.zero_manager.load_zero_position_set(set_name)
        if success:
            self.update_display()
            # 确保下拉框显示正确的选中项
            index = self.zero_set_combo.findText(set_name)
            if index >= 0:
                self.zero_set_combo.setCurrentIndex(index)
            
            self.zero_position_changed.emit(self.zero_manager.get_zero_positions())
            QMessageBox.information(
                self, "成功", 
                f"零位集合 '{set_name}' 已应用为当前零位\n"
                f"现在点击'全部回零'将使用此零位"
            )
        else:
            QMessageBox.critical(self, "错误", f"应用零位集合 '{set_name}' 失败")
    
    def _on_delete_set_clicked(self):
        """删除零位集合"""
        set_name = self.zero_set_combo.currentText()
        if not set_name: return
        
        if QMessageBox.question(self, "确认", f"删除 '{set_name}'?") == QMessageBox.Yes:
            if self.zero_manager.delete_zero_position_set(set_name):
                self.update_display()
                QMessageBox.information(self, "成功", "删除成功")
    
    def _on_move_to_zero_clicked(self):
        """移动到零位"""
        self.move_to_zero_requested.emit()
    
    def update_current_positions(self, positions: List[int]):
        """更新当前位置"""
        self.current_positions = positions[:10]
        # 更新Label显示
        for i, pos in enumerate(self.current_positions):
            if i < len(self.current_val_labels):
                self.current_val_labels[i].setText(str(pos))
                
                # 如果当前位置与零位不同，标记颜色
                zero_pos = int(self.zero_val_labels[i].text())
                if abs(pos - zero_pos) > 5:
                    self.current_val_labels[i].setStyleSheet("font-family: monospace; color: #D83B01; font-weight: bold;")
                else:
                    self.current_val_labels[i].setStyleSheet("font-family: monospace; color: #107C10;")
    
    def update_display(self):
        """更新显示"""
        # 保存当前选中的项
        current_selection = self.zero_set_combo.currentText()
        
        # 更新Combo
        self.zero_set_combo.clear()
        zero_sets = self.zero_manager.get_zero_position_sets()
        
        logger.debug(f"更新显示: 找到 {len(zero_sets)} 个零位集合")
        
        for set_name in zero_sets.keys():
            self.zero_set_combo.addItem(set_name)
            logger.debug(f"添加零位集合到下拉框: {set_name}")
        
        # 恢复选中项（如果还存在的话）
        if current_selection:
            index = self.zero_set_combo.findText(current_selection)
            if index >= 0:
                self.zero_set_combo.setCurrentIndex(index)
                logger.debug(f"恢复选中项: {current_selection} (索引: {index})")
            else:
                logger.debug(f"未找到之前选中的项: {current_selection}")
            
        # 更新零位Label
        zero_positions = self.zero_manager.get_zero_positions()
        for i, pos in enumerate(zero_positions):
            if i < len(self.zero_val_labels):
                self.zero_val_labels[i].setText(str(pos))
        
        # 刷新对比状态
        self.update_current_positions(self.current_positions)
        
        logger.debug(f"显示更新完成，当前选中: {self.zero_set_combo.currentText()}")
    
    def get_zero_positions(self) -> List[int]:
        return self.zero_manager.get_zero_positions()
    
    def set_enabled(self, enabled: bool):
        self.read_button.setEnabled(enabled)
        self.record_current_button.setEnabled(enabled)
        self.record_zero_button.setEnabled(enabled)
        self.adjust_button.setEnabled(enabled)
        self.load_set_button.setEnabled(enabled)
        self.apply_as_current_button.setEnabled(enabled)
        self.delete_set_button.setEnabled(enabled)
        self.move_to_zero_button.setEnabled(enabled)