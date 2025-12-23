"""
参数调优面板

功能：
- 实时参数调整
- 参数预设管理
- 效果预览功能
- 参数导入导出
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QComboBox,
    QGroupBox, QTabWidget, QListWidget, QListWidgetItem,
    QMessageBox, QFileDialog, QCheckBox, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from typing import Dict, Any, Optional, List
import json
import time

from utils.logger import get_logger
from utils.config_manager import get_config_manager
from core.motion_controller import get_motion_controller
from core.trajectory_planner import get_trajectory_planner, InterpolationType

logger = get_logger(__name__)


class ParameterWidget(QWidget):
    """参数控制控件"""
    
    # 信号
    value_changed = pyqtSignal(str, object)  # 参数名, 新值
    
    def __init__(self, param_name: str, param_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.param_name = param_name
        self.param_config = param_config
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 参数名称
        name_label = QLabel(self.param_config.get('display_name', self.param_name))
        name_label.setMinimumWidth(120)
        layout.addWidget(name_label)
        
        # 根据参数类型创建控件
        param_type = self.param_config.get('type', 'float')
        
        if param_type == 'int':
            self.create_int_widget(layout)
        elif param_type == 'float':
            self.create_float_widget(layout)
        elif param_type == 'bool':
            self.create_bool_widget(layout)
        elif param_type == 'choice':
            self.create_choice_widget(layout)
        
        # 单位标签
        unit = self.param_config.get('unit', '')
        if unit:
            unit_label = QLabel(unit)
            unit_label.setMinimumWidth(30)
            layout.addWidget(unit_label)
        
        # 描述工具提示
        description = self.param_config.get('description', '')
        if description:
            self.setToolTip(description)
    
    def create_int_widget(self, layout):
        """创建整数控件"""
        min_val = self.param_config.get('min', 0)
        max_val = self.param_config.get('max', 100)
        default_val = self.param_config.get('default', min_val)
        
        # 滑块
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_val)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.slider)
        
        # 数值框
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.valueChanged.connect(self.on_spinbox_changed)
        layout.addWidget(self.spinbox)
    
    def create_float_widget(self, layout):
        """创建浮点数控件"""
        min_val = self.param_config.get('min', 0.0)
        max_val = self.param_config.get('max', 10.0)
        default_val = self.param_config.get('default', min_val)
        step = self.param_config.get('step', 0.1)
        decimals = self.param_config.get('decimals', 2)
        
        # 滑块（转换为整数）
        scale = 10 ** decimals
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(min_val * scale))
        self.slider.setMaximum(int(max_val * scale))
        self.slider.setValue(int(default_val * scale))
        self.slider.valueChanged.connect(self.on_float_slider_changed)
        layout.addWidget(self.slider)
        
        # 数值框
        self.doublespinbox = QDoubleSpinBox()
        self.doublespinbox.setMinimum(min_val)
        self.doublespinbox.setMaximum(max_val)
        self.doublespinbox.setValue(default_val)
        self.doublespinbox.setSingleStep(step)
        self.doublespinbox.setDecimals(decimals)
        self.doublespinbox.valueChanged.connect(self.on_doublespinbox_changed)
        layout.addWidget(self.doublespinbox)
        
        self.scale = scale
    
    def create_bool_widget(self, layout):
        """创建布尔控件"""
        default_val = self.param_config.get('default', False)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(default_val)
        self.checkbox.stateChanged.connect(self.on_checkbox_changed)
        layout.addWidget(self.checkbox)
    
    def create_choice_widget(self, layout):
        """创建选择控件"""
        choices = self.param_config.get('choices', [])
        default_val = self.param_config.get('default', choices[0] if choices else '')
        
        self.combobox = QComboBox()
        self.combobox.addItems(choices)
        if default_val in choices:
            self.combobox.setCurrentText(default_val)
        self.combobox.currentTextChanged.connect(self.on_combobox_changed)
        layout.addWidget(self.combobox)
    
    def on_slider_changed(self, value):
        """滑块值改变"""
        self.spinbox.setValue(value)
        self.value_changed.emit(self.param_name, value)
    
    def on_spinbox_changed(self, value):
        """数值框值改变"""
        self.slider.setValue(value)
        self.value_changed.emit(self.param_name, value)
    
    def on_float_slider_changed(self, value):
        """浮点滑块值改变"""
        float_value = value / self.scale
        self.doublespinbox.setValue(float_value)
        self.value_changed.emit(self.param_name, float_value)
    
    def on_doublespinbox_changed(self, value):
        """浮点数值框值改变"""
        int_value = int(value * self.scale)
        self.slider.setValue(int_value)
        self.value_changed.emit(self.param_name, value)
    
    def on_checkbox_changed(self, state):
        """复选框状态改变"""
        value = state == Qt.Checked
        self.value_changed.emit(self.param_name, value)
    
    def on_combobox_changed(self, text):
        """下拉框选择改变"""
        self.value_changed.emit(self.param_name, text)
    
    def get_value(self):
        """获取当前值"""
        param_type = self.param_config.get('type', 'float')
        
        if param_type == 'int':
            return self.spinbox.value()
        elif param_type == 'float':
            return self.doublespinbox.value()
        elif param_type == 'bool':
            return self.checkbox.isChecked()
        elif param_type == 'choice':
            return self.combobox.currentText()
        
        return None
    
    def set_value(self, value):
        """设置值"""
        param_type = self.param_config.get('type', 'float')
        
        try:
            if param_type == 'int':
                self.spinbox.setValue(int(value))
            elif param_type == 'float':
                self.doublespinbox.setValue(float(value))
            elif param_type == 'bool':
                self.checkbox.setChecked(bool(value))
            elif param_type == 'choice':
                self.combobox.setCurrentText(str(value))
        except (ValueError, TypeError) as e:
            logger.warning(f"设置参数值失败 {self.param_name}: {e}")


class ParameterTuningPanel(QWidget):
    """参数调优面板"""
    
    # 信号
    parameter_changed = pyqtSignal(str, str, object)  # 分组, 参数名, 新值
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.motion_controller = get_motion_controller()
        self.trajectory_planner = get_trajectory_planner()
        
        # 参数控件字典
        self.parameter_widgets: Dict[str, Dict[str, ParameterWidget]] = {}
        
        # 当前参数值
        self.current_parameters: Dict[str, Dict[str, Any]] = {}
        
        self.setup_ui()
        self.load_parameter_definitions()
        self.load_current_parameters()
        
        # 自动保存定时器
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_parameters)
        self.auto_save_timer.start(5000)  # 5秒自动保存
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("参数调优")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 预设管理
        toolbar_layout.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(150)
        toolbar_layout.addWidget(self.preset_combo)
        
        load_preset_button = QPushButton("加载预设")
        load_preset_button.clicked.connect(self.load_preset)
        toolbar_layout.addWidget(load_preset_button)
        
        save_preset_button = QPushButton("保存预设")
        save_preset_button.clicked.connect(self.save_preset)
        toolbar_layout.addWidget(save_preset_button)
        
        toolbar_layout.addStretch()
        
        # 文件操作
        import_button = QPushButton("导入参数")
        import_button.clicked.connect(self.import_parameters)
        toolbar_layout.addWidget(import_button)
        
        export_button = QPushButton("导出参数")
        export_button.clicked.connect(self.export_parameters)
        toolbar_layout.addWidget(export_button)
        
        reset_button = QPushButton("重置默认")
        reset_button.clicked.connect(self.reset_to_defaults)
        toolbar_layout.addWidget(reset_button)
        
        layout.addLayout(toolbar_layout)
        
        # 参数选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.auto_save_label = QLabel("自动保存: 开启")
        self.auto_save_label.setStyleSheet("color: #4CAF50;")
        status_layout.addWidget(self.auto_save_label)
        
        layout.addLayout(status_layout)
    
    def load_parameter_definitions(self):
        """加载参数定义"""
        # 运动控制参数
        motion_params = {
            'max_velocity': {
                'type': 'float',
                'display_name': '最大速度',
                'min': 0.1,
                'max': 10.0,
                'default': 2.0,
                'step': 0.1,
                'decimals': 1,
                'unit': 'rad/s',
                'description': '关节最大运动速度'
            },
            'max_acceleration': {
                'type': 'float',
                'display_name': '最大加速度',
                'min': 0.1,
                'max': 20.0,
                'default': 5.0,
                'step': 0.1,
                'decimals': 1,
                'unit': 'rad/s²',
                'description': '关节最大加速度'
            },
            'max_jerk': {
                'type': 'float',
                'display_name': '最大加加速度',
                'min': 1.0,
                'max': 100.0,
                'default': 20.0,
                'step': 1.0,
                'decimals': 1,
                'unit': 'rad/s³',
                'description': 'S曲线最大加加速度'
            },
            'position_tolerance': {
                'type': 'int',
                'display_name': '位置容差',
                'min': 1,
                'max': 50,
                'default': 5,
                'unit': '单位',
                'description': '位置到达判断容差'
            },
            'velocity_tolerance': {
                'type': 'float',
                'display_name': '速度容差',
                'min': 0.01,
                'max': 1.0,
                'default': 0.1,
                'step': 0.01,
                'decimals': 2,
                'unit': 'rad/s',
                'description': '速度到达判断容差'
            }
        }
        
        # 轨迹规划参数
        trajectory_params = {
            'interpolation_type': {
                'type': 'choice',
                'display_name': '插值算法',
                'choices': ['LINEAR', 'CUBIC_SPLINE', 'QUINTIC', 'TRAPEZOIDAL', 'S_CURVE'],
                'default': 'CUBIC_SPLINE',
                'description': '轨迹插值算法类型'
            },
            'smoothing_factor': {
                'type': 'float',
                'display_name': '平滑因子',
                'min': 0.0,
                'max': 1.0,
                'default': 0.5,
                'step': 0.01,
                'decimals': 2,
                'description': '轨迹平滑程度'
            },
            'time_scaling': {
                'type': 'float',
                'display_name': '时间缩放',
                'min': 0.1,
                'max': 5.0,
                'default': 1.0,
                'step': 0.1,
                'decimals': 1,
                'description': '轨迹时间缩放因子'
            },
            'optimize_time': {
                'type': 'bool',
                'display_name': '时间优化',
                'default': True,
                'description': '是否启用轨迹时间优化'
            }
        }
        
        # 控制系统参数
        control_params = {
            'control_frequency': {
                'type': 'int',
                'display_name': '控制频率',
                'min': 50,
                'max': 500,
                'default': 200,
                'unit': 'Hz',
                'description': '控制循环频率'
            },
            'buffer_size': {
                'type': 'int',
                'display_name': '缓冲区大小',
                'min': 10,
                'max': 1000,
                'default': 100,
                'unit': '点',
                'description': '轨迹缓冲区大小'
            },
            'lookahead_time': {
                'type': 'float',
                'display_name': '前瞻时间',
                'min': 0.01,
                'max': 1.0,
                'default': 0.1,
                'step': 0.01,
                'decimals': 2,
                'unit': 's',
                'description': '轨迹前瞻时间'
            },
            'emergency_decel': {
                'type': 'float',
                'display_name': '紧急减速度',
                'min': 1.0,
                'max': 50.0,
                'default': 10.0,
                'step': 1.0,
                'decimals': 1,
                'unit': 'rad/s²',
                'description': '紧急停止减速度'
            }
        }
        
        # 安全参数
        safety_params = {
            'enable_soft_limits': {
                'type': 'bool',
                'display_name': '软限位',
                'default': True,
                'description': '是否启用软限位检查'
            },
            'enable_velocity_limits': {
                'type': 'bool',
                'display_name': '速度限制',
                'default': True,
                'description': '是否启用速度限制检查'
            },
            'enable_current_monitor': {
                'type': 'bool',
                'display_name': '电流监控',
                'default': True,
                'description': '是否启用电流监控'
            },
            'current_threshold': {
                'type': 'int',
                'display_name': '电流阈值',
                'min': 100,
                'max': 2000,
                'default': 1000,
                'unit': 'mA',
                'description': '电流报警阈值'
            }
        }
        
        # 创建参数选项卡
        self.create_parameter_tab("运动控制", motion_params)
        self.create_parameter_tab("轨迹规划", trajectory_params)
        self.create_parameter_tab("控制系统", control_params)
        self.create_parameter_tab("安全设置", safety_params)
        
        # 加载预设列表
        self.load_preset_list()
    
    def create_parameter_tab(self, tab_name: str, params: Dict[str, Dict[str, Any]]):
        """创建参数选项卡"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 参数组
        group_box = QGroupBox(f"{tab_name}参数")
        group_layout = QVBoxLayout(group_box)
        
        # 创建参数控件
        self.parameter_widgets[tab_name] = {}
        self.current_parameters[tab_name] = {}
        
        for param_name, param_config in params.items():
            param_widget = ParameterWidget(param_name, param_config)
            param_widget.value_changed.connect(
                lambda name, value, group=tab_name: self.on_parameter_changed(group, name, value)
            )
            
            group_layout.addWidget(param_widget)
            self.parameter_widgets[tab_name][param_name] = param_widget
            self.current_parameters[tab_name][param_name] = param_config.get('default')
        
        layout.addWidget(group_box)
        layout.addStretch()
        
        self.tab_widget.addTab(tab_widget, tab_name)
    
    def on_parameter_changed(self, group: str, param_name: str, value: Any):
        """参数值改变"""
        self.current_parameters[group][param_name] = value
        self.parameter_changed.emit(group, param_name, value)
        
        # 应用参数到系统
        self.apply_parameter(group, param_name, value)
        
        self.status_label.setText(f"参数已更新: {group}.{param_name} = {value}")
        logger.debug(f"参数更新: {group}.{param_name} = {value}")
    
    def apply_parameter(self, group: str, param_name: str, value: Any):
        """应用参数到系统"""
        try:
            if group == "运动控制":
                if param_name == "max_velocity":
                    # 应用到运动控制器
                    pass
                elif param_name == "max_acceleration":
                    # 应用到运动控制器
                    pass
            
            elif group == "轨迹规划":
                if param_name == "interpolation_type":
                    # 应用到轨迹规划器
                    pass
            
            elif group == "控制系统":
                if param_name == "control_frequency":
                    # 应用到插值引擎
                    pass
            
        except Exception as e:
            logger.error(f"应用参数失败 {group}.{param_name}: {e}")
    
    def load_current_parameters(self):
        """加载当前参数"""
        try:
            config = self.config_manager.load_config()
            
            # 从配置中加载参数值
            for group_name, group_widgets in self.parameter_widgets.items():
                for param_name, param_widget in group_widgets.items():
                    # 尝试从配置中获取值
                    config_path = f"{group_name.lower()}.{param_name}"
                    value = self._get_config_value(config, config_path)
                    
                    if value is not None:
                        param_widget.set_value(value)
                        self.current_parameters[group_name][param_name] = value
                        
        except Exception as e:
            logger.error(f"加载当前参数失败: {e}")
    
    def _get_config_value(self, config: Dict, path: str) -> Any:
        """从配置中获取值"""
        keys = path.split('.')
        current = config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def load_preset_list(self):
        """加载预设列表"""
        self.preset_combo.clear()
        self.preset_combo.addItem("选择预设...", "")
        
        # 内置预设
        presets = [
            "高速模式",
            "平滑模式", 
            "精确模式",
            "节能模式"
        ]
        
        for preset in presets:
            self.preset_combo.addItem(preset, preset)
    
    def load_preset(self):
        """加载预设"""
        preset_name = self.preset_combo.currentData()
        if not preset_name:
            return
        
        try:
            # 预设参数定义
            presets = {
                "高速模式": {
                    "运动控制": {
                        "max_velocity": 5.0,
                        "max_acceleration": 15.0,
                        "max_jerk": 50.0
                    },
                    "轨迹规划": {
                        "interpolation_type": "LINEAR",
                        "time_scaling": 0.8
                    }
                },
                "平滑模式": {
                    "运动控制": {
                        "max_velocity": 2.0,
                        "max_acceleration": 5.0,
                        "max_jerk": 20.0
                    },
                    "轨迹规划": {
                        "interpolation_type": "S_CURVE",
                        "smoothing_factor": 0.8
                    }
                },
                "精确模式": {
                    "运动控制": {
                        "max_velocity": 1.0,
                        "max_acceleration": 2.0,
                        "position_tolerance": 2
                    },
                    "轨迹规划": {
                        "interpolation_type": "QUINTIC",
                        "smoothing_factor": 0.9
                    }
                },
                "节能模式": {
                    "运动控制": {
                        "max_velocity": 1.5,
                        "max_acceleration": 3.0
                    },
                    "控制系统": {
                        "control_frequency": 100
                    }
                }
            }
            
            if preset_name in presets:
                preset_params = presets[preset_name]
                
                for group_name, group_params in preset_params.items():
                    if group_name in self.parameter_widgets:
                        for param_name, value in group_params.items():
                            if param_name in self.parameter_widgets[group_name]:
                                widget = self.parameter_widgets[group_name][param_name]
                                widget.set_value(value)
                
                self.status_label.setText(f"已加载预设: {preset_name}")
                QMessageBox.information(self, "成功", f"预设 '{preset_name}' 加载成功")
            
        except Exception as e:
            logger.error(f"加载预设失败: {e}")
            QMessageBox.warning(self, "错误", f"加载预设失败:\\n{e}")
    
    def save_preset(self):
        """保存预设"""
        from PyQt5.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称:")
        if ok and name:
            try:
                # 收集当前参数
                preset_data = {}
                for group_name, group_widgets in self.parameter_widgets.items():
                    preset_data[group_name] = {}
                    for param_name, param_widget in group_widgets.items():
                        preset_data[group_name][param_name] = param_widget.get_value()
                
                # 保存到文件
                filename = f"config/presets/{name}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(preset_data, f, ensure_ascii=False, indent=2)
                
                # 更新预设列表
                self.preset_combo.addItem(name, name)
                
                self.status_label.setText(f"预设已保存: {name}")
                QMessageBox.information(self, "成功", f"预设 '{name}' 保存成功")
                
            except Exception as e:
                logger.error(f"保存预设失败: {e}")
                QMessageBox.warning(self, "错误", f"保存预设失败:\\n{e}")
    
    def import_parameters(self):
        """导入参数"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入参数", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    params = json.load(f)
                
                # 应用参数
                for group_name, group_params in params.items():
                    if group_name in self.parameter_widgets:
                        for param_name, value in group_params.items():
                            if param_name in self.parameter_widgets[group_name]:
                                widget = self.parameter_widgets[group_name][param_name]
                                widget.set_value(value)
                
                self.status_label.setText(f"参数已导入: {filename}")
                QMessageBox.information(self, "成功", "参数导入成功")
                
            except Exception as e:
                logger.error(f"导入参数失败: {e}")
                QMessageBox.warning(self, "错误", f"导入参数失败:\\n{e}")
    
    def export_parameters(self):
        """导出参数"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出参数", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                # 收集当前参数
                params = {}
                for group_name, group_widgets in self.parameter_widgets.items():
                    params[group_name] = {}
                    for param_name, param_widget in group_widgets.items():
                        params[group_name][param_name] = param_widget.get_value()
                
                # 保存到文件
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(params, f, ensure_ascii=False, indent=2)
                
                self.status_label.setText(f"参数已导出: {filename}")
                QMessageBox.information(self, "成功", "参数导出成功")
                
            except Exception as e:
                logger.error(f"导出参数失败: {e}")
                QMessageBox.warning(self, "错误", f"导出参数失败:\\n{e}")
    
    def reset_to_defaults(self):
        """重置为默认值"""
        reply = QMessageBox.question(
            self, "重置参数", 
            "确定要重置所有参数为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                for group_name, group_widgets in self.parameter_widgets.items():
                    for param_name, param_widget in group_widgets.items():
                        default_value = param_widget.param_config.get('default')
                        if default_value is not None:
                            param_widget.set_value(default_value)
                
                self.status_label.setText("参数已重置为默认值")
                QMessageBox.information(self, "成功", "参数重置成功")
                
            except Exception as e:
                logger.error(f"重置参数失败: {e}")
                QMessageBox.warning(self, "错误", f"重置参数失败:\\n{e}")
    
    def auto_save_parameters(self):
        """自动保存参数"""
        try:
            # 收集当前参数
            params = {}
            for group_name, group_widgets in self.parameter_widgets.items():
                params[group_name] = {}
                for param_name, param_widget in group_widgets.items():
                    params[group_name][param_name] = param_widget.get_value()
            
            # 保存到配置文件
            filename = "config/auto_saved_parameters.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            
            # 更新状态
            current_time = time.strftime("%H:%M:%S")
            self.auto_save_label.setText(f"自动保存: {current_time}")
            
        except Exception as e:
            logger.error(f"自动保存参数失败: {e}")
    
    def get_current_parameters(self) -> Dict[str, Dict[str, Any]]:
        """获取当前参数"""
        return self.current_parameters.copy()