"""
数据录制器

功能：
- 运动序列录制
- 多格式数据保存 (CSV, JSON, HDF5)
- 实时数据采集
- 数据压缩和优化
- 录制配置管理
"""

import time
import json
import csv
import threading
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import numpy as np

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority

logger = get_logger(__name__)


class RecordingFormat(Enum):
    """录制格式"""
    JSON = "json"
    CSV = "csv"
    HDF5 = "hdf5"
    BINARY = "binary"


class RecordingState(Enum):
    """录制状态"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class DataPoint:
    """数据点"""
    timestamp: float
    positions: List[int]
    velocities: List[float]
    currents: List[int]
    forces: Optional[List[float]] = None
    temperatures: Optional[List[float]] = None
    voltages: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataPoint':
        """从字典创建"""
        return cls(**data)


@dataclass
class RecordingSession:
    """录制会话"""
    name: str
    description: str
    format: RecordingFormat
    sample_rate: float  # Hz
    data_points: List[DataPoint]
    created_at: float
    duration: float
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'description': self.description,
            'format': self.format.value,
            'sample_rate': self.sample_rate,
            'data_points': [dp.to_dict() for dp in self.data_points],
            'created_at': self.created_at,
            'duration': self.duration,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecordingSession':
        """从字典创建"""
        data_points = [DataPoint.from_dict(dp_data) for dp_data in data['data_points']]
        return cls(
            name=data['name'],
            description=data['description'],
            format=RecordingFormat(data['format']),
            sample_rate=data['sample_rate'],
            data_points=data_points,
            created_at=data['created_at'],
            duration=data['duration'],
            metadata=data.get('metadata', {})
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.data_points:
            return {}
        
        # 计算位置统计
        positions_array = np.array([dp.positions for dp in self.data_points])
        velocities_array = np.array([dp.velocities for dp in self.data_points])
        currents_array = np.array([dp.currents for dp in self.data_points])
        
        return {
            'total_points': len(self.data_points),
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'position_stats': {
                'min': positions_array.min(axis=0).tolist(),
                'max': positions_array.max(axis=0).tolist(),
                'mean': positions_array.mean(axis=0).tolist(),
                'std': positions_array.std(axis=0).tolist()
            },
            'velocity_stats': {
                'min': velocities_array.min(axis=0).tolist(),
                'max': velocities_array.max(axis=0).tolist(),
                'mean': velocities_array.mean(axis=0).tolist(),
                'std': velocities_array.std(axis=0).tolist()
            },
            'current_stats': {
                'min': currents_array.min(axis=0).tolist(),
                'max': currents_array.max(axis=0).tolist(),
                'mean': currents_array.mean(axis=0).tolist(),
                'std': currents_array.std(axis=0).tolist()
            }
        }


class DataRecorder:
    """数据录制器"""
    
    def __init__(self):
        """初始化数据录制器"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        
        # 状态管理
        self.state = RecordingState.IDLE
        self.current_session: Optional[RecordingSession] = None
        
        # 录制参数
        self.sample_rate = 100.0  # 默认100Hz
        self.recording_format = RecordingFormat.JSON
        self.auto_save = True
        self.compression_enabled = True
        
        # 数据缓冲
        self.data_buffer: List[DataPoint] = []
        self.buffer_lock = threading.RLock()
        
        # 录制线程
        self.recording_thread: Optional[threading.Thread] = None
        self.recording_event = threading.Event()
        self.stop_event = threading.Event()
        
        # 数据存储
        self.recordings_dir = Path("data/recordings")
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前机器人状态
        self.current_positions = [1500] * 10
        self.current_velocities = [0.0] * 10
        self.current_currents = [0] * 10
        self.current_forces = [0.0] * 10
        self.current_temperatures = [25.0] * 10
        self.current_voltages = [12.0] * 10
        
        # 录制统计
        self.recording_start_time = 0.0
        self.total_points_recorded = 0
        
        # 订阅机器人状态更新
        self.message_bus.subscribe(Topics.ROBOT_STATE, self._on_robot_state_update)
        
        logger.info("数据录制器初始化完成")
    
    def configure_recording(self, sample_rate: float = 100.0, 
                          format: RecordingFormat = RecordingFormat.JSON,
                          auto_save: bool = True,
                          compression: bool = True) -> bool:
        """
        配置录制参数
        
        Args:
            sample_rate: 采样率 (Hz)
            format: 录制格式
            auto_save: 自动保存
            compression: 启用压缩
            
        Returns:
            是否配置成功
        """
        try:
            if self.state != RecordingState.IDLE:
                logger.warning("录制进行中，无法修改配置")
                return False
            
            self.sample_rate = sample_rate
            self.recording_format = format
            self.auto_save = auto_save
            self.compression_enabled = compression
            
            logger.info(f"录制配置已更新: 采样率={sample_rate}Hz, 格式={format.value}")
            return True
            
        except Exception as e:
            logger.error(f"配置录制参数失败: {e}")
            return False
    
    def start_recording(self, session_name: str, description: str = "") -> bool:
        """
        开始录制
        
        Args:
            session_name: 会话名称
            description: 描述
            
        Returns:
            是否成功启动
        """
        try:
            if self.state != RecordingState.IDLE:
                logger.warning("录制器不在空闲状态，无法开始录制")
                return False
            
            # 创建录制会话
            self.current_session = RecordingSession(
                name=session_name,
                description=description,
                format=self.recording_format,
                sample_rate=self.sample_rate,
                data_points=[],
                created_at=time.time(),
                duration=0.0
            )
            
            # 清空缓冲区
            with self.buffer_lock:
                self.data_buffer.clear()
            
            # 重置统计
            self.recording_start_time = time.time()
            self.total_points_recorded = 0
            
            # 启动录制线程
            self.stop_event.clear()
            self.recording_event.set()
            self.recording_thread = threading.Thread(target=self._recording_worker)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            self.state = RecordingState.RECORDING
            
            logger.info(f"开始录制数据: {session_name}, 采样率: {self.sample_rate}Hz")
            
            # 发布事件
            self.message_bus.publish(
                Topics.RECORDING_STARTED,
                {
                    'session_name': session_name,
                    'sample_rate': self.sample_rate,
                    'format': self.recording_format.value
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始录制失败: {e}")
            return False
    
    def pause_recording(self) -> bool:
        """暂停录制"""
        try:
            if self.state != RecordingState.RECORDING:
                logger.warning("当前不在录制状态")
                return False
            
            self.recording_event.clear()
            self.state = RecordingState.PAUSED
            
            logger.info("录制已暂停")
            
            # 发布事件
            self.message_bus.publish(
                Topics.RECORDING_PAUSED,
                {'session_name': self.current_session.name if self.current_session else ''},
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"暂停录制失败: {e}")
            return False
    
    def resume_recording(self) -> bool:
        """恢复录制"""
        try:
            if self.state != RecordingState.PAUSED:
                logger.warning("当前不在暂停状态")
                return False
            
            self.recording_event.set()
            self.state = RecordingState.RECORDING
            
            logger.info("录制已恢复")
            
            # 发布事件
            self.message_bus.publish(
                Topics.RECORDING_RESUMED,
                {'session_name': self.current_session.name if self.current_session else ''},
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"恢复录制失败: {e}")
            return False
    
    def stop_recording(self) -> bool:
        """停止录制"""
        try:
            if self.state not in [RecordingState.RECORDING, RecordingState.PAUSED]:
                logger.warning("当前不在录制状态")
                return False
            
            self.state = RecordingState.STOPPING
            
            # 停止录制线程
            self.stop_event.set()
            self.recording_event.set()  # 确保线程能够退出
            
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=5.0)
            
            # 处理缓冲区中的剩余数据
            self._flush_buffer()
            
            # 更新会话信息
            if self.current_session:
                self.current_session.duration = time.time() - self.recording_start_time
                self.current_session.data_points = self.data_buffer.copy()
                
                # 自动保存
                if self.auto_save:
                    self.save_session(self.current_session)
            
            self.state = RecordingState.IDLE
            
            logger.info(f"录制已停止，共录制 {self.total_points_recorded} 个数据点")
            
            # 发布事件
            self.message_bus.publish(
                Topics.RECORDING_STOPPED,
                {
                    'session_name': self.current_session.name if self.current_session else '',
                    'total_points': self.total_points_recorded,
                    'duration': self.current_session.duration if self.current_session else 0
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"停止录制失败: {e}")
            return False
    
    def _recording_worker(self):
        """录制工作线程"""
        sample_interval = 1.0 / self.sample_rate
        last_sample_time = time.time()
        
        logger.info(f"录制线程启动，采样间隔: {sample_interval:.3f}s")
        
        try:
            while not self.stop_event.is_set():
                # 等待录制事件
                if not self.recording_event.wait(timeout=0.1):
                    continue
                
                current_time = time.time()
                
                # 检查是否到了采样时间
                if current_time - last_sample_time >= sample_interval:
                    self._capture_data_point()
                    last_sample_time = current_time
                    self.total_points_recorded += 1
                
                # 短暂休眠以避免过度占用CPU
                time.sleep(0.001)
                
        except Exception as e:
            logger.error(f"录制线程异常: {e}")
        
        logger.info("录制线程结束")
    
    def _capture_data_point(self):
        """捕获数据点"""
        try:
            timestamp = time.time() - self.recording_start_time
            
            data_point = DataPoint(
                timestamp=timestamp,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                forces=self.current_forces.copy(),
                temperatures=self.current_temperatures.copy(),
                voltages=self.current_voltages.copy()
            )
            
            with self.buffer_lock:
                self.data_buffer.append(data_point)
            
        except Exception as e:
            logger.error(f"捕获数据点失败: {e}")
    
    def _flush_buffer(self):
        """刷新缓冲区"""
        with self.buffer_lock:
            logger.info(f"刷新缓冲区，共 {len(self.data_buffer)} 个数据点")
    
    @log_performance
    def save_session(self, session: RecordingSession, filename: Optional[str] = None) -> bool:
        """
        保存录制会话
        
        Args:
            session: 录制会话
            filename: 文件名（可选）
            
        Returns:
            是否保存成功
        """
        try:
            if not filename:
                # 生成文件名
                safe_name = "".join(c for c in session.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                timestamp = int(session.created_at)
                filename = f"{safe_name}_{timestamp}.{session.format.value}"
            
            filepath = self.recordings_dir / filename
            
            if session.format == RecordingFormat.JSON:
                self._save_as_json(session, filepath)
            elif session.format == RecordingFormat.CSV:
                self._save_as_csv(session, filepath)
            elif session.format == RecordingFormat.HDF5:
                self._save_as_hdf5(session, filepath)
            elif session.format == RecordingFormat.BINARY:
                self._save_as_binary(session, filepath)
            
            logger.info(f"录制会话已保存: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"保存录制会话失败: {e}")
            return False
    
    def _save_as_json(self, session: RecordingSession, filepath: Path):
        """保存为JSON格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _save_as_csv(self, session: RecordingSession, filepath: Path):
        """保存为CSV格式"""
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 写入标题行
            headers = ['timestamp'] + \
                     [f'pos_{i}' for i in range(10)] + \
                     [f'vel_{i}' for i in range(10)] + \
                     [f'cur_{i}' for i in range(10)] + \
                     [f'force_{i}' for i in range(10)] + \
                     [f'temp_{i}' for i in range(10)] + \
                     [f'volt_{i}' for i in range(10)]
            writer.writerow(headers)
            
            # 写入数据行
            for dp in session.data_points:
                row = [dp.timestamp] + dp.positions + dp.velocities + dp.currents
                if dp.forces:
                    row.extend(dp.forces)
                else:
                    row.extend([0.0] * 10)
                if dp.temperatures:
                    row.extend(dp.temperatures)
                else:
                    row.extend([25.0] * 10)
                if dp.voltages:
                    row.extend(dp.voltages)
                else:
                    row.extend([12.0] * 10)
                writer.writerow(row)
    
    def _save_as_hdf5(self, session: RecordingSession, filepath: Path):
        """保存为HDF5格式"""
        try:
            import h5py
            
            with h5py.File(filepath, 'w') as f:
                # 元数据
                f.attrs['name'] = session.name
                f.attrs['description'] = session.description
                f.attrs['sample_rate'] = session.sample_rate
                f.attrs['created_at'] = session.created_at
                f.attrs['duration'] = session.duration
                
                # 数据数组
                timestamps = [dp.timestamp for dp in session.data_points]
                positions = np.array([dp.positions for dp in session.data_points])
                velocities = np.array([dp.velocities for dp in session.data_points])
                currents = np.array([dp.currents for dp in session.data_points])
                
                f.create_dataset('timestamps', data=timestamps)
                f.create_dataset('positions', data=positions)
                f.create_dataset('velocities', data=velocities)
                f.create_dataset('currents', data=currents)
                
                # 可选数据
                if session.data_points and session.data_points[0].forces:
                    forces = np.array([dp.forces for dp in session.data_points])
                    f.create_dataset('forces', data=forces)
                
                if session.data_points and session.data_points[0].temperatures:
                    temperatures = np.array([dp.temperatures for dp in session.data_points])
                    f.create_dataset('temperatures', data=temperatures)
                
                if session.data_points and session.data_points[0].voltages:
                    voltages = np.array([dp.voltages for dp in session.data_points])
                    f.create_dataset('voltages', data=voltages)
                    
        except ImportError:
            logger.error("HDF5支持需要安装h5py库")
            raise
    
    def _save_as_binary(self, session: RecordingSession, filepath: Path):
        """保存为二进制格式"""
        import pickle
        
        with open(filepath, 'wb') as f:
            pickle.dump(session.to_dict(), f)
    
    def load_session(self, filepath: str) -> Optional[RecordingSession]:
        """
        加载录制会话
        
        Args:
            filepath: 文件路径
            
        Returns:
            录制会话对象
        """
        try:
            path = Path(filepath)
            
            if path.suffix == '.json':
                return self._load_from_json(path)
            elif path.suffix == '.csv':
                return self._load_from_csv(path)
            elif path.suffix == '.hdf5' or path.suffix == '.h5':
                return self._load_from_hdf5(path)
            elif path.suffix == '.binary' or path.suffix == '.pkl':
                return self._load_from_binary(path)
            else:
                logger.error(f"不支持的文件格式: {path.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"加载录制会话失败: {e}")
            return None
    
    def _load_from_json(self, filepath: Path) -> RecordingSession:
        """从JSON文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return RecordingSession.from_dict(data)
    
    def _load_from_csv(self, filepath: Path) -> RecordingSession:
        """从CSV文件加载"""
        data_points = []
        
        with open(filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                timestamp = float(row['timestamp'])
                positions = [int(row[f'pos_{i}']) for i in range(10)]
                velocities = [float(row[f'vel_{i}']) for i in range(10)]
                currents = [int(row[f'cur_{i}']) for i in range(10)]
                
                # 可选字段
                forces = None
                if f'force_0' in row:
                    forces = [float(row[f'force_{i}']) for i in range(10)]
                
                temperatures = None
                if f'temp_0' in row:
                    temperatures = [float(row[f'temp_{i}']) for i in range(10)]
                
                voltages = None
                if f'volt_0' in row:
                    voltages = [float(row[f'volt_{i}']) for i in range(10)]
                
                data_point = DataPoint(
                    timestamp=timestamp,
                    positions=positions,
                    velocities=velocities,
                    currents=currents,
                    forces=forces,
                    temperatures=temperatures,
                    voltages=voltages
                )
                data_points.append(data_point)
        
        # 从文件名推断会话信息
        name = filepath.stem
        duration = data_points[-1].timestamp if data_points else 0.0
        
        return RecordingSession(
            name=name,
            description=f"从CSV导入: {filepath.name}",
            format=RecordingFormat.CSV,
            sample_rate=len(data_points) / duration if duration > 0 else 100.0,
            data_points=data_points,
            created_at=filepath.stat().st_mtime,
            duration=duration
        )
    
    def _load_from_hdf5(self, filepath: Path) -> RecordingSession:
        """从HDF5文件加载"""
        import h5py
        
        with h5py.File(filepath, 'r') as f:
            # 读取元数据
            name = f.attrs.get('name', filepath.stem)
            description = f.attrs.get('description', '')
            sample_rate = f.attrs.get('sample_rate', 100.0)
            created_at = f.attrs.get('created_at', time.time())
            duration = f.attrs.get('duration', 0.0)
            
            # 读取数据
            timestamps = f['timestamps'][:]
            positions = f['positions'][:]
            velocities = f['velocities'][:]
            currents = f['currents'][:]
            
            forces = f['forces'][:] if 'forces' in f else None
            temperatures = f['temperatures'][:] if 'temperatures' in f else None
            voltages = f['voltages'][:] if 'voltages' in f else None
            
            # 构建数据点
            data_points = []
            for i in range(len(timestamps)):
                data_point = DataPoint(
                    timestamp=timestamps[i],
                    positions=positions[i].tolist(),
                    velocities=velocities[i].tolist(),
                    currents=currents[i].tolist(),
                    forces=forces[i].tolist() if forces is not None else None,
                    temperatures=temperatures[i].tolist() if temperatures is not None else None,
                    voltages=voltages[i].tolist() if voltages is not None else None
                )
                data_points.append(data_point)
            
            return RecordingSession(
                name=name,
                description=description,
                format=RecordingFormat.HDF5,
                sample_rate=sample_rate,
                data_points=data_points,
                created_at=created_at,
                duration=duration
            )
    
    def _load_from_binary(self, filepath: Path) -> RecordingSession:
        """从二进制文件加载"""
        import pickle
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        return RecordingSession.from_dict(data)
    
    def list_recordings(self) -> List[Dict[str, Any]]:
        """列出所有录制文件"""
        recordings = []
        
        try:
            for filepath in self.recordings_dir.glob("*"):
                if filepath.suffix in ['.json', '.csv', '.hdf5', '.h5', '.binary', '.pkl']:
                    try:
                        stat = filepath.stat()
                        recordings.append({
                            'filename': filepath.name,
                            'filepath': str(filepath),
                            'size': stat.st_size,
                            'modified_at': stat.st_mtime,
                            'format': filepath.suffix[1:]  # 去掉点号
                        })
                    except Exception as e:
                        logger.warning(f"读取文件信息失败 {filepath}: {e}")
                        
        except Exception as e:
            logger.error(f"列出录制文件失败: {e}")
        
        # 按修改时间排序
        recordings.sort(key=lambda x: x['modified_at'], reverse=True)
        return recordings
    
    def get_state(self) -> RecordingState:
        """获取当前状态"""
        return self.state
    
    def get_current_session(self) -> Optional[RecordingSession]:
        """获取当前会话"""
        return self.current_session
    
    def get_recording_statistics(self) -> Dict[str, Any]:
        """获取录制统计信息"""
        return {
            'state': self.state.value,
            'total_points_recorded': self.total_points_recorded,
            'current_duration': time.time() - self.recording_start_time if self.state == RecordingState.RECORDING else 0,
            'sample_rate': self.sample_rate,
            'buffer_size': len(self.data_buffer),
            'session_name': self.current_session.name if self.current_session else None
        }
    
    def _on_robot_state_update(self, message):
        """机器人状态更新回调"""
        try:
            data = message.data
            joints = data.get('joints', [])
            
            # 更新当前状态
            for joint_data in joints:
                joint_id = joint_data.get('id')
                if 0 <= joint_id < 10:
                    self.current_positions[joint_id] = joint_data.get('position', 0)
                    self.current_velocities[joint_id] = joint_data.get('velocity', 0.0)
                    self.current_currents[joint_id] = joint_data.get('current', 0)
                    
                    # 可选数据
                    if 'force' in joint_data:
                        self.current_forces[joint_id] = joint_data['force']
                    if 'temperature' in joint_data:
                        self.current_temperatures[joint_id] = joint_data['temperature']
                    if 'voltage' in joint_data:
                        self.current_voltages[joint_id] = joint_data['voltage']
                        
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")


# 全局数据录制器实例
_data_recorder = None


def get_data_recorder() -> DataRecorder:
    """获取全局数据录制器实例"""
    global _data_recorder
    if _data_recorder is None:
        _data_recorder = DataRecorder()
    return _data_recorder