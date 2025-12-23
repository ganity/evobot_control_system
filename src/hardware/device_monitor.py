"""
设备监控器

功能：
- 监控机器人实时状态
- 检测异常情况和错误
- 触发告警和保护机制
- 统计通信质量
- 健康状态评估
"""

import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import queue

from .serial_manager import SerialManager, ConnectionState
from .protocol_handler import ProtocolHandler, RobotStatus, BoardID, FrameType
from utils.logger import get_logger, log_performance
from utils.message_bus import get_message_bus, Topics, MessagePriority, Message

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"             # 良好
    WARNING = "warning"       # 警告
    ERROR = "error"           # 错误
    CRITICAL = "critical"     # 严重


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警信息"""
    level: AlertLevel
    message: str
    timestamp: float
    source: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class JointHealth:
    """关节健康状态"""
    joint_id: int
    position: int = 0
    velocity: int = 0
    current: int = 0
    temperature: int = 25
    status: HealthStatus = HealthStatus.GOOD
    alerts: List[Alert] = field(default_factory=list)
    last_update: float = 0.0


@dataclass
class CommunicationStats:
    """通信统计"""
    total_sent: int = 0
    total_received: int = 0
    success_rate: float = 100.0
    average_latency: float = 0.0
    packet_loss_rate: float = 0.0
    last_activity: float = 0.0


class DeviceMonitor:
    """设备监控器"""
    
    def __init__(self, serial_manager: SerialManager, protocol_handler: ProtocolHandler):
        """
        初始化设备监控器
        
        Args:
            serial_manager: 串口管理器
            protocol_handler: 协议处理器
        """
        self.serial_manager = serial_manager
        self.protocol_handler = protocol_handler
        self.message_bus = get_message_bus()
        
        # 监控状态
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.query_thread: Optional[threading.Thread] = None
        
        # 关节健康状态
        self.joint_health: Dict[int, JointHealth] = {}
        for i in range(10):
            self.joint_health[i] = JointHealth(joint_id=i)
        
        # 通信统计
        self.comm_stats = CommunicationStats()
        
        # 告警队列
        self.alert_queue = queue.Queue(maxsize=100)
        
        # 配置参数
        self.config = {
            'query_interval': 0.2,       # 查询间隔 (200ms，适配50Hz硬件)
            'monitor_interval': 1.0,     # 监控间隔 (1s)
            'timeout_threshold': 5.0,    # 超时阈值 (5s)
            'current_threshold': 1500,   # 电流阈值 (1500mA)
            'temperature_threshold': 60, # 温度阈值 (60°C)
            'position_tolerance': 50,    # 位置容差 (50单位)
        }
        
        # 回调函数
        self.alert_callback: Optional[Callable[[Alert], None]] = None
        self.status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # 订阅消息
        self.message_bus.subscribe(Topics.ROBOT_STATE, self._on_robot_state)
        self.message_bus.subscribe(Topics.ROBOT_CONNECTED, self._on_robot_connected)
        self.message_bus.subscribe(Topics.ROBOT_DISCONNECTED, self._on_robot_disconnected)
        
        # 设置串口数据接收回调
        self.serial_manager.set_data_received_callback(self._on_serial_data_received)
        
        logger.info("设备监控器初始化完成")
    
    def start(self) -> None:
        """启动监控"""
        if self.running:
            logger.warning("设备监控器已在运行")
            return
        
        self.running = True
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="DeviceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        # 启动查询线程
        self.query_thread = threading.Thread(
            target=self._query_worker,
            name="DeviceQuery",
            daemon=True
        )
        self.query_thread.start()
        
        logger.info("设备监控器已启动")
    
    def stop(self) -> None:
        """停止监控"""
        if not self.running:
            return
        
        self.running = False
        
        # 等待线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        if self.query_thread and self.query_thread.is_alive():
            self.query_thread.join(timeout=2.0)
        
        logger.info("设备监控器已停止")
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        获取系统健康状态
        
        Returns:
            系统健康状态信息
        """
        # 计算整体健康状态
        joint_statuses = [joint.status for joint in self.joint_health.values()]
        
        if HealthStatus.CRITICAL in joint_statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.ERROR in joint_statuses:
            overall_status = HealthStatus.ERROR
        elif HealthStatus.WARNING in joint_statuses:
            overall_status = HealthStatus.WARNING
        elif HealthStatus.GOOD in joint_statuses:
            overall_status = HealthStatus.GOOD
        else:
            overall_status = HealthStatus.EXCELLENT
        
        # 统计告警数量
        alert_counts = {level.value: 0 for level in AlertLevel}
        for joint in self.joint_health.values():
            for alert in joint.alerts:
                alert_counts[alert.level.value] += 1
        
        return {
            'overall_status': overall_status.value,
            'connection_state': self.serial_manager.get_connection_state().value,
            'joints': {
                joint_id: {
                    'status': joint.status.value,
                    'position': joint.position,
                    'velocity': joint.velocity,
                    'current': joint.current,
                    'temperature': joint.temperature,
                    'alert_count': len(joint.alerts),
                    'last_update': joint.last_update
                }
                for joint_id, joint in self.joint_health.items()
            },
            'communication': {
                'success_rate': self.comm_stats.success_rate,
                'average_latency': self.comm_stats.average_latency,
                'packet_loss_rate': self.comm_stats.packet_loss_rate,
                'last_activity': self.comm_stats.last_activity
            },
            'alerts': alert_counts,
            'timestamp': time.time()
        }
    
    def get_joint_health(self, joint_id: int) -> Optional[JointHealth]:
        """获取指定关节的健康状态"""
        return self.joint_health.get(joint_id)
    
    def get_recent_alerts(self, count: int = 10) -> List[Alert]:
        """获取最近的告警"""
        alerts = []
        temp_queue = queue.Queue()
        
        # 从队列中取出告警
        while not self.alert_queue.empty() and len(alerts) < count:
            try:
                alert = self.alert_queue.get_nowait()
                alerts.append(alert)
                temp_queue.put(alert)
            except queue.Empty:
                break
        
        # 将告警放回队列
        while not temp_queue.empty():
            try:
                self.alert_queue.put_nowait(temp_queue.get_nowait())
            except queue.Full:
                break
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def set_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """设置告警回调函数"""
        self.alert_callback = callback
    
    def set_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """设置状态回调函数"""
        self.status_callback = callback
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置参数"""
        self.config.update(config)
        logger.info(f"监控配置已更新: {config}")
    
    def _monitor_worker(self) -> None:
        """监控工作线程"""
        logger.debug("设备监控线程启动")
        
        while self.running:
            try:
                # 检查关节健康状态
                self._check_joint_health()
                
                # 检查通信质量
                self._check_communication_health()
                
                # 检查超时
                self._check_timeouts()
                
                # 更新统计信息
                self._update_statistics()
                
                # 调用状态回调
                if self.status_callback:
                    try:
                        status = self.get_system_health()
                        self.status_callback(status)
                    except Exception as e:
                        logger.error(f"状态回调错误: {e}")
                
                time.sleep(self.config['monitor_interval'])
                
            except Exception as e:
                logger.error(f"监控线程错误: {e}")
                time.sleep(1.0)
        
        logger.debug("设备监控线程退出")
    
    def _query_worker(self) -> None:
        """查询工作线程 - 200ms查询间隔，适配50Hz硬件响应频率"""
        logger.debug("设备查询线程启动")
        
        query_cycle = 0  # 查询周期计数器
        
        while self.running:
            try:
                if self.serial_manager.is_connected():
                    # 每200ms轮询查询，交替查询手臂和手腕
                    # 硬件响应频率50Hz(20ms)，200ms查询频率合适
                    if query_cycle % 2 == 0:
                        # 查询手臂状态 (肩部+肘部)
                        query_cmd = self.protocol_handler.encode_query_command(BoardID.ARM_BOARD)
                        success = self.serial_manager.send_data(query_cmd)
                        if success:
                            logger.debug("发送手臂状态查询")
                        else:
                            logger.debug("手臂状态查询发送失败，队列可能已满")
                    else:
                        # 查询手腕状态 (手指+手腕)
                        query_cmd = self.protocol_handler.encode_query_command(BoardID.WRIST_BOARD)
                        success = self.serial_manager.send_data(query_cmd)
                        if success:
                            logger.debug("发送手腕状态查询")
                        else:
                            logger.debug("手腕状态查询发送失败，队列可能已满")
                    
                    query_cycle += 1
                
                # 使用200ms间隔，适配硬件50Hz响应频率
                time.sleep(0.2)  # 200ms
                
            except Exception as e:
                logger.error(f"查询线程错误: {e}")
                time.sleep(0.5)  # 错误时等待500ms
        
        logger.debug("设备查询线程退出")
    
    def _check_joint_health(self) -> None:
        """检查关节健康状态"""
        current_time = time.time()
        
        for joint_id, joint in self.joint_health.items():
            # 清除过期告警
            joint.alerts = [alert for alert in joint.alerts 
                          if current_time - alert.timestamp < 300]  # 5分钟
            
            # 检查电流
            if joint.current > self.config['current_threshold']:
                self._add_alert(
                    joint_id,
                    AlertLevel.WARNING,
                    f"关节{joint_id}电流过高: {joint.current}mA",
                    {'current': joint.current, 'threshold': self.config['current_threshold']}
                )
                joint.status = HealthStatus.WARNING
            
            # 检查温度
            if joint.temperature > self.config['temperature_threshold']:
                self._add_alert(
                    joint_id,
                    AlertLevel.ERROR,
                    f"关节{joint_id}温度过高: {joint.temperature}°C",
                    {'temperature': joint.temperature, 'threshold': self.config['temperature_threshold']}
                )
                joint.status = HealthStatus.ERROR
            
            # 检查数据更新时间
            if current_time - joint.last_update > self.config['timeout_threshold']:
                self._add_alert(
                    joint_id,
                    AlertLevel.WARNING,
                    f"关节{joint_id}数据超时",
                    {'last_update': joint.last_update, 'timeout': self.config['timeout_threshold']}
                )
                joint.status = HealthStatus.WARNING
            
            # 如果没有告警，状态为良好
            if not joint.alerts:
                joint.status = HealthStatus.GOOD
    
    def _check_communication_health(self) -> None:
        """检查通信健康状态"""
        serial_stats = self.serial_manager.get_statistics()
        
        # 更新通信统计
        self.comm_stats.total_sent = serial_stats['bytes_sent']
        self.comm_stats.total_received = serial_stats['bytes_received']
        self.comm_stats.last_activity = serial_stats['last_activity']
        
        # 计算成功率
        total_operations = serial_stats['bytes_sent'] + serial_stats['bytes_received']
        total_errors = serial_stats['send_errors'] + serial_stats['receive_errors']
        
        if total_operations > 0:
            self.comm_stats.success_rate = ((total_operations - total_errors) / total_operations) * 100
        
        # 检查通信质量
        if self.comm_stats.success_rate < 95.0:
            self._add_system_alert(
                AlertLevel.WARNING,
                f"通信成功率低: {self.comm_stats.success_rate:.1f}%",
                {'success_rate': self.comm_stats.success_rate}
            )
        
        if self.comm_stats.success_rate < 90.0:
            self._add_system_alert(
                AlertLevel.ERROR,
                f"通信质量严重下降: {self.comm_stats.success_rate:.1f}%",
                {'success_rate': self.comm_stats.success_rate}
            )
    
    def _check_timeouts(self) -> None:
        """检查超时情况"""
        current_time = time.time()
        
        # 检查整体通信超时
        if (current_time - self.comm_stats.last_activity > self.config['timeout_threshold'] and
            self.serial_manager.is_connected()):
            self._add_system_alert(
                AlertLevel.WARNING,
                "通信超时",
                {'last_activity': self.comm_stats.last_activity, 'timeout': self.config['timeout_threshold']}
            )
    
    def _update_statistics(self) -> None:
        """更新统计信息"""
        # 这里可以添加更多统计信息的计算
        pass
    
    def _add_alert(self, joint_id: int, level: AlertLevel, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """添加关节告警"""
        alert = Alert(
            level=level,
            message=message,
            timestamp=time.time(),
            source=f"joint_{joint_id}",
            data=data
        )
        
        # 添加到关节告警列表
        joint = self.joint_health.get(joint_id)
        if joint:
            # 避免重复告警
            existing_alerts = [a for a in joint.alerts if a.message == message]
            if not existing_alerts:
                joint.alerts.append(alert)
        
        # 添加到全局告警队列
        try:
            self.alert_queue.put_nowait(alert)
        except queue.Full:
            # 队列满了，移除最老的告警
            try:
                self.alert_queue.get_nowait()
                self.alert_queue.put_nowait(alert)
            except queue.Empty:
                pass
        
        # 调用告警回调
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"告警回调错误: {e}")
        
        # 发布告警事件
        self.message_bus.publish(
            Topics.ROBOT_ERROR,
            {
                'type': 'joint_alert',
                'joint_id': joint_id,
                'level': level.value,
                'message': message,
                'data': data
            },
            MessagePriority.HIGH if level in [AlertLevel.ERROR, AlertLevel.CRITICAL] else MessagePriority.NORMAL
        )
        
        logger.warning(f"关节{joint_id}告警 [{level.value}]: {message}")
    
    def _add_system_alert(self, level: AlertLevel, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """添加系统告警"""
        alert = Alert(
            level=level,
            message=message,
            timestamp=time.time(),
            source="system",
            data=data
        )
        
        # 添加到全局告警队列
        try:
            self.alert_queue.put_nowait(alert)
        except queue.Full:
            try:
                self.alert_queue.get_nowait()
                self.alert_queue.put_nowait(alert)
            except queue.Empty:
                pass
        
        # 调用告警回调
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"告警回调错误: {e}")
        
        # 发布告警事件
        self.message_bus.publish(
            Topics.ROBOT_ERROR,
            {
                'type': 'system_alert',
                'level': level.value,
                'message': message,
                'data': data
            },
            MessagePriority.HIGH if level in [AlertLevel.ERROR, AlertLevel.CRITICAL] else MessagePriority.NORMAL
        )
        
        logger.warning(f"系统告警 [{level.value}]: {message}")
    
    def _on_robot_state(self, message: Message) -> None:
        """处理机器人状态更新"""
        try:
            data = message.data
            if isinstance(data, dict) and 'type' in data:
                # 处理解析后的帧数据
                if data['type'] == 'status' and 'data' in data and data['data'] is not None:
                    robot_status = data['data']
                    
                    # 更新关节状态
                    for joint_data in robot_status.joints:
                        joint_id = joint_data.joint_id
                        if joint_id in self.joint_health:
                            joint = self.joint_health[joint_id]
                            joint.position = joint_data.position
                            joint.velocity = joint_data.velocity
                            joint.current = joint_data.current
                            joint.last_update = time.time()
            
            # 兼容旧格式
            elif isinstance(data, dict) and 'type' in data:
                if data['type'] == 'finger_status':
                    # 更新手指和手腕状态 (关节0-5)
                    for joint_data in data['joints']:
                        joint_id = joint_data['id']
                        if joint_id in self.joint_health:
                            joint = self.joint_health[joint_id]
                            joint.position = joint_data['position']
                            joint.velocity = joint_data['velocity']
                            joint.current = joint_data['current']
                            joint.last_update = time.time()
                
                elif data['type'] == 'arm_status':
                    # 更新手臂状态 (关节6-9)
                    for joint_data in data['joints']:
                        joint_id = joint_data['id']
                        if joint_id in self.joint_health:
                            joint = self.joint_health[joint_id]
                            joint.position = joint_data['position']
                            joint.velocity = joint_data['velocity']
                            joint.current = joint_data['current']
                            joint.last_update = time.time()
        
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")
    
    def _on_robot_connected(self, message: Message) -> None:
        """处理机器人连接事件"""
        logger.info("机器人已连接，开始监控")
        # 重置统计信息
        self.comm_stats = CommunicationStats()
        self.comm_stats.last_activity = time.time()
    
    def _on_robot_disconnected(self, message: Message) -> None:
        """处理机器人断开事件"""
        logger.info("机器人已断开连接")
        # 添加断开告警
        self._add_system_alert(
            AlertLevel.WARNING,
            "机器人连接断开",
            message.data
        )
    
    def _on_serial_data_received(self, raw_data: bytes) -> None:
        """处理串口接收到的原始数据"""
        try:
            # 使用协议处理器解析数据
            parsed_frames = self.protocol_handler.parse_received_data(raw_data)
            
            for frame_info in parsed_frames:
                if frame_info['type'] == 'status' and frame_info['data']:
                    robot_status = frame_info['data']
                    
                    # 发布状态更新事件
                    self.message_bus.publish(
                        Topics.ROBOT_STATE,
                        {
                            'type': 'status',
                            'data': robot_status,
                            'timestamp': frame_info['timestamp']
                        },
                        MessagePriority.NORMAL
                    )
                    
                    logger.debug(f"处理状态帧: {robot_status.frame_type.name}, {len(robot_status.joints)}个关节")
        
        except Exception as e:
            logger.error(f"处理串口数据失败: {e}")
            import traceback
            traceback.print_exc()


# 全局设备监控器实例
_device_monitor = None


def get_device_monitor() -> Optional[DeviceMonitor]:
    """获取全局设备监控器实例"""
    return _device_monitor


def create_device_monitor(serial_manager: SerialManager, protocol_handler: ProtocolHandler) -> DeviceMonitor:
    """创建设备监控器实例"""
    global _device_monitor
    _device_monitor = DeviceMonitor(serial_manager, protocol_handler)
    return _device_monitor