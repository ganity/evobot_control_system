"""
主窗口

功能：
- 应用程序主界面
- 串口连接管理
- 状态显示和监控
- 菜单和工具栏
- 各功能模块的容器
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QTabWidget,
    QStatusBar, QMenuBar, QToolBar, QAction, QMessageBox,
    QGroupBox, QProgressBar, QSplitter, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

from typing import Optional, Dict, Any
import time

from hardware.serial_manager import SerialManager, SerialConfig, ConnectionState, get_serial_manager
from hardware.protocol_handler import ProtocolHandler, get_protocol_handler
from hardware.device_monitor import DeviceMonitor, create_device_monitor, Alert, HealthStatus
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics, Message, MessagePriority

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """主窗口类"""
    
    # 信号定义
    connection_changed = pyqtSignal(str)  # 连接状态变化
    status_updated = pyqtSignal(dict)     # 状态更新
    alert_received = pyqtSignal(object)   # 告警接收
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        
        self.config_manager = config_manager
        self.config = config_manager.load_config()
        
        # 硬件组件
        self.serial_manager = get_serial_manager()
        self.protocol_handler = get_protocol_handler()
        self.device_monitor: Optional[DeviceMonitor] = None
        
        # 运动控制组件
        from core.motion_controller import get_motion_controller, ControlMode
        self.motion_controller = get_motion_controller()
        self.ControlMode = ControlMode
        
        # UI组件引用
        self.central_widget: Optional[QWidget] = None
        self.status_bar: Optional[QStatusBar] = None
        self.connection_status_label: Optional[QLabel] = None
        self.port_combo: Optional[QComboBox] = None
        self.connect_button: Optional[QPushButton] = None
        self.log_text: Optional[QTextEdit] = None
        
        # 定时器
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self.update_ui)
        
        # 消息总线
        self.message_bus = get_message_bus()
        
        # 初始化UI
        self.init_ui()
        self.setup_connections()
        self.setup_message_handlers()
        
        # 启动UI更新定时器
        update_frequency = self.config.get('ui', {}).get('update_frequency', 50)
        self.ui_update_timer.start(1000 // update_frequency)
        
        logger.info("主窗口初始化完成")
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("EvoBot 智能控制中心")
        self.setMinimumSize(820, 600) # 减小最小尺寸限制，允许用户自由调整
        
        # 应用全局深色主题
        self.apply_theme()
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_tool_bar()
        
        # 创建中央部件
        self.create_central_widget()
        
        # 创建状态栏
        self.create_status_bar()
    
    def apply_theme(self):
        """应用现代明亮主题样式"""
        # 定义颜色变量
        light_bg = "#F9F9F9"       # 整体背景 - 极浅灰/白
        panel_bg = "#FFFFFF"       # 面板背景 - 纯白
        border_color = "#E5E5E5"   # 边框颜色 - 浅灰
        accent_blue = "#0078D4"    # 强调色 - 科技蓝
        accent_hover = "#1084D9"   # 强调色悬停
        text_primary = "#333333"   # 主要文本 - 深灰/黑
        text_secondary = "#666666" # 次要文本 - 中灰
        success_green = "#107C10"  # 成功色 - 深绿
        warning_orange = "#D83B01" # 警告色 - 深橙
        danger_red = "#E81123"     # 危险色 - 红
        status_bar_bg = "#F3F3F3"  # 状态栏背景 - 浅灰

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {light_bg};
                color: {text_primary};
            }}
            QWidget {{
                background-color: {light_bg};
                color: {text_primary};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }}
            
            /* 菜单栏 */
            QMenuBar {{
                background-color: {panel_bg};
                border-bottom: 1px solid {border_color};
            }}
            QMenuBar::item {{
                padding: 8px 12px;
                background: transparent;
                color: {text_primary};
            }}
            QMenuBar::item:selected {{
                background-color: {border_color};
            }}
            QMenu {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
            }}
            QMenu::item {{
                color: {text_primary};
                padding: 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {accent_blue};
                color: white;
            }}
            
            /* 工具栏 */
            QToolBar {{
                background-color: {panel_bg};
                border-bottom: 1px solid {border_color};
                padding: 6px;
                spacing: 12px;
            }}
            QToolBar QLabel {{
                color: {text_secondary};
                font-weight: 600;
            }}
            
            /* 组合框 - 恢复系统箭头以保证显示 */
            QComboBox {{
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px;
                min-width: 80px;
                background-color: {panel_bg};
                color: {text_primary};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            /* 下拉列表弹窗样式 - 解决Windows下部分系统可能出现的黑底问题 */
            QComboBox QAbstractItemView {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
                selection-background-color: {accent_blue};
                selection-color: white;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 8px;
                background-color: {panel_bg};
                color: {text_primary};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent_blue};
                color: white;
            }}
            
            /* 按钮通用样式 */
            QPushButton {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px 16px;
                color: {text_primary};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
            }}
            QPushButton:pressed {{
                background-color: #E0E0E0;
            }}
            
            /* 强调按钮 */
            QPushButton[class="accent"] {{
                background-color: {accent_blue};
                color: white;
                border: 1px solid {accent_blue};
            }}
            QPushButton[class="accent"]:hover {{
                background-color: {accent_hover};
            }}
            
            /* 危险按钮 */
            QPushButton[class="danger"] {{
                background-color: {danger_red};
                color: white;
                border: 1px solid {danger_red};
            }}
            QPushButton[class="danger"]:hover {{
                background-color: #C50F1F;
            }}
            
            /* 成功按钮 */
            QPushButton[class="success"] {{
                background-color: {success_green};
                color: white;
                border: 1px solid {success_green};
            }}
            
            /* TabWidget */
            QTabWidget::pane {{
                border: 1px solid {border_color};
                background-color: {panel_bg};
                border-radius: 4px;
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background-color: {light_bg};
                color: {text_secondary};
                border: 1px solid {border_color};
                border-bottom: 1px solid {border_color};
                padding: 8px 20px;
                margin-right: -1px; /* Overlap for continuous border look */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {panel_bg};
                color: {accent_blue};
                border-bottom: 1px solid {panel_bg}; /* Merge with pane */
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #F0F0F0;
            }}
            
            /* 状态栏 - 改为浅色中性色 */
            QStatusBar {{
                background-color: {status_bar_bg};
                color: {text_primary};
                border-top: 1px solid {border_color};
            }}
            QStatusBar QLabel {{
                color: {text_primary};
            }}
            
            /* 文本框 */
            QTextEdit {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
                color: {text_primary};
                font-family: 'Consolas', monospace;
            }}
            
            /* 分组框 */
            QGroupBox {{
                border: 1px solid {border_color};
                border-radius: 6px;
                margin-top: 1.2em; /* Leave space for title */
                padding: 15px 10px 10px 10px;
                font-weight: bold;
                color: {text_primary};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: {accent_blue};
            }}
            
            /* 滚动条 */
            QScrollBar:vertical {{
                border: none;
                background: {light_bg};
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #CDCDCD;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #A6A6A6;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        exit_action = QAction('退出系统', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        # 可以添加显示/隐藏工具栏等选项
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        about_action = QAction('关于 EvoBot', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tool_bar(self):
        """创建现代化的工具栏"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        
        # --- 连接控制组 ---
        
        # 端口选择
        toolbar.addWidget(QLabel(" 端口 "))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        toolbar.addWidget(self.port_combo)
        
        # 刷新按钮 (回归文字以确保显示)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedSize(60, 30) # 加宽以防截断
        refresh_btn.setToolTip("刷新串口列表")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                color: #333333;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F0F0F0; }
        """)
        refresh_btn.clicked.connect(self.refresh_ports)
        toolbar.addWidget(refresh_btn)
        
        # 连接按钮
        self.connect_button = QPushButton("连接设备")
        self.connect_button.setProperty("class", "success") # 初始样式
        self.connect_button.setCursor(Qt.PointingHandCursor)
        self.connect_button.clicked.connect(self.toggle_connection)
        toolbar.addWidget(self.connect_button)
        
        # 分隔线
        self.add_toolbar_spacer(toolbar)
        
        # --- 模式控制组 ---
        
        toolbar.addWidget(QLabel(" 控制模式 "))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["手动控制", "轨迹控制", "示教模式", "脚本模式"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        toolbar.addWidget(self.mode_combo)
        
        self.current_mode_label = QLabel(" ⚪ 待机 ")
        self.current_mode_label.setStyleSheet("color: #858585; margin-left: 10px;")
        toolbar.addWidget(self.current_mode_label)
        
        # 分隔线
        self.add_toolbar_spacer(toolbar)
        
        # --- 关键操作组 ---
        
        # 回零
        home_btn = QPushButton("⌂ 回零")
        home_btn.setProperty("class", "accent")
        home_btn.clicked.connect(self.go_home)
        toolbar.addWidget(home_btn)
        
        # 急停 (靠右)
        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(empty)
        
        emergency_btn = QPushButton("STOP 急停")
        emergency_btn.setProperty("class", "danger")
        emergency_btn.setFixedSize(100, 32)
        emergency_btn.clicked.connect(self.emergency_stop)
        toolbar.addWidget(emergency_btn)

    def add_toolbar_spacer(self, toolbar):
        """添加工具栏分隔符"""
        line = QFrame()
        line.setFrameShape(QFrame.NoFrame)
        line.setFixedWidth(1)
        line.setFixedHeight(16) # 稍微调更短一点
        line.setStyleSheet("background-color: #CCCCCC; margin: 0 10px;") # 明显的灰色
        toolbar.addWidget(line)

    def create_central_widget(self):
        """创建中央内容区域"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.main_tab_widget = QTabWidget()
        layout.addWidget(self.main_tab_widget)
        
        # 添加各个功能选项卡
        self.main_tab_widget.addTab(self.create_joint_control_tab(), "🎮 关节控制")
        self.main_tab_widget.addTab(self.create_monitor_tab(), "📈 数据监控")
        self.main_tab_widget.addTab(self.create_teaching_tab(), "🎓 示教模式")
        self.main_tab_widget.addTab(self.create_script_tab(), "📜 脚本运行")
        self.main_tab_widget.addTab(self.create_velocity_tab(), "⚡ 速度控制")
        self.main_tab_widget.addTab(self.create_recording_tab(), "📹 数据录制")
        self.main_tab_widget.addTab(self.create_settings_tab(), "🔧 参数设置")
        self.main_tab_widget.addTab(self.create_log_tab(), "📝 系统日志")

    # --- Tab Creation Helper Methods ---
    # These instantiate the optimized widgets. We will need to update those widgets
    # to respect the parent theme or manually update their styles.

    def create_joint_control_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        from ui.widgets.joint_control_panel_v2 import OptimizedJointControlPanel
        joints_config = self.config.get('joints', [])
        self.joint_control_panel = OptimizedJointControlPanel(joints_config)
        self.joint_control_panel.joint_move_requested.connect(self.on_joint_move_requested)
        self.joint_control_panel.all_joints_move_requested.connect(self.on_all_joints_move_requested)
        self.joint_control_panel.main_window = self
        layout.addWidget(self.joint_control_panel)
        return tab

    def create_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.data_visualization import DataVisualizationPanel
        self.data_viz_panel = DataVisualizationPanel()
        layout.addWidget(self.data_viz_panel)
        return tab

    def create_teaching_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.teaching_panel import TeachingPanel
        self.teaching_panel = TeachingPanel()
        layout.addWidget(self.teaching_panel)
        return tab

    def create_script_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.script_panel import ScriptPanel
        self.script_panel = ScriptPanel()
        layout.addWidget(self.script_panel)
        return tab

    def create_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.parameter_tuning_panel import ParameterTuningPanel
        self.parameter_tuning_panel = ParameterTuningPanel()
        layout.addWidget(self.parameter_tuning_panel)
        return tab

    def create_recording_tab(self) -> QWidget:
        """创建数据录制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.recording_panel import RecordingPanel
        self.recording_panel = RecordingPanel()
        layout.addWidget(self.recording_panel)
        return tab

    def create_velocity_tab(self) -> QWidget:
        """创建速度控制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        from ui.widgets.velocity_panel import VelocityPanel
        self.velocity_panel = VelocityPanel()
        layout.addWidget(self.velocity_panel)
        return tab

    def create_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        clear_btn = QPushButton("清除日志")
        clear_btn.clicked.connect(self.clear_log)
        ctrl_layout.addWidget(clear_btn)
        ctrl_layout.addStretch()
        
        # Log View
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #3E3E42;
                background-color: #121212;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        layout.addLayout(ctrl_layout)
        layout.addWidget(self.log_text)
        return tab

    def create_status_bar(self):
        """创建底部状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 左侧及主状态
        self.overall_status_label = QLabel(" 系统就绪 ")
        self.overall_status_label.setStyleSheet("font-weight: bold;")
        self.status_bar.addWidget(self.overall_status_label)
        
        # 实时位置信息
        self.position_display_label = QLabel(" Pos: Ready ")
        self.position_display_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.status_bar.addPermanentWidget(self.position_display_label)
        
        # 提示信息
        version_label = QLabel("v1.0.0 ")
        version_label.setStyleSheet("opacity: 0.7;")
        self.status_bar.addPermanentWidget(version_label)

    # --- Logic Methods (Kept largely the same but cleaned up) ---

    def setup_connections(self):
        self.serial_manager.set_connection_changed_callback(self.on_connection_changed)
        self.connection_changed.connect(self.update_connection_status)
        self.status_updated.connect(self.update_system_status)
        self.alert_received.connect(self.handle_alert)
        self.refresh_ports()
    
    def setup_message_handlers(self):
        self.message_bus.subscribe(Topics.ROBOT_CONNECTED, self.on_robot_connected)
        self.message_bus.subscribe(Topics.ROBOT_DISCONNECTED, self.on_robot_disconnected)
        self.message_bus.subscribe(Topics.ROBOT_ERROR, self.on_robot_error)
        self.message_bus.subscribe(Topics.ROBOT_STATE, self.on_robot_state_update)
        self.message_bus.subscribe(Topics.MOTION_STOP, self.on_motion_stop)
        self.message_bus.subscribe(Topics.TRAJECTORY_STARTED, self.on_trajectory_started)
        self.message_bus.subscribe(Topics.TRAJECTORY_COMPLETED, self.on_trajectory_completed)

    def refresh_ports(self):
        try:
            ports = SerialManager.scan_ports()
            self.port_combo.clear()
            for port_info in ports:
                self.port_combo.addItem(f"{port_info['device']} ({port_info['description']})", port_info['device'])
            if not ports:
                self.port_combo.addItem("无可用设备", "")
            self.log_message(f"扫描完成: 发现 {len(ports)} 个设备")
        except Exception as e:
            self.log_message(f"扫描失败: {str(e)}", "ERROR")

    def toggle_connection(self):
        if self.serial_manager.is_connected():
            self.disconnect_device()
        else:
            self.connect_device()

    def connect_device(self):
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "连接错误", "请选择一个有效的端口")
            return
            
        baudrate = self.config.get('communication', {}).get('serial', {}).get('baudrate', 1000000)
        try:
            self.serial_manager.config = SerialConfig(port=port, baudrate=baudrate)
            
            # 设置数据接收回调
            self.serial_manager.set_data_received_callback(self.on_data_received)
            
            if self.serial_manager.connect():
                if not self.device_monitor:
                    self.device_monitor = create_device_monitor(self.serial_manager, self.protocol_handler)
                    self.device_monitor.set_alert_callback(self.on_alert_received)
                    self.device_monitor.set_status_callback(self.on_status_updated)
                self.device_monitor.start()
                self.log_message(f"已连接到 {port}")
            else:
                self.log_message(f"连接失败: {port}", "ERROR")
        except Exception as e:
            self.log_message(f"连接异常: {e}", "ERROR")
            QMessageBox.critical(self, "错误", str(e))

    def disconnect_device(self):
        try:
            if self.device_monitor:
                self.device_monitor.stop()
            self.serial_manager.disconnect()
            self.log_message("设备已断开")
        except Exception as e:
            self.log_message(f"断开异常: {e}", "ERROR")

    def go_home(self):
        try:
            if self.motion_controller.move_to_position([1500]*10):
                self.log_message("执行回零操作...")
            else:
                self.log_message("回零指令发送失败", "ERROR")
        except Exception as e:
            self.log_message(f"回零异常: {e}", "ERROR")

    def emergency_stop(self):
        try:
            self.message_bus.publish(Topics.EMERGENCY_STOP, time.time(), priority=MessagePriority.CRITICAL)
            self.log_message("!!! 紧急停止触发 !!!", "CRITICAL")
            QMessageBox.warning(self, "急停", "紧急停止已触发！系统已锁定。")
        except Exception as e:
            self.log_message(f"急停异常: {e}", "ERROR")

    def clear_log(self):
        if self.log_text:
            self.log_text.clear()

    def log_message(self, message: str, level: str = "INFO"):
        if not self.log_text: return
        
        timestamp = time.strftime("%H:%M:%S")
        color_map = {
            "INFO": "#333333",
            "WARNING": "#D83B01",
            "ERROR": "#E81123",
            "CRITICAL": "#FF0000"
        }
        color = color_map.get(level, "#333333")
        self.log_text.append(f'<font color="{color}">[{timestamp}] {level}: {message}</font>')

    # --- Event Handlers ---
    
    def on_connection_changed(self, state: ConnectionState):
        self.connection_changed.emit(state.value)

    def update_connection_status(self, status: str):
        if status == "connected":
            self.connect_button.setText("断开连接")
            self.connect_button.setProperty("class", "danger")
            self.port_combo.setEnabled(False)
            self.overall_status_label.setText(" 系统在线 ")
        else:
            self.connect_button.setText("连接设备")
            self.connect_button.setProperty("class", "success")
            self.port_combo.setEnabled(True)
            self.overall_status_label.setText(" 等待连接 ")
        
        # 刷新样式
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)

    def on_alert_received(self, alert: Alert):
        self.alert_received.emit(alert)

    def handle_alert(self, alert: Alert):
        self.log_message(f"{alert.message}", "WARNING" if alert.level == "warning" else "ERROR")
        self.status_bar.showMessage(f"警告: {alert.message}", 5000)

    def on_status_updated(self, status: Dict[str, Any]):
        self.status_updated.emit(status)

    def on_data_received(self, data: bytes):
        """处理接收到的串口数据"""
        try:
            # 使用协议处理器解析数据
            parsed_frames = self.protocol_handler.parse_received_data(data)
            for frame_data in parsed_frames:
                # 发布到消息总线供其他组件处理
                self.message_bus.publish(
                    Topics.ROBOT_STATE, 
                    frame_data, 
                    MessagePriority.NORMAL
                )
        except Exception as e:
            logger.error(f"数据处理错误: {e}")
            self.log_message(f"数据处理错误: {e}", "ERROR")

    def update_system_status(self, status: dict):
        pass # Handle detailed status updates if needed

    def on_mode_changed(self, mode_text):
        self.current_mode_label.setText(f" 🟢 模式: {mode_text} ")
        # Notify controller if needed
        
    def on_joint_move_requested(self, joint_id, pos):
        self.motion_controller.move_joint(joint_id, pos)
    
    def on_all_joints_move_requested(self, positions):
        self.motion_controller.move_to_position(positions)

    def on_robot_connected(self, _): 
        pass
    def on_robot_disconnected(self, _): 
        pass
    def on_robot_error(self, msg: Message):
        self.log_message(f"机器人错误: {msg.data}", "ERROR")
    def on_robot_state_update(self, msg: Message):
        """处理机器人状态更新"""
        try:
            data = msg.data
            if isinstance(data, dict) and 'type' in data and data['type'] == 'status':
                robot_status = data.get('data')
                if robot_status and hasattr(robot_status, 'joints'):
                    # 更新关节控制面板的位置显示
                    self._update_joint_positions(robot_status.joints)
                    
                    # 更新电流显示
                    if hasattr(robot_status, 'total_current'):
                        self._update_current_display(robot_status.frame_type, robot_status.total_current)
        
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")
    
    def _update_joint_positions(self, joints):
        """更新关节位置显示"""
        try:
            # 更新关节控制面板
            if hasattr(self, 'joint_control_panel') and self.joint_control_panel:
                for joint in joints:
                    # 通知关节控制面板更新位置
                    if hasattr(self.joint_control_panel, 'update_joint_position'):
                        self.joint_control_panel.update_joint_position(joint.joint_id, joint.position)
            
            # 更新状态显示（如果有的话）
            if hasattr(self, 'status_display') and self.status_display:
                for joint in joints:
                    if hasattr(self.status_display, 'update_joint_status'):
                        self.status_display.update_joint_status(
                            joint.joint_id, 
                            joint.position, 
                            joint.velocity, 
                            joint.current
                        )
        
        except Exception as e:
            logger.error(f"更新关节位置显示失败: {e}")
    
    def _update_current_display(self, frame_type, total_current):
        """更新电流显示"""
        try:
            # 根据帧类型更新对应的电流显示
            if hasattr(frame_type, 'name'):
                if 'ARM' in frame_type.name:
                    # 手臂板电流
                    if hasattr(self, 'arm_current_label'):
                        self.arm_current_label.setText(f"手臂板总电流: {total_current} mA")
                elif 'FINGER' in frame_type.name or 'WRIST' in frame_type.name:
                    # 手腕板电流
                    if hasattr(self, 'wrist_current_label'):
                        self.wrist_current_label.setText(f"手腕板总电流: {total_current} mA")
        
        except Exception as e:
            logger.error(f"更新电流显示失败: {e}")
    def on_motion_stop(self, _):
        self.log_message("运动停止")
    def on_trajectory_started(self, _):
        self.log_message("轨迹开始执行")
    def on_trajectory_completed(self, _):
        self.log_message("轨迹执行完成")
        
    def show_about(self):
        QMessageBox.about(self, "关于", "EvoBot 控制系统 v1.0.0\n\n基于 Python/PyQt5 开发")

    def update_ui(self):
        pass # Timer event 