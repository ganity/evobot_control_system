"""
关节位置标定管理器

功能：
- 读取0位（归零位置标定）
- 读取最大位置（行程标定）
- 位置转换（用户空间 ↔ 硬件空间）
- 标定数据持久化
- 标定历史管理
"""

import time
import threading
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import yaml
import os

from utils.logger import get_logger, log_performance
from utils.config_manager import get_config_manager
from utils.message_bus import get_message_bus, Topics, MessagePriority
from hardware.serial_manager import get_serial_manager
from hardware.protocol_handler import get_protocol_handler

logger = get_logger(__name__)


@dataclass
class CalibrationData:
    """标定数据"""
    calibrated_at: str
    calibration_method: str = "manual"
    zero_offsets: List[int] = None
    max_positions: List[int] = None
    is_calibrated: bool = False
    operator: str = "user"
    notes: str = ""
    
    def __post_init__(self):
        if self.zero_offsets is None:
            self.zero_offsets = [0] * 10
        if self.max_positions is None:
            self.max_positions = [3000] * 10


@dataclass
class CalibrationResult:
    """标定结果"""
    success: bool
    positions: Optional[List[int]] = None
    error_message: Optional[str] = None
    timestamp: Optional[str] = None


class CalibrationManager:
    """标定管理器"""
    
    def __init__(self):
        """初始化标定管理器"""
        self.config_manager = get_config_manager()
        self.message_bus = get_message_bus()
        self.serial_manager = get_serial_manager()
        self.protocol_handler = get_protocol_handler()
        
        # 标定数据
        self.calibration_data = CalibrationData(
            calibrated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 状态管理
        self.is_calibrating = False
        self.calibration_lock = threading.RLock()
        
        # 配置文件路径
        self.config_dir = "config"
        self.calibration_file = os.path.join(self.config_dir, "calibration_data.yaml")
        self.history_file = os.path.join(self.config_dir, "calibration_history.yaml")
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 加载现有标定数据
        self.load_calibration()
        
        logger.info("标定管理器初始化完成")
    
    def is_system_calibrated(self) -> bool:
        """检查系统是否已标定"""
        return self.calibration_data.is_calibrated
    
    @log_performance
    def read_current_positions(self, timeout: float = 2.0) -> CalibrationResult:
        """
        读取当前所有关节位置
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            标定结果
        """
        with self.calibration_lock:
            try:
                # 检查连接
                if not self.serial_manager.is_connected():
                    return CalibrationResult(
                        success=False,
                        error_message="串口未连接，请先连接硬件"
                    )
                
                logger.info("开始读取当前关节位置")
                
                # 发送状态查询指令
                query_command = self.protocol_handler.encode_status_query()
                self.serial_manager.send_data(query_command)
                
                # 等待接收反馈数据
                positions = []
                start_time = time.time()
                received_joints = set()
                
                while len(received_joints) < 10 and (time.time() - start_time) < timeout:
                    # 检查是否有新的状态数据
                    # 这里需要从消息总线获取最新的关节状态
                    # 实际实现中需要根据具体的协议处理逻辑调整
                    
                    # 模拟接收数据的过程
                    time.sleep(0.1)
                    
                    # 从协议处理器获取最新状态
                    latest_status = self._get_latest_joint_status()
                    if latest_status:
                        for joint_id, position in latest_status.items():
                            if joint_id not in received_joints:
                                received_joints.add(joint_id)
                                if len(positions) <= joint_id:
                                    positions.extend([0] * (joint_id + 1 - len(positions)))
                                positions[joint_id] = position
                
                # 检查是否成功接收所有关节数据
                if len(received_joints) < 10:
                    missing_joints = set(range(10)) - received_joints
                    return CalibrationResult(
                        success=False,
                        error_message=f"读取超时，缺少关节数据: {list(missing_joints)}"
                    )
                
                # 确保位置数组长度为10
                while len(positions) < 10:
                    positions.append(1500)  # 默认中位
                
                logger.info(f"成功读取关节位置: {positions}")
                
                return CalibrationResult(
                    success=True,
                    positions=positions[:10],  # 确保只返回10个关节
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
            except Exception as e:
                logger.error(f"读取关节位置失败: {e}")
                return CalibrationResult(
                    success=False,
                    error_message=f"读取失败: {str(e)}"
                )
    
    def _get_latest_joint_status(self) -> Optional[Dict[int, int]]:
        """获取最新的关节状态（模拟实现）"""
        # 这里应该从实际的硬件状态获取数据
        # 为了演示，返回模拟数据
        return {
            0: 1523, 1: 1487, 2: 1501, 3: 1495, 4: 1512,
            5: 1488, 6: 1502, 7: 1497, 8: 1505, 9: 1493
        }
    
    def set_zero_positions(self, positions: List[int], notes: str = "") -> bool:
        """
        设置归零位置
        
        Args:
            positions: 当前位置作为0位
            notes: 标定备注
            
        Returns:
            是否成功
        """
        with self.calibration_lock:
            try:
                # 验证数据
                if len(positions) != 10:
                    logger.error(f"位置数据长度错误: {len(positions)} != 10")
                    return False
                
                # 验证位置合理性
                for i, pos in enumerate(positions):
                    if pos < 0 or pos > 4095:  # 假设硬件范围0-4095
                        logger.error(f"关节{i}位置超出范围: {pos}")
                        return False
                
                # 更新标定数据
                self.calibration_data.zero_offsets = positions.copy()
                self.calibration_data.calibrated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.calibration_data.notes = notes
                
                logger.info(f"设置归零位置: {positions}")
                
                # 发布标定更新事件
                self.message_bus.publish(
                    Topics.CALIBRATION_UPDATED,
                    {
                        'type': 'zero_positions',
                        'positions': positions,
                        'timestamp': self.calibration_data.calibrated_at
                    },
                    MessagePriority.HIGH
                )
                
                return True
                
            except Exception as e:
                logger.error(f"设置归零位置失败: {e}")
                return False
    
    def set_max_positions(self, positions: List[int], notes: str = "") -> bool:
        """
        设置最大位置
        
        Args:
            positions: 当前位置作为最大位置
            notes: 标定备注
            
        Returns:
            是否成功
        """
        with self.calibration_lock:
            try:
                # 验证数据
                if len(positions) != 10:
                    logger.error(f"位置数据长度错误: {len(positions)} != 10")
                    return False
                
                # 计算相对于0位的最大行程
                max_positions = []
                for i, pos in enumerate(positions):
                    zero_offset = self.calibration_data.zero_offsets[i]
                    max_travel = pos - zero_offset
                    
                    if max_travel <= 0:
                        logger.error(f"关节{i}最大位置小于等于0位: {pos} <= {zero_offset}")
                        return False
                    
                    max_positions.append(max_travel)
                
                # 更新标定数据
                self.calibration_data.max_positions = max_positions
                self.calibration_data.is_calibrated = True
                self.calibration_data.calibrated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if notes:
                    self.calibration_data.notes += f"; {notes}"
                
                logger.info(f"设置最大位置: {max_positions}")
                
                # 发布标定更新事件
                self.message_bus.publish(
                    Topics.CALIBRATION_UPDATED,
                    {
                        'type': 'max_positions',
                        'positions': max_positions,
                        'timestamp': self.calibration_data.calibrated_at
                    },
                    MessagePriority.HIGH
                )
                
                return True
                
            except Exception as e:
                logger.error(f"设置最大位置失败: {e}")
                return False
    
    def apply_calibration(self, user_positions: List[int]) -> List[int]:
        """
        将用户空间位置转换为硬件空间位置
        
        Args:
            user_positions: 用户空间位置（相对于0位）
            
        Returns:
            硬件空间位置（绝对位置）
        """
        hardware_positions = []
        
        for i, user_pos in enumerate(user_positions):
            if i < len(self.calibration_data.zero_offsets):
                hardware_pos = user_pos + self.calibration_data.zero_offsets[i]
            else:
                hardware_pos = user_pos
            
            hardware_positions.append(hardware_pos)
        
        return hardware_positions
    
    def reverse_calibration(self, hardware_positions: List[int]) -> List[int]:
        """
        将硬件空间位置转换为用户空间位置
        
        Args:
            hardware_positions: 硬件空间位置（绝对位置）
            
        Returns:
            用户空间位置（相对于0位）
        """
        user_positions = []
        
        for i, hardware_pos in enumerate(hardware_positions):
            if i < len(self.calibration_data.zero_offsets):
                user_pos = hardware_pos - self.calibration_data.zero_offsets[i]
            else:
                user_pos = hardware_pos
            
            user_positions.append(user_pos)
        
        return user_positions
    
    def get_joint_limits(self, joint_id: int) -> Tuple[int, int]:
        """
        获取关节的用户空间限位
        
        Args:
            joint_id: 关节ID
            
        Returns:
            (最小位置, 最大位置) 在用户空间
        """
        if joint_id < 0 or joint_id >= 10:
            return (0, 3000)
        
        min_pos = 0
        max_pos = self.calibration_data.max_positions[joint_id] if joint_id < len(self.calibration_data.max_positions) else 3000
        
        return (min_pos, max_pos)
    
    def get_hardware_limits(self, joint_id: int) -> Tuple[int, int]:
        """
        获取关节的硬件空间限位
        
        Args:
            joint_id: 关节ID
            
        Returns:
            (最小位置, 最大位置) 在硬件空间
        """
        if joint_id < 0 or joint_id >= 10:
            return (0, 4095)
        
        zero_offset = self.calibration_data.zero_offsets[joint_id] if joint_id < len(self.calibration_data.zero_offsets) else 0
        max_travel = self.calibration_data.max_positions[joint_id] if joint_id < len(self.calibration_data.max_positions) else 3000
        
        hardware_min = zero_offset
        hardware_max = zero_offset + max_travel
        
        return (hardware_min, hardware_max)
    
    def save_calibration(self) -> bool:
        """保存标定数据到配置文件"""
        try:
            # 保存当前标定数据
            calibration_dict = asdict(self.calibration_data)
            
            with open(self.calibration_file, 'w', encoding='utf-8') as f:
                yaml.dump(calibration_dict, f, default_flow_style=False, allow_unicode=True)
            
            # 保存到历史记录
            self._save_to_history()
            
            # 更新主配置文件
            self._update_main_config()
            
            logger.info(f"标定数据已保存到: {self.calibration_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存标定数据失败: {e}")
            return False
    
    def load_calibration(self) -> bool:
        """从配置文件加载标定数据"""
        try:
            if not os.path.exists(self.calibration_file):
                logger.info("标定文件不存在，使用默认标定数据")
                return False
            
            with open(self.calibration_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data:
                self.calibration_data = CalibrationData(**data)
                logger.info("标定数据加载成功")
                return True
            else:
                logger.warning("标定文件为空")
                return False
                
        except Exception as e:
            logger.error(f"加载标定数据失败: {e}")
            return False
    
    def _save_to_history(self):
        """保存到标定历史"""
        try:
            # 加载现有历史
            history = []
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = yaml.safe_load(f)
                    if history_data and 'calibration_records' in history_data:
                        history = history_data['calibration_records']
            
            # 添加当前记录
            current_record = asdict(self.calibration_data)
            history.append(current_record)
            
            # 保持最近20条记录
            if len(history) > 20:
                history = history[-20:]
            
            # 保存历史
            history_data = {'calibration_records': history}
            with open(self.history_file, 'w', encoding='utf-8') as f:
                yaml.dump(history_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("标定历史已更新")
            
        except Exception as e:
            logger.error(f"保存标定历史失败: {e}")
    
    def _update_main_config(self):
        """更新主配置文件中的标定相关配置"""
        try:
            config = self.config_manager.load_config()
            
            # 更新标定部分
            config['calibration'] = asdict(self.calibration_data)
            
            # 更新关节限位
            if 'joints' in config:
                for i, joint_config in enumerate(config['joints']):
                    if i < 10:
                        min_pos, max_pos = self.get_joint_limits(i)
                        hardware_min, hardware_max = self.get_hardware_limits(i)
                        
                        joint_config['limits']['min_position'] = min_pos
                        joint_config['limits']['max_position'] = max_pos
                        joint_config['limits']['hardware_min'] = hardware_min
                        joint_config['limits']['hardware_max'] = hardware_max
            
            # 保存配置
            self.config_manager.save_config(config)
            
            logger.info("主配置文件已更新")
            
        except Exception as e:
            logger.error(f"更新主配置文件失败: {e}")
    
    def get_calibration_summary(self) -> Dict[str, Any]:
        """获取标定摘要信息"""
        return {
            'is_calibrated': self.calibration_data.is_calibrated,
            'calibrated_at': self.calibration_data.calibrated_at,
            'calibration_method': self.calibration_data.calibration_method,
            'operator': self.calibration_data.operator,
            'notes': self.calibration_data.notes,
            'zero_offsets': self.calibration_data.zero_offsets.copy(),
            'max_positions': self.calibration_data.max_positions.copy(),
            'joint_ranges': [self.get_joint_limits(i) for i in range(10)],
            'hardware_ranges': [self.get_hardware_limits(i) for i in range(10)]
        }
    
    def reset_calibration(self):
        """重置标定数据"""
        with self.calibration_lock:
            self.calibration_data = CalibrationData(
                calibrated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            logger.info("标定数据已重置")
    
    def validate_calibration_data(self) -> Tuple[bool, List[str]]:
        """验证标定数据的合理性"""
        errors = []
        
        # 检查数据完整性
        if len(self.calibration_data.zero_offsets) != 10:
            errors.append(f"归零偏移数量错误: {len(self.calibration_data.zero_offsets)} != 10")
        
        if len(self.calibration_data.max_positions) != 10:
            errors.append(f"最大位置数量错误: {len(self.calibration_data.max_positions)} != 10")
        
        # 检查数值合理性
        for i in range(min(10, len(self.calibration_data.zero_offsets))):
            zero_offset = self.calibration_data.zero_offsets[i]
            if zero_offset < 0 or zero_offset > 4095:
                errors.append(f"关节{i}归零偏移超出范围: {zero_offset}")
        
        for i in range(min(10, len(self.calibration_data.max_positions))):
            max_pos = self.calibration_data.max_positions[i]
            if max_pos <= 0 or max_pos > 4095:
                errors.append(f"关节{i}最大位置超出范围: {max_pos}")
        
        # 检查逻辑一致性
        for i in range(min(10, len(self.calibration_data.zero_offsets), len(self.calibration_data.max_positions))):
            zero_offset = self.calibration_data.zero_offsets[i]
            max_pos = self.calibration_data.max_positions[i]
            hardware_max = zero_offset + max_pos
            
            if hardware_max > 4095:
                errors.append(f"关节{i}硬件最大位置超限: {hardware_max} > 4095")
        
        return len(errors) == 0, errors


# 全局标定管理器实例
_calibration_manager = None


def get_calibration_manager() -> CalibrationManager:
    """获取全局标定管理器实例"""
    global _calibration_manager
    if _calibration_manager is None:
        _calibration_manager = CalibrationManager()
    return _calibration_manager