"""
优化的关节控制面板

功能：
- 10个关节的独立控制
- 紧凑型布局设计
- 实时状态显示
- 电流监控和警告
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSlider, QSpinBox, QProgressBar, QGroupBox,
    QScrollArea, QFrame, QSplitter, QTabWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
from typing import List, Dict, Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class CompactJointWidget(QFrame):
    """紧凑型关节控制控件 (Card Style)"""
    
    # 信号定义
    position_changed = pyqtSignal(int, int)  # joint_id, position
    move_requested = pyqtSignal(int, int)    # joint_id, position
    
    def __init__(self, joint_id: int, joint_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.joint_id = joint_id
        self.joint_config = joint_config
        
        # 关节参数
        joint_names = ["拇指", "食指", "中指", "无名指", "小指 (Pinky)", "手腕 (Wrist)", "肩部1 (S1)", "肩部2 (S2)", "肘部1 (E1)", "肘部2 (E2)"]
        self.joint_name = joint_names[joint_id] if joint_id < len(joint_names) else f'关节{joint_id}'
        self.min_position = joint_config.get('limits', {}).get('min_position', 0)
        self.max_position = joint_config.get('limits', {}).get('max_position', 3000)
        self.max_velocity = joint_config.get('limits', {}).get('max_velocity', 100)
        self.max_current = joint_config.get('limits', {}).get('max_current', 1000)
        
        # 当前状态
        self.current_position = 1500
        self.current_velocity = 0.0
        self.current_current = 0
        self.target_position = 1500
        
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """设置用户界面"""
        # Card 样式
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            CompactJointWidget {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                border-bottom: 2px solid #D0D0D0;
            }
            QLabel {
                color: #333333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # 减小边距
        layout.setSpacing(5) # 减小间距
        
        # 顶部：名称 + 状态 + 当前值
        header_layout = QHBoxLayout()
        
        name_label = QLabel(self.joint_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #0078D4;")
        header_layout.addWidget(name_label)
        
        # 状态指示器 - 防止拉伸并垂直居中
        self.status_indicator = QLabel("就绪")
        self.status_indicator.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.status_indicator.setStyleSheet("color: #107C10; font-size: 10px; background: #E6F4EA; padding: 2px 6px; border-radius: 4px;")
        header_layout.addWidget(self.status_indicator)
        
        header_layout.addStretch()
        
        self.current_pos_label = QLabel("1500")
        self.current_pos_label.setStyleSheet("font-family: monospace; font-weight: bold; color: #333333;")
        header_layout.addWidget(self.current_pos_label)
        
        layout.addLayout(header_layout)
        
        # 中部：滑块
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(self.min_position, self.max_position)
        self.position_slider.setValue(1500)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #D0D0D0;
                height: 6px;
                background: #F3F3F3;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                border: 1px solid #0078D4;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1084D9;
            }
            QSlider::sub-page:horizontal {
                background: #0078D4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.position_slider)
        
        # 底部：控制 + 监控
        bottom_layout = QHBoxLayout()
        
        # 输入框
        self.position_spinbox = QSpinBox()
        self.position_spinbox.setRange(self.min_position, self.max_position)
        self.position_spinbox.setValue(1500)
        self.position_spinbox.setButtonSymbols(QSpinBox.NoButtons) # 极简风格
        self.position_spinbox.setFixedWidth(50)
        self.position_spinbox.setAlignment(Qt.AlignCenter)
        self.position_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
            }
        """)
        bottom_layout.addWidget(self.position_spinbox)
        
        # 移动按钮 - 回归文字，调整尺寸
        self.move_button = QPushButton("移动")
        self.move_button.setFixedSize(48, 26) # 宽度适中
        self.move_button.setCursor(Qt.PointingHandCursor)
        self.move_button.setToolTip("执行移动")
        self.move_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px; /* 字体适中 */
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover { background-color: #1084D9; }
            QPushButton:pressed { background-color: #006CC1; }
        """)
        bottom_layout.addWidget(self.move_button)
        
        bottom_layout.addStretch()
        
        # 电流监控条 (用户提到的横条)
        status_layout = QVBoxLayout()
        status_layout.setSpacing(1)
        
        # 添加 Current 标签 tooltip
        self.current_label = QLabel("0mA")
        self.current_label.setAlignment(Qt.AlignRight)
        self.current_label.setToolTip("实时电流监控")
        self.current_label.setStyleSheet("font-size: 9px; color: #999999;")
        status_layout.addWidget(self.current_label)
        
        self.current_progressbar = QProgressBar()
        self.current_progressbar.setMaximum(self.max_current)
        self.current_progressbar.setValue(0)
        self.current_progressbar.setTextVisible(False)
        self.current_progressbar.setFixedSize(50, 4)
        self.current_progressbar.setToolTip("电机电流负载") # 添加说明
        self.current_progressbar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #E0E0E0;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #107C10;
                border-radius: 2px;
            }
        """)
        status_layout.addWidget(self.current_progressbar)
        
        bottom_layout.addLayout(status_layout)
        
        layout.addLayout(bottom_layout)

    def connect_signals(self):
        self.position_slider.valueChanged.connect(self._on_slider_changed)
        self.position_spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.move_button.clicked.connect(self._on_move_clicked)
    
    def _on_slider_changed(self, value: int):
        self.position_spinbox.setValue(value)
        self.target_position = value
        self.position_changed.emit(self.joint_id, value)
    
    def _on_spinbox_changed(self, value: int):
        self.position_slider.setValue(value)
        self.target_position = value
        self.position_changed.emit(self.joint_id, value)
    
    def _on_move_clicked(self):
        self.move_requested.emit(self.joint_id, self.target_position)
    
    def update_current_position(self, position: int):
        """更新当前位置显示（不改变滑块）"""
        self.current_position = position
        self.current_pos_label.setText(str(position))
    
    def update_status(self, position: int, velocity: float, current: int):
        self.current_position = position
        self.current_velocity = velocity
        self.current_current = current
        
        self.current_pos_label.setText(str(position))
        self.current_label.setText(f"{current}mA")
        self.current_progressbar.setValue(min(current, self.max_current))
        
        # Warning colors
        if current > self.max_current * 0.8:
            self.current_progressbar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }") # Red
        elif current > self.max_current * 0.6:
            self.current_progressbar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }") # Orange
        else:
            self.current_progressbar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }") # Green
            
    def set_target_position(self, position: int):
        self.target_position = position
        self.position_slider.setValue(position)


class OptimizedJointControlPanel(QWidget):
    """优化的关节控制面板"""
    
    # 信号定义
    joint_move_requested = pyqtSignal(int, int)      # joint_id, position
    all_joints_move_requested = pyqtSignal(list)    # positions
    
    def __init__(self, joints_config: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.joints_config = joints_config
        self.joint_count = 10
        
        self.joint_widgets: List[CompactJointWidget] = []
        self.current_positions = [1500] * self.joint_count
        
        self.setup_ui()
        self.connect_signals()
        
        # 状态更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # --- 全局控制栏 (Top Bar) ---
        global_group = QFrame()
        global_group.setProperty("class", "panel")
        global_group.setStyleSheet("""
            .QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        global_layout = QHBoxLayout(global_group)
        global_layout.setContentsMargins(10, 10, 10, 10)
        
        # 按钮
        self.home_button = QPushButton("⌂ 全部回零")
        self.home_button.setProperty("class", "accent") 
        self.home_button.setFixedSize(100, 32)
        global_layout.addWidget(self.home_button)
        
        self.move_all_button = QPushButton("▶ 执行同步")
        self.move_all_button.setProperty("class", "success")
        self.move_all_button.setFixedSize(100, 32)
        global_layout.addWidget(self.move_all_button)
        
        self.stop_button = QPushButton("⏹ 全部停止")
        self.stop_button.setProperty("class", "danger")
        self.stop_button.setFixedSize(100, 32)
        global_layout.addWidget(self.stop_button)
        
        self.zero_record_button = QPushButton("📍 零位录制")
        self.zero_record_button.setProperty("class", "special")
        self.zero_record_button.setFixedSize(100, 32)
        self.zero_record_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
        """)
        global_layout.addWidget(self.zero_record_button)
        
        global_layout.addSpacing(20)
        
        # 预设
        global_layout.addWidget(QLabel("快捷指令:"))
        
        presets = [
            ("预设 A", [2000, 2000, 2000, 2000, 2000, 1500, 1500, 1500, 1500, 1500]),
            ("预设 B", [1000, 1000, 1000, 1000, 1000, 2000, 2000, 2000, 2000, 2000]),
            ("张开手", [2500, 2500, 2500, 2500, 2500, 1500, 1500, 1500, 1500, 1500]),
            ("握拳",   [500, 500, 500, 500, 500, 1500, 1500, 1500, 1500, 1500])
        ]
        
        for name, pos in presets:
            btn = QPushButton(name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #F3F3F3;
                    border: 1px solid #D0D0D0;
                    color: #333333;
                    padding: 5px 10px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #E0E0E0; }
            """)
            btn.clicked.connect(lambda checked, p=pos: self.load_preset(p))
            global_layout.addWidget(btn)
            
        global_layout.addStretch()
        layout.addWidget(global_group)
        
        # --- 关节网格区域 ---
        # 使用 ScrollArea 防止窗口过小时无法显示
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        # 设置滚动条样式，防止出现黑色方块
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #F0F0F0;
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A0A0A0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            QScrollBar:horizontal {
                border: none;
                background: #F0F0F0;
                height: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #C0C0C0;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #A0A0A0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(10) # 减小卡片间距
        
        # 布局：5列 x 2行
        for i in range(self.joint_count):
            joint_config = self.joints_config[i] if i < len(self.joints_config) else {}
            joint_widget = CompactJointWidget(i, joint_config)
            joint_widget.position_changed.connect(self.on_joint_position_changed)
            joint_widget.move_requested.connect(self.on_joint_move_requested)
            
            row = i // 5
            col = i % 5
            scroll_layout.addWidget(joint_widget, row, col)
            self.joint_widgets.append(joint_widget)
            
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # --- 零位录制面板 ---
        from ui.widgets.simple_zero_panel import SimpleZeroPositionPanel
        self.zero_position_panel = SimpleZeroPositionPanel(self.joints_config)
        self.zero_position_panel.setVisible(False)  # 默认隐藏
        layout.addWidget(self.zero_position_panel)
    
    def load_preset(self, positions: List[int]):
        self.set_all_target_positions(positions)
        self.update_overall_status("预设已加载")
        logger.info(f"加载预设位置: {positions}")
    
    def connect_signals(self):
        self.home_button.clicked.connect(self.move_all_to_home)
        self.stop_button.clicked.connect(self.stop_all_motion)
        self.move_all_button.clicked.connect(self.move_all_joints)
        self.zero_record_button.clicked.connect(self.toggle_zero_record_panel)
        
        # 连接零位面板信号
        self.zero_position_panel.zero_position_changed.connect(self.on_zero_position_changed)
        self.zero_position_panel.move_to_zero_requested.connect(self.on_move_to_zero_requested)
        self.zero_position_panel.read_current_positions_requested.connect(self.on_read_current_positions_requested)
    
    def update_joint_position(self, joint_id: int, position: int):
        """更新指定关节的当前位置显示"""
        try:
            if 0 <= joint_id < len(self.joint_widgets):
                joint_widget = self.joint_widgets[joint_id]
                joint_widget.update_current_position(position)
                self.current_positions[joint_id] = position
                logger.debug(f"更新关节{joint_id}位置: {position}")
        except Exception as e:
            logger.error(f"更新关节{joint_id}位置失败: {e}")
    
    def update_joint_status(self, joint_id: int, position: int, velocity: int, current: int):
        """更新指定关节的完整状态"""
        try:
            if 0 <= joint_id < len(self.joint_widgets):
                joint_widget = self.joint_widgets[joint_id]
                joint_widget.update_status(position, velocity, current)
                self.current_positions[joint_id] = position
                logger.debug(f"更新关节{joint_id}状态: 位置={position}, 速度={velocity}, 电流={current}")
        except Exception as e:
            logger.error(f"更新关节{joint_id}状态失败: {e}")
    
    def on_joint_position_changed(self, joint_id: int, position: int):
        if 0 <= joint_id < self.joint_count:
            self.current_positions[joint_id] = position
            self.update_position_display()
    
    def on_joint_move_requested(self, joint_id: int, position: int):
        self.joint_move_requested.emit(joint_id, position)
    
    def move_all_to_home(self):
        # 使用零位管理器的零位
        from core.zero_position_manager import get_zero_position_manager
        zero_manager = get_zero_position_manager()
        home_positions = zero_manager.get_zero_positions()
        
        self.set_all_target_positions(home_positions)
        self.all_joints_move_requested.emit(home_positions)
        self.update_overall_status("正在回零...")
    
    def toggle_zero_record_panel(self):
        """切换零位录制面板显示状态"""
        is_visible = self.zero_position_panel.isVisible()
        self.zero_position_panel.setVisible(not is_visible)
        
        # 更新按钮文本和样式
        if not is_visible:
            self.zero_record_button.setText("📍 隐藏录制")
            self.zero_record_button.setStyleSheet("""
                QPushButton {
                    background-color: #607D8B;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #546E7A;
                }
                QPushButton:pressed {
                    background-color: #455A64;
                }
            """)
        else:
            self.zero_record_button.setText("📍 零位录制")
            self.zero_record_button.setStyleSheet("""
                QPushButton {
                    background-color: #9C27B0;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7B1FA2;
                }
                QPushButton:pressed {
                    background-color: #6A1B9A;
                }
            """)
    
    def on_zero_position_changed(self, zero_positions: list):
        """零位改变"""
        logger.info(f"零位已更新: {zero_positions}")
    
    def on_move_to_zero_requested(self):
        """请求移动到零位"""
        from core.zero_position_manager import get_zero_position_manager
        zero_manager = get_zero_position_manager()
        zero_positions = zero_manager.get_zero_positions()
        
        self.set_all_target_positions(zero_positions)
        self.all_joints_move_requested.emit(zero_positions)
        self.update_overall_status("移动到零位...")
    
    def on_read_current_positions_requested(self):
        """请求读取当前位置"""
        # 获取当前关节位置并更新零位面板
        current_positions = []
        for i in range(self.joint_count):
            if i < len(self.joint_widgets):
                current_positions.append(self.joint_widgets[i].current_position)
            else:
                current_positions.append(1500)
        
        self.zero_position_panel.update_current_positions(current_positions)
    
    def stop_all_motion(self):
        self.update_overall_status("已停止所有运动")
    
    def move_all_joints(self):
        target_positions = [w.target_position for w in self.joint_widgets]
        self.all_joints_move_requested.emit(target_positions)
        self.update_overall_status("多关节同步运动中...")
    
    def set_all_target_positions(self, positions: List[int]):
        for i, position in enumerate(positions):
            if i < len(self.joint_widgets):
                self.joint_widgets[i].set_target_position(position)
    
    def update_all_joints_status(self, positions: List[int], velocities: List[float], currents: List[int]):
        for i in range(min(len(positions), len(self.joint_widgets))):
            p = positions[i] if i < len(positions) else 0
            v = velocities[i] if i < len(velocities) else 0.0
            c = currents[i] if i < len(currents) else 0
            self.joint_widgets[i].update_status(p, v, c)
        
        self.current_positions = positions.copy()
        self.update_position_display()
    
    def update_position_display(self):
        pos_str = "[" + ", ".join(f"{pos}" for pos in self.current_positions) + "]"
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'position_display_label'):
            self.main_window.position_display_label.setText(f" Pos: {pos_str} ")
    
    def update_overall_status(self, status_text: str):
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'overall_status_label'):
            self.main_window.overall_status_label.setText(f" {status_text} ")
    
    def update_display(self):
        pass