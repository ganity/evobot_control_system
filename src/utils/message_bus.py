"""
消息总线

功能：
- 发布-订阅模式的消息传递
- 线程安全的消息队列
- 事件分发机制
- 消息过滤和路由
"""

import threading
import queue
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time
import weakref

from .logger import get_logger

logger = get_logger(__name__)


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """消息数据结构"""

    topic: str
    data: Any
    timestamp: float
    priority: MessagePriority = MessagePriority.NORMAL
    sender: Optional[str] = None
    message_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.message_id is None:
            import uuid
            self.message_id = str(uuid.uuid4())[:8]
    
    def __lt__(self, other):
        """定义小于比较，用于优先级队列排序"""
        if not isinstance(other, Message):
            return NotImplemented
        # 按时间戳排序，如果时间戳相同则按消息ID排序
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.message_id < other.message_id
    
    def __eq__(self, other):
        """定义相等比较"""
        if not isinstance(other, Message):
            return NotImplemented
        return (self.topic == other.topic and 
                self.timestamp == other.timestamp and 
                self.message_id == other.message_id)


class MessageBus:
    """消息总线"""

    def __init__(self, max_queue_size: int = 1000):
        """
        初始化消息总线

        Args:
            max_queue_size: 消息队列最大大小
        """
        self.max_queue_size = max_queue_size
        self.subscribers: Dict[str, List[weakref.WeakMethod]] = {}
        self.message_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.running = False
        self.worker_thread = None
        self.lock = threading.RLock()
        self.message_filters: Dict[str, List[Callable[[Message], bool]]] = {}
        self.statistics = {
            "messages_sent": 0,
            "messages_processed": 0,
            "messages_dropped": 0,
            "subscribers_count": 0,
        }

    def start(self):
        """启动消息总线"""
        with self.lock:
            if not self.running:
                self.running = True
                self.worker_thread = threading.Thread(
                    target=self._message_worker, daemon=True
                )
                self.worker_thread.start()
                logger.info("消息总线已启动")

    def stop(self):
        """停止消息总线"""
        with self.lock:
            if self.running:
                self.running = False
                # 发送停止信号
                self.message_queue.put(
                    (MessagePriority.CRITICAL.value, time.time(), None)
                )
                if self.worker_thread:
                    self.worker_thread.join(timeout=1.0)
                logger.info("消息总线已停止")

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """
        订阅主题

        Args:
            topic: 主题名称
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        try:
            with self.lock:
                if topic not in self.subscribers:
                    self.subscribers[topic] = []

                # 使用弱引用避免内存泄漏
                weak_callback = (
                    weakref.WeakMethod(callback)
                    if hasattr(callback, "__self__")
                    else weakref.ref(callback)
                )
                self.subscribers[topic].append(weak_callback)
                self.statistics["subscribers_count"] += 1

                logger.debug(f"订阅主题: {topic}, 回调: {callback}")
                return True

        except Exception as e:
            logger.error(f"订阅主题失败: {topic}, 错误: {e}")
            return False

    def unsubscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """
        取消订阅主题

        Args:
            topic: 主题名称
            callback: 回调函数

        Returns:
            是否取消成功
        """
        try:
            with self.lock:
                if topic in self.subscribers:
                    # 查找并移除回调
                    callbacks = self.subscribers[topic]
                    for i, weak_callback in enumerate(callbacks):
                        if weak_callback() == callback:
                            callbacks.pop(i)
                            self.statistics["subscribers_count"] -= 1
                            logger.debug(f"取消订阅主题: {topic}, 回调: {callback}")

                            # 如果没有订阅者了，删除主题
                            if not callbacks:
                                del self.subscribers[topic]
                            return True

                logger.warning(f"未找到订阅: {topic}, 回调: {callback}")
                return False

        except Exception as e:
            logger.error(f"取消订阅失败: {topic}, 错误: {e}")
            return False

    def publish(
        self,
        topic: str,
        data: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        sender: Optional[str] = None,
    ) -> bool:
        """
        发布消息

        Args:
            topic: 主题名称
            data: 消息数据
            priority: 消息优先级
            sender: 发送者标识

        Returns:
            是否发布成功
        """
        try:
            message = Message(
                topic=topic,
                data=data,
                timestamp=time.time(),
                priority=priority,
                sender=sender,
            )

            # 应用消息过滤器
            if not self._apply_filters(message):
                logger.debug(f"消息被过滤器拒绝: {topic}")
                return False

            # 将消息放入队列（优先级队列）
            priority_value = priority.value
            try:
                self.message_queue.put_nowait(
                    (priority_value, message.timestamp, message)
                )
                self.statistics["messages_sent"] += 1
                logger.debug(f"发布消息: {topic}, 优先级: {priority.name}")
                return True
            except queue.Full:
                self.statistics["messages_dropped"] += 1
                logger.warning(f"消息队列已满，丢弃消息: {topic}")
                return False

        except Exception as e:
            logger.error(f"发布消息失败: {topic}, 错误: {e}")
            return False

    def add_filter(self, topic: str, filter_func: Callable[[Message], bool]):
        """
        添加消息过滤器

        Args:
            topic: 主题名称
            filter_func: 过滤函数，返回True表示通过
        """
        with self.lock:
            if topic not in self.message_filters:
                self.message_filters[topic] = []
            self.message_filters[topic].append(filter_func)
            logger.debug(f"添加过滤器: {topic}")

    def remove_filter(self, topic: str, filter_func: Callable[[Message], bool]):
        """
        移除消息过滤器

        Args:
            topic: 主题名称
            filter_func: 过滤函数
        """
        with self.lock:
            if topic in self.message_filters:
                try:
                    self.message_filters[topic].remove(filter_func)
                    logger.debug(f"移除过滤器: {topic}")
                except ValueError:
                    logger.warning(f"过滤器不存在: {topic}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.statistics.copy()
            stats["queue_size"] = self.message_queue.qsize()
            stats["topics_count"] = len(self.subscribers)
            return stats

    def _message_worker(self):
        """消息处理工作线程"""
        logger.debug("消息处理线程启动")

        while self.running:
            try:
                # 获取消息（阻塞等待）
                priority, timestamp, message = self.message_queue.get(timeout=0.1)

                # 检查停止信号
                if message is None:
                    break

                # 处理消息
                self._dispatch_message(message)
                self.statistics["messages_processed"] += 1

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"消息处理错误: {e}")

        logger.debug("消息处理线程退出")

    def _dispatch_message(self, message: Message):
        """
        分发消息给订阅者

        Args:
            message: 消息对象
        """
        topic = message.topic

        with self.lock:
            if topic not in self.subscribers:
                logger.debug(f"没有订阅者: {topic}")
                return

            # 清理失效的弱引用
            valid_callbacks = []
            for weak_callback in self.subscribers[topic]:
                callback = weak_callback()
                if callback is not None:
                    valid_callbacks.append(weak_callback)
                else:
                    self.statistics["subscribers_count"] -= 1

            self.subscribers[topic] = valid_callbacks

            # 如果没有有效订阅者，删除主题
            if not valid_callbacks:
                del self.subscribers[topic]
                return

        # 调用订阅者回调
        for weak_callback in valid_callbacks:
            try:
                callback = weak_callback()
                if callback is not None:
                    callback(message)
            except Exception as e:
                logger.error(f"回调函数执行错误: {e}, 主题: {topic}")

    def _apply_filters(self, message: Message) -> bool:
        """
        应用消息过滤器

        Args:
            message: 消息对象

        Returns:
            是否通过过滤
        """
        topic = message.topic

        with self.lock:
            if topic in self.message_filters:
                for filter_func in self.message_filters[topic]:
                    try:
                        if not filter_func(message):
                            return False
                    except Exception as e:
                        logger.error(f"过滤器执行错误: {e}, 主题: {topic}")
                        return False

        return True


# 全局消息总线实例
_message_bus = None


def get_message_bus() -> MessageBus:
    """获取全局消息总线实例"""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
        _message_bus.start()
    return _message_bus


# 便捷函数
def publish(
    topic: str,
    data: Any,
    priority: MessagePriority = MessagePriority.NORMAL,
    sender: Optional[str] = None,
) -> bool:
    """发布消息"""
    return get_message_bus().publish(topic, data, priority, sender)


def subscribe(topic: str, callback: Callable[[Message], None]) -> bool:
    """订阅主题"""
    return get_message_bus().subscribe(topic, callback)


def unsubscribe(topic: str, callback: Callable[[Message], None]) -> bool:
    """取消订阅"""
    return get_message_bus().unsubscribe(topic, callback)


# 常用主题定义
class Topics:
    """消息主题定义"""

    # 机器人状态
    ROBOT_STATE = "robot/state"
    ROBOT_CONNECTED = "robot/connected"
    ROBOT_DISCONNECTED = "robot/disconnected"
    ROBOT_ERROR = "robot/error"

    # 控制指令
    CONTROL_COMMAND = "control/command"
    CONTROL_MODE_CHANGED = "control/mode_changed"
    EMERGENCY_STOP = "control/emergency_stop"
    
    # 运动控制消息
    MOTION_START = "motion/start"
    MOTION_STOP = "motion/stop"
    MOTION_PAUSE = "motion/pause"
    MOTION_RESUME = "motion/resume"

    # 轨迹相关
    TRAJECTORY_UPDATE = "trajectory/update"
    TRAJECTORY_COMPLETE = "trajectory/complete"
    TRAJECTORY_ERROR = "trajectory/error"
    TRAJECTORY_STARTED = "trajectory/started"
    TRAJECTORY_STOPPED = "trajectory/stopped"
    TRAJECTORY_COMPLETED = "trajectory/completed"
    TRAJECTORY_POINT = "trajectory/point"
    
    # 示教模式相关
    TEACHING_STARTED = "teaching/started"
    TEACHING_STOPPED = "teaching/stopped"
    TEACHING_MODE_CHANGED = "teaching/mode_changed"
    TEACHING_PLAYBACK_STARTED = "teaching/playback_started"
    TEACHING_PLAYBACK_STOPPED = "teaching/playback_stopped"
    KEYFRAME_ADDED = "teaching/keyframe_added"
    KEYFRAME_EDITED = "teaching/keyframe_edited"
    SEQUENCE_OPTIMIZED = "teaching/sequence_optimized"
    DRAG_TEACHING_STARTED = "teaching/drag_started"
    DRAG_TEACHING_STOPPED = "teaching/drag_stopped"
    
    # 速度控制相关
    VELOCITY_CHANGED = "velocity/changed"
    VELOCITY_PRESET_APPLIED = "velocity/preset_applied"
    
    # 标定相关
    CALIBRATION_STARTED = "calibration/started"
    CALIBRATION_COMPLETED = "calibration/completed"
    CALIBRATION_POINT_ADDED = "calibration/point_added"
    
    # 数据录制相关
    RECORDING_STARTED = "recording/started"
    RECORDING_STOPPED = "recording/stopped"
    RECORDING_PAUSED = "recording/paused"
    RECORDING_RESUMED = "recording/resumed"
    
    # 数据回放相关
    PLAYBACK_STARTED = "playback/started"
    PLAYBACK_STOPPED = "playback/stopped"
    PLAYBACK_PAUSED = "playback/paused"
    PLAYBACK_RESUMED = "playback/resumed"
    PLAYBACK_COMPLETED = "playback/completed"
    PLAYBACK_POSITION_UPDATE = "playback/position_update"
    
    # 脚本模式相关
    SCRIPT_STARTED = "script/started"
    SCRIPT_STOPPED = "script/stopped"
    SCRIPT_COMPLETED = "script/completed"
    SCRIPT_ERROR = "script/error"
    SCRIPT_STATE_CHANGED = "script/state_changed"

    # UI事件
    UI_UPDATE = "ui/update"
    UI_EVENT = "ui/event"

    # 系统事件
    SYSTEM_LOG = "system/log"
    SYSTEM_SHUTDOWN = "system/shutdown"
    
    # 标定事件
    CALIBRATION_UPDATED = "calibration/updated"
    CALIBRATION_STARTED = "calibration/started"
    CALIBRATION_COMPLETED = "calibration/completed"
    
    # 速度控制
    VELOCITY_CHANGED = "velocity/changed"
    VELOCITY_PRESET_APPLIED = "velocity/preset_applied"
    
    # 数据记录
    RECORDING_STARTED = "recording/started"
    RECORDING_STOPPED = "recording/stopped"
    RECORDING_SAVED = "recording/saved"
