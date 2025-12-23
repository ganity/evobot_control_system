"""
串口管理器

功能：
- 串口扫描和连接管理
- 数据发送和接收
- 错误处理和自动重连
- 缓冲区管理
- 连接状态监控
"""

import serial
import serial.tools.list_ports
import threading
import queue
import time
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger, log_performance
from utils.message_bus import get_message_bus, Topics, MessagePriority

logger = get_logger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class SerialConfig:
    """串口配置"""
    port: str
    baudrate: int = 1000000
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 0.1
    buffer_size: int = 12000


class SerialManager:
    """串口管理器"""
    
    def __init__(self, config: Optional[SerialConfig] = None):
        """
        初始化串口管理器
        
        Args:
            config: 串口配置
        """
        self.config = config or SerialConfig(port="COM3")
        self.serial_port: Optional[serial.Serial] = None
        self.connection_state = ConnectionState.DISCONNECTED
        
        # 线程控制
        self.running = False
        self.receive_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 数据队列
        self.send_queue = queue.Queue(maxsize=100)
        self.receive_queue = queue.Queue(maxsize=1000)
        
        # 回调函数
        self.data_received_callback: Optional[Callable[[bytes], None]] = None
        self.connection_changed_callback: Optional[Callable[[ConnectionState], None]] = None
        
        # 统计信息
        self.statistics = {
            'bytes_sent': 0,
            'bytes_received': 0,
            'send_errors': 0,
            'receive_errors': 0,
            'reconnect_count': 0,
            'last_activity': 0
        }
        
        # 锁
        self.lock = threading.RLock()
        
        # 消息总线
        self.message_bus = get_message_bus()
        
    @staticmethod
    def scan_ports() -> List[Dict[str, str]]:
        """
        扫描可用串口
        
        Returns:
            串口信息列表
        """
        ports = []
        try:
            for port_info in serial.tools.list_ports.comports():
                port_data = {
                    'device': port_info.device,
                    'name': port_info.name or 'Unknown',
                    'description': port_info.description or 'No description',
                    'manufacturer': port_info.manufacturer or 'Unknown',
                    'vid': port_info.vid,
                    'pid': port_info.pid,
                    'serial_number': port_info.serial_number
                }
                ports.append(port_data)
                
            logger.info(f"扫描到 {len(ports)} 个串口")
            return ports
            
        except Exception as e:
            logger.error(f"扫描串口失败: {e}")
            return []
    
    def connect(self, port: Optional[str] = None, baudrate: Optional[int] = None) -> bool:
        """
        连接串口
        
        Args:
            port: 串口名称
            baudrate: 波特率
            
        Returns:
            是否连接成功
        """
        with self.lock:
            if self.connection_state == ConnectionState.CONNECTED:
                logger.warning("串口已连接")
                return True
            
            # 更新配置
            if port:
                self.config.port = port
            if baudrate:
                self.config.baudrate = baudrate
            
            self._set_connection_state(ConnectionState.CONNECTING)
            
            try:
                # 关闭现有连接
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.close()
                
                # 创建串口连接
                self.serial_port = serial.Serial(
                    port=self.config.port,
                    baudrate=self.config.baudrate,
                    bytesize=self.config.bytesize,
                    parity=self.config.parity,
                    stopbits=self.config.stopbits,
                    timeout=self.config.timeout
                )
                
                # 设置缓冲区大小
                if hasattr(self.serial_port, 'set_buffer_size'):
                    self.serial_port.set_buffer_size(
                        rx_size=self.config.buffer_size,
                        tx_size=self.config.buffer_size
                    )
                
                # 启动工作线程
                self.running = True
                self._start_threads()
                
                self._set_connection_state(ConnectionState.CONNECTED)
                logger.info(f"串口连接成功: {self.config.port} @ {self.config.baudrate}")
                
                # 发布连接事件
                self.message_bus.publish(
                    Topics.ROBOT_CONNECTED,
                    {'port': self.config.port, 'baudrate': self.config.baudrate},
                    MessagePriority.HIGH
                )
                
                return True
                
            except Exception as e:
                self._set_connection_state(ConnectionState.ERROR)
                logger.error(f"串口连接失败: {e}")
                
                # 发布错误事件
                self.message_bus.publish(
                    Topics.ROBOT_ERROR,
                    {'type': 'connection_failed', 'error': str(e)},
                    MessagePriority.HIGH
                )
                
                return False
    
    def disconnect(self) -> None:
        """断开串口连接"""
        with self.lock:
            logger.info("断开串口连接")
            
            # 停止线程
            self.running = False
            
            # 等待线程结束
            if self.receive_thread and self.receive_thread.is_alive():
                self.receive_thread.join(timeout=1.0)
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=1.0)
            
            # 关闭串口
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except Exception as e:
                    logger.error(f"关闭串口失败: {e}")
            
            self.serial_port = None
            self._set_connection_state(ConnectionState.DISCONNECTED)
            
            # 清空队列
            self._clear_queues()
            
            # 发布断开事件
            self.message_bus.publish(
                Topics.ROBOT_DISCONNECTED,
                {'port': self.config.port},
                MessagePriority.NORMAL
            )
    
    @log_performance
    def send_data(self, data: bytes) -> bool:
        """
        发送数据
        
        Args:
            data: 要发送的数据
            
        Returns:
            是否发送成功
        """
        if self.connection_state != ConnectionState.CONNECTED:
            logger.warning("串口未连接，无法发送数据")
            return False
        
        try:
            # 将数据放入发送队列
            self.send_queue.put_nowait(data)
            return True
        except queue.Full:
            logger.warning("发送队列已满，丢弃数据")
            self.statistics['send_errors'] += 1
            return False
    
    def receive_data(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        接收数据
        
        Args:
            timeout: 超时时间
            
        Returns:
            接收到的数据
        """
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def set_data_received_callback(self, callback: Callable[[bytes], None]) -> None:
        """设置数据接收回调"""
        self.data_received_callback = callback
    
    def set_connection_changed_callback(self, callback: Callable[[ConnectionState], None]) -> None:
        """设置连接状态变化回调"""
        self.connection_changed_callback = callback
    
    def get_connection_state(self) -> ConnectionState:
        """获取连接状态"""
        return self.connection_state
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.statistics.copy()
            stats['connection_state'] = self.connection_state.value
            stats['send_queue_size'] = self.send_queue.qsize()
            stats['receive_queue_size'] = self.receive_queue.qsize()
            return stats
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection_state == ConnectionState.CONNECTED
    
    def _start_threads(self) -> None:
        """启动工作线程"""
        # 接收线程
        self.receive_thread = threading.Thread(
            target=self._receive_worker,
            name="SerialReceive",
            daemon=True
        )
        self.receive_thread.start()
        
        # 监控线程
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="SerialMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.debug("串口工作线程已启动")
    
    def _receive_worker(self) -> None:
        """接收数据工作线程"""
        logger.debug("串口接收线程启动")
        
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                # 检查是否有数据要发送
                self._process_send_queue()
                
                # 接收数据
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        self._process_received_data(data)
                
                time.sleep(0.001)  # 1ms
                
            except Exception as e:
                logger.error(f"接收数据错误: {e}")
                self.statistics['receive_errors'] += 1
                
                # 如果是严重错误，尝试重连
                if not self.serial_port.is_open:
                    self._handle_connection_lost()
                    break
        
        logger.debug("串口接收线程退出")
    
    def _monitor_worker(self) -> None:
        """连接监控工作线程"""
        logger.debug("串口监控线程启动")
        
        while self.running:
            try:
                # 检查连接状态
                if self.serial_port and not self.serial_port.is_open:
                    self._handle_connection_lost()
                
                # 检查活动状态
                current_time = time.time()
                if (current_time - self.statistics['last_activity'] > 5.0 and 
                    self.connection_state == ConnectionState.CONNECTED):
                    logger.debug("串口连接空闲")
                
                time.sleep(1.0)  # 1秒检查一次
                
            except Exception as e:
                logger.error(f"连接监控错误: {e}")
        
        logger.debug("串口监控线程退出")
    
    def _process_send_queue(self) -> None:
        """处理发送队列"""
        try:
            while not self.send_queue.empty():
                data = self.send_queue.get_nowait()
                self.serial_port.write(data)
                self.statistics['bytes_sent'] += len(data)
                self.statistics['last_activity'] = time.time()
                logger.debug(f"发送数据: {len(data)} 字节")
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"发送数据错误: {e}")
            self.statistics['send_errors'] += 1
    
    def _process_received_data(self, data: bytes) -> None:
        """处理接收到的数据"""
        self.statistics['bytes_received'] += len(data)
        self.statistics['last_activity'] = time.time()
        
        logger.debug(f"接收数据: {len(data)} 字节")
        
        # 放入接收队列
        try:
            self.receive_queue.put_nowait(data)
        except queue.Full:
            # 队列满了，丢弃最老的数据
            try:
                self.receive_queue.get_nowait()
                self.receive_queue.put_nowait(data)
            except queue.Empty:
                pass
        
        # 调用回调函数
        if self.data_received_callback:
            try:
                self.data_received_callback(data)
            except Exception as e:
                logger.error(f"数据接收回调错误: {e}")
    
    def _handle_connection_lost(self) -> None:
        """处理连接丢失"""
        logger.warning("检测到连接丢失")
        self._set_connection_state(ConnectionState.RECONNECTING)
        
        # 发布连接丢失事件
        self.message_bus.publish(
            Topics.ROBOT_DISCONNECTED,
            {'port': self.config.port, 'reason': 'connection_lost'},
            MessagePriority.HIGH
        )
        
        # 尝试重连
        self._attempt_reconnect()
    
    def _attempt_reconnect(self) -> None:
        """尝试重连"""
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts and self.running:
            attempt += 1
            logger.info(f"尝试重连 ({attempt}/{max_attempts})")
            
            try:
                time.sleep(1.0)  # 等待1秒
                
                if self.serial_port:
                    self.serial_port.close()
                
                # 重新连接
                self.serial_port = serial.Serial(
                    port=self.config.port,
                    baudrate=self.config.baudrate,
                    bytesize=self.config.bytesize,
                    parity=self.config.parity,
                    stopbits=self.config.stopbits,
                    timeout=self.config.timeout
                )
                
                if hasattr(self.serial_port, 'set_buffer_size'):
                    self.serial_port.set_buffer_size(
                        rx_size=self.config.buffer_size,
                        tx_size=self.config.buffer_size
                    )
                
                self._set_connection_state(ConnectionState.CONNECTED)
                self.statistics['reconnect_count'] += 1
                
                logger.info("重连成功")
                
                # 发布重连成功事件
                self.message_bus.publish(
                    Topics.ROBOT_CONNECTED,
                    {'port': self.config.port, 'reconnected': True},
                    MessagePriority.HIGH
                )
                
                return
                
            except Exception as e:
                logger.error(f"重连失败 ({attempt}/{max_attempts}): {e}")
        
        # 重连失败
        logger.error("重连失败，放弃重连")
        self._set_connection_state(ConnectionState.ERROR)
        
        # 发布重连失败事件
        self.message_bus.publish(
            Topics.ROBOT_ERROR,
            {'type': 'reconnect_failed', 'port': self.config.port},
            MessagePriority.HIGH
        )
    
    def _set_connection_state(self, state: ConnectionState) -> None:
        """设置连接状态"""
        if self.connection_state != state:
            old_state = self.connection_state
            self.connection_state = state
            
            logger.info(f"连接状态变化: {old_state.value} -> {state.value}")
            
            # 调用回调函数
            if self.connection_changed_callback:
                try:
                    self.connection_changed_callback(state)
                except Exception as e:
                    logger.error(f"连接状态回调错误: {e}")
    
    def _clear_queues(self) -> None:
        """清空队列"""
        while not self.send_queue.empty():
            try:
                self.send_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.receive_queue.empty():
            try:
                self.receive_queue.get_nowait()
            except queue.Empty:
                break
    
    def __del__(self):
        """析构函数"""
        self.disconnect()


# 全局串口管理器实例
_serial_manager = None


def get_serial_manager() -> SerialManager:
    """获取全局串口管理器实例"""
    global _serial_manager
    if _serial_manager is None:
        _serial_manager = SerialManager()
    return _serial_manager