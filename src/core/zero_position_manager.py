"""
零位管理器

功能：
- 零位录制和保存
- 零位加载和应用
- 零位微调
- 归零操作
"""

import os
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from utils.logger import get_logger
from utils.config_manager import get_config_manager

logger = get_logger(__name__)


@dataclass
class ZeroPosition:
    """零位数据"""
    joint_id: int
    position: int
    name: str = ""
    description: str = ""
    timestamp: str = ""


@dataclass
class ZeroPositionSet:
    """零位集合"""
    name: str
    description: str
    positions: List[ZeroPosition]
    created_time: str
    modified_time: str
    is_default: bool = False


class ZeroPositionManager:
    """零位管理器"""
    
    def __init__(self):
        """初始化零位管理器"""
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_config()
        
        # 零位配置文件路径
        self.zero_config_file = Path("config/zero_positions.yaml")
        
        # 当前零位数据
        self.current_zero_positions: Dict[int, ZeroPosition] = {}
        self.zero_position_sets: Dict[str, ZeroPositionSet] = {}
        
        # 默认零位（中位）
        self.default_zero_positions = self._create_default_zero_positions()
        
        # 加载零位配置
        self.load_zero_positions()
        
        logger.info("零位管理器初始化完成")
    
    def _create_default_zero_positions(self) -> Dict[int, ZeroPosition]:
        """创建默认零位（中位）"""
        default_positions = {}
        joints_config = self.config.get('joints', [])
        
        for joint_config in joints_config:
            joint_id = joint_config.get('id', 0)
            joint_name = joint_config.get('name', f'Joint {joint_id}')
            limits = joint_config.get('limits', {})
            
            # 计算中位
            min_pos = limits.get('min_position', 0)
            max_pos = limits.get('max_position', 3000)
            center_pos = (min_pos + max_pos) // 2
            
            default_positions[joint_id] = ZeroPosition(
                joint_id=joint_id,
                position=center_pos,
                name=joint_name,
                description="默认中位"
            )
        
        return default_positions
    
    def load_zero_positions(self):
        """加载零位配置"""
        try:
            if self.zero_config_file.exists():
                with open(self.zero_config_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                # 解析零位集合
                if 'zero_position_sets' in data:
                    for set_name, set_data in data['zero_position_sets'].items():
                        positions = []
                        for pos_data in set_data.get('positions', []):
                            positions.append(ZeroPosition(**pos_data))
                        
                        zero_set = ZeroPositionSet(
                            name=set_data.get('name', set_name),
                            description=set_data.get('description', ''),
                            positions=positions,
                            created_time=set_data.get('created_time', ''),
                            modified_time=set_data.get('modified_time', ''),
                            is_default=set_data.get('is_default', False)
                        )
                        
                        self.zero_position_sets[set_name] = zero_set
                
                # 加载当前零位
                if 'current_zero_positions' in data:
                    for pos_data in data['current_zero_positions']:
                        zero_pos = ZeroPosition(**pos_data)
                        self.current_zero_positions[zero_pos.joint_id] = zero_pos
                
                logger.info(f"零位配置加载成功: {len(self.current_zero_positions)}个关节")
            else:
                # 使用默认零位
                self.current_zero_positions = self.default_zero_positions.copy()
                logger.info("使用默认零位配置")
                
        except Exception as e:
            logger.error(f"零位配置加载失败: {e}")
            # 使用默认零位
            self.current_zero_positions = self.default_zero_positions.copy()
    
    def save_zero_positions(self):
        """保存零位配置"""
        try:
            # 确保配置目录存在
            self.zero_config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备保存数据
            data = {
                'current_zero_positions': [
                    asdict(pos) for pos in self.current_zero_positions.values()
                ],
                'zero_position_sets': {}
            }
            
            # 保存零位集合
            for set_name, zero_set in self.zero_position_sets.items():
                data['zero_position_sets'][set_name] = {
                    'name': zero_set.name,
                    'description': zero_set.description,
                    'positions': [asdict(pos) for pos in zero_set.positions],
                    'created_time': zero_set.created_time,
                    'modified_time': zero_set.modified_time,
                    'is_default': zero_set.is_default
                }
            
            # 写入文件
            with open(self.zero_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("零位配置保存成功")
            
        except Exception as e:
            logger.error(f"零位配置保存失败: {e}")
            raise
    
    def record_current_positions(self, current_positions: List[int], 
                               set_name: str = "recorded", 
                               description: str = "录制的零位") -> bool:
        """
        录制当前位置为零位
        
        Args:
            current_positions: 当前各关节位置
            set_name: 零位集合名称
            description: 描述
            
        Returns:
            是否成功
        """
        try:
            import datetime
            
            # 创建零位数据
            zero_positions = []
            joints_config = self.config.get('joints', [])
            
            for i, position in enumerate(current_positions):
                if i < len(joints_config):
                    joint_config = joints_config[i]
                    joint_id = joint_config.get('id', i)
                    joint_name = joint_config.get('name', f'Joint {i}')
                    
                    zero_pos = ZeroPosition(
                        joint_id=joint_id,
                        position=position,
                        name=joint_name,
                        description=f"{joint_name}零位",
                        timestamp=datetime.datetime.now().isoformat()
                    )
                    
                    zero_positions.append(zero_pos)
                    # 更新当前零位
                    self.current_zero_positions[joint_id] = zero_pos
            
            # 创建零位集合
            zero_set = ZeroPositionSet(
                name=set_name,
                description=description,
                positions=zero_positions,
                created_time=datetime.datetime.now().isoformat(),
                modified_time=datetime.datetime.now().isoformat(),
                is_default=True
            )
            
            # 保存零位集合
            self.zero_position_sets[set_name] = zero_set
            
            # 保存到文件
            self.save_zero_positions()
            
            logger.info(f"零位录制成功: {set_name}, {len(zero_positions)}个关节")
            return True
            
        except Exception as e:
            logger.error(f"零位录制失败: {e}")
            return False
    
    def get_zero_positions(self) -> List[int]:
        """获取当前零位"""
        positions = []
        
        for i in range(10):  # 10个关节
            if i in self.current_zero_positions:
                positions.append(self.current_zero_positions[i].position)
            else:
                # 使用默认中位
                if i in self.default_zero_positions:
                    positions.append(self.default_zero_positions[i].position)
                else:
                    positions.append(1500)  # 兜底值
        
        return positions
    
    def set_zero_position(self, joint_id: int, position: int) -> bool:
        """
        设置单个关节的零位
        
        Args:
            joint_id: 关节ID
            position: 零位位置
            
        Returns:
            是否成功
        """
        try:
            if joint_id in self.current_zero_positions:
                self.current_zero_positions[joint_id].position = position
            else:
                # 创建新的零位
                joints_config = self.config.get('joints', [])
                joint_name = f'Joint {joint_id}'
                
                for joint_config in joints_config:
                    if joint_config.get('id') == joint_id:
                        joint_name = joint_config.get('name', joint_name)
                        break
                
                self.current_zero_positions[joint_id] = ZeroPosition(
                    joint_id=joint_id,
                    position=position,
                    name=joint_name,
                    description=f"{joint_name}零位"
                )
            
            # 保存配置
            self.save_zero_positions()
            
            logger.info(f"关节{joint_id}零位设置为: {position}")
            return True
            
        except Exception as e:
            logger.error(f"设置关节{joint_id}零位失败: {e}")
            return False
    
    def adjust_zero_position(self, joint_id: int, offset: int) -> bool:
        """
        微调零位
        
        Args:
            joint_id: 关节ID
            offset: 偏移量
            
        Returns:
            是否成功
        """
        try:
            if joint_id in self.current_zero_positions:
                current_pos = self.current_zero_positions[joint_id].position
                new_pos = current_pos + offset
                
                # 检查限位
                joints_config = self.config.get('joints', [])
                for joint_config in joints_config:
                    if joint_config.get('id') == joint_id:
                        limits = joint_config.get('limits', {})
                        min_pos = limits.get('min_position', 0)
                        max_pos = limits.get('max_position', 3000)
                        
                        new_pos = max(min_pos, min(max_pos, new_pos))
                        break
                
                return self.set_zero_position(joint_id, new_pos)
            else:
                logger.warning(f"关节{joint_id}零位不存在，无法微调")
                return False
                
        except Exception as e:
            logger.error(f"微调关节{joint_id}零位失败: {e}")
            return False
    
    def load_zero_position_set(self, set_name: str) -> bool:
        """
        加载零位集合
        
        Args:
            set_name: 零位集合名称
            
        Returns:
            是否成功
        """
        try:
            if set_name in self.zero_position_sets:
                zero_set = self.zero_position_sets[set_name]
                
                # 更新当前零位
                self.current_zero_positions.clear()
                for zero_pos in zero_set.positions:
                    self.current_zero_positions[zero_pos.joint_id] = zero_pos
                
                # 保存配置
                self.save_zero_positions()
                
                logger.info(f"零位集合加载成功: {set_name}")
                return True
            else:
                logger.warning(f"零位集合不存在: {set_name}")
                return False
                
        except Exception as e:
            logger.error(f"加载零位集合失败: {e}")
            return False
    
    def get_zero_position_sets(self) -> Dict[str, ZeroPositionSet]:
        """获取所有零位集合"""
        return self.zero_position_sets.copy()
    
    def delete_zero_position_set(self, set_name: str) -> bool:
        """
        删除零位集合
        
        Args:
            set_name: 零位集合名称
            
        Returns:
            是否成功
        """
        try:
            if set_name in self.zero_position_sets:
                del self.zero_position_sets[set_name]
                self.save_zero_positions()
                logger.info(f"零位集合删除成功: {set_name}")
                return True
            else:
                logger.warning(f"零位集合不存在: {set_name}")
                return False
                
        except Exception as e:
            logger.error(f"删除零位集合失败: {e}")
            return False


# 全局零位管理器实例
_zero_position_manager = None


def get_zero_position_manager() -> ZeroPositionManager:
    """获取零位管理器实例"""
    global _zero_position_manager
    if _zero_position_manager is None:
        _zero_position_manager = ZeroPositionManager()
    return _zero_position_manager