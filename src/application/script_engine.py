"""
脚本引擎

功能：
- Python脚本执行
- 丰富的API接口
- 脚本调试功能
- 安全执行环境
"""

import sys
import io
import traceback
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.motion_controller import get_motion_controller, ControlMode
from core.trajectory_planner import get_trajectory_planner, InterpolationType
from application.teaching_mode import get_teaching_mode

logger = get_logger(__name__)


class ScriptState(Enum):
    """脚本状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ScriptResult:
    """脚本执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    variables: Optional[Dict[str, Any]] = None


class RobotAPI:
    """机器人控制API"""
    
    def __init__(self, script_engine):
        self.script_engine = script_engine
        self.motion_controller = get_motion_controller()
        self.trajectory_planner = get_trajectory_planner()
        self.teaching_mode = get_teaching_mode()
        
    def move_to(self, positions: List[int], duration: float = 2.0) -> bool:
        """移动到指定位置"""
        try:
            if self.script_engine.is_stopped():
                return False
            
            success = self.motion_controller.move_to_position(positions, duration)
            if success:
                # 等待运动完成
                self.wait_for_motion_complete(duration + 1.0)
            return success
        except Exception as e:
            logger.error(f"移动失败: {e}")
            return False
    
    def move_joint(self, joint_id: int, position: int, duration: float = 2.0) -> bool:
        """移动单个关节"""
        try:
            if self.script_engine.is_stopped():
                return False
            
            return self.motion_controller.move_joint(joint_id, position, duration)
        except Exception as e:
            logger.error(f"关节移动失败: {e}")
            return False
    
    def get_positions(self) -> List[int]:
        """获取当前位置"""
        return self.motion_controller.get_current_positions()
    
    def wait(self, seconds: float):
        """等待指定时间"""
        if self.script_engine.is_stopped():
            return
        
        start_time = time.time()
        while time.time() - start_time < seconds:
            if self.script_engine.is_stopped():
                break
            time.sleep(0.1)
    
    def wait_for_motion_complete(self, timeout: float = 10.0):
        """等待运动完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.script_engine.is_stopped():
                break
            
            if not self.motion_controller.interpolator.is_running():
                break
            
            time.sleep(0.1)
    
    def stop_motion(self):
        """停止运动"""
        self.motion_controller.stop()
    
    def emergency_stop(self):
        """紧急停止"""
        self.motion_controller.emergency_stop()
    
    def set_mode(self, mode: str) -> bool:
        """设置控制模式"""
        mode_map = {
            'manual': ControlMode.MANUAL,
            'trajectory': ControlMode.TRAJECTORY,
            'teaching': ControlMode.TEACHING,
            'script': ControlMode.SCRIPT
        }
        
        if mode in mode_map:
            return self.motion_controller.set_mode(mode_map[mode])
        return False
    
    def home(self) -> bool:
        """回到零位"""
        return self.move_to([1500] * 10, 3.0)
    
    def play_sequence(self, sequence_name: str) -> bool:
        """播放示教序列"""
        try:
            sequences = self.teaching_mode.list_sequences()
            for seq_info in sequences:
                if seq_info['name'] == sequence_name:
                    filepath = f"data/sequences/{seq_info['filename']}"
                    sequence = self.teaching_mode.load_sequence(filepath)
                    if sequence:
                        return self.teaching_mode.play_sequence(sequence)
            return False
        except Exception as e:
            logger.error(f"播放序列失败: {e}")
            return False
    
    def log(self, message: str):
        """输出日志"""
        print(f"[ROBOT] {message}")


class ScriptEngine:
    """脚本引擎"""
    
    def __init__(self):
        """初始化脚本引擎"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        
        # 状态管理
        self.state = ScriptState.IDLE
        self.current_script = ""
        self.execution_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        
        # API对象
        self.robot_api = RobotAPI(self)
        
        # 执行结果
        self.last_result: Optional[ScriptResult] = None
        
        # 回调函数
        self.output_callback: Optional[Callable[[str], None]] = None
        self.state_callback: Optional[Callable[[ScriptState], None]] = None
        
        logger.info("脚本引擎初始化完成")
    
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置输出回调"""
        self.output_callback = callback
    
    def set_state_callback(self, callback: Callable[[ScriptState], None]):
        """设置状态回调"""
        self.state_callback = callback
    
    @log_performance
    def execute_script(self, script: str) -> bool:
        """执行脚本"""
        try:
            if self.state == ScriptState.RUNNING:
                logger.warning("脚本正在运行中")
                return False
            
            self.current_script = script
            self.stop_flag.clear()
            
            # 启动执行线程
            self.execution_thread = threading.Thread(target=self._execute_script_thread, daemon=True)
            self.execution_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"启动脚本执行失败: {e}")
            return False
    
    def stop_script(self):
        """停止脚本执行"""
        if self.state == ScriptState.RUNNING:
            self.stop_flag.set()
            self._set_state(ScriptState.STOPPED)
            
            # 停止机器人运动
            self.robot_api.stop_motion()
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.state == ScriptState.RUNNING
    
    def is_stopped(self) -> bool:
        """检查是否已停止"""
        return self.stop_flag.is_set()
    
    def get_state(self) -> ScriptState:
        """获取当前状态"""
        return self.state
    
    def get_last_result(self) -> Optional[ScriptResult]:
        """获取最后执行结果"""
        return self.last_result
    
    def _execute_script_thread(self):
        """脚本执行线程"""
        start_time = time.time()
        output_buffer = io.StringIO()
        error_buffer = io.StringIO()
        
        try:
            self._set_state(ScriptState.RUNNING)
            
            # 准备执行环境
            global_vars = self._prepare_globals()
            local_vars = {}
            
            # 重定向输出
            with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                # 执行脚本
                exec(self.current_script, global_vars, local_vars)
            
            # 检查是否被停止
            if self.stop_flag.is_set():
                self._set_state(ScriptState.STOPPED)
                output_buffer.write("\n[脚本被用户停止]")
            else:
                self._set_state(ScriptState.IDLE)
            
            # 保存结果
            execution_time = time.time() - start_time
            self.last_result = ScriptResult(
                success=True,
                output=output_buffer.getvalue(),
                execution_time=execution_time,
                variables=local_vars
            )
            
            logger.info(f"脚本执行完成，耗时: {execution_time:.2f}s")
            
        except Exception as e:
            self._set_state(ScriptState.ERROR)
            
            error_msg = traceback.format_exc()
            execution_time = time.time() - start_time
            
            self.last_result = ScriptResult(
                success=False,
                output=output_buffer.getvalue(),
                error=error_msg,
                execution_time=execution_time
            )
            
            logger.error(f"脚本执行失败: {e}")
        
        finally:
            # 输出结果
            if self.output_callback and self.last_result:
                self.output_callback(self.last_result.output)
                if self.last_result.error:
                    self.output_callback(f"\n错误:\n{self.last_result.error}")
    
    def _prepare_globals(self) -> Dict[str, Any]:
        """准备全局变量"""
        return {
            # 内置函数
            '__builtins__': {
                'print': self._safe_print,
                'len': len,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'int': int,
                'float': float,
                'str': str,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
            },
            
            # 机器人API
            'robot': self.robot_api,
            
            # 工具函数
            'sleep': self.robot_api.wait,
            'wait': self.robot_api.wait,
            'time': time,
            
            # 常量
            'JOINT_COUNT': 10,
            'HOME_POSITION': [1500] * 10,
            
            # 插值类型
            'LINEAR': InterpolationType.LINEAR,
            'CUBIC_SPLINE': InterpolationType.CUBIC_SPLINE,
            'QUINTIC': InterpolationType.QUINTIC,
            'TRAPEZOIDAL': InterpolationType.TRAPEZOIDAL,
            'S_CURVE': InterpolationType.S_CURVE,
        }
    
    def _safe_print(self, *args, **kwargs):
        """安全的打印函数"""
        if self.stop_flag.is_set():
            return
        
        # 使用标准print，输出会被重定向
        print(*args, **kwargs)
        
        # 同时发送到回调
        if self.output_callback:
            message = ' '.join(str(arg) for arg in args)
            self.output_callback(message + '\n')
    
    def _set_state(self, new_state: ScriptState):
        """设置状态"""
        old_state = self.state
        self.state = new_state
        
        if self.state_callback:
            self.state_callback(new_state)
        
        # 发布状态变化事件
        self.message_bus.publish(
            Topics.SCRIPT_STATE_CHANGED,
            {
                'old_state': old_state.value,
                'new_state': new_state.value
            },
            MessagePriority.NORMAL
        )
    
    def get_example_scripts(self) -> Dict[str, str]:
        """获取示例脚本"""
        return {
            "基本移动": '''# 基本移动示例
robot.log("开始基本移动测试")

# 移动到指定位置
robot.move_to([2000, 1800, 1000, 1200, 1500, 2000, 1800, 1500, 1000, 1200])
robot.wait(2)

# 回到零位
robot.home()
robot.log("基本移动测试完成")
''',
            
            "单关节控制": '''# 单关节控制示例
robot.log("开始单关节控制测试")

# 依次移动每个关节
for joint_id in range(10):
    robot.log(f"移动关节 {joint_id}")
    robot.move_joint(joint_id, 2000, 1.0)
    robot.wait(1.5)
    
    robot.move_joint(joint_id, 1000, 1.0)
    robot.wait(1.5)
    
    robot.move_joint(joint_id, 1500, 1.0)
    robot.wait(1.5)

robot.log("单关节控制测试完成")
''',
            
            "循环运动": '''# 循环运动示例
robot.log("开始循环运动测试")

# 定义几个位置
positions = [
    [1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500],
    [2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000],
    [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
    [1500, 2000, 1000, 2000, 1000, 1500, 2000, 1000, 2000, 1000]
]

# 循环执行
for i in range(3):
    robot.log(f"第 {i+1} 轮循环")
    for j, pos in enumerate(positions):
        robot.log(f"移动到位置 {j+1}")
        robot.move_to(pos, 2.0)
        robot.wait(2.5)

robot.home()
robot.log("循环运动测试完成")
''',
            
            "状态监控": '''# 状态监控示例
robot.log("开始状态监控测试")

# 移动并监控位置
target = [2000, 1800, 1000, 1200, 1500, 2000, 1800, 1500, 1000, 1200]
robot.move_to(target, 3.0)

# 监控运动过程
for i in range(30):
    current = robot.get_positions()
    robot.log(f"当前位置: {current[:3]}...")  # 只显示前3个关节
    robot.wait(0.1)

robot.log("状态监控测试完成")
''',
            
            "示教序列播放": '''# 示教序列播放示例
robot.log("开始示教序列播放测试")

# 播放已保存的序列（需要先录制序列）
sequences = ["测试序列1", "测试序列2"]  # 替换为实际序列名称

for seq_name in sequences:
    robot.log(f"播放序列: {seq_name}")
    if robot.play_sequence(seq_name):
        robot.log(f"序列 {seq_name} 播放成功")
        robot.wait(5)  # 等待播放完成
    else:
        robot.log(f"序列 {seq_name} 播放失败")

robot.log("示教序列播放测试完成")
'''
        }


# 全局脚本引擎实例
_script_engine = None


def get_script_engine() -> ScriptEngine:
    """获取全局脚本引擎实例"""
    global _script_engine
    if _script_engine is None:
        _script_engine = ScriptEngine()
    return _script_engine