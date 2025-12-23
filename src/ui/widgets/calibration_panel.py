"""
关节位置标定面板

功能：
- 标定向导界面
- 读取0位功能
- 读取最大位置功能
- 标定数据显示和管理
- 标定历史查看
"""

import sys
from typing import List, Optional, Dict, Any
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QTabWidget, QDialog, QDialogButtonBox,
    QMessageBox, QSpinBox, QCheckBox, QComboBox, QLineEdit,
    QHeaderView, QAbstractItemView, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

from utils.logger import get_logger
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.calibration_manager import get_calibration_manager, CalibrationResult
from hardware.serial_manager import get_serial_manager

logger = get_logger(__name__)


class CalibrationWorker(QThread):
    """标定工作线程"""
    
    position_read = pyqtSignal(object)  # CalibrationResult
    
    def __init__(self, calibration_manager, parent=None):
        super().__init__(parent)
        self.calibration_manager = calibration_manager
        
    def run(self):
        """执行位置读取"""
        result = self.calibration_manager.read_current_positions()
        self.position_read.emit(result)


class CalibrationWizardDialog(QDialog):
    """标定向导对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.calibration_manager = get_calibration_manager()
        self.serial_manager = get_serial_manager()
        
        self.current_step = 0
        self.zero_positions = None
        self.max_positions = None
        
        self.setup_ui()
        self.connect_signals()
        
        # 工作线程
        self.worker = None
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("关节位置标定向导")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("关节位置标定向导")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 步骤指示器
        self.step_label = QLabel("步骤 1/2: 读取归零位置")
        step_font = QFont()
        step_font.setPointSize(12)
        self.step_label.setFont(step_font)
        layout.addWidget(self.step_label)
        
        # 说明文本
        self.instruction_label = QLabel()
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setMinimumHeight(60)
        layout.addWidget(self.instruction_label)
        
        # 位置数据表格
        self.position_table = QTableWidget()
        self.position_table.setColumnCount(4)
        self.position_table.setHorizontalHeaderLabels(["关节", "当前位置", "设为0位", "备注"])
        self.position_table.setRowCount(10)
        
        # 设置表格属性
        header = self.position_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.position_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.position_table.setAlternatingRowColors(True)
        
        # 填充关节名称
        joint_names = ["拇指", "食指", "中指", "无名指", "小指", "手腕", "肩部1", "肩部2", "肘部1", "肘部2"]
        for i, name in enumerate(joint_names):
            self.position_table.setItem(i, 0, QTableWidgetItem(f"{i}: {name}"))
            self.position_table.setItem(i, 1, QTableWidgetItem("--"))
            self.position_table.setItem(i, 2, QTableWidgetItem("--"))
            self.position_table.setItem(i, 3, QTableWidgetItem(""))
        
        layout.addWidget(self.position_table)
        
        # 操作按钮区域
        button_layout = QHBoxLayout()
        
        self.read_button = QPushButton("读取当前位置")
        self.read_button.setMinimumHeight(35)
        button_layout.addWidget(self.read_button)
        
        button_layout.addStretch()
        
        # 进度指示
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        button_layout.addWidget(self.progress_bar)
        
        layout.addLayout(button_layout)
        
        # 对话框按钮
        self.button_box = QDialogButtonBox()
        self.prev_button = self.button_box.addButton("上一步", QDialogButtonBox.ActionRole)
        self.next_button = self.button_box.addButton("下一步", QDialogButtonBox.ActionRole)
        self.finish_button = self.button_box.addButton("完成", QDialogButtonBox.AcceptRole)
        self.cancel_button = self.button_box.addButton("取消", QDialogButtonBox.RejectRole)
        
        # 初始状态
        self.prev_button.setEnabled(False)
        self.finish_button.setVisible(False)
        
        layout.addWidget(self.button_box)
        
        # 更新界面
        self.update_step_ui()
    
    def connect_signals(self):
        """连接信号"""
        self.read_button.clicked.connect(self.read_positions)
        self.prev_button.clicked.connect(self.prev_step)
        self.next_button.clicked.connect(self.next_step)
        self.finish_button.clicked.connect(self.finish_calibration)
        self.cancel_button.clicked.connect(self.reject)
    
    def update_step_ui(self):
        """更新步骤界面"""
        if self.current_step == 0:
            # 步骤1：读取0位
            self.step_label.setText("步骤 1/2: 读取归零位置")
            self.instruction_label.setText(
                "请将机器人移动到初始位置（0位），这个位置将作为所有关节的参考点。\n"
                "建议将机器人调整到一个安全、易于识别的姿态，然后点击"读取当前位置"按钮。"
            )
            
            # 更新表格标题
            self.position_table.setHorizontalHeaderLabels(["关节", "当前位置", "设为0位", "备注"])
            
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(self.zero_positions is not None)
            self.finish_button.setVisible(False)
            
        elif self.current_step == 1:
            # 步骤2：读取最大位置
            self.step_label.setText("步骤 2/2: 读取最大位置")
            self.instruction_label.setText(
                "请将机器人移动到最大行程位置，这将确定各关节的运动范围。\n"
                "请小心操作，确保不要超出机械限位，然后点击"读取当前位置"按钮。"
            )
            
            # 更新表格标题
            self.position_table.setHorizontalHeaderLabels(["关节", "当前位置", "最大位置", "行程范围"])
            
            self.prev_button.setEnabled(True)
            self.next_button.setVisible(False)
            self.finish_button.setVisible(True)
            self.finish_button.setEnabled(self.max_positions is not None)
    
    def read_positions(self):
        """读取当前位置"""
        # 检查连接
        if not self.serial_manager.is_connected():
            QMessageBox.warning(self, "警告", "请先连接机器人硬件")
            return
        
        # 显示进度
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.read_button.setEnabled(False)
        
        # 启动工作线程
        self.worker = CalibrationWorker(self.calibration_manager)
        self.worker.position_read.connect(self.on_positions_read)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_positions_read(self, result: CalibrationResult):
        """位置读取完成回调"""
        # 隐藏进度
        self.progress_bar.setVisible(False)
        self.read_button.setEnabled(True)
        
        if result.success:
            positions = result.positions
            
            if self.current_step == 0:
                # 步骤1：设置0位
                self.zero_positions = positions
                
                for i, pos in enumerate(positions):
                    self.position_table.setItem(i, 1, QTableWidgetItem(str(pos)))
                    self.position_table.setItem(i, 2, QTableWidgetItem("0"))
                    self.position_table.setItem(i, 3, QTableWidgetItem("归零参考点"))
                
                self.next_button.setEnabled(True)
                
            elif self.current_step == 1:
                # 步骤2：设置最大位置
                self.max_positions = positions
                
                for i, pos in enumerate(positions):
                    zero_offset = self.zero_positions[i] if self.zero_positions else 0
                    max_travel = pos - zero_offset
                    
                    self.position_table.setItem(i, 1, QTableWidgetItem(str(pos)))
                    self.position_table.setItem(i, 2, QTableWidgetItem(str(max_travel)))
                    self.position_table.setItem(i, 3, QTableWidgetItem(f"行程: {max_travel}"))
                
                self.finish_button.setEnabled(True)
            
            logger.info(f"位置读取成功: {positions}")
            
        else:
            QMessageBox.critical(self, "错误", f"读取位置失败:\n{result.error_message}")
    
    def prev_step(self):
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step_ui()
            
            # 恢复步骤1的数据显示
            if self.current_step == 0 and self.zero_positions:
                for i, pos in enumerate(self.zero_positions):
                    self.position_table.setItem(i, 1, QTableWidgetItem(str(pos)))
                    self.position_table.setItem(i, 2, QTableWidgetItem("0"))
                    self.position_table.setItem(i, 3, QTableWidgetItem("归零参考点"))
    
    def next_step(self):
        """下一步"""
        if self.current_step < 1:
            self.current_step += 1
            self.update_step_ui()
            
            # 清空表格数据，准备步骤2
            for i in range(10):
                self.position_table.setItem(i, 1, QTableWidgetItem("--"))
                self.position_table.setItem(i, 2, QTableWidgetItem("--"))
                self.position_table.setItem(i, 3, QTableWidgetItem(""))
    
    def finish_calibration(self):
        """完成标定"""
        if not self.zero_positions or not self.max_positions:
            QMessageBox.warning(self, "警告", "请完成所有标定步骤")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认标定",
            "确定要保存标定数据吗？\n这将覆盖现有的标定配置。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 保存标定数据
                notes = f"标定向导完成于 {result.timestamp if hasattr(result, 'timestamp') else 'unknown'}"
                
                success1 = self.calibration_manager.set_zero_positions(self.zero_positions, notes)
                success2 = self.calibration_manager.set_max_positions(self.max_positions, notes)
                
                if success1 and success2:
                    success3 = self.calibration_manager.save_calibration()
                    
                    if success3:
                        QMessageBox.information(self, "成功", "标定数据已保存！")
                        self.accept()
                    else:
                        QMessageBox.critical(self, "错误", "保存标定数据失败")
                else:
                    QMessageBox.critical(self, "错误", "设置标定数据失败")
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"标定失败: {str(e)}")


class CalibrationPanel(QWidget):
    """标定控制面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.calibration_manager = get_calibration_manager()
        self.serial_manager = get_serial_manager()
        self.message_bus = get_message_bus()
        
        self.setup_ui()
        self.connect_signals()
        self.setup_timer()
        
        logger.info("标定控制面板初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # 上半部分：标定控制
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 标定状态组
        status_group = QGroupBox("标定状态")
        status_layout = QGridLayout(status_group)
        
        status_layout.addWidget(QLabel("标定状态:"), 0, 0)
        self.calibration_status_label = QLabel("未标定")
        status_layout.addWidget(self.calibration_status_label, 0, 1)
        
        status_layout.addWidget(QLabel("标定时间:"), 1, 0)
        self.calibration_time_label = QLabel("--")
        status_layout.addWidget(self.calibration_time_label, 1, 1)
        
        status_layout.addWidget(QLabel("标定方法:"), 2, 0)
        self.calibration_method_label = QLabel("--")
        status_layout.addWidget(self.calibration_method_label, 2, 1)
        
        control_layout.addWidget(status_group)
        
        # 快速标定组
        quick_group = QGroupBox("快速标定")
        quick_layout = QHBoxLayout(quick_group)
        
        self.read_zero_button = QPushButton("读取0位")
        self.read_zero_button.setMinimumHeight(35)
        quick_layout.addWidget(self.read_zero_button)
        
        self.read_max_button = QPushButton("读取最大位")
        self.read_max_button.setMinimumHeight(35)
        quick_layout.addWidget(self.read_max_button)
        
        self.save_calibration_button = QPushButton("保存标定")
        self.save_calibration_button.setMinimumHeight(35)
        quick_layout.addWidget(self.save_calibration_button)
        
        control_layout.addWidget(quick_group)
        
        # 标定向导组
        wizard_group = QGroupBox("标定向导")
        wizard_layout = QVBoxLayout(wizard_group)
        
        wizard_info = QLabel("推荐使用标定向导进行完整的标定流程，确保标定数据的准确性。")
        wizard_info.setWordWrap(True)
        wizard_layout.addWidget(wizard_info)
        
        wizard_button_layout = QHBoxLayout()
        
        self.calibration_wizard_button = QPushButton("启动标定向导")
        self.calibration_wizard_button.setMinimumHeight(40)
        wizard_button_layout.addWidget(self.calibration_wizard_button)
        
        self.reset_calibration_button = QPushButton("重置标定")
        self.reset_calibration_button.setMinimumHeight(40)
        wizard_button_layout.addWidget(self.reset_calibration_button)
        
        wizard_layout.addLayout(wizard_button_layout)
        control_layout.addWidget(wizard_group)
        
        splitter.addWidget(control_widget)
        
        # 下半部分：标定数据显示
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        
        # 标定数据表格
        data_group = QGroupBox("标定数据")
        data_group_layout = QVBoxLayout(data_group)
        
        self.calibration_table = QTableWidget()
        self.calibration_table.setColumnCount(6)
        self.calibration_table.setHorizontalHeaderLabels([
            "关节", "归零偏移", "最大位置", "用户范围", "硬件范围", "状态"
        ])
        self.calibration_table.setRowCount(10)
        
        # 设置表格属性
        header = self.calibration_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        self.calibration_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.calibration_table.setAlternatingRowColors(True)
        
        data_group_layout.addWidget(self.calibration_table)
        data_layout.addWidget(data_group)
        
        splitter.addWidget(data_widget)
        
        # 设置分割器比例
        splitter.setSizes([300, 200])
    
    def connect_signals(self):
        """连接信号"""
        self.read_zero_button.clicked.connect(self.read_zero_positions)
        self.read_max_button.clicked.connect(self.read_max_positions)
        self.save_calibration_button.clicked.connect(self.save_calibration)
        self.calibration_wizard_button.clicked.connect(self.start_calibration_wizard)
        self.reset_calibration_button.clicked.connect(self.reset_calibration)
        
        # 订阅标定更新事件
        self.message_bus.subscribe(Topics.CALIBRATION_UPDATED, self.on_calibration_updated)
    
    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # 1秒更新一次
        
        # 初始更新
        self.update_display()
    
    def read_zero_positions(self):
        """读取0位"""
        if not self.serial_manager.is_connected():
            QMessageBox.warning(self, "警告", "请先连接机器人硬件")
            return
        
        # 启动工作线程
        self.worker = CalibrationWorker(self.calibration_manager)
        self.worker.position_read.connect(self.on_zero_positions_read)
        self.worker.start()
        
        self.read_zero_button.setEnabled(False)
        self.read_zero_button.setText("读取中...")
    
    def read_max_positions(self):
        """读取最大位置"""
        if not self.serial_manager.is_connected():
            QMessageBox.warning(self, "警告", "请先连接机器人硬件")
            return
        
        if not self.calibration_manager.calibration_data.zero_offsets or \
           all(offset == 0 for offset in self.calibration_manager.calibration_data.zero_offsets):
            QMessageBox.warning(self, "警告", "请先读取0位")
            return
        
        # 启动工作线程
        self.worker = CalibrationWorker(self.calibration_manager)
        self.worker.position_read.connect(self.on_max_positions_read)
        self.worker.start()
        
        self.read_max_button.setEnabled(False)
        self.read_max_button.setText("读取中...")
    
    @pyqtSlot(object)
    def on_zero_positions_read(self, result: CalibrationResult):
        """0位读取完成"""
        self.read_zero_button.setEnabled(True)
        self.read_zero_button.setText("读取0位")
        
        if result.success:
            success = self.calibration_manager.set_zero_positions(
                result.positions, 
                f"快速标定0位于 {result.timestamp}"
            )
            
            if success:
                QMessageBox.information(self, "成功", "0位读取成功！")
                self.update_display()
            else:
                QMessageBox.critical(self, "错误", "设置0位失败")
        else:
            QMessageBox.critical(self, "错误", f"读取0位失败:\n{result.error_message}")
    
    @pyqtSlot(object)
    def on_max_positions_read(self, result: CalibrationResult):
        """最大位置读取完成"""
        self.read_max_button.setEnabled(True)
        self.read_max_button.setText("读取最大位")
        
        if result.success:
            success = self.calibration_manager.set_max_positions(
                result.positions,
                f"快速标定最大位于 {result.timestamp}"
            )
            
            if success:
                QMessageBox.information(self, "成功", "最大位置读取成功！")
                self.update_display()
            else:
                QMessageBox.critical(self, "错误", "设置最大位置失败")
        else:
            QMessageBox.critical(self, "错误", f"读取最大位置失败:\n{result.error_message}")
    
    def save_calibration(self):
        """保存标定"""
        success = self.calibration_manager.save_calibration()
        
        if success:
            QMessageBox.information(self, "成功", "标定数据已保存！")
        else:
            QMessageBox.critical(self, "错误", "保存标定数据失败")
    
    def start_calibration_wizard(self):
        """启动标定向导"""
        wizard = CalibrationWizardDialog(self)
        if wizard.exec_() == QDialog.Accepted:
            self.update_display()
    
    def reset_calibration(self):
        """重置标定"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要重置标定数据吗？\n这将清除所有标定信息。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.calibration_manager.reset_calibration()
            self.update_display()
            QMessageBox.information(self, "成功", "标定数据已重置")
    
    def update_display(self):
        """更新显示"""
        try:
            # 更新标定状态
            summary = self.calibration_manager.get_calibration_summary()
            
            if summary['is_calibrated']:
                self.calibration_status_label.setText("已标定")
                self.calibration_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.calibration_status_label.setText("未标定")
                self.calibration_status_label.setStyleSheet("color: red; font-weight: bold;")
            
            self.calibration_time_label.setText(summary['calibrated_at'])
            self.calibration_method_label.setText(summary['calibration_method'])
            
            # 更新标定数据表格
            joint_names = ["拇指", "食指", "中指", "无名指", "小指", "手腕", "肩部1", "肩部2", "肘部1", "肘部2"]
            
            for i in range(10):
                # 关节名称
                self.calibration_table.setItem(i, 0, QTableWidgetItem(f"{i}: {joint_names[i]}"))
                
                # 归零偏移
                zero_offset = summary['zero_offsets'][i] if i < len(summary['zero_offsets']) else 0
                self.calibration_table.setItem(i, 1, QTableWidgetItem(str(zero_offset)))
                
                # 最大位置
                max_pos = summary['max_positions'][i] if i < len(summary['max_positions']) else 0
                self.calibration_table.setItem(i, 2, QTableWidgetItem(str(max_pos)))
                
                # 用户范围
                user_range = summary['joint_ranges'][i] if i < len(summary['joint_ranges']) else (0, 0)
                self.calibration_table.setItem(i, 3, QTableWidgetItem(f"0 ~ {user_range[1]}"))
                
                # 硬件范围
                hardware_range = summary['hardware_ranges'][i] if i < len(summary['hardware_ranges']) else (0, 0)
                self.calibration_table.setItem(i, 4, QTableWidgetItem(f"{hardware_range[0]} ~ {hardware_range[1]}"))
                
                # 状态
                if summary['is_calibrated'] and max_pos > 0:
                    status_item = QTableWidgetItem("正常")
                    status_item.setBackground(QColor(200, 255, 200))
                else:
                    status_item = QTableWidgetItem("未标定")
                    status_item.setBackground(QColor(255, 200, 200))
                
                self.calibration_table.setItem(i, 5, status_item)
            
        except Exception as e:
            logger.error(f"更新标定显示失败: {e}")
    
    def on_calibration_updated(self, message):
        """标定更新事件回调"""
        self.update_display()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = CalibrationPanel()
    panel.show()
    
    sys.exit(app.exec_())