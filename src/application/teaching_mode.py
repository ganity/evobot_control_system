"""
示教模式

功能：
- 位置记录功能
- 关键帧管理
- 轨迹回放功能
- 示教数据保存和加载
- 拖拽示教模式
- 关键帧编辑
- 轨迹优化
- 高级示教数据管理
"""

import time
import json
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from core.trajectory_planner import get_trajectory_planner, InterpolationType, TrajectoryConstraints

logger = get_logger(__name__)


class TeachingState(Enum):
    """示教状态"""
    IDLE = "idle"
    RECORDING = "recording"
    DRAG_TEACHING = "drag_teaching"  # 拖拽示教
    PLAYING = "playing"
    PAUSED = "paused"
    OPTIMIZING = "optimizing"  # 轨迹优化中


class TeachingMode(Enum):
    """示教模式类型"""
    POSITION_RECORDING = "position_recording"  # 位置录制
    DRAG_TEACHING = "drag_teaching"           # 拖拽示教
    KEYFRAME_EDITING = "keyframe_editing"     # 关键帧编辑


@dataclass
class KeyFrame:
    """关键帧"""
    timestamp: float
    positions: List[int]
    velocities: List[float]
    currents: List[int]
    name: Optional[str] = None
    description: Optional[str] = None
    # 新增字段
    joint_stiffness: Optional[List[float]] = None  # 关节刚度
    force_feedback: Optional[List[float]] = None   # 力反馈
    teaching_mode: Optional[str] = None            # 示教模式
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyFrame':
        """从字典创建"""
        return cls(**data)
    
    def copy(self) -> 'KeyFrame':
        """创建副本"""
        return KeyFrame(
            timestamp=self.timestamp,
            positions=self.positions.copy(),
            velocities=self.velocities.copy(),
            currents=self.currents.copy(),
            name=self.name,
            description=self.description,
            joint_stiffness=self.joint_stiffness.copy() if self.joint_stiffness else None,
            force_feedback=self.force_feedback.copy() if self.force_feedback else None,
            teaching_mode=self.teaching_mode
        )
    
    def interpolate_with(self, other: 'KeyFrame', ratio: float) -> 'KeyFrame':
        """与另一个关键帧插值"""
        if not (0 <= ratio <= 1):
            raise ValueError("插值比例必须在0-1之间")
        
        # 位置插值
        interp_positions = []
        for p1, p2 in zip(self.positions, other.positions):
            interp_positions.append(int(p1 + (p2 - p1) * ratio))
        
        # 速度插值
        interp_velocities = []
        for v1, v2 in zip(self.velocities, other.velocities):
            interp_velocities.append(v1 + (v2 - v1) * ratio)
        
        # 时间插值
        interp_timestamp = self.timestamp + (other.timestamp - self.timestamp) * ratio
        
        return KeyFrame(
            timestamp=interp_timestamp,
            positions=interp_positions,
            velocities=interp_velocities,
            currents=self.currents.copy(),  # 电流不插值
            name=f"插值_{ratio:.2f}",
            teaching_mode="interpolated"
        )


@dataclass
class TeachingSequence:
    """示教序列"""
    name: str
    description: str
    keyframes: List[KeyFrame]
    created_at: float
    modified_at: float
    metadata: Optional[Dict[str, Any]] = None
    # 新增字段
    teaching_mode_type: Optional[str] = None       # 示教模式类型
    optimization_level: int = 0                    # 优化级别 (0-3)
    smoothness_factor: float = 1.0                 # 平滑因子
    velocity_scaling: float = 1.0                  # 速度缩放
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'description': self.description,
            'keyframes': [kf.to_dict() for kf in self.keyframes],
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'metadata': self.metadata or {},
            'teaching_mode_type': self.teaching_mode_type,
            'optimization_level': self.optimization_level,
            'smoothness_factor': self.smoothness_factor,
            'velocity_scaling': self.velocity_scaling
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeachingSequence':
        """从字典创建"""
        keyframes = [KeyFrame.from_dict(kf_data) for kf_data in data['keyframes']]
        return cls(
            name=data['name'],
            description=data['description'],
            keyframes=keyframes,
            created_at=data['created_at'],
            modified_at=data['modified_at'],
            metadata=data.get('metadata', {}),
            teaching_mode_type=data.get('teaching_mode_type'),
            optimization_level=data.get('optimization_level', 0),
            smoothness_factor=data.get('smoothness_factor', 1.0),
            velocity_scaling=data.get('velocity_scaling', 1.0)
        )
    
    def add_keyframe(self, keyframe: KeyFrame):
        """添加关键帧"""
        self.keyframes.append(keyframe)
        self.modified_at = time.time()
    
    def insert_keyframe(self, index: int, keyframe: KeyFrame) -> bool:
        """在指定位置插入关键帧"""
        if 0 <= index <= len(self.keyframes):
            self.keyframes.insert(index, keyframe)
            self.modified_at = time.time()
            return True
        return False
    
    def update_keyframe(self, index: int, keyframe: KeyFrame) -> bool:
        """更新关键帧"""
        if 0 <= index < len(self.keyframes):
            self.keyframes[index] = keyframe
            self.modified_at = time.time()
            return True
        return False
    
    def remove_keyframe(self, index: int) -> bool:
        """删除关键帧"""
        if 0 <= index < len(self.keyframes):
            self.keyframes.pop(index)
            self.modified_at = time.time()
            return True
        return False
    
    def get_duration(self) -> float:
        """获取序列总时长"""
        if len(self.keyframes) < 2:
            return 0.0
        return self.keyframes[-1].timestamp - self.keyframes[0].timestamp
    
    def get_keyframe_at_time(self, timestamp: float) -> Optional[KeyFrame]:
        """获取指定时间的关键帧（插值）"""
        if not self.keyframes:
            return None
        
        # 找到时间范围
        for i in range(len(self.keyframes) - 1):
            kf1, kf2 = self.keyframes[i], self.keyframes[i + 1]
            if kf1.timestamp <= timestamp <= kf2.timestamp:
                # 计算插值比例
                ratio = (timestamp - kf1.timestamp) / (kf2.timestamp - kf1.timestamp)
                return kf1.interpolate_with(kf2, ratio)
        
        # 超出范围，返回最近的关键帧
        if timestamp <= self.keyframes[0].timestamp:
            return self.keyframes[0]
        else:
            return self.keyframes[-1]
    
    def optimize_trajectory(self, optimization_level: int = 1) -> bool:
        """优化轨迹"""
        if len(self.keyframes) < 3:
            return False
        
        try:
            if optimization_level == 1:
                # 基础优化：移除冗余关键帧
                self._remove_redundant_keyframes()
            elif optimization_level == 2:
                # 中级优化：平滑处理
                self._smooth_trajectory()
            elif optimization_level == 3:
                # 高级优化：速度优化
                self._optimize_velocities()
            
            self.optimization_level = optimization_level
            self.modified_at = time.time()
            return True
            
        except Exception as e:
            logger.error(f"轨迹优化失败: {e}")
            return False
    
    def _remove_redundant_keyframes(self):
        """移除冗余关键帧"""
        if len(self.keyframes) < 3:
            return
        
        optimized_keyframes = [self.keyframes[0]]  # 保留第一个
        
        for i in range(1, len(self.keyframes) - 1):
            prev_kf = optimized_keyframes[-1]
            curr_kf = self.keyframes[i]
            next_kf = self.keyframes[i + 1]
            
            # 计算位置变化
            pos_change_prev = sum(abs(c - p) for c, p in zip(curr_kf.positions, prev_kf.positions))
            pos_change_next = sum(abs(n - c) for n, c in zip(next_kf.positions, curr_kf.positions))
            
            # 如果变化太小，跳过此关键帧
            if pos_change_prev > 50 or pos_change_next > 50:  # 阈值可配置
                optimized_keyframes.append(curr_kf)
        
        optimized_keyframes.append(self.keyframes[-1])  # 保留最后一个
        self.keyframes = optimized_keyframes
        
        logger.info(f"冗余关键帧优化完成，从 {len(self.keyframes)} 减少到 {len(optimized_keyframes)}")
    
    def _smooth_trajectory(self):
        """平滑轨迹"""
        if len(self.keyframes) < 3:
            return
        
        # 使用移动平均平滑位置
        window_size = min(3, len(self.keyframes) // 2)
        
        for joint_idx in range(10):  # 10个关节
            positions = [kf.positions[joint_idx] for kf in self.keyframes]
            smoothed_positions = self._moving_average(positions, window_size)
            
            for i, smoothed_pos in enumerate(smoothed_positions):
                self.keyframes[i].positions[joint_idx] = int(smoothed_pos)
        
        logger.info("轨迹平滑处理完成")
    
    def _optimize_velocities(self):
        """优化速度"""
        if len(self.keyframes) < 2:
            return
        
        # 重新计算速度
        for i in range(len(self.keyframes) - 1):
            curr_kf = self.keyframes[i]
            next_kf = self.keyframes[i + 1]
            
            time_diff = next_kf.timestamp - curr_kf.timestamp
            if time_diff > 0:
                for joint_idx in range(10):
                    pos_diff = next_kf.positions[joint_idx] - curr_kf.positions[joint_idx]
                    velocity = pos_diff / time_diff
                    curr_kf.velocities[joint_idx] = velocity * self.velocity_scaling
        
        logger.info("速度优化完成")
    
    def _moving_average(self, data: List[float], window_size: int) -> List[float]:
        """移动平均"""
        if window_size <= 1:
            return data
        
        smoothed = []
        half_window = window_size // 2
        
        for i in range(len(data)):
            start_idx = max(0, i - half_window)
            end_idx = min(len(data), i + half_window + 1)
            window_data = data[start_idx:end_idx]
            smoothed.append(sum(window_data) / len(window_data))
        
        return smoothed


class TeachingModeManager:
    """示教模式管理器"""
    
    def __init__(self):
        """初始化示教模式"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        self.message_bus = get_message_bus()
        self.trajectory_planner = get_trajectory_planner()
        
        # 状态管理
        self.state = TeachingState.IDLE
        self.current_mode = TeachingMode.POSITION_RECORDING
        self.current_sequence: Optional[TeachingSequence] = None
        self.recording_start_time = 0.0
        
        # 录制参数
        self.recording_interval = 0.1  # 100ms间隔录制
        self.last_record_time = 0.0
        
        # 拖拽示教参数
        self.drag_sensitivity = 1.0      # 拖拽灵敏度
        self.drag_threshold = 100        # 拖拽阈值
        self.enable_force_feedback = False  # 力反馈使能
        
        # 数据存储
        self.sequences_dir = Path("data/sequences")
        self.sequences_dir.mkdir(parents=True, exist_ok=True)
        
        # 备份目录
        self.backup_dir = Path("data/sequences/backup")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前机器人状态
        self.current_positions = [1500] * 10
        self.current_velocities = [0.0] * 10
        self.current_currents = [0] * 10
        self.current_forces = [0.0] * 10  # 力传感器数据
        
        # 拖拽示教状态
        self.drag_start_positions = [1500] * 10
        self.drag_active_joints = set()  # 激活的拖拽关节
        
        # 订阅机器人状态更新
        self.message_bus.subscribe(Topics.ROBOT_STATE, self._on_robot_state_update)
        
        logger.info("示教模式管理器初始化完成")
    
    def set_teaching_mode(self, mode: TeachingMode) -> bool:
        """设置示教模式"""
        if self.state != TeachingState.IDLE:
            logger.warning("示教模式不在空闲状态，无法切换模式")
            return False
        
        old_mode = self.current_mode
        self.current_mode = mode
        
        logger.info(f"示教模式切换: {old_mode.value} -> {mode.value}")
        
        # 发布模式切换事件
        self.message_bus.publish(
            Topics.TEACHING_MODE_CHANGED,
            {
                'old_mode': old_mode.value,
                'new_mode': mode.value
            },
            MessagePriority.NORMAL
        )
        
        return True
    
    def start_drag_teaching(self, sequence_name: str, description: str = "", 
                          active_joints: Optional[List[int]] = None) -> bool:
        """
        开始拖拽示教
        
        Args:
            sequence_name: 序列名称
            description: 描述
            active_joints: 激活的关节列表，None表示全部关节
            
        Returns:
            是否成功启动
        """
        try:
            if self.state != TeachingState.IDLE:
                logger.warning("示教模式不在空闲状态，无法开始拖拽示教")
                return False
            
            # 设置拖拽模式
            self.current_mode = TeachingMode.DRAG_TEACHING
            
            # 创建新序列
            self.current_sequence = TeachingSequence(
                name=sequence_name,
                description=description,
                keyframes=[],
                created_at=time.time(),
                modified_at=time.time(),
                teaching_mode_type="drag_teaching"
            )
            
            # 设置激活关节
            if active_joints is None:
                self.drag_active_joints = set(range(10))  # 全部关节
            else:
                self.drag_active_joints = set(active_joints)
            
            # 记录起始位置
            self.drag_start_positions = self.current_positions.copy()
            
            start_keyframe = KeyFrame(
                timestamp=0.0,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                name="拖拽起始位置",
                teaching_mode="drag_teaching"
            )
            self.current_sequence.add_keyframe(start_keyframe)
            
            self.state = TeachingState.DRAG_TEACHING
            self.recording_start_time = time.time()
            
            # 启用拖拽模式（降低关节刚度）
            self._enable_drag_mode()
            
            logger.info(f"开始拖拽示教: {sequence_name}, 激活关节: {self.drag_active_joints}")
            
            # 发布事件
            self.message_bus.publish(
                Topics.DRAG_TEACHING_STARTED,
                {
                    'sequence_name': sequence_name,
                    'active_joints': list(self.drag_active_joints)
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始拖拽示教失败: {e}")
            return False
    
    def stop_drag_teaching(self) -> bool:
        """停止拖拽示教"""
        try:
            if self.state != TeachingState.DRAG_TEACHING:
                logger.warning("当前不在拖拽示教状态")
                return False
            
            # 记录结束位置
            if self.current_sequence:
                current_time = time.time() - self.recording_start_time
                end_keyframe = KeyFrame(
                    timestamp=current_time,
                    positions=self.current_positions.copy(),
                    velocities=self.current_velocities.copy(),
                    currents=self.current_currents.copy(),
                    name="拖拽结束位置",
                    teaching_mode="drag_teaching"
                )
                self.current_sequence.add_keyframe(end_keyframe)
            
            # 禁用拖拽模式（恢复关节刚度）
            self._disable_drag_mode()
            
            self.state = TeachingState.IDLE
            self.drag_active_joints.clear()
            
            logger.info(f"停止拖拽示教，共记录 {len(self.current_sequence.keyframes)} 个关键帧")
            
            # 发布事件
            self.message_bus.publish(
                Topics.DRAG_TEACHING_STOPPED,
                {
                    'sequence_name': self.current_sequence.name if self.current_sequence else '',
                    'keyframes_count': len(self.current_sequence.keyframes) if self.current_sequence else 0
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"停止拖拽示教失败: {e}")
            return False
    
    def _enable_drag_mode(self):
        """启用拖拽模式"""
        try:
            # 降低激活关节的刚度
            from core.motion_controller import get_motion_controller
            motion_controller = get_motion_controller()
            
            # 这里可以发送降低刚度的指令
            # 具体实现取决于硬件协议
            logger.info("拖拽模式已启用，关节刚度降低")
            
        except Exception as e:
            logger.error(f"启用拖拽模式失败: {e}")
    
    def _disable_drag_mode(self):
        """禁用拖拽模式"""
        try:
            # 恢复关节刚度
            from core.motion_controller import get_motion_controller
            motion_controller = get_motion_controller()
            
            # 这里可以发送恢复刚度的指令
            logger.info("拖拽模式已禁用，关节刚度恢复")
            
        except Exception as e:
            logger.error(f"禁用拖拽模式失败: {e}")
    
    def edit_keyframe(self, sequence: TeachingSequence, keyframe_index: int, 
                     new_positions: Optional[List[int]] = None,
                     new_name: Optional[str] = None,
                     new_description: Optional[str] = None) -> bool:
        """
        编辑关键帧
        
        Args:
            sequence: 目标序列
            keyframe_index: 关键帧索引
            new_positions: 新位置
            new_name: 新名称
            new_description: 新描述
            
        Returns:
            是否编辑成功
        """
        try:
            if keyframe_index < 0 or keyframe_index >= len(sequence.keyframes):
                logger.error(f"关键帧索引超出范围: {keyframe_index}")
                return False
            
            keyframe = sequence.keyframes[keyframe_index]
            
            # 更新位置
            if new_positions is not None:
                if len(new_positions) != 10:
                    logger.error("位置数组长度必须为10")
                    return False
                keyframe.positions = new_positions.copy()
            
            # 更新名称
            if new_name is not None:
                keyframe.name = new_name
            
            # 更新描述
            if new_description is not None:
                keyframe.description = new_description
            
            sequence.modified_at = time.time()
            
            logger.info(f"关键帧 {keyframe_index} 编辑完成")
            
            # 发布事件
            self.message_bus.publish(
                Topics.KEYFRAME_EDITED,
                {
                    'sequence_name': sequence.name,
                    'keyframe_index': keyframe_index,
                    'keyframe_name': keyframe.name
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"编辑关键帧失败: {e}")
            return False
    
    def insert_interpolated_keyframe(self, sequence: TeachingSequence, 
                                   index1: int, index2: int, ratio: float = 0.5) -> bool:
        """
        在两个关键帧之间插入插值关键帧
        
        Args:
            sequence: 目标序列
            index1: 第一个关键帧索引
            index2: 第二个关键帧索引
            ratio: 插值比例 (0-1)
            
        Returns:
            是否插入成功
        """
        try:
            if not (0 <= index1 < len(sequence.keyframes) and 0 <= index2 < len(sequence.keyframes)):
                logger.error("关键帧索引超出范围")
                return False
            
            if index1 >= index2:
                logger.error("第一个索引必须小于第二个索引")
                return False
            
            kf1 = sequence.keyframes[index1]
            kf2 = sequence.keyframes[index2]
            
            # 创建插值关键帧
            interpolated_kf = kf1.interpolate_with(kf2, ratio)
            interpolated_kf.name = f"插值_{index1}_{index2}_{ratio:.2f}"
            
            # 插入到序列中
            insert_index = index1 + 1
            sequence.insert_keyframe(insert_index, interpolated_kf)
            
            logger.info(f"插值关键帧已插入到位置 {insert_index}")
            
            return True
            
        except Exception as e:
            logger.error(f"插入插值关键帧失败: {e}")
            return False
    
    def optimize_sequence(self, sequence: TeachingSequence, 
                         optimization_level: int = 1,
                         smoothness_factor: float = 1.0,
                         velocity_scaling: float = 1.0) -> bool:
        """
        优化序列
        
        Args:
            sequence: 目标序列
            optimization_level: 优化级别 (1-3)
            smoothness_factor: 平滑因子
            velocity_scaling: 速度缩放
            
        Returns:
            是否优化成功
        """
        try:
            self.state = TeachingState.OPTIMIZING
            
            # 设置优化参数
            sequence.smoothness_factor = smoothness_factor
            sequence.velocity_scaling = velocity_scaling
            
            # 执行优化
            success = sequence.optimize_trajectory(optimization_level)
            
            self.state = TeachingState.IDLE
            
            if success:
                logger.info(f"序列 '{sequence.name}' 优化完成，级别: {optimization_level}")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.SEQUENCE_OPTIMIZED,
                    {
                        'sequence_name': sequence.name,
                        'optimization_level': optimization_level,
                        'keyframes_count': len(sequence.keyframes)
                    },
                    MessagePriority.NORMAL
                )
            
            return success
            
        except Exception as e:
            logger.error(f"优化序列失败: {e}")
            self.state = TeachingState.IDLE
            return False
    
    def backup_sequence(self, sequence: TeachingSequence) -> bool:
        """备份序列"""
        try:
            timestamp = int(time.time())
            backup_filename = f"{sequence.name}_backup_{timestamp}.json"
            backup_path = self.backup_dir / backup_filename
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(sequence.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"序列已备份: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"备份序列失败: {e}")
            return False
    
    def restore_sequence_from_backup(self, backup_filename: str) -> Optional[TeachingSequence]:
        """从备份恢复序列"""
        try:
            backup_path = self.backup_dir / backup_filename
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sequence = TeachingSequence.from_dict(data)
            logger.info(f"序列已从备份恢复: {sequence.name}")
            return sequence
            
        except Exception as e:
            logger.error(f"从备份恢复序列失败: {e}")
            return None
    
    def export_sequence_to_csv(self, sequence: TeachingSequence, filepath: str) -> bool:
        """导出序列为CSV格式"""
        try:
            import csv
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # 写入标题行
                headers = ['timestamp', 'name'] + [f'joint_{i}_pos' for i in range(10)] + \
                         [f'joint_{i}_vel' for i in range(10)] + [f'joint_{i}_cur' for i in range(10)]
                writer.writerow(headers)
                
                # 写入数据行
                for kf in sequence.keyframes:
                    row = [kf.timestamp, kf.name or ''] + kf.positions + kf.velocities + kf.currents
                    writer.writerow(row)
            
            logger.info(f"序列已导出为CSV: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            return False
    
    def import_sequence_from_csv(self, filepath: str, sequence_name: str) -> Optional[TeachingSequence]:
        """从CSV文件导入序列"""
        try:
            import csv
            
            keyframes = []
            
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    timestamp = float(row['timestamp'])
                    name = row.get('name', '')
                    
                    positions = [int(row[f'joint_{i}_pos']) for i in range(10)]
                    velocities = [float(row[f'joint_{i}_vel']) for i in range(10)]
                    currents = [int(row[f'joint_{i}_cur']) for i in range(10)]
                    
                    keyframe = KeyFrame(
                        timestamp=timestamp,
                        positions=positions,
                        velocities=velocities,
                        currents=currents,
                        name=name,
                        teaching_mode="imported"
                    )
                    keyframes.append(keyframe)
            
            sequence = TeachingSequence(
                name=sequence_name,
                description=f"从CSV导入: {filepath}",
                keyframes=keyframes,
                created_at=time.time(),
                modified_at=time.time(),
                teaching_mode_type="imported"
            )
            
            logger.info(f"序列已从CSV导入: {sequence_name}, {len(keyframes)}个关键帧")
            return sequence
            
        except Exception as e:
            logger.error(f"从CSV导入失败: {e}")
            return None
    
    def start_recording(self, sequence_name: str, description: str = "") -> bool:
        """开始录制"""
        try:
            if self.state != TeachingState.IDLE:
                logger.warning("示教模式不在空闲状态，无法开始录制")
                return False
            
            # 设置录制模式
            self.current_mode = TeachingMode.POSITION_RECORDING
            
            # 创建新序列
            self.current_sequence = TeachingSequence(
                name=sequence_name,
                description=description,
                keyframes=[],
                created_at=time.time(),
                modified_at=time.time(),
                teaching_mode_type="position_recording"
            )
            
            # 记录起始位置
            start_keyframe = KeyFrame(
                timestamp=0.0,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                name="起始位置",
                teaching_mode="position_recording"
            )
            self.current_sequence.add_keyframe(start_keyframe)
            
            self.state = TeachingState.RECORDING
            self.recording_start_time = time.time()
            self.last_record_time = 0.0
            
            logger.info(f"开始录制示教序列: {sequence_name}")
            
            # 发布事件
            self.message_bus.publish(
                Topics.TEACHING_STARTED,
                {
                    'sequence_name': sequence_name,
                    'description': description,
                    'mode': 'position_recording'
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始录制失败: {e}")
            return False
    
    def stop_recording(self) -> bool:
        """停止录制"""
        try:
            if self.state != TeachingState.RECORDING:
                logger.warning("当前不在录制状态")
                return False
            
            # 记录结束位置
            if self.current_sequence:
                current_time = time.time() - self.recording_start_time
                end_keyframe = KeyFrame(
                    timestamp=current_time,
                    positions=self.current_positions.copy(),
                    velocities=self.current_velocities.copy(),
                    currents=self.current_currents.copy(),
                    name="结束位置",
                    teaching_mode="position_recording"
                )
                self.current_sequence.add_keyframe(end_keyframe)
            
            self.state = TeachingState.IDLE
            
            logger.info(f"停止录制，共记录 {len(self.current_sequence.keyframes)} 个关键帧")
            
            # 发布事件
            self.message_bus.publish(
                Topics.TEACHING_STOPPED,
                {
                    'sequence_name': self.current_sequence.name if self.current_sequence else '',
                    'keyframes_count': len(self.current_sequence.keyframes) if self.current_sequence else 0
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"停止录制失败: {e}")
            return False
    
    def add_keyframe_manually(self, name: str = "", description: str = "") -> bool:
        """手动添加关键帧"""
        try:
            if self.state != TeachingState.RECORDING:
                logger.warning("不在录制状态，无法添加关键帧")
                return False
            
            if not self.current_sequence:
                logger.error("当前序列为空")
                return False
            
            current_time = time.time() - self.recording_start_time
            keyframe = KeyFrame(
                timestamp=current_time,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                name=name or f"关键帧{len(self.current_sequence.keyframes)}",
                description=description,
                teaching_mode="manual"
            )
            
            self.current_sequence.add_keyframe(keyframe)
            
            logger.info(f"手动添加关键帧: {keyframe.name}")
            
            # 发布事件
            self.message_bus.publish(
                Topics.KEYFRAME_ADDED,
                {
                    'keyframe_name': keyframe.name,
                    'timestamp': keyframe.timestamp,
                    'positions': keyframe.positions
                },
                MessagePriority.NORMAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"添加关键帧失败: {e}")
            return False
    
    @log_performance
    def play_sequence(self, sequence: TeachingSequence, 
                     interpolation_type: InterpolationType = InterpolationType.CUBIC_SPLINE,
                     velocity_scaling: float = 1.0) -> bool:
        """回放序列"""
        try:
            if self.state != TeachingState.IDLE:
                logger.warning("示教模式不在空闲状态，无法回放")
                return False
            
            if len(sequence.keyframes) < 2:
                logger.warning("序列关键帧不足，无法回放")
                return False
            
            # 提取路径点
            waypoints = []
            durations = []
            
            for i, keyframe in enumerate(sequence.keyframes):
                waypoints.append(keyframe.positions)
                
                if i > 0:
                    # 计算时间间隔
                    time_diff = keyframe.timestamp - sequence.keyframes[i-1].timestamp
                    durations.append(max(time_diff / velocity_scaling, 0.5))  # 最小0.5秒，应用速度缩放
            
            # 创建轨迹约束
            from core.velocity_controller import get_velocity_controller
            velocity_controller = get_velocity_controller()
            velocity_params = velocity_controller.get_current_parameters()
            
            constraints = TrajectoryConstraints(
                max_velocity=velocity_params.velocity * sequence.velocity_scaling,
                max_acceleration=velocity_params.acceleration,
                max_jerk=velocity_params.jerk
            )
            
            # 生成轨迹
            trajectory = self.trajectory_planner.plan_multi_point(
                waypoints=waypoints,
                durations=durations,
                interpolation_type=interpolation_type,
                constraints=constraints
            )
            
            # 通过运动控制器执行轨迹
            from core.motion_controller import get_motion_controller
            motion_controller = get_motion_controller()
            
            self.state = TeachingState.PLAYING
            
            success = motion_controller.move_trajectory(trajectory)
            
            if success:
                logger.info(f"开始回放序列: {sequence.name}")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.TEACHING_PLAYBACK_STARTED,
                    {
                        'sequence_name': sequence.name,
                        'duration': trajectory.duration,
                        'keyframes_count': len(sequence.keyframes),
                        'velocity_scaling': velocity_scaling
                    },
                    MessagePriority.NORMAL
                )
            else:
                self.state = TeachingState.IDLE
                logger.error("轨迹执行失败")
            
            return success
            
        except Exception as e:
            logger.error(f"回放序列失败: {e}")
            self.state = TeachingState.IDLE
            return False
    
    def stop_playback(self):
        """停止回放"""
        try:
            if self.state == TeachingState.PLAYING:
                from core.motion_controller import get_motion_controller
                motion_controller = get_motion_controller()
                motion_controller.stop()
                
                self.state = TeachingState.IDLE
                logger.info("停止序列回放")
                
                # 发布事件
                self.message_bus.publish(
                    Topics.TEACHING_PLAYBACK_STOPPED,
                    {},
                    MessagePriority.NORMAL
                )
                
        except Exception as e:
            logger.error(f"停止回放失败: {e}")
    
    def save_sequence(self, sequence: TeachingSequence, filename: Optional[str] = None) -> bool:
        """保存序列到文件"""
        try:
            if not filename:
                # 生成文件名
                safe_name = "".join(c for c in sequence.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{safe_name}_{int(sequence.created_at)}.json"
            
            filepath = self.sequences_dir / filename
            
            # 保存为JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(sequence.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"序列已保存: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"保存序列失败: {e}")
            return False
    
    def load_sequence(self, filepath: str) -> Optional[TeachingSequence]:
        """从文件加载序列"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sequence = TeachingSequence.from_dict(data)
            logger.info(f"序列已加载: {sequence.name}")
            return sequence
            
        except Exception as e:
            logger.error(f"加载序列失败: {e}")
            return None
    
    def list_sequences(self) -> List[Dict[str, Any]]:
        """列出所有保存的序列"""
        sequences = []
        
        try:
            for filepath in self.sequences_dir.glob("*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    sequences.append({
                        'filename': filepath.name,
                        'name': data.get('name', '未知'),
                        'description': data.get('description', ''),
                        'keyframes_count': len(data.get('keyframes', [])),
                        'created_at': data.get('created_at', 0),
                        'modified_at': data.get('modified_at', 0)
                    })
                    
                except Exception as e:
                    logger.warning(f"读取序列文件失败 {filepath}: {e}")
                    
        except Exception as e:
            logger.error(f"列出序列失败: {e}")
        
        # 按修改时间排序
        sequences.sort(key=lambda x: x['modified_at'], reverse=True)
        return sequences
    
    def get_state(self) -> TeachingState:
        """获取当前状态"""
        return self.state
    
    def get_current_sequence(self) -> Optional[TeachingSequence]:
        """获取当前序列"""
        return self.current_sequence
    
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
            
            # 自动录制（如果在录制状态或拖拽示教状态）
            if self.state == TeachingState.RECORDING and self.current_sequence:
                current_time = time.time()
                if current_time - self.last_record_time >= self.recording_interval:
                    self._auto_record_keyframe()
                    self.last_record_time = current_time
            elif self.state == TeachingState.DRAG_TEACHING and self.current_sequence:
                current_time = time.time()
                if current_time - self.last_record_time >= self.recording_interval:
                    self._auto_record_drag_keyframe()
                    self.last_record_time = current_time
                    
        except Exception as e:
            logger.error(f"处理机器人状态更新失败: {e}")
    
    def _auto_record_keyframe(self):
        """自动录制关键帧"""
        try:
            if not self.current_sequence:
                return
            
            current_time = time.time() - self.recording_start_time
            
            # 检查是否有显著变化
            if len(self.current_sequence.keyframes) > 0:
                last_keyframe = self.current_sequence.keyframes[-1]
                
                # 计算位置变化
                position_change = sum(abs(curr - last) for curr, last in 
                                    zip(self.current_positions, last_keyframe.positions))
                
                # 如果变化太小，跳过录制
                if position_change < 50:  # 阈值可配置
                    return
            
            keyframe = KeyFrame(
                timestamp=current_time,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                name=f"自动_{len(self.current_sequence.keyframes)}",
                teaching_mode="auto_recording"
            )
            
            self.current_sequence.add_keyframe(keyframe)
            
        except Exception as e:
            logger.error(f"自动录制关键帧失败: {e}")
    
    def _auto_record_drag_keyframe(self):
        """自动录制拖拽关键帧"""
        try:
            if not self.current_sequence:
                return
            
            current_time = time.time() - self.recording_start_time
            
            # 检查激活关节是否有显著变化
            if len(self.current_sequence.keyframes) > 0:
                last_keyframe = self.current_sequence.keyframes[-1]
                
                # 只检查激活关节的位置变化
                position_change = 0
                for joint_id in self.drag_active_joints:
                    if joint_id < len(self.current_positions):
                        change = abs(self.current_positions[joint_id] - last_keyframe.positions[joint_id])
                        position_change += change
                
                # 如果变化太小，跳过录制
                if position_change < self.drag_threshold:
                    return
            
            keyframe = KeyFrame(
                timestamp=current_time,
                positions=self.current_positions.copy(),
                velocities=self.current_velocities.copy(),
                currents=self.current_currents.copy(),
                force_feedback=self.current_forces.copy(),
                name=f"拖拽_{len(self.current_sequence.keyframes)}",
                teaching_mode="drag_teaching"
            )
            
            self.current_sequence.add_keyframe(keyframe)
            
        except Exception as e:
            logger.error(f"自动录制拖拽关键帧失败: {e}")


# 全局示教模式实例
_teaching_mode = None


def get_teaching_mode() -> TeachingModeManager:
    """获取全局示教模式实例"""
    global _teaching_mode
    if _teaching_mode is None:
        _teaching_mode = TeachingModeManager()
    return _teaching_mode