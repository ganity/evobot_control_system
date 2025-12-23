"""
插值引擎

功能：
- 实时轨迹插值
- 轨迹缓冲队列管理
- 10Hz控制循环 (100ms周期)
- 轨迹平滑过渡
- 多线程安全
"""

import numpy as np
import threading
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from queue import Queue, Empty
from collections import deque

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.trajectory_planner import Trajectory, TrajectoryPoint, get_trajectory_planner

logger = get_logger(__name__)


class InterpolatorState(Enum):
    """插值器状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class InterpolatorStatus:
    """插值器状态信息"""
    state: InterpolatorState
    current_trajectory: Optional[str] = None
    current_time: float = 0.0
    total_time: float = 0.0
    progress: float = 0.0
    buffer_size: int = 0
    control_frequency: float = 0.0
    last_error: Optional[str] = None


class TrajectoryBuffer:
    """轨迹缓冲区"""
    
    def __init__(self, max_size: int = 1000):
        """初始化缓冲区"""
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.current_index = 0
        
    def add_trajectory(self, trajectory: Trajectory) -> bool:
        """添加轨迹到缓冲区"""
        with self.lock:
            try:
                # 清空现有缓冲区
                self.buffer.clear()
                self.current_index = 0
                
                # 添加轨迹点
                for point in trajectory.points:
                    self.buffer.append(point)
                
                logger.info(f"轨迹已加载到缓冲区: {len(trajectory.points)}个点")
                return True
                
            except Exception as e:
                logger.error(f"添加轨迹到缓冲区失败: {e}")
                return False
    
    def get_next_point(self) -> Optional[TrajectoryPoint]:
        """获取下一个轨迹点"""
        with self.lock:
            if self.current_index < len(self.buffer):
                point = self.buffer[self.current_index]
                self.current_index += 1
                return point
            return None
    
    def get_current_point(self) -> Optional[TrajectoryPoint]:
        """获取当前轨迹点"""
        with self.lock:
            if self.current_index > 0 and self.current_index <= len(self.buffer):
                return self.buffer[self.current_index - 1]
            return None
    
    def peek_next_point(self) -> Optional[TrajectoryPoint]:
        """预览下一个轨迹点（不移动索引）"""
        with self.lock:
            if self.current_index < len(self.buffer):
                return self.buffer[self.current_index]
            return None
    
    def get_point_at_time(self, t: float) -> Optional[TrajectoryPoint]:
        """获取指定时间的轨迹点（插值）"""
        with self.lock:
            if not self.buffer:
                return None
            
            # 查找时间区间
            for i in range(len(self.buffer) - 1):
                p1, p2 = self.buffer[i], self.buffer[i + 1]
                if p1.timestamp <= t <= p2.timestamp:
                    # 线性插值
                    if p2.timestamp == p1.timestamp:
                        return p1
                    
                    alpha = (t - p1.timestamp) / (p2.timestamp - p1.timestamp)
                    
                    positions = []
                    velocities = []
                    accelerations = []
                    
                    for j in range(len(p1.positions)):
                        pos = p1.positions[j] + alpha * (p2.positions[j] - p1.positions[j])
                        vel = p1.velocities[j] + alpha * (p2.velocities[j] - p1.velocities[j])
                        acc = p1.accelerations[j] + alpha * (p2.accelerations[j] - p1.accelerations[j])
                        
                        positions.append(pos)
                        velocities.append(vel)
                        accelerations.append(acc)
                    
                    return TrajectoryPoint(t, positions, velocities, accelerations)
            
            # 返回最后一个点
            return self.buffer[-1] if self.buffer else None
    
    def is_empty(self) -> bool:
        """检查缓冲区是否为空"""
        with self.lock:
            return len(self.buffer) == 0
    
    def is_finished(self) -> bool:
        """检查是否已完成"""
        with self.lock:
            return self.current_index >= len(self.buffer)
    
    def get_progress(self) -> float:
        """获取执行进度"""
        with self.lock:
            if not self.buffer:
                return 0.0
            return min(1.0, self.current_index / len(self.buffer))
    
    def reset(self):
        """重置缓冲区"""
        with self.lock:
            self.current_index = 0
    
    def clear(self):
        """清空缓冲区"""
        with self.lock:
            self.buffer.clear()
            self.current_index = 0
    
    def size(self) -> int:
        """获取缓冲区大小"""
        with self.lock:
            return len(self.buffer)


class Interpolator:
    """插值引擎"""
    
    def __init__(self):
        """初始化插值引擎"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        
        # 控制参数 - 设置为10Hz (100ms周期)
        self.control_frequency = self.config.get('control', {}).get('frequency', 10)  # 10Hz
        self.control_period = 1.0 / self.control_frequency
        
        logger.info(f"插值器初始化: 频率={self.control_frequency}Hz, 周期={self.control_period*1000:.1f}ms")
        
        # 状态管理
        self.state = InterpolatorState.IDLE
        self.state_lock = threading.RLock()
        
        # 轨迹缓冲区
        buffer_size = self.config.get('control', {}).get('trajectory_buffer_size', 1000)
        self.trajectory_buffer = TrajectoryBuffer(buffer_size)
        
        # 控制线程
        self.control_thread = None
        self.stop_event = threading.Event()
        
        # 状态信息
        self.status = InterpolatorStatus(InterpolatorState.IDLE)
        self.start_time = 0.0
        self.current_time = 0.0
        
        # 回调函数
        self.position_callback: Optional[Callable[[List[float]], None]] = None
        self.status_callback: Optional[Callable[[InterpolatorStatus], None]] = None
        
        # 性能统计
        self.loop_times = deque(maxlen=100)
        self.last_loop_time = 0.0
        
        logger.info(f"插值引擎初始化完成: 控制频率={self.control_frequency}Hz")
    
    def set_position_callback(self, callback: Callable[[List[float]], None]):
        """设置位置输出回调函数"""
        self.position_callback = callback
    
    def set_status_callback(self, callback: Callable[[InterpolatorStatus], None]):
        """设置状态更新回调函数"""
        self.status_callback = callback
    
    @log_performance
    def start_trajectory(self, trajectory: Trajectory) -> bool:
        """开始执行轨迹"""
        with self.state_lock:
            if self.state == InterpolatorState.RUNNING:
                logger.warning("插值器正在运行，停止当前轨迹")
                self.stop()
            
            try:
                # 加载轨迹到缓冲区
                if not self.trajectory_buffer.add_trajectory(trajectory):
                    return False
                
                # 重置状态
                self.start_time = time.time()
                self.current_time = 0.0
                self.status.current_trajectory = trajectory.metadata.get('name', 'unnamed') if trajectory.metadata else 'unnamed'
                self.status.total_time = trajectory.duration
                self.status.progress = 0.0
                self.status.last_error = None
                
                # 启动控制线程
                self.stop_event.clear()
                self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
                self.control_thread.start()
                
                self.state = InterpolatorState.RUNNING
                self.status.state = self.state
                
                logger.info(f"开始执行轨迹: {self.status.current_trajectory}, 时长={trajectory.duration:.3f}s")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.TRAJECTORY_STARTED,
                    {
                        'trajectory_name': self.status.current_trajectory,
                        'duration': trajectory.duration,
                        'points': len(trajectory.points)
                    },
                    MessagePriority.HIGH
                )
                
                return True
                
            except Exception as e:
                logger.error(f"启动轨迹执行失败: {e}")
                self.state = InterpolatorState.ERROR
                self.status.state = self.state
                self.status.last_error = str(e)
                return False
    
    def pause(self):
        """暂停执行"""
        with self.state_lock:
            if self.state == InterpolatorState.RUNNING:
                self.state = InterpolatorState.PAUSED
                self.status.state = self.state
                logger.info("轨迹执行已暂停")
    
    def resume(self):
        """恢复执行"""
        with self.state_lock:
            if self.state == InterpolatorState.PAUSED:
                self.state = InterpolatorState.RUNNING
                self.status.state = self.state
                logger.info("轨迹执行已恢复")
    
    def stop(self):
        """停止执行"""
        with self.state_lock:
            if self.state in [InterpolatorState.RUNNING, InterpolatorState.PAUSED]:
                self.state = InterpolatorState.STOPPING
                self.status.state = self.state
                
                # 停止控制线程
                self.stop_event.set()
                if self.control_thread and self.control_thread.is_alive():
                    self.control_thread.join(timeout=1.0)
                
                self.state = InterpolatorState.IDLE
                self.status.state = self.state
                self.status.current_trajectory = None
                self.status.progress = 0.0
                
                logger.info("轨迹执行已停止")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.TRAJECTORY_STOPPED,
                    {'reason': 'user_stop'},
                    MessagePriority.HIGH
                )
    
    def emergency_stop(self):
        """紧急停止"""
        with self.state_lock:
            logger.warning("紧急停止触发")
            self.stop_event.set()
            self.state = InterpolatorState.IDLE
            self.status.state = self.state
            
            # 发布紧急停止事件
            self.message_bus.publish(
                Topics.EMERGENCY_STOP,
                {'timestamp': time.time()},
                MessagePriority.CRITICAL
            )
    
    def get_status(self) -> InterpolatorStatus:
        """获取当前状态"""
        with self.state_lock:
            # 更新状态信息
            self.status.current_time = self.current_time
            self.status.progress = self.trajectory_buffer.get_progress()
            self.status.buffer_size = self.trajectory_buffer.size()
            
            # 计算实际控制频率
            if len(self.loop_times) > 1:
                avg_period = sum(self.loop_times) / len(self.loop_times)
                self.status.control_frequency = 1.0 / avg_period if avg_period > 0 else 0.0
            
            return self.status
    
    def _control_loop(self):
        """控制循环 - 200Hz"""
        logger.info("控制循环启动")
        
        next_time = time.time()
        
        try:
            while not self.stop_event.is_set():
                loop_start = time.time()
                
                # 等待到下一个控制周期
                current_time = time.time()
                if current_time < next_time:
                    time.sleep(next_time - current_time)
                
                # 执行控制步骤
                if self.state == InterpolatorState.RUNNING:
                    self._control_step()
                
                # 更新时间
                next_time += self.control_period
                
                # 记录循环时间
                loop_end = time.time()
                loop_duration = loop_end - loop_start
                self.loop_times.append(loop_duration)
                
                # 检查循环时间
                if loop_duration > self.control_period * 1.5:
                    logger.warning(f"控制循环超时: {loop_duration*1000:.1f}ms > {self.control_period*1000:.1f}ms")
                
        except Exception as e:
            logger.error(f"控制循环异常: {e}")
            self.state = InterpolatorState.ERROR
            self.status.last_error = str(e)
        
        logger.info("控制循环结束")
    
    def _control_step(self):
        """单步控制"""
        try:
            # 更新当前时间
            self.current_time = time.time() - self.start_time
            
            # 获取当前轨迹点
            current_point = self.trajectory_buffer.get_point_at_time(self.current_time)
            
            if current_point is None:
                # 轨迹结束
                logger.info("轨迹执行完成")
                self.state = InterpolatorState.IDLE
                self.status.state = self.state
                
                # 发布完成事件
                self.message_bus.publish(
                    Topics.TRAJECTORY_COMPLETED,
                    {
                        'trajectory_name': self.status.current_trajectory,
                        'duration': self.current_time
                    },
                    MessagePriority.HIGH
                )
                
                return
            
            # 输出位置指令
            if self.position_callback:
                # 转换为整数位置
                positions = [int(round(pos)) for pos in current_point.positions]
                self.position_callback(positions)
            
            # 发布实时状态
            self.message_bus.publish(
                Topics.TRAJECTORY_POINT,
                {
                    'timestamp': current_point.timestamp,
                    'positions': current_point.positions,
                    'velocities': current_point.velocities,
                    'accelerations': current_point.accelerations
                },
                MessagePriority.LOW
            )
            
            # 更新状态回调
            if self.status_callback:
                self.status_callback(self.get_status())
                
        except Exception as e:
            logger.error(f"控制步骤异常: {e}")
            self.state = InterpolatorState.ERROR
            self.status.last_error = str(e)
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.state == InterpolatorState.RUNNING
    
    def is_idle(self) -> bool:
        """检查是否空闲"""
        return self.state == InterpolatorState.IDLE
    
    def get_control_frequency(self) -> float:
        """获取实际控制频率"""
        if len(self.loop_times) > 1:
            avg_period = sum(self.loop_times) / len(self.loop_times)
            return 1.0 / avg_period if avg_period > 0 else 0.0
        return 0.0


# 全局插值引擎实例
_interpolator = None


def get_interpolator() -> Interpolator:
    """获取全局插值引擎实例"""
    global _interpolator
    if _interpolator is None:
        _interpolator = Interpolator()
    return _interpolator