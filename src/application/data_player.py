"""
数据回放器

功能：
- 录制数据回放
- 多种回放模式
- 回放速度控制
- 实时数据可视化
- 回放同步控制
"""

import time
import threading
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from application.data_recorder import RecordingSession, DataPoint, get_data_recorder

logger = get_logger(__name__)


class PlaybackMode(Enum):
    """回放模式"""
    POSITION_ONLY = "position_only"      # 仅位置回放
    FULL_REPLAY = "full_replay"          # 完整回放
    VELOCITY_PROFILE = "velocity_profile" # 速度曲线回放
    FORCE_FEEDBACK = "force_feedback"     # 力反馈回放


class PlaybackState(Enum):
    """回放状态"""
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"


@dataclass
class PlaybackConfig:
    """回放配置"""
    mode: PlaybackMode = PlaybackMode.POSITION_ONLY
    speed_factor: float = 1.0           # 速度因子
    loop_enabled: bool = False          # 循环播放
    sync_to_realtime: bool = True       # 同步到实时
    interpolation_enabled: bool = True   # 启用插值
    start_time: float = 0.0             # 开始时间
    end_time: Optional[float] = None    # 结束时间
    selected_joints: Optional[List[int]] = None  # 选择的关节


class DataPlayer:
    """数据回放器"""
    
    def __init__(self):
        """初始化数据回放器"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        self.data_recorder = get_data_recorder()
        
        # 状态管理
        self.state = PlaybackState.IDLE
        self.current_session: Optional[RecordingSession] = None
        self.playback_config = PlaybackConfig()
        
        # 回放控制
        self.playback_thread: Optional[threading.Thread] = None
        self.playback_event = threading.Event()
        self.stop_event = threading.Event()
        
        # 回放状态
        self.playback_start_time = 0.0
        self.current_playback_time = 0.0
        self.current_data_index = 0
        self.total_data_points = 0
        
        # 数据缓存
        self.interpolated_data: List[DataPoint] = []
        self.playback_positions = [1500] * 10
        
        # 回调函数
        self.position_callback: Optional[Callable[[List[int]], None]] = None
        self.progress_callback: Optional[Callable[[float], None]] = None
        self.status_callback: Optional[Callable[[PlaybackState], None]] = None
        
        logger.info("数据回放器初始化完成")
    
    def set_callbacks(self, 
                     position_callback: Optional[Callable[[List[int]], None]] = None,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     status_callback: Optional[Callable[[PlaybackState], None]] = None):
        """设置回调函数"""
        self.position_callback = position_callback
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def configure_playback(self, config: PlaybackConfig) -> bool:
        """
        配置回放参数
        
        Args:
            config: 回放配置
            
        Returns:
            是否配置成功
        """
        try:
            if self.state != PlaybackState.IDLE:
                logger.warning("回放进行中，无法修改配置")
                return False
            
            self.playback_config = config
            
            logger.info(f"回放配置已更新: 模式={config.mode.value}, 速度={config.speed_factor}")
            return True
            
        except Exception as e:
            logger.error(f"配置回放参数失败: {e}")
            return False
    
    def load_session_for_playback(self, session: RecordingSession) -> bool:
        """
        加载会话用于回放
        
        Args:
            session: 录制会话
            
        Returns:
            是否加载成功
        """
        try:
            if self.state != PlaybackState.IDLE:
                logger.warning("回放器不在空闲状态，无法加载会话")
                return False
            
            self.current_session = session
            self.total_data_points = len(session.data_points)
            
            # 预处理数据
            self._preprocess_data()
            
            logger.info(f"会话已加载用于回放: {session.name}, {self.total_data_points}个数据点")
            return True
            
        except Exception as e:
            logger.error(f"加载回放会话失败: {e}")
            return False
    
    def _preprocess_data(self):
        """预处理数据"""
        if not self.current_session:
            return
        
        try:
            # 应用时间范围过滤
            filtered_data = []
            for dp in self.current_session.data_points:
                if self.playback_config.start_time <= dp.timestamp:
                    if self.playback_config.end_time is None or dp.timestamp <= self.playback_config.end_time:
                        filtered_data.append(dp)
            
            # 应用关节选择过滤
            if self.playback_config.selected_joints:
                for dp in filtered_data:
                    # 只保留选择的关节数据，其他关节保持当前位置
                    new_positions = self.playback_positions.copy()
                    for joint_id in self.playback_config.selected_joints:
                        if 0 <= joint_id < len(dp.positions):
                            new_positions[joint_id] = dp.positions[joint_id]
                    dp.positions = new_positions
            
            # 插值处理
            if self.playback_config.interpolation_enabled and len(filtered_data) > 1:
                self.interpolated_data = self._interpolate_data(filtered_data)
            else:
                self.interpolated_data = filtered_data
            
            logger.info(f"数据预处理完成: {len(self.interpolated_data)}个数据点")
            
        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            self.interpolated_data = self.current_session.data_points.copy()
    
    def _interpolate_data(self, data_points: List[DataPoint]) -> List[DataPoint]:
        """插值数据以提高平滑度"""
        if len(data_points) < 2:
            return data_points
        
        try:
            # 目标采样率（提高到200Hz以获得更平滑的回放）
            target_sample_rate = 200.0
            
            # 计算时间范围
            start_time = data_points[0].timestamp
            end_time = data_points[-1].timestamp
            duration = end_time - start_time
            
            if duration <= 0:
                return data_points
            
            # 生成新的时间点
            num_points = int(duration * target_sample_rate)
            new_timestamps = np.linspace(start_time, end_time, num_points)
            
            # 提取原始数据
            original_timestamps = [dp.timestamp for dp in data_points]
            original_positions = np.array([dp.positions for dp in data_points])
            original_velocities = np.array([dp.velocities for dp in data_points])
            original_currents = np.array([dp.currents for dp in data_points])
            
            # 插值位置数据
            interpolated_positions = []
            for joint_idx in range(10):
                joint_positions = original_positions[:, joint_idx]
                interp_positions = np.interp(new_timestamps, original_timestamps, joint_positions)
                interpolated_positions.append(interp_positions)
            
            interpolated_positions = np.array(interpolated_positions).T
            
            # 插值速度数据
            interpolated_velocities = []
            for joint_idx in range(10):
                joint_velocities = original_velocities[:, joint_idx]
                interp_velocities = np.interp(new_timestamps, original_timestamps, joint_velocities)
                interpolated_velocities.append(interp_velocities)
            
            interpolated_velocities = np.array(interpolated_velocities).T
            
            # 插值电流数据
            interpolated_currents = []
            for joint_idx in range(10):
                joint_currents = original_currents[:, joint_idx]
                interp_currents = np.interp(new_timestamps, original_timestamps, joint_currents)
                interpolated_currents.append(interp_currents)
            
            interpolated_currents = np.array(interpolated_currents).T
            
            # 创建插值后的数据点
            interpolated_data = []
            for i in range(len(new_timestamps)):
                data_point = DataPoint(
                    timestamp=new_timestamps[i],
                    positions=interpolated_positions[i].astype(int).tolist(),
                    velocities=interpolated_velocities[i].tolist(),
                    currents=interpolated_currents[i].astype(int).tolist()
                )
                interpolated_data.append(data_point)
            
            logger.info(f"数据插值完成: {len(data_points)} -> {len(interpolated_data)}个数据点")
            return interpolated_data
            
        except Exception as e:
            logger.error(f"数据插值失败: {e}")
            return data_points
    
    def start_playback(self) -> bool:
        """开始回放"""
        try:
            if self.state != PlaybackState.IDLE:
                logger.warning("回放器不在空闲状态，无法开始回放")
                return False
            
            if not self.current_session or not self.interpolated_data:
                logger.error("没有可回放的数据")
                return False
            
            # 重置回放状态
            self.current_data_index = 0
            self.current_playback_time = 0.0
            self.playback_start_time = time.time()
            
            # 启动回放线程
            self.stop_event.clear()
            self.playback_event.set()
            self.playback_thread = threading.Thread(target=self._playback_worker)
            self.playback_thread.daemon = True
            self.playback_thread.start()
            
            self.state = PlaybackState.PLAYING
            
            if self.status_callback:
                self.status_callback(self.state)
            
            logger.info(f"开始回放数据: {self.current_session.name}")
            
            # 发布事件
            self.message_bus.publish(
                Topics.PLAYBACK_STARTED,
                {
                    'session_name': self.current_session.name,
                    'total_points': len(self.interpolated_data),
                    'duration': self.interpolated_data[-1].timestamp - self.interpolated_data[0].timestamp,
                    'mode': self.playback_config.mode.value
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始回放失败: {e}")
            return False
    
    def pause_playback(self) -> bool:
        """暂停回放"""
        try:
            if self.state != PlaybackState.PLAYING:
                logger.warning("当前不在回放状态")
                return False
            
            self.playback_event.clear()
            self.state = PlaybackState.PAUSED
            
            if self.status_callback:
                self.status_callback(self.state)
            
            logger.info("回放已暂停")
            
            # 发布事件
            self.message_bus.publish(
                Topics.PLAYBACK_PAUSED,
                {'session_name': self.current_session.name if self.current_session else ''},
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"暂停回放失败: {e}")
            return False
    
    def resume_playback(self) -> bool:
        """恢复回放"""
        try:
            if self.state != PlaybackState.PAUSED:
                logger.warning("当前不在暂停状态")
                return False
            
            # 调整开始时间以补偿暂停时间
            pause_duration = time.time() - self.playback_start_time - self.current_playback_time
            self.playback_start_time += pause_duration
            
            self.playback_event.set()
            self.state = PlaybackState.PLAYING
            
            if self.status_callback:
                self.status_callback(self.state)
            
            logger.info("回放已恢复")
            
            # 发布事件
            self.message_bus.publish(
                Topics.PLAYBACK_RESUMED,
                {'session_name': self.current_session.name if self.current_session else ''},
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"恢复回放失败: {e}")
            return False
    
    def stop_playback(self) -> bool:
        """停止回放"""
        try:
            if self.state not in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
                logger.warning("当前不在回放状态")
                return False
            
            self.state = PlaybackState.STOPPING
            
            # 停止回放线程
            self.stop_event.set()
            self.playback_event.set()  # 确保线程能够退出
            
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=3.0)
            
            self.state = PlaybackState.IDLE
            
            if self.status_callback:
                self.status_callback(self.state)
            
            logger.info("回放已停止")
            
            # 发布事件
            self.message_bus.publish(
                Topics.PLAYBACK_STOPPED,
                {
                    'session_name': self.current_session.name if self.current_session else '',
                    'completed': False
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"停止回放失败: {e}")
            return False
    
    def seek_to_time(self, target_time: float) -> bool:
        """跳转到指定时间"""
        try:
            if not self.interpolated_data:
                return False
            
            # 查找最接近的数据点
            for i, dp in enumerate(self.interpolated_data):
                if dp.timestamp >= target_time:
                    self.current_data_index = i
                    self.current_playback_time = target_time
                    
                    # 如果正在回放，调整开始时间
                    if self.state == PlaybackState.PLAYING:
                        self.playback_start_time = time.time() - target_time / self.playback_config.speed_factor
                    
                    logger.info(f"跳转到时间: {target_time:.2f}s")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"跳转时间失败: {e}")
            return False
    
    def seek_to_progress(self, progress: float) -> bool:
        """跳转到指定进度（0-1）"""
        if not self.interpolated_data:
            return False
        
        progress = max(0.0, min(1.0, progress))
        target_index = int(progress * (len(self.interpolated_data) - 1))
        target_time = self.interpolated_data[target_index].timestamp
        
        return self.seek_to_time(target_time)
    
    def _playback_worker(self):
        """回放工作线程"""
        logger.info("回放线程启动")
        
        try:
            while not self.stop_event.is_set() and self.current_data_index < len(self.interpolated_data):
                # 等待回放事件
                if not self.playback_event.wait(timeout=0.1):
                    continue
                
                current_real_time = time.time()
                
                if self.playback_config.sync_to_realtime:
                    # 同步到实时时间
                    elapsed_real_time = current_real_time - self.playback_start_time
                    target_playback_time = elapsed_real_time * self.playback_config.speed_factor
                else:
                    # 尽快回放
                    target_playback_time = self.current_playback_time + 0.01  # 10ms步进
                
                # 查找当前应该播放的数据点
                while (self.current_data_index < len(self.interpolated_data) and 
                       self.interpolated_data[self.current_data_index].timestamp <= target_playback_time):
                    
                    data_point = self.interpolated_data[self.current_data_index]
                    self.current_playback_time = data_point.timestamp
                    
                    # 发送位置数据
                    self._send_position_data(data_point)
                    
                    # 更新进度
                    progress = self.current_data_index / len(self.interpolated_data)
                    if self.progress_callback:
                        self.progress_callback(progress)
                    
                    self.current_data_index += 1
                
                # 短暂休眠
                time.sleep(0.001)
            
            # 回放完成
            if self.current_data_index >= len(self.interpolated_data):
                self._on_playback_completed()
            
        except Exception as e:
            logger.error(f"回放线程异常: {e}")
        
        logger.info("回放线程结束")
    
    def _send_position_data(self, data_point: DataPoint):
        """发送位置数据"""
        try:
            if self.playback_config.mode == PlaybackMode.POSITION_ONLY:
                # 仅发送位置
                self.playback_positions = data_point.positions.copy()
                
            elif self.playback_config.mode == PlaybackMode.FULL_REPLAY:
                # 完整回放（位置+速度+电流）
                self.playback_positions = data_point.positions.copy()
                # 这里可以添加速度和电流的处理
                
            elif self.playback_config.mode == PlaybackMode.VELOCITY_PROFILE:
                # 速度曲线回放
                # 根据速度曲线计算位置
                pass
                
            elif self.playback_config.mode == PlaybackMode.FORCE_FEEDBACK:
                # 力反馈回放
                if data_point.forces:
                    # 处理力反馈数据
                    pass
            
            # 调用位置回调
            if self.position_callback:
                self.position_callback(self.playback_positions)
            
            # 发布位置更新事件
            self.message_bus.publish(
                Topics.PLAYBACK_POSITION_UPDATE,
                {
                    'positions': self.playback_positions,
                    'timestamp': data_point.timestamp,
                    'velocities': data_point.velocities,
                    'currents': data_point.currents
                },
                MessagePriority.HIGH
            )
            
        except Exception as e:
            logger.error(f"发送位置数据失败: {e}")
    
    def _on_playback_completed(self):
        """回放完成处理"""
        try:
            if self.playback_config.loop_enabled:
                # 循环播放
                self.current_data_index = 0
                self.current_playback_time = 0.0
                self.playback_start_time = time.time()
                logger.info("循环回放重新开始")
            else:
                # 回放完成
                self.state = PlaybackState.COMPLETED
                
                if self.status_callback:
                    self.status_callback(self.state)
                
                logger.info("回放完成")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.PLAYBACK_COMPLETED,
                    {
                        'session_name': self.current_session.name if self.current_session else '',
                        'total_points': len(self.interpolated_data)
                    },
                    MessagePriority.NORMAL
                )
                
                # 自动切换到空闲状态
                self.state = PlaybackState.IDLE
                
        except Exception as e:
            logger.error(f"回放完成处理失败: {e}")
    
    def get_state(self) -> PlaybackState:
        """获取当前状态"""
        return self.state
    
    def get_current_session(self) -> Optional[RecordingSession]:
        """获取当前会话"""
        return self.current_session
    
    def get_playback_progress(self) -> float:
        """获取回放进度（0-1）"""
        if not self.interpolated_data:
            return 0.0
        
        return self.current_data_index / len(self.interpolated_data)
    
    def get_playback_time(self) -> float:
        """获取当前回放时间"""
        return self.current_playback_time
    
    def get_playback_statistics(self) -> Dict[str, Any]:
        """获取回放统计信息"""
        return {
            'state': self.state.value,
            'current_time': self.current_playback_time,
            'progress': self.get_playback_progress(),
            'total_points': len(self.interpolated_data) if self.interpolated_data else 0,
            'current_index': self.current_data_index,
            'speed_factor': self.playback_config.speed_factor,
            'mode': self.playback_config.mode.value,
            'session_name': self.current_session.name if self.current_session else None
        }


# 全局数据回放器实例
_data_player = None


def get_data_player() -> DataPlayer:
    """获取全局数据回放器实例"""
    global _data_player
    if _data_player is None:
        _data_player = DataPlayer()
    return _data_player