"""
协议处理器测试
"""

import pytest
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from hardware.protocol_handler import ProtocolHandler, FrameCodec, FrameType, BoardID


class TestFrameCodec:
    """帧编解码器测试"""
    
    def test_encode_decode_frame(self):
        """测试帧编码和解码"""
        # 测试数据（不包含校验和）
        test_data = [0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x01]
        
        # 编码
        encoded = FrameCodec.encode_frame(test_data.copy())  # 使用副本，因为encode_frame会修改原数据
        
        # 验证帧头帧尾
        assert encoded[0] == 0xFD  # 帧头
        assert encoded[-1] == 0xF8  # 帧尾
        
        # 解码
        decoded = FrameCodec.decode_frame(encoded)
        
        # 验证解码结果（不包含校验和）
        assert decoded == test_data
    
    def test_escape_handling(self):
        """测试转义处理"""
        # 包含需要转义的字符（不包含校验和）
        test_data = [0xFD, 0xFE, 0xF8, 0x01, 0x02]
        
        # 编码
        encoded = FrameCodec.encode_frame(test_data.copy())  # 使用副本
        
        # 解码
        decoded = FrameCodec.decode_frame(encoded)
        
        # 验证转义处理正确
        assert decoded == test_data
    
    def test_checksum_validation(self):
        """测试校验和验证"""
        # 正确的帧
        test_data = [0x00, 0x05, 0x02, 0x01, 0x00, 0x72, 0x01]
        encoded = FrameCodec.encode_frame(test_data.copy())  # 使用副本
        
        # 验证正确帧可以解码
        decoded = FrameCodec.decode_frame(encoded)
        assert decoded is not None
        
        # 损坏校验和
        corrupted = bytearray(encoded)
        corrupted[-2] = 0x00  # 修改校验和
        
        # 验证损坏的帧无法解码
        decoded = FrameCodec.decode_frame(bytes(corrupted))
        assert decoded is None


class TestProtocolHandler:
    """协议处理器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.handler = ProtocolHandler()
    
    def test_encode_position_command(self):
        """测试位置控制指令编码"""
        positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        
        # 编码指令
        encoded = self.handler.encode_position_command(positions)
        
        # 验证帧格式
        assert encoded[0] == 0xFD  # 帧头
        assert encoded[-1] == 0xF8  # 帧尾
        
        # 解码验证
        decoded = FrameCodec.decode_frame(encoded)
        assert decoded is not None
        assert decoded[5] == FrameType.POSITION_CONTROL.value  # 指令类型
    
    def test_encode_query_command(self):
        """测试状态查询指令编码"""
        # 编码手臂查询指令
        encoded = self.handler.encode_query_command(BoardID.ARM_BOARD)
        
        # 验证帧格式
        assert encoded[0] == 0xFD  # 帧头
        assert encoded[-1] == 0xF8  # 帧尾
        
        # 解码验证
        decoded = FrameCodec.decode_frame(encoded)
        assert decoded is not None
        assert decoded[5] == FrameType.STATUS_QUERY.value  # 指令类型
        assert decoded[6] == BoardID.ARM_BOARD.value  # 板ID
    
    def test_encode_id_config_command(self):
        """测试ID配置指令编码"""
        # 编码ID配置指令
        encoded = self.handler.encode_id_config_command(
            board_type=0x04,  # 手指板
            register_addr=0x07,
            motor_id=0x01,
            data2=0x00
        )
        
        # 验证帧格式
        assert encoded[0] == 0xFD  # 帧头
        assert encoded[-1] == 0xF8  # 帧尾
        
        # 解码验证
        decoded = FrameCodec.decode_frame(encoded)
        assert decoded is not None
        assert decoded[5] == FrameType.ID_CONFIG.value  # 指令类型
    
    def test_validate_positions(self):
        """测试位置验证"""
        # 测试正常位置
        positions = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        validated = self.handler.validate_positions(positions)
        assert validated == positions
        
        # 测试超限位置
        positions = [-100, 5000, 1500, 2000, 500, 600, 700, 800, 900, 1000]
        validated = self.handler.validate_positions(positions)
        assert validated[0] == 0     # 负数限制为0
        assert validated[1] == 3000  # 超过3000限制为3000
    
    def test_get_joint_names(self):
        """测试关节名称映射"""
        names = self.handler.get_joint_names()
        
        # 验证关节数量
        assert len(names) == 10
        
        # 验证特定关节名称
        assert names[0] == "拇指"
        assert names[5] == "手腕"
        assert names[6] == "肩部1"