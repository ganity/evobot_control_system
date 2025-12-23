"""
配置管理器

功能：
- 加载和验证YAML配置文件
- 支持配置热更新
- 提供配置默认值
- 配置参数验证
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import copy

from .logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir)
        self.config_cache: Dict[str, Any] = {}
        self.default_config = self._get_default_config()

    def load_config(self, config_file: str = "robot_config.yaml") -> Dict[str, Any]:
        """
        加载配置文件

        Args:
            config_file: 配置文件名

        Returns:
            配置字典
        """
        config_path = self.config_dir / config_file

        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                logger.info(f"成功加载配置文件: {config_path}")
            else:
                logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
                config = copy.deepcopy(self.default_config)

            # 合并默认配置
            config = self._merge_config(self.default_config, config)

            # 验证配置
            self._validate_config(config)

            # 缓存配置
            self.config_cache[config_file] = config

            return config

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            logger.info("使用默认配置")
            return copy.deepcopy(self.default_config)

    def save_config(
        self, config: Dict[str, Any], config_file: str = "robot_config.yaml"
    ) -> bool:
        """
        保存配置文件

        Args:
            config: 配置字典
            config_file: 配置文件名

        Returns:
            是否保存成功
        """
        config_path = self.config_dir / config_file

        try:
            # 确保目录存在
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # 验证配置
            self._validate_config(config)

            # 保存配置
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config, f, default_flow_style=False, allow_unicode=True, indent=2
                )

            # 更新缓存
            self.config_cache[config_file] = copy.deepcopy(config)

            logger.info(f"配置文件保存成功: {config_path}")
            return True

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False

    def get_config_value(
        self, key_path: str, config_file: str = "robot_config.yaml", default: Any = None
    ) -> Any:
        """
        获取配置值

        Args:
            key_path: 配置键路径，如 "robot.name" 或 "joints.0.limits.max_position"
            config_file: 配置文件名
            default: 默认值

        Returns:
            配置值
        """
        if config_file not in self.config_cache:
            self.load_config(config_file)

        config = self.config_cache.get(config_file, {})

        # 解析键路径
        keys = key_path.split(".")
        value = config

        try:
            for key in keys:
                if key.isdigit():
                    # 数组索引
                    value = value[int(key)]
                else:
                    # 字典键
                    value = value[key]
            return value
        except (KeyError, IndexError, TypeError):
            logger.warning(f"配置键不存在: {key_path}，使用默认值: {default}")
            return default

    def set_config_value(
        self, key_path: str, value: Any, config_file: str = "robot_config.yaml"
    ) -> bool:
        """
        设置配置值

        Args:
            key_path: 配置键路径
            value: 配置值
            config_file: 配置文件名

        Returns:
            是否设置成功
        """
        if config_file not in self.config_cache:
            self.load_config(config_file)

        config = self.config_cache.get(config_file, {})

        # 解析键路径
        keys = key_path.split(".")
        current = config

        try:
            # 导航到父级
            for key in keys[:-1]:
                if key.isdigit():
                    current = current[int(key)]
                else:
                    current = current[key]

            # 设置值
            final_key = keys[-1]
            if final_key.isdigit():
                current[int(final_key)] = value
            else:
                current[final_key] = value

            logger.info(f"配置值已更新: {key_path} = {value}")
            return True

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"设置配置值失败: {key_path} = {value}, 错误: {e}")
            return False

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "robot": {
                "name": "EvoBot",
                "version": "1.0",
                "dof": 10,
                "description": "10自由度机器人手臂",
            },
            "communication": {
                "serial": {
                    "port": "COM3",
                    "baudrate": 1000000,
                    "bytesize": 8,
                    "parity": "N",
                    "stopbits": 1,
                    "timeout": 0.1,
                    "buffer_size": 12000,
                },
                "protocol": {
                    "frame_header": 0xFD,
                    "frame_tail": 0xF8,
                    "escape_char": 0xFE,
                    "max_retry": 3,
                    "retry_delay": 0.05,
                },
            },
            "control": {
                "frequency": 200,
                "trajectory_buffer_size": 200,
                "buffer_low_watermark": 50,
                "buffer_high_watermark": 500,
                "default_interpolation": "trapezoidal",
                "enable_feedforward": True,
                "enable_pid": False,
            },
            "trajectory": {
                "default_duration": 1.0,
                "default_max_velocity": 500,
                "default_max_acceleration": 1000,
                "default_max_jerk": 5000,
                "smooth_factor": 0.1,
            },
            "safety": {
                "enable_soft_limits": True,
                "enable_velocity_limits": True,
                "enable_current_limits": True,
                "enable_collision_detection": False,
                "emergency_stop_deceleration": 2000,
            },
            "logging": {
                "enable": True,
                "level": "INFO",
                "log_file": "logs/robot.log",
                "max_file_size": 10485760,
                "backup_count": 5,
                "data_recording": {
                    "enable": False,
                    "format": "csv",
                    "output_dir": "data/",
                    "record_frequency": 50,
                },
            },
            "ui": {
                "theme": "light",
                "language": "zh_CN",
                "update_frequency": 50,
                "plot_history_length": 300,
                "enable_3d_visualization": False,
            },
        }

    def _merge_config(
        self, default: Dict[str, Any], user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并配置，用户配置覆盖默认配置

        Args:
            default: 默认配置
            user: 用户配置

        Returns:
            合并后的配置
        """
        result = copy.deepcopy(default)

        def merge_dict(target: Dict[str, Any], source: Dict[str, Any]):
            for key, value in source.items():
                if (
                    key in target
                    and isinstance(target[key], dict)
                    and isinstance(value, dict)
                ):
                    merge_dict(target[key], value)
                else:
                    target[key] = value

        merge_dict(result, user)
        return result

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        验证配置参数

        Args:
            config: 配置字典

        Raises:
            ValueError: 配置参数无效
        """
        # 验证基本结构
        required_sections = [
            "robot",
            "communication",
            "control",
            "trajectory",
            "safety",
            "logging",
            "ui",
        ]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"缺少必需的配置节: {section}")

        # 验证机器人配置
        robot_config = config["robot"]
        if robot_config.get("dof", 0) != 10:
            raise ValueError("机器人自由度必须为10")

        # 验证通信配置
        comm_config = config["communication"]["serial"]
        if not (9600 <= comm_config.get("baudrate", 0) <= 2000000):
            raise ValueError("波特率必须在9600-2000000范围内")

        # 验证控制配置
        control_config = config["control"]
        if not (10 <= control_config.get("frequency", 0) <= 1000):
            raise ValueError("控制频率必须在10-1000Hz范围内")

        # 验证轨迹配置
        traj_config = config["trajectory"]
        if traj_config.get("default_max_velocity", 0) <= 0:
            raise ValueError("默认最大速度必须大于0")

        if traj_config.get("default_max_acceleration", 0) <= 0:
            raise ValueError("默认最大加速度必须大于0")

        logger.debug("配置验证通过")


# 全局配置管理器实例
_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
