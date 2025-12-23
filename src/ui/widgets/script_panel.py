"""
脚本模式面板

功能：
- 脚本编辑器
- 脚本执行控制
- 输出显示
- 示例脚本管理
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QComboBox, QSplitter, QTabWidget,
    QMessageBox, QFileDialog, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter
from typing import Optional, Dict, Any
import re

from utils.logger import get_logger
from application.script_engine import get_script_engine, ScriptState

logger = get_logger(__name__)


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Python语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 定义语法高亮规则
        self.highlighting_rules = []
        
        # 关键字
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(0, 0, 255))
        keyword_format.setFontWeight(QFont.Bold)
        
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'not', 'or', 'pass', 'print', 'raise', 'return', 'try',
            'while', 'with', 'yield', 'True', 'False', 'None'
        ]
        
        for keyword in keywords:
            pattern = f'\\b{keyword}\\b'
            self.highlighting_rules.append((re.compile(pattern), keyword_format))
        
        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(0, 128, 0))
        self.highlighting_rules.append((re.compile(r'".*?"'), string_format))
        self.highlighting_rules.append((re.compile(r"'.*?'"), string_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(128, 128, 128))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r'#.*'), comment_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(255, 0, 255))
        self.highlighting_rules.append((re.compile(r'\\b\\d+\\b'), number_format))
        
        # 函数定义
        function_format = QTextCharFormat()
        function_format.setForeground(QColor(0, 0, 255))
        function_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((re.compile(r'\\bdef\\s+(\\w+)'), function_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)


class ScriptEditor(QTextEdit):
    """脚本编辑器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置字体
        font = QFont("Consolas", 12)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # 设置语法高亮
        self.highlighter = PythonSyntaxHighlighter(self.document())
        
        # 设置样式
        self.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #3399ff;
            }
        """)
        
        # 设置制表符宽度
        self.setTabStopWidth(40)
    
    def insertFromMimeData(self, source):
        """处理粘贴操作"""
        # 只粘贴纯文本
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


class ScriptPanel(QWidget):
    """脚本模式面板"""
    
    # 信号
    script_executed = pyqtSignal(str)  # 脚本执行
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.script_engine = get_script_engine()
        
        self.setup_ui()
        self.connect_signals()
        
        # 状态更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(100)  # 100ms更新
        
        # 加载示例脚本
        self.load_example_scripts()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("脚本模式")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # 上半部分 - 脚本编辑区域
        editor_widget = self.create_editor_widget()
        splitter.addWidget(editor_widget)
        
        # 下半部分 - 输出区域
        output_widget = self.create_output_widget()
        splitter.addWidget(output_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 200])
    
    def create_editor_widget(self) -> QWidget:
        """创建编辑器控件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 示例脚本选择
        toolbar_layout.addWidget(QLabel("示例:"))
        self.example_combo = QComboBox()
        self.example_combo.setMinimumWidth(150)
        toolbar_layout.addWidget(self.example_combo)
        
        load_example_button = QPushButton("加载示例")
        load_example_button.clicked.connect(self.load_selected_example)
        toolbar_layout.addWidget(load_example_button)
        
        toolbar_layout.addStretch()
        
        # 文件操作按钮
        new_button = QPushButton("新建")
        new_button.clicked.connect(self.new_script)
        toolbar_layout.addWidget(new_button)
        
        open_button = QPushButton("打开")
        open_button.clicked.connect(self.open_script)
        toolbar_layout.addWidget(open_button)
        
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_script)
        toolbar_layout.addWidget(save_button)
        
        layout.addLayout(toolbar_layout)
        
        # 脚本编辑器
        self.script_editor = ScriptEditor()
        self.script_editor.setPlaceholderText("在此输入Python脚本...")
        layout.addWidget(self.script_editor)
        
        # 执行控制
        control_layout = QHBoxLayout()
        
        self.run_button = QPushButton("运行脚本")
        self.run_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        control_layout.addWidget(self.run_button)
        
        self.stop_button = QPushButton("停止脚本")
        self.stop_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        # 状态显示
        self.status_label = QLabel("状态: 空闲")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # 清除输出按钮
        clear_button = QPushButton("清除输出")
        control_layout.addWidget(clear_button)
        
        layout.addLayout(control_layout)
        
        return widget
    
    def create_output_widget(self) -> QWidget:
        """创建输出控件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 输出选项卡
        tab_widget = QTabWidget()
        
        # 输出标签页
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
            }
        """)
        tab_widget.addTab(self.output_text, "输出")
        
        # 变量标签页
        self.variables_text = QTextEdit()
        self.variables_text.setReadOnly(True)
        self.variables_text.setFont(QFont("Consolas", 10))
        self.variables_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
            }
        """)
        tab_widget.addTab(self.variables_text, "变量")
        
        layout.addWidget(tab_widget)
        
        return widget
    
    def connect_signals(self):
        """连接信号"""
        self.run_button.clicked.connect(self.run_script)
        self.stop_button.clicked.connect(self.stop_script)
        
        # 设置脚本引擎回调
        self.script_engine.set_output_callback(self.on_script_output)
        self.script_engine.set_state_callback(self.on_script_state_changed)
    
    def load_example_scripts(self):
        """加载示例脚本"""
        examples = self.script_engine.get_example_scripts()
        
        self.example_combo.clear()
        self.example_combo.addItem("选择示例...", "")
        
        for name, script in examples.items():
            self.example_combo.addItem(name, script)
    
    def load_selected_example(self):
        """加载选中的示例脚本"""
        script = self.example_combo.currentData()
        if script:
            self.script_editor.setPlainText(script)
    
    def new_script(self):
        """新建脚本"""
        if self.script_editor.toPlainText().strip():
            reply = QMessageBox.question(
                self, "新建脚本", 
                "当前脚本未保存，确定要新建吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        self.script_editor.clear()
        self.output_text.clear()
        self.variables_text.clear()
    
    def open_script(self):
        """打开脚本文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "打开脚本", "", "Python Files (*.py);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.script_editor.setPlainText(content)
                logger.info(f"脚本已加载: {filename}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"打开文件失败:\\n{e}")
    
    def save_script(self):
        """保存脚本文件"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存脚本", "", "Python Files (*.py);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.script_editor.toPlainText())
                logger.info(f"脚本已保存: {filename}")
                QMessageBox.information(self, "成功", "脚本保存成功")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存文件失败:\\n{e}")
    
    def run_script(self):
        """运行脚本"""
        script = self.script_editor.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "警告", "请输入脚本内容")
            return
        
        # 清除之前的输出
        self.output_text.clear()
        self.variables_text.clear()
        
        # 执行脚本
        if self.script_engine.execute_script(script):
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.script_executed.emit(script)
        else:
            QMessageBox.warning(self, "错误", "脚本执行失败")
    
    def stop_script(self):
        """停止脚本"""
        self.script_engine.stop_script()
    
    def on_script_output(self, output: str):
        """脚本输出回调"""
        self.output_text.append(output)
        
        # 自动滚动到底部
        cursor = self.output_text.textCursor()
        cursor.movePosition(cursor.End)
        self.output_text.setTextCursor(cursor)
    
    def on_script_state_changed(self, state: ScriptState):
        """脚本状态变化回调"""
        if state == ScriptState.IDLE:
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 显示变量
            result = self.script_engine.get_last_result()
            if result and result.variables:
                self.show_variables(result.variables)
        
        elif state == ScriptState.RUNNING:
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        
        elif state == ScriptState.STOPPED:
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
        elif state == ScriptState.ERROR:
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    
    def show_variables(self, variables: Dict[str, Any]):
        """显示变量"""
        self.variables_text.clear()
        
        for name, value in variables.items():
            if not name.startswith('_'):  # 跳过私有变量
                try:
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    
                    self.variables_text.append(f"{name} = {value_str}")
                except:
                    self.variables_text.append(f"{name} = <无法显示>")
    
    def update_status(self):
        """更新状态显示"""
        state = self.script_engine.get_state()
        
        status_map = {
            ScriptState.IDLE: ("状态: 空闲", "#666"),
            ScriptState.RUNNING: ("状态: 运行中...", "#4CAF50"),
            ScriptState.PAUSED: ("状态: 已暂停", "#FF9800"),
            ScriptState.STOPPED: ("状态: 已停止", "#f44336"),
            ScriptState.ERROR: ("状态: 错误", "#f44336")
        }
        
        text, color = status_map.get(state, ("状态: 未知", "#666"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")