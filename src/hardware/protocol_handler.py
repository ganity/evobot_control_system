"""
RS-485协议处理器

功能：
- 完全兼容现有RS-485通信协议
- 位置控制指令编码 (0x71)
- 状态查询指令编码 (0x72)
- 状态反馈解码 (0x73, 0x74)
- ID配置指令 (0x75)
- 帧编解码和转义处理
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import time

from utils.logger import get_logger, log_performance
from utils.message_bus import get_message_bus, Topics, MessagePriority

logger = get_logger(__name__)


class FrameType(Enum):
    """帧类型定义"""
    POSITION_CONTROL = 0x71  # 位置控制指令
    STATUS_QUERY = 0x72      # 状态查询指令
    ARM_STATUS = 0x73        # 手臂状态反馈
    FINGER_STATUS = 0x74     # 手指状态反馈
    ID_CONFIG = 0x75         # ID配置指令


class BoardID(Enum):
    """板卡ID定义"""
    ARM_BOARD = 0x01    # 手臂板（肩部+肘部）
    WRIST_BOARD = 0x02  # 手腕板（手指+手腕）


@dataclass
class JointStatus:
    """关节状态"""
    joint_id: int
    position: int
    velocity: int
    current: int
    temperature: Optional[int] = None
    error_code: Optional[int] = None


@dataclass
class RobotStatus:
    """机器人状态"""
    frame_type: FrameType
    timestamp: float
    joints: List[JointStatus]
    total_current: int
    board_id: Optional[BoardID] = None


class FrameCodec:
    """帧编解码器 - 处理转义和校验"""
    
    # 协议常量
    FRAME_HEADER = 0xFD
    FRAME_TAIL = 0xF8
    ESCAPE_CHAR = 0xFE
    ESCAPE_CHARS = [0xFD, 0xFE, 0xF8]
    
    @classmethod
    @log_performance
    def encode_frame(cls, frame_data: List[int]) -> bytes:
        """
        编码完整帧 - 包含转义和校验
        
        Args:
            frame_data: 帧数据（不含帧头帧尾）
            
        Returns:
            编码后的完整帧
        """
        # 计算校验和
        checksum = sum(frame_data) & 0xFF
        frame_data.append(checksum)
        
        # 转义处理
        escaped_data = []
        for byte_val in frame_data:
            if byte_val in cls.ESCAPE_CHARS:
                escaped_data.append(cls.ESCAPE_CHAR)
                escaped_data.append((byte_val & 0x0F) + 0x70)
            else:
                escaped_data.append(byte_val)
        
        # 添加帧头和帧尾
        frame = [cls.FRAME_HEADER] + escaped_data + [cls.FRAME_TAIL]
        
        logger.debug(f"编码帧: {len(frame)} 字节, 校验和: 0x{checksum:02X}")
        return bytes(frame)
    
    @classmethod
    @log_performance
    def decode_frame(cls, raw_data: bytes) -> Optional[List[int]]:
        """
        解码完整帧 - 包含反转义和校验验证
        
        Args:
            raw_data: 原始帧数据
            
        Returns:
            解码后的帧数据（不含帧头帧尾和校验）
        """
        if len(raw_data) < 3:
            logger.debug("帧长度不足")
            return None
            
        if raw_data[0] != cls.FRAME_HEADER or raw_data[-1] != cls.FRAME_TAIL:
            logger.debug("帧头或帧尾错误")
            return None
        
        # 去除帧头帧尾
        frame_body = raw_data[1:-1]
        
        # 反转义 - 按照现有程序的逻辑
        unescaped_data = []
        i = 0
        while i < len(frame_body):
            if frame_body[i] == cls.ESCAPE_CHAR and i + 1 < len(frame_body):
                # 反转义：i+0x80 (按照现有程序逻辑)
                original_byte = frame_body[i + 1] + 0x80
                unescaped_data.append(original_byte)
                i += 2
            else:
                unescaped_data.append(frame_body[i])
                i += 1
        
        if len(unescaped_data) < 3:
            logger.debug("反转义后数据长度不足")
            return None
        
        # 校验和验证
        data_part = unescaped_data[:-1]
        received_checksum = unescaped_data[-1]
        calculated_checksum = sum(data_part) & 0xFF
        
        if received_checksum != calculated_checksum:
            logger.warning(f"校验和错误: 接收=0x{received_checksum:02X}, 计算=0x{calculated_checksum:02X}")
            return None
        
        logger.debug(f"解码帧成功: {len(data_part)} 字节数据")
        return data_part


class ProtocolHandler:
    """RS-485协议处理器"""
    
    def __init__(self):
        """初始化协议处理器"""
        self.frame_sequence = 0
        self.message_bus = get_message_bus()
        
    def encode_position_command(self, positions: List[int], speeds: Optional[List[int]] = None) -> bytes:
        """
        编码位置控制指令 (0x71) - 完全兼容现有格式
        
        Args:
            positions: 10个关节的目标位置
            speeds: 10个关节的速度参数（可选，默认为0x08）
            
        Returns:
            编码后的指令帧
        """
        if len(positions) != 10:
            raise ValueError("必须提供10个关节的位置数据")
        
        if speeds is None:
            speeds = [0x08] * 10  # 默认速度参数
        elif len(speeds) != 10:
            raise ValueError("必须提供10个关节的速度数据")
        
        # 构建帧数据
        frame_data = []
        frame_data.append(0x00)  # 长度占位符
        frame_data.append(0x2C)  # 长度 = 44字节
        frame_data.append(0x02)  # 序号
        frame_data.append(0x01)  # 源ID
        frame_data.append(0x00)  # 目标ID
        frame_data.append(FrameType.POSITION_CONTROL.value)  # 指令类型
        
        # 10个关节数据，每个关节4字节
        for i in range(10):
            pos = max(0, min(3000, positions[i]))  # 限制范围
            speed = speeds[i] & 0xFF
            
            frame_data.append(pos >> 8)      # 位置高字节
            frame_data.append(pos & 0xFF)    # 位置低字节
            frame_data.append(speed)         # 速度参数
            frame_data.append(0x00)          # 保留字节
        
        encoded_frame = FrameCodec.encode_frame(frame_data)
        
        logger.debug(f"编码位置控制指令: {positions}")
        return encoded_frame
    
    def encode_query_command(self, board_id: BoardID) -> bytes:
        """
        编码状态查询指令 (0x72) - 完全兼容现有格式
        
        Args:
            board_id: 板卡ID
            
        Returns:
            编码后的查询帧
        """
        frame_data = []
        frame_data.append(0x00)  # 长度占位符
        frame_data.append(0x05)  # 长度 = 5字节
        frame_data.append(0x02)  # 序号
        frame_data.append(0x01)  # 源ID
        frame_data.append(0x00)  # 目标ID
        frame_data.append(FrameType.STATUS_QUERY.value)  # 指令类型
        frame_data.append(board_id.value)  # 板ID
        
        encoded_frame = FrameCodec.encode_frame(frame_data)
        
        logger.debug(f"编码状态查询指令: 板ID={board_id.name}")
        return encoded_frame
    
    def encode_id_config_command(self, board_type: int, register_addr: int, 
                                motor_id: int, data2: int = 0x00) -> bytes:
        """
        编码ID配置指令 (0x75) - 兼容现有格式
        
        Args:
            board_type: 板类型 (0x01=肩部, 0x02=肘部, 0x03=手腕, 0x04=手指)
            register_addr: 寄存器地址
            motor_id: 电机ID
            data2: 附加数据
            
        Returns:
            编码后的配置帧
        """
        frame_data = []
        frame_data.append(0x00)  # 长度占位符
        frame_data.append(0x09)  # 长度 = 9字节
        frame_data.append(0x02)  # 序号
        frame_data.append(0x01)  # 源ID
        frame_data.append(0x00)  # 目标ID
        frame_data.append(FrameType.ID_CONFIG.value)  # 指令类型
        frame_data.append(board_type)     # 板类型
        frame_data.append(0x01)           # 写入个数
        frame_data.append(register_addr)  # 寄存器地址
        frame_data.append(motor_id)       # 电机ID
        frame_data.append(data2)          # 附加数据
        
        encoded_frame = FrameCodec.encode_frame(frame_data)
        
        logger.debug(f"编码ID配置指令: 板类型={board_type}, 电机ID={motor_id}")
        return encoded_frame
    
    @log_performance
    def decode_status_response(self, raw_data: bytes) -> Optional[RobotStatus]:
        """
        解码状态反馈 - 支持0x73和0x74
        
        Args:
            raw_data: 原始帧数据
            
        Returns:
            机器人状态对象
        """
        frame_data = FrameCodec.decode_frame(raw_data)
        if not frame_data or len(frame_data) < 6:
            return None
        
        try:
            # 解析帧头信息
            length = frame_data[1]
            sequence = frame_data[2]
            frame_type_value = frame_data[5]
            
            # 检查帧类型
            if frame_type_value == FrameType.ARM_STATUS.value:
                return self._decode_arm_status(frame_data[6:])
            elif frame_type_value == FrameType.FINGER_STATUS.value:
                return self._decode_finger_status(frame_data[6:])
            else:
                logger.warning(f"未知帧类型: 0x{frame_type_value:02X}")
                return None
                
        except Exception as e:
            logger.error(f"解码状态反馈失败: {e}")
            return None
    
    def _decode_arm_status(self, data: List[int]) -> RobotStatus:
        """
        解码手臂状态 (0x73) - 4个关节 + 总电流
        
        Args:
            data: 状态数据
            
        Returns:
            机器人状态
        """
        if len(data) < 26:  # 4*6 + 2 = 26字节
            raise ValueError("手臂状态数据长度不足")
        
        joints = []
        
        # 解析4个关节数据
        for i in range(4):
            offset = i * 6
            joint = JointStatus(
                joint_id=6 + i,  # 关节6-9 (肩部1,2 + 肘部1,2)
                position=(data[offset] << 8) | data[offset + 1],
                velocity=(data[offset + 2] << 8) | data[offset + 3],
                current=(data[offset + 4] << 8) | data[offset + 5]
            )
            joints.append(joint)
        
        # 总电流
        total_current = (data[24] << 8) | data[25]
        
        status = RobotStatus(
            frame_type=FrameType.ARM_STATUS,
            timestamp=time.time(),
            joints=joints,
            total_current=total_current,
            board_id=BoardID.ARM_BOARD
        )
        
        logger.debug(f"解码手臂状态: {len(joints)}个关节, 总电流={total_current}mA")
        
        # 发布状态更新事件
        self.message_bus.publish(
            Topics.ROBOT_STATE,
            {
                'type': 'arm_status',
                'joints': [
                    {
                        'id': j.joint_id,
                        'position': j.position,
                        'velocity': j.velocity,
                        'current': j.current
                    } for j in joints
                ],
                'total_current': total_current
            },
            MessagePriority.NORMAL
        )
        
        return status
    
    def _decode_finger_status(self, data: List[int]) -> RobotStatus:
        """
        解码手指状态 (0x74) - 6个关节 + 总电流
        
        Args:
            data: 状态数据
            
        Returns:
            机器人状态
        """
        if len(data) < 38:  # 6*6 + 2 = 38字节
            raise ValueError("手指状态数据长度不足")
        
        joints = []
        
        # 解析6个关节数据 (5个手指 + 1个手腕)
        for i in range(6):
            offset = i * 6
            joint = JointStatus(
                joint_id=i,  # 关节0-5 (拇指,食指,中指,无名指,小指,手腕)
                position=(data[offset] << 8) | data[offset + 1],
                velocity=(data[offset + 2] << 8) | data[offset + 3],
                current=(data[offset + 4] << 8) | data[offset + 5]
            )
            joints.append(joint)
        
        # 总电流
        total_current = (data[36] << 8) | data[37]
        
        status = RobotStatus(
            frame_type=FrameType.FINGER_STATUS,
            timestamp=time.time(),
            joints=joints,
            total_current=total_current,
            board_id=BoardID.WRIST_BOARD
        )
        
        logger.debug(f"解码手指状态: {len(joints)}个关节, 总电流={total_current}mA")
        
        # 发布状态更新事件
        self.message_bus.publish(
            Topics.ROBOT_STATE,
            {
                'type': 'finger_status',
                'joints': [
                    {
                        'id': j.joint_id,
                        'position': j.position,
                        'velocity': j.velocity,
                        'current': j.current
                    } for j in joints
                ],
                'total_current': total_current
            },
            MessagePriority.NORMAL
        )
        
        return status
    
    def get_joint_names(self) -> Dict[int, str]:
        """获取关节名称映射"""
        return {
            0: "拇指",
            1: "食指", 
            2: "中指",
            3: "无名指",
            4: "小指",
            5: "手腕",
            6: "肩部1",
            7: "肩部2", 
            8: "肘部1",
            9: "肘部2"
        }
    
    def validate_positions(self, positions: List[int]) -> List[int]:
        """
        验证和限制关节位置
        
        Args:
            positions: 关节位置列表
            
        Returns:
            验证后的位置列表
        """
        validated = []
        for i, pos in enumerate(positions):
            # 限制在0-3000范围内
            limited_pos = max(0, min(3000, pos))
            if limited_pos != pos:
                logger.warning(f"关节{i}位置超限: {pos} -> {limited_pos}")
            validated.append(limited_pos)
        
        return validated


# 全局协议处理器实例
_protocol_handler = None


def get_protocol_handler() -> ProtocolHandler:
    """获取全局协议处理器实例"""
    global _protocol_handler
    if _protocol_handler is None:
        _protocol_handler = ProtocolHandler()
    return _protocol_handler